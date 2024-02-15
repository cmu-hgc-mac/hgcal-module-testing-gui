import yaml

config_dict = {'DebugMode': True,
               'DefaultFontSize': '15',
               'TrenzHostname': ['cmshgcaltb4.lan.local.cmu.edu'],
               'MACSerial': 'CM',
               'DataLoc': '/home/hgcal/data/',
               #'HexmapPath': '/home/hgcal/hexmap',
               'HVResource': 'ASRL/dev/ttyUSB0::INSTR'
               'HVTerminal': 'Rear', # 'Front' for front terminals, 'Rear' for rear terminals
               'HVWiresPolarization': 'Reverse', # 'Reverse' for reverse bias (V in [0, 800]) 'Forward' for forward bias (V in [-800, 0])
               'PCKeyLoc': '/home/hgcal/.ssh/id_rsa',
               'HasHVSwitch': True,
               'HasRHSensor': False,
               'Inspectors': ['acrobert', 'simurthy', 'jestein', 'ekloiber', 'ppalit', 'akallilt']
               }

with open('configuration.yaml','w') as yconf:
    yaml_string=yaml.dump(config_dict, yconf)
