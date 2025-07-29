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

        # check if the serial is opened or not
        if self.nano.is_open:
            print("  >> AirControl: Serial ready to connect")

        if not self.nano.is_open:
            try:
                self.nano.open()
            except:
                self.nano = serial.Serial(self.ttystr, 115200, timeout=2) # try reconnect

        # query the env data incase to remove the potential error ahead
        self.nano.readline().decode('ASCII').rstrip()
        
            
    def __del__(self):
        self.nano.close()

    def set_air_on(self):
        """Turns the air relay on
        """
        if self.nano.in_waiting:
            print(" >> AirControl: Serial receiving command")
            
        time.sleep(0.5)
        self.nano.write(b'air on\n')
        time.sleep(0.5)
        self.nano.write(b'air on\n')
        print('  >> AirControl: air on')

    def set_air_off(self):
        """Turns the air relay off
        """
        time.sleep(0.5)
        self.nano.write(b'air off\n')
        time.sleep(0.5)
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

    def close(self):
        """Close the serial for releasing process.
        """
        self.nano.close()
        print(" >> AirControl: Serial closed.")
        
if __name__ == "__main__":
    controller = AirControl()
    while True:
        print(f"Temperature = {controller.get_temperature()}ºC")
        print(f"Humidity = {controller.get_humidity()}%")
        time.sleep(1)

