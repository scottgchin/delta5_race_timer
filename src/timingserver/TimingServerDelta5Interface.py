import gevent # For threads and timing
import sys

sys.path.append('../delta5interface')

from Delta5Interface import *

class TimingServerDelta5Interface(Delta5Interface):
    def __init(self):
        Delta5Interface.__init__(self)

    def start(self):
        '''Starts main update thread.'''
        self.set_race_status(1) # Move this into a race start, re cal command
        if self.update_thread is None:
            self.log('Starting background thread.')
            self.update_thread = gevent.spawn(self.update_loop)

    def update(self):
        '''Updates all node data for timing server.'''
        for node in self.nodes:
            data = self.read_block(node.i2c_addr, READ_LAP_TIMESINCE_RSSI, 7)
            lap_id = data[0]
            ms_since_lap = unpack_32(data[1:])
            node.current_rssi = unpack_16(data[5:]) # Saves rssi to current node

            if lap_id != node.last_lap_id:
                if callable(self.pass_record_callback):
                    self.pass_record_callback(node, ms_since_lap)
                node.last_lap_id = lap_id

    def get_node_settings_json(self, node):
        return {'frequency': node.frequency, 'current_rssi': node.current_rssi, 'trigger_rssi': node.trigger_rssi}

    def get_settings_json(self):
        settings = [self.get_node_settings_json(node) for node in self.nodes]
        return settings

    def get_heartbeat_json(self):
        return { 'current_rssi': [node.current_rssi for node in self.nodes]}

def get_hardware_interface():
    '''Returns the delta 5 interface object.'''
    return TimingServerDelta5Interface()
