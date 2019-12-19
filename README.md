# Delta 5 Race Timer

-------------------------------------------------------------------------------------------------------------
Changing the way to select the node i2c address using a pin in the nano

by pulling one of the pins(5-8) low i2cSlaveAddress will be assigned 8,10,12 or 14

by pulling pin 4 low you tell the nodes they are on board 2 so i2cSlaveAddress will be assigned 16,18,20 or 22

the rest of the code is as pulled from the orginal source 

-------------------------------------------------------------------------------------------------------------
 
 
<img src="doc/img/delta5racetimer.jpg" align="right" alt="Delta5 Race Timer"/>

Multi-node radio frequency race timing system for FPV drone racing. Uses the 5.8Ghz video signals already being broadcast by each drones to trigger a lap timer; no additional equipment is required on the drone.

Each receiver node is tuned to the video frequency that a drone is broadcasting on and then connected to a raspberry pi. By default, up to eight racing drones can be tracked in a race.

### Major Features
* The system hosts its own web server which is used to control the system, no additional software is needed, any device with a web browser can connect
* Automatic calibration; the system sets triggers at the start of each race
* Manage pilot names, assign them to heats, and after each race save the results to a local database
* Supports the standard 40 FPV video channels

### Hardware and Software Setup
To build the system, follow the instructions here: [/doc/Hardware and Software Setup Instructions.md](/doc/Hardware%20and%20Software%20Setup%20Instructions.md)

### User Guide
For initial setup and running races, follow these instructions: [/doc/User Guide.md](/doc/User%20Guide.md)

### Support
Have questions? Comments? Join us at the Delta 5 Race Timer Facebook Group page and we'll try to help troubleshoot.
https://www.facebook.com/groups/Delta5RaceTimer/
