import paramiko
import time
import os

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

class TrenzTestStand:
    """
    Class that wraps the Trenz-based testing system. The class connects to the Trenz using a paramiko
    SSH client and then runs commands over ssh.
    """

    
    def __init__(self, hostname, keyloc=configuration['PCKeyLoc']):
        """
        Instantiates object. Can run as soon as Trenz is powered; will wait until ping succeeds to try 
        to connect. Some issues with this that are being debugged.
        """
    
        self.fwloaded = False
        self.services = False
        self.hostname = hostname
        print(f' >> Connecting to Trenz at {self.hostname}...')

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
        print(' >> Connected')

    def _runcmd(self, cmd):
        """
        Class to run an arbitrary bash command over ssh. Currently sleeps for three seconds to ensure safety.
        """
        
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

        #input('    Connect DCDC power cord and press enter.')
        ssh_stdout, ssh_stderr = self._runcmd('fw-loader load hexaboard-hd-tester-v1p1-trophy-v3 && listdevice')

        firmware_loaded = False
        channels_found = False
        listdevice_lines = ['00: -- -- -- -- -- -- -- -- 08 09 0a 0b 0c 0d 0e 0f', # LD Full
                            '40: -- -- -- -- -- -- -- 47 48 49 4a 4b 4c 4d 4e 4f', # LD Right
                            '40: -- -- -- -- -- -- -- -- 48 49 4a 4b 4c 4d 4e 4f'] # LD Right
        for line in ssh_stdout.readlines():
            print(' >> fw:', line.strip('\n'))
            # check FW load              
            if 'Loaded the device tree overlay successfully using the zynqMP FPGA manager' in line:
                print(' >> Loaded firmware')
                firmware_loaded = True
            
            # check channels in listdevice
            for dl in listdevice_lines:
                if dl in line:
                    print(' >> Discovered ROC channels')
                    channels_found = True
            
            if firmware_loaded and channels_found:
                break

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
        time.sleep(5)

        error_check = True

        ssh_stdout, ssh_stderr = self._runcmd('systemctl status daq-server.service')
        daq_initiated = False
        if len(ssh_stderr.readlines()) != 0:
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
            print(' >> DAQ server initiated')
        
        ssh_stdout, ssh_stderr = self._runcmd('systemctl status i2c-server.service')    
        board_discovered = False
        if len(ssh_stderr.readlines()) != 0:
            error_check = False

        check1 = False
        check2 = False
        i2cstatus_lines = ['[I2C] Board identification: V3 LD Full HB',
                           '[I2C] Board identification: V3 LD Semi or Half HB']
        for line in ssh_stdout.readlines():
            print(' >> i2c:', line.strip('\n'))
            if 'Active: active (running)' in line:
                check1 = True

            for il in i2cstatus_lines:
                if il in line:
                    check2 = True
                
        if check1 and check2:
            board_discovered = True
        if board_discovered:
            print(' >> Identified LD Full Hexaboard')

        if board_discovered and daq_initiated and error_check:
            self.services = True
            print(' >> Started services successfully')
            return True
        else:
            self.services = False
            print(' -- Error in starting services')
            return False

    def statusservers(self):
        """
        Check status of DAQ and I2C servers. Returns status of servers as a 2-length tuple.
        """
        
        error_check = True
        
        ssh_stdout, ssh_stderr = self._runcmd('systemctl status daq-server.service')
        daq_running = False
        if len(ssh_stderr.readlines()) != 0:
            error_check = False

        for line in ssh_stdout.readlines():
            if 'Active: active (running)' in line:
                daq_running = True

            
        ssh_stdout, ssh_stderr = self._runcmd('systemctl status i2c-server.service')
        i2c_running = False
        if len(ssh_stderr.readlines()) != 0:
            error_check = False

        for line in ssh_stdout.readlines():
            if 'Active: active (running)' in line:
                i2c_running = True

        if daq_running and  i2c_running:
            print(' >> Services up and running')
            self.services = True
        else:
            print(f' -- Services not running: DAQ {daq_running} I2C {i2c_running}')
            self.services = False
        return daq_running, i2c_running

    def status(self):

        return self.fwloaded and self.services

    def shutdown(self):
        """
        Shuts the Trenz down remotely. Tested many times and works properly.
        """

        print(' >> Shutting down the Trenz test stand')
        ssh_stdout, ssh_stderr = self._runcmd('shutdown now')
        time.sleep(5)
        return ssh_stdout.readlines(), ssh_stderr.readlines()