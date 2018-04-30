#!/usr/bin/env python
import gevent
import gevent.monkey
gevent.monkey.patch_all()

import json
import os

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect

import sys

import argparse

parser = argparse.ArgumentParser(description='Timing Server')
parser.add_argument('--mock', dest='mock', action='store_true', default=False, help="use mock data for testing")
args = parser.parse_args()

sys.path.append('../delta5interface')
if args.mock or sys.platform.lower().startswith('win'):
    from MockInterface import get_hardware_interface
elif sys.platform.lower().startswith('linux'):
    from Delta5Interface import get_hardware_interface

hardwareInterface = get_hardware_interface()

# frequencies
band_channel_frequency = []
# Band A - Team BlackSheep, RangeVideo, SpyHawk, FlyCamOne USA
band_channel_frequency.append({'band':'A', 'channel':'A1', 'frequency':'5865'})
band_channel_frequency.append({'band':'A', 'channel':'A2', 'frequency':'5845'})
band_channel_frequency.append({'band':'A', 'channel':'A3', 'frequency':'5825'})
band_channel_frequency.append({'band':'A', 'channel':'A4', 'frequency':'5805'})
band_channel_frequency.append({'band':'A', 'channel':'A5', 'frequency':'5785'})
band_channel_frequency.append({'band':'A', 'channel':'A6', 'frequency':'5765'})
band_channel_frequency.append({'band':'A', 'channel':'A7', 'frequency':'5745'})
band_channel_frequency.append({'band':'A', 'channel':'A8', 'frequency':'5725'})
# Band B - FlyCamOne Europe
band_channel_frequency.append({'band':'B', 'channel':'B1', 'frequency':'5733'})
band_channel_frequency.append({'band':'B', 'channel':'B2', 'frequency':'5752'})
band_channel_frequency.append({'band':'B', 'channel':'B3', 'frequency':'5771'})
band_channel_frequency.append({'band':'B', 'channel':'B4', 'frequency':'5790'})
band_channel_frequency.append({'band':'B', 'channel':'B5', 'frequency':'5809'})
band_channel_frequency.append({'band':'B', 'channel':'B6', 'frequency':'5828'})
band_channel_frequency.append({'band':'B', 'channel':'B7', 'frequency':'5847'})
band_channel_frequency.append({'band':'B', 'channel':'B8', 'frequency':'5866'})
# Band E - HobbyKing, Foxtech
band_channel_frequency.append({'band':'E', 'channel':'E1', 'frequency':'5705'})
band_channel_frequency.append({'band':'E', 'channel':'E2', 'frequency':'5685'})
band_channel_frequency.append({'band':'E', 'channel':'E3', 'frequency':'5665'})
band_channel_frequency.append({'band':'E', 'channel':'E4', 'frequency':'5645'})
band_channel_frequency.append({'band':'E', 'channel':'E5', 'frequency':'5885'})
band_channel_frequency.append({'band':'E', 'channel':'E6', 'frequency':'5905'})
band_channel_frequency.append({'band':'E', 'channel':'E7', 'frequency':'5925'})
band_channel_frequency.append({'band':'E', 'channel':'E8', 'frequency':'5945'})
# Band F - ImmersionRC, Iftron
band_channel_frequency.append({'band':'F', 'channel':'F1', 'frequency':'5740'})
band_channel_frequency.append({'band':'F', 'channel':'F2', 'frequency':'5760'})
band_channel_frequency.append({'band':'F', 'channel':'F3', 'frequency':'5780'})
band_channel_frequency.append({'band':'F', 'channel':'F4', 'frequency':'5800'})
band_channel_frequency.append({'band':'F', 'channel':'F5', 'frequency':'5820'})
band_channel_frequency.append({'band':'F', 'channel':'F6', 'frequency':'5840'})
band_channel_frequency.append({'band':'F', 'channel':'F7', 'frequency':'5860'})
band_channel_frequency.append({'band':'F', 'channel':'F8', 'frequency':'5880'})
# Band L - Lowband
band_channel_frequency.append({'band':'L', 'channel':'L1', 'frequency':'5362'})
band_channel_frequency.append({'band':'L', 'channel':'L2', 'frequency':'5399'})
band_channel_frequency.append({'band':'L', 'channel':'L3', 'frequency':'5436'})
band_channel_frequency.append({'band':'L', 'channel':'L4', 'frequency':'5473'})
band_channel_frequency.append({'band':'L', 'channel':'L5', 'frequency':'5510'})
band_channel_frequency.append({'band':'L', 'channel':'L6', 'frequency':'5547'})
band_channel_frequency.append({'band':'L', 'channel':'L7', 'frequency':'5584'})
band_channel_frequency.append({'band':'L', 'channel':'L8', 'frequency':'5621'})
# Band R - Raceband
band_channel_frequency.append({'band':'R', 'channel':'R1', 'frequency':'5658'})
band_channel_frequency.append({'band':'R', 'channel':'R2', 'frequency':'5695'})
band_channel_frequency.append({'band':'R', 'channel':'R3', 'frequency':'5732'})
band_channel_frequency.append({'band':'R', 'channel':'R4', 'frequency':'5769'})
band_channel_frequency.append({'band':'R', 'channel':'R5', 'frequency':'5806'})
band_channel_frequency.append({'band':'R', 'channel':'R6', 'frequency':'5843'})
band_channel_frequency.append({'band':'R', 'channel':'R7', 'frequency':'5880'})
band_channel_frequency.append({'band':'R', 'channel':'R8', 'frequency':'5917'})

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = "gevent"

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
heartbeat_thread = None

firmware_version = {'major': 0, 'minor': 1}

def parse_json(data):
    if isinstance(data, basestring):
        return json.loads(data)
    return data

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

@socketio.on('shutdown_pi')
def on_shutdown_pi():
    '''Shutdown the raspberry pi.'''
    print('Shutting down pi')
    os.system("sudo shutdown now")

@socketio.on('restart_pi')
def on_shutdown_pi():
    '''Restart the raspberry pi.'''
    print('Restarting pi')
    os.system("sudo restart now")

@socketio.on('get_band_channel_frequency')
def on_get_band_channel_frequency():
    return {'band_channel_frequency':band_channel_frequency}

@socketio.on('get_version')
def on_get_version():
    return firmware_version

@socketio.on('get_timestamp')
def on_get_timestamp():
    print('get_timestamp')
    return {'timestamp': hardwareInterface.milliseconds()}

@socketio.on('get_settings')
def on_get_settings():
    print('get_settings')
    return hardwareInterface.get_settings_json()

@socketio.on('get_system_info')
def on_get_system_info():
    print('get_system_info')
    return hardwareInterface.get_system_info_json()

@socketio.on('set_frequency')
def on_set_frequency(data):
    data = parse_json(data)
    print(data)
    index = data['node']
    frequency = data['frequency']
    hardwareInterface.set_frequency(index, frequency)
    emit('frequency_set', hardwareInterface.get_frequency_json(index), broadcast=True)

@socketio.on('set_calibration_threshold')
def on_set_calibration_threshold(data):
    data = parse_json(data)
    print(data)
    calibration_threshold = data['calibration_threshold']
    hardwareInterface.set_calibration_threshold_global(calibration_threshold)
    emit('calibration_threshold_set', hardwareInterface.get_calibration_threshold_json(), broadcast=True)

@socketio.on('set_calibration_offset')
def on_set_calibration_offset(data):
    data = parse_json(data)
    print(data)
    calibration_offset = data['calibration_offset']
    hardwareInterface.set_calibration_offset_global(calibration_offset)
    emit('calibration_offset_set', hardwareInterface.get_calibration_offset_json(), broadcast=True)

@socketio.on('set_trigger_threshold')
def on_set_trigger_threshold(data):
    data = parse_json(data)
    print(data)
    trigger_threshold = data['trigger_threshold']
    hardwareInterface.set_trigger_threshold_global(trigger_threshold)
    emit('trigger_threshold_set', hardwareInterface.get_trigger_threshold_json(), broadcast=True)

@socketio.on('set_filter_ratio')
def on_set_filter_ratio(data):
    data = parse_json(data)
    print(data)
    filter_ratio = data['filter_ratio']
    hardwareInterface.set_filter_ratio_global(filter_ratio)
    emit('filter_ratio_set', hardwareInterface.get_filter_ratio_json(), broadcast=True)

# Keep this around for a bit.. old version of the api
# @socketio.on('reset_auto_calibration')
# def on_reset_auto_calibration():
#     print('reset_auto_calibration all')
#     hardwareInterface.enable_calibration_mode();

@socketio.on('reset_auto_calibration')
def on_reset_auto_calibration(data):
    data = parse_json(data)
    print(data)
    index = data['node']
    if index == -1:
        print('reset_auto_calibration all')
        hardwareInterface.enable_calibration_mode()
    else:
        print('reset_auto_calibration {0}'.format(index))
        hardwareInterface.set_calibration_mode(index, True)

@socketio.on('simulate_pass')
def on_simulate_pass(data):
    data = parse_json(data)
    index = data['node']
    # todo: how should frequency be sent?
    emit('pass_record', {'node': index, 'frequency': hardwareInterface.nodes[index].frequency, 'timestamp': hardwareInterface.milliseconds()}, broadcast=True)

def pass_record_callback(node, ms_since_lap):
    print('Pass record from {0}{1}: {2}, {3}'.format(node.index, node.frequency, ms_since_lap, hardwareInterface.milliseconds() - ms_since_lap))
    #TODO: clean this up
    socketio.emit('pass_record', {
        'node': node.index,
        'frequency': node.frequency,
        'timestamp': hardwareInterface.milliseconds() - ms_since_lap,
        'trigger_rssi': node.trigger_rssi,
        'peak_rssi_raw': node.peak_rssi_raw,
        'peak_rssi': node.peak_rssi})

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
