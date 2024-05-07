import numpy as np
import traceback
import time
import matplotlib.pyplot as plt
import pickle
from argparse import ArgumentParser
from datetime import datetime 
import os
#import psycopg2
from PostgresTools import upload_PostgreSQL, fetch_PostgreSQL
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
        
def read_table(tablename, printall=False):
    """
    Reads the table in the local database of the given name. If printall is true, prints all rows in the db table. If printall
    is false, prints only the most recently uploaded row.
    """
    
    coro = fetch_PostgreSQL(tablename)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    if not printall:
        print(f' >> DBTools: Last upload to {tablename}: {result[-1]}')
    else:
        print(f' >> DBTools: Printing all rows in {tablename}:')
        for r in result:
            print(r)
   

def pedestal_upload(state, ind=-1):
    """
    Uploads the resultant data of a pedestal_run to the local database. The module serial and other information is read from the state dict. Unless
    otherwise specified, uploads the most recent run. Includes the RH and T from the pedestal run which are read from the state dict. 
    """
    
    modulename = state['-Module-Serial-']
    
    runs = glob.glob(f'{configuration["DataLoc"]}/{modulename}/pedestal_run/*')
    runs.sort()
    fname = runs[ind]+'/pedestal_run0.root'

    print(runs[ind])

    print(f" >> DBTools: Uploading pedestal run of {modulename} board from summary file {fname} into database")

    # Open the hex data ".root" file and turn the contents into a pandas DataFrame.
    f = uproot.open(fname)
    try:
        tree = f["runsummary"]["summary"]
        df_data = tree.pandas.df()
    except:
        print(" -- DBTools: No tree found in pedestal file!")
        return 0

    density = modulename.split('-')[1][1]
    shape = modulename.split('-')[2][0]
    hb_type = density+shape

    df_data = add_mapping(df_data, hb_type = hb_type)

    count_dead_chan = 0
    list_dead_pad = []
    ##### XYZ fix dead chan/pad
    if configuration['HasRHSensor']:
        if '-Box-RH-' not in state.keys(): # should already exist
            add_RH_T(state)
        RH = str(state['-Box-RH-'])
        T = str(state['-Box-T-'])
    else:
        RH = 'N/A'
        T = 'N/A'

    now = datetime.now()

    comment = runs[-1].split('/')[-1] # for now, comment is dir name of raw test results

    if '-Pedestals-Trimmed-' in state.keys():
        if state['-Pedestals-Trimmed-']:
            comment += " pedestals trimmed"
    
    # build upload row list
    db_upload_ped = [modulename, RH, T, df_data['chip'].tolist(), df_data['channel'].tolist(), 
                     df_data['channeltype'].tolist(), df_data['adc_median'].tolist(), df_data['adc_iqr'].tolist(), 
                     df_data['tot_median'].tolist(), df_data['tot_iqr'].tolist(), df_data['toa_median'].tolist(), 
                     df_data['toa_iqr'].tolist(), df_data['adc_mean'].tolist(), df_data['adc_stdd'].tolist(), 
                     df_data['tot_mean'].tolist(), df_data['tot_stdd'].tolist(), df_data['toa_mean'].tolist(), 
                     df_data['toa_stdd'].tolist(), df_data['tot_efficiency'].tolist(), df_data['tot_efficiency_error'].tolist(), 
                     df_data['toa_efficiency'].tolist(), df_data['toa_efficiency_error'].tolist(), df_data['pad'].tolist(), 
                     #df_data['x'].tolist(), df_data['y'].tolist(), count_dead_chan, list_dead_pad, now.date(), now.time(), state['-Inspector-'], comment]
                     df_data['x'].tolist(), df_data['y'].tolist(), count_dead_chan, now.date(), now.time(), state['-Inspector-'], comment]

    # if live module, add the bias voltage to the row list
    if 'BV' in runs[ind] and '320-M' in modulename:
        BV = runs.split('BV').rstrip('\n ')
        db_upload_ped.insert(3, BV)
    elif '320-M' in modulename:
        BV = -1
        db_upload_ped.insert(3, BV)
    else:
        pass

    table = 'module_pedestal_test' if ('320-M' in modulename) else 'hxb_pedestal_test'

    # upload
    coro = upload_PostgreSQL(table_name = table, db_upload_data = db_upload_ped)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded pedestal run of {modulename}!")
    
    read_table(table)


def iv_upload(datadict, state):
    """
    Uploads the resultant data from an IV curve. Information including the module serial is read from the state dict, but the
    IV data itself is read from the output datadict.
    """
    
    modulename = state['-Module-Serial-']
    data = datadict['data']
    RH = datadict['RH']
    Temp = datadict['Temp'] 

    print(f" >> DBTools: Uploading (and saving) iv curve of {modulename}")
    
    # save iv as pkl file
    iv_save(datadict, modulename)
    
    #### XYZ what should be commented?
    #### XYZ status? etc.
    #### IV ratio at 600V, 800V
    #db_upload_iv = [modulename, str(RH), str(Temp), 0, '', '', 0., [0., 0.], data[:,0].tolist(), data[:,1].tolist(), data[:,2].tolist(), data[:,3].tolist(),
    #                datadict['datetime'].date(), datadict['datetime'].time(), state['-Inspector-'], '']
    db_upload_iv = [modulename, str(RH), str(Temp), 0, '', '', 0., data[:,0].tolist(), data[:,1].tolist(), data[:,2].tolist(), data[:,3].tolist(),
                    datadict['datetime'].date(), datadict['datetime'].time(), state['-Inspector-'], '']

    # upload
    coro = upload_PostgreSQL(table_name = 'module_iv_test', db_upload_data = db_upload_iv)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded iv curve of {modulename}")
    read_table('module_iv_test')
        
def plots_upload(state, ind=-1):
    """
    Uploads pedestal run plots to db for later viewing.
    """
    
    # define the path to the hexmap plots
    modulename = state['-Module-Serial-']
    hexpaths = glob.glob(f'{configuration["DataLoc"]}/{modulename}/{modulename}_run*_adc_mean.png')
    hexinds = [ int(hexpaths[i].split('/')[-1].split('_')[1].split('n')[1]) for i in range(len(hexpaths)) ]
    hexinds.sort()
    thisind = hexinds[ind]
    hexpath = f'{configuration["DataLoc"]}/{modulename}/{modulename}_run{thisind}'

    print(f" >> DBTools: Uploading pedestal plots of module {modulename} into database")

    # open hexmaps
    with open(f'{hexpath}_adc_mean.png', 'rb') as f:
        hexmean = f.read()
    with open(f'{hexpath}_adc_stdd.png', 'rb') as f:
        hexstdd = f.read()

    # find pedestal run dir
    runs = glob.glob(f'{configuration["DataLoc"]}/{modulename}/pedestal_run/*')
    runs.sort()
    dname = runs[ind] # should always be the same run


    # open plots from pedestal run dir
    noiseplots = glob.glob(dname+'/noise_vs_channel_chip*.png')
    noise = []
    for chip in noiseplots:
        with open(chip, 'rb') as f:
            noise.append(f.read())

    pedestalplots = glob.glob(dname+'/pedestal_vs_channel_chip*.png')
    pedestal = []
    for chip in pedestalplots:
        with open(chip, 'rb') as f:
            pedestal.append(f.read())
            
    totnoiseplots = glob.glob(dname+'/total_noise_chip*.png')
    totnoise = []
    for chip in totnoiseplots:
        with open(chip, 'rb') as f:
            totnoise.append(f.read())
                
    comment = f'run{thisind}'

    # upload the plots
    db_upload_plots = [modulename, hexmean, hexstdd, noise, pedestal, totnoise, state['-Inspector-'], comment]
    coro = upload_PostgreSQL(table_name = 'module_pedestal_plots', db_upload_data = db_upload_plots)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded pedestal plots of {modulename}")
    
    read_table('module_pedestal_plots')

def add_RH_T(state):
    """
    Adds RH, T inside box to the state dictionary as integers. Uses AirControl class which was implemented for CMU and is not
    general to all MACs. 
    """

    RH = None
    Temp = None
    if not configuration['HasRHSensor']:

        layout = [[sg.Text('Enter current humidity and temperature:', font=lgfont)], [sg.Input(s=3, key='-RH-'), sg.Text("% RH"), sg.Input(s=4, key='-Temp-'), sg.Text(" deg C")], [sg.Button('Enter')]]
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

    else:

        from AirControl import AirControl
        for i in range(10):
            controller = AirControl()
            try:
                RH = controller.get_humidity()
                T = controller.get_temperature()
                break
            except Exception:
                print('  -- RH/T exception:', traceback.format_exc())
                print(f'  -- Trying again (attempt {i})')

        print(f'  >> RH/T: measured RH={RH}%; T={T}ºC')

    state['-Box-RH-'] = int(RH)
    state['-Box-T-'] = int(T)

    return RH, T
