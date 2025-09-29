import argparse
import subprocess

"""
This script serves as a launcher for different testing GUI applications. 
    - The current implementation only supports SMTS and MMTS testing GUI applications.
"""


parser = argparse.ArgumentParser(description='Start and run the Testing GUI.')

parser.add_argument('--mode', default='SMTS')

args = parser.parse_args()

if args.mode == 'SMTS':
    subprocess.run(['python', 'SMTS_TestingGUIBase.py'])
elif args.mode == 'MMTS':
    subprocess.run(['python', 'MMTS_TestingGUIBase.py'])
else:
    print("Invalid mode. Please choose 'SMTS' or 'MMTS'.")