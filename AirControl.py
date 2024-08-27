import serial
import time

class AirControl:

    def __init__(self):
        try:
            self.nano = serial.Serial('/dev/ttyUSB1', 115200, timeout=2) 
        except:
            self.nano = serial.Serial('/dev/ttyUSB2', 115200, timeout=2) 
        #Change port if needed, default /dev/ttyUSB1 # port changed on 07/25/2024, #lsusb; dmesg | grep tty
        # As of 2024/8/26 trying both ports as they seem to change without warning

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
        #print("humidity env string : ", environment_string)
        humidity_string = environment_string.split(',')[0]
        #print("humidity string : ", humidity_string)
        return int(humidity_string)

    def get_temperature(self):
        """Returns the current temperature in degrees Celcius as an integer
        """
        environment_string = self.nano.readline().decode('ASCII').rstrip()
        #print("temp env string : ", environment_string)
        temperature_string = environment_string.split(',')[1]
        #print("temp string : ", temperature_string)
        return int(temperature_string)
        
if __name__ == "__main__":
    controller = AirControl()
    while True:
        print(f"Temperature = {controller.get_temperature()}ºC")
        print(f"Humidity = {controller.get_humidity()}%")
        time.sleep(1)

