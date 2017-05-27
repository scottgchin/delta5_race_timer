import smbus
import gevent

from Node import Node

READ_RSSI = 0x01
READ_FREQUENCY = 0x03
READ_TRIGGER_RSSI = 0x04

WRITE_TRIGGER_RSSI = 0x53
WRITE_FREQUENCY = 0x56

def unpack_16(data):
    result = data[0]
    result = (result << 8) | data[1]
    return result

def pack_16(data):
    part_a = (data >> 8)
    part_b = (data & 0xFF)
    return [part_a, part_b]

class Delta5Interface:
    def __init__(self):
        self.update_thread = None

        # Start i2c bus
        self.i2c = smbus.SMBus(1)
        self.nodes = []

        # i2cAddr = [8]
        # for index, addr in enumerate(i2cAddr):
        #     node = Node(addr)
        #     nodes.append(node)

        node = Node()
        node.i2cAddr = 8
        self.nodes.append(node)

        self.get_frequencies()
        self.get_trigger_rssis()

    def read_block(self, addr, offset, size):
        data = self.i2c.read_i2c_block_data(addr, offset, size)
        return data

    def write_block(self, addr, offset, data):
        self.i2c.write_i2c_block_data(addr, offset, data)

    def update_loop(self):
        while True:
            self.update()
            gevent.sleep(0.1)

    def update(self):
        for node in self.nodes:
            data = self.read_block(node.i2c_addr, READ_RSSI, 2)
            node.current_rssi = data[1];
            gevent.sleep(0.01)

    def start(self):
        if self.update_thread is None:
            self.log('starting background thread')
            self.update_thread = gevent.spawn(self.update_loop)

    def get_frequencies(self):
        for node in self.nodes:
            self.get_frequency_node(node)
            gevent.sleep(0.01)

    def get_frequency_node(self, node):
        data = self.read_block(node.i2c_addr, READ_FREQUENCY, 2)
        node.frequency = unpack_16(data)
        self.log(data)
        self.log(node.frequency)
        return node.frequency

    def set_frequency_index(self, node_index, frequency):
        node = self.nodes[node_index]
        self.write_block(node.i2c_addr, WRITE_FREQUENCY, pack_16(frequency))
        # TODO: error checking?
        gevent.sleep(0.01)
        self.get_frequency_node(node)
        return node.frequency

    def get_trigger_rssis(self):
        for node in self.nodes:
            self.get_trigger_rssi_node(node);
            gevent.sleep(0.01)

    def get_trigger_rssi_node(self, node):
        data = self.read_block(node.i2c_addr, READ_TRIGGER_RSSI, 2)
        node.trigger_rssi = data[0]
        return node.trigger_rssi

    def set_trigger_rssi_index(self, node_index, trigger_rssi):
        node = self.nodes[node_index]
        self.write_block(node.i2c_addr, WRITE_TRIGGER_RSSI, [trigger_rssi])
        # TODO: error checking?
        gevent.sleep(0.01)
        self.get_trigger_rssi_node(node)
        return node.trigger_rssi

    def capture_trigger_rssi_index(self, node_index):
        node = self.nodes[node_index]
        self.write_block(node.i2c_addr, WRITE_TRIGGER_RSSI, [node.current_rssi])
        # TODO: error checking?
        gevent.sleep(0.01)
        self.get_trigger_rssi_node(node)
        return node.trigger_rssi

    def log(self, message):
        string = 'Delta5: {0}'.format(message)
        print(string)

    def get_settings_json(self):
        settings = [node.get_settings_json() for node in self.nodes]
        print(settings)
        return settings

    def get_heartbeat_json(self):
        return { 'current_rssi': [node.current_rssi for node in self.nodes]}

def get_hardware_interface():
    return Delta5Interface()
