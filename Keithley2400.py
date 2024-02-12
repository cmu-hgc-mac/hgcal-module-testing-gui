from time import sleep
from time import time
import numpy as np
from os import environ
import pyvisa
from datetime import datetime

import contextlib
import io
import sys

from SCPI import SCPI

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

@contextlib.contextmanager
def nostdout():
    save_stdout = sys.stdout
    sys.stdout = io.BytesIO()
    yield
    sys.stdout = save_stdout

class Keithley2400:

    # Initializer opens visa resource and pushes initial state
    # Importantly, it sets the HV switch to be active and sets the current compliance
    def __init__(self):

        resource = environ.get('K2400_VISA', configuration['HVResource'])
        self.inst = SCPI(resource, verbosity=1, wait=0.5)
        self.inst.open()
        self.inst.rst()
        self.check_for_errors()

        if configuration['HVTerminal'] == 'Rear':
            self.write('ROUT:TERM REAR')
        elif configuration['HVTerminal'] == 'Front':
            self.write('ROUT:TERM FRON')
        else:
            raise RuntimeError('HVTerminal in configuration should be Front or Rear')

            
        self.inst.beeperOff()
        self.inst.setRemote()
        self.inst.setVoltageRange(None, channel=1)
        self.write('SOUR1:FUNC:MODE VOLT')
        self.write('SENS1:FUNC:ON "CURR"')
        self.inst.outputOff(channel=1)
        if configuration['HasHVSwitch']:
            self.write('OUTPut:ENABle ON')
        self.output = False
        self.inst.setVoltage(0., channel=1)
        self.inst.setCurrentCompliance(0.000105, channel=1)
        self.inst.setMeasureCurrentRange(None, channel=1)
        self.inst.setVoltageRange(None, channel=1)

        self.display_string('Adapter connected')

        self.IVdata = []

    # Add suffix string to all write commands
    def write(self, string):
        self.inst._instWrite(string)
        
    # Add suffix string to all query commands and format response
    def query(self, string):
        return self.inst._instQuery(string).strip('\r\n').split(',')
        
    # Destructor that only sorta works. not sure why.
    def __del__(self):
        self.outputOff()
        self.check_for_errors()
        self.inst.beeperOn()
        self.inst.setLocal()
        self.inst.close()
        
    # Make the Keithley display whatever string you want
    # Set for top screen, bottom screen is possible but not implemented
    def display_string(self, string):

        self.write('DISP:WIND1:TEXT "{}"'.format(string))
        self.write('DISP:WIND1:TEXT:STAT ON')
        sleep(2.0)
        self.write('DISP:WIND1:TEXT:STAT OFF')
        self.write('DISP:WIND2:TEXT:STAT OFF')

    # Clear the Keithley error cache and print errors present
    def check_for_errors(self, ln=None):
        err_string = ''
        if ln == None:
            while True:
                err = self.inst.readError()
                if (err[0:3] != '+0,' and err[0:2] != '0,'):
                    err_string += err
                else:
                    break
        else:
            for i in range(ln):
                err = self.inst.readError()
                if (err[0:3] != '+0,' and err[0:2] != '0,'):
                    err_string += err
                else:
                    break
        if err_string != '':
            print('>> Found error: {}'.format(err_string))
            raise ValueError(err_string)

    # Activate voltage output
    def outputOn(self):
        self.inst.outputOn(channel=1)
        self.output = True

    # Deactivate voltage output
    def outputOff(self):
        self.inst.outputOff(channel=1)
        self.output = False

    # Set voltage output
    def setVoltage(self, voltage):
        self.inst.setVoltage(voltage, channel=1)

    # Measure current
    # NOTE: currently sleeping 5sec to stabilize measurement
    # Current stabilizes much faster when you ask for a measurement continually
    def measureCurrent(self):
        self.write('SENS1:FUNC:ON "CURR"')
        start = time()
        #with nostdout():
        while True:
            outdata = self.query('MEASure:CURRent:DC?')
            if time() - start >= 4.:
                break
        outdata = self.query('MEASure:CURRent:DC?')
        voltage = float(outdata[0])
        current = float(outdata[1])
        resistance = float(outdata[2])

        return voltage, current, resistance

    # Measure voltage
    def measureVoltage(self):
        self.write('SENS1:FUNC:ON "VOLT"')
        outdata = self.query('MEASure:VOLTage:DC?')
        voltage = float(outdata[0])
        current = float(outdata[1])
        resistance = float(outdata[2])

        return voltage,	current, resistance

    # Take IV curve
    # Storing/plotting curve handled elsewhere
    def takeIV(self, maxV, stepV, RH, Temp, errcheck_step=5):

        self.setVoltage(0.)
        self.outputOn()

        ln = int(maxV//stepV)+1
        data = [] # append measurements to this list as rows 

        self.display_string('Looping...')
        print(f'>> Looping to {maxV}V in steps of {stepV}V')
        sleep(5) 

        # Record date
        current_date = datetime.now()
        date = current_date.isoformat().split('T')[0]
        time = current_date.isoformat().split('T')[1].split('.')[0]

        # Count the number of measurements that hit current compliance
        # Break the loop after the second to save time
        compl_ctr = 0
        for i in range(0, ln):
            if i % errcheck_step == 0:
                self.check_for_errors(1) # Periodically check Keithley error cache

            vltg = i*stepV
            self.setVoltage(vltg)
            # Delay here doesn't work for some reason
            # maybe because the Keithley isn't in measure mode?
            #sleep(measdelay)
            _, current, _ = self.measureCurrent()
            voltage, _, resistance = self.measureVoltage()

            data.append([vltg, voltage, np.abs(current), resistance])
            
            print(f'   Set {vltg} V Act {round(voltage,2)} V Meas {round(np.abs(current)*1000000.,2)} muA')
            if np.abs(current)*1000000. > 100.:
                print(f'>> Hit compliance {np.abs(current)*1000000.}muA at step {i}')
                compl_ctr += 1

            if compl_ctr == 2:
                break

        self.display_string('Loop finished.')
        print('>> Loop finished')

        # Make output dictionary and return
        datadict = {'RH': RH, 'Temp': Temp, 'data': np.array(data), 'date': date, 'time': time}
        self.IVdata.append(datadict)
        print('>> Disabling output')
        self.setVoltage(0.)
        self.outputOff()

        return datadict

    # Check state of HV switch
    def switch_state(self):
        outdata = self.query('OUTPut:ENABle:TRIPped?')
        state = int(outdata[0])
        if state == 1:
            return True
        elif state == 0:
            return False
        else:
            raise ValueError('Unknown HV switch state')

