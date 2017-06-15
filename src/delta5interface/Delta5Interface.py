'''Delta 5 hardware interface layer.'''

import smbus # For i2c comms
import gevent # For threads and timing
from gevent.lock import BoundedSemaphore # To limit i2c calls

from Node import Node # Load the node class representing arduino/rx pairs

READ_ADDRESS = 0x00 # Gets i2c address of arduino (1 byte)
READ_LAP_LAPTIME_RSSI = 0x02 # Gets lap (1 byte) lap time in ms (4 byte) rssi (2 byte)
READ_FREQUENCY = 0x03 # Gets channel frequency (2 byte)
READ_LAP_TIMESINCE_RSSI = 0x05 # Gets lap (1 byte) time since lap (4 byte) current rssi (2 byte)
READ_TRIG_PEAK_RSSI = 0x07 # Get rssi trigger (2 byte) rssi peak (2 byte)

WRITE_FULL_RESET_FREQUENCY = 0x51 # Full reset, sets frequency (2 byte)
WRITE_RACE_STATUS = 0x52 # Starts or stops a race (1 byte)

UPDATE_SLEEP = 0.1 # Main update loop delay

I2C_CHILL_TIME = 0.05 # Delay after i2c read/write
I2C_RETRY_SLEEP = 0.05 # Delay for i2c retries
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


class Delta5Interface:
    '''Manages the i2c comms and update loops with the nodes.'''
    def __init__(self):
        self.update_thread = None # Thread for running the main update loop
        self.pass_record_callback = None # Function added in server.py
        self.hardware_log_callback = None # Function added in server.py

        self.i2c = smbus.SMBus(1) # Start i2c bus
        self.semaphore = BoundedSemaphore(1) # Limits i2c to 1 read/write at a time

        # Scans all i2c_addrs to populate nodes array
        self.nodes = [] # Array to hold each node object
        i2c_addrs = [8, 10, 12, 14, 16, 18, 20, 22] # Software limited to 8 nodes
        for index, addr in enumerate(i2c_addrs):
            try:
                self.i2c.read_i2c_block_data(addr, READ_ADDRESS, 1)
                print "Node FOUND at address {0}".format(addr)
                gevent.sleep(I2C_CHILL_TIME)
                node = Node() # New node object
                node.i2c_addr = addr
                node.index = index
                self.nodes.append(node) # Add new node to Delta5Interface
            except IOError as err:
                print "No node at address {0}".format(addr)
            gevent.sleep(I2C_CHILL_TIME)
        self.num_nodes = len(self.nodes) # Save the number of nodes detected

        print "Setting default frequencies."
        self.default_frequencies() # This should be moved out of init to optionally be called

    #
    # Class Functions
    #

    def start(self):
        '''Starts main update thread.'''
        if self.update_thread is None:
            self.log('Starting background thread.')
            self.update_thread = gevent.spawn(self.update_loop)

    def log(self, message):
        '''Hardware log of messages.'''
        if callable(self.hardware_log_callback):
            string = 'Delta 5 Log: {0}'.format(message)
            self.hardware_log_callback(string)

    def default_frequencies(self):
        '''Set each nodes frequency, use imd frequncies for 6 or less and race band for 7 or 8'''
        frequencies_imd_5_6 = [5685, 5760, 5800, 5860, 5905, 5645]
        frequencies_raceband = [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917]
        for index, node in enumerate(self.nodes):
            if self.num_nodes < 7:
                node.frequency = self.set_full_reset_frequency(index, frequencies_imd_5_6[index])
            else:
                node.frequency = self.set_full_reset_frequency(index, frequencies_raceband[index])

    #
    # Update Loops
    #

    def update_loop(self):
        '''Main update loop with timed delay.'''
        while True:
            self.update()
            gevent.sleep(UPDATE_SLEEP)

    def update(self):
        '''Updates all node data.'''
        for node in self.nodes:
            current_lap = node.last_lap_id
            self.get_lap_laptime_rssi(node.index)
            if node.last_lap_id != current_lap:
                if callable(self.pass_record_callback):
                    self.pass_record_callback(node.index, node.last_lap_time)
                self.get_trig_peak_rssi(node.index) # Get updated values

    #
    # I2C Common Functions
    #

    def read_block(self, addr, offset, size):
        '''Read i2c data given an address, code, and data size.'''
        success = False
        retry_count = 0
        data = None
        while success is False and retry_count < I2C_RETRY_COUNT:
            try:
                with self.semaphore: # Wait if i2c comms is already in progress
                    data = self.i2c.read_i2c_block_data(addr, offset, size + 1)
                    if validate_checksum(data):
                        success = True
                        gevent.sleep(I2C_CHILL_TIME)
                        data = data[:-1] # Save the data array without the checksum from the end
                    else:
                        retry_count = retry_count + 1
                        self.log('Bad checksum, retrying {0}, data {1}'.format(retry_count, data))
                        gevent.sleep(I2C_RETRY_SLEEP)
            except IOError as err:
                self.log(err)
                retry_count = retry_count + 1
                gevent.sleep(I2C_RETRY_SLEEP)
        return data # What happens if the i2c read fails every time? Does it return garbage data? Should it return 'None'?

    def write_block(self, addr, offset, data):
        '''Write i2c data given an address, code, and data.'''
        success = False
        retry_count = 0
        data_with_checksum = data
        data_with_checksum.append(sum(data) & 0xFF)
        while success is False and retry_count < I2C_RETRY_COUNT:
            try:
                with self.semaphore: # Wait if i2c comms is already in progress
                    self.i2c.write_i2c_block_data(addr, offset, data_with_checksum)
                    success = True
                    gevent.sleep(I2C_CHILL_TIME)
            except IOError as err:
                self.log(err)
                retry_count = retry_count + 1
                gevent.sleep(I2C_RETRY_SLEEP)

    #
    # I2C Get Functions
    #

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
        node.time_since_lap = unpack_32(node_data[1:]) # Lap time of Last completed lap
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

    #
    # I2C Set Functions
    #

    def set_full_reset_frequency(self, node_index, frequency):
        '''Sets the given frequency to a node based on index number.'''
        success = False
        retry_count = 0
        node = self.nodes[node_index]
        while success is False and retry_count < I2C_RETRY_COUNT:
            self.write_block(node.i2c_addr, WRITE_FULL_RESET_FREQUENCY, pack_16(frequency))
            if self.get_frequency(node.index) == frequency:
                success = True
                self.log('Node {0}, frequency set {1}.'.format(node.index, frequency))
            else:
                retry_count = retry_count + 1
                self.log('Error, node {0}, frequency not set, retrying {1}' \
                    .format(node.index, retry_count))
        self.get_trig_peak_rssi(node.index) # Get updated values
        return node.frequency

    def set_race_status(self, race_status):
        '''Sets the node to defaults for a new race or stops the race.'''
        for node in self.nodes:
            success = False
            retry_count = 0
            while success is False and retry_count < I2C_RETRY_COUNT:
                self.write_block(node.i2c_addr, WRITE_RACE_STATUS, [race_status])
                # How to check that the race status has changed here?
                success = True
                self.log('Node {0}, race status set {1}'.format(node.index, race_status))
            self.get_trig_peak_rssi(node.index) # Get updated values
        return race_status

    #
    # Get Json Node Data Functions
    #

    def get_frequency_json(self):
        '''Returns json: frequency.'''
        return {'frequency': [node.frequency for node in self.nodes]}

    def get_current_rssi_json(self):
        '''Returns json: current_rssi.'''
        return {'current_rssi': [node.current_rssi for node in self.nodes]}

    def get_trigger_rssi_json(self):
        '''Returns json: trigger_rssi.'''
        return {'trigger_rssi': [node.trigger_rssi for node in self.nodes]}

    def get_peak_rssi_json(self):
        '''Returns json: peak_rssi.'''
        return {'peak_rssi': [node.peak_rssi for node in self.nodes]}

def get_hardware_interface():
    '''Returns the delta 5 interface object.'''
    return Delta5Interface()
