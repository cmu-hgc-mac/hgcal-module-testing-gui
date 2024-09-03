# HGCal Module Testing GUI
A GUI for HGCAL hexaboard and silicon module testing

This repository is a copy of the repository at [https://gitlab.cern.ch/acrobert/hgcal-module-testing-gui](https://gitlab.cern.ch/acrobert/hgcal-module-testing-gui) and should (but may not) be up-to-date with that repository.

## Motivation
We have been using detailed procedures for module testing, and though these do work, I found it was very easy for people new to the system to skip steps and make mistakes. Additionally, it seemed that a large portion of the test sequence can be automated. A GUI would greatly simplify training, force users to follow the correct steps in the correct order, and hide the parts of the sequence that require special skills (i.e. bash) behind automation. Also, this GUI is integrated with the database and may soon serve as the starting point for the multimodule testing GUI.

## Installing the GUI
The GUI can be installed by simply cloning this repository. You will also need to  install `PySimpleGUI` (and let's preemptively install `psycopg2` and `asyncpg` as well):
```
pip3 install PySimpleGUI psycopg2 asyncpg
git clone https://gitlab.cern.ch/acrobert/hgcal-module-testing-gui.git
cd hgcal-module-testing-gui
```

Also, if you do not already have an ssh key for use between the Centos PC and the Trenz FPGA, create one (ensure the Trenz is powered for this, but no need to connect anything to it):
```
ssh-keygen # follow the prompts, no need to enter a password or use a name other than the default
ssh-copy-id -i ~/.ssh/id_rsa root@[TrenzFPGAHostname]
```

The GUI uses PyVISA to control the HV power supply. CMU uses an RS232 cable to control it; if you have another type of cable, you may have to re-implement part of the code. To discover the VISA resource name, run the following in a python shell:
```
import pyvisa
rm = pyvisa.ResourceManager()
rm.list_resources()
```
In some cases, it is needed to add the argument `'@py'` to the `ResourceManager()` intialization. Ignore the `'ASRL1::INSTR'` and `'ASRL2::INSTR'` resources. The resource name for the RS232 includes `USB0::INSTR`; look for something similar. If you are using GPIB, the resource name will include `GPIB`. To confirm it is correct, you can run from the same python shell:
```
my_instrument = rm.open_resource('ASRL/dev/ttyUSB0::INSTR')
print(my_instrument.query('*IDN?'))
```
The power supply's make and model should be printed if you have found the correct string. If you at some time change which port the power supply is plugged into, this string may change.

Lastly, create a configuration file with `writeconfig.py`. Open the python script in a text editor and change the values in the dictionary:
* `DebugMode`: initial value of the GUI's Debug Mode; keep this true for now!
* `DefaultFontSize`: font of the GUI; matters depending on the resolution of your monitor: if the monitor is 1920x1080, 15 is good
* `TestingPCOpSys`: operating system of the testing PC: 'Centos7' or 'Alma9'
* `TrenzHostname`: list of the hostnames of your Trenz FPGAs
* `MACSerial`: two-letter code for modules made by the MAC
* `DataLoc`: path to where you want test results to be stored
* `HVResource`: VISA resource name of the high voltage power supply found above
* `HVTerminal`: `'Front'` for front terminals, `'Rear'` for rear terminals
* `HVWiresPolarization`: `'Reverse'` for reverse bias (V in [0, 800]); `'Forward'` for forward bias (V in [-800, 0])
* `PCKeyLoc`: location of the private key you made above
* `HasHVSwitch`: true if you have a switch on the dark box which can automatically detect if the box is closed; false otherwise
* `HasRHSensor`: true if you have the ability to automatically read the relative humidity in the box; false otherwise
* `Inspectors`: list CERN usernames of people who may use the GUI
* `HasLocalDB`: boolean if MAC uses a local database
* `DBHostname`, `DBDatabase`, `DBUsername`. `DBPassword`: Fields for local database connection (only needed if `HasLocalDB = True`)

Once finished, run `python3 writeconfig.py` to create the configuration file. The file will not be overwritten when you update the repository (i.e. with `git pull`).

## Using the GUI
Currently, the GUI has to be run on the Centos PC used for testing. The GUI can be opened by simply running `python3 TestingGUIBase.py` from a terminal window. There are several parts of the GUI that are highly setup-dependent and may have to be heavily modified or **entirely re-implemented** for other MACs, but we'll discuss that later. For now, let's assume your setup is the same as the CMU setup.

The GUI consists of three main windows. The "Module Setup" window controls the selection of the module type and number (which determines the serial number) and other settings. The "Select Tests" window is initially disabled and allows the user to select which tests to run once the system is set up. The "Status Bar" summarizes the current status of the testing system with several indicators. Several values and settings are stored in the `configuration.yaml` file, including the site code ('CM' for CMU) and things like the test stand IP address. Lastly, the GUI has a "Debug Mode" which can be toggled with the checkbox on the bottom. In Debug Mode, the GUI will run normally but will not interface with any of the testing equipment, but it will interface with the user, so it is helpful for understanding the flow of testing and ensuring things are being done as expected inside the GUI. 

Currently, the GUI only functions for HD Full, LD Full, Left, and Right modules and hexaboards. Other densities and geometries will be added as details arrive.

### It is **always safe** to exit the GUI (i.e. by canceling the python process) and shut the testing system down manually.
If you encounter an error or the GUI closes suddenly, shut the testing system down the way you would if you were testing a module without the GUI.

The Module Setup is how the module serial number is defined. The GUI can either test bare hexaboards or live modules; the density and geometry of the module is selectable. For hexaboards, the hexaboard version must be selected (either V3 or Production) and the manufacturer code must be entered. For live modules, the sensor thickness and baseplate type must be selected. For both, the module index must be entered and the test stand IP selected. The "Module Serial Number" text updates as you enter this information. If only tests involving bias voltage (that is, IV curves) are desired, the system can then be initiated with the "Only IV Test" button. This button will guide the user through the steps to connect the HV cable and also automatically connect to the power supply. This button does nothing for hexaboards as IV tests are meaningless. If full electrical tests are desired, the "Configure Test Stand" button will guide the user through the steps to connect and power the test stand and automatically start the required services. Once either of these are pressed, the Module Setup window is disabled.

For the initial part of the module test, you will need a multimeter to check the hexaboard for shorts and to verify the power is correct. When checking the power, **do not short the probes**.

%The Pedestal Scan test runs the `pedestal_run.py` script and the `pedestal_scan.py` script, and the Vref Inv and NoInv Scan test runs the `vrefinv_scan.py` and `vrefnoinv_scan.py` scripts. Both of these are intended to be used to adjust the ROC settings. 

Once the testing system is ready to run tests, the Select Tests window will be enabled. At the moment, there are four possible tests. The Trim Pedestals test runs`pedestal_run.py`, `pedestal_scan.py`, `vrefinv_scan.py`, and `vrefnoinv_scan.py` scripts in sequence. The outputs of these tests are used to configure the chips and channels ("trim" the pedestals) which has the effect of flattening the pedestals by half-chip. The Pedestal Run test allows the user to run up to 6 pedestal runs. If the module is live, the user can also specify the bias voltage for each of these runs. The Ambient and Dry IV Curve tests are only enabled for live modules and take IV curves at the respective humidity levels. At CMU, our test system is inside a box with a dry air valve and we have no thermal control, so we are limited to these two options. Once the tests are selected, they can be run with the Run Tests button. The GUI will automatically run them as you wait. If the test stand is connected (i.e. not only IV tests), the button will also check the status of the services on the test stand and on the testing PC. If there is an error in them, the test will abort and the indicator lights will change. The services can be restarted with the Restart Services button, though some errors may require a full reset of the system. Once testing is complete, the End Session button will disable the Select Tests menu and guide the user through the system shutdown sequence. Once finished, the Module Setup menu will be re-enabled and another module can be tested without restarting the GUI.

## How it works
There are two main GUI scripts. The first, `TestingGUIBase.py`, creates and runs the main window. The script `InteractionGUI.py` contains many functions that control the interaction of the user, main window, and the testing system. The current state of the testing system is essential to performing the right actions at the right times and detecting errors in the testing sequence. This is passed back and forth between the two scripts as a dictionary: if I want to run a test, the `TestingGUIBase.py` loop calls a function from `InteractionGUI.py` which runs the test, and one of the arguments to the function call is the state dictionary. The state dictionary also contains fields that store the objects that wrap the test system components. The booleans which keep track of the state are also displayed in the Status Bar on the right of the main window.

Together, these two scripts make up the bulk of the GUI. However, there are parts of them that other MACs may have to re-implement. `InteractionGUI.py` has functions that for example instruct the user to turn a dry air valve on or off; other MACs may have other ways of controlling the humidity or not have control over it at all. Additionally, the order of assembling and starting the testing system is specific and may not work out-of-the-box for other setups. It will be good to merge all of our different setups and methods into one codebase but this will take time.

Then follows a number of classes that interact with the testing system. Portions of these may have to be re-implemented for the setup at other MACs.

The class `CentosPC.py` wraps the Centos testing PC. It takes the Trenz test stand hostname, the module serial number, and a flag specifying if it is a live module as arguments to the constructor. During instantiation, the class restarts the DAQ client service which interacts with the Trenz test stand. It has member functions to check the status of and restart the DAQ client, as well as functions to run the testing scripts (i.e. `pedestal_run.py` from the hexacontroller package) and store the output in the correct place. It also contains a function to make hexmaps from any given pedestal run, which are most useful to evaluating the module under test. There is also a static function to make hexmap plots in this file. Some small parts of this file may have to be modified for other MACs but largely it should apply to any Trenz system.

The class `TrenzTestStand.py` wraps the Trenz FPGA test stand. It takes the hostname as an argument to its constructor, which waits until the Trenz can be pinged and then creates a SSH Client object with Paramiko. This SSH Client is then used to remotely start and check the services on the test stand. The class includes member functions which load the firmware on the Trenz and start the DAQ and I2C servers, as well as a function that checks the status of the servers and a function that remotely shuts the Trenz down. Some small parts of this file may have to be modified for other MACs, like file paths, but largely it should apply to any Trenz system.

The class `Keithley2400.py` wraps the Keithley 2410 power supply used to bias the module. It uses PyVISA to interact over an RS232 cable with the power supply and includes member functions to read from, query, and write to the power supply, and member functions that use these to set and measure current and voltage as well as take IV curves on live modules. This is currently done by configuring the sweep function of the Keithley, running a sweep, and then waiting until it is finished and reading all of the data back. It also includes a function to check the state of a switch attached to the testing box which ensures the power is not activated when the box is open. This class is fairly dependent on what power supply is used and how it is connected to the PC. In principle, if connection using PyVISA is possible, editing the constructor to correctly select which resource to open should be the only thing to change, but it is possible that other parts need to change as well, such as the power enable switch or the syntax of the read/write/query calls.

The markdown file `configuration.yaml` stores MAC-specific values that are used by the other scripts. This includes the location on the testing PC where data is stored, the default value for the debug mode flag, the resource name for the power supply, the MAC-specific code to use in live module serial numbers, the location on the PC of the private ssh key used to connect to the test stand, and a list of test stand hostnames. These should be edited manually by each MAC.

The `DBTools.py` and `PostgresTools.py` scripts contain functions used to upload testing results to the local MAC database. If the configuration file sets `HasLocalDB = False` then these will be entirely ignored.

The `AirControl.py` class is used to control the dry air valve and automatically read the relative humidity and temperature inside the dark box. This setup is likely quite specific to CMU. If the configuration file sets `HasRHSensor = False` this will be ignored. Feel free to re-implement this class partially or entirely if you have these capabilities but must use them in a different way. Note however that changes to this class will be overwritten by gitlab.

If your test system is different and you have capability that the CMU MAC does not, you will have to add interaction steps to perform them and/or sections of the GUI that controls them. Features that you may want to implement that are not currently implemented include thermal control of the test box and vacuum hold-down of the module. Additionally, you may desire to do things in a different order or add tests that are currently not implemented. 




