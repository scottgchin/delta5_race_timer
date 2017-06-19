'''Delta5 timing system server script'''

import os
import sys
from datetime import datetime
from datetime import timedelta

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
RACE = get_race_state()

PROGRAM_START = datetime.now()
RACE_START = datetime.now()

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

@APP.route('/timingserver')
def timingserver():
    '''Route to timing server page.'''
    return render_template('timingserver.html', async_mode=SOCKET_IO.async_mode)

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
    emit_channel()
    emit_trigger_rssi()
    emit_peak_rssi()

    emit_current_laps()

@SOCKET_IO.on('disconnect')
def disconnect_handler():
    '''Print disconnect event.'''
    server_log('Client disconnected')

# Settings socket io events

@SOCKET_IO.on('set_frequency')
def on_set_frequency(data):
    '''Gets a node index number and frequency to update on the node.'''
    node_index = data['node']
    frequency = data['frequency']
    server_log('Set Frequency: Node {0} Frequency {1}'.format(node_index, frequency))
    # emit('frequency_set', {'node': node_index, 'frequency': \
    #     INTERFACE.set_full_reset_frequency(node_index, frequency)}, broadcast=True)
    INTERFACE.set_frequency(node_index, frequency)
    emit('frequency_set', INTERFACE.get_frequency_json(index), broadcast=True)
    emit_channel()

@SOCKET_IO.on('set_pilot_position')
def on_set_pilot_position(data):
    '''Gets a node index number and frequency to update on the node.'''
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
    '''Starts the race.'''
    print 'Start Race'
    INTERFACE.set_race_status(1) # Start registering laps
    gevent.sleep(0.500) # Make this random 2 to 5 seconds
    SOCKET_IO.emit('start_timer')
    RACE_START = datetime.now()
    server_log('Race started at {0}'.format(RACE_START))
    emit_trigger_rssi() # Just to see the values on the start line
    emit_peak_rssi()

@SOCKET_IO.on('start_race_2_min')
def on_start_race_2_min():
    '''Starts the race with a two minute countdown clock.'''
    # On starting a race, have a 2 to 5 second delay here after setting the hardware interface
    # setting to true and then sound the start buzzer tied into the clock function
    # stopping the race should stop and reset the timer
    print 'Start Race'
    INTERFACE.set_race_status(1)
    gevent.sleep(0.500) # Make this random 2 to 5 seconds
    SOCKET_IO.emit('start_timer_2min')
    RACE_START = datetime.now()
    server_log('Race started at {0}'.format(RACE_START))
    emit_trigger_rssi() # Just to see the values on the start line
    emit_peak_rssi()

@SOCKET_IO.on('stop_race')
def on_race_status():
    '''Stops the racing and sets the hardware to stop looking for laps.'''
    server_log('Race stopped')
    INTERFACE.set_race_status(0)

@SOCKET_IO.on('save_laps')
def on_save_laps():
    '''Command to save current laps data to the database and clear the current laps.'''

@SOCKET_IO.on('clear_laps')
def on_clear_laps():
    '''Command to clear the current laps due to false start or practice.'''

# Timingserver events

@SOCKET_IO.on('get_settings')
def on_get_settings():
    return INTERFACE.get_settings_json()

@SOCKET_IO.on('set_calibration_threshold')
def on_set_calibration_threshold(data):
    server_log(data)
    calibration_threshold = data['calibration_threshold']
    INTERFACE.set_calibration_threshold_global(calibration_threshold)
    emit('calibration_threshold_set', INTERFACE.get_calibration_threshold_json(), broadcast=True)

@SOCKET_IO.on('set_calibration_offset')
def on_set_calibration_offset(data):
    server_log(data)
    calibration_offset = data['calibration_offset']
    INTERFACE.set_calibration_offset_global(calibration_offset)
    emit('calibration_offset_set', INTERFACE.get_calibration_offset_json(), broadcast=True)

@SOCKET_IO.on('set_trigger_threshold')
def on_set_trigger_threshold(data):
    server_log(data)
    trigger_threshold = data['trigger_threshold']
    INTERFACE.set_trigger_threshold_global(trigger_threshold)
    emit('trigger_threshold_set', INTERFACE.get_trigger_threshold_json(), broadcast=True)

@SOCKET_IO.on('enable_calibration_mode')
def on_enable_calibration_mode():
    INTERFACE.enable_calibration_mode();

@SOCKET_IO.on('simulate_pass')
def on_simulate_pass(data):
    server_log(data)
    index = data['node']
    # todo: how should frequency be sent?
    emit('pass_record', {'node': index, 'frequency': INTERFACE.nodes[index].frequency, 'timestamp': milliseconds()}, broadcast=True)

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

def milliseconds():
    '''Returns the elapsed milliseconds since the start of the program.'''
    dt = datetime.now() - PROGRAM_START
    ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
    return ms

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

    print('Pass record from {0}{1}: {2}, {3}'.format(node.index, node.frequency, ms_since_lap, milliseconds() - ms_since_lap))
    SOCKET_IO.emit('pass_record', {
        'node': node.index,
        'frequency': node.frequency,
        'timestamp': milliseconds() - ms_since_lap,
        'trigger_rssi': node.trigger_rssi,
        'peak_rssi_raw': node.peak_rssi_raw,
        'peak_rssi': node.peak_rssi})


    # # Get the current pilot id on the node
    # print 'node_index {0}'.format(node_index)
    # pilot_id = Heat.query.filter_by( \
    #     heat_id=RACE.current_heat, node_index=node_index).first().pilot_id
    # print 'pilot_id {0}'.format(pilot_id)

    # # Calculate the lap time stamp, total time since start of race
    # lap_time_stamp = ms_from_race_start() - ms_since_lap
    # print 'lap_time_stamp {0}'.format(lap_time_stamp)

    # # Instead of lap_id query the database for an existing lap zero
    # if lap_id == 0: # If lap is zero this is the first fly through the gate
    #     # Lap zero represents the time from the launch pad to flying through the gate
    #     lap_time = lap_time_stamp
    # else: # Else this is a normal completed lap
    #     # Find the last lap number completed
    #     last_lap_id = DB.session.query(DB.func.max(CurrentLap.lap_id)).filter_by( \
    #         node_index=node_index).scalar()
    #     print 'last_lap_id {0}'.format(last_lap_id)
    #     # Find the time stamp of the last lap completed
    #     last_lap_time_stamp = CurrentLap.query.filter_by( \
    #         node_index=node_index, lap_id=last_lap_id).first().lap_time_stamp
    #     print 'last_lap_time_stamp {0}'.format(last_lap_time_stamp)
    #     # New lap time is the difference between the current time stamp and the last lap timestamp
    #     lap_time = lap_time_stamp - last_lap_time_stamp
    # print 'lap_time {0}'.format(lap_time)

    # # Add the new lap to the database
    # DB.session.add(CurrentLap(node_index=node_index, pilot_id=pilot_id, lap_id=lap_id, \
    #     lap_time_stamp=lap_time_stamp, lap_time=lap_time))
    # DB.session.commit()

    # server_log('Pass record: Node: {0}, Lap: {1}, Lap time: {2}'.format(node_index, lap_id, time_format(lap_time)))
    # emit_current_laps()
    # emit_trigger_rssi()
    # emit_peak_rssi()

INTERFACE.pass_record_callback = pass_record_callback

def server_log(message):
    '''Messages emitted from the server script.'''
    print message
    SOCKET_IO.emit('server_log', message)

def hardware_log_callback(message):
    '''Message emitted from the delta 5 interface class.'''
    print(message)
    SOCKET_IO.emit('hardware_log', message)

INTERFACE.hardware_log_callback = hardware_log_callback

def emit_channel():
    '''Emits channel json.'''
    SOCKET_IO.emit('channel', \
        {'channel': [Frequency.query.filter_by(frequency=node.frequency).first().channel \
        for node in INTERFACE.nodes], \
        'frequency': [node.frequency for node in INTERFACE.nodes]})

def emit_trigger_rssi():
    '''Emits trigger_rssi json.'''
    SOCKET_IO.emit('trigger_rssi', \
        {'trigger_rssi': [node.trigger_rssi for node in INTERFACE.nodes]})

def emit_peak_rssi():
    '''Emits peak_rssi json.'''
    SOCKET_IO.emit('peak_rssi', \
        {'peak_rssi': [node.peak_rssi for node in INTERFACE.nodes]})

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
# Program Initialize
#


# gevent.sleep(0.500) # Delay to get I2C addresses
# INTERFACE.default_frequencies()

RACE.num_nodes = len(INTERFACE.nodes)

DB.session.query(CurrentLap).delete() # Clear out the current laps table
DB.session.commit()


# Test data
DB.session.add(CurrentLap(node_index=2, pilot_id=2, lap_id=0, lap_time_stamp=5000, lap_time=5000))
DB.session.add(CurrentLap(node_index=2, pilot_id=2, lap_id=1, lap_time_stamp=15000, lap_time=10000))
DB.session.add(CurrentLap(node_index=2, pilot_id=2, lap_id=2, lap_time_stamp=30000, lap_time=15000))
DB.session.add(CurrentLap(node_index=3, pilot_id=3, lap_id=0, lap_time_stamp=6000, lap_time=6000))
DB.session.add(CurrentLap(node_index=3, pilot_id=3, lap_id=1, lap_time_stamp=15000, lap_time=9000))
DB.session.commit()

if __name__ == '__main__':
    SOCKET_IO.run(APP, host='0.0.0.0', debug=True)
