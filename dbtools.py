from Keithley2400 import Keithley2400
import numpy as np
import time
import matplotlib.pyplot as plt
import pickle
from argparse import ArgumentParser
import datetime
import os
import psycopg2
import pandas as pd
import glob
import uproot3 as uproot

import yaml
configuration = {}
with open('configuration.yaml', 'r') as file:
    configuration = yaml.safe_load(file)

def save_and_upload(datadict, modulename, tag, relhum, temp, inspector, upload=False):

    if upload:
        pass

    os.system(f'mkdir -p {configuration["DataLoc"]}/{modulename}')
    with open(f'{configuration["DataLoc"]}/{modulename}/{modulename}_IVset_{datadict["date"]}_{tag}_{datadict["RH"]}.pkl', 'wb') as datafile:
        pickle.dump(datadict, datafile)

