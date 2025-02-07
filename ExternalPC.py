import paramiko
import time
import os
import subprocess
import sys
import glob
from time import sleep
import traceback

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

sys.path.insert(1, './hexmap')
from plot_summary import make_hexmap_plots_from_file
import plot_summary

class ExternalPC: # no longer Centos7
    """
    Class that wraps the role of the Testing PC in module testing. It starts and tracks the DAQ client service 
    and runs the testing scripts.
    """    
    
    def __init__(self, trenzhostname, state):
        """
        Constructor. Needs the IP address of the test stand and the module name. Also needs to know if this is a
        live module or if is a hexaboard. Object created and destroyed during every test session, so it will never
        need to change the module name or type. Density and shape are read from the module name and used to choose
        the correct configuration file.
        """

        self.trenzhostname = trenzhostname
        self.modulename = state['-Module-Serial-']
        self.live = state['-Live-Module-']
        
        self.initiated = False
        # start the DAQ client
        os.system('systemctl restart daq-client.service')
        print(' >> ExternalPC: DAQ client started. PC ready to run tests.')

        # in Centos7 or Alma9 branch ROCv3, stick to main path of environment and scripts
        # in feature-alma9 branch, use specific paths
        if configuration['TestingPCOpSys'] == 'Centos7':
            self.env = '/opt/hexactrl/ROCv3/ctrl/etc/env.sh' 
            self.scriptloc = '/opt/hexactrl/ROCv3/ctrl/'

        # for backwards compatibility before 'HexactrlSWBranch' was in configuration
        elif (configuration['TestingPCOpSys'] == 'Alma9') and ('HexactrlSWBranch' not in configuration.keys()):
            self.env = '/opt/hexactrl/feature-alma9/ctrl/etc/env.sh'
            self.scriptloc = '/opt/hexactrl/feature-alma9/ctrl/'

        elif (configuration['TestingPCOpSys'] == 'Alma9') and (configuration['HexactrlSWBranch'] == 'feature-alma9'):
            self.env = '/opt/hexactrl/feature-alma9/ctrl/etc/env.sh'
            self.scriptloc = '/opt/hexactrl/feature-alma9/ctrl/'

        elif (configuration['TestingPCOpSys'] == 'Alma9') and (configuration['HexactrlSWBranch'] == 'ROCv3'):
            self.env = '/opt/hexactrl/ROCv3/ctrl/etc/env.sh'
            self.scriptloc = '/opt/hexactrl/ROCv3/ctrl/'

        # make sure above files exist
        assert os.path.isfile(f'{self.env}')
        assert os.path.isfile(f'{self.scriptloc}pedestal_run.py')
            
        density = self.modulename.split('-')[1][1]
        shape = self.modulename.split('-')[2][0]
        rocvers = self.modulename.split('-')[2][-1] # -1 so works for hexaboards and live modules

        if rocvers == '3':
            rocvers = 'X'
        
        # different module density/geometry need different config files
        if density == 'L':
            if shape == 'F':
                if rocvers == 'X':
                    self.config = f'{self.scriptloc}etc/configs/initLD-trophyV3.yaml'
                elif rocvers == '2' or rocvers == 'B' or rocvers == '4':
                    self.config = f'{self.scriptloc}etc/configs/initLD-trophyV3-3b.yaml'
            elif shape == 'L' or shape == 'R' or shape == 'T':
                if rocvers == '2' or rocvers == 'B' or rocvers == '4':
                    self.config = f'{self.scriptloc}etc/configs/initLD-semi-V3b.yaml'
                elif rocvers == 'X':
                    self.config = f'{self.scriptloc}etc/configs/initLD-semi.yaml'
            elif shape == 'B':
                if rocvers == '2' or rocvers == 'B' or rocvers == '4':
                    self.config = f'{self.scriptloc}etc/configs/initLD-bottom-3b.yaml'
                elif rocvers == 'X':
                    raise NotImplementedError
            elif shape == '5':
                if rocvers == 'X':
                    raise NotImplementedError
                elif rocvers == '2' or rocvers == 'B' or rocvers == '4':
                    self.config = f'{self.scriptloc}etc/configs/initLD-five-3b.yaml'
        elif density == 'H':
            if shape == 'F':
                if rocvers == '2' or rocvers == 'B' or rocvers == '4':
                    self.config = f'{self.scriptloc}etc/configs/initHD_trophyV3-V3b.yaml'
                elif rocvers == 'X':
                    self.config = f'{self.scriptloc}etc/configs/initHD_trophyV3.yaml'
            elif shape == 'B':
                if rocvers == 'X':
                    self.config = f'{self.scriptloc}etc/configs/initHD-bottom.yaml'
                else: # no V3b bottom yet
                    raise NotImplementedErro
            elif shape == 'R' or 'L':
                if rocvers == '2' or rocvers == 'B' or rocvers == '4':
                    self.config = f'{self.scriptloc}etc/configs/initHD-semi-V3b.yaml'
                elif rocvers == 'X':
                    raise NotImplementedError
            elif shape == 'T':
                if rocvers == '2' or rocvers == 'B' or rocvers == '4':
                    self.config = f'{self.scriptloc}etc/configs/initHD-top-V3b.yaml'
                elif rocvers == 'X':
                    raise NotImplementedError

        # copy to current directory to update it safely while trimming
        os.system(f'cp {self.config} current_config.yaml')
        print(f' >> ExternalPC: copying {self.config} to current directory as current_config.yaml')
        self.config = 'current_config.yaml'

        self.outyaml = {'pedestal_scan': 'trimmed_pedestal.yaml', 'sampling_scan': 'best_phase.yaml',
                        'vrefinv_scan': 'vrefinv.yaml', 'vrefnoinv_scan': 'vrefnoinv.yaml',
                        'toa_vref_scan_noinj': 'toa_vref.yaml', 'toa_vref_scan': 'toa_vref.yaml',
                        'toa_trim_scan': 'trimmed_toa.yaml'}
        
    def init_outdir(self, outdir):
        self.outdir = outdir
        # a small hack to get test output to the right place
        self.basedir = '/'.join(self.outdir.split('/')[0:-1])
        self.dut = self.outdir.split('/')[-1]
        
    def restart_daq(self):
        """
        Restarts DAQ client service by running a bash command, then checks the status and returns it.
        """

        print(' >> ExternalPC: systemctl restart daq-client.service')
        os.system('systemctl restart daq-client.service')
        sleep(1)
        print(' >> ExternalPC: systemctl status daq-client')
        stdout = os.popen('systemctl status daq-client').read().split('\n')
        client = False
        for line in stdout:
            if 'Active: active (running)' in line:
                print(' >> ExternalPC: DAQ client running')
                client = True

        if not client:
            print(' -- ExternalPC: Error in DAQ client')

        return client
        
    def status_daq(self):
        """
        Checks the status of the DAQ client and returns it.
        """

        print(' >> ExternalPC: systemctl status daq-client')
        stdout = os.popen('systemctl status daq-client').read().split('\n')
        client = False
        for line in stdout:
            if 'Active: active (running)' in line:
                print(' >> ExternalPC: DAQ client running')
                client = True
                
        if not client:
            print(' -- ExternalPC: Error in DAQ client')
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

        If the script run produces an output configuration file, this function uses it to modify the original configuration file with its values.
        """

        if config is None:
            config = self.config
        
        script = self.scriptloc + scriptname + '.py'

        print(f' >> ExternalPC: Running {scriptname}.py with config {config}...')

        if not self.initiated:
            os.system(f'source {self.env} && python3 {script} -i {self.trenzhostname} -f {config} -o {configuration["DataLoc"]}/{self.basedir}/ -d {self.dut} -I > /dev/null 2>&1')
        else:
            os.system(f'source {self.env} && python3 {script} -i {self.trenzhostname} -f {config} -o {configuration["DataLoc"]}/{self.basedir}/ -d {self.dut} > /dev/null 2>&1')
        runs = glob.glob(f'{configuration["DataLoc"]}/{self.outdir}/{scriptname}/*')
            
        runs.sort()
        try:
            print(f' >> ExternalPC: Output of {scriptname}.py located in {runs[-1]}')
            self.initiated = True
        except:
            print(f' >> ExternalPC: Did not find output of test. Maybe it crashed? Continuing')
            return ''
            
        if scriptname in self.outyaml.keys():
            print(f' >> ExternalPC: Updating configuration file with {runs[-1]}/{self.outyaml[scriptname]}')
            updateconf(self.config, runs[-1]+'/'+self.outyaml[scriptname])
            
        thisrun = runs[-1].split('/')[-1]
        #return f'{scriptname}/{thisrun}'
        return runs[-1]

    def create_proc(self, scriptname):
            
        script = self.scriptloc + scriptname + '.py'

        if not self.initiated:
            command = f'source {self.env} && python3 {script} -i {self.trenzhostname} -f {self.config} -o {configuration["DataLoc"]}/{self.basedir}/ -d {self.dut} -I > /dev/null 2>&1'
        else:
            command = f'source {self.env} && python3 {script} -i {self.trenzhostname} -f {self.config} -o {configuration["DataLoc"]}/{self.basedir}/ -d {self.dut} > /dev/null 2>&1'

        proc = ScriptProcess(scriptname, command, self)
        return proc

    def pedestal_proc(self, BV=None):

        proc = self.create_proc('pedestal_run')
        return proc

    def script_proc(self, script, BV=None):

        proc = self.create_proc(script)
        return proc

    def pedestal_run(self, BV=None):
        """
        Runs the pedestal_run.py script and then, if the bias voltage isn't None, renames the output dir to include the bias voltage.
        """
        
        dirname = self._run_script('pedestal_run')
        return dirname
        
    # these functions are mostly irrelevant as _run_script() can be called from outside
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
                
    def make_hexmaps(self, ind=-1, tag=None):
        """
        Makes fancy hexmap plots. By default, it will take the most recent pedestal run by default, though this can be 
        controlled manually with the ind argument. If the BV isn't None, it renames the title of the plot and the filename
        to include the BV.
        """

        runs = glob.glob(f'{configuration["DataLoc"]}/{self.outdir}/pedestal_run/*')
        runs.sort() # needed because glob doesn't sort things in the order that `ls` does for some reason

        # use the last run by default but allow any                                             
        labelind = ind if ind != -1 else len(runs)-1
        label = f'{self.modulename}_run{labelind}' if tag is None else f'{self.modulename}_run{labelind}_{tag}'

        make_hexmap_plots_from_file(f'{runs[ind]}/pedestal_run0.root', figdir=f'{configuration["DataLoc"]}/{self.outdir}/', label=label)
        print(f' >> Hexmap: Summary plots located in {configuration["DataLoc"]}/{self.outdir} as {label}')

        return f'{configuration["DataLoc"]}/{self.outdir}/{label}'

def static_make_hexmaps(modulename, ind=-1, tag=None):
    """
    Make hexmaps but outside of the class.
    """
    
    runs = glob.glob(f'{configuration["DataLoc"]}/{modulename}/pedestal_run/*')
    runs.sort()

    # use the last run by default but allow any                                             
    labelind = ind if ind != -1 else len(runs)-1
    label = f'{modulename}_run{labelind}' if tag is None else f'{modulename}_run{labelind}_{tag}'

    make_hexmap_plots_from_file(f'{runs[ind]}/pedestal_run0.root', figdir=f'{configuration["DataLoc"]}/{modulename}', label=label)
    print(f'  >> Hexmap: Summary plots located in {configuration["DataLoc"]}/{modulename}')


def recursive_update(conf, mod):
    """
    Recursively updates a nested dictionary conf with a new dictionary mod
    """
    
    newconf = conf
    for key in mod.keys():

        if key in conf.keys():
            if conf[key] != mod[key]:
                if type(mod[key]) == dict:
                    recursive_update(conf[key], mod[key])
                else:
                    if conf[key] != mod[key]:
                        newconf[key] = mod[key]

        else:
            newconf[key] = mod[key]

    return newconf

def updateconf(conffile, updfile):
    """
    Add or modify values of test output yaml file to original configuration. Used for pedestal trimming.
    """
    
    conf = {}
    with open(conffile, 'r') as fileconf:
        conf = yaml.safe_load(fileconf)
        
    mod = {}
    if os.path.isfile(updfile):
        with open(updfile, 'r') as fileupd:
            mod = yaml.safe_load(fileupd)
        
        conf = recursive_update(conf, mod)
        
        with open(conffile,'w') as filenew:
            yaml_string=yaml.dump(conf, filenew)
    else:
        print(' >> ExternalPC: did not find output yaml file {updfile}, maybe it crashed? Continuing')

def check_hexactrl_sw():

    # in Centos7 or Alma9 branch ROCv3, stick to main path of environment and scripts                                                                                                                          
    # in feature-alma9 branch, use specific paths                                                                                                                                                              
    if configuration['TestingPCOpSys'] == 'Centos7':
        env = '/opt/hexactrl/ROCv3/ctrl/etc/env.sh'
        scriptloc = '/opt/hexactrl/ROCv3/ctrl/'

    # for backwards compatibility before 'HexactrlSWBranch' was in configuration                                                                                                         
    elif (configuration['TestingPCOpSys'] == 'Alma9') and ('HexactrlSWBranch' not in configuration.keys()):
        env = '/opt/hexactrl/feature-alma9/ctrl/etc/env.sh'
        scriptloc = '/opt/hexactrl/feature-alma9/ctrl/'

    elif (configuration['TestingPCOpSys'] == 'Alma9') and (configuration['HexactrlSWBranch'] == 'feature-alma9'):
        env = '/opt/hexactrl/feature-alma9/ctrl/etc/env.sh'
        scriptloc = '/opt/hexactrl/feature-alma9/ctrl/'

    elif (configuration['TestingPCOpSys'] == 'Alma9') and (configuration['HexactrlSWBranch'] == 'ROCv3'):
        env = '/opt/hexactrl/ROCv3/ctrl/etc/env.sh'
        scriptloc = '/opt/hexactrl/ROCv3/ctrl/'

    # make sure above files exist                                                                                                                                                                              
    assert os.path.isfile(f'{env}')
    assert os.path.isfile(f'{scriptloc}pedestal_run.py')


# Class to handle detached test script processes running on the PC 
class ScriptProcess:

    def __init__(self, scriptname, command, pc):

        self.pc = pc
        self.command = command
        self.scriptname = scriptname

        print(f' >> ExternalPC: Running {self.scriptname}.py with config {self.pc.config}...')

        self.proc = subprocess.Popen(self.command, shell=True, executable="/bin/bash")

    def is_finished(self):

        isfin = self.proc.poll()

        if isfin is None:
            return False
        elif isfin == 0:
            return True
        else:
            print(f' >> ExternalPC: Issue encountered in test. Ending test sequence...')
            raise RuntimeError

    def end_test(self):

        terminated = False
        if not self.is_finished:
            terminated = True
            self.proc.terminate()

        runs = glob.glob(f'{configuration["DataLoc"]}/{self.pc.outdir}/{self.scriptname}/*')
        runs.sort()

        try:
            print(f' >> ExternalPC: Output of {self.scriptname}.py located in {runs[-1]}')
            self.pc.initiated = True
        except:
            print(f' >> ExternalPC: Did not find output of test. Maybe it crashed? Continuing')
            return ''

        if self.scriptname in self.pc.outyaml.keys() and not terminated:
            print(f' >> ExternalPC: Updating configuration file with {runs[-1]}/{self.pc.outyaml[self.scriptname]}')
            updateconf(self.pc.config, runs[-1]+'/'+self.pc.outyaml[self.scriptname])

        thisrun = runs[-1].split('/')[-1]
        #return f'{scriptname}/{thisrun}'
        return runs[-1]

