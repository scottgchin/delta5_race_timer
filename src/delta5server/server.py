'''Delta5 timing system server script'''

import os
from datetime import datetime
from datetime import timedelta

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy

import gevent
from gevent.lock import BoundedSemaphore # To limit i2c calls
import gevent.monkey
gevent.monkey.patch_all()

import smbus # For i2c comms

APP = Flask(__name__, static_url_path='/static')
APP.config['SECRET_KEY'] = 'secret!'
SOCKET_IO = SocketIO(APP, async_mode='gevent')

BASEDIR = os.path.abspath(os.path.dirname(__file__))
APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASEDIR, 'database.db')
APP.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
DB = SQLAlchemy(APP)

CURRENT_RSSI_THREAD = None

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
        num_nodes=INTERFACE.num_nodes, current_heat=INTERFACE.current_heat, heats=Heat)

@APP.route('/settings')
def settings():
    '''Route to settings page.'''
    return render_template('settings.html', async_mode=SOCKET_IO.async_mode, \
        num_nodes=INTERFACE.num_nodes, pilots=Pilot, frequencies=Frequency, heats=Heat)

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
    hardware_log('Client connected')
    INTERFACE.start()
    global CURRENT_RSSI_THREAD
    if CURRENT_RSSI_THREAD is None:
        CURRENT_RSSI_THREAD = gevent.spawn(current_rssi_thread_function)
    emit_channel()
    emit_trigger_rssi()
    emit_peak_rssi()

    emit_current_laps()

@SOCKET_IO.on('disconnect')
def disconnect_handler():
    '''Print disconnect event.'''
    hardware_log('Client disconnected')

# Settings socket io events

@SOCKET_IO.on('set_frequency')
def on_set_frequency(data):
    '''Gets a node index number and frequency to update on the node.'''
    node_index = data['node']
    frequency = data['frequency']
    hardware_log('Set Frequency: Node {0} Frequency {1}'.format(node_index, frequency))
    # emit('frequency_set', {'node': node_index, 'frequency': \
    #     INTERFACE.set_full_reset_frequency(node_index, frequency)}, broadcast=True)
    INTERFACE.set_full_reset_frequency(node_index, frequency)
    emit_channel()

@SOCKET_IO.on('set_pilot_position')
def on_set_pilot_position(data):
    '''Gets a node index number and frequency to update on the node.'''
    heat = data['heat']
    node = data['node']
    pilot = data['pilot']
    hardware_log('Set Pilot Position: Heat {0} Node {1} Pilot {2}'.format(heat, node, pilot))
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
    hardware_log('Race started at {0}'.format(RACE_START))
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
    hardware_log('Race started at {0}'.format(RACE_START))
    emit_trigger_rssi() # Just to see the values on the start line
    emit_peak_rssi()

@SOCKET_IO.on('stop_race')
def on_race_status():
    '''Stops the racing and sets the hardware to stop looking for laps.'''
    hardware_log('Race stopped')
    INTERFACE.set_race_status(0)

@SOCKET_IO.on('save_laps')
def on_save_laps():
    '''Command to save current laps data to the database and clear the current laps.'''

@SOCKET_IO.on('clear_laps')
def on_clear_laps():
    '''Command to clear the current laps due to false start or practice.'''

#
# Hardware interface
#

READ_ADDRESS = 0x00 # Gets i2c address of arduino (1 byte)
READ_LAP_LAPTIME_RSSI = 0x02 # Gets lap (1 byte) lap time in ms (4 byte) rssi (2 byte)
READ_FREQUENCY = 0x03 # Gets channel frequency (2 byte)
READ_LAP_TIMESINCE_RSSI = 0x05 # Gets lap (1 byte) time since lap (4 byte) current rssi (2 byte)
READ_TRIG_PEAK_RSSI = 0x07 # Get rssi trigger (2 byte) rssi peak (2 byte)

WRITE_FULL_RESET_FREQUENCY = 0x51 # Full reset, sets frequency (2 byte)
WRITE_RACE_STATUS = 0x52 # Starts or stops a race (1 byte)

UPDATE_SLEEP = 0.100 # Main update loop delay

I2C_DELAY = 0.075 # Delay before i2c read/write
I2C_RETRY_COUNT = 5 # Limit of i2c retries

def unpack_16(data):
    '''Returns the full variable from 2 bytes input.'''
    result = data[0]
    result = (result << 8) | data[1]
    return result

def pack_16(data):
    '''Returns a 2 part array from the full variable.'''
    part_a = (data >> 8)
    part_b = (data & 0xFF)
    return [part_a, part_b]

def unpack_32(data):
    '''Returns the full variable from 4 bytes input.'''
    result = data[0]
    result = (result << 8) | data[1]
    result = (result << 8) | data[2]
    result = (result << 8) | data[3]
    return result

def validate_checksum(data):
    '''Returns True if the checksum matches the data.'''
    if data is None:
        return False
    checksum = sum(data[:-1]) & 0xFF
    return checksum == data[-1]

class Node:
    '''Node class represents the arduino/rx pair.'''
    def __init__(self):
        self.frequency = 0
        self.current_rssi = 0
        self.trigger_rssi = 0
        self.peak_rssi = 0
        self.last_lap_id = 250 # Can't use -1 so set no laps registered to 250
        self.last_lap_time = 0
        self.ms_since_lap = 0

class Delta5Interface:
    '''Manages the i2c comms and update loops with the nodes.'''
    def __init__(self):
        self.update_thread = None # Thread for running the main update loop

        self.i2c = smbus.SMBus(1) # Start i2c bus
        self.semaphore = BoundedSemaphore(1) # Limits i2c to 1 read/write at a time

        self.race_status = 0
        self.current_heat = 1 # Default to heat 1

        # Scans all i2c_addrs to populate nodes array
        self.nodes = [] # Array to hold each node object
        i2c_addrs = [8, 10, 12, 14, 16, 18, 20, 22] # Software limited to 8 nodes
        # Add retries here, program fails if a node is missed
        for index, addr in enumerate(i2c_addrs):
            try:
                gevent.sleep(I2C_DELAY) # Wait before i2c action
                self.i2c.read_i2c_block_data(addr, READ_ADDRESS, 1)
                hardware_log('Node found at address {0}'.format(addr))
                node = Node() # New node object
                node.i2c_addr = addr
                node.index = index
                self.nodes.append(node) # Add new node to Delta5Interface
            except IOError as err:
                hardware_log('No node at address {0}'.format(addr))
        self.num_nodes = len(self.nodes) # Save the number of nodes detected

    #
    # Class Functions
    #

    def start(self):
        '''Starts main update thread.'''
        if self.update_thread is None:
            hardware_log('Starting background thread')
            self.update_thread = gevent.spawn(self.update_loop)

    def update_loop(self):
        '''Main update loop with timed delay.'''
        while True:
            self.update()
            gevent.sleep(UPDATE_SLEEP)

    def update(self):
        '''Updates all node data.'''
        for node in self.nodes:
            current_lap = node.last_lap_id
            self.get_lap_timesince_rssi(node.index)
            if node.last_lap_id != current_lap: # Check if new lap
                pass_record_callback(node.index, node.last_lap_id, node.ms_since_lap)
                self.get_trig_peak_rssi(node.index) # Get updated values

    def default_frequencies(self):
        '''Set each nodes frequency, use imd frequncies for 6 or less and race band for 7 or 8'''
        hardware_log('Setting default frequencies')
        frequencies_imd_5_6 = [5685, 5760, 5800, 5860, 5905, 5645]
        frequencies_raceband = [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917]
        for index, node in enumerate(self.nodes):
            if self.num_nodes < 7:
                node.frequency = self.set_full_reset_frequency(index, frequencies_imd_5_6[index])
            else:
                node.frequency = self.set_full_reset_frequency(index, frequencies_raceband[index])

    # I2C Common Functions

    def read_block(self, addr, offset, size):
        '''Read i2c data given an address, code, and data size.'''
        success = False
        retry_count = 0
        data = None
        while success is False and retry_count < I2C_RETRY_COUNT:
            try:
                with self.semaphore: # Wait if i2c comms is already in progress
                    gevent.sleep(I2C_DELAY)
                    data = self.i2c.read_i2c_block_data(addr, offset, size + 1)
                    if validate_checksum(data):
                        success = True
                        data = data[:-1] # Save the data array without the checksum from the end
                    else:
                        retry_count = retry_count + 1
                        hardware_log('*Error* Bad Checksum: Retry: {0} Data: {1}'. \
                            format(retry_count, data))
            except IOError as err:
                hardware_log(str(err))
                retry_count = retry_count + 1
        return data # What happens if the i2c read fails every time? Does it return garbage data?
                    # Should it return 'None'?

    def write_block(self, addr, offset, data):
        '''Write i2c data given an address, code, and data.'''
        success = False
        retry_count = 0
        data_with_checksum = data
        data_with_checksum.append(sum(data) & 0xFF)
        while success is False and retry_count < I2C_RETRY_COUNT:
            try:
                with self.semaphore: # Wait if i2c comms is already in progress
                    gevent.sleep(I2C_DELAY)
                    self.i2c.write_i2c_block_data(addr, offset, data_with_checksum)
                    success = True
            except IOError as err:
                hardware_log(str(err))
                retry_count = retry_count + 1

    # I2C Get Functions

    def get_lap_laptime_rssi(self, node_index):
        '''Gets and updates the nodes lap count, lap time, and rssi.'''
        node = self.nodes[node_index]
        node_data = self.read_block(node.i2c_addr, READ_LAP_LAPTIME_RSSI, 7)
        node.last_lap_id = node_data[0] # Number of completed laps
        node.last_lap_time = unpack_32(node_data[1:]) # Lap time of Last completed lap
        node.current_rssi = unpack_16(node_data[5:])
        return [node.last_lap_id, node.last_lap_time, node.current_rssi]

    def get_lap_timesince_rssi(self, node_index):
        '''Gets and updates the nodes lap count, time since last lap, and rssi.'''
        node = self.nodes[node_index]
        node_data = self.read_block(node.i2c_addr, READ_LAP_TIMESINCE_RSSI, 7)
        node.last_lap_id = node_data[0] # Number of completed laps
        # print 'last_lap_id {0}'.format(node.last_lap_id)
        node.time_since_lap = unpack_32(node_data[1:]) # Milliseconds since last lap
        # print 'time_since_lap {0}'.format(node.time_since_lap)
        node.current_rssi = unpack_16(node_data[5:])
        return [node.last_lap_id, node.time_since_lap, node.current_rssi]

    def get_frequency(self, node_index):
        '''Gets and updates the nodes frequency.'''
        node = self.nodes[node_index]
        node_data = self.read_block(node.i2c_addr, READ_FREQUENCY, 2)
        node.frequency = unpack_16(node_data[0:])
        return node.frequency

    def get_trig_peak_rssi(self, node_index):
        '''Gets and updates the nodes trigger and peak rssis.'''
        node = self.nodes[node_index]
        node_data = self.read_block(node.i2c_addr, READ_TRIG_PEAK_RSSI, 4)
        node.trigger_rssi = unpack_16(node_data[0:])
        node.peak_rssi = unpack_16(node_data[2:])
        return [node.trigger_rssi, node.peak_rssi]

    # I2C Set Functions

    def set_full_reset_frequency(self, node_index, frequency):
        '''Sets the given frequency to a node based on index number.'''
        success = False
        retry_count = 0
        node = self.nodes[node_index]
        while success is False and retry_count < I2C_RETRY_COUNT:
            self.write_block(node.i2c_addr, WRITE_FULL_RESET_FREQUENCY, pack_16(frequency))
            if self.get_frequency(node.index) == frequency:
                success = True
                hardware_log('Frequency Set: Node {0} Frequency: {1}' \
                    .format(node.index, frequency))
            else:
                retry_count = retry_count + 1
                hardware_log('*Error* Setting Frequency: Node {0} Retry: {1}' \
                    .format(node.index, retry_count))
        self.get_trig_peak_rssi(node.index) # Get updated values
        node.last_lap_id = 250 # Reset laps
        return node.frequency

    def set_race_status(self, race_status):
        '''Sets the node to defaults for a new race or stops the race.'''
        self.race_status = race_status
        for node in self.nodes:
            success = False
            retry_count = 0
            while success is False and retry_count < I2C_RETRY_COUNT:
                self.write_block(node.i2c_addr, WRITE_RACE_STATUS, [race_status])
                # How to check that the race status has changed here?
                success = True
                hardware_log('Race Status Set: Node {0}, Race Status: {1}' \
                    .format(node.index, race_status))
            self.get_trig_peak_rssi(node.index) # Get updated values
        node.last_lap_id = 250 # Reset laps
        return race_status

#
# Program Functions
#

def hardware_log(message):
    '''Hardware log of messages.'''
    print message
    SOCKET_IO.emit('hardware_log', message)

def current_rssi_thread_function():
    '''Emits 'current_rssi' with json node data.'''
    while True:
        SOCKET_IO.emit('current_rssi', \
            {'current_rssi': [node.current_rssi for node in INTERFACE.nodes]})
        gevent.sleep(0.500) # Emit current rssi every half second

def ms_from_race_start():
    '''Return milliseconds since race start.'''
    delta_time = datetime.now() - RACE_START
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

def pass_record_callback(node_index, lap_id, ms_since_lap):
    '''Logs and emits a completed lap.'''
    # Get the current pilot id on the node
    print 'node_index {0}'.format(node_index)
    pilot_id = Heat.query.filter_by( \
        heat_id=INTERFACE.current_heat, node_index=node_index).first().pilot_id
    print 'pilot_id {0}'.format(pilot_id)

    # Calculate the lap time stamp, total time since start of race
    lap_time_stamp = ms_from_race_start() - ms_since_lap
    print 'lap_time_stamp {0}'.format(lap_time_stamp)

    if lap_id == 0: # If lap is zero this is the first fly through the gate
        # Lap zero represents the time from the launch pad to flying through the gate
        lap_time = lap_time_stamp
    else: # Else this is a normal completed lap
        # Find the last lap number completed
        last_lap_id = DB.session.query(DB.func.max(CurrentLap.lap_id)).filter_by( \
            node_index=node_index).scalar()
        print 'last_lap_id {0}'.format(last_lap_id)
        # Find the time stamp of the last lap completed
        last_lap_time_stamp = CurrentLap.query.filter_by( \
            node_index=node_index, lap_id=last_lap_id).first().lap_time_stamp
        print 'last_lap_time_stamp {0}'.format(last_lap_time_stamp)
        # New lap time is the difference between the current time stamp and the last lap timestamp
        lap_time = lap_time_stamp - last_lap_time_stamp
    print 'lap_time {0}'.format(lap_time)

    # Add the new lap to the database
    DB.session.add(CurrentLap(node_index=node_index, pilot_id=pilot_id, lap_id=lap_id, \
        lap_time_stamp=lap_time_stamp, lap_time=lap_time))
    DB.session.commit()

    hardware_log('Pass record: Node: {0}, Lap: {1}, Lap time: {2}'.format(node_index, lap_id, time_format(lap_time)))
    SOCKET_IO.emit('pass_record', {'node': node_index, 'lap': lap_id, 'laptime': time_format(lap_time)})
    emit_current_laps()
    emit_trigger_rssi()
    emit_peak_rssi()

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
    for node in range(INTERFACE.num_nodes):
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

INTERFACE = Delta5Interface()
gevent.sleep(0.500) # Delay to get I2C addresses
INTERFACE.default_frequencies()

PROGRAM_START = datetime.now()
RACE_START = datetime.now()

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
