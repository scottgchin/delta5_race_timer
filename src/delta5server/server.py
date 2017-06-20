'''Delta5 race timer server script'''

import os
import sys
from datetime import datetime

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy

import gevent
import gevent.monkey
gevent.monkey.patch_all()

sys.path.append('../delta5interface')
from Delta5Interface import get_hardware_interface

from Delta5Race import get_race_state

APP = Flask(__name__, static_url_path='/static')
APP.config['SECRET_KEY'] = 'secret!'
SOCKET_IO = SocketIO(APP, async_mode='gevent')

HEARTBEAT_THREAD = None

BASEDIR = os.path.abspath(os.path.dirname(__file__))
APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASEDIR, 'database.db')
APP.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
DB = SQLAlchemy(APP)

INTERFACE = get_hardware_interface()
RACE = get_race_state() # For storing race management variables

PROGRAM_START = datetime.now()
RACE_START = datetime.now() # Updated on race start commands

#
# Database Models
#

class Pilot(DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    pilot_id = DB.Column(DB.Integer, unique=True, nullable=False)
    callsign = DB.Column(DB.String(80), unique=True, nullable=False)
    name = DB.Column(DB.String(120), nullable=False)

    def __repr__(self):
        return '<Pilot %r>' % self.pilot_id

class Heat(DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    heat_id = DB.Column(DB.Integer, nullable=False)
    node_index = DB.Column(DB.Integer, nullable=False)
    pilot_id = DB.Column(DB.Integer, nullable=False)

    def __repr__(self):
        return '<Heat %r>' % self.heat_id

class CurrentLap(DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    node_index = DB.Column(DB.Integer, nullable=False)
    pilot_id = DB.Column(DB.Integer, nullable=False)
    lap_id = DB.Column(DB.Integer, nullable=False)
    lap_time_stamp = DB.Column(DB.Integer, nullable=False)
    lap_time = DB.Column(DB.Integer, nullable=False)

    def __repr__(self):
        return '<CurrentLap %r>' % self.pilot_id

class SavedRace(DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    round_id = DB.Column(DB.Integer, nullable=False)
    heat_id = DB.Column(DB.Integer, nullable=False)
    pilot_id = DB.Column(DB.Integer, nullable=False)
    lap_time = DB.Column(DB.Integer, nullable=False)

    def __repr__(self):
        return '<SavedRace %r>' % self.round_id

class Frequency(DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    band = DB.Column(DB.Integer, nullable=False)
    channel = DB.Column(DB.Integer, unique=True, nullable=False)
    frequency = DB.Column(DB.Integer, nullable=False)

    def __repr__(self):
        return '<Frequency %r>' % self.frequency

#
# Routes
#

@APP.route('/')
def index():
    '''Route to round summary page.'''
    return render_template('rounds.html', async_mode=SOCKET_IO.async_mode)

@APP.route('/race')
def race():
    '''Route to race management page.'''
    return render_template('race.html', async_mode=SOCKET_IO.async_mode, \
        num_nodes=RACE.num_nodes, current_heat=RACE.current_heat, heats=Heat)

@APP.route('/settings')
def settings():
    '''Route to settings page.'''
    return render_template('settings.html', async_mode=SOCKET_IO.async_mode, \
        num_nodes=RACE.num_nodes, pilots=Pilot, frequencies=Frequency, heats=Heat)

# Debug Routes

@APP.route('/database')
def database():
    '''Route to database page.'''
    return render_template('database.html', \
        pilots=Pilot, heats=Heat, currentlaps=CurrentLap, \
        savedraces=SavedRace, frequencies=Frequency, )

#
# Socket IO Events
#

@SOCKET_IO.on('connect')
def connect_handler():
    '''Starts the delta 5 interface and starts a CURRENT_RSSI thread to emit node data.'''
    server_log('Client connected')
    INTERFACE.start()
    global HEARTBEAT_THREAD
    if HEARTBEAT_THREAD is None:
        HEARTBEAT_THREAD = gevent.spawn(heartbeat_thread_function)
    emit_node_data()
    # emit_current_laps()

@SOCKET_IO.on('disconnect')
def disconnect_handler():
    '''Print disconnect event.'''
    server_log('Client disconnected')

# Settings socket io events

@SOCKET_IO.on('set_frequency')
def on_set_frequency(data):
    '''Gets node index and frequency to update a node.'''
    node_index = data['node']
    frequency = data['frequency']
    server_log('Set Frequency: Node {0} Frequency {1}'.format(node_index, frequency))
    INTERFACE.set_frequency(node_index, frequency)
    emit_node_data()

@SOCKET_IO.on('set_pilot_position')
def on_set_pilot_position(data):
    '''Gets heat index, node index, and pilot it to update database.'''
    heat = data['heat']
    node = data['node']
    pilot = data['pilot']
    server_log('Set Pilot Position: Heat {0} Node {1} Pilot {2}'.format(heat, node, pilot))
    db_update = Heat.query.filter_by(heat_id=heat, node_index=node).first()
    db_update.pilot_id = pilot
    DB.session.commit()

# Race management socket io events

@SOCKET_IO.on('start_race')
def on_start_race():
    '''Starts the race and the timer counting up, no defined finish.'''
    INTERFACE.enable_calibration_mode() # Prep nodes to reset triggers on next pass
    gevent.sleep(0.500) # Make this random 2 to 5 seconds
    SOCKET_IO.emit('start_timer') # Loop back to race page to start the timer counting up
    RACE.race_status = True # To enable registering passed laps
    RACE_START = datetime.now() # Update the race start time stamp
    server_log('Race started at {0}'.format(RACE_START))
    emit_node_data() # Just to see the values on the start line

@SOCKET_IO.on('start_race_2_min')
def on_start_race_2_min():
    '''Starts the race with a two minute countdown clock.'''
    INTERFACE.enable_calibration_mode() # Prep nodes to reset triggers on next pass
    gevent.sleep(0.500) # Make this random 2 to 5 seconds
    SOCKET_IO.emit('start_timer_2min') # Loop back to race page to start a 2 min countdown
    RACE.race_status = True # To enable registering passed laps
    RACE_START = datetime.now() # Update the race start time stamp
    server_log('Race started at {0}'.format(RACE_START))
    emit_node_data() # Just to see the values on the start line

@SOCKET_IO.on('stop_race')
def on_race_status():
    '''Stops the racing and stops looking for laps.'''
    server_log('Race stopped')
    RACE.race_status = False # To stop registering passed laps

@SOCKET_IO.on('save_laps')
def on_save_laps():
    '''Command to save current laps to the database and clear the current laps.'''

@SOCKET_IO.on('clear_laps')
def on_clear_laps():
    '''Command to clear the current laps due to false start or practice.'''

# Socket io emit functions

def emit_node_data():
    '''Emits node data.'''
    SOCKET_IO.emit('node_data', {
        'frequency': [node.frequency for node in INTERFACE.nodes],
        'channel': [Frequency.query.filter_by(frequency=node.frequency).first().channel \
            for node in INTERFACE.nodes],
        'trigger_rssi': [node.trigger_rssi for node in INTERFACE.nodes],
        'peak_rssi': [node.peak_rssi for node in INTERFACE.nodes]
    })

def emit_current_laps():
    '''Emits current_laps json.'''
    current_laps = []
    # for node in DB.session.query(CurrentLap.node_index).distinct():
    for node in range(RACE.num_nodes):
        node_laps = []
        node_lap_times = []
        for lap in CurrentLap.query.filter_by(node_index=node).all():
            node_laps.append(lap.lap_id)
            node_lap_times.append(time_format(lap.lap_time))
        current_laps.append({'lap_id': node_laps, 'lap_time': node_lap_times})
    current_laps = {'node_index': current_laps}
    SOCKET_IO.emit('current_laps', current_laps)

#
# Program Functions
#

def heartbeat_thread_function():
    '''Emits 'heartbeat' with json node data.'''
    while True:
        SOCKET_IO.emit('heartbeat', INTERFACE.get_heartbeat_json())
        gevent.sleep(0.500)

def ms_from_race_start():
    '''Return milliseconds since race start.'''
    delta_time = datetime.now() - RACE_START
    milli_sec = (delta_time.days * 24 * 60 * 60 + delta_time.seconds) \
        * 1000 + delta_time.microseconds / 1000.0
    return milli_sec

def ms_from_program_start():
    '''Returns the elapsed milliseconds since the start of the program.'''
    delta_time = datetime.now() - PROGRAM_START
    milli_sec = (delta_time.days * 24 * 60 * 60 + delta_time.seconds) \
        * 1000 + delta_time.microseconds / 1000.0
    return milli_sec

def time_format(millis):
    '''Convert milliseconds to 00:00.000'''
    millis = int(millis)
    minutes = millis / 60000
    over = millis % 60000
    seconds = over / 1000
    over = over % 1000
    milliseconds = over
    return '{0:02d}:{1:02d}.{2:03d}'.format(minutes, seconds, milliseconds)

def pass_record_callback(node, ms_since_lap):
    '''Logs and emits a completed lap.'''
    server_log('Raw pass record: Node: {0}, MS Since Lap: {1}'.format(node.index, ms_since_lap))
    emit_node_data()

    if RACE.race_status:
        # Get the current pilot id on the node
        # print 'node_index {0}'.format(node_index)
        pilot_id = Heat.query.filter_by( \
            heat_id=RACE.current_heat, node_index=node.index).first().pilot_id
        # print 'pilot_id {0}'.format(pilot_id)

        # Calculate the lap time stamp, milliseconds since start of race
        lap_time_stamp = ms_from_race_start() - ms_since_lap
        # print 'lap_time_stamp {0}'.format(lap_time_stamp)

        # Get the last completed lap from the database
        last_lap_id = DB.session.query(DB.func.max(CurrentLap.lap_id)) \
            .filter_by(node_index=node.index).scalar()
        print 'last_lap_id {0}'.format(last_lap_id)

        # Instead of lap_id query the database for an existing lap zero
        if last_lap_id is None: # If no laps this is the first pass
            # Lap zero represents the time from the launch pad to flying through the gate
            lap_time = lap_time_stamp
            lap_id = 0
        else: # Else this is a normal completed lap
            # Find the time stamp of the last lap completed
            last_lap_time_stamp = CurrentLap.query.filter_by( \
                node_index=node.index, lap_id=last_lap_id).first().lap_time_stamp
            print 'last_lap_time_stamp {0}'.format(last_lap_time_stamp)
            # New lap time is the difference between the current time stamp and the last
            lap_time = lap_time_stamp - last_lap_time_stamp
            lap_id = last_lap_id + 1
        print 'lap_time {0}'.format(lap_time)

        # Add the new lap to the database
        DB.session.add(CurrentLap(node_index=node.index, pilot_id=pilot_id, lap_id=lap_id, \
            lap_time_stamp=lap_time_stamp, lap_time=lap_time))
        DB.session.commit()

        server_log('Pass record: Node: {0}, Lap: {1}, Lap time: {2}' \
            .format(node.index, lap_id, time_format(lap_time)))
        emit_current_laps()

INTERFACE.pass_record_callback = pass_record_callback

def server_log(message):
    '''Messages emitted from the server script.'''
    print message
    SOCKET_IO.emit('hardware_log', message)

def hardware_log_callback(message):
    '''Message emitted from the delta 5 interface class.'''
    print message
    SOCKET_IO.emit('hardware_log', message)

INTERFACE.hardware_log_callback = hardware_log_callback

def default_frequencies():
    '''Set each nodes frequency, use imd frequncies for 6 or less and race band for 7 or 8'''
    server_log('Setting default frequencies')
    frequencies_imd_5_6 = [5685, 5760, 5800, 5860, 5905, 5645]
    frequencies_raceband = [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917]
    for index, node in enumerate(INTERFACE.nodes):
        gevent.sleep(0.100)
        if RACE.num_nodes < 7:
            INTERFACE.set_frequency(index, frequencies_imd_5_6[index])
        else:
            INTERFACE.set_frequency(index, frequencies_raceband[index])

#
# Program Initialize
#

RACE.num_nodes = len(INTERFACE.nodes)
print 'Number of nodes found: {0}'.format(RACE.num_nodes)

gevent.sleep(0.500) # Delay to get I2C addresses
default_frequencies()
INTERFACE.set_calibration_threshold_global(80)

DB.session.query(CurrentLap).delete() # Clear out the current laps table
DB.session.commit()


# Test data
# DB.session.add(CurrentLap(node_index=2, pilot_id=2, lap_id=0, lap_time_stamp=5000, lap_time=5000))
# DB.session.add(CurrentLap(node_index=2, pilot_id=2, lap_id=1, lap_time_stamp=15000, lap_time=10000))
# DB.session.add(CurrentLap(node_index=2, pilot_id=2, lap_id=2, lap_time_stamp=30000, lap_time=15000))
# DB.session.add(CurrentLap(node_index=3, pilot_id=3, lap_id=0, lap_time_stamp=6000, lap_time=6000))
# DB.session.add(CurrentLap(node_index=3, pilot_id=3, lap_id=1, lap_time_stamp=15000, lap_time=9000))
# DB.session.commit()

if __name__ == '__main__':
    SOCKET_IO.run(APP, host='0.0.0.0', debug=True)
