import yaml

config_dict = {'DebugMode': True,
               'DefaultFontSize': '15', # 15 works well for 1920x1080 screens
               'TestingPCOpSys': 'Centos7', # or 'Alma9'
               'TrenzHostname': ['cmshgcaltb4.lan.local.cmu.edu'],
               'MACSerial': 'CM',
               'DataLoc': '/home/hgcal/data/', # place to store all output data
               'HVResource': 'ASRL/dev/ttyUSB0::INSTR',
               'HVTerminal': 'Rear', # 'Front' for front terminals, 'Rear' for rear terminals
               'HVWiresPolarization': 'Reverse', # 'Reverse' for reverse bias (V in [0, 800]) 'Forward' for forward bias (V in [-800, 0])
               'PCKeyLoc': '/home/hgcal/.ssh/id_rsa', # private key location
               'HasHVSwitch': True,
               'HasRHSensor': False,
               'Inspectors': ['acrobert', 'simurthy', 'jestein', 'ekloiber', 'ppalit', 'akallilt'], # CERN usernames
               'HasLocalDB': True,
               'DBHostname': '', # these four only if you have a local database
               'DBDatabase': '',
               'DBUsername': '',
               'DBPassword': ''
               }

with open('configuration.yaml','w') as yconf:
    yaml_string=yaml.dump(config_dict, yconf)
