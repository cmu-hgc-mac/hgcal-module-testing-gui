import paramiko
import time
import os

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

# required I2C addresses for discovering ROCs by density and geometry. Always second half of the line, but add X7s in as alternates
# as these addresses sometimes show up and are not a problem.
listeddevices = {'LF': [['00: -- -- -- -- -- -- -- -- 08 09 0a 0b 0c 0d 0e 0f', '00: -- -- -- -- -- -- -- 07 08 09 0a 0b 0c 0d 0e 0f'],
                        ['10: -- -- -- -- -- -- -- -- 18 19 1a 1b 1c 1d 1e 1f', '10: -- -- -- -- -- -- -- 17 18 19 1a 1b 1c 1d 1e 1f'],
                        ['20: -- -- -- -- -- -- -- -- 28 29 2a 2b 2c 2d 2e 2f', '20: -- -- -- -- -- -- -- 27 28 29 2a 2b 2c 2d 2e 2f']],
                 'LR': [['40: -- -- -- -- -- -- -- -- 48 49 4a 4b 4c 4d 4e 4f', '40: -- -- -- -- -- -- -- 47 48 49 4a 4b 4c 4d 4e 4f'],
                        ['50: -- -- -- -- -- -- -- -- 58 59 5a 5b 5c 5d 5e 5f', '50: -- -- -- -- -- -- -- 57 58 59 5a 5b 5c 5d 5e 5f']],
                 'LL': [['40: -- -- -- -- -- -- -- -- 48 49 4a 4b 4c 4d 4e 4f', '40: -- -- -- -- -- -- -- 47 48 49 4a 4b 4c 4d 4e 4f'],
                        ['50: -- -- -- -- -- -- -- -- 58 59 5a 5b 5c 5d 5e 5f', '50: -- -- -- -- -- -- -- 57 58 59 5a 5b 5c 5d 5e 5f']],
                 'HF': [['00: -- -- -- -- -- -- -- -- 08 09 0a 0b 0c 0d 0e 0f', '00: -- -- -- -- -- -- -- 07 08 09 0a 0b 0c 0d 0e 0f'],
                        ['10: -- -- -- -- -- -- -- -- 18 19 1a 1b 1c 1d 1e 1f', '10: -- -- -- -- -- -- -- 17 18 19 1a 1b 1c 1d 1e 1f'],
                        ['20: -- -- -- -- -- -- -- -- 28 29 2a 2b 2c 2d 2e 2f', '20: -- -- -- -- -- -- -- 27 28 29 2a 2b 2c 2d 2e 2f'],
                        ['40: -- -- -- -- -- -- -- -- 48 49 4a 4b 4c 4d 4e 4f', '40: -- -- -- -- -- -- -- 47 48 49 4a 4b 4c 4d 4e 4f'],
                        ['50: -- -- -- -- -- -- -- -- 58 59 5a 5b 5c 5d 5e 5f', '50: -- -- -- -- -- -- -- 57 58 59 5a 5b 5c 5d 5e 5f'],
                        ['60: -- -- -- -- -- -- -- -- 68 69 6a 6b 6c 6d 6e 6f', '60: -- -- -- -- -- -- -- 67 68 69 6a 6b 6c 6d 6e 6f']]}
    
class TrenzTestStand:
    """
    Class that wraps the Trenz-based testing system. The class connects to the Trenz using a paramiko
    SSH client and then runs commands over ssh.
    """
   
    def __init__(self, hostname, modulename, keyloc=configuration['PCKeyLoc']):
        """
        Instantiates object. Can run as soon as Trenz is powered; will wait until ping succeeds to try 
        to connect. Some issues with this that are being debugged.
        """
    
        self.fwloaded = False
        self.services = False
        self.hostname = hostname
        print(f' >> TrenzTestStand: Connecting to Trenz at {self.hostname}...')

        time.sleep(2)
        
        # wait until can ping test stand                                                                                                                                                              
        connected = False
        while not connected:
            response = os.system("ping -c 1 " + self.hostname + " >/dev/null 2>&1")
            if response == 0:
                connected = True

        time.sleep(2)
                
        # create ssh client                                                                                                                                                                     
        self.ssh = paramiko.SSHClient()
        k = paramiko.RSAKey.from_private_key_file(keyloc)
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(hostname=hostname, username='root', pkey=k)
        # at this point, can consider to be "connected"
        print(' >> TrenzTestStand: Connected')

        density = modulename.split('-')[1][1]
        shape = modulename.split('-')[2][0]
        self.fw = ''
        if density == 'L':
            if shape in ['F', 'L', 'R']:
                self.fw = 'hexaboard-hd-tester-v1p1-trophy-v3'
            else: # T B 5
                raise NotImplementedError
        elif density == 'H':
            if shape == 'F':
                self.fw = 'hexaboard-hd-tester-v1p1-trophy-v2'
            else: # L R T B 5
                raise NotImplementedError

        self.hbtype = density+shape
            
    def _runcmd(self, cmd):
        """
        Class to run an arbitrary bash command over ssh. Currently sleeps for three seconds to ensure safety.
        """

        print(' >> TrenzTestStand:', cmd)
        ssh_stdin, ssh_stdout, ssh_stderr = self.ssh.exec_command(cmd)
        time.sleep(3)
        ssh_stdin.close()

        return ssh_stdout, ssh_stderr

    def loadfw(self):
        """
        Loads the firmware for the HGCAL testing system. Currently locked to version hexaboard-hd-tester-v1p1-trophy-v3,
        may allow for selection in the future. After the firmware is loaded, this function prints the I2C devices found
        and then checks to ensure that the correct channels are discovered. Currently only implemented for LD full boards.
        Returns True if proper startup detected, otherwise returns False.
        """

        ssh_stdout, ssh_stderr = self._runcmd(f'fw-loader load {self.fw} && listdevice')
        stdout = ssh_stdout.read().decode('ascii')

        firmware_loaded = False
        channels_found = True
        
        for line in stdout.split('\n'):
            print('   >> fw:', line)

        # check fw load
        if 'Loaded the device tree overlay successfully using the zynqMP FPGA manager' in stdout:
            print(' >> TrenzTestStand: Loaded firmware')
            firmware_loaded = True

        # check channels in listdevice
        for addressbar in listeddevices[self.hbtype]:
            if addressbar[0] not in stdout and addressbar[1] not in stdout:
                channels_found = False

        if channels_found:
            print(' >> TrenzTestStand: Discovered ROC channels')

        if firmware_loaded and channels_found:
            self.fwloaded = True
            return True
        else:
            return False

    
    def startservers(self):
        """
        Starts the DAQ and I2C servers on the Trenz and then checks their status to ensure proper instantiation. Returns True if proper startup
        detected, otherwise returns False.
        """

        ssh_stdout, ssh_stderr = self._runcmd('systemctl restart daq-server.service && systemctl restart i2c-server.service')
        time.sleep(3)

        error_check = True

        ssh_stdout, ssh_stderr = self._runcmd('systemctl status daq-server.service')
        daq_initiated = False
        errreadlines = ssh_stderr.readlines()
        if len(errreadlines) != 0:
            # catch something specific to Alma9 
            if not (len(errreadlines) == 1 and 'uio_pdrv_genirq' in errreadlines[0] and configuration['TestingPCOpSys'] == 'Alma9'):
                error_check = False 

        check1 = False
        check2 = False
        for line in ssh_stdout.readlines():
            print(' >> daq:', line.strip('\n'))
            if 'Active: active (running)' in line:
                check1 = True

            if 'Started daq-client start/stop service script.' in line:
                check2  = True
            
        if check1 and check2:
            daq_initiated = True
        if daq_initiated:
            print(' >> TrenzTestStand: DAQ server initiated')
        
        ssh_stdout, ssh_stderr = self._runcmd('systemctl status i2c-server.service')    
        board_discovered = False
        errreadlines = ssh_stderr.readlines()
        if len(errreadlines) != 0:
            # catch something specific to Alma9
            if not (len(errreadlines) == 1 and 'uio_pdrv_genirq' in errreadlines[0] and configuration['TestingPCOpSys'] == 'Alma9'):
                error_check = False

        check1 = False
        check2 = False
        i2cstatus_lines = ['[I2C] Board identification: V3 LD Full HB',
                           '[I2C] Board identification: V3 LD Semi or Half HB',
                           '[I2C] Board identification: V3 HD Full HB']
        for line in ssh_stdout.readlines():
            print('   >> i2c:', line.strip('\n'))
            if 'Active: active (running)' in line:
                check1 = True

            for il in i2cstatus_lines:
                if il in line:
                    check2 = True
                
        if check1 and check2:
            board_discovered = True
        if board_discovered:
            print(' >> TrenzTestStand: Identified LD Full Hexaboard')

        if board_discovered and daq_initiated and error_check:
            self.services = True
            print(' >> TrenzTestStand: Started services successfully')
            return True
        else:
            self.services = False
            print(' -- TrenzTestStand: Error in starting services')
            return False

    def statusservers(self):
        """
        Check status of DAQ and I2C servers. Returns status of servers as a 2-length tuple.
        """
        
        error_check = True
        
        ssh_stdout, ssh_stderr = self._runcmd('systemctl status daq-server.service')
        daq_running = False

        errreadlines = ssh_stderr.readlines()
        if len(errreadlines) != 0:
            # catch something specific to Alma9
            if not (len(errreadlines) == 1 and 'uio_pdrv_genirq' in errreadlines[0] and configuration['TestingPCOpSys'] == 'Alma9'):
                error_check = False
        
        for line in ssh_stdout.readlines():
            print('   >> daq:', line.strip('\n'))
            if 'Active: active (running)' in line:
                daq_running = True

            
        ssh_stdout, ssh_stderr = self._runcmd('systemctl status i2c-server.service')
        i2c_running = False
        
        errreadlines = ssh_stderr.readlines()
        if len(errreadlines) != 0:
            # catch something specific to Alma9
            if not (len(errreadlines) == 1 and 'uio_pdrv_genirq' in errreadlines[0] and configuration['TestingPCOpSys'] == 'Alma9'):
                error_check = False

        for line in ssh_stdout.readlines():
            print('   >> i2c:', line.strip('\n'))
            if 'Active: active (running)' in line:
                i2c_running = True

        if daq_running and  i2c_running:
            print(' >> TrenzTestStand: Services up and running')
            self.services = True
        else:
            print(f' -- TrenzTestStand: Services not running: DAQ {daq_running} I2C {i2c_running}')
            self.services = False
        return daq_running, i2c_running

    def status(self):

        return self.fwloaded and self.services

    def shutdown(self):
        """
        Shuts the Trenz down remotely. Tested many times and works properly.
        """

        print(' >> TrenzTestStand: Shutting down the Trenz test stand')
        ssh_stdout, ssh_stderr = self._runcmd('shutdown now')
        time.sleep(5)
        return ssh_stdout.readlines(), ssh_stderr.readlines()
