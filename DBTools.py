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
from PostgresTools import upload_PostgreSQL, fetch_PostgreSQL
import pandas as pd
import glob
import uproot3 as uproot
import asyncio
import asyncpg

#from InteractionGUI import add_RH_T
from hexmap.plot_summary import add_mapping
from hexmap.plot_summary import get_pad_id
from hexmap.plot_summary import create_masks

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

statusdict = {'Untaped': 0, 'Taped': 1, 'Assembled': 2, 'Backside Bonded': 3, 'Backside Encapsulated': 4, 'Frontside Bonded': 5, 'Bonds Reworked': 6, 'Frontside Encapsulated': 7}
    
def iv_save(datadict, modulename):
    """
    Takes the IV curve output dict and saves it to a pkl file. Returns the path to the pkl file.
    """
    
    os.system(f'mkdir -p {configuration["DataLoc"]}/{modulename}')
    with open(f'{configuration["DataLoc"]}/{modulename}/{modulename}_IVset_{datadict["date"]}_{datadict["time"]}_{datadict["RH"]}.pkl', 'wb') as datafile:
        pickle.dump(datadict, datafile)

    return f'{configuration["DataLoc"]}/{modulename}/{modulename}_IVset_{datadict["date"]}_{datadict["time"]}_{datadict["RH"]}_{datadict["Temp"]}.pkl'
        
def read_table(tablename, printall=False):
    """
    Reads the table in the local database of the given name. If printall is true, prints all rows in the db table. If printall
    is false, prints only the most recently uploaded row.
    """
    
    coro = fetch_PostgreSQL(tablename)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    if not printall:
        print(f' >> DBTools: Last upload to {tablename}: {result[0]}')
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

    norm_mask, calib_mask, cm0_mask, cm1_mask, nc_mask = create_masks(df_data)


    # count dead/noisy channels
    column = 'adc_stdd'
    zeros = df_data[column] == 0
    med_norm = df_data[column][norm_mask].median()
    mean_norm = df_data[column][norm_mask].mean()
    std_norm = df_data[column][norm_mask].std()
    noisy_limit = (2 if (column == 'adc_stdd' or column == 'adc_iqr') else 100)
    highval = (df_data[column] - med_norm) > noisy_limit
    # median + 2 adc counts as temporary check for high noise? we'll see how it goes

    count_bad_cells = np.sum((zeros) & (df_data["pad"] > 0)) + np.sum(highval & (df_data["pad"] > 0) & ~(calib_mask))
    list_dead_cells = df_data["pad"][zeros & (df_data["pad"] > 0)].tolist()
    list_noisy_cells = df_data["pad"][highval & (df_data["pad"] > 0) & ~(calib_mask)].tolist()

    print(count_bad_cells, list_dead_cells, list_noisy_cells)

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
        if state['-Pedestals-Trimmed-'] == True:
            comment += " pedestals trimmed"
        else:
            comment += f" pedestals trimmed at {state['-Pedestals-Trimmed-']}V"
    
    trimval = None if '-Pedestals-Trimmed-' not in state.keys() else (0. if state['-Pedestals-Trimmed-'] == True else state['-Pedestals-Trimmed-'])

    # build upload row list
    namekey = 'module_name' if '320-M' in modulename else 'hxb_name'
    db_upload_ped = {namekey: modulename,
                     'status': statusdict[state['-Module-Status-']],
                     'status_desc': state['-Module-Status-'],
                     'rel_hum': RH,
                     'temp_c': T,
                     'count_bad_cells': count_bad_cells,
                     'list_dead_cells': list_dead_cells,
                     'list_noisy_cells':list_noisy_cells,
                     'date_test': now.date(),
                     'time_test': now.time(),
                     'inspector': state['-Inspector-'],
                     'comment': comment,
                     'trim_bias_voltage': trimval,
                     'cell': df_data['pad'].tolist() # rename pad -> cell
                     }

    dfkeys = ['chip', 'channel', 'channeltype', 'adc_median', 'adc_iqr', 'tot_median', 'tot_iqr', 'toa_median', 'toa_iqr',
              'adc_mean', 'adc_stdd', 'tot_mean', 'tot_stdd', 'toa_mean', 'toa_stdd', 'tot_efficiency', 'tot_efficiency_error',
              'toa_efficiency', 'toa_efficiency_error', 'x', 'y']
    for key in dfkeys:
        db_upload_ped[key] = df_data[key].tolist()
    
    # if live module, add the bias voltage to the row list
    if 'BV' in runs[ind] and '320-M' in modulename:
        BV = int(runs[ind].split('_')[4].split('BV')[1].rstrip('\n '))
        db_upload_ped['bias_vol'] = BV
        db_upload_ped['list_disconnected_cells'] = [] ### XYZ fix
    elif '320-M' in modulename:
        BV = -1
        db_upload_ped['bias_vol'] = BV
        db_upload_ped['list_disconnected_cells'] = [] ### XYZ fix
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

    v1 = 600
    v2 = 800
    ratio = float(data[:,2][np.argwhere(data[:,0] == v2)] / data[:,2][np.argwhere(data[:,0] == v1)])
    
    db_upload_iv = {'module_name': modulename,
                    'rel_hum': str(RH),
                    'temp_c': str(Temp),
                    'status': statusdict[state['-Module-Status-']],
                    'status_desc': state['-Module-Status-'],
                    'grade': '',
                    'ratio_i_at_vs': ratio,
                    'ratio_at_vs': [float(v1), float(v2)],
                    'program_v': data[:,0].tolist(),
                    'meas_v': data[:,1].tolist(),
                    'meas_i': data[:,2].tolist(),
                    'meas_r': data[:,3].tolist(),
                    'date_test': datadict['datetime'].date(),
                    'time_test': datadict['datetime'].time(),
                    'inspector': state['-Inspector-'],
                    'comment': '' 
                    }
    
    # upload
    coro = upload_PostgreSQL(table_name = 'module_iv_test', db_upload_data = db_upload_iv)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded iv curve of {modulename}")
    read_table('module_iv_test')

def other_test_upload(state, test_name, BV, ind=-1):

    modulename = state['-Module-Serial-']
    RH = state['-Box-RH-']
    Temp = state['-Box-T-']

    now = datetime.now()
    trimval = None if '-Pedestals-Trimmed-' not in state.keys() else (0. if state['-Pedestals-Trimmed-'] == True else state['-Pedestals-Trimmed-'])

    runs = glob.glob(f'{configuration["DataLoc"]}/{modulename}/{test_name}/run_*')
    runs.sort()
    thisrun = runs[ind] # most recent run by default

    os.system(f'tar -czf tar_{test_name}_{thisrun.split("/")[-1][4:]}.tgz {thisrun}')
    with open(f'tar_{test_name}_{thisrun.split("/")[-1][4:]}.tgz',"rb") as f:
        tarfile = f.read()
    
    db_upload_other = {'module_name': modulename,
                       'status': statusdict[state['-Module-Status-']],
                       'status_desc': state['-Module-Status-'],
                       'rel_hum': str(RH),
                       'temp_c': str(Temp),
                       'bias_vol': BV,
                       'trim_bias_vol': trimval,
                       'date_test': now.date(),
                       'time_test': now.time(),
                       'inspector': state['-Inspector-'],
                       'comment': '',
                       'other_test_name': test_name,
                       'other_test_output': tarfile 
                   }
    
    # upload
    coro = upload_PostgreSQL(table_name = 'mod_hxb_other_test', db_upload_data = db_upload_other)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    os.system(f'rm tar_{test_name}_{thisrun.split("/")[-1][4:]}.tgz')

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
    
    # if live, must modify with bias voltage and conditions
    fixpath = glob.glob(f'{hexpath}*.png')
    if 'BV' in fixpath[0]:
        thistag = '_'.join(fixpath[0].split('/')[-1].split('_')[2:-2])
        hexpath = hexpath + '_' + thistag

    print(f" >> DBTools: Uploading pedestal plots of module {modulename} into database")

    # open hexmaps
    hexpaths = glob.glob(f'{hexpath}_*.png')
    for path in hexpaths:
        if 'mean' in path:
            with open(path, 'rb') as f:
                hexmean = f.read()
        elif 'stdd' in path:
            with open(path, 'rb') as f:
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

    trimval = None if '-Pedestals-Trimmed-' not in state.keys() else (0. if state['-Pedestals-Trimmed-'] == True else state['-Pedestals-Trimmed-'])

    # upload the plots
    #db_upload_plots = [modulename, hexmean, hexstdd, noise, pedestal, totnoise, state['-Inspector-'], comment]
    db_upload_plots = {'module_name': modulename,
                       'status': statusdict[state['-Module-Status-']],
                       'status_desc': state['-Module-Status-'],
                       'adc_mean_hexmap': hexmean,
                       'adc_std_hexmap': hexstdd,
                       'noise_channel_chip': noise,
                       'pedestal_channel_chip': pedestal,
                       'total_noise_chip': totnoise,
                       'trim_bias_voltage': trimval,
                       'inspector': state['-Inspector-'],
                       'comment_plot_test': comment
                       }

    print(db_upload_plots['module_name'], db_upload_plots['inspector'], db_upload_plots['comment_plot_test'])

    coro = upload_PostgreSQL(table_name = 'module_pedestal_plots', db_upload_data = db_upload_plots)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded pedestal plots of {modulename}")
    
    read_table('module_pedestal_plots')

def add_RH_T(state, force=False):
    """
    Adds RH, T inside box to the state dictionary as integers. Uses AirControl class which was implemented for CMU and is not
    general to all MACs. Automatic sensing is disabled by "HasRHSensor: false" in the configuration file.
    """
    
    RH = None
    Temp = None
    
    if ('-Box-RH-' not in state.keys() or '-Box-T-' not in state.keys()) or force: # only add once per testing session, except if you really need

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

        try:
            state['-Box-RH-'] = int(RH)
            state['-Box-T-'] = int(Temp)
        except ValueError:
            add_RH_T(state, force)
        
        return RH, Temp

    # if no update, return state values
    else:
        return state['-Box-RH-'], state['-Box-T-']
