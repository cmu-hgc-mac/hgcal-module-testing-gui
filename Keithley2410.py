import pyvisa
from time import sleep, time
from datetime import datetime
from math import copysign
import numpy as np

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

class Keithley2410:

    def __init__(self):
        # Initiate and configure PyVISA:
        self._rm = pyvisa.ResourceManager('@py')
        self._resource_list = self._rm.list_resources()
        print(" >> Keithley2410:", self._resource_list)
        #self._inst = self._rm.open_resource(self._resource_list[1])
        self._inst = self._rm.open_resource(configuration['HVResource'])
        self._inst.read_termination = "\r\n"
        self._inst.write_termination = "\r\n"

        # Instrument parameters, do not change
        self._VOLTAGE_LIMIT_LOW = -1.1e3
        self._VOLTAGE_LIMIT_HIGH = 1.1e3
        self._CURRENT_LIMIT_LOW = -1.05
        self._CURRENT_LIMIT_HIGH = 1.05
        self._ELEMENTS = ["voltage", "current", "resistance", "time", "status"]

        # User-editable default parameters below:
        self._channel = 1  # Default channel is 1, on rear of device
        self._wait_time_s = 0.1  # Wait time in seconds
        self._ilimit = 105e-6  # Current limit in A
        self._vlimit = 821  # Voltage limit in V - 821 to configure sweep to 800 correctly
        self._sense_mode = "current"
        self._elements = ["voltage", "current", "resistance", "time", "status"]

        # Initiate instrument
        self._write("*RST")
        self._write("SYSTem:REMote")

        self.voltage_now = 0.

        if configuration['HVTerminal'] == 'Rear':
            self._write('ROUTe:TERMinals REAR')
        elif configuration['HVTerminal'] == 'Front':
            self._write('ROUTe:TERMinals FRON')
        else:
            raise RuntimeError('HVTerminal in configuration should be Front or Rear')

        self._write(f"SOURCe{self._channel}:CLEar:AUTO ON")
        self._write(f"SENSe{self._channel}:FUNCtion:CONCurrent OFF")
        # self._write("FORMat:ELEMents VOLTage, CURRent, RESistance, TIME, STATus")
        self.set_elements(self._elements)
        self.set_current_limit(self._ilimit)
        self.set_voltage_limit(self._vlimit)
        self.set_sense_mode(self._sense_mode)
        if configuration['HasHVSwitch']:
            self.set_output_enable(1)
        self.set_output(0)
        self._write('SOURce1:CLEar:AUTO OFF')
        self.check_for_errors()

        self.display_string("Adapter connected.")
        
        # store all IV curves since this class was created
        self.IVdata = []

        self.bv_ramp_step = 25.
        self.bv_ramp_wait = 0.5
                
    def __del__(self):
        self._inst.close()

    def shutdown(self):
        """Safely shuts down the instrument
        """
        self.set_source_voltage(0)
        self.set_output(0)
        self.set_output_enable(0)
        self._write("SYSTem:LOCal")

    def _write(self, writeStr):
        print(' >> Keithley2410 Write:', writeStr)
        """Write command with built-in delay. Defaults to 100ms
        """
        self._inst.write(writeStr)
        sleep(self._wait_time_s)

    def _query(self, queryStr, wait = None):
        """Query command returns most recent buffer
        """
        print(' >> Keithley2410 Query:', queryStr)
        if wait is None:
            wait = self._wait_time_s
        response = self._inst.query(queryStr, wait).strip("\r\n")
        print(' >> Keithley2410 Response:', response)
        return response

    def _read(self):
        """Performs a read command and returns the parsed response
        """
        response = self._query("READ?")
        return self._parse_data(response)

    def set_elements(self, element_list):
        """Sets the elements returned in a read command
        Element must be one of the five enumerated below
        """
        self._elements = element_list
        element_string = ""
        for element in element_list:
            if element in self._ELEMENTS:
                if element_string != "":
                    element_string += ", "
                if element == "voltage":
                    element_string += "VOLTage"
                elif element == "current":
                    element_string += "CURRent"
                elif element == "resistance":
                    element_string += "RESistance"
                elif element == "time":
                    element_string += "TIME"
                elif element == "status":
                    element_string += "STATus"
                else:
                    raise ValueError("Undefined element")
            else:
                raise ValueError("Undefined element")
        self._write("FORMat:ELEMents " + element_string)

    def _parse_data(self, response):
        """Parses the received data into an array of dictionaries
        """
        response_list = response.split(",")
        num_elements = len(self._elements)
        if len(response_list) >= num_elements:
            data = []
            for i in range(0, int(len(response_list) / num_elements)):
                single_response = response_list[(num_elements * i):(num_elements * (i + 1) - 1)]
                element = dict(zip(self._elements, single_response))
                data.append(element)
            return data
        else:
            return response

    def _read_async(self):
        """Waits for data to be available for reading. Returns the response when available.
        """
        self._write("INIT; *OPC?")
        opc_status = 0
        while opc_status != 1:
            try:
                status_raw = self._inst.read_raw()  # For some reason Python prints new lines after read()
                opc_status = int(status_raw.decode('ASCII').strip("\r\n"))
            except pyvisa.errors.VisaIOError:
                sleep(1)
        response = self._query("FETCh?", 5.)
        return response

    def get_id(self):
        """Queries the instrument ID
        """
        return self._query("*IDN?")

    def set_channel(self, chan):
        """Sets the current channel. Only 1 is supported in the instrument.
        """
        self._channel = chan

    def set_output_enable(self, onoff):
        """Sets the output enable function active. This is used for safeguarding the test stand.
        """
        if onoff:
            self._write(f"OUTPut{self._channel}:ENABle ON")
        else:
            self._write(f"OUTPut{self._channel}:ENABle OFF")

    def set_output(self, onoff):
        """Sets the output on or off. Also sets voltage output to zero to keep state consistent
        and structure class properly for ramping.
        """
        if self.voltage_now != 0.:
            self.set_source_voltage(0.)
        if onoff:
            self._write(f"OUTPut ON")
        else:
            self._write(f"OUTPut OFF")
            
    def outputOn(self):
        """Sets the output on
        """
        self.set_output(True)

    def outputOff(self):
        """Sets the output off                                                                                                                                                                            
        """
        self.set_output(False)
                 
    def get_output(self):
        return bool(int(self._query(f"OUTPut?")))
       
    def set_current_limit(self, ilimit):
        """Sets the current compliance limit.
        """
        if self._CURRENT_LIMIT_LOW <= abs(ilimit) <= self._CURRENT_LIMIT_HIGH:
            self._ilimit = ilimit
            self._write(f"SENSe{self._channel}:CURRent:PROTection:LEVel {ilimit}")
        else:
            raise ValueError("Invalid current limit")

    def set_voltage_limit(self, vlimit):
        """Sets the voltage compliance limit
        """
        if self._VOLTAGE_LIMIT_LOW <= abs(vlimit) <= self._VOLTAGE_LIMIT_HIGH:
            self._vlimit = vlimit
            self._write(f"SENSe{self._channel}:VOLTage:PROTection:LEVel {vlimit}")
        else:
            raise ValueError("Invalid voltage limit")

    def get_limit_tripped(self):
        """Returns true if either voltage or current limits are tripped
        """
        vtrip = int(self._query(f"SENSe{self._channel}:VOLTage:PROTection:TRIPped?"))
        itrip = int(self._query(f"SENSe{self._channel}:CURRent:PROTection:TRIPped?"))
        return (vtrip or itrip)

    def get_enable_tripped(self):
        """Returns 1 if the output enable line has been tripped. (Tripped means the output can be enabled)
        """
        status = int(self._query("OUTPut:ENABle:TRIPped?"))
        return status
        
    def switch_state(self):
        """Renaming of above class for compatibility
        """
        return bool(self.get_enable_tripped())

    def set_source_voltage_mode(self, mode):
        """Sets the source mode to voltage with the defined mode.
        Options are fixed, list, or sweep.
        """
        self._write(f"SOURce{self._channel}:FUNCtion VOLTage")
        if mode == "fixed":
            self._write(f"SOURce{self._channel}:VOLTage:MODE FIXed")
        elif mode == "list":
            self._write(f"SOURce{self._channel}:VOLTage:MODE LIST")
        elif mode == "sweep":
            self._write(f"SOURce{self._channel}:VOLTage:MODE SWEep")
        else:
            raise ValueError("Invalid mode selection")

    def set_source_current_mode(self, mode):
        """Sets the source mode to current with the defined mode.
        Options are fixed, list, or sweep.
        """
        self._write(f"SOURce{self._channel}:FUNCtion CURRent")
        if mode == "fixed":
            self._write(f"SOURce{self._channel}:CURRent:MODE FIXed")
        elif mode == "list":
            self._write(f"SOURce{self._channel}:CURRent:MODE LIST")
        elif mode == "sweep":
            self._write(f"SOURce{self._channel}:CURRent:MODE SWEep")
        else:
            raise ValueError("Invalid mode selection")

    def set_source_voltage(self, value):
        """Sets the source mode to fixed voltage with the defined value. If the set voltage is
        sufficiently different from the current voltage, the output will be slowly ramped to that
        new voltage.
        """
        if not self.get_output() and value != 0.:
            raise ValueError('Output must be on to change output voltage')
            return

        if self._VOLTAGE_LIMIT_LOW <= abs(value) <= self._vlimit:

            self.set_source_voltage_mode("fixed")

            # ramp up the voltage slowly if it's very different than current voltage
            # do this only if the 
            difference = value - self.voltage_now
            if abs(difference) > self.bv_ramp_step:
                for i in range(1, int(abs(difference) // self.bv_ramp_step) + 1):
                    this_voltage = self.voltage_now + self.bv_ramp_step*i*copysign(1, difference)
                    self._write(f"SOURce{self._channel}:VOLTage {this_voltage}")
                    sleep(self.bv_ramp_wait)

            self.voltage_now = value
            self._write(f"SOURce{self._channel}:VOLTage {value}")
        else:
            raise ValueError("Invalid set voltage")

    def setVoltage(self, value):
        """Renaming of above function for compatibility
        """
        self.set_source_voltage(value)

    def set_source_current(self, value):
        """Sets the source mode to fixed current with the defined value.
        """
        if self._CURRENT_LIMIT_LOW <= abs(value) <= self._ilimit:
            self.set_source_current_mode("fixed")
            self._write(f"SOURce{self._channel}:CURRent {value}")
        else:
            raise ValueError("Invalid set current")
    def set_sense_mode(self, mode):
        """Sets the sense mode to either "voltage" or "current"
        """
        if mode == "voltage":
            self._sense_mode = mode
            self._write(f"SENSe{self._channel}:FUNCtion:ON 'VOLTage:DC'")
            self._write(f"SENSe{self._channel}:VOLTage:DC:RANGe:AUTO ON")
        elif mode == "current":
            self._sense_mode = mode
            self._write(f"SENSe{self._channel}:FUNCtion:ON 'CURRent:DC'")
            #self._write(f"SENSe{self._channel}:CURRent:DC:RANGe:AUTO ON")
            self._write(f"SENSe{self._channel}:CURRent:DC:RANG 100E-6")
        else:
            raise ValueError("Invalid sense mode")

    def get_sense_voltage(self):
        """Returns the sensed voltage
        """
        if self._sense_mode != "voltage":
            self.set_sense_mode("voltage")
        self._write("CONFigure:VOLTage:DC")
        measurement = self._query("READ?")
        return float(self._parse_data(measurement)[0]['voltage'])

    def measureVoltage(self):
        """Renaming of above function for compatibility
        """
        return self.get_sense_voltage(), '', ''


    def get_sense_current(self):
        """Returns the sensed current
        """
        if self._sense_mode != "current":
            self.set_sense_mode("current")
        self._write("CONFigure:CURRent:DC")
        # reconfigure to disable auto-ranging
        self._write(f"SENSe{self._channel}:CURRent:DC:RANG 100E-6")
        #measurement = self._query("READ?", 1.) ### fix 1s delay
        start = time()
        while True:
            measurement = self._query("READ?", 0.)
            if time() - start >= 5.:
                break
        measurement = self._query("READ?", 0.)
        return float(self._parse_data(measurement)[0]['current'])

    def measureCurrent(self):
        """Renaming of above function for compatibility
        """
        return '', self.get_sense_current(), ''

    def voltage_sweep(self, Vmin, Vmax, steps, Ilimit=105e-6, delay_s=1.):
        """Performs a voltage sweep from Vmin to Vmax over steps.
        Optional parameters Ilimit and delay_s set the current limit and time delay.
        """
        if Vmin >= self._VOLTAGE_LIMIT_LOW and Vmax <= self._vlimit:

            self.display_string("Sweeping...")
            self.set_source_voltage(0.)

            Vstep = (Vmax - Vmin) / steps 
            self.set_sense_mode("current")
            self.set_current_limit(Ilimit)
            self._write(f"SOURce{self._channel}:FUNCtion VOLTage")
            self._write(f"SOURce{self._channel}:VOLTage:START {Vmin}")
            self._write(f"SOURce{self._channel}:VOLTage:STOP {Vmax}")
            self._write(f"SOURce{self._channel}:VOLTage:STEP {Vstep}")
            self._write(f"SOURce{self._channel}:VOLTage:MODE SWEep")
            self._write(f"SOURce{self._channel}:SWEep:SPACing LINear")
            self._write(f"TRIGger:COUNt {steps+1}")
            self._write(f"SOURce{self._channel}:DELay {delay_s}")
            self.set_output(1)
            sweep_data = self._read_async()
            self.voltage_now = Vmax
            self.set_output(0)
            parsed_data = self._parse_data(sweep_data)

            self.display_string("Sweep complete.")        
            
            return parsed_data
        else:
            raise ValueError("Voltage range out of bounds")

    def takeIV(self, Vmax, step, RH, Temp):
        """Simple wrapper of voltage_sweep above, mostly for compatibility
        Records date and time and formats response into specific array structure
        """
    
        current_date = datetime.now()
        date = current_date.isoformat().split('T')[0]
        time = current_date.isoformat().split('T')[1].split('.')[0]

        steps = int(Vmax//step)
        ivdata = self.voltage_sweep(0, Vmax, steps, delay_s=1.)
        
        temparray = [[i*step, float(ivdata[i]['voltage']), float(ivdata[i]['current']), float(ivdata[i]['resistance'])] for i in range(len(ivdata))]

        datadict = {'RH': RH, 'Temp': Temp, 'data': np.array(temparray), 'date': date, 'time': time, 'datetime': current_date}
        self.IVdata.append(datadict)
                
        return datadict

    def display_string(self, string):
        """Display a string on the upper display of the power supply
        """
        
        self._write('DISP:WIND1:TEXT "{}"'.format(string))
        self._write('DISP:WIND1:TEXT:STAT ON')
        sleep(2.0)
        self._write('DISP:WIND1:TEXT:STAT OFF')
        self._write('DISP:WIND2:TEXT:STAT OFF')

    # Clear the Keithley error cache and print errors present
    def check_for_errors(self, ln=None):
        err_string = ''
        if ln == None:
            while True:
                err = self._query('SYSTem:ERRor?')
                if (err[0:3] != '+0,' and err[0:2] != '0,'):
                    err_string += err
                else:
                    break
        else:
            for i in range(ln):
                err = self._query('SYSTem:ERRor?')
                if (err[0:3] != '+0,' and err[0:2] != '0,'):
                    err_string += err
                else:
                    break
        if err_string != '':
            print('>> Found error: {}'.format(err_string))
            raise ValueError(err_string)

    # Take IV curve
    # Storing/plotting curve handled elsewhere
    def takeIVold(self, maxV, stepV, RH, Temp, errcheck_step=5):

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
            voltage, _, _ = self.measureVoltage()
            resistance = voltage / current

            data.append([vltg, voltage, np.abs(current), resistance])

            print(f'   Set {vltg} V Act {round(voltage,2)} V Meas {round(np.abs(current)*1000000.,2)} muA')
            if np.abs(current)*1000000. > 100.:
                print(f'>> Hit compliance {np.abs(current)*1000000.}muA at step {i}')
                compl_ctr += 1

            if compl_ctr == 3:
                break

        self.display_string('Loop finished.')
        print('>> Loop finished')
        
        # Make output dictionary and return
        datadict = {'RH': RH, 'Temp': Temp, 'data': np.array(data), 'date': date, 'time': time, 'datetime': current_date}
        self.IVdata.append(datadict)
        print('>> Disabling output')
        self.setVoltage(0.)
        self.outputOff()

        return datadict
