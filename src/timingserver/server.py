#!/usr/bin/env python
import gevent
import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from datetime import datetime
from datetime import timedelta

import sys

if sys.platform.lower().startswith('win'):
    from MockInterface import get_hardware_interface
elif sys.platform.lower().startswith('linux'):
    from TimingServerDelta5Interface import get_hardware_interface

hardwareInterface = get_hardware_interface()

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = "gevent"

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
heartbeat_thread = None

firmware_version = {'major': 0, 'minor': 1}
start_time = datetime.now()

# returns the elapsed milliseconds since the start of the program
def milliseconds():
   dt = datetime.now() - start_time
   ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
   return ms

@app.route('/')
def index():
    template_data = { }
    return render_template('index.html', async_mode=socketio.async_mode, **template_data)

@app.route('/graphs')
def graphs():
    return render_template('graphs.html', async_mode=socketio.async_mode)

@app.route('/rssi')
def rssi():
    return render_template('rssi.html', async_mode=socketio.async_mode)

@socketio.on('connect')
def connect_handler():
    print ('connected!!');
    hardwareInterface.start()
    global heartbeat_thread
    if (heartbeat_thread is None):
        heartbeat_thread = gevent.spawn(heartbeat_thread_function)

@socketio.on('disconnect')
def disconnect_handler():
    print ('disconnected!!');

@socketio.on('get_version')
def on_get_version():
    return firmware_version

@socketio.on('get_timestamp')
def on_get_timestamp():
    return {'timestamp': milliseconds()}

@socketio.on('get_settings')
def on_get_settings():
    return {'nodes': hardwareInterface.get_settings_json()}

@socketio.on('set_frequency')
def on_set_frequency(data):
    print(data)
    index = data['node']
    frequency = data['frequency']
    emit('frequency_set', {'node': index, 'frequency': hardwareInterface.set_full_reset_frequency(index, frequency)}, broadcast=True) # Added

@socketio.on('simulate_pass')
def on_simulate_pass(data):
    index = data['node']
    # todo: how should frequency be sent?
    emit('pass_record', {'node': index, 'frequency': hardwareInterface.nodes[index].frequency, 'timestamp': milliseconds()}, broadcast=True)

def pass_record_callback(node, ms_since_lap):
    print('Pass record from {0}{1}: {2}'.format(node.index, node.frequency, ms_since_lap))
    socketio.emit('pass_record', {'node': node.index, 'frequency': node.frequency, 'timestamp': milliseconds() - ms_since_lap})

hardwareInterface.pass_record_callback = pass_record_callback

def hardware_log_callback(message):
    print(message)
    socketio.emit('hardware_log', message)

hardwareInterface.hardware_log_callback = hardware_log_callback

def heartbeat_thread_function():
    while True:
        socketio.emit('heartbeat', hardwareInterface.get_heartbeat_json())
        gevent.sleep(0.5)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', debug=True)
