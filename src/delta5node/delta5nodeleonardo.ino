//#include <I2C_Anything.h>
#include <EEPROM.h>
//#include <SoftwareSerial.h>
#include <Wire.h>
/*
 * RaceBox - Slave
 *
 * RaceBand 1 (C) - 5658 Mhz 32
 * RaceBand 2 (C) - 5695 Mhz 33
 * RaceBand 3 (C) - 5732 Mhz 34
 * RaceBand 4 (C) - 5769 Mhz 35
 * RaceBand 5 (C) - 5806 Mhz 36
 * RaceBand 6 (C) - 5843 Mhz 37
 * RaceBand 7 (C) - 5880 Mhz 38
 * RaceBand 8 (C) - 5917 Mhz 39
 *
 * SRSSIMS - set minimum trigger stringth
 * SVTX - set the VTX channel
 * TAV - last tracked time available
 * LTT - get the last tracked time
 * GMLT - gets minimum lap time
 * SMLT - sets minimum lap time
 * SRST - soft reset
 * GRSSIS - getting the setted RSSI trigger strength
 * SET_I2C_ID X
 * INIT_SETUP X
 * CRSSI
 * ILT - invalidate last time tracking
 * GSSS - get smart sense strength
 * P_GSSS - serial print smart sense strength
 * GSSCO - get smart sense strength cut off
 * SSSCO - set smart sense strength cut off
 * FWV - gets the firmware version
 */

#define spiDataPin 14
#define slaveSelectPin 15
#define spiClockPin 16
#define rssiPinA A3
#define MIN_TUNE_TIME 25
#define RSSI_READS 50
#define RSSI_MIN_VAL 90
#define RSSI_MAX_VAL 220


#define TIME_ACCURACY 0
#define RBS_VERSION 101

// Channels to sent to the SPI registers
const uint16_t channelTable[] PROGMEM = {
  // Channel 1 - 8
  0x2A05,    0x299B,    0x2991,    0x2987,    0x291D,    0x2913, 0x2909,    0x289F,    // Band A
  0x2903,    0x290C,    0x2916,    0x291F,    0x2989,    0x2992, 0x299C,    0x2A05,    // Band B
  0x2895,    0x288B,    0x2881,    0x2817,    0x2A0F,    0x2A19, 0x2A83,    0x2A8D,    // Band E
  0x2906,    0x2910,    0x291A,    0x2984,    0x298E,    0x2998, 0x2A02,    0x2A0C,    // Band F / Airwave
  0x281D,    0x288F,    0x2902,    0x2914,    0x2987,    0x2999, 0x2A0C,    0x2A1E     // Band C / Immersion Raceband
};

// Channels with their Mhz Values
const uint16_t channelFreqTable[] PROGMEM = {
  // Channel 1 - 8
  5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725, // Band A
  5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866, // Band B
  5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945, // Band E
  5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880, // Band F / Airwave
  5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917  // Band C / Immersion Raceband
};

// do coding as simple hex value to save memory.
const uint8_t channelNames[] PROGMEM = {
  0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, // Band A
  0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, // Band B
  0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, // Band E
  0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, // Band F / Airwave
  0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8  // Band C / Immersion Raceband
};

// All Channels of the above List ordered by Mhz
const uint8_t channelList[] PROGMEM = {
  19, 18, 32, 17, 33, 16, 7, 34, 8, 24, 6, 9, 25, 5, 35, 10, 26, 4, 11, 27, 3, 36, 12, 28, 2, 13, 29, 37, 1, 14, 30, 0, 15, 31, 38, 20, 21, 39, 22, 23
};

unsigned long time_tracking_ts = 0;
unsigned int channel = 0;
byte num_available_channels = sizeof(channelTable) / sizeof(channelTable[0]);
uint16_t rssi_best=0; // used for band scaner
uint16_t rssi_min_a=RSSI_MIN_VAL;
uint16_t rssi_max_a=RSSI_MAX_VAL;
uint16_t rssi_setup_min_a=RSSI_MIN_VAL;
uint16_t rssi_setup_max_a=RSSI_MAX_VAL;
volatile uint16_t min_signal_for_triggering_lap_tracking;
volatile uint16_t smart_sense_signal_high;
volatile uint16_t smart_sense_signal;
volatile uint16_t smart_sense_signal_cut_off;
volatile uint16_t fw_version;

int i2c_slave_id = 1;
unsigned long time_of_tune = 0; // will store last time when tuner was changed

unsigned long last_tracked_time_stamp = 0;
bool first_tracked_time = true;
volatile unsigned long last_tracked_time = 0;
volatile unsigned long last_tracked_time_backup = 0;
volatile bool last_tracked_time_available = false;

volatile unsigned long min_lap_time = 0;

bool debugging = false;

void i2c_receive(int bytes);

#define WRM_NONE    0
#define WRM_TAV     1
#define WRM_LTT     2
#define WRM_GRSSIS  3
#define WRM_CRSSIS  4
#define WRM_GMLT    5
#define WRM_GSSS    6
#define WRM_GSSCO   7
#define WRM_SSSCO   8
#define WRM_VERSION 9

unsigned int wire_request_mode = 0;


void setup() {
   fw_version = RBS_VERSION;
  digitalWrite(rssiPinA, HIGH); // enable pull up resistor for less heat on the receiver

  Serial.begin(115200);
  Serial.print("LEONARDO UP AND RUNNING!");


  // SPI pins for RX control
  pinMode (slaveSelectPin, OUTPUT);
  pinMode (spiDataPin, OUTPUT);
  pinMode (spiClockPin, OUTPUT);

  // reading config from EEPROM
  channel = EEPROMReadInt(0);
  /*if(channel > num_available_channels || channel < 0){
    Serial.println("channel from EEPROM was invalid");
    channel = 0;
    EEPROMWriteInt(0,channel);
  }*/

  // min signal from triggering from EEPROM
  min_signal_for_triggering_lap_tracking = EEPROMReadInt(2);
  // check for default min triggering signal
  if(min_signal_for_triggering_lap_tracking == 0 || min_signal_for_triggering_lap_tracking >= 255){
    min_signal_for_triggering_lap_tracking = 100;
  }

   // I2C slave id
  i2c_slave_id = EEPROMReadInt(4);
  i2c_slave_id = 1;
  if(i2c_slave_id == 0 || i2c_slave_id > 32){
    i2c_slave_id = 1;
  }

  min_lap_time = EEPROMReadlong(6);
  if(min_lap_time < 3000){
    Serial.println("min_lap_time from EEPROM was invalid");
    min_lap_time = 3000;
    EEPROMWritelong(6,min_lap_time);
  }

  // SMART SENSE
  smart_sense_signal_high = min_signal_for_triggering_lap_tracking;
  smart_sense_signal = smart_sense_signal_high;
  smart_sense_signal_cut_off = EEPROMReadInt(8);
  // check for default min triggering signal
  if(smart_sense_signal_cut_off == 0 || smart_sense_signal_cut_off >= 100){
    smart_sense_signal_cut_off = 20;
  }

  Serial.print("SMART SENSE HIGH:");
  Serial.println(smart_sense_signal_high);

  Serial.print("SMART SENSE SIG:");
  Serial.println(smart_sense_signal);

  Serial.print("SMART SENSE CUT OFF:");
  Serial.println(smart_sense_signal_cut_off);

  setChannelModule(channel);
  print_current_channel();

  Serial.print("MIN SIGNAL:");
  Serial.println(min_signal_for_triggering_lap_tracking);

  Serial.print("MIN LAP TIME:");
  Serial.println(min_lap_time);

  // enabling I2C-Slave Mode
  Wire.begin(i2c_slave_id);
  Serial.print("enabled I2C slave mode ID: ");
  Serial.println(i2c_slave_id);
  Wire.onReceive(i2c_receive);
  Wire.onRequest(i2c_on_request);

  pinMode(13, OUTPUT);
}


// initial setup - first time setup
void init_setup(int id){
  set_i2c_id(id);
  setChannelModule(31 + id);
  EEPROMWriteInt(0,31 + id);
  print_current_channel();
}

void smart_sense_filter(uint16_t rssi_signal){

  if(rssi_signal > 200 && rssi_signal >= min_signal_for_triggering_lap_tracking){
    return;
  }


  if(rssi_signal > smart_sense_signal_high){
    //Serial.print("SMARTSENSE RAW SIG:");
    //Serial.println(rssi_signal);

    smart_sense_signal_high = rssi_signal;
    smart_sense_signal = smart_sense_signal_high - smart_sense_signal_cut_off;

    if(smart_sense_signal < min_signal_for_triggering_lap_tracking){
      smart_sense_signal = min_signal_for_triggering_lap_tracking;
    }

    //Serial.print("SMARTSENSE NEW SIG HIGH:");
    //Serial.println(smart_sense_signal_high);

    //Serial.print("SMARTSENSE NEW SIG:");
    //Serial.println(smart_sense_signal);
  }
}

void loop() {
  if(TIME_ACCURACY == 1){
   time_tracking_ts = millis();
  }

  // checking if there is serial input
  if(Serial.available()){
    String incomming = Serial.readString();
    process_cmd(incomming);
  }

  sensor_for_time_tracking();
}

void soft_reset(){
  last_tracked_time_stamp = 0;
  first_tracked_time = true;
  last_tracked_time = 0;
  last_tracked_time_available = false;
  last_tracked_time_stamp = 0;
  last_tracked_time_backup = 0;
  smart_sense_signal_high = min_signal_for_triggering_lap_tracking;
  smart_sense_signal = min_signal_for_triggering_lap_tracking;
}

void invalidate_last_tracking(){
  last_tracked_time_stamp = last_tracked_time_backup;
}

void sensor_for_time_tracking(){
  wait_rssi_ready();
  uint16_t rssi_signal = readRSSI();

  smart_sense_filter(rssi_signal);
  if(rssi_signal > smart_sense_signal){
    /*if(debugging){
      Serial.print(rssi_signal);
      Serial.print(" rssi > ss ");
      Serial.println(smart_sense_signal);
    }*/
    unsigned long c_time = millis();

  if(TIME_ACCURACY == 1){
   Serial.print("ACCURACY: ");
   Serial.print(c_time - time_tracking_ts);
   Serial.print("ms RSSI: ");
   Serial.print(rssi_signal);
   Serial.print(" SS: ");
   Serial.println(smart_sense_signal);
  }

    if(first_tracked_time){
      first_tracked_time = false;
      last_tracked_time_stamp = millis();
      return;
    }

    if(c_time - last_tracked_time_stamp < min_lap_time){
      //last_tracked_time_stamp = millis();
      // do nothing
    }else{
      last_tracked_time_backup = last_tracked_time_stamp;
      last_tracked_time = c_time - last_tracked_time_stamp;
      last_tracked_time_available = true;
      last_tracked_time_stamp = millis();

      //if(debugging){
      Serial.print("TRIGGERED CHANNEL: ");
      Serial.print((int)channel);
      Serial.print("/");
      Serial.print(num_available_channels);
      Serial.print(" ");
      Serial.print(pgm_read_word_near(channelFreqTable + channel));
      Serial.print(" - ");
      Serial.print("RSSI: ");
      Serial.println(rssi_signal);

      //}

      digitalWrite(13, HIGH); // LED anschalten
      delay(10);
      digitalWrite(13, LOW); // LED ausschalten
    }
  }
}

void i2c_receive(int bytes){
  String incomming_data = "";
  for(int i =0; i < bytes; i++){
    incomming_data += char(Wire.read());
  }

  if(incomming_data.indexOf("#") > 0){
    process_cmd(incomming_data.substring(0, incomming_data.indexOf("#")));
  }
}

void i2c_on_request(){
  if(wire_request_mode == WRM_VERSION){
    byte myArray[2];
    myArray[0] = (fw_version >> 8) & 0xFF;
    myArray[1] = fw_version & 0xFF;

    Wire.write(myArray, 2);
  }

  if(wire_request_mode == WRM_TAV){
     Wire.write(last_tracked_time_available);
  }

  if(wire_request_mode == WRM_GSSS){
    byte myArray[2];
    myArray[0] = (smart_sense_signal >> 8) & 0xFF;
    myArray[1] = smart_sense_signal & 0xFF;

    Wire.write(myArray, 2);
  }

  if(wire_request_mode == WRM_GSSCO){
    byte myArray[2];
    myArray[0] = (smart_sense_signal_cut_off >> 8) & 0xFF;
    myArray[1] = smart_sense_signal_cut_off & 0xFF;

    Wire.write(myArray, 2);
  }

  if(wire_request_mode == WRM_GMLT){
    byte myArray[4];
    myArray[0] = (min_lap_time  >> 24) & 0xFF;
    myArray[1] = (min_lap_time >> 16) & 0xFF;
    myArray[2] = (min_lap_time >> 8) & 0xFF;
    myArray[3] = min_lap_time & 0xFF;

    Wire.write(myArray, 4);
  }

  if(wire_request_mode == WRM_LTT){
    //Wire.write(last_tracked_time);
    byte myArray[4];
    myArray[0] = (last_tracked_time >> 24) & 0xFF;
    myArray[1] = (last_tracked_time >> 16) & 0xFF;
    myArray[2] = (last_tracked_time >> 8) & 0xFF;
    myArray[3] = last_tracked_time & 0xFF;

    Wire.write(myArray, 4);

    last_tracked_time = 0;
    last_tracked_time_available = false;

    /*for(int i = 0; i < 4; i++){
      Serial.print("BYTE: ");
      Serial.println(myArray[i]);
    }*/
  }

  if(wire_request_mode == WRM_GRSSIS){
    byte myArray[2];
    myArray[0] = (min_signal_for_triggering_lap_tracking >> 8) & 0xFF;
    myArray[1] = min_signal_for_triggering_lap_tracking & 0xFF;

    Wire.write(myArray, 2);
    //I2C_writeAnything(min_signal_for_triggering_lap_tracking);
  }

  if(wire_request_mode == WRM_CRSSIS){
    wait_rssi_ready();
    uint16_t rssi_signal = readRSSI();
    byte myArray[2];
    myArray[0] = (rssi_signal >> 8) & 0xFF;
    myArray[1] = rssi_signal & 0xFF;

    Wire.write(myArray, 2);
    //I2C_writeAnything(min_signal_for_triggering_lap_tracking);
  }
  wire_request_mode = WRM_NONE;
}

void set_i2c_id(int i2c_slave_id){
  EEPROMWriteInt(4,i2c_slave_id);
}

void process_cmd(String incomming){
  //Serial.println(incomming);

  if(incomming.indexOf("INIT_SETUP") == 0){
    String xval = getValue(incomming, ' ', 1);
    init_setup(xval.toInt());
  }

  if(incomming.indexOf("SRSSIMS") == 0){
    String xval = getValue(incomming, ' ', 1);
    //Serial.print("set rssi val: ");
    //Serial.println(xval);

    min_signal_for_triggering_lap_tracking = xval.toInt();
    EEPROMWriteInt(2,min_signal_for_triggering_lap_tracking);
    wire_request_mode = WRM_NONE;
  }


  if(incomming.indexOf("SSSCO") == 0){
    String xval = getValue(incomming, ' ', 1);
    smart_sense_signal_cut_off = xval.toInt();
    EEPROMWriteInt(8,smart_sense_signal_cut_off);

  }

  if(incomming.indexOf("SET_I2C_ID") == 0){
    String xval = getValue(incomming, ' ', 1);
    i2c_slave_id = xval.toInt();
    set_i2c_id(i2c_slave_id);
  }

  if(incomming.indexOf("SMLT") == 0){
    Serial.println(min_lap_time);
    String xval = getValue(incomming, ' ', 1);
    min_lap_time = xval.toInt();
    EEPROMWritelong(6,min_lap_time);
    Serial.println(min_lap_time);
  }

  if(incomming.indexOf("SVTX") == 0){
    String xval = getValue(incomming, ' ', 1);
    channel = xval.toInt();
    setChannelModule(channel);
    EEPROMWriteInt(0,channel);

    print_current_channel();
  }

  if(incomming.indexOf("TAV") == 0){
    //Serial.println("WRM_TAV");
    wire_request_mode = WRM_TAV;
  }

  if(incomming.indexOf("LTT") == 0){
    //Serial.println("LTT");
    //Serial.println(last_tracked_time);
    wire_request_mode = WRM_LTT;
  }

  if(incomming.indexOf("CRRSI") == 0){
    Serial.println(readRSSI());
  }

  if(incomming.indexOf("GRSSIS") == 0){
    wire_request_mode = WRM_GRSSIS;
  }

  if(incomming.indexOf("FWV") == 0){
    wire_request_mode = WRM_VERSION;
  }

  if(incomming.indexOf("SRST")== 0){
    soft_reset();
  }

  if(incomming.indexOf("CRSSI")== 0){
    wire_request_mode = WRM_CRSSIS;
    uint16_t rssi_signal = readRSSI();
    Serial.println(rssi_signal);
  }

  if(incomming.indexOf("GMLT")== 0){
    wire_request_mode = WRM_GMLT;
  }

  if(incomming.indexOf("GSSCO")== 0){
    wire_request_mode = WRM_GSSCO;
  }

  if(incomming.indexOf("P_GSSS") == 0){
    Serial.print("SMART SENSE SIG:");
    Serial.println(smart_sense_signal);
  }

  if(incomming.indexOf("GSSS")== 0){
    wire_request_mode = WRM_GSSS;
  }

  if(incomming.indexOf("ILT") == 0){
    invalidate_last_tracking();
  }
}

void print_current_channel(){
  if(channel > 100){
    Serial.print("CURRENT_CHANNEL ");
    Serial.print((int)channel);
    Serial.print(" Mhz");
    uint16_t t = convert_freq_to_reg(channel);
    Serial.print(" HEX: ");
    Serial.print(t,HEX);
    Serial.println("");
  }else{
    Serial.print("CURRENT_CHANNEL ");
    Serial.print((int)channel);
    Serial.print(" ");
    Serial.print(pgm_read_word_near(channelFreqTable + channel));
    Serial.print(" Mhz");
    uint16_t t = pgm_read_word_near(channelTable + channel);
    Serial.print(" HEX: ");
    Serial.print(t,HEX);
    Serial.println("");
  }

}

void wait_rssi_ready()
{
    // CHECK FOR MINIMUM DELAY
    // check if RSSI is stable after tune by checking the time
    uint16_t tune_time = millis()-time_of_tune;
    if(tune_time < MIN_TUNE_TIME)
    {
        // wait until tune time is full filled
        delay(MIN_TUNE_TIME-tune_time);
    }
}

uint16_t readRSSI()
{
    int rssi = 0;
    int rssiA = 0;


    for (uint8_t i = 0; i < RSSI_READS; i++)
    {
        rssiA += analogRead(rssiPinA);//random(RSSI_MAX_VAL-200, RSSI_MAX_VAL);//
    }
    rssiA = rssiA/RSSI_READS; // average of RSSI_READS readings

    // special case for RSSI setup

    //    Serial.println(rssiA);

    rssiA = map(rssiA, rssi_min_a, rssi_max_a , 1, 100);   // scale from 1..100%
    //return constrain(rssiA,1,100); // clip values to only be within this range.
    return rssiA;
}

uint16_t convert_freq_to_reg(uint16_t f)
{
    uint16_t tf, N, A;
    tf = (f - 479) / 2;
    N = tf / 32;
    A = tf % 32;
    return (N<<7) + A;
}

void setChannelModule(uint16_t channel)
{
  Serial.print("setChannelModule: ");
  Serial.println(channel);

  uint8_t i;
  uint16_t channelData;

  if(channel < 100){
    channelData = pgm_read_word_near(channelTable + channel);
  }else{
      channelData = convert_freq_to_reg(channel);
  }

  programChannelModule(channelData);
}

void programChannelModule(uint16_t channelData)
{
  uint8_t i;
  Serial.print("programChannelModule: ");
  Serial.print(channelData);
  Serial.print(" ");
  Serial.print(channelData,HEX);
  Serial.println("");

  // bit bash out 25 bits of data
  // Order: A0-3, !R/W, D0-D19
  // A0=0, A1=0, A2=0, A3=1, RW=0, D0-19=0
  SERIAL_ENABLE_HIGH();
  delayMicroseconds(1);
  //delay(2);
  SERIAL_ENABLE_LOW();

  SERIAL_SENDBIT0();
  SERIAL_SENDBIT0();
  SERIAL_SENDBIT0();
  SERIAL_SENDBIT1();

  SERIAL_SENDBIT0();

  // remaining zeros
  for (i = 20; i > 0; i--)
    SERIAL_SENDBIT0();

  // Clock the data in
  SERIAL_ENABLE_HIGH();
  //delay(2);
  delayMicroseconds(1);
  SERIAL_ENABLE_LOW();

  // Second is the channel data from the lookup table
  // 20 bytes of register data are sent, but the MSB 4 bits are zeros
  // register address = 0x1, write, data0-15=channelData data15-19=0x0
  SERIAL_ENABLE_HIGH();
  SERIAL_ENABLE_LOW();

  // Register 0x1
  SERIAL_SENDBIT1();
  SERIAL_SENDBIT0();
  SERIAL_SENDBIT0();
  SERIAL_SENDBIT0();

  // Write to register
  SERIAL_SENDBIT1();

  // D0-D15
  //   note: loop runs backwards as more efficent on AVR
  for (i = 16; i > 0; i--)
  {
    // Is bit high or low?
    if (channelData & 0x1)
    {
      SERIAL_SENDBIT1();
    }
    else
    {
      SERIAL_SENDBIT0();
    }

    // Shift bits along to check the next one
    channelData >>= 1;
  }

  // Remaining D16-D19
  for (i = 4; i > 0; i--)
    SERIAL_SENDBIT0();

  // Finished clocking data in
  SERIAL_ENABLE_HIGH();
  delayMicroseconds(1);
  //delay(2);

  digitalWrite(slaveSelectPin, LOW);
  digitalWrite(spiClockPin, LOW);
  digitalWrite(spiDataPin, LOW);
}

void SERIAL_SENDBIT1()
{
  digitalWrite(spiClockPin, LOW);
  delayMicroseconds(1);

  digitalWrite(spiDataPin, HIGH);
  delayMicroseconds(1);
  digitalWrite(spiClockPin, HIGH);
  delayMicroseconds(1);

  digitalWrite(spiClockPin, LOW);
  delayMicroseconds(1);
}

void SERIAL_SENDBIT0()
{
  digitalWrite(spiClockPin, LOW);
  delayMicroseconds(1);

  digitalWrite(spiDataPin, LOW);
  delayMicroseconds(1);
  digitalWrite(spiClockPin, HIGH);
  delayMicroseconds(1);

  digitalWrite(spiClockPin, LOW);
  delayMicroseconds(1);
}

void SERIAL_ENABLE_LOW()
{
  delayMicroseconds(1);
  digitalWrite(slaveSelectPin, LOW);
  delayMicroseconds(1);
}

void SERIAL_ENABLE_HIGH()
{
  delayMicroseconds(1);
  digitalWrite(slaveSelectPin, HIGH);
  delayMicroseconds(1);
}

String getValue(String data, char separator, int index)
{
 int found = 0;
  int strIndex[] = {
0, -1  };
  int maxIndex = data.length()-1;
  for(int i=0; i<=maxIndex && found<=index; i++){
  if(data.charAt(i)==separator || i==maxIndex){
  found++;
  strIndex[0] = strIndex[1]+1;
  strIndex[1] = (i == maxIndex) ? i+1 : i;
  }
 }
  return found>index ? data.substring(strIndex[0], strIndex[1]) : "";
}

void EEPROMWritelong(int address, long value)
{
  //Decomposition from a long to 4 bytes by using bitshift.
  //One = Most significant -> Four = Least significant byte
  byte four = (value & 0xFF);
  byte three = ((value >> 8) & 0xFF);
  byte two = ((value >> 16) & 0xFF);
  byte one = ((value >> 24) & 0xFF);

  //Write the 4 bytes into the eeprom memory.
  EEPROM.write(address, four);
  EEPROM.write(address + 1, three);
  EEPROM.write(address + 2, two);
  EEPROM.write(address + 3, one);
}

long EEPROMReadlong(long address)
{
  //Read the 4 bytes from the eeprom memory.
  long four = EEPROM.read(address);
  long three = EEPROM.read(address + 1);
  long two = EEPROM.read(address + 2);
  long one = EEPROM.read(address + 3);

  //Return the recomposed long by using bitshift.
  return ((four << 0) & 0xFF) + ((three << 8) & 0xFFFF) + ((two << 16) & 0xFFFFFF) + ((one << 24) & 0xFFFFFFFF);
}
//This function will write a 2 byte integer to the eeprom at the specified address and address + 1
void EEPROMWriteInt(int p_address, int p_value)
{
  byte lowByte = ((p_value >> 0) & 0xFF);
  byte highByte = ((p_value >> 8) & 0xFF);

  EEPROM.write(p_address, lowByte);
  EEPROM.write(p_address + 1, highByte);
}

//This function will read a 2 byte integer from the eeprom at the specified address and address + 1
unsigned int EEPROMReadInt(int p_address)
{
  byte lowByte = EEPROM.read(p_address);
  byte highByte = EEPROM.read(p_address + 1);

  return ((lowByte << 0) & 0xFF) + ((highByte << 8) & 0xFF00);
}
