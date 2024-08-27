import PySimpleGUI as sg
from TrenzTestStand import TrenzTestStand
from CentosPC import CentosPC
from Keithley2410 import Keithley2410
import time
from InteractionGUI import *
import yaml
from datetime import datetime, timedelta
"""
This script creates and runs the main GUI window for the testing system. It firsts establishes a theme and sets some functions, 
then creates the GUI layout and then the GUI window. Once done, the script runs a loop which tracks and responds to the user's
interaction with the layout.
"""

# Load configuration file
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

from DBTools import add_RH_T
    
# Create theme
lgfont = ('Arial', 40)
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

# Base window layouts
# Module Setup fields for live modules only
livemoduleonly = [[sg.Text('Sensor Thickness: '),
                   sg.Radio('120 micron', 6, key='-120-', enable_events=True),
                   sg.Radio('200 micron', 6, key='-200-', default=True, enable_events=True),
                   sg.Radio('300 micron', 6, key='-300-', enable_events=True)],
                  [sg.Text('Baseplate Type: '),
                   sg.Radio('PCB', 5, key='-PCB-', enable_events=True),
                   sg.Radio("Carbon Fiber", 5, key='-CF-', default=True, enable_events=True),
                   sg.Radio("Copper-Tungsten", 5, key='-CuW-', enable_events=True)],
                  [sg.Checkbox('Preseries Module', default=True, key='-Preseries-', enable_events=True)]]

# Module Setup fields for hexaboards only
hexaboardonly = [[sg.Text('Hexaboard version: '), sg.Radio('V3', 4, key="-V3-", default=True, enable_events=True), sg.Radio('Production', 4, key="-Prod-", enable_events=True)],
                 [sg.Text("Hexaboard manufacturer: "), sg.Input(s=5, key='-HB-Manufacturer-', enable_events=True)]]

# Module Setup section which has both live module and hexaboard fields from above but initially hides them
modulesetup = [[sg.Radio('Live Module', 1, key="-IsLive-", enable_events=True), sg.Radio('Hexaboard', 1, key='-IsHB-', enable_events=True)],
               [sg.Text('Hexaboard Density: '), sg.Radio('Low', 2, key="-LD-", default=True, enable_events=True), sg.Radio('High', 2, key="-HD-", enable_events=True)],
               [sg.Text('Hexaboard shape: '), sg.Radio('Full', 3, key='-Full-', default=True, enable_events=True), sg.Radio("Top", 3, enable_events=True, key='-Top-'),
                sg.Radio("Bottom", 3, enable_events=True, key='-Bottom-'), sg.Radio("Left", 3, enable_events=True, key='-Left-'),
                sg.Radio("Right", 3, enable_events=True, key='-Right-'), sg.Radio("Five", 3, enable_events=True, key='-Five-')],
               [sg.pin(sg.Column(livemoduleonly, key='-LM-Menu-', visible=False))],
               [sg.pin(sg.Column(hexaboardonly, key='-HB-Menu-', visible=False))],
               [sg.Text("Module Index: "), sg.Input(s=5, key='-Module-Index-', enable_events=True)],
               [sg.Text("Module Serial Number: "), sg.Text('', key='-Module-Serial-')],
               [sg.Text("Test Stand IP: "), sg.Combo(configuration['TrenzHostname'], default_value=configuration['TrenzHostname'][0], key="-TrenzHostname-")],
               [sg.Text("Inspector: "), sg.Combo(configuration['Inspectors'], key="-Inspector-")],
               [sg.Text("Module Status: ", key="-Mod-Status-Text-"), sg.Combo(['                   '], key="-Module-Status-")], # blank replaced dynamically when live/hxb specified
               [sg.Button("Configure Test Stand"), sg.Button('Only IV Test'), sg.Text('', visible=False, key='-Display-Str-Left-')]]

# Select Tests fields only shown if able to bias the module
BVonly = [[sg.Text('Bias Voltage (per run): '),
           sg.Input(s=5, key='-Bias-Voltage-Pedestal1-'), sg.Input(s=5, key='-Bias-Voltage-Pedestal2-'),
           sg.Input(s=5, key='-Bias-Voltage-Pedestal3-'), sg.Input(s=5, key='-Bias-Voltage-Pedestal4-'),
           sg.Input(s=5, key='-Bias-Voltage-Pedestal5-'), sg.Input(s=5, key='-Bias-Voltage-Pedestal6-')]]

# Select Tests section
other_scripts = ['pedestal_scan', 'delay_scan', 'injection_scan', 'phase_scan', 'sampling_scan', 'toa_trim_scan', 
                 'toa_vref_scan_noinj', 'toa_vref_scan', 'vref2D_scan', 'vrefinv_scan', 'vrefnoinv_scan']
testsetup = [[sg.Text('Tests to run: ')],
             [sg.Checkbox('Trim Pedestals', key='-Trim-Pedestals-'), sg.Text('Bias Voltage: ', key='-Bias-Voltage-PedTrim-Text-'), sg.Input(s=5, key='-Bias-Voltage-PedTrim-')],
             [sg.Checkbox('Pedestal Run', key='-Pedestal-Run-'), sg.Text('Number of tests: '), sg.Input(s=2, key='-N-Pedestals-')],
             [sg.pin(sg.Column(BVonly, key='-BV-Menu-', visible=False))],
             [sg.Checkbox('Other Test Script:', key='-Other-Script-'), sg.Combo(other_scripts, key="-Other-Which-Script-"), 
              sg.Text('Bias Voltage: ', key='-Bias-Voltage-Other-Text-'), sg.Input(s=5, key='-Bias-Voltage-Other-')],
             [sg.Checkbox('Ambient IV Curve', key='-Ambient-IV-')],
             [sg.Checkbox('Dry IV Curve', key='-Dry-IV-'), sg.Text('Wait'), sg.Input(s=3, key='-DryIV-Wait-Time-'), sg.Text('min')],
             [sg.Button("Run Tests", disabled=True, key='Run Tests'), sg.Button("Restart Services", disabled=True), sg.Text('', visible=False, key='-Display-Str-Right-')]]

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

# Title bar that only works with newer python versions that Centos 7 can't use =.=
#titlebar = sg.Frame('', [[sg.Text("Module Testing GUI (WIP)", font=lgfont, text_color=cmured)],
#                         [sg.Image('cmu-wordmark-horizontal-r.resized.png')]])

# Layout version 2
leftcol = sg.Frame('', [[sg.Frame('Module Setup', modulesetup)], [sg.Checkbox('Debug Mode', key='-DEBUG-MODE-', enable_events=True, default=DEBUG_MODE), sg.Button("Close GUI")]])
rightcol = sg.Frame('', [[sg.Frame('Select Tests', testsetup)], [sg.Button("End Session")]])

layout = [[sg.Text("Module Testing GUI", font=lgfont, text_color=cmured)],
          [sg.Text("Carnegie Mellon University", text_color=cmured, font=('Arial', 20))],
          [leftcol, rightcol],
          [sg.Text(key='-EXPAND-', font='ANY 1', pad=(0, 0))],
          [sg.Frame('Status Bar', statusbar)]]

# Create the window
basewindow = sg.Window("Module Test: Start", layout, margins=(200,80), finalize=True, resizable=True)
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
    keys = ['-DEBUG-MODE-', '-IsLive-', '-IsHB-', '-LD-', '-HD-', '-Full-', '-Top-', '-Bottom-', '-Left-', '-Right-', '-Five-', '-120-', '-200-', '-300-',
            '-PCB-', '-CF-', '-CuW-', '-Preseries-', '-V3-', '-Prod-', '-HB-Manufacturer-', '-Module-Index-', '-TrenzHostname-', 'Configure Test Stand',
            'Only IV Test', '-Inspector-', '-Module-Status-', 'Close GUI']
    for key in keys:
        basewindow[key].update(disabled=(not enabled))

def enable_module_setup():
    toggle_module_setup(True)
def disable_module_setup():
    toggle_module_setup(False)

# Functions for enabling/disabling select tests fields
def toggle_ts_tests(enabled):
    keys = ['-Pedestal-Run-', '-N-Pedestals-', '-Bias-Voltage-Pedestal1-', '-Bias-Voltage-Pedestal2-', '-Bias-Voltage-Pedestal3-', '-Bias-Voltage-Pedestal4-', 
            '-Bias-Voltage-Pedestal5-', '-Bias-Voltage-Pedestal6-', 'Restart Services', '-Trim-Pedestals-', '-Bias-Voltage-PedTrim-', '-Other-Script-', 
            '-Bias-Voltage-Other-']
    for key in keys:
        basewindow[key].update(disabled=(not enabled))

    basewindow['-Bias-Voltage-PedTrim-'].update(value='300')
    basewindow['-Bias-Voltage-Other-'].update(value='300')

def enable_ts_tests():
    toggle_ts_tests(True)
def disable_ts_tests():
    toggle_ts_tests(False)

def toggle_iv_tests(enabled):
    keys = ['-Ambient-IV-', '-Dry-IV-', '-DryIV-Wait-Time-']
    for key in keys:
        basewindow[key].update(disabled=(not enabled))
        

def enable_iv_tests():
    toggle_iv_tests(True)
def disable_iv_tests():
    toggle_iv_tests(False)

# Function to clear the values of the tests in the Select Tests section
def clear_tests():
    for key in ['-Pedestal-Run-','-Trim-Pedestals-', '-Other-Script-', '-Ambient-IV-', '-Dry-IV-']:
        basewindow[key].update(False)
    for key in ['-N-Pedestals-', '-Bias-Voltage-Pedestal1-', '-Bias-Voltage-Pedestal2-', '-Bias-Voltage-Pedestal3-', '-Bias-Voltage-Pedestal4-', '-Bias-Voltage-Pedestal5-', '-Bias-Voltage-Pedestal\
6-', '-Bias-Voltage-PedTrim-', '-Bias-Voltage-Other-']:
        basewindow[key].update('')
    basewindow['-Bias-Voltage-PedTrim-'].update(value='300')
    basewindow['-Bias-Voltage-Other-'].update(value='300')
        
# Variables that will be set by the user and then used to create the module serial number
trenzhostname = ''
livemodule = None

ivonly_skip = False

empty = ''
majortype = ['X', 'L']
minortype = ['F', '2', 'C', '']
macserial = configuration['MACSerial']
moduleindex = ''
vendorserial = ''
moduleserial = ''
inspector = ''
modulestatus = ''

hxb_statuses = ['Untaped', 'Taped']
mod_statuses = ['Assembled', 'Backside Bonded', 'Backside Encapsulated', 'Frontside Bonded', 'Bonds Reworked', 'Frontside Encapsulated']

# Function to clear the values entered into the Module Setup section
def clear_setup():
    event, values = basewindow.read(timeout=10)
    moduleindex = ''
    basewindow['-Module-Index-'].update('')
    basewindow['-Inspector-'].update('')
    basewindow['-Module-Status-'].update('')

    if values['-IsLive-']:
        moduleserial = f'320-{empty.join(majortype)}-{empty.join(minortype)}-{macserial}-{moduleindex}'
    elif values['-IsHB-']:
        moduleserial = f'320-{empty.join(majortype)}-{empty.join(minortype)}-{vendorid}-{moduleindex}'
    else:
        moduleserial = ''
        
    basewindow['-Module-Serial-'].update(value=moduleserial)
        
# Create state dictionary 
current_state = {}

# Function to initialize values of state dictionary
def init_state():
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
    current_state['-Module-Serial-'] = moduleserial
    current_state['-Inspector-'] = inspector
    current_state['-Module-Status-'] = modulestatus
    
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
    time.sleep(2)
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

# Main window loop
while True:

    # In PySimpleGUI, this loop runs every time there is an 'event' i.e. a button is pressed or
    # a field is modified. It does _not_ run continually.
    
    event, values = basewindow.read()
    basewindow.maximize() # Fullscreen

    SetLED(basewindow, '-Debug-Mode-', 'green' if values['-DEBUG-MODE-'] else 'red')
    DEBUG_MODE = values['-DEBUG-MODE-']        
    
    # Check if live module
    if values['-IsLive-']:
        majortype[0] = 'M'
        SetLED(basewindow, '-Live-Module-', 'green')
        livemodule = True
    if values['-IsHB-']:
        majortype[0] = 'X'
        SetLED(basewindow, '-Live-Module-', 'black')
        livemodule = False
        
    # Change visibility of sections based on if live module or not
    basewindow['-LM-Menu-'].update(visible=values['-IsLive-'])
    basewindow['-HB-Menu-'].update(visible=values['-IsHB-'])
    basewindow['-Mod-Status-Text-'].update('Module Status:' if values['-IsLive-'] else 'Hexaboard Status:')
    thesestatuses = mod_statuses if values['-IsLive-'] else hxb_statuses
    if basewindow['-Module-Status-'].Values != thesestatuses:
        basewindow['-Module-Status-'].update(values=mod_statuses if values['-IsLive-'] else hxb_statuses)
    basewindow['-BV-Menu-'].update(visible=values['-IsLive-'])
    basewindow['-Bias-Voltage-PedTrim-Text-'].update(visible=values['-IsLive-'])
    basewindow['-Bias-Voltage-PedTrim-'].update(visible=values['-IsLive-'])
    basewindow['-Bias-Voltage-Other-Text-'].update(visible=values['-IsLive-'])
    basewindow['-Bias-Voltage-Other-'].update(visible=values['-IsLive-'])
    
    basewindow['Only IV Test'].update(disabled=(values['-IsHB-'] or basewindow['Configure Test Stand'].Widget['state'] == 'disabled'))
    basewindow['Close GUI'].update(disabled=(basewindow['Configure Test Stand'].Widget['state'] == 'disabled'))

    # Set characters in the module serial number
    if values['-LD-']: majortype[1] = 'L'
    if values['-HD-']: majortype[1] = 'H'

    if values['-Full-']: minortype[0] = 'F'
    if values['-Top-']: minortype[0] = 'T'
    if values['-Bottom-']: minortype[0] = 'B'
    if values['-Left-']: minortype[0] = 'L'
    if values['-Right-']: minortype[0] = 'R'
    if values['-Five-']: minortype[0] = '5'

    if values['-IsLive-']:
        if values['-120-']: minortype[1] = '1'
        if values['-200-']: minortype[1] = '2'
        if values['-300-']: minortype[1] = '3'
    
        if values['-PCB-']: minortype[2] = 'P'
        if values['-CF-']: minortype[2] = 'C'
        if values['-CuW-']: minortype[2] = 'W'
    
        if values['-Preseries-']: minortype[3] = 'X'
        if not values['-Preseries-']: minortype[3] = ''
        
    elif values['-IsHB-']:
        if values['-V3-']: minortype[1] = '0'
        if values['-V3-']: minortype[2] = '3'
        if values['-Prod-']: minortype[1] = '1'
        if values['-Prod-']: minortype[2] = '0'
        minortype[3] = ''
        
        vendorid = values['-HB-Manufacturer-'].rstrip().upper()

    # Only usign DCDC if LD Full
    if majortype[1] != 'L' or minortype[0] != 'F':
        basewindow['-DCDC-Connected-Txt-'].update("LV Cables Connected")
        basewindow['-DCDC-Powered-Txt-'].update("LV Output Powered")
    else:
        basewindow['-DCDC-Connected-Txt-'].update("DCDC Connected")
        basewindow['-DCDC-Powered-Txt-'].update("DCDC Powered")
        
        
    # Set the module index
    mind = values['-Module-Index-'].rstrip()
    serlen = 4 if values['-IsLive-'] else 5 # hexaboards have 5 digits, live modules 4
    if mind != '' and mind.isnumeric():
        if int(mind) >= 0 and int(mind) < 10**serlen and len(mind) == serlen:
            moduleindex = mind
        elif int(mind) >= 0 and int(mind) < 10**serlen and len(mind) < serlen:
            moduleindex = mind.zfill(serlen)
    else:
        moduleindex = ''    

    # Set and show module serial number 
    if values['-IsLive-']:
        moduleserial = f'320-{empty.join(majortype)}-{empty.join(minortype)}-{macserial}-{moduleindex}'
    elif values['-IsHB-']:
        moduleserial = f'320-{empty.join(majortype)}-{empty.join(minortype)}-{vendorid}-{moduleindex}'
        
    basewindow['-Module-Serial-'].update(value=moduleserial)
    if values['-Inspector-'] != '':
        inspector = values['-Inspector-']
    modulestatus = values['-Module-Status-']
        
    # Now, check for button presses
    # Configure test stand starts the Trenz assembly and startup process
    if event == "Configure Test Stand":

        # If live module or hexaboard isn't selected, skip
        if not values['-IsLive-'] and not values['-IsHB-']:
            show_string("Invalid Setup")
            continue
            
        # If module serial isn't defined well, skip
        if moduleindex == '' or values['-TrenzHostname-'].rstrip() == '':
            show_string("Invalid Setup")
            continue
        if values['-IsHB-'] and vendorid == '':
            show_string("Invalid Setup")
            continue
        if moduleserial == '':
            show_string("Invalid Setup")
            continue
            
        # Catch non-implemented denisities and geometries
        if (values['-HD-'] and not values['-Full-']) or (values['-LD-'] and (values['-Top-'] or values['-Bottom-'] or values['-Five-'])):
            show_string("Not Implemented")
            continue
        # HD Full implemented but not tested, so let's disable it for now
        
        trenzhostname = values['-TrenzHostname-'].rstrip()
        
        # Initialize test stand state dictionary
        init_state()
        # Disable the module setup section
        disable_module_setup()

        # Run initial checks on module, including pad resistance and power
        # If the checks show a problem, the function handles the ending of the test session
        outcode = initial_module_checks(current_state)
        
        if outcode == 'CONT':

            # If checks are good, assemble the parts and configure the test stand
            # If there is an issue, the function handles the ending of the test session
            outcode = configure_test_stand(current_state, trenzhostname)
            
            if outcode == 'CONT':

                # If the setup succeeded, enable the select tests section
                enable_ts_tests()
                if livemodule:
                    enable_iv_tests()
                basewindow['Run Tests'].update(disabled=False)
                basewindow['End Session'].update(disabled=False)

            # If there was an issue, after session end re-enable the module setup section
            elif outcode == 'END':
                enable_module_setup()

        # If there was an issue, after session end re-enable the module setup section
        elif outcode == 'END':
            enable_module_setup()

    # Only perform tests that involve the power supply and do not use the Trenz
    if event == 'Only IV Test':
        
        # If module serial isn't defined well, skip
        if values['-IsHB-']:
            show_string("Invalid Setup")
            continue
        if moduleindex == '':
            show_string("Invalid Setup")
            continue
        if moduleserial == '':
            show_string("Invalid Setup")
            continue


        # Catch non-implemented denisities and geometries
        if (values['-HD-'] and not values['-Full-']) or (values['-LD-'] and (values['-Top-'] or values['-Bottom-'] or values['-Five-'])):
            show_string("Not Implemented")
            continue
        
        # Initialize state dictionary
        init_state()
        # Disable module setup section
        disable_module_setup()

        # Check the leakage current briefly first to make sure it's not abnormal
        # This function also handles connecting the HV cable and instantiating
        # the power supply object, and handles errors as well.
        outcode = check_leakage_current(current_state)
        if outcode == 'CONT':

            # If there are no issues, enable the IV tests
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
        end_session(current_state)
        clear_tests()
        clear_setup()
        enable_module_setup()

        # if controlling box air automatically, turn off
        if configuration['HasRHSensor']:
            from AirControl import AirControl
            ac = AirControl()
            ac.set_air_off()
        
    # Run the selected tests
    if event == 'Run Tests':
        basewindow['Run Tests'].update(disabled=True)

        os.system(f'mkdir -p {configuration["DataLoc"]}/{moduleserial}')
        
        # Start by checking test stand services
        if current_state['-Hexactrl-Accessed-']:
            check_services(current_state)
            
            # If services not running properly, do not proceed with tests (but it does not automatically end session)
            if not (values['-FW-Loaded-'] and values['-DAQ-Server-'] and values['-I2C-Server-'] and values['-DAQ-Client-']):
                basewindow['Run Tests'].update(disabled=False)
                show_string("Error in Statuses", field="Right")
                continue

        # If running an electrical test, re-check just to make sure
        #if values['-Pedestal-Scan-'] or values['-Vref-Scan-'] or values['-Pedestal-Run-']:
        if values['-Trim-Pedestals-'] or values['-Pedestal-Run-'] or values['-Other-Script-']:
            if not (current_state['-DCDC-Powered-'] and current_state['-Hexactrl-Accessed-'] and current_state['-I2C-Server-'] and current_state['-DAQ-Client-']):
                basewindow['Run Tests'].update(disabled=False)
                show_string("Error in Statuses", field="Right")
                continue

        # add RH, T to state dict now
        # values also modified at the start of an IV curve
        RH, Temp = add_RH_T(current_state)

        # For trimming pedestals, check to make sure bias voltage is entered if needed and then run
        if values['-Trim-Pedestals-']:
            tpbv = values['-Bias-Voltage-PedTrim-'].rstrip()
            if (tpbv == '' or not tpbv.isnumeric()) and values['-IsLive-']:
                basewindow['Run Tests'].update(disabled=False)
                show_string("Invalid Instructions", field="Right")
                continue

            if values['-IsLive-']:
                trim_pedestals(current_state, tpbv)
            else:
                trim_pedestals(current_state, None)

        # If pedestal run, read settings and then run        
        if values['-Pedestal-Run-']:

            # Check to make sure number of runs is entered
            if values['-N-Pedestals-'].rstrip() == '' or not values['-N-Pedestals-'].rstrip().isnumeric():
                basewindow['Run Tests'].update(disabled=False)
                show_string("Invalid Instructions", field="Right")
                continue

            # Only allow up to six runs at a time
            nBVs = 0
            BVs = []
            nPedestals = int(values['-N-Pedestals-'].rstrip())                   
            if nPedestals > 6:
                nPedestals = 6

            # If live, read bias voltages into list 
            if values['-IsLive-']:
                for i in range(nPedestals):
                    thisval = values[f'-Bias-Voltage-Pedestal{i+1}-'].rstrip() 
                    if thisval != '' and thisval.isnumeric():
                        nBVs += 1
                        BVs.append(thisval)
            else:
                for i in range(nPedestals):
                    BVs.append(None)

            if (nBVs < nPedestals and values['-IsLive-']):
                basewindow['Run Tests'].update(disabled=False)
                show_string("Invalid Instructions", field="Right")
                continue

            # Run
            multi_run_pedestals(current_state, BVs)
            
        # For trimming pedestals, check to make sure bias voltage is entered if needed and then run
        if values['-Other-Script-']:
            osbv = values['-Bias-Voltage-Other-'].rstrip()
            if (osbv == '' or not osbv.isnumeric()) and values['-IsLive-']:
                basewindow['Run Tests'].update(disabled=False)
                show_string("Invalid Instructions", field="Right")
                continue
            
            script = values['-Other-Which-Script-']
            if values['-IsLive-']:
                run_other_script(script, current_state, osbv)
            else:
                run_other_script(script, current_state, None)

        # Take IV curve at ambient humidity
        if values['-Ambient-IV-']:

            take_IV_curve(current_state)
            plot_IV_curves(current_state)

        # If taking IV curve at zero humidity, must wait some time for humidity to drop
        if values['-Dry-IV-']:

            if values['-DryIV-Wait-Time-'] == '':
                time_to_wait = 15. if not DEBUG_MODE else 0.5
            elif values['-DryIV-Wait-Time-'] == '0':
                time_to_wait = 0.01
            else:
                time_to_wait = float(values['-DryIV-Wait-Time-'])
            final_dry_time = 60*(time_to_wait)

            # open dry air valve manually or automatically
            if not configuration['HasRHSensor']:
                from InteractionGUI import do_something_window
                do_something_window('Open dry air valve', 'Open')
            else:
                from AirControl import AirControl
                ac = AirControl()
                ac.set_air_on()
                            
            time.sleep(1)
                
            drytime = time.time()
            dry_date = datetime.now()
            finalIV_date = dry_date + timedelta(seconds=final_dry_time)
            finalIV_time = finalIV_date.isoformat().split('T')[1].split('.')[0]

        # Could run tests here

        # Wait until time passed, then run dry IV curve
        if values['-Dry-IV-']:

            time_to_wait = final_dry_time - (time.time() - drytime)
            from InteractionGUI import waiting_window
            wait = waiting_window(f'Waiting until {finalIV_time} to perform final IV')

            # module conditioning
            if current_state['-Live-Module-'] and not current_state['-Debug-Mode-'] and time_to_wait > 10:
                current_state['ps'].outputOff()
                update_state(current_state, '-HV-Output-On-', False, 'black')
                
            time.sleep(time_to_wait)

            if current_state['-Live-Module-'] and not current_state['-Debug-Mode-']:
                current_state['ps'].setVoltage(0.)

            wait.close()

            take_IV_curve(current_state)
            plot_IV_curves(current_state)

        # After tests run, check status of services
        if current_state['-Hexactrl-Accessed-']:
            check_services(current_state)    

        # Reset test values
        clear_tests()

        # Turn of HV output if live module
        if current_state['-Live-Module-'] and not current_state['-Debug-Mode-']:
            current_state['ps'].outputOff()
            update_state(current_state, '-HV-Output-On-', False, 'black')
            
        basewindow['Run Tests'].update(disabled=False)

        from InteractionGUI import waiting_window
        wait = waiting_window(f'Plots located in {configuration["DataLoc"]}/{moduleserial}')
        time.sleep(2)
        wait.close()
        
    # Restart the services and check to ensure success
    if event == 'Restart Services':
        restart_services(current_state)
        check_services(current_state)

    # This shouldn't ever happen. To kill the window, kill it from the terminal window where you ran it
    # or press the 'Close GUI' button.
    if event == sg.WIN_CLOSED:
        exit()

    # exit
    if event == 'Close GUI':
        exit()
        
