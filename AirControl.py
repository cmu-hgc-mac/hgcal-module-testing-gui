import serial
import time

class AirControl:

    def __init__(self):
        self.nano = serial.Serial('/dev/ttyUSB1', 115200, timeout=2) #Change port if needed, default /dev/TTYUSB1

    def __del__(self):
        self.nano.close()

    def set_air_on(self):
        """Turns the air relay on
        """
        self.nano.write(b'air on\n')

    def set_air_off(self):
        """Turns the air relay off
        """
        self.nano.write(b'air off\n')

    def get_humidity(self):
        """Returns the current humidity as an integer percentage
        """
        environment_string = self.nano.readline().decode('ASCII').rstrip()
        print(environment_string)
        humidity_string = environment_string.split(',')[0]
        return int(humidity_string)

    def get_temperature(self):
        """Returns the current temperature in degrees Celcius as an integer
        """
        environment_string = self.nano.readline().decode('ASCII').rstrip()
        print(environment_string)
        temperature_string = environment_string.split(',')[1]
        return int(temperature_string)
        
if __name__ == "__main__":
    controller = AirControl()
    while True:
        print(f"Temperature = {controller.get_temperature()}ºC")
        print(f"Humidity = {controller.get_humidity()}%")
        time.sleep(1)

