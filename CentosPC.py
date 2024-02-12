import paramiko
import time
import os
import subprocess
import sys
import glob
from time import sleep

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

#sys.path.insert(1, configuration['HexmapPath'])
sys.path.insert(1, './hexmap')
from plot_summary import make_hexmap_plots_from_file
import plot_summary

class CentosPC:
    """
    Class that wraps the role of the Centos7 PC in module testing. It starts and tracks the DAQ client service 
    and runs the testing scripts.
    """    
    
    def __init__(self, trenzhostname, modulename, live=True):
        """
        Constructor. Needs the IP address of the test stand and the module name. Also needs to know if this is a
        live module or if is a hexaboard. Object created and destroyed during every test session, so it will never
        need to change the module name or type. Density and shape are read from the module name and used to choose
        the correct configuration file.
        """
        
        self.trenzhostname = trenzhostname
        self.modulename = modulename
        self.live = live
        self.initiated = False
        # start the DAQ client
        os.system('systemctl restart daq-client.service')
        print(' >> CentosPC: DAQ client started. PC ready to run tests.')

        self.env = '/opt/hexactrl/ROCv3/ctrl/etc/env.sh'
        self.scriptloc = '/opt/hexactrl/ROCv3/ctrl/'

        density = modulename.split('-')[1][1]
        shape = modulename.split('-')[2][0]

        if density == 'L':
            if shape == 'F':
                self.config = '/opt/hexactrl/ROCv3/ctrl/etc/configs/initLD-trophyV3.yaml'
            elif shape == 'L' or shape == 'R':
                self.config = '/opt/hexactrl/ROCv3/ctrl/etc/configs/initLD-semi.yaml'
            else: # T B 5
                raise NotImplementedError
        elif density == 'H': # F L R T B 5
            raise NotImplementedError
                
    def restart_daq(self):
        """
        Restarts DAQ client service by running a bash command, then checks the status and returns it.
        """

        print(' >> CentosPC: systemctl restart daq-client.service')
        os.system('systemctl restart daq-client.service')
        sleep(1)
        print(' >> CentosPC: systemctl status daq-client')
        stdout = os.popen('systemctl status daq-client').read().split('\n')
        client = False
        for line in stdout:
            if 'Active: active (running)' in line:
                print(' >> CentosPC: DAQ client running')
                client = True

        if not client:
            print(' -- CentosPC: Error in DAQ client')

        return client
        
    def status_daq(self):
        """
        Checks the status of the DAQ client and returns it.
        """

        print(' >> CentosPC: systemctl status daq-client')
        stdout = os.popen('systemctl status daq-client').read().split('\n')
        client = False
        for line in stdout:
            if 'Active: active (running)' in line:
                print(' >> CentosPC: DAQ client running')
                client = True
                
        if not client:
            print(' -- CentosPC: Error in DAQ client')
        return client

    def _run_script(self, scriptname, config=None):
        """
        Runs a testing script after setting up the environment. Inputs are the name of the script without the location or the .py and optionally
        the location of the configuration .yaml file. It also reads the output data location from the GUI configuration
        and sends the script output there. Returns the relative location of the output plots inside the data location.

        This class uses the self.initiated flag to track if it should add -I to the 
        testing script call - if false, it will run with -I and then set the flag to true. You can always manually set 
        the flag from outside the class if you want it to run -I at any given time.

        The environment script is run every time because os.system deletes the shell after the call is over.
        """

        if config is None:
            config = self.config
        
        script = self.scriptloc + scriptname + '.py'

        print(f' >> CentosPC: Running {scriptname}.py...')
        if not self.initiated:
            os.system(f'source {self.env} && python3 {script} -i {self.trenzhostname} -f {config} -o {configuration["DataLoc"]}/ -d {self.modulename} -I > /dev/null 2>&1')
        else:
            os.system(f'source {self.env} && python3 {script} -i {self.trenzhostname} -f {config} -o {configuration["DataLoc"]}/ -d {self.modulename} > /dev/null 2>&1')

        runs = glob.glob(f'{configuration["DataLoc"]}/{self.modulename}/{scriptname}/*')
        runs.sort()
        print(f' >> CentosPC: Output of {scriptname}.py located in {runs[-1]}')
        self.initiated = True

        return f'{scriptname}/{runs[-1]}'
        
    def pedestal_run(self, BV=None):
        """
        Runs the pedestal_run.py script and then, if the bias voltage isn't None, renames the output dir to include the bias voltage.
        """
        
        dirname = self._run_script('pedestal_run')
        
        if BV is not None:
            print(' >> CentosPC:', f'mv {configuration["DataLoc"]}/{self.modulename}/{dirname} {configuration["DataLoc"]}/{self.modulename}/{dirname}_BV{BV}')
            try:
                os.system(f'mv {configuration["DataLoc"]}/{self.modulename}/{dirname} {configuration["DataLoc"]}/{self.modulename}/{dirname}_BV{BV}')
                return f'{configuration["DataLoc"]}/{self.modulename}/{dirname}_BV{BV}'
            except:
                print(' -- CentosPC: outdict renaming failed; continuing')
                return f'{configuration["DataLoc"]}/{self.modulename}/{dirname}'
        
    def pedestal_scan(self):
        self._run_script('pedestal_scan')

    def vrefnoinv_scan(self):
        self._run_script('vrefnoinv_scan')

    def vrefinv_scan(self):
        self._run_script('vrefinv_scan')

    def phase_scan(self):
        self._run_script('phase_scan')

    def sampling_scan(self):
        self._run_script('sampling_scan')
        
    def make_hexmaps(self, ind=-1, BV=None):
        """
        Makes fancy hexmap plots. By default, it will take the most recent pedestal run by default, though this can be 
        controlled manually with the ind argument. If the BV isn't None, it renames the title of the plot and the filename
        to include the BV.
        """
        
        runs = glob.glob(f'{configuration["DataLoc"]}/{self.modulename}/pedestal_run/*')
        runs.sort() # needed because glob doesn't sort things in the order that `ls` does for some reason

        # use the last run by default but allow any                                             
        labelind = ind if ind != -1 else len(runs)-1
        if BV is None and 'BV' in runs[labelind]:
            BV = runs.split('BV').rstrip('\n ')    
        label = f'{self.modulename}_run{labelind}' if BV is None else f'{self.modulename}_run{labelind}_BV{BV}'

        make_hexmap_plots_from_file(f'{runs[ind]}/pedestal_run0.root', figdir=f'{configuration["DataLoc"]}/{self.modulename}', label=label)
        print(f' >> Hexmap: Summary plots located in ~/data/{self.modulename}')

        return f'{configuration["DataLoc"]}/{self.modulename}/{label}'
            
def static_make_hexmaps(modulename, ind=-1):
    """
    Make hexmaps but outside of the class.
    """
    
    runs = glob.glob(f'{configuration["DataLoc"]}/{modulename}/pedestal_run/*')
    runs.sort()

    # use the last run by default but allow any                                             
    labelind = ind if ind != -1 else len(runs)-1
    if 'BV' in runs[labelind]:
        BV = runs.split('BV').rstrip('\n ')
    else:
        BV = None
    label = f'{modulename}_run{labelind}' if BV is None else f'{modulename}_run{labelind}_BV{BV}'

    make_hexmap_plots_from_file(f'{runs[ind]}/pedestal_run0.root', figdir=f'{configuration["DataLoc"]}/{modulename}', label=label)
    print(f' >> Hexmap: Summary plots located in {configuration["DataLoc"]}/{modulename}')
