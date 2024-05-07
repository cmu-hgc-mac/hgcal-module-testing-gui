import numpy as np
import matplotlib.pyplot as plt
import PySimpleGUI as sg
from TrenzTestStand import TrenzTestStand
from CentosPC import CentosPC
from Keithley2410 import Keithley2410
from time import sleep
import os
import traceback

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

if configuration['HasLocalDB']:
    from DBTools import iv_save, pedestal_upload, iv_upload, plots_upload

from DBTools import add_RH_T
    
lgfont = ('Arial', 30)
sg.set_options(font=("Arial", int(configuration['DefaultFontSize'])))


"""
-------------------InteractionGUI.py-----------------

This class contains a number of functions that are called by the TestingGUIBase. In general, they are for interacting
with the user: telling them what to do and when to do it, and managing the testing sequence. Most of the functions use
an argument called `state`: this is a dictionary which contains information about the state of the testing system (i.e.
if the DCDC is powered) and is passed back and forth between the TestingGUIBase and these functions.

Perhaps the most important function is the `end_session` function, which handles the safe exiting of the test setup for
any state.
-----------------------------------------------------
"""

def do_something_window(instruction, button, title=None, can_end=False):
    """
    Function which opens a window which tells the user to do something and has a button which is pressed once they've 
    done the thing. It has the option to allow the user to end the session instead of continuing, which when pressed
    makes the function return 'END'.
    """

    if title == None:
        title = instruction
    
    layout = [[sg.Text(instruction, font=lgfont)], [sg.Button(button)]]
    if can_end:
        layout[1].append(sg.Button("End Session"))
    window = sg.Window(f"Module Test: {instruction}", layout, margins=(200,100))

    ret = ''
    while True:
        event, values = window.read()
        if event == button or event == sg.WIN_CLOSED:
            ret = 'CONT'
            break
        if can_end and event == "End Session":
            ret = 'END'
            break
        
    window.close()
    return ret

def waiting_window(message, title=None, description=None):
    """
    Function which opens a window when the GUI is handling something automatically and the user has to wait.
    """
    
    if title is None:
        title = message

    layout = [[sg.Text(message, font=lgfont)]]
    if description is not None:
        layout.append([sg.Text(description)])
    window = sg.Window(f"Module Test: {message}", layout, margins=(200,100))

    event, values = window.read(timeout=100)
    return window

    
def end_session(state):
    """
    Ends the testing session. The state of the testing system is contained in the `state` dictionary; this 
    function uses those flags to tell the user what must be done (and in what order) to safely shut down the
    system. In general, shutting it down broadly follows five steps:
        - Disabling the HV power
        - De-powering the DCDC or Low Voltage Supply
        - Shutting down the Trenz
        - De-powering the Trenz
        - Disconnecting all of the parts and the module
    """

    # read density and shape from module serial
    density = state['-Module-Serial-'].split('-')[1][1]
    shape = state['-Module-Serial-'].split('-')[2][0]
    if density == 'L':
        if shape not in ['F', 'L', 'R']:
            raise NotImplementedError
    elif density == 'H':
        if shape not in ['F']:
            raise NotImplementedError
                            
    ending = waiting_window("Ending session...")
    sleep(2)

    # First disable HV if it's on
    # This part assumes the 'ps' is instantiated; a reasonable assumption if the HV output is on
    if state['-HV-Output-On-']:
        state['ps'].outputOff()
        update_state(state, '-HV-Output-On-', False, 'black')

    # De-power and disconnect the DCDC/LV Power and Hexacontroller
    # Have to nest these steps because of shutdown order
    if state['-DCDC-Connected-']:
        if state['-DCDC-Powered-']:

            command = "Disconnect DCDC power"+(" (green)" if configuration['MACSerial'] == 'CM' else '') if density+shape == 'LF' else "Turn off low voltage power"
            button = "Depowered"
            do_something_window(command, button)
            update_state(state, '-DCDC-Powered-', False, 'black')
            
            if state['-Hexactrl-Connected-']:
                if state['-Hexactrl-Powered-']:
                    if state['-Hexactrl-Accessed-']:
                        shutdown = waiting_window("Shutting down hexacontroller...")
                        if not state['-Debug-Mode-']:
                            state['ts'].shutdown()
                        sleep(10)
                        shutdown.close()
                        update_state(state, '-FW-Loaded-', False, 'black')
                        update_state(state, '-DAQ-Server-', False, 'black')
                        update_state(state, '-I2C-Server-', False, 'black')
                        update_state(state, '-Hexactrl-Accessed-', False, 'black')
                        
                    do_something_window("Disconnect hexacontroller power"+(" (blue)" if configuration['MACSerial'] == 'CM' else ''), "Disconnected")
                    update_state(state, '-Hexactrl-Powered-', False, 'black')
                    
                open_box(state)
                
                do_something_window("Disconnect hexacontroller from trophy", "Disconnected")
                update_state(state, '-Hexactrl-Connected-', False, 'black')

        # Disconnect trophy, looback, and DCDC/LV Cables
        if state['-Trophy-Connected-']:
            if density+shape == 'LF':
                do_something_window("Disconnect loopback", "Disconnected")
            do_something_window("Disconnect trophy", "Disconnected")
            update_state(state, '-Trophy-Connected-', False, 'black')
            
        command = "Disconnect DCDC" if density+shape == 'LF' else "Disconnect low voltage cables"
        do_something_window(command, "Disconnected")
        update_state(state, '-DCDC-Connected-', False, 'black')

    # Open the box (function handles if it's already open)
    open_box(state)

    # Lastly, disconnect the HV cable
    if state['-HV-Connected-']:

        do_something_window("Disconnect HV cable", "Disconnected")
        update_state(state, '-HV-Connected-', False, 'black')
        
    sleep(2)
    ending.close()
    return
    
def SetLED(window, key, color, empty=False):
    """
    Changes color of LED indicator
    """

    graph = window[key]
    graph.erase()
    if not empty:
        graph.draw_circle((0, 0), 12, fill_color=color, line_color=color)
    else:
        graph.draw_circle((0, 0), 12, fill_color=None, line_color=color)
    
def update_state(state, field, val, color=None):
    """
    Safely modifies a field of the state dictionary. If that field has an LED, update the color
    """
    
    state[field] = val
    if field[0] == '-' and color is not None:
        SetLED(state['basewindow'], field, color)
    event, values = state['basewindow'].read(timeout=10)

def initial_module_checks(state):
    """
    Guides the user through initial checks to ensure the module is safe to test. Right now, this involves
    measuring pad resistance, measuring the DC power on the same pads, and verifying the behavior under
    bias voltage is correct. I imagine that during full production we can skip most of these, but they are
    wise until then to ensure the test stand is protected.

    If there is an issue or the user decides to abort the test, the function will return 'END'; otherwise,
    it will return 'CONT'
    """

    # read density and shape from module serial
    density = state['-Module-Serial-'].split('-')[1][1]
    shape = state['-Module-Serial-'].split('-')[2][0]
    if density == 'L':
        if shape not in ['F', 'L', 'R']:
            raise NotImplementedError
    elif density == 'H':
        if shape not in ['F']:
            raise NotImplementedError

    do_something_window("Ensure you are grounded (i.e. with grounding strap)", "Grounded", title="Ground Yourself")
        
    pads_LF = ["P1V2D", "P1V2A", "P1V5C", "P1V5D"]
    pads_LR_LL = ["P1V2D", "P1V2A", "P1V5"]
    pads_HF = ['P1V2_D', 'P1V2A_UP', 'P1V2A_DW', 'P1V5A', 'P1V5A_UP', 'P1V5D']

    if density == 'L':
        if shape == 'F':
            thesepads = pads_LF
        elif shape == 'R' or shape == 'L':
            thesepads = pads_LR_LL
    if density == 'H':
        if shape == 'F':
            thesepads = pads_HF
            
    layout = [[sg.Text("Use multimeter to check hexaboard resistances for shorts", font="Any 15")]]
    colleft = []
    colright = []
    idx = 2
    for pad in thesepads:
        colleft.append([sg.Text(f"{pad}: ")])
        colright.append([sg.Radio('Short', idx, key=f"-{pad}-Short-"), sg.Radio('No Short', idx, key=f"-{pad}-No-Short-")])
        idx += 1
    layout.append([sg.Column(colleft), sg.Column(colright)])
    layout.append([sg.Button("Continue")])
    
    window = sg.Window("Module Test: Check Hexaboard", layout, margins=(200,100))

    while True:
        event, values = window.read()
        if event == "Continue":
            noshorts = all([values[f"-{pad}-No-Short-"] for pad in thesepads])
            if not noshorts:
                window.close()
                end_session(state)
                return 'END'
            else:
                break
        if event == sg.WIN_CLOSED:
            window.close()
            end_session(state)
            return 'END'

    window.close()

    # If live module, check the bias voltage behavior
    if state['-Live-Module-']:

        outcode = check_leakage_current(state)
        if outcode == 'END':
            return 'END'

        open_box(state)

    # Check the voltage on the pads to ensure correct power
    command = "Connect DCDC to hexaboard" if density+shape == 'LF' else "Connect low voltage wires"
    do_something_window(command, "Connected")
    update_state(state, '-DCDC-Connected-', True, 'green')

    command = "Connect DCDC power cable"+(" (green)" if configuration['MACSerial'] == 'CM' else "") if density+shape == 'LF' else "Turn on low voltage power"
    do_something_window(command, "Powered")
    update_state(state, '-DCDC-Powered-', True, 'green')

    layout = [[sg.Text("Measure voltage on pads", font=lgfont)], [sg.Text("Be careful to not short the probes!")]]
    colleft = []
    colright = []
    idx = 2
    for pad in thesepads:
        expect = '1.2-1.25V' if '1V2' in pad else '1.47-1.5V'
        colleft.append([sg.Text(f"{pad}:")])
        colright.append([sg.Text(f"(expect {expect})"), sg.Radio('Correct', idx, key=f"-{pad}-corr-"), sg.Radio('Incorrect', idx, key=f"-{pad}-incorr-")])
        idx += 1
    layout.append([sg.Column(colleft), sg.Column(colright)])
    layout.append([sg.Button("Continue")])

    window = sg.Window("Module Test: Probe power pads", layout, margins=(200,100))

    while True:
        event, values = window.read()
        if event == "Continue":
            allcorr = all([values[f"-{pad}-corr-"] for pad in thesepads])
            if not allcorr:
                window.close()
                end_session(state)
                return 'END'
            else:
                break

            break
        if event == sg.WIN_CLOSED or event == "Power incorrect":
            window.close()
            end_session(state)
            return 'END'
            
    window.close()

    command = "Disconnect DCDC power cable"+(" (green)" if configuration['MACSerial'] == 'CM' else '') if density+shape == 'LF' else "Turn off low voltage power"
    do_something_window(command, "Disconnected")
    update_state(state, '-DCDC-Powered-', False, 'black')
    return 'CONT'

def open_close_box(state, close=True):
    """
    Handles the opening and closing of the testing dark box. If debug mode is off and the power supply object is 
    instantiated, automatically checks the switch on the dark box to see if it's closed or not; otherwise, it pulls
    from the `state` dictionary to check if it's closed.
    """

    if state['ps'] is not None and type(state['ps']) != int and configuration['HasHVSwitch']: 
        HVswitch_tripped = state['ps'].switch_state()
    else:
        HVswitch_tripped = state['-Box-Closed-']

    if state['-Box-Closed-'] != close or HVswitch_tripped != close:
        closeopen = 'Close' if close else 'Open'
        button = 'Closed' if close else 'Opened'
        if state['-Debug-Mode-'] or configuration['HasHVSwitch'] == False:
            do_something_window(f"{closeopen} lid of dark box", button, title=f"{closeopen} Box")
            update_state(state, '-Box-Closed-', close, 'green' if close else 'black')
        else:
            changelid = waiting_window(f"{closeopen} lid of dark box")
            while True:
                HVswitch_tripped = state['ps'].switch_state()
                if HVswitch_tripped == close:
                    break
            sleep(2)
            changelid.close()
            update_state(state, '-Box-Closed-', close, 'green' if close else 'black')

def open_box(state):
    open_close_box(state, close=False)

def close_box(state):
    open_close_box(state, close=True) 

def connect_HV(state):
    """
    Handles the instantiation of the power supply object and connecting the HV cable. Should only
    be called if the module is live. 

    The power supply object is stored in the `state` dictionary under the field 'ps' for power supply.
    If in debug mode, the 'ps' field is set to be an integer. This way, other functions can check
    that this function was run even in debug mode.
    """

    if not state['-HV-Connected-']:
        do_something_window("Connect HV cable to hexaboard", "Connected", title="Connect HV")
        update_state(state, '-HV-Connected-', True, 'green')
        
    if state['ps'] is None:
        keith = waiting_window('Connecting to Keithley...', description=f'Initialize PyVISA Resource {configuration["HVResource"]}')
        if state['-Debug-Mode-']:
            sleep(5)
            ps = 1
            update_state(state, 'ps', ps)
        else:
            ps = Keithley2410()
            update_state(state, 'ps', ps)
        keith.close()
    
    close_box(state)
            
def check_leakage_current(state):
    """
    Measures the leakage current of the module at a few select bias voltages to ensure there are
    not issues. It displays the measurements to the user afterward for verificaton. If the leakage 
    current at or below 300V is above 1μA, stops the check and offers the user a chance to abort. 
    If the user desires to continue, the function returns 'CONT'; otherwise, it returns 'END' after
    ending the session.
    """

    leakage_current = {} #{0: None, 1: None, 10: None, 100: None, 300: None, 600: None}
    # best to set the keys in the dict according to bias direction
    # and then use those keys
    for vltg in [0, 1, 10, 100, 300, 600]:
        if configuration['HVWiresPolarization'] == 'Forward':
            leakage_current[-vltg] = None
        else:
            leakage_current[vltg] = None

    connect_HV(state)

    ivprobe = waiting_window('Verifying module IV behavior...')
    nominal = True
    if state['-Debug-Mode-']:
        sleep(5)
    else:
        state['ps'].outputOn()
        update_state(state, '-HV-Output-On-', True, 'green')
        
        for key in leakage_current.keys():

            state['ps'].setVoltage(key)
            _, current, _ = state['ps'].measureCurrent()
            leakage_current[key] = current
            print(' >> Checking leakage current:', key, current*1000000.)
            if np.abs(current)*1000000. > 1. and abs(key) < 500:
                nominal = False
                break

        state['ps'].outputOff()
        update_state(state, '-HV-Output-On-', False, 'black')

    ivprobe.close()
    
    readout = [[sg.Text(f"{key} V Bias: {round(1000000.*leakage_current[key],3)} μA") if leakage_current[key] is not None else sg.Text(f"{key} V Bias: {None} μA")] for key in leakage_current.keys()]

    title = "Module leakage current good" if nominal else "Module leakage current not nominal. Continue?"
    
    layout = [[sg.Text(title, font=lgfont)],
              [sg.Frame('Leakage Current', readout, key='-Leakage-Current-')],
              [sg.Button("Continue"), sg.Button("End Test")]]
    window = sg.Window(f"Module Test: Leakage Current Results", layout, margins=(200,100))

    while True:
        event, values = window.read()
        if event == "Continue" or event == sg.WIN_CLOSED:
            break
        if event=="End Test":
            window.close()
            end_session(state)
            return 'END'
            
    window.close()
    return 'CONT'

def configure_test_stand(state, trenzhostname):
    """
    Guides the user through connecting the various boards and then handles the startup of the testing system. At
    the moment, it assumes the DCDC has already been connected but is not powered. The Trenz test stand is added to
    the `state` dictionary under the field 'ts' and the Centos PC object is added under the field 'pc'. If the objects
    detect errors in the firmware or services, the function returns 'END' after ending the sesion; if all succeed, 
    it returns 'CONT'.
    """
    
    # read density and shape from module serial
    density = state['-Module-Serial-'].split('-')[1][1]
    shape = state['-Module-Serial-'].split('-')[2][0]
    if density == 'L':
        if shape not in ['F', 'L', 'R']:
            raise NotImplementedError
    elif density == 'H':
        if shape not in ['F']:
            raise NotImplementedError
    else:
        raise NotImplementedError
        
    do_something_window("Connect trophy board to hexaboard", "Connected", title="Connect Trophy")
    if density+shape == 'LF':
        do_something_window("Connect loopback board to hexaboard", "Connected", title="Connect Loopback")
    update_state(state, '-Trophy-Connected-', True, 'green')
    do_something_window("Ensure NOTHING is powered", "No power")
    do_something_window("Connect trophy board and hexacontroller", "Connected", title='Connect Hexacontroller')
    update_state(state, '-Hexactrl-Connected-', True, 'green')
    if state['-Live-Module-']:
        close_box(state)
    do_something_window("Connect hexacontroller power cable"+(" (blue)" if configuration['MACSerial'] == 'CM' else ''), "Powered", title='Power Hexacontroller')
    update_state(state, '-Hexactrl-Powered-', True, 'green')
    
    connecting = waiting_window("Connecting to hexacontroller...", description=f'ssh root@{trenzhostname}')
    if state['-Debug-Mode-']:
        sleep(5)
        ts = None
    else:
        ts = TrenzTestStand(trenzhostname, state['-Module-Serial-']) # will take some time if the Trenz was just powered
    connecting.close()
    update_state(state, '-Hexactrl-Accessed-', True, 'green')
    update_state(state, 'ts', ts)

    command = "Connect DCDC power cable"+(" (green)" if configuration['MACSerial'] == 'CM' else "") if density+shape == 'LF' else "Turn on low voltage power"
    do_something_window(command, "Powered")
    update_state(state, '-DCDC-Powered-', True, 'green')
    loading = waiting_window("Loading firmware on hexacontroller...", title="Loading Firmware...", description='fw-loader load [firmware] && listdevice')
    if state['-Debug-Mode-']:
        sleep(5)
        fwloaded = True
    else:
        fwloaded = state['ts'].loadfw()
    loading.close()
    update_state(state, '-FW-Loaded-', fwloaded, 'green' if fwloaded else 'red')
    if not fwloaded:
        ending = waiting_window("Firmware loading error or unable to find ROC channels. Exiting...", title="Error in Firmware")
        sleep(2)
        ending.close()
        end_session(state)
        return 'END'

    starting = waiting_window("Starting services on test stand...", title="Starting Services...", description='systemctl restart daq-server && systemctl restart i2c-server')
    if state['-Debug-Mode-']:
        sleep(5)
        services = True
    else:
        services = state['ts'].startservers()
    starting.close()
    update_state(state, '-DAQ-Server-', services, 'green' if services else 'red')
    update_state(state, '-I2C-Server-', services, 'green' if services else 'red')
    if not services:
        ending = waiting_window("Error in Trenz services. Exiting...", title="Error in Services")
        sleep(2)
        ending.close()
        end_session(state)
        return 'END'

    daq = waiting_window("Starting services on PC...", title="Starting Services...", description='systemctl restart daq-client')
    if state['-Debug-Mode-']:
        pc = None
        sleep(5)
    else:
        pc = CentosPC(trenzhostname, state['-Module-Serial-'], state['-Live-Module-']) # automatically starts daq client
    daq.close()
    update_state(state, '-DAQ-Client-', True, 'green')
    update_state(state, 'pc', pc)

    ready = waiting_window("Ready to run tests.", title="Ready")
    sleep(2)
    ready.close()
    return 'CONT'

def run_pedestals(state, BV):
    """
    Runs pedestals via the PC and then makes hexmap plots. If the module is live, sets the bias voltage 
    according to the BV argument.
    """
    
    pedestals = waiting_window(f"Running Pedestals (BV={BV})...", description='python3 pedestal_run.py [options...]')
    
    if state['-Debug-Mode-']:
        sleep(5)
        hexpath = ''
    else:
        if state['-Live-Module-'] and BV is not None:
            state['ps'].outputOn()
            update_state(state, '-HV-Output-On-', True, 'green')
            state['ps'].setVoltage(float(BV))

        state['pc'].pedestal_run(BV=BV)
        
        if configuration['HasLocalDB']:
            try:
                pedestal_upload(state) # uploads pedestals to database
            except Exception:
                print('  -- Pedestal upload exception:', traceback.format_exc())
                ### XYZ save as csv?

        #if state['-Live-Module-']:
        #    state['ps'].outputOff()
        #    update_state(state, '-HV-Output-On-', False, 'black')
        #try:
        hexpath = state['pc'].make_hexmaps(BV=BV)
        if configuration['HasLocalDB']:
            try:
                plots_upload(state) # uploads pedestal plots to database
            except Exception:
                print('  -- Plots upload exception:', traceback.format_exc())
                ### XYZ save as csv?
        #except Exception as e:
        #    print('  ---', e)
        #    hexpath = ''
    pedestals.close()
    return hexpath

def multi_run_pedestals(state, BV_list):
    """
    Runs multiple pedestal runs. If the module is not live, the argument BV_list is full of Nones.
    """

    hexpath = ''
    for BV in BV_list:
        hexpath = run_pedestals(state, BV)
    if not state['-Debug-Mode-'] and len(BV_list) > 0 and hexpath != '':
        os.system(f'xdg-open {hexpath}_adc_mean.png')
        os.system(f'xdg-open {hexpath}_adc_stdd.png')

def trim_pedestals(state, BV):
    """
    """
    trimming = waiting_window(f"Trimming Pedestals (BV={BV})...", description='python3 pedestal_run.py [options...] && python3 pedestal_scan.py [options...] &&\npython3 vrefnoinv_scan.py [options...] && python3 vrefinv_scan.py [options...]')
    
    if state['-Debug-Mode-']:
        sleep(5)
    else:
        if state['-Live-Module-'] and BV is not None:
            state['ps'].outputOn()
            update_state(state, '-HV-Output-On-', True, 'green')
            state['ps'].setVoltage(float(BV))
        state['pc'].pedestal_run()
        state['pc'].pedestal_scan()
        state['pc'].vrefnoinv_scan()
        state['pc'].vrefinv_scan()
        state['-Pedestals-Trimmed-'] = True
        
    trimming.close()

def run_other_script(script, state, BV):
    """
    """
    running = waiting_window(f"Running {script}.py (BV={BV})...", description=f'python3 {script}.py [options...]')

    if state['-Debug-Mode-']:
        sleep(5)
    else:
        if state['-Live-Module-'] and BV is not None:
            state['ps'].outputOn()
            update_state(state, '-HV-Output-On-', True, 'green')
            state['ps'].setVoltage(float(BV))
        state['pc']._run_script(script)

    running.close()

def scan_pedestals(state, BV):
    """
    Runs pedestals and also performs a pedestal scan. This function is intented to be used at the 
    beginning of a test to configure the ROCs.
    """

    pedestals = waiting_window(f"Running and Scanning Pedestals (BV={BV})...", description='python3 pedestal_run.py [options...] && python3 pedestal_scan.py [options...]')

    if state['-Debug-Mode-']:
        sleep(5)
    else:
        if state['-Live-Module-'] and BV is not None:
            state['ps'].outputOn()
            update_state(state, '-HV-Output-On-', True, 'green')
            state['ps'].setVoltage(float(BV))
        state['pc'].pedestal_run()
        state['pc'].pedestal_scan()
        #if state['-Live-Module-']:
        #    state['ps'].outputOff()
        #    update_state(state, '-HV-Output-On-', False, 'black')
    pedestals.close()
    
def scan_vref(state, BV):
    """
    Runs vrefnoinv_scan and vrefinv_scan.  This function is intented to be used at the beginning of
    a test to configure the ROCs. 
    """
    
    vref = waiting_window(f"Scanning Vref Inv and NoInv (BV={BV})...", description='python3 vrefnoinv_scan.py [options...] && python3 vrefinv_scan.py [options...]')

    if state['-Debug-Mode-']:
        sleep(5)
    else:
        if state['-Live-Module-'] and BV is not None:
            state['ps'].outputOn()
            update_state(state, '-HV-Output-On-', True, 'green')
            state['ps'].setVoltage(float(BV))
        state['pc'].vrefnoinv_scan()
        state['pc'].vrefinv_scan()
        #if state['-Live-Module-']:
        #    state['ps'].outputOff()
        #    update_state(state, '-HV-Output-On-', False, 'black')
    vref.close()

def take_IV_curve(state, step=20):
    """
    Takes an IV curve automatically using the power supply object. The range is assumed to be 0-800V
    and the default step is 20V. If the RH argument is not zero, it prompts the user to enter the ambient
    humidity. We intend to query this automatically in the future but do not have the capability at the 
    moment.
    """
     
    connect_HV(state) # will do nothing if already connected
    RH, Temp = add_RH_T(state) # also adds RH,T to state dict
        
    curvew = waiting_window(f'Taking IV curve...')

    if state['-Debug-Mode-']:
       sleep(5)
    else:
        HVswitch_tripped = state['ps'].switch_state()
        if not HVswitch_tripped and configuration['HasHVSwitch']:
            print('>> HV switch not tripped - exiting. Please close box and try again.')
            return 'END'
        update_state(state, '-HV-Output-On-', True, 'green')
        maxV = 800 if configuration['HVWiresPolarization'] == 'Reverse' else -800
        if configuration['HVWiresPolarization'] == 'Forward':
            step = -step
        curve = state['ps'].takeIVold(maxV, step, RH, Temp) # IV curve is stored in the ps object so all curves can be plotted together
        update_state(state, '-HV-Output-On-', False, 'black')

        if configuration['HasLocalDB']:
            try:
                iv_upload(curve, state) # saves IV curve as pickle object and uploads to local db
            except Exception:
                print('  -- IV upload exception:', traceback.format_exc())
        else:
            iv_save(curve, state) # saves IV curve as pickle object
    curvew.close()
    return 'CONT'
        
def restart_services(state):
    """
    Restarts and checks the status of the DAQ Server, I2C Server, and DAQ Client services. It also
    updates the status LEDs accordingly.
    """

    if not (state['-DCDC-Connected-'] and state['-DCDC-Powered-'] and state['-Hexactrl-Powered-'] and state['-Hexactrl-Accessed-'] and state['-FW-Loaded-']):
        return
    
    starting = waiting_window("Restarting services on test stand...", title="Starting Services...", description='systemctl restart daq-server && systemctl restart i2c-server')
    if state['-Debug-Mode-']:
        sleep(5)
        services = True
    else:
        services = state['ts'].startservers()
    starting.close()
    update_state(state, '-DAQ-Server-', services, 'green' if services else 'black')
    update_state(state, '-I2C-Server-', services, 'green' if services else 'black')

    daq = waiting_window("Starting services on PC...", title="Starting Services...", description='systemctl restart daq-client')
    if state['-Debug-Mode-']:
        sleep(1)
        service = True
    else:
        service = state['pc'].restart_daq()
    daq.close()
    update_state(state, '-DAQ-Client-', service, 'green' if service else 'black')

    if not state['-Debug-Mode-']:
        state['pc'].initiated = False

def check_services(state):
    """
    Checks the status of the services and updates the status LEDs accordingly.
    """

    checking = waiting_window("Checking status of services...", title="Checking Services...")

    if state['-Debug-Mode-']:
        update_state(state, '-DAQ-Server-', True, 'green')
        update_state(state, '-I2C-Server-', True, 'green')
        update_state(state, '-DAQ-Client-', True, 'green')
    else:
    
        daq_server, i2c_server = state['ts'].statusservers()
        update_state(state, '-DAQ-Server-', daq_server, 'green' if daq_server else 'red')
        update_state(state, '-I2C-Server-', i2c_server, 'green' if i2c_server else 'red')

        daq_client = state['pc'].status_daq()
        update_state(state, '-DAQ-Client-', daq_client, 'green' if daq_client else 'red')
    
    checking.close()

def plot_IV_curves(state):
    """
    Plots all IV curves taken during this session. These curves are stored in the IVdata field of the
    power supply object.
    """

    if state['-Debug-Mode-']:
        pass
    else:

        plt.rcParams.update({'font.size': 10})

        fig, ax = plt.subplots(figsize=(8, 5))
        RHs = []
        for datadict in state['ps'].IVdata:
            data = datadict['data']
            plt.plot(data[:,1], data[:,2]*1000000., 'o-', label=f"{datadict['RH']}\% RH; {datadict['Temp']} deg C")
            RHs.append(str(datadict['RH']))

        ax.set_yscale('log')
        ax.set_title(f'{state["-Module-Serial-"]} module IV Curve Set {datadict["date"]}')
        ax.set_xlabel('Bias Voltage [V]')
        ax.set_ylabel(r'Leakage Current [$\mu$A]')
        ax.set_ylim(0.01, 100)
        ax.set_xlim(0, 800)
        ax.legend()
        os.system(f'mkdir -p {configuration["DataLoc"]}/{state["-Module-Serial-"]}')
        plt.savefig(f'{configuration["DataLoc"]}/{state["-Module-Serial-"]}/{state["-Module-Serial-"]}_IVset_{datadict["date"]}.png')
        plt.close(fig)
        RHstr = 'RH'+('_RH'.join(RHs))
        os.system(f'xdg-open {configuration["DataLoc"]}/{state["-Module-Serial-"]}/{state["-Module-Serial-"]}_IVset_{datadict["date"]}_{RHstr}.png')

