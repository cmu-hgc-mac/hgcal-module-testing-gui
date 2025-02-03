import PySimpleGUI as sg
import numpy as np
import traceback
import time
import matplotlib.pyplot as plt
import pickle
from argparse import ArgumentParser
from datetime import datetime 
import os
from PostgresTools import upload_PostgreSQL, fetch_PostgreSQL, fetch_serial_PostgreSQL
import pandas as pd
import glob
import asyncio
import asyncpg
from datetime import datetime, date
from hexmap.plot_summary import add_mapping
from hexmap.plot_summary import get_pad_id
from hexmap.plot_summary import create_masks
from functools import reduce

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

# different versions of uproot for each OS =.=
if configuration['TestingPCOpSys'] == 'Centos7':
    import uproot3 as uproot
elif configuration['TestingPCOpSys'] == 'Alma9':
    import uproot
    
#statusdict = {'Untaped': 0, 'Taped': 1, 'Assembled': 2, 'Backside Bonded': 3, 'Backside Encapsulated': 4, 'Frontside Bonded': 5, 'Bonds Reworked': 6, 'Frontside Encapsulated': 7, 'Bolted': 8}
statusdict = {'Untaped': 0, 'Taped': 1, 'Assembled': 2, 'Backside Bonded': 3, 'Backside Encapsulated': 4, 'Completely Bonded': 5, 'Bonds Reworked': 6, 'Completely Encapsulated': 7, 'Bolted': 8}
    
def iv_save(datadict, state):
    """
    Takes the IV curve output dict and saves it to a pkl file. Returns the path to the pkl file.
    """

    moduleserial = state['-Module-Serial-']
    outdir = state['-Output-Subdir-']
    with open(f'{configuration["DataLoc"]}/{outdir}/{moduleserial}_IVset_{datadict["date"]}_{datadict["time"]}_{datadict["RH"]}.pkl', 'wb') as datafile:
        pickle.dump(datadict, datafile)

    return f'{configuration["DataLoc"]}/{outdir}/{moduleserial}_IVset_{datadict["date"]}_{datadict["time"]}_{datadict["RH"]}_{datadict["Temp"]}.pkl'
        
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
   
def fetch_pedestal(moduleserial, BV, trimBV, modulestatus):
    """
    Reads module_pedestal_test in the local database and returns the most recent test with the requested
    module serial number, bias voltage, and trimming conditions
    """

    coro = fetch_serial_PostgreSQL('module_pedestal_test', serial_remove_dashes(moduleserial))
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    runs = []
    
    for r in result:
        if r['bias_vol'] == BV and r['trim_bias_voltage'] == trimBV and r['status_desc'] == modulestatus:
            runs.append(r)

    return runs        
        
def fetch_iv(moduleserial, modulestatus, dry=True, roomtemp=True):
    """
    Reads module_iv_test or hxb_pedestal_test in the local database and returns the most recent test with the requested
    module serial number, bias voltage, and trimming conditions
    """

    coro = fetch_serial_PostgreSQL('module_iv_test', serial_remove_dashes(moduleserial))
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    runs = []
    
    for r in result:
        RH = float(r['rel_hum'])
        T = float(r['temp_c'])
        req1 = (RH < 8) if dry else (RH > 20)
        req2 = (T > 10 and T < 30) if roomtemp else (T < -20)
        if req1 and req2 and r['status_desc'] == modulestatus:
            runs.append(r)

    return runs        
        
def pedestal_upload(state, ind=-1):
    """
    Uploads the resultant data of a pedestal_run to the local database. The module serial and other information is read from the state dict. Unless
    otherwise specified, uploads the most recent run. Includes the RH and T from the pedestal run which are read from the state dict. 
    """
    
    moduleserial = state['-Module-Serial-']

    outdir = state['-Output-Subdir-']
    runs = glob.glob(f'{configuration["DataLoc"]}/{outdir}/pedestal_run/*')
    runs.sort()
    fname = runs[ind]+'/pedestal_run0.root'

    print(f" >> DBTools: Uploading pedestal run of {moduleserial} board from summary file {fname} into database")

    # Open the hex data ".root" file and turn the contents into a pandas DataFrame.
    f = uproot.open(fname)
    try:
        tree = f["runsummary"]["summary"]

        # different uproot functions for different OS =.=
        if configuration['TestingPCOpSys'] == 'Centos7':
            df_data = tree.pandas.df()
        elif configuration['TestingPCOpSys'] == 'Alma9':
            df_data = tree.arrays(library='pd')

    except:
        print(" -- DBTools: No tree found in pedestal file!")
        return 0

    density = moduleserial.split('-')[1][1]
    shape = moduleserial.split('-')[2][0]
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

    print(' >> DBTools: count bad cells', count_bad_cells, 'list dead', list_dead_cells, 'list noisy', list_noisy_cells)

    if configuration['HasRHSensor']:
        if '-Box-RH-' not in state.keys(): # should already exist
            add_RH_T(state)
        RH = str(state['-Box-RH-'])
        T = str(state['-Box-T-'])
    else:
        RH = 'N/A'
        T = 'N/A'

    now = datetime.now()

    comment = runs[-1].split('/')[-1]+' '+state['-Output-Subdir-'] # for now, comment is dir name of raw test results

    if '-Pedestals-Trimmed-' in state.keys():
        if state['-Pedestals-Trimmed-'] == True:
            comment += " pedestals trimmed"
        else:
            comment += f" pedestals trimmed at {state['-Pedestals-Trimmed-']}V"
    
    trimval = None if '-Pedestals-Trimmed-' not in state.keys() else (0. if state['-Pedestals-Trimmed-'] == True else float(state['-Pedestals-Trimmed-']))

    # build upload row list
    namekey = 'module_name' if '320-M' in moduleserial else 'hxb_name'
    db_upload_ped = {namekey: serial_remove_dashes(moduleserial),
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
    if 'BV' in runs[ind] and '320-M' in moduleserial:
        segments = runs[ind].split('_')
        for seg in segments:
            if 'BV' in seg:
                BV = int(seg.split('BV')[1].rstrip('\n '))
        db_upload_ped['bias_vol'] = BV
        db_upload_ped['list_disconnected_cells'] = [] ### XYZ fix
        if '-Leakage-Current-' in state.keys(): # add measured leakage current
            db_upload_ped['meas_leakage_current'] = state['-Leakage-Current-']
    elif '320-M' in moduleserial:
        BV = -1
        db_upload_ped['bias_vol'] = BV
        db_upload_ped['list_disconnected_cells'] = [] ### XYZ fix
    else:
        pass
    
    table = 'module_pedestal_test' if ('320-M' in moduleserial) else 'hxb_pedestal_test'
    
    # upload
    coro = upload_PostgreSQL(table_name = table, db_upload_data = db_upload_ped)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded pedestal run of {moduleserial}!")
    
    read_table(table)

def previous_pedestal_upload(path):

    runs = glob.glob(f'{path}/pedestal_run/*')
    runs.sort()
    for run in runs:

        moduleserial = run.removeprefix(configuration["DataLoc"]).split('/')[0]
        fname = run+'/pedestal_run0.root'

        df_data = df_from_path(run)
        if pedestal_exists(moduleserial, df_data):
            continue

        norm_mask, calib_mask, cm0_mask, cm1_mask, nc_mask = create_masks(df_data)

        column = 'adc_stdd'
        zeros = df_data[column] == 0
        med_norm = df_data[column][norm_mask].median()
        mean_norm = df_data[column][norm_mask].mean()
        std_norm = df_data[column][norm_mask].std()
        noisy_limit = (2 if (column == 'adc_stdd' or column == 'adc_iqr') else 100)
        highval = (df_data[column] - med_norm) > noisy_limit

        count_bad_cells = np.sum((zeros) & (df_data["pad"] > 0)) + np.sum(highval & (df_data["pad"] > 0) & ~(calib_mask))
        list_dead_cells = df_data["pad"][zeros & (df_data["pad"] > 0)].tolist()
        list_noisy_cells = df_data["pad"][highval & (df_data["pad"] > 0) & ~(calib_mask)].tolist()

        status = None
        date_test = None
        
        for key in statusdict.keys():
            if key.replace(' ', '_') in run:
                
                status = key
                datelist = [int(i) for i in run.removeprefix(configuration["DataLoc"]).split('/')[1].split('_')[-1].split('-')]
                date_test = date(datelist[0], datelist[1], datelist[2])
                
        # build upload row list
        namekey = 'module_name' if '320-M' in moduleserial else 'hxb_name'
        db_upload_ped = {namekey: serial_remove_dashes(moduleserial),
                         'status': statusdict[status],
                         'status_desc': status,
                         'count_bad_cells': count_bad_cells,
                         'list_dead_cells': list_dead_cells,
                         'list_noisy_cells':list_noisy_cells,
                         'date_test': date_test,
                         'cell': df_data['pad'].tolist() # rename pad -> cell
                         }

        dfkeys = ['chip', 'channel', 'channeltype', 'adc_median', 'adc_iqr', 'tot_median', 'tot_iqr', 'toa_median', 'toa_iqr',
                  'adc_mean', 'adc_stdd', 'tot_mean', 'tot_stdd', 'toa_mean', 'toa_stdd', 'tot_efficiency', 'tot_efficiency_error',
                  'toa_efficiency', 'toa_efficiency_error', 'x', 'y']
        for key in dfkeys:
            db_upload_ped[key] = df_data[key].tolist()

        # if live module, add the bias voltage to the row list                                                       
        if 'BV' in run and '320-M' in moduleserial:
            segments = run.split('_')
            for seg in segments:
                if 'BV' in seg:
                    BV = int(seg.split('BV')[1].rstrip('\n '))
                    db_upload_ped['bias_vol'] = BV
        elif '320-M' in moduleserial:
            BV = -1
            db_upload_ped['bias_vol'] = BV
        else:
            pass

        table = 'module_pedestal_test' if ('320-M' in moduleserial or '320M' in moduleserial) else 'hxb_pedestal_test'

        # upload                                                                                                                                       
        coro = upload_PostgreSQL(table_name = table, db_upload_data = db_upload_ped)
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(coro)
        
        print(f" >> DBTools: Uploaded pedestal run {run} for {moduleserial}!")
        
        #read_table(table)   
        
def pedestal_exists(moduleserial, df):
    
    if '320M' in moduleserial or '320-M' in moduleserial:
        coro = fetch_serial_PostgreSQL('module_pedestal_test', serial_remove_dashes(moduleserial))
    elif '320X' in moduleserial or '320-X' in moduleserial:
        coro = fetch_serial_PostgreSQL('hxb_pedestal_test', serial_remove_dashes(moduleserial))
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    runs = []

    for r in result:
        runs.append(r)

    for r in runs:
        if np.all(np.array(r['adc_stdd']) == np.array(df['adc_stdd'])):
           return True

    return False

def df_from_path(path):

    fname = path+'/pedestal_run0.root'
    moduleserial = path.removeprefix(configuration["DataLoc"]).split('/')[0]
    f = uproot.open(fname)
    try:
        tree = f["runsummary"]["summary"]

        # different uproot functions for different OS =.=
        if configuration['TestingPCOpSys'] == 'Centos7':
            df_data = tree.pandas.df()
        elif configuration['TestingPCOpSys'] == 'Alma9':
            df_data = tree.arrays(library='pd')
    except:
        print(" -- DBTools: No tree found in pedestal file!")
        return 0

    density = moduleserial.split('-')[1][1]
    shape = moduleserial.split('-')[2][0]
    hb_type = density+shape

    df_data = add_mapping(df_data, hb_type = hb_type)

    return df_data

def iv_upload(datadict, state):
    """
    Uploads the resultant data from an IV curve. Information including the module serial is read from the state dict, but the
    IV data itself is read from the output datadict.
    """
    
    moduleserial = state['-Module-Serial-']
    data = datadict['data']
    RH = datadict['RH']
    Temp = datadict['Temp'] 

    print(f" >> DBTools: Uploading (and saving) iv curve of {moduleserial}")
    
    # save iv as pkl file
    iv_save(datadict, state)
    
    #### XYZ what should be commented?
    #### XYZ status? etc.

    v1 = 600
    v2 = 800
    ratio = float(data[:,2][np.argwhere(data[:,0] == v2)] / data[:,2][np.argwhere(data[:,0] == v1)])
    
    db_upload_iv = {'module_name': serial_remove_dashes(moduleserial),
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
                    'comment': state['-Output-Subdir-'] 
                    }
    
    # upload
    coro = upload_PostgreSQL(table_name = 'module_iv_test', db_upload_data = db_upload_iv)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded iv curve of {moduleserial}")
    read_table('module_iv_test')

def other_test_upload(state, test_name, BV, ind=-1):

    moduleserial = state['-Module-Serial-']
    RH = state['-Box-RH-']
    Temp = state['-Box-T-']

    now = datetime.now()
    trimval = None if '-Pedestals-Trimmed-' not in state.keys() else (0. if state['-Pedestals-Trimmed-'] == True else float(state['-Pedestals-Trimmed-']))

    outdir = state['-Output-Subdir-']
    runs = glob.glob(f'{configuration["DataLoc"]}/{outdir}/{test_name}/run_*')
    runs.sort()
    thisrun = runs[ind] # most recent run by default

    os.system(f'tar -czf tar_{test_name}_{thisrun.split("/")[-1][4:]}.tgz {thisrun}')
    with open(f'tar_{test_name}_{thisrun.split("/")[-1][4:]}.tgz',"rb") as f:
        tarfile = f.read()
    
    db_upload_other = {'module_name': serial_remove_dashes(moduleserial),
                       'status': statusdict[state['-Module-Status-']],
                       'status_desc': state['-Module-Status-'],
                       'rel_hum': str(RH),
                       'temp_c': str(Temp),
                       'bias_vol': BV,
                       'trim_bias_vol': trimval,
                       'date_test': now.date(),
                       'time_test': now.time(),
                       'inspector': state['-Inspector-'],
                       'comment': state['-Output-Subdir-'],
                       'other_test_name': test_name,
                       'other_test_output': tarfile 
                   }

    if '320-M' in moduleserial:
        if '-Leakage-Current-' in state.keys(): # add measured leakage current
            db_upload_other['meas_leakage_current'] = state['-Leakage-Current-']

    # upload
    coro = upload_PostgreSQL(table_name = 'mod_hxb_other_test', db_upload_data = db_upload_other)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    os.system(f'rm tar_{test_name}_{thisrun.split("/")[-1][4:]}.tgz')

    print(f" >> DBTools: Uploaded other test of {moduleserial}")
    read_table('mod_hxb_other_test')

def plots_upload(state, ind=-1):
    """
    Uploads pedestal run plots to db for later viewing.
    """
    
    # define the path to the hexmap plots
    moduleserial = state['-Module-Serial-']
    outdir = state['-Output-Subdir-']
    hexpaths = glob.glob(f'{configuration["DataLoc"]}/{outdir}/{moduleserial}_run*_adc_mean.png')
    hexinds = [ int(hexpaths[i].split('/')[-1].split('_')[1].split('n')[1]) for i in range(len(hexpaths)) ]
    hexinds.sort()
    thisind = hexinds[ind]
    hexpath = f'{configuration["DataLoc"]}/{outdir}/{moduleserial}_run{thisind}'
    
    # if live, must modify with bias voltage and conditions
    fixpath = glob.glob(f'{hexpath}*.png')
    if 'BV' in fixpath[0]:
        thistag = '_'.join(fixpath[0].split('/')[-1].split('_')[2:-2])
        hexpath = hexpath + '_' + thistag

    print(f" >> DBTools: Uploading pedestal plots of module {moduleserial} into database")

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
    runs = glob.glob(f'{configuration["DataLoc"]}/{outdir}/pedestal_run/*')
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
                
    comment = f'run{thisind}'+' '+state['-Output-Subdir-']

    trimval = None if '-Pedestals-Trimmed-' not in state.keys() else (0. if state['-Pedestals-Trimmed-'] == True else float(state['-Pedestals-Trimmed-']))

    # upload the plots
    db_upload_plots = {'module_name': serial_remove_dashes(moduleserial),
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

    coro = upload_PostgreSQL(table_name = 'module_pedestal_plots', db_upload_data = db_upload_plots)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded pedestal plots of {moduleserial}")
    
    read_table('module_pedestal_plots')

def fetch_front_wirebond(moduleserial):

    coro = fetch_serial_PostgreSQL('front_wirebond', serial_remove_dashes(moduleserial))
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    runs = []
    for r in result:
        runs.append(r)

    return runs

def fetch_module_inspect(moduleserial):

    coro = fetch_serial_PostgreSQL('module_inspect', serial_remove_dashes(moduleserial))
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    runs = []
    for r in result:
        runs.append(r)

    return runs

def fetch_proto_inspect(moduleserial):

    moduleserial = moduleserial.replace('M', 'P', 1) # protomodule serial number

    coro = fetch_serial_PostgreSQL('proto_inspect', serial_remove_dashes(moduleserial))
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    runs = []
    for r in result:
        runs.append(r)

    return runs

def readout_info(moduleserial):

    lowBVruns = fetch_pedestal(moduleserial, 10, 300, 'Completely Encapsulated')
    midBVruns = fetch_pedestal(moduleserial, 300, 300, 'Completely Encapsulated')
    highBVruns = fetch_pedestal(moduleserial, 800, 300, 'Completely Encapsulated')

    # backwards compatibility
    if len(lowBVruns) < 1 or len(midBVruns) < 5 or len(highBVruns) < 2:
        lowBVruns = fetch_pedestal(moduleserial, 10, 300, 'Frontside Encapsulated')
        midBVruns = fetch_pedestal(moduleserial, 300, 300, 'Frontside Encapsulated')
        highBVruns = fetch_pedestal(moduleserial, 800, 300, 'Frontside Encapsulated')

    if len(lowBVruns) < 1 or len(midBVruns) < 5 or len(highBVruns) < 2:
        print(f' >> DBTools: not enough pedestal tests: lowBV {len(lowBVruns)} midBV {len(midBVruns)} high BV {len(highBVruns)}')
        return None
    
    badcell = set()
    
    # check unbonded channels - for now only works for LD modules
    if '320-MH' not in moduleserial:
        unbondedrun = lowBVruns[-1]
        noise = np.array(unbondedrun['adc_stdd'])
        cellid = np.array(unbondedrun['cell'])
        celltype = np.array(unbondedrun['channeltype'])
        norm_mask = (celltype == 0) & (cellid > 0)
        nc_mask = (celltype == 0) & (cellid < 0)
        calib_mask = celltype == 1
        med_nc = np.median(noise[nc_mask])
        uncon = np.abs(noise[norm_mask] - med_nc) < 1. # is 1 adc count enough?
        unconcells = cellid[norm_mask][uncon]
        for cell in unconcells:
            badcell.add(cell)
    else:
        unconcells = np.array([])
            
    # check dead channels
    ldeadcells = []
    for run in midBVruns[-5:]:
        noise = np.array(run['adc_stdd'])
        cellid = np.array(run['cell'])
        celltype = np.array(run['channeltype'])
        zeros = noise == 0
        norm_mask = (celltype == 0) & (cellid > 0)
        nc_mask = (celltype == 0) & (cellid < 0)
        calib_mask = celltype == 1
        deadcell = cellid[zeros & (norm_mask | calib_mask)]
        ldeadcells.append(deadcell)
    # Find intersection
    deadcells = reduce(np.intersect1d, ldeadcells)
    for cell in deadcells:
        badcell.add(cell)
    
    # check noisy channels
    lnoisycells = []
    for run in highBVruns[-2:]:
        noise = np.array(run['adc_stdd'])
        cellid = np.array(run['cell'])
        celltype = np.array(run['channeltype'])
        norm_mask = (celltype == 0) & (cellid > 0)
        nc_mask = (celltype == 0) & (cellid < 0)
        calib_mask = celltype == 1
        med_norm = np.median(noise[norm_mask])
        mean_norm = np.mean(noise[norm_mask])
        std_norm = np.std(noise[norm_mask])
        noisy_limit = 2
        # median + 2 adc counts as temporary check for high noise? we'll see how it goes
        noisycell = cellid[norm_mask | calib_mask][(noise[norm_mask | calib_mask] - med_norm) > noisy_limit]
        lnoisycells.append(noisycell)
        noisycells = reduce(np.union1d, lnoisycells)
    for cell in noisycells:
        badcell.add(cell)

    frontwirebond = fetch_front_wirebond(moduleserial)
    if len(frontwirebond) == 0:
        print(f' >> DBTools: no front wirebond info')
        return None
    
    groundedcells = np.array(frontwirebond[-1]['list_grounded_cells'])
    for cell in groundedcells:
        badcell.add(cell)

    print(f' >> DBTools: uncon {unconcells} dead {deadcells} noisy {noisycells} grounded {groundedcells}')
    badfrac = len(badcell) / len(cellid[norm_mask | calib_mask])
    return unconcells, deadcells, noisycells, groundedcells, badcell, badfrac

def iv_info(moduleserial):

    ivcurve = fetch_iv(moduleserial, 'Completely Encapsulated', dry=True, roomtemp=True)
    if len(ivcurve) < 1: # backwards compatibility
        ivcurve = fetch_iv(moduleserial, 'Frontside Encapsulated', dry=True, roomtemp=True)
    if len(ivcurve) < 1:
        print(f' >> DBTools: no IV tests')
        return None
    ivcurve = ivcurve[-1]
    v = np.array(ivcurve['program_v'])
    i = np.array(ivcurve['meas_i'])
    i_600v = i[v == 600]
    i_850v = i[v == 850]

    return i_600v[0], i_850v[0]

def assembly_info(moduleserial):

    moduleins = fetch_module_inspect(moduleserial)
    protoins = fetch_proto_inspect(moduleserial)

    if len(moduleins) < 1 or len(protoins) < 1:
        print(f' >> DBTools: no assembly info')
        return None

    return protoins[-1]['avg_thickness'], protoins[-1]['flatness'], protoins[-1]['x_offset_mu'], protoins[-1]['y_offset_mu'], protoins[-1]['ang_offset_deg'], moduleins[-1]['avg_thickness'], moduleins[-1]['flatness'], moduleins[-1]['x_offset_mu'], moduleins[-1]['y_offset_mu'], moduleins[-1]['ang_offset_deg']

def summary_upload(moduleserial, qc_summary):

    coro = upload_PostgreSQL(table_name = 'module_qc_summary', db_upload_data = qc_summary)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    print(f" >> DBTools: Uploaded to qc summary table for {moduleserial}")
    #ead_table('module_qc_summary')
    
def add_RH_T(state, force=False):
    """
    Adds RH, T inside box to the state dictionary as integers. Uses AirControl class which was implemented for CMU and is not
    general to all MACs. Automatic sensing is disabled by "HasRHSensor: false" in the configuration file.
    """
    
    RH = None
    Temp = None
    
    if ('-Box-RH-' not in state.keys() or '-Box-T-' not in state.keys()) or force: # only add once per testing session, except if you really need

        # if no automatic RH sensor, enter manually
        if not configuration['HasRHSensor'] or state['-Debug-Mode-']: 

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

def serial_add_dashes(moduleserial):

    if moduleserial.count('-') == 4:
        return moduleserial
    elif moduleserial.count('-') > 0 and moduleserial.count('-') < 4:
        raise ValueError

    dashedserial = moduleserial[0:3]+'-'+moduleserial[3:5]+'-'

    if '320-M' in dashedserial: # live module
        dashedserial += moduleserial[5:9]+'-'+moduleserial[9:11]+'-'+moduleserial[11:15]
    elif '320-X' in dashedserial: # hexaboard
        dashedserial +=	moduleserial[5:8]+'-'+moduleserial[8:10]+'-'+moduleserial[10:15]
    else:
        raise ValueError
        
    return dashedserial

def serial_remove_dashes(moduleserial):

    if moduleserial.count('-') == 0:
        return moduleserial
    elif moduleserial.count('-') > 0 and moduleserial.count('-') < 4:
        raise ValueError

    undashedserial = moduleserial[0:3]+moduleserial[4:6]

    if '320M' in undashedserial or '320P' in undashedserial: # live module
        undashedserial += moduleserial[7:11]+moduleserial[12:14]+moduleserial[15:19]
    elif '320X' in undashedserial: # hexaboard
        undashedserial += moduleserial[7:10]+moduleserial[11:13]+moduleserial[14:19]
    else:
        print(undashedserial)
        raise ValueError
        
    return undashedserial
