// Delta 5 Race Timer by Scott Chin
// SPI driver based on fs_skyrf_58g-main.c Written by Simon Chambers
// I2C functions by Mike Ochtman
// Lap trigger function by Alex Huisman
//
// MIT License
//
// Copyright (c) 2017 Scott G Chin
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

#include <Wire.h>

#define rxFault 0x80
#define txFault 0x40
#define txRequest 0x20

// Node Setup -- Set the i2c address here
// Node 1 = 8, Node 2 = 10, Node 3 = 12, Node 4 = 14
// Node 5 = 16, Node 6 = 18, Node 7 = 20, Node 8 = 22
#define i2cSlaveAddress 8

const int slaveSelectPin = 10; // Setup data pins for rx5808 comms
const int spiDataPin = 11;
const int spiClockPin = 13;

const int buttonPin = 3; // Arduino D3 as a button to set rssiTriggerThreshold, ground button to press
int buttonState = 0;

// unsigned long rssiRisingTime = 0; // The time the rssi value is registered going above the threshold
// unsigned long rssiFallingTime = 0; // The time the rssi value is registered going below the threshold
bool crossing = false; // True when the quad is going through the gate
int rssiTriggerBandwidth = 10; // Added and subtracted from rssiTrigger, tries to account for noise in rssi
int rssiPeakHold = 0; // The peak rssi seen during a crossing event
unsigned long rssiPeakHoldTime = 0; // The time of the peak rssi during a crossing event
int rssiTriggerOffset = 20; // Subtracted from the peak rssi detected, accounts for variabilities crossing the gate
int rssiTriggerMinCheck = 40; // Used to set a low trigger on initialization

// Rssi smoothing variables
const int rssiSmoothingNumReadings = 50;
int rssiSmoothing[rssiSmoothingNumReadings];
int rssiSmoothingIndex = 0;
long rssiSmoothingTotal = 0;

// Use volatile for variables that will be used in interrupt service routines.
// "Volatile" instructs the compiler to get a fresh copy of the data rather than try to
// optimise temporary registers before using, as interrupts can change the value.

// Define data package for i2c comms, variables that can be changed by i2c
struct {
	byte volatile command; // I2C code to identify messages
	int volatile vtxFreq; // Frequency in mhz, 2 bytes
	int volatile rssi; // Current rssi, 2 bytes
	int volatile rssiTrigger; // Automatically set based on peak rssi value seen, 2 bytes
	int volatile rssiPeak; // Set rssi trigger, 2 bytes
	byte volatile lap; // Current lap number
	unsigned long volatile completedLapTime; // Calculated time of the last completed lap, milliseconds, 4 bytes
	unsigned long volatile lastLapTimeStamp; // Arduino clock time of the last completed lap, milliseconds, 4 bytes
	byte volatile raceStatus; // True (1) when the race has been started from the raspberry pi, False (0)
} commsTable;

byte volatile ioBuffer[32]; // Data array for sending over i2c, up to 32 bytes per message
int volatile ioBufferSize = 0;
int volatile ioBufferIndex = 0;
bool volatile dataReady = false; // Flag to trigger a Serial printout after an i2c event

// Define vtx frequencies in mhz and their hex code for setting the rx5808 module
int vtxFreqTable[] = {
  5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725, // Band A
  5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866, // Band B
  5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945, // Band E
  5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880, // Band F
  5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917  // Band C / Raceband
};
uint16_t vtxHexTable[] = {
  0x2A05, 0x299B, 0x2991, 0x2987, 0x291D, 0x2913, 0x2909, 0x289F, // Band A
  0x2903, 0x290C, 0x2916, 0x291F, 0x2989, 0x2992, 0x299C, 0x2A05, // Band B
  0x2895, 0x288B, 0x2881, 0x2817, 0x2A0F, 0x2A19, 0x2A83, 0x2A8D, // Band E
  0x2906, 0x2910, 0x291A, 0x2984, 0x298E, 0x2998, 0x2A02, 0x2A0C, // Band F
  0x281D, 0x288F, 0x2902, 0x2914, 0x2987, 0x2999, 0x2A0C, 0x2A1E  // Band C / Raceband
};


// Initialize program
void setup() {
	Serial.begin(115200); // Start serial for output/debugging

	pinMode(buttonPin, INPUT); // Define digital button for setting rssi trigger
	digitalWrite(buttonPin, HIGH);

	pinMode (slaveSelectPin, OUTPUT); // RX5808 comms
	pinMode (spiDataPin, OUTPUT);
	pinMode (spiClockPin, OUTPUT);
	digitalWrite(slaveSelectPin, HIGH);

	while (!Serial) {}; // Wait for the Serial port to initialise
	Serial.print("Ready: ");
	Serial.println(i2cSlaveAddress);

	Wire.begin(i2cSlaveAddress); // I2C slave address setup
	Wire.onReceive(i2cReceive); // Trigger 'i2cReceive' function on incoming data
	Wire.onRequest(i2cTransmit); // Trigger 'i2cTransmit' function for outgoing data, on master request

	// Initialize commsTable defaults
	commsTable.vtxFreq = 5800; // Frequency is set by pi when number of nodes is known
	commsTable.rssi = 0;
	commsTable.rssiTrigger = rssiRead() + rssiTriggerMinCheck; // Sets a low trigger value to ensure capturing the first gate crossing
	commsTable.rssiPeak = 0;
	commsTable.lap = 0;
	commsTable.completedLapTime = 0;
	commsTable.lastLapTimeStamp = 0;
	commsTable.raceStatus = 0; // True when the race has been started from the raspberry pi

	setRxModule(commsTable.vtxFreq); // Setup rx module to default frequency

	// Initialize rssi smoothing array
	for (int index = 0; index < rssiSmoothingNumReadings; index++) {
		rssiSmoothing[index] = 0;
	}
}

// Functions for the rx5808 module
void SERIAL_SENDBIT1() {
	digitalWrite(spiClockPin, LOW);
	delayMicroseconds(300);
	digitalWrite(spiDataPin, HIGH);
	delayMicroseconds(300);
	digitalWrite(spiClockPin, HIGH);
	delayMicroseconds(300);
	digitalWrite(spiClockPin, LOW);
	delayMicroseconds(300);
}
void SERIAL_SENDBIT0() {
	digitalWrite(spiClockPin, LOW);
	delayMicroseconds(300);
	digitalWrite(spiDataPin, LOW);
	delayMicroseconds(300);
	digitalWrite(spiClockPin, HIGH);
	delayMicroseconds(300);
	digitalWrite(spiClockPin, LOW);
	delayMicroseconds(300);
}
void SERIAL_ENABLE_LOW() {
	delayMicroseconds(100);
	digitalWrite(slaveSelectPin,LOW);
	delayMicroseconds(100);
}
void SERIAL_ENABLE_HIGH() {
	delayMicroseconds(100);
	digitalWrite(slaveSelectPin,HIGH);
	delayMicroseconds(100);
}

// Set the frequency given on the rx5808 module
void setRxModule(int frequency) {
	uint8_t i; // Used in the for loops

	uint8_t index; // Find the index in the frequency lookup table
	for (i = 0; i < sizeof(vtxFreqTable); i++) {
		if (frequency == vtxFreqTable[i]) {
			index = i;
			break;
		}
	}

	uint16_t vtxHex; // Get the hex value to send to the rx module
	vtxHex = vtxHexTable[index];

	// bit bash out 25 bits of data / Order: A0-3, !R/W, D0-D19 / A0=0, A1=0, A2=0, A3=1, RW=0, D0-19=0
	SERIAL_ENABLE_HIGH();
	delay(2);
	SERIAL_ENABLE_LOW();
	SERIAL_SENDBIT0();
	SERIAL_SENDBIT0();
	SERIAL_SENDBIT0();
	SERIAL_SENDBIT1();
	SERIAL_SENDBIT0();

	for (i = 20; i > 0; i--) SERIAL_SENDBIT0(); // Remaining zeros

	SERIAL_ENABLE_HIGH(); // Clock the data in
	delay(2);
	SERIAL_ENABLE_LOW();

	// Second is the channel data from the lookup table, 20 bytes of register data are sent, but the
	// MSB 4 bits are zeros register address = 0x1, write, data0-15=vtxHex data15-19=0x0
	SERIAL_ENABLE_HIGH();
	SERIAL_ENABLE_LOW();

	SERIAL_SENDBIT1(); // Register 0x1
	SERIAL_SENDBIT0();
	SERIAL_SENDBIT0();
	SERIAL_SENDBIT0();

	SERIAL_SENDBIT1(); // Write to register

	// D0-D15, note: loop runs backwards as more efficent on AVR
	for (i = 16; i > 0; i--) {
		if (vtxHex & 0x1) { // Is bit high or low?
			SERIAL_SENDBIT1();
		}
		else {
			SERIAL_SENDBIT0();
		}
		vtxHex >>= 1; // Shift bits along to check the next one
	}

	for (i = 4; i > 0; i--) // Remaining D16-D19
		SERIAL_SENDBIT0();

	SERIAL_ENABLE_HIGH(); // Finished clocking data in
	delay(2);

	digitalWrite(slaveSelectPin,LOW);
	digitalWrite(spiClockPin, LOW);
	digitalWrite(spiDataPin, LOW);
}

// This function only exists for rssi thriggering from the arduino digital button
void setRssiThreshold() {
	Serial.println(" ");
	Serial.println("Setting rssiTreshold.");

	int thresholdAvg = rssiRead(); // Calculate rssiThreshold average
	thresholdAvg += rssiRead();
	thresholdAvg += rssiRead();
	thresholdAvg = thresholdAvg/3; // Average of 3 rssi readings
	commsTable.rssiTrigger = thresholdAvg;

	Serial.print("rssiTrigger: ");
	Serial.println(commsTable.rssiTrigger);
}

// Read the RSSI value for the current channel
int rssiRead() {
	// This function with 50 analog reads takes around 5 ms
	long rssiAvg = 0; // Calculate rssi average
	for (uint8_t i = 0; i < 50; i++){
		rssiAvg += analogRead(0); // Pin A0
	}
	rssiAvg = (int) (rssiAvg / 50); // Average of 50 rssi readings
	rssiAvg = constrain(rssiAvg, 1, 32000); // Positive 2 byte limit, not really needed
	return rssiAvg;
}

// Only used for serial printing the lap times
void lapCompleted() {
	float h, m, s, ms;
	unsigned long over;

	m = int(commsTable.completedLapTime / 60000); // Convert millis() time to m, s, ms
	over = commsTable.completedLapTime % 60000;
	s = int(over / 1000);
	over = over % 1000;
	ms = int(over);

	Serial.println(" ");
	Serial.print("Lap: ");
	Serial.print(commsTable.lap);
	Serial.print(" Time: ");
	Serial.print(m, 0);
	Serial.print("m ");
	Serial.print(s, 0);
	Serial.print("s ");
	Serial.print(ms, 0);
	Serial.println("ms");
}

// Main loop
void loop() {
	//commsTable.raceStatus = 1; // Uncomment for individual node testing
	//delay(250);

	// Get the next reading
	rssiSmoothing[rssiSmoothingIndex] = rssiRead();
	// Advance the index and wrap if at the end
	rssiSmoothingIndex += 1;
	if (rssiSmoothingIndex >= rssiSmoothingNumReadings) { rssiSmoothingIndex = 0; }
	// Calculate and save to comms table the running average
	rssiSmoothingTotal = 0;
	for (int index = 0; index < rssiSmoothingNumReadings; index++) {
		rssiSmoothingTotal += rssiSmoothing[index];
	}
	commsTable.rssi = (int) (rssiSmoothingTotal / rssiSmoothingNumReadings);

	// Wait for raceStatus True
	if (commsTable.raceStatus == 1) {
		// Find the peak rssi and the time it occured during a crossing event
		if (crossing == true && commsTable.rssi > rssiPeakHold) {
			rssiPeakHold = commsTable.rssi;
			rssiPeakHoldTime = millis();
		}
		// Rssi above threshold and quad not already crossing the gate, quad is entering to start gate
		if ((commsTable.rssi > (commsTable.rssiTrigger + rssiTriggerBandwidth)) && (crossing == false)) {
			// rssiRisingTime = millis(); // Sets the arduino clock time of the quad approaching the gate
			// Serial.print("rssiRisingTime: ");
			// Serial.println(rssiRisingTime);
			crossing = true; // Quad is going through the gate
			Serial.println("Crossing = True");
		}
		// Rssi below threshold and quad is crossing the gate, quad has now left the start gate
		else if ((commsTable.rssi < (commsTable.rssiTrigger - rssiTriggerBandwidth)) && (crossing == true)) {
			// rssiFallingTime = millis(); // Sets the arduino clock time of the quad leaving the gate
			// Serial.print("rssiFallingTime: ");
			// Serial.println(rssiFallingTime);
			crossing = false; // Quad has left the gate
			Serial.println("Crossing = False");

			// Calculates the completed lap time
			// commsTable.completedLapTime = rssiRisingTime + (rssiFallingTime - rssiRisingTime)/2 - commsTable.lastLapTimeStamp;
			commsTable.completedLapTime = rssiPeakHoldTime - commsTable.lastLapTimeStamp;

			commsTable.rssiPeak = rssiPeakHold; // Saves the peak rssi value to the comms table
			rssiPeakHold = 0;

			// Race starting, this logs the first time through the gate
			if (commsTable.lastLapTimeStamp == 0) {
				// Sets the arduino clock time through the gate
				// commsTable.lastLapTimeStamp = rssiRisingTime + ((rssiFallingTime - rssiRisingTime)/2);
				commsTable.lastLapTimeStamp = rssiPeakHoldTime;
				commsTable.rssiTrigger = commsTable.rssiPeak - rssiTriggerOffset; // Sets a new trigger
				Serial.println("Fly over start!");
			}
			else { // Race is running, this is a lap completed
				// Records the arduino clock time through the gate
				// commsTable.lastLapTimeStamp = rssiRisingTime + ((rssiFallingTime - rssiRisingTime)/2);
				commsTable.lastLapTimeStamp = rssiPeakHoldTime;
				commsTable.lap = commsTable.lap + 1;
				lapCompleted(); // Serial prints lap time
			}
		}
	}

	buttonState = digitalRead(buttonPin); // Detect button press to set rssi trigger
	if (buttonState == LOW) {
		Serial.println("Button pressed.");
		setRssiThreshold();
	}

	if (dataReady) { // Set True in i2cReceive, print current commsTable and ioBuffer
		// printCommsTable();
		// printIoBuffer();
		dataReady = false;
	}
}


// Function called by twi interrupt service when master sends information to the slave
// or when master sets up a specific read request
void i2cReceive(int byteCount) { // Number of bytes in rx buffer
	// If byteCount is zero, the master only checked for presence of the slave device, no response necessary
	if (byteCount == 0) {
		Serial.println("Error: no bytes for a receive?");
		return;
	}

	if (byteCount != Wire.available()) {
		Serial.println("Error: rx byte count and wire available don't agree");
	}

	commsTable.command = Wire.read(); // The first byte sent is a command byte

	if (commsTable.command > 0x50) { // Commands > 0x50 are writes TO this slave
		i2cHandleRx(commsTable.command);
	}
	else { // Otherwise this is a request FROM this device
		if (Wire.available()) { // There shouldn't be any data present on the line for a read request
			Serial.println("Error: Wire.available() on a read request.");
			while(Wire.available()) {
				Wire.read();
			}
		}
	}
	dataReady = true; // Flag to the main loop to print the commsTable
}

bool readAndValidateIoBuffer(int expectedSize) {
	uint8_t checksum = 0;
	ioBufferSize = 0;
	ioBufferIndex = 0;

	if (expectedSize == 0) {
		Serial.println("No Expected Size");
		return true;
	}

	if (!Wire.available()) {
		Serial.println("Nothing Avialable");
		return false;
	}

	while(Wire.available()) {
		ioBuffer[ioBufferSize++] = Wire.read();
		if (expectedSize < ioBufferSize) {
			checksum += ioBuffer[ioBufferSize-1];
		}
	}

	if (checksum != ioBuffer[ioBufferSize-1] ||
		ioBufferSize-1 != expectedSize) {
		Serial.println("invalid checksum");
		Serial.println(checksum);
		Serial.println(ioBuffer[ioBufferSize-1]);
		Serial.println(ioBufferSize-1);
		Serial.println(expectedSize);
		return false;
	}

	return true;
}

uint8_t ioBufferRead8() {
	return ioBuffer[ioBufferIndex++];
}

uint16_t ioBufferRead16() {
	uint16_t result;
	result = ioBuffer[ioBufferIndex++];
	result = (result << 8) | ioBuffer[ioBufferIndex++];
	return result;
}

void ioBufferWrite8(uint8_t data) {
	ioBuffer[ioBufferSize++] = data;
}

void ioBufferWrite16(uint16_t data) {
	ioBuffer[ioBufferSize++] = (uint16_t)(data >> 8);
	ioBuffer[ioBufferSize++] = (uint16_t)(data & 0xFF);
}

void ioBufferWrite32(uint32_t data) {
	ioBuffer[ioBufferSize++] = (uint16_t)(data >> 24);
	ioBuffer[ioBufferSize++] = (uint16_t)(data >> 16);
	ioBuffer[ioBufferSize++] = (uint16_t)(data >> 8);
	ioBuffer[ioBufferSize++] = (uint16_t)(data & 0xFF);
}

void ioBufferWriteChecksum() {
	uint8_t checksum = 0;
	for (int i = 0; i < ioBufferSize ; i++) {
		checksum += ioBuffer[i];
	}

	ioBufferWrite8(checksum);
}

// Function called by i2cReceive for writes TO this device, the I2C Master has sent data
// using one of the SMBus write commands, if the MSB of 'command' is 0, master is sending only
// Returns the number of bytes read, or FF if unrecognised command or mismatch between
// data expected and received
byte i2cHandleRx(byte command) { // The first byte sent by the I2C master is the command
	bool success = false;

	switch (command) {
		case 0x51: // Full reset, initialize arduinos, change frequency
			if (readAndValidateIoBuffer(2)) { // Confirm expected number of bytes
				commsTable.vtxFreq = ioBufferRead16();
				setRxModule(commsTable.vtxFreq); // Shouldn't do this in Interrupt Service Routine
				commsTable.rssiTrigger = (commsTable.rssi + rssiTriggerMinCheck);
				commsTable.rssiPeak = 0;
				commsTable.lap = 0;
				commsTable.completedLapTime = 0;
				commsTable.lastLapTimeStamp = 0;
				commsTable.raceStatus = 0;
				success = true;
			}
			break;
		case 0x52: // Set race status, reset for a new race or stop
			if (readAndValidateIoBuffer(1)) { // Confirm expected number of bytes
				commsTable.raceStatus = ioBufferRead8();
				if (commsTable.raceStatus == 1) {
					commsTable.rssiTrigger = (commsTable.rssi + rssiTriggerMinCheck);
					commsTable.rssiPeak = 0;
					commsTable.lap = 0;
					commsTable.completedLapTime = 0;
					commsTable.lastLapTimeStamp = 0; // Reset to zero to catch first gate fly through again
				}
				else {
					commsTable.raceStatus = 0;
				}
				success = true;
			}
			break;
	}

	commsTable.command = 0; // Clear previous command

	if (!success) { // Set control to rxFault if 0xFF result
		 Serial.print("RX Fault command: ");
		 Serial.println(command, HEX);
	}
	return success;
}

// Function called by twi interrupt service when the Master wants to get data from the Slave
// No parameters and no returns
// A transmit buffer (ioBuffer) is populated with the data before sending.
void i2cTransmit() {
	ioBufferSize = 0;

	switch (commsTable.command) {
		case 0x00: // Send i2cSlaveAddress
			ioBufferWrite8(i2cSlaveAddress);
			break;
		case 0x02: // Send lap number and calculated lap time in milliseconds
			ioBufferWrite8(commsTable.lap);
			ioBufferWrite32(commsTable.completedLapTime);
			break;
		case 0x03: // Send frequency
			ioBufferWrite16(commsTable.vtxFreq);
			break;
		case 0x05: // Send lap number, time since last lap, and current rssi
			ioBufferWrite8(commsTable.lap);
			ioBufferWrite32(millis() - commsTable.lastLapTimeStamp);
			ioBufferWrite16(commsTable.rssi);
			break;
		case 0x07: // Send all rssi info
			ioBufferWrite16(commsTable.rssi);
			ioBufferWrite16(commsTable.rssiTrigger);
			ioBufferWrite16(commsTable.rssiPeak);
			break;
		default: // If an invalid command is sent, write nothing back, master must react
			Serial.print("TX Fault command: ");
			Serial.println(commsTable.command, HEX);
	}

	commsTable.command = 0; // Clear previous command

	if (ioBufferSize > 0) { // If there is pending data, send it
		ioBufferWriteChecksum();
		Wire.write((byte *)&ioBuffer, ioBufferSize);
	}
}

// Prints to commsTable to arduino serial console
// Are all these builder lines needed?
void printCommsTable() {
	String builder = "";
	builder = "commsTable contents:";
	Serial.println(builder);
	builder = "  Command: ";
	builder += String(commsTable.command, HEX);
	Serial.println(builder);
	builder = "  VTX Freq: ";
	builder += commsTable.vtxFreq;
	Serial.println(builder);
	builder = "  RSSI: ";
	builder += commsTable.rssi;
	Serial.println(builder);
	builder = "  RSSI Triger: ";
	builder += commsTable.rssiTrigger;
	Serial.println(builder);
	builder = "  Lap: ";
	builder += commsTable.lap;
	Serial.println(builder);
	builder = "  Completed Lap Time: ";
	builder += commsTable.completedLapTime;
	Serial.println(builder);
	builder = "  Race Status: ";
	builder += commsTable.raceStatus;
	Serial.println(builder);
	Serial.println();
}

// Prints the transmit buffer to arduino serial console
void printIoBuffer() {
	Serial.println("Transmit Table:");
	for (byte i = 0; i < 32; i++) {
		Serial.print(" ");
		Serial.print(ioBuffer[i]);
	}
	Serial.println(); // ends print line
}
