'''Node class for the delta 5 interface.'''

class Node:
    '''Node class represents the arduino/rx pair.'''
    def __init__(self):
        self.frequency = 0
        self.current_rssi = 0
        self.trigger_rssi = 0
        self.last_lap_id = -1

    def get_node_data_json(self):
        '''doc string'''
        return {'frequency': self.frequency, 'current_rssi': self.current_rssi, \
            'trigger_rssi': self.trigger_rssi}
