'''Delta 5 hardware interface layer.'''

import smbus # For i2c comms
import gevent # For threads and timing
from gevent.lock import BoundedSemaphore # To limit i2c calls

from Node import Node # Load the node class representing arduino/rx pairs

READ_ADDRESS = 0x00 # Gets i2c address of arduino (1 byte)
READ_RSSI = 0x01 # Gets current rssi (2 byte)
READ_LAP = 0x02 # Gets lap number (1 byte) and lap time in ms (4 byte)
READ_FREQUENCY = 0x03 # Gets channel frequency (2 byte)
READ_TRIGGER_RSSI = 0x04 # Gets rssi trigger (2 byte)
READ_LAPRSSI = 0x05 # Gets lap number (1 byte) time since last lap (4 byte) current rssi (2 byte)
READ_TIMING_SERVER_MODE = 0x06 # Gets timing server mode (1 byte)

WRITE_FULL_RESET_FREQUENCY = 0x51 # Full reset, sets frequency (2 byte)
WRITE_RACE_REST = 0x52 # Starts a new race (0 byte)
WRITE_TRIGGER_RSSI = 0x53 # Sets rssi trigger (2 byte)
WRITE_MIN_LAP_TIME = 0x54 # Sets min lap time (1 byte)
WRITE_RACE_STATUS = 0x55 # Sets race status (1 byte)
WRITE_FREQUENCY = 0x56 # Sets frequency (2 byte)
WRITE_TIMING_SERVER_MODE = 0x57 # Sets timing server mode (1 byte)

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
        self.pass_record_callback = None # Gets added in server.py
        self.hardware_log_callback = None # Gets added in server.py

        self.i2c = smbus.SMBus(1) # Start i2c bus
        self.semaphore = BoundedSemaphore(1) # Limits i2c to 1 read/write at a time

        # Scans all i2c_addrs to populate nodes array
        self.nodes = [] # Array to hold each node object
        i2c_addrs = [8, 10, 12, 14, 16, 18, 20, 22] # Software limited to 8 nodes
        for addr in i2c_addrs:
            try:
                self.i2c.read_i2c_block_data(addr, READ_ADDRESS, 1)
                print "Node FOUND at address {0}".format(addr)
                gevent.sleep(I2C_CHILL_TIME)
                node = Node() # New node instance
                node.i2c_addr = addr # Set current loop i2c_addr
                self.nodes.append(node) # Add new node to Delta5Interface
                #self.get_frequency_node(node)
                #self.get_trigger_rssi_node(node)
                #self.enable_timing_server_mode(node)
            except IOError as err:
                print "No node at address {0}".format(addr)
            gevent.sleep(I2C_CHILL_TIME)
        # Define arrays for frequncies based on number of nodes
        # For loop to initialize each node with its new frequencies and save to nodes object

    def start(self):
        '''Starts main update thread.'''
        if self.update_thread is None:
            self.log('Starting background thread.')
            self.update_thread = gevent.spawn(self.update_loop)

    def update_loop(self):
        '''Main update loop with timed delay.'''
        while True:
            self.update()
            gevent.sleep(UPDATE_SLEEP)

    def update(self):
        '''Updates all node data.'''
        for node in self.nodes:
            data = self.read_block(node.i2c_addr, READ_LAPRSSI, 7)
            lap_id = data[0]
            ms_since_lap = unpack_32(data[1:])
            node.current_rssi = unpack_16(data[5:]) # Saves rssi to current node

            if lap_id != node.last_lap_id:
                if callable(self.pass_record_callback):
                    self.pass_record_callback(node.frequency, ms_since_lap)
                node.last_lap_id = lap_id

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
                        data = data[:-1]
                    else:
                        self.log('Invalid Checksum ({0}): {1}'.format(retry_count, data))
                        retry_count = retry_count + 1
                        gevent.sleep(I2C_RETRY_SLEEP)
            except IOError as err:
                self.log(err)
                retry_count = retry_count + 1
                gevent.sleep(I2C_RETRY_SLEEP)
        return data

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

    def enable_timing_server_mode(self, node):
        '''Sets true the timer server variable on the node.'''
        success = False
        retry_count = 0

        while success is False and retry_count < I2C_RETRY_COUNT:
            self.write_block(node.i2c_addr, WRITE_TIMING_SERVER_MODE, [1])
            data = self.read_block(node.i2c_addr, READ_TIMING_SERVER_MODE, 1)
            if  data[0] == 1:
                print 'Timing Server Mode Set'
                success = True
            else:
                retry_count = retry_count + 1
                print 'Timing Server Mode Not Set ({0})'.format(retry_count)
                gevent.sleep(I2C_RETRY_SLEEP)

        return node.trigger_rssi

    def get_frequencies(self):
        '''Not called anywhere?'''
        for node in self.nodes:
            self.get_frequency_node(node)

    def get_frequency_node(self, node):
        '''Returns the frequency for a given node.'''
        data = self.read_block(node.i2c_addr, READ_FREQUENCY, 2)
        node.frequency = unpack_16(data)
        return node.frequency

    def set_frequency_index(self, node_index, frequency):
        '''Sets the given frequency to a node based on index number.'''
        success = False
        retry_count = 0

        node = self.nodes[node_index]
        while success is False and retry_count < I2C_RETRY_COUNT:
            self.write_block(node.i2c_addr, WRITE_FREQUENCY, pack_16(frequency))
            if self.get_frequency_node(node) == frequency:
                success = True
            else:
                retry_count = retry_count + 1
                self.log('Frequency Not Set ({0})'.format(retry_count))

        return node.frequency

    def get_trigger_rssis(self):
        '''Not called anywhere?'''
        for node in self.nodes:
            self.get_trigger_rssi_node(node)

    def get_trigger_rssi_node(self, node):
        '''Returns the trigger for a given node.'''
        data = self.read_block(node.i2c_addr, READ_TRIGGER_RSSI, 2)
        node.trigger_rssi = unpack_16(data)
        return node.trigger_rssi

    def set_trigger_rssi_index(self, node_index, trigger_rssi):
        '''doc string'''
        success = False
        retry_count = 0

        node = self.nodes[node_index]
        while success is False and retry_count < I2C_RETRY_COUNT:
            self.write_block(node.i2c_addr, WRITE_TRIGGER_RSSI, pack_16(trigger_rssi))
            if self.get_trigger_rssi_node(node) == trigger_rssi:
                success = True
            else:
                retry_count = retry_count + 1
                self.log('RSSI Not Set ({0})'.format(retry_count))

        return node.trigger_rssi

    def capture_trigger_rssi_index(self, node_index):
        '''doc string'''
        node = self.nodes[node_index]
        return self.set_trigger_rssi_index(node_index, node.current_rssi)

    def log(self, message):
        '''doc string'''
        if callable(self.hardware_log_callback):
            string = 'Delta5: {0}'.format(message)
            self.hardware_log_callback(string)

    def get_node_data_json(self):
        '''doc string'''
        settings = [node.get_node_data_json() for node in self.nodes]
        return settings

    def get_heartbeat_json(self):
        '''doc string'''
        return {'current_rssi': [node.current_rssi for node in self.nodes]}

def get_hardware_interface():
    '''Returns the delta 5 interface object.'''
    return Delta5Interface()
