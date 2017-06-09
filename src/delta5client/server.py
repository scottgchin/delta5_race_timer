'''Delta5 timing system server script'''

import sys
from datetime import datetime

from flask import Flask, render_template
from flask_socketio import SocketIO, emit

import gevent
import gevent.monkey
gevent.monkey.patch_all()

# Load the common delta 5 interface module
sys.path.append('../delta5interface')
from Delta5Interface import get_hardware_interface
HARDWARE_INTERFACE = get_hardware_interface()

ASYNC_MODE = "gevent"

APP = Flask(__name__, static_url_path='/static')
APP.config['SECRET_KEY'] = 'secret!'
SOCKET_IO = SocketIO(APP, async_mode=ASYNC_MODE)
HEARTBEAT_THREAD = None

START_TIME = datetime.now()

def milliseconds():
    '''Returns the elapsed milliseconds since the start of the program.'''
    delta_t = datetime.now() - START_TIME
    milli_sec = (delta_t.days * 24 * 60 * 60 + delta_t.seconds) * 1000 \
        + delta_t.microseconds / 1000.0
    return milli_sec

@APP.route('/')
def index():
    '''Route to round summary page.'''
    return render_template('rounds.html', async_mode=SOCKET_IO.async_mode)

@APP.route('/settings')
def settings():
    '''Route to settings page.'''
    return render_template('settings.html', async_mode=SOCKET_IO.async_mode, num_nodes=5)

@SOCKET_IO.on('connect')
def connect_handler():
    '''Print connection event.'''
    print 'Client connected.'
    HARDWARE_INTERFACE.start()
    global HEARTBEAT_THREAD
    if HEARTBEAT_THREAD is None:
        HEARTBEAT_THREAD = gevent.spawn(heartbeat_thread_function)

@SOCKET_IO.on('disconnect')
def disconnect_handler():
    '''Print disconnect event.'''
    print 'Client disconnected.'

@SOCKET_IO.on('get_timestamp')
def on_get_timestamp():
    '''Returns the elapsed milliseconds since the start of the program.'''
    return {'timestamp': milliseconds()}

@SOCKET_IO.on('get_settings')
def on_get_settings():
    '''doc string'''
    return {'nodes': HARDWARE_INTERFACE.get_settings_json()}

# todo: how should the frequency be sent?
@SOCKET_IO.on('set_frequency')
def on_set_frequency(data):
    '''doc string'''
    print data
    node_index = data['node']
    frequency = data['frequency']
    emit('frequency_set', {'node': node_index, 'frequency': \
        HARDWARE_INTERFACE.set_frequency_index(node_index, frequency)}, broadcast=True)

@SOCKET_IO.on('set_trigger_rssi')
def on_set_trigger_rssi(data):
    '''doc string'''
    print data
    node_index = data['node']
    trigger_rssi = data['trigger_rssi']
    emit('trigger_rssi_set', {'node': node_index, 'trigger_rssi': \
        HARDWARE_INTERFACE.set_trigger_rssi_index(node_index, trigger_rssi)}, broadcast=True)

@SOCKET_IO.on('capture_trigger_rssi')
def on_capture_trigger_rssi(data):
    '''doc string'''
    node_index = data['node']
    emit('trigger_rssi_set', {'node': node_index, 'trigger_rssi': \
        HARDWARE_INTERFACE.capture_trigger_rssi_index(node_index)}, broadcast=True)

@SOCKET_IO.on('simulate_pass')
def on_simulate_pass(data):
    '''doc string'''
    node_index = data['node']
    # todo: how should frequency be sent?
    emit('pass_record', {'frequency': HARDWARE_INTERFACE.nodes[node_index].frequency, \
        'timestamp': milliseconds()}, broadcast=True)

def pass_record_callback(frequency, milli_sec_since_lap):
    '''doc string'''
    print 'Pass record from {0}: {1}'.format(frequency, milli_sec_since_lap)
    SOCKET_IO.emit('pass_record', {'frequency': frequency, \
        'timestamp': milliseconds() - milli_sec_since_lap})

HARDWARE_INTERFACE.pass_record_callback = pass_record_callback

def hardware_log_callback(message):
    '''doc string'''
    print message
    SOCKET_IO.emit('hardware_log', message)

HARDWARE_INTERFACE.hardware_log_callback = hardware_log_callback

def heartbeat_thread_function():
    '''doc string'''
    while True:
        SOCKET_IO.emit('heartbeat', HARDWARE_INTERFACE.get_heartbeat_json())
        gevent.sleep(0.5)

if __name__ == '__main__':
    SOCKET_IO.run(APP, host='0.0.0.0', debug=True)
