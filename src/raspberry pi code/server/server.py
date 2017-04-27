#!/usr/bin/env python
from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from datetime import datetime
from datetime import timedelta
from random import randint

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None

firmware_version = {'major': 0, 'minor': 1}
start_time = datetime.now()

mock_nodes = [
    {'frequency': 5685, 'current_rssi': 110, 'trigger_rssi': 50},
    {'frequency': 5760, 'current_rssi': 110, 'trigger_rssi': 50},
    {'frequency': 5800, 'current_rssi': 110, 'trigger_rssi': 50},
    {'frequency': 5860, 'current_rssi': 110, 'trigger_rssi': 50},
    {'frequency': 5905, 'current_rssi': 110, 'trigger_rssi': 50},
]

# returns the elapsed milliseconds since the start of the program
def milliseconds():
   dt = datetime.now() - start_time
   ms = (dt.days * 24 * 60 * 60 + dt.seconds) * 1000 + dt.microseconds / 1000.0
   return ms

@app.route('/')
def index():
    template_data = { 'nodes': mock_nodes }
    return render_template('index.html', async_mode=socketio.async_mode, **template_data)

@socketio.on('connect')
def connect_handler():
    print ('connected!!');

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
    return {'nodes': mock_nodes}

# todo: how should the frequency be sent?
@socketio.on('set_frequency')
def on_set_frequency(data):
    # todo: do this right
    print(data)
    index = data['node']
    frequency = data['frequency']
    mock_nodes[index]['frequency'] = frequency;
    emit('frequency_set', {'node': index, 'frequency': mock_nodes[index]['frequency']}, broadcast=True)

# todo: how should the frequency be sent?
@socketio.on('set_trigger_rssi')
def on_set_trigger_rssi(data):
    # todo: do this right
    print(data)
    index = data['node']
    trigger_rssi = data['trigger_rssi']
    mock_nodes[index]['trigger_rssi'] = trigger_rssi;
    emit('trigger_rssi_set', {'node': index, 'trigger_rssi': mock_nodes[index]['trigger_rssi']}, broadcast=True)

@socketio.on('capture_trigger_rssi')
def on_capture_trigger_rssi(data):
    index = data['node']
    # todo: do this right
    mock_nodes[index]['trigger_rssi'] = mock_nodes[index]['current_rssi']
    emit('trigger_rssi_set', {'node': index, 'trigger_rssi': mock_nodes[index]['trigger_rssi']}, broadcast=True)

@socketio.on('simulate_pass')
def on_simulate_pass(data):
    index = data['node']
    # todo: how should frequency be sent?
    emit('pass_record', {'frequency': mock_nodes[index]['frequency'], 'timestamp': milliseconds()}, broadcast=True)

def background_thread():
    while True:
        # todo: do this right
        for node in mock_nodes:
            node['current_rssi'] = randint(0,255)

        socketio.emit('heartbeat', {'current_rssi': [node['current_rssi'] for node in mock_nodes]})
        socketio.sleep(5)

if __name__ == '__main__':
    thread = socketio.start_background_task(target=background_thread)
    socketio.run(app, debug=True)
