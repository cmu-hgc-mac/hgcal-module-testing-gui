import sys
import PySimpleGUI as sg
from KeithleyPowerSupply import KeithleyPowerSupply
from time import sleep, time
from InteractionGUI import *
import yaml
from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import tkinter as tk

"""
This script creates and runs the main GUI window for the multi-modules testing system.
"""

# direct print statements to both terminal and log file
class Tee:
    def __init__(self, file, stream):
        self.file = file
        self.stream = stream

    def write(self, message):
        self.file.write(message)
        self.stream.write(message)
        self.file.flush()
    def flush(self):
        self.file.flush()
        self.stream.flush()


# create and open new file for logging
now = datetime.now()
timestamp = now.strftime("%Y-%m-%d_%Hh%Mm%Ss")
folder_path = Path("logs")
filename = f"log_{timestamp}.log"

folder_path.mkdir(parents = True, exist_ok = True)
filepath = f'{folder_path}/{filename}'
logfile = open(filepath, 'w')

# redirect stdout to both console and file
sys.stdout = Tee(logfile, sys.__stdout__)

            
#prints current date and time
print(f' >> TestingGUIBase: start GUI {timestamp}')

#sets max output voltage to 500V
default_max_V = 500

# Load configuration file
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)
if 'FPGAHostname' not in configuration.keys() or 'FPGAType' not in configuration.keys():
    configuration['FPGAHostname'] = configuration['TrenzHostname']
    configuration['FPGAType'] = ['Trenz' for k in configuration['TrenzHostname']]

from DBTools import add_RH_T, readout_info, hexaboard_readout_info, iv_info, assembly_info, summary_upload, upload_bonding_instructions

# Create theme
lgfont = ('Arial', 2*int(configuration['DefaultFontSize']))
sg.set_options(font=("Arial", int(configuration['DefaultFontSize'])))

cmured = '#C41230'
bkggray = '#252525'
cmutheme = {'BACKGROUND': bkggray,
            'TEXT': '#FFFFFF', 
            'INPUT': bkggray,
            'TEXT_INPUT': '#FFFFFF',
            'SCROLL': cmured,
            'BUTTON': (cmured, bkggray),
            'PROGRESS': ('#000000', '#000000'),
            'BORDER': 1,
            'SLIDER_DEPTH': 0,
            'PROGRESS_DEPTH': 0,
            'COLOR_LIST': [cmured, '#FFFFFF', bkggray],
            'DESCRIPTION': ['Red', 'Blue', 'Grey', 'Vintage', 'Wedding']}
sg.LOOK_AND_FEEL_TABLE['cmutheme'] = cmutheme
sg.theme('cmutheme')

DEBUG_MODE = configuration['DebugMode']

# Functions for current state status indicators
def LEDIndicator(key=None, radius=30):
    return sg.Graph(canvas_size=(radius, radius),
                    graph_bottom_left=(-radius, -radius),
                    graph_top_right=(radius, radius),
                    pad=(0, 0), key=key, visible=True)

def SetLED(window, key, color, empty=False):
    graph = window[key]
    graph.erase()
    if not empty:
        graph.draw_circle((0, 0), 12, fill_color=color, line_color=color)
    else:
        graph.draw_circle((0, 0), 12, fill_color=None, line_color=color)


# Setup for the main layout
def setup_single_module(module_no):
    """Return a per-module layout (list of rows) with unique keys.
    """
    # Select Tests fields only shown if able to bias the module
    BVonly = [[sg.Text('Bias Voltage (per run): ')],
              [sg.Input(s=5, key=f'-Bias-Voltage-Pedestal1-{module_no}-'), 
               sg.Input(s=5, key=f'-Bias-Voltage-Pedestal2-{module_no}-'),
               sg.Input(s=5, key=f'-Bias-Voltage-Pedestal3-{module_no}-'), 
               sg.Input(s=5, key=f'-Bias-Voltage-Pedestal4-{module_no}-'),
               sg.Input(s=5, key=f'-Bias-Voltage-Pedestal5-{module_no}-'), 
               sg.Input(s=5, key=f'-Bias-Voltage-Pedestal6-{module_no}-')]]

    # Select Tests section
    other_scripts = ['pedestal_scan', 'delay_scan', 'injection_scan', 'phase_scan', 'sampling_scan', 'toa_trim_scan', 
                    'toa_vref_scan_noinj', 'toa_vref_scan', 'vref2D_scan', 'vrefinv_scan', 'vrefnoinv_scan', 'inputdac_scan']
    testsetup = [[sg.Text('Tests to run: ')],
                [sg.Checkbox('Standard Test Procedure', key=f'-Standard-Test-{module_no}-'), sg.Text('IV Max Voltage:'), sg.Input(s=5,key=f'-StandardIV-MaxV-{module_no}-')],
                [sg.Checkbox('Trim Pedestals', key=f'-Trim-Pedestals-{module_no}-'), sg.Text('Bias Voltage: ', key=f'-Bias-Voltage-PedTrim-Text-{module_no}-'), sg.Input(s=5, key=f'-Bias-Voltage-PedTrim-{module_no}-')],
                [sg.Checkbox('Pedestal Run', key=f'-Pedestal-Run-{module_no}-', enable_events=True), sg.Text('Number of tests: '), sg.Input(s=2, key=f'-N-Pedestals-{module_no}-', enable_events=True)],
                [sg.pin(sg.Column(BVonly, key=f'-BV-Menu-{module_no}-', visible=True))],
                [sg.Checkbox('Other Test Script:', key=f'-Other-Script-{module_no}-'), sg.Combo(other_scripts, key=f"-Other-Which-Script-{module_no}-")], 
                [sg.Text('Bias Voltage: ', key=f'-Bias-Voltage-Other-Text-{module_no}-'), sg.Input(s=5, key=f'-Bias-Voltage-Other-{module_no}-')],
                [sg.Checkbox('Ambient IV Curve', key=f'-Ambient-IV-{module_no}-'), sg.Text(' Max V:'), sg.Input(s=5,key=f'-AmbIV-MaxV-{module_no}-')],
                [sg.Checkbox('Dry IV Curve', key=f'-Dry-IV-{module_no}-'), sg.Text('Number of tests: '), sg.Input(s=2, key=f'-N-Dry-IV-{module_no}-')], 
                [sg.Text('                 '), sg.Checkbox('Bias in Wait Period', key=f'-Dry-Wait-Bias-{module_no}-'), sg.Text(' Max V:'), sg.Input(s=5,key=f'-DryIV-MaxV-{module_no}-')],
                [sg.Text('Wait Periods (minutes):'), sg.Input(s=3,key=f'-DryIV-Wait-Time-1-{module_no}-'), sg.Input(s=3,key=f'-DryIV-Wait-Time-2-{module_no}-'), sg.Input(s=3,key=f'-DryIV-Wait-Time-3-{module_no}-')]]

    # Module Setup section
    header = [
        [sg.Text("Scan QR Code: "),
         sg.Input(s=20, key=f'-Scanned-QR-Code-{module_no}-', enable_events=True),
         sg.Button('Clear', key=f'-Clear-Scanned-QR-Code-{module_no}-')],

        [sg.Text("Module Serial Number: "),
         sg.Text('', key=f'-Module-Serial-{module_no}-', size=(20, 1))],

        [sg.Text("Trophy Serial No.: "),
         sg.Input(s=15, key=f'-Trophy-Serial-{module_no}-', enable_events=True),
         sg.Button('Clear', key=f'-Trophy-Clear-{module_no}-')],
    ]

    # Full Module Setup section
    setup = header + [[sg.Frame('', testsetup, expand_x=True)]]

    return setup

module_frames = [
    sg.Frame(f'Module {i}', setup_single_module(i), expand_x=True, relief=sg.RELIEF_SUNKEN)
    for i in range(1, 4)
]

# arrage module frames
modules_stack = [[mf] for mf in module_frames]

# Outer frame for module setup section, including debug mode and skip checks
modulesetup = sg.Frame(
    '',
    [[module_frames[0], module_frames[1], module_frames[2]],
     [sg.Checkbox('Debug Mode', key='-DEBUG-MODE-', enable_events=True, default=DEBUG_MODE),
      sg.Checkbox('Skip Electrical Checks', key='-Skip-Checks-', enable_events=True, default=False),
      sg.Button("Close GUI"),
      sg.Push(),
      sg.Button("Configure Test Stand"), 
      sg.Button('Only IV Test'),
      sg.Button("Run Tests", disabled=True, key='Run Tests'), 
      sg.Button("Restart Services", disabled=True), 
      sg.Button("End Session", disabled=True), 
      sg.Text('', visible=False, key='-Display-Str-Right-')]],
    expand_x=True
)

# Status Bar version 2
sbcol1 = sg.Frame('', [[sg.Text("Debug Mode: "), sg.Push(), LEDIndicator(key='-Debug-Mode-')],
                       [sg.Text("Is Live Module: "), sg.Push(), LEDIndicator(key='-Live-Module-')],
                       [sg.Text("HV Cable Connected: "), sg.Push(), LEDIndicator(key='-HV-Connected-')]])
sbcol2 = sg.Frame('', [[sg.Text("Dark Box Closed: "), sg.Push(), LEDIndicator(key='-Box-Closed-')],
                       [sg.Text("HV Output Powered: "), sg.Push(), LEDIndicator(key='-HV-Output-On-')],
                       [sg.Text("DCDC Connected: ", key='-DCDC-Connected-Txt-'), sg.Push(), LEDIndicator(key='-DCDC-Connected-')]])
sbcol3 = sg.Frame('', [[sg.Text("DCDC Powered: ", key='-DCDC-Powered-Txt-'), sg.Push(), LEDIndicator(key='-DCDC-Powered-')],
                       [sg.Text("Trophy Connected: "), sg.Push(), LEDIndicator(key='-Trophy-Connected-')],
                       [sg.Text("Hexacontroller Connected: "), sg.Push(), LEDIndicator(key='-Hexactrl-Connected-')]])
sbcol4 = sg.Frame('', [[sg.Text("Hexacontroller Powered: "), sg.Push(), LEDIndicator(key='-Hexactrl-Powered-')],
                       [sg.Text("Hexacontroller Accessed: "), sg.Push(), LEDIndicator(key='-Hexactrl-Accessed-')],
                       [sg.Text("Firmware Loaded: "), sg.Push(), LEDIndicator(key='-FW-Loaded-')]])
sbcol5 = sg.Frame('', [[sg.Text("DAQ Server: "), sg.Push(), LEDIndicator(key='-DAQ-Server-')],
                       [sg.Text("I2C Server: "), sg.Push(), LEDIndicator(key='-I2C-Server-')],
                       [sg.Text("DAQ Client: "), sg.Push(), LEDIndicator(key='-DAQ-Client-')]])

statusbar = [[sbcol1, sbcol2, sbcol3, sbcol4, sbcol5]]


vers0 = sys.version_info[0]
vers1 = sys.version_info[1]
if vers0 == 3 and vers1 >= 9:
    logo = [sg.Image('hexmap/geometries/cmu-wordmark-horizontal-r-resized.png')]
elif vers0 == 3 and vers1 < 9:
    logo = [sg.Text("Carnegie Mellon University", text_color=cmured, font=('Arial', 20))]

layout = [[sg.Text("Multi-Modules Testing GUI", font=lgfont, text_color=cmured)], 
          logo + [sg.Push(), sg.Text("Inspector: "), sg.Combo(configuration['Inspectors'], key="-Inspector-"), sg.Text("Test Stand IP: "), sg.Combo(configuration['FPGAHostname'], default_value=configuration['FPGAHostname'][0], key="-FPGAHostname-")], 
          [modulesetup],
          [sg.Push(), sg.Button("Grade All Modules", key='-Grade-All-Modules-')],
          [sg.Text(key='-EXPAND-', font='ANY 1', pad=(0, 0))],
          [sg.Frame('Status Bar', statusbar)]]

# Create the window
basewindow = sg.Window("Module Test: Start", layout, margins=(200,80), finalize=True, resizable=True, return_keyboard_events=True)
# margins can be changed to suit the monitor; these are for a 1080p monitor
basewindow['-EXPAND-'].expand(True, True, True) # expand space between menus and status bar
event, values = basewindow.read(timeout=10)
basewindow.maximize()


# Set the initial colors and values of the status indicators
ledlist = ['-Debug-Mode-', '-Live-Module-', '-HV-Connected-', '-Box-Closed-', '-HV-Output-On-', '-DCDC-Connected-', '-DCDC-Powered-', '-Trophy-Connected-',
           '-Hexactrl-Connected-', '-Hexactrl-Powered-', '-Hexactrl-Accessed-', '-FW-Loaded-', '-DAQ-Server-', '-I2C-Server-', '-DAQ-Client-' ]

for led in ledlist:
    SetLED(basewindow, led, 'black', empty=True)
SetLED(basewindow, '-Debug-Mode-', 'green' if DEBUG_MODE else 'red')
    
# Functions for enabling/disabling module setup fields
def toggle_module_setup(enabled):
    keys = ['-DEBUG-MODE-', '-FPGAHostname-', 'Configure Test Stand',
            'Only IV Test', '-Inspector-', '-Skip-Checks-', 'Close GUI']
    for module_no in range(1, 4):
        keys += [f'-Scanned-QR-Code-{module_no}-', f'-Trophy-Serial-{module_no}-']
    for key in keys:
        basewindow[key].update(disabled=(not enabled))

def enable_module_setup():
    toggle_module_setup(True)
def disable_module_setup():
    toggle_module_setup(False)

# Functions for enabling/disabling select tests fields
def toggle_ts_tests(enabled, valid_modules):
    keys = ['Restart Services', 'Run Tests']

    for module_no in valid_modules:
        keys += [f'-Pedestal-Run-{module_no}-', f'-N-Pedestals-{module_no}-', f'-Bias-Voltage-Pedestal1-{module_no}-', f'-Bias-Voltage-Pedestal2-{module_no}-', f'-Bias-Voltage-Pedestal3-{module_no}-', f'-Bias-Voltage-Pedestal4-{module_no}-',
                 f'-Bias-Voltage-Pedestal5-{module_no}-', f'-Bias-Voltage-Pedestal6-{module_no}-', f'-Trim-Pedestals-{module_no}-', f'-Bias-Voltage-PedTrim-{module_no}-', f'-Other-Script-{module_no}-',
                 f'-Bias-Voltage-Other-{module_no}-', f'-Standard-Test-{module_no}-']

    for key in keys:
        basewindow[key].update(disabled=(not enabled))

        basewindow[f'-Bias-Voltage-PedTrim-{module_no}-'].update(value='300')
        basewindow[f'-Bias-Voltage-Other-{module_no}-'].update(value='300')

def enable_ts_tests(valid_modules):
    toggle_ts_tests(True, valid_modules)
def disable_ts_tests(valid_modules=[1, 2, 3]):
    toggle_ts_tests(False, valid_modules)

def toggle_iv_tests(enabled, is_live_modules):
    keys = []
    for module_no in is_live_modules:
        keys += [f'-Ambient-IV-{module_no}-', f'-Dry-IV-{module_no}-', f'-N-Dry-IV-{module_no}-', f'-Dry-Wait-Bias-{module_no}-', f'-DryIV-Wait-Time-1-{module_no}-', f'-DryIV-Wait-Time-2-{module_no}-', f'-DryIV-Wait-Time-3-{module_no}-', f'-DryIV-MaxV-{module_no}-', f'-AmbIV-MaxV-{module_no}-', f'-StandardIV-MaxV-{module_no}-']
    for key in keys:
        basewindow[key].update(disabled=(not enabled))
        
def enable_iv_tests(is_live_modules):
    toggle_iv_tests(True, is_live_modules)
def disable_iv_tests(is_live_modules=[1, 2, 3]):
    toggle_iv_tests(False, is_live_modules)

# Function to clear the values of the tests in the Select Tests section
def clear_tests():
    update_false_keys = []
    update_empty_keys = []

    for module_no in range(1, 4):
        update_false_keys += [f'-Standard-Test-{module_no}-', f'-Pedestal-Run-{module_no}-', f'-Trim-Pedestals-{module_no}-', f'-Other-Script-{module_no}-', f'-Ambient-IV-{module_no}-', f'-Dry-IV-{module_no}-']
        for key in update_false_keys:
            basewindow[key].update(False)
        update_empty_keys += [f'-N-Pedestals-{module_no}-', f'-Bias-Voltage-Pedestal1-{module_no}-', f'-Bias-Voltage-Pedestal2-{module_no}-', f'-Bias-Voltage-Pedestal3-{module_no}-', f'-Bias-Voltage-Pedestal4-{module_no}-', f'-Bias-Voltage-Pedestal5-{module_no}-', f'-Bias-Voltage-Pedestal6-{module_no}-', f'-Bias-Voltage-PedTrim-{module_no}-', f'-Bias-Voltage-Other-{module_no}-', f'-DryIV-MaxV-{module_no}-', f'-AmbIV-MaxV-{module_no}-', f'-StandardIV-MaxV-{module_no}-']
        for key in update_empty_keys:
            basewindow[key].update('')

        basewindow[f'-Bias-Voltage-PedTrim-{module_no}-'].update(value='300')
        basewindow[f'-Bias-Voltage-Other-{module_no}-'].update(value='300')
        basewindow[f'-DryIV-MaxV-{module_no}-'].update(value=f'{default_max_V}')
        basewindow[f'-AmbIV-MaxV-{module_no}-'].update(value=f'{default_max_V}')
        basewindow[f'-StandardIV-MaxV-{module_no}-'].update(value=f'{default_max_V}')
        basewindow[f'-BV-Menu-{module_no}-'].update(visible=True)

def exit_tests():

    # After tests run, check status of services
    if current_state['-Hexactrl-Accessed-']:
        check_services(current_state)

    # Reset test values
    clear_tests()

    # Turn off HV output if live module
    if current_state['-Live-Module-'] and not current_state['-Debug-Mode-']:
        current_state['ps'].outputOff()
        update_state(current_state, '-HV-Output-On-', False, 'black')
        
    basewindow['Run Tests'].update(disabled=False)
   
    
# Variables that will be set by the user and then used to create the module serial number
fpgahostname = ''
livemodule = None

ivonly_skip = False

empty = ''
majortype = ['X', 'L']
minortype = ['F', '2', 'C', '']
macserial = configuration['MACSerial'] if configuration['MACSerial'] in ['CM', 'SB', 'TT', 'NT', 'IH', 'TI'] else ''
moduleindex = ''
vendorserial = ''
moduleserial = ''
inspector = ''
modulestatus = ''

hxb_statuses = ['Untaped', 'Taped']
#mod_statuses = ['Assembled', 'Backside Bonded', 'Backside Encapsulated', 'Frontside Bonded', 'Bonds Reworked', 'Frontside Encapsulated', 'Bolted']
mod_statuses = ['Assembled', 'Backside Bonded', 'Backside Encapsulated', 'Completely Bonded', 'Bonds Reworked', 'Completely Encapsulated', 'Bolted']

# Function to clear the values entered into the Module Setup section
def clear_setup(basewindow=basewindow):
    for module_no in range(1, 4):
        basewindow[f'-Scanned-QR-Code-{module_no}-'].update(value='')
        basewindow[f'-Module-Serial-{module_no}-'].update(value='')
        basewindow[f'-Trophy-Serial-{module_no}-'].update(value='')
        
# Create state dictionary 
current_state = {}

# Function to initialize values of state dictionary
def init_state(valid_modules):
    for led in ledlist:
        if led == '-Live-Module-':
            current_state[led] = livemodule
        elif led == '-Debug-Mode-':
            current_state[led] = DEBUG_MODE
        else:
            current_state[led] = False
            SetLED(basewindow, led, 'black')

    current_state.pop('-Pedestals-Trimmed-', None)
    current_state['ts'] = None
    current_state['pc'] = None
    current_state['ps'] = None
    current_state['basewindow'] = basewindow
    current_state['-Inspector-'] = inspector
    
# Update the value of a field in the state dict and update LED color if exists
def update_state(state, field, val, color=None):
    state[field] = val
    if field[0] == '-':
        assert color is not None
        SetLED(basewindow, field, color)

def show_string(string, field='Left'):
    basewindow[f'-Display-Str-{field}-'].update(string)
    basewindow[f'-Display-Str-{field}-'].update(visible=True)
    basewindow.refresh()
    sleep(2)
    basewindow[f'-Display-Str-{field}-'].update(visible=False)
    basewindow.refresh()

        
# Initial setup
event, values = basewindow.read(timeout = 10)
disable_ts_tests()
disable_iv_tests()
basewindow['Run Tests'].update(disabled=True)
basewindow['End Session'].update(disabled=True)
clear_tests()
clear_setup()

# Re-assign focus to entry fields when clicked (to avoid focus issues in tkinter and Alma9) 
root: tk.Tk = basewindow.TKroot
def on_entry_click(event):
    try:
        root.grab_release()
    except tk.TclError:
        pass 
    event.widget.after_idle(lambda w=event.widget: w.focus_set())
root.bind_class('Entry', '<Button-1>', on_entry_click, add='+')



# Main window loop
while True:

    # In PySimpleGUI, this loop runs every time there is an 'event' i.e. a button is pressed or
    # a field is modified. It does _not_ run continually.
    
    event, values = basewindow.read()
   
   # Update debug mode
    SetLED(basewindow, '-Debug-Mode-', 'green' if values['-DEBUG-MODE-'] else 'red')
    DEBUG_MODE = values['-DEBUG-MODE-']       

    # Set and show the valid module serial number via QR code scanner
    if values[f'-Scanned-QR-Code-1-'] != '':
        scannedcode = values[f'-Scanned-QR-Code-1-'].rstrip()
        module_no = 1
        update_Module_Serial(basewindow, module_no, scannedcode, current_state)
        
    if values[f'-Scanned-QR-Code-2-'] != '':
        scannedcode = values[f'-Scanned-QR-Code-2-'].rstrip()
        module_no = 2
        update_Module_Serial(basewindow, module_no, scannedcode, current_state)

    if values[f'-Scanned-QR-Code-3-'] != '':
        scannedcode = values[f'-Scanned-QR-Code-3-'].rstrip()
        module_no = 3
        update_Module_Serial(basewindow, module_no, scannedcode, current_state)
    

    # Clear QR code input
    if event.startswith('-Clear-'):
        module_no = event.split('-')[-2]
        basewindow[f'-Scanned-QR-Code-{module_no}-'].update(value='')
        basewindow[f'-Module-Serial-{module_no}-'].update(value='')
        SetLED(basewindow, '-Live-Module-', 'black')
        basewindow[f'-BV-Menu-{module_no}-'].update(visible=True)

    if event.startswith('-Trophy-Clear-'):
        module_no = event.split('-')[-2]
        basewindow[f'-Trophy-Serial-{module_no}-'].update(value='')


    # Now, check for button presses
    # Configure test stand starts the FPGA assembly and startup process
    if event == "Configure Test Stand":

        # check if there exists valid input
        valid_modules = []
        # list of live modules
        is_live_modules = []

        for module_no in range(1, 4):
            if basewindow[f'-Module-Serial-{module_no}-'].get() != '':
                # '-Module-Serial-{module_no}-' only updates when the serial is valid
                valid_modules.append(module_no)
                module_type, valid = check_serial(basewindow[f'-Module-Serial-{module_no}-'].get())
                if module_type == 'live':
                    is_live_modules.append(module_no)

        if not valid_modules:
            show_string("Invalid Setup")
            continue    # if no valid input, do nothing
        
        if is_live_modules:
            livemodule = True

        # list of hexaboards
        is_hxb_modules = list(set(valid_modules) - set(is_live_modules))

        # check if module or hexaboard is in database to prevent incorrect QR code entries
        if configuration['HasLocalDB']:
            from PostgresTools import module_exists, hxb_exists
            for module_no in is_live_modules:
                moduleserial = basewindow[f'-Module-Serial-{module_no}-'].get()
                if not module_exists(moduleserial):
                    ret = do_something_window("Module not in local database, continue?", "Test Anyway", can_end=True)
                    if ret == 'END':
                        continue
            for module_no in is_hxb_modules:
                moduleserial = basewindow[f'-Module-Serial-{module_no}-'].get()
                if not hxb_exists(moduleserial):
                    ret = do_something_window("Hexaboard not in local database, continue?", "Test Anyway", can_end=True)
                    if ret == 'END':
                        continue

        fpgahostname = values['-FPGAHostname-'].rstrip()

        # print out the testing module serial
        for module_no in is_live_modules:
            moduleserial = basewindow[f'-Module-Serial-{module_no}-'].get()
            print(f' >> TestingGUIBase: Beginning test of live module: {moduleserial}')
        for module_no in is_hxb_modules:
            moduleserial = basewindow[f'-Module-Serial-{module_no}-'].get()
            print(f' >> TestingGUIBase: Beginning test of hexaboard: {moduleserial}')
    
        # Initialize test stand state dictionary
        init_state(valid_modules)
        current_state['-Skip-Checks-'] = values['-Skip-Checks-']
        for module_no in valid_modules:
            current_state[f'-Trophy-Serial-{module_no}-'] = values[f'-Trophy-Serial-{module_no}-']
        # Disable the module setup section
        disable_module_setup()
        
        # Run initial checks on module, including pad resistance and power
        # If the checks show a problem, the function handles the ending of the test session
        for module_no in valid_modules:
            outcode = initial_module_checks(current_state, module_no)
            # If there was an issue, after session end re-enable the module setup section and break the loop
            if outcode == 'END':
                enable_module_setup()
                break

        # figure out FPGA type based on chosen hostname
        for iN in range(len(configuration['FPGAHostname'])):
            if configuration['FPGAHostname'][iN] == fpgahostname:
                fpgatype = configuration['FPGAType'][iN]
        current_state['-FPGA-Type-'] = fpgatype

        # If checks are good, assemble the parts and configure the test stand
        # If there is an issue, the function handles the ending of the test session
        for module_no in valid_modules:
            outcode = configure_test_stand(current_state, fpgahostname, module_no)
            # If there was an issue, after session end re-enable the module setup section and break the loop
            if outcode == 'END':
                enable_module_setup()
                break
        
        # If the setup succeeded, enable the select tests section
        enable_ts_tests(valid_modules)
        if livemodule:
            enable_iv_tests(is_live_modules)
        basewindow['Run Tests'].update(disabled=False)
        basewindow['End Session'].update(disabled=False)


    # Only perform tests that involve the power supply and do not use the FPGA
    if event == 'Only IV Test':

        # check if there exists valid input
        is_live_modules = []

        for module_no in range(1, 4):
            if basewindow[f'-Module-Serial-{module_no}-'].get() != '':
                # '-Module-Serial-{module_no}-' only updates when the serial is valid
                module_type, valid = check_serial(basewindow[f'-Module-Serial-{module_no}-'].get())
                if module_type == 'live':
                    is_live_modules.append(module_no)

        if not is_live_modules:
            show_string("Invalid Setup")
            continue    # if no valid input, do nothing
        

        # print out the testing module
        for module_no in is_live_modules:
            moduleserial = basewindow[f'-Module-Serial-{module_no}-'].get()
            print(f' >> TestingGUIBase: Beginning IV-only test for live module {module_no}: {moduleserial}')

        # Initialize state dictionary
        init_state()
        current_state['-Skip-Checks-'] = values['-Skip-Checks-']
        # Disable module setup section
        disable_module_setup()

        # Check the leakage current briefly first to make sure it's not abnormal
        # This function also handles connecting the HV cable and instantiating
        # the power supply object, and handles errors as well.
        outcode = check_leakage_current(current_state)

        """check_leakage_current() might need to be modified to handle multi-modules case"""

        if outcode == 'CONT':
            # If there are no issues, enable the IV tests
            close_box(current_state)
            enable_iv_tests()
            basewindow['Run Tests'].update(disabled=False)
            basewindow['End Session'].update(disabled=False)

        # If there was an issue, re-enable module setup section after ending session
        elif outcode == 'END':
            enable_module_setup()

    # If done testing, disable select tests section, end the session, and re-enable module setup section
    if event == 'End Session':
        basewindow['Run Tests'].update(disabled=True)
        basewindow['End Session'].update(disabled=True)
        disable_ts_tests()
        disable_iv_tests()
        for module_no in valid_modules:
            end_session(current_state, module_no)
        clear_tests()
        clear_setup()
        enable_module_setup()

        # if controlling box air automatically, turn off
        if configuration['HasRHSensor'] and not current_state['-Debug-Mode-']:
            from AirControl import AirControl
            ac = AirControl()
            ac.set_air_off()
            ac.close()
    
    # Run the selected tests
    if event == 'Run Tests':
        print(' >> TestingGUIBase: I have no idea how to run tests')
        pass

    # Restart the services and check to ensure success
    if event == 'Restart Services':
        restart_services(current_state)
        check_services(current_state)

    # Grade the module/modules:
    if event == '-Grade-All-Modules-':
        for module_no in range(1, 4):
            handle_grade_module(basewindow, module_no)


    # This shouldn't ever happen. To kill the window, kill it from the terminal window where you ran it
    # or press the 'Close GUI' button.
    if event == sg.WIN_CLOSED:
        exit()

    # exit
    if event == 'Close GUI':
        exit()

#Closes .txt file         
logfile.close