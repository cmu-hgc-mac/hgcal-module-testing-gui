import yaml

config_dict = {'DebugMode': True,
               'DefaultFontSize': '15', # 15 works well for 1920x1080 screens
               'TestingPCOpSys': 'Centos7', # or 'Alma9'
               'HexactrlSWBranch': 'ROCv3', # gitlab branch of `hexactrl-sw`, should be 'ROCv3' for most. If you updated to Alma 9 some time ago (but not recently), use 'feature-alma9' instead.
               'FPGAHostname': ['cmshgcaltb4.lan.local.cmu.edu', 'cmshgcalkria1.lan.local.cmu.edu'], # renamed Trenz->FPGA
               'FPGAType': ['Trenz', 'Kria'], # type of FPGA; order __must__ match 'FPGAHostname'
               'MACSerial': 'CM',
               'DataLoc': '/home/hgcal/data/', # place to store all output data
               'HVResource': 'ASRL/dev/ttyUSB0::INSTR',
               'HVDiscoveryMode': 'by-resource', # if you use something like the above; use 'by-id' if instead of the /dev/ location you use the link shown by `ls -l /dev/serial/by-id`
               'HVTerminal': 'Rear', # 'Front' for front terminals, 'Rear' for rear terminals
               'HVWiresPolarization': 'Reverse', # 'Reverse' for reverse bias (V in [0, 800]) 'Forward' for forward bias (V in [-800, 0])
               'PCKeyLoc': '/home/hgcal/.ssh/id_rsa', # private key location
               'HasHVSwitch': True, # switch on the box which only allows HV when switch is triggered
               'HasRHSensor': False, # automatic sensing of RH and T inside test box, see AirControl.py. You may want to re-implement it.
               'Inspectors': ['acrobert', 'simurthy', 'jestein', 'ppalit', 'akallilt'], # CERN usernames
               'HasLocalDB': True,
               # these four only if you have a local database
               'DBHostname': '', # fill out
               'DBDatabase': 'hgcdb',
               'DBUsername': 'teststand_user',
               'DBPassword': ''  # fill out
               }

import os
if config_dict['TestingPCOpSys'] == 'Centos7':
    assert os.path.isfile('/opt/hexactrl/ROCv3/ctrl/etc/env.sh')
    assert os.path.isfile('/opt/hexactrl/ROCv3/ctrl/pedestal_run.py')
elif config_dict['TestingPCOpSys'] == 'Alma9' and config_dict['HexactrlSWBranch'] == 'ROCv3': 
    assert os.path.isfile('/opt/hexactrl/ROCv3/ctrl/etc/env.sh')
    assert os.path.isfile('/opt/hexactrl/ROCv3/ctrl/pedestal_run.py')
elif config_dict['TestingPCOpSys'] == 'Alma9' and config_dict['HexactrlSWBranch'] == 'feature-alma9':
    assert os.path.isfile('/opt/hexactrl/feature-alma9/ctrl/etc/env.sh')
    assert os.path.isfile('/opt/hexactrl/feature-alma9/ctrl/pedestal_run.py')
else:
    raise AssertionError("TestingPCOpSys and HexactrlSWBranch not specified properly")

with open('configuration.yaml','w') as yconf:
    yaml_string=yaml.dump(config_dict, yconf)
