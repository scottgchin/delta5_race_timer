'''Delta5 timing system server script'''

import sys
from datetime import datetime

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy

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
APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
APP.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
DB = SQLAlchemy(APP)
SOCKET_IO = SocketIO(APP, async_mode=ASYNC_MODE)
HEARTBEAT_THREAD = None

START_TIME = datetime.now()


# Database setup

class User(DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    username = DB.Column(DB.String(80), unique=True, nullable=False)
    email = DB.Column(DB.String(120), unique=True, nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username



# App routing locations

@APP.route('/')
def index():
    '''Route to round summary page.'''
    return render_template('rounds.html', async_mode=SOCKET_IO.async_mode)

@APP.route('/settings')
def settings():
    '''Route to settings page.'''
    return render_template('settings.html', async_mode=SOCKET_IO.async_mode, \
        num_nodes=HARDWARE_INTERFACE.num_nodes)

@APP.route('/race')
def race():
    '''Route to race management page.'''
    return render_template('race.html', async_mode=SOCKET_IO.async_mode, \
        num_nodes=HARDWARE_INTERFACE.num_nodes)

# Main program








# General socket io events

@SOCKET_IO.on('connect')
def connect_handler():
    '''Starts the delta 5 interface and starts a heartbeat thread to emit node data.'''
    print 'Client connected.'
    HARDWARE_INTERFACE.start()
    global HEARTBEAT_THREAD
    if HEARTBEAT_THREAD is None:
        HEARTBEAT_THREAD = gevent.spawn(heartbeat_thread_function)

@SOCKET_IO.on('disconnect')
def disconnect_handler():
    '''Print disconnect event.'''
    print 'Client disconnected.'

# Settings socket io events

@SOCKET_IO.on('set_frequency')
def on_set_frequency(data):
    '''Gets a node index number and frequency to update on the node.'''
    print data
    node_index = data['node']
    frequency = data['frequency']
    emit('frequency_set', {'node': node_index, 'frequency': \
        HARDWARE_INTERFACE.set_full_reset_frequency(node_index, frequency)}, broadcast=True)

# Race management socket io events

@SOCKET_IO.on('set_race_status')
def on_race_status(race_status):
    '''Gets 1 to start a race and 0 to stop a race.'''
    # On a starting a race, have a 2 to 5 second delay here after setting the hardware interface
    # setting to true and then sound the start buzzer tied into the clock function
    # stopping the race should stop and reset the timer
    emit('race_status_set', {'race_status': \
        HARDWARE_INTERFACE.set_race_status(race_status)}, broadcast=True)

@SOCKET_IO.on('save_laps')
def on_save_laps():
    '''Command to save current laps data to the database and clear the current laps.'''

@SOCKET_IO.on('clear_laps')
def on_clear_laps():
    '''Command to clear the current laps due to false start or practice.'''

# Functions to also be attached to the delte 5 interface class

def pass_record_callback(frequency, lap_time):
    '''Logs and emits a completed lap.'''
    print 'Pass record from {0}: {1}'.format(frequency, lap_time)
    SOCKET_IO.emit('pass_record', {'frequency': frequency, \
        'laptime': lap_time})

HARDWARE_INTERFACE.pass_record_callback = pass_record_callback

def hardware_log_callback(message):
    '''Print to the console and emits 'hardware_log' message'''
    print message
    SOCKET_IO.emit('hardware_log', message)

HARDWARE_INTERFACE.hardware_log_callback = hardware_log_callback

def heartbeat_thread_function():
    '''Emits 'heartbeat' and json node data: frequency, current_rssi, trigger_rssi, peak_rssi.'''
    while True:
        SOCKET_IO.emit('heartbeat', HARDWARE_INTERFACE.get_heartbeat_json())
        gevent.sleep(0.5)

if __name__ == '__main__':
    SOCKET_IO.run(APP, host='0.0.0.0', debug=True)