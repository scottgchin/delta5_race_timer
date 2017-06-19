

from server import DB
from server import Delta5Interface

from server import Pilot
from server import Heat
from server import CurrentLap
from server import SavedRace
from server import Frequency

INTERFACE = Delta5Interface()

print 'Start database initialization.'

DB.create_all()

# For loop based on INTERFACE.num_nodes
pilot0 = Pilot(pilot_id='0', callsign=' ', name=' ')
DB.session.add(pilot0)
pilot1 = Pilot(pilot_id='1', callsign='pilot1', name='Pilot Name')
DB.session.add(pilot1)
pilot2 = Pilot(pilot_id='2', callsign='pilot2', name='Pilot Name')
DB.session.add(pilot2)
pilot3 = Pilot(pilot_id='3', callsign='pilot3', name='Pilot Name')
DB.session.add(pilot3)
pilot4 = Pilot(pilot_id='4', callsign='pilot4', name='Pilot Name')
DB.session.add(pilot4)
pilot5 = Pilot(pilot_id='5', callsign='pilot5', name='Pilot Name')
DB.session.add(pilot5)

# For loop based on INTERFACE.num_nodes
heat1pilot1 = Heat(heat_id='1', node_index='0', pilot_id='1')
DB.session.add(heat1pilot1)
heat1pilot2 = Heat(heat_id='1', node_index='1', pilot_id='2')
DB.session.add(heat1pilot2)
heat1pilot3 = Heat(heat_id='1', node_index='2', pilot_id='3')
DB.session.add(heat1pilot3)
heat1pilot4 = Heat(heat_id='1', node_index='3', pilot_id='4')
DB.session.add(heat1pilot4)
heat1pilot5 = Heat(heat_id='1', node_index='4', pilot_id='5')
DB.session.add(heat1pilot5)

# IMD Channels
IMD1 = Frequency(band='IMD', channel='E2', frequency='5685')
DB.session.add(IMD1)
IMD2 = Frequency(band='IMD', channel='F2', frequency='5760')
DB.session.add(IMD2)
IMD3 = Frequency(band='IMD', channel='F4', frequency='5800')
DB.session.add(IMD3)
IMD4 = Frequency(band='IMD', channel='F7', frequency='5860')
DB.session.add(IMD4)
IMD5 = Frequency(band='IMD', channel='E6', frequency='5905')
DB.session.add(IMD5)
IMD6 = Frequency(band='IMD', channel='E4', frequency='5645')
DB.session.add(IMD6)
# Raceband
C1 = Frequency(band='C', channel='C1', frequency='5658')
DB.session.add(C1)
C2 = Frequency(band='C', channel='C2', frequency='5695')
DB.session.add(C2)
C3 = Frequency(band='C', channel='C3', frequency='5732')
DB.session.add(C3)
C4 = Frequency(band='C', channel='C4', frequency='5769')
DB.session.add(C4)
C5 = Frequency(band='C', channel='C5', frequency='5806')
DB.session.add(C5)
C6 = Frequency(band='C', channel='C6', frequency='5843')
DB.session.add(C6)
C7 = Frequency(band='C', channel='C7', frequency='5880')
DB.session.add(C7)
C8 = Frequency(band='C', channel='C8', frequency='5917')
DB.session.add(C8)




# E4 = Frequency(band='E', channel='E4', frequency='5645')
# DB.session.add(E4)

# E3 = Frequency(band='E', channel='E3', frequency='5665')
# DB.session.add(E3)
# E2 = Frequency(band='E', channel='E2', frequency='5685')
# DB.session.add(E2)

# E1 = Frequency(band='E', channel='E1', frequency='5705')
# DB.session.add(E1)
# A8 = Frequency(band='A', channel='A8', frequency='5725')
# DB.session.add(A8)

# B1 = Frequency(band='B', channel='B1', frequency='5733')
# DB.session.add(B1)
# F1 = Frequency(band='F', channel='F1', frequency='5740')
# DB.session.add(F1)
# A7 = Frequency(band='A', channel='A7', frequency='5745')
# DB.session.add(A7)
# B2 = Frequency(band='B', channel='B2', frequency='5752')
# DB.session.add(B2)
# F2 = Frequency(band='F', channel='F2', frequency='5760')
# DB.session.add(F2)
# A6 = Frequency(band='A', channel='A6', frequency='5765')
# DB.session.add(A6)

# B3 = Frequency(band='B', channel='B3', frequency='5771')
# DB.session.add(B3)
# F3 = Frequency(band='F', channel='F3', frequency='5780')
# DB.session.add(F3)
# A5 = Frequency(band='A', channel='A5', frequency='5785')
# DB.session.add(A5)
# B4 = Frequency(band='B', channel='B4', frequency='5790')
# DB.session.add(B4)
# F4 = Frequency(band='F', channel='F4', frequency='5800')
# DB.session.add(F4)
# A4 = Frequency(band='A', channel='A4', frequency='5805')
# DB.session.add(A4)

# B5 = Frequency(band='B', channel='B5', frequency='5809')
# DB.session.add(B5)
# F5 = Frequency(band='F', channel='F5', frequency='5820')
# DB.session.add(F5)
# A3 = Frequency(band='A', channel='A3', frequency='5825')
# DB.session.add(A3)
# B6 = Frequency(band='B', channel='B6', frequency='5828')
# DB.session.add(B6)
# F6 = Frequency(band='F', channel='F6', frequency='5840')
# DB.session.add(F6)

# A2 = Frequency(band='A', channel='A2', frequency='5845')
# DB.session.add(A2)
# B7 = Frequency(band='B', channel='B7', frequency='5847')
# DB.session.add(B7)
# F7 = Frequency(band='F', channel='F7', frequency='5860')
# DB.session.add(F7)
# A1 = Frequency(band='A', channel='A1', frequency='5865')
# DB.session.add(A1)
# B8 = Frequency(band='B', channel='B8', frequency='5866')
# DB.session.add(B8)
# F8 = Frequency(band='F', channel='F8', frequency='5880')
# DB.session.add(F8)

# E5 = Frequency(band='E', channel='E5', frequency='5885')
# DB.session.add(E5)
# E6 = Frequency(band='E', channel='E6', frequency='5905')
# DB.session.add(E6)

# E7 = Frequency(band='E', channel='E7', frequency='5925')
# DB.session.add(E7)
# E8 = Frequency(band='E', channel='E8', frequency='5945')
# DB.session.add(E8)


DB.session.commit()
