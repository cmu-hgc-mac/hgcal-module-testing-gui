import numpy as np
import time
import matplotlib.pyplot as plt
import pickle
from argparse import ArgumentParser
from datetime import datetime 
import os
#import psycopg2
from postgres_tools_testing import upload_PostgreSQL, fetch_PostgreSQL
import pandas as pd
import glob
import uproot3 as uproot
import asyncio
import asyncpg

from hexmap.plot_summary import add_mapping
from hexmap.plot_summary import get_pad_id

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

def iv_save(datadict, modulename):

    os.system(f'mkdir -p {configuration["DataLoc"]}/{modulename}')
    with open(f'{configuration["DataLoc"]}/{modulename}/{modulename}_IVset_{datadict["date"]}_{datadict["time"]}_{datadict["RH"]}.pkl', 'wb') as datafile:
        pickle.dump(datadict, datafile)

    return f'{configuration["DataLoc"]}/{modulename}/{modulename}_IVset_{datadict["date"]}_{datadict["time"]}_{datadict["RH"]}.pkl'
        
def save_and_upload(datadict, modulename, inspector, upload=False):

    if upload:
        dt = datadict['datetime']
        data = datadict['data']
        temp_c = '21'
        db_upload_iv = [modulename, datadict['RH'], datadict['Temp'], 
                        data[:,0].tolist(), data[:,1].tolist(), data[:,2].tolist(), data[:,3].tolist(), 
                        dt.date(), dt.time(), inspector, '']
        upload_PostgreSQL(table_name = 'module_iv_test', db_upload_data = db_upload_iv)

    iv_save(datadict, modulename)

def read_table(tablename):

    coro = fetch_PostgreSQL(tablename)
    #print(coro)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)
    #print(result)

    for r in result: 
        print(r)


def pedestal_upload(state, ind=-1):

    modulename = state['-Module-Serial-']
    
    runs = glob.glob(f'{configuration["DataLoc"]}/{modulename}/pedestal_run/*')
    runs.sort()
    fname = runs[-1]+'/pedestal_run0.root'

    print(">> Uploading pedestal run of %s board from summary file %s into database" %(modulename, fname))

    # Open the hex data ".root" file and turn the contents into a pandas DataFrame.
    f = uproot.open(fname)
    try:
        tree = f["runsummary"]["summary"]
        df_data = tree.pandas.df()
    except:
        print("No tree found!")
        return 0

    density = modulename.split('-')[1][1]
    shape = modulename.split('-')[2][0]
    hb_type = density+shape

    df_data = add_mapping(df_data, hb_type = hb_type)

    nDeadChan = 0
    ##### XYZ fix dead chan
    if configuration['HasRHSensor']:
        if '-Box-RH-' not in state.keys(): # should already exist
            add_RH_T(state)
        RH = str(state['-Box-RH-'])
        T = str(state['-Box-T-'])
    else:
        RH = 'N/A'
        T = 'N?A'

    now = datetime.now()

    comment = runs[-1].split('/')[-1] # for now, comment is dir name of raw test results
    
    db_upload_ped = [modulename, RH, T, df_data['chip'].tolist(), df_data['channel'].tolist(), 
                     df_data['channeltype'].tolist(), df_data['adc_median'].tolist(), df_data['adc_iqr'].tolist(), 
                     df_data['tot_median'].tolist(), df_data['tot_iqr'].tolist(), df_data['toa_median'].tolist(), 
                     df_data['toa_iqr'].tolist(), df_data['adc_mean'].tolist(), df_data['adc_stdd'].tolist(), 
                     df_data['tot_mean'].tolist(), df_data['tot_stdd'].tolist(), df_data['toa_mean'].tolist(), 
                     df_data['toa_stdd'].tolist(), df_data['tot_efficiency'].tolist(), df_data['tot_efficiency_error'].tolist(), 
                     df_data['toa_efficiency'].tolist(), df_data['toa_efficiency_error'].tolist(), df_data['pad'].tolist(), 
                     df_data['x'].tolist(), df_data['y'].tolist(), nDeadChan, now.date(), now.time(), state['-Inspector-'], 'First upload']

    if 'BV' in runs[ind] and '320-M' in modulename:
        BV = runs.split('BV').rstrip('\n ')
        db_upload_ped.insert(3, BV)
    elif '320-M' in modulename:
        BV = -1
        db_upload_ped.insert(3, BV)
    else:
        pass

    table = 'module_pedestal_test' if ('320-M' in modulename) else 'hxb_pedestal_test'

    coro = upload_PostgreSQL(table_name = table, db_upload_data = db_upload_ped)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    read_table(table)


def iv_upload(datadict, state):

    modulename = state['-Module-Serial-']
    
    iv_save(datadict, modulename)
    
    data = datadict['data']
    
    RH = datadict['RH']
    Temp = datadict['Temp'] 
    #### XYZ what should be commented?
    #### XYZ status? etc.
    {datadict["date"]}_{datadict["time"]}_{datadict["RH"]}
    db_upload_iv = [modulename, RH, Temp, 0, '', '', 0, 0., data[:,0].tolist(), data[:,1].tolist(), data[:,2].tolist(), data[:,3].tolist(),
                    datadict['datetime'].date(), datadict['datetime'].time(), state['-Inspector-'], '']

    coro = upload_PostgreSQL(table_name = 'module_iv_test', db_upload_data = db_upload_iv)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    read_table('module_iv_test')
        
def plots_upload(modulename, hexpath, ind=-1):

    with open(f'{hexpath}_adc_mean.png', 'rb') as f:
        hexmean = f.read()
    with open(f'{hexpath}_adc_stdd.png', 'rb') as f:
        hexstdd = f.read()
    
    runs = glob.glob(f'{configuration["DataLoc"]}/{modulename}/pedestal_run/*')
    runs.sort()
    dname = runs[ind]

    print(">> Uploading pedestal plots of %s board from directory %s into database" %(modulename, dname))

    
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
            
    #with open(dname+'/noise_vs_channel_chip0.png', 'rb') as f:
    #    noise0 = f.read()
    #with open(dname+'/noise_vs_channel_chip1.png', 'rb') as f:
    #    noise1 = f.read()
    #with open(dname+'/noise_vs_channel_chip2.png', 'rb') as f:
    #    noise2 = f.read()
    #with open(dname+'/pedestal_vs_channel_chip0.png', 'rb') as f:
    #    pedestal0 = f.read()
    #with open(dname+'/pedestal_vs_channel_chip1.png', 'rb') as f:
    #    pedestal1 = f.read()
    #with open(dname+'/pedestal_vs_channel_chip2.png', 'rb') as f:
    #    pedestal2 = f.read()
    #with open(dname+'/total_noise_chip0.png', 'rb') as f:
    #    totnoise0 = f.read()
    #with open(dname+'/total_noise_chip1.png', 'rb') as f:
    #    totnoise1 = f.read()
    #with open(dname+'/total_noise_chip2.png', 'rb') as f:
    #    totnoise2 = f.read()

    comment = hexpath.split('_')[-3] # 'runX'
    
    db_upload_plots = [modulename, hexmean, hexstdd, noise, pedestal, totnoise, state['-Inspector-'], comment]
    coro = upload_PostgreSQL(table_name = 'module_pedestal_plots', db_upload_data = db_upload_plots)
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(coro)

    read_table('module_pedestal_plots')


# example of how to read
#coro = fetch_PostgreSQL('module_pedestal_test')
#loop = asyncio.get_event_loop()
#result = loop.run_until_complete(coro)
#
#for r in result: 
#    print(r)

"""
tables:

module_pedestal_test
(module_name, rel_hum, temp_c, bias_vol, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, count_dead_chan, date_test, time_test, inspector, comment)                                                           

module_iv_test:
(module_name, rel_hum, temp_c, status, status_desc, grade, count_dead_chan, ratio_iv, prog_v, meas_v, meas_i, meas_r, date_test, time_test, inspector, comment)                                    

hxb_pedestal_test:
(hxb_name, rel_hum, temp_c, chip, channel, channeltype, adc_median, adc_iqr, tot_median, tot_iqr, toa_median, toa_iqr, adc_mean, adc_stdd, tot_mean, tot_stdd, toa_mean, toa_stdd, tot_efficiency, tot_efficiency_error, toa_efficiency, toa_efficiency_error, pad, x, y, count_dead_chan, date_test, time_test, inspector, comment)                                                                         

module_pedestal_plots:
(module_name, adc_mean_hexmap, adc_stdd_hexmap, noise_channel_chip0, noise_channel_chip1, noise_channel_chip2, pedestal_channel_chip0, pedestal_channel_chip1, pedestal_channel_chip2, total_noise_chip0, total_noise_chip1, total_noise_chip2, inspector, comment_plot_test)                                                                                                                                
"""
