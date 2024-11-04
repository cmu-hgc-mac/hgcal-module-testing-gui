import serial
import time
import subprocess

class AirControl:

    def __init__(self):

        # automatic discovery of serial address location by device ID
        usblines = subprocess.getoutput("ls -l /dev/serial/by-id").split('\n')
        thisboard = 'usb-FTDI_FT232R_USB_UART_AC0090JP-if00-port'

        for line in usblines:
            if thisboard in line:
                thisusb = line.split(' ')[-1].split('/')[-1]
                self.ttystr = '/dev/'+thisusb
                print('  >> AirControl: using', self.ttystr)

        self.nano = serial.Serial(self.ttystr, 115200, timeout=2)
        # Change port if needed, default /dev/ttyUSB1 # port changed on 07/25/2024, #lsusb; dmesg | grep tty
        # As of 2024/8/26 trying both ports as they seem to change without warning
        # As of 2024/10/4, switched to automatic discovery

    def __del__(self):
        self.nano.close()

    def set_air_on(self):
        """Turns the air relay on
        """
        self.nano.write(b'air on\n')
        self.nano.write(b'air on\n')
        print('  >> AirControl: air on')

    def set_air_off(self):
        """Turns the air relay off
        """
        self.nano.write(b'air off\n')
        self.nano.write(b'air off\n')
        print('  >> AirControl: air off')

    def get_humidity(self):
        """Returns the current humidity as an integer percentage
        """
        environment_string = self.nano.readline().decode('ASCII').rstrip()
        humidity_string = environment_string.split(',')[0]
        return int(humidity_string)

    def get_temperature(self):
        """Returns the current temperature in degrees Celcius as an integer
        """
        environment_string = self.nano.readline().decode('ASCII').rstrip()
        temperature_string = environment_string.split(',')[1]
        return int(temperature_string)
        
if __name__ == "__main__":
    controller = AirControl()
    while True:
        print(f"Temperature = {controller.get_temperature()}ºC")
        print(f"Humidity = {controller.get_humidity()}%")
        time.sleep(1)

