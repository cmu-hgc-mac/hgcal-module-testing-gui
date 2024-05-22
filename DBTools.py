import PySimpleGUI as sg
import numpy as np
import traceback
import time
import matplotlib.pyplot as plt
import pickle
from argparse import ArgumentParser
from datetime import datetime 
import os
#import psycopg2
import pandas as pd
import glob
import uproot3 as uproot
import asyncio
import asyncpg

#from InteractionGUI import add_RH_T
from hexmap.plot_summary import add_mapping
from hexmap.plot_summary import get_pad_id

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

def iv_save(datadict, modulename):
    """
    Takes the IV curve output dict and saves it to a pkl file. Returns the path to the pkl file.
    """
    
    os.system(f'mkdir -p {configuration["DataLoc"]}/{modulename}')
    with open(f'{configuration["DataLoc"]}/{modulename}/{modulename}_IVset_{datadict["date"]}_{datadict["time"]}_{datadict["RH"]}.pkl', 'wb') as datafile:
        pickle.dump(datadict, datafile)

    return f'{configuration["DataLoc"]}/{modulename}/{modulename}_IVset_{datadict["date"]}_{datadict["time"]}_{datadict["RH"]}.pkl'
        
def add_RH_T(state, force=False):
    """
    Adds RH, T inside box to the state dictionary as integers. Uses AirControl class which was implemented for CMU and is not
    general to all MACs. Automatic sensing is disabled by HasRHSensor: false in the configuration file.
    """
    
    RH = None
    Temp = None
    
    if '-Box-RH-' not in state.keys() or force: # only add once per testing session, except if you really need

        # if no automatic RH sensor, enter manually
        if not configuration['HasRHSensor']: 

            layout = [[sg.Text('Enter current humidity and temperature:', font=('Arial', 30))],
                      [sg.Input(s=3, key='-RH-'), sg.Text("% RH"), sg.Input(s=4, key='-Temp-'), sg.Text(" deg C")], [sg.Button('Enter')]]
            window = sg.Window(f"Module Test: Enter RH and Temp", layout, margins=(200,100))
        
            while True:
                event, values = window.read()
                if event == 'Enter' or event == sg.WIN_CLOSED:
                    RH = values['-RH-'].rstrip()
                    Temp = values['-Temp-'].rstrip()
                if RH is None or Temp is None:
                    continue
                else:
                    break

            window.close()

        # if automatic RH sensor, query for RH and T
        else:
            from AirControl import AirControl
            for i in range(10):
                controller = AirControl()
                try:
                    RH = controller.get_humidity()
                    Temp = controller.get_temperature()
                    break
                except Exception:
                    print('  -- RH/T exception:', traceback.format_exc())
                    print(f'  -- Trying again (attempt {i})')

            print(f'  >> RH/T: measured RH={RH}%; T={Temp}ºC')

        state['-Box-RH-'] = int(RH)
        state['-Box-T-'] = int(Temp)
    
        return RH, Temp

    # if no update, return state values
    else:
        return state['-Box-RH-'], state['-Box-T-']
