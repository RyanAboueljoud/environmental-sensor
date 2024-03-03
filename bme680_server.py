"""
BME680 Sensor Server.
Hosted on a Raspberry Pi Pico W

Monitors sensor values, and
reports them to influxDB
"""

import uos
import urequests
from machine import Pin, I2C
import wlan_setup
from bme680 import *
import time
import math
import ntp_client as ntp

# Function to read the config file and build a dictionary
def read_config(filename='config'):
    config_dict = {}
    
    try:
        with open(filename, 'r') as file:
            for line in file:
                key, value = line.strip().split('=')
                config_dict[key.strip()] = value.strip()
    except Exception as e:
        print("Error reading config file:", str(e))
    
    return config_dict

# Initialize global variables
led = Pin("LED", Pin.OUT)   # activity led
config = read_config()
addr = f'http://{config['address']}:{config['port']}/api/v2/write?org=HOME_ASSISTANT&bucket={config['database']}&precision=s'
credentials = f"Token {config['login']}:{config['password']}"


# Function convert second into day
# hours, minutes and seconds
def seconds_to_time(n):
    day = n // (24 * 3600)

    n = n % (24 * 3600)
    hour = n // 3600

    n %= 3600
    minutes = n // 60

    n %= 60
    seconds = n

    return [seconds, minutes, hour, day]

led.on()

# Print hardware info
print()
print("Machine: \t" + uos.uname()[4])
print("MicroPython: \t" + uos.uname()[3])

# Initializing the I2C method 
i2c=I2C(0, scl=Pin(17), sda=Pin(16), freq=400000)
bme = BME680_I2C(i2c=i2c)

# Initialize and connect wireless lan
wlan_setup.connect()

# Sync NTP Online
ntp.setup()
start_timestamp = time.mktime(time.localtime())     # Program start time
last_sample_time = start_timestamp

led.off()

# Networking initialized, start monitoring sensors
print('Starting Sensor Monitor...')
print(f'influxDB API URL: {addr}')
while True:
    try:
        now = time.mktime(time.localtime())
        if (now - last_sample_time) > 1800:   # Update every 30min (1800 sec)
            # Update current date and time
            year, month, mday, hour, minute, second, weekday, yearday = time.localtime()
            date = f'{month}/{mday}/{year}'
            time_now = f'{hour}:{minute}:{second}'
            runtime = seconds_to_time((now - start_timestamp))
            
            led.on()
            precision = 3
            for x in range(6):  # Warm up sensor before reporting readings
                temperature = round(bme.temperature, precision)
                temperature_f = round(((bme.temperature * 9 / 5) + 32), precision)
                humid = round(bme.humidity, precision)
                press = round(bme.pressure, precision) # in Si units for hPascal
                gas = round(bme.gas / 1000, precision) # The gas resistance in ohms
                aqi = round((math.log(round(bme.gas / 1000, precision)) + 0.04 * round(bme.humidity, precision)), precision)
                altitude = round(bme.altitude, precision) # meters
                time.sleep_us(10)
            
            measurements = {
                "temperature_C": temperature,
                "temperature_F": temperature_f,
                "humidity": humid,
                "pressure": press,
                "gas": gas,
                "aqi": aqi,
                "altitude": altitude
            }
            
            headers = {
                'Authorization': credentials,
                'Content-Type': 'text/plain; charset=utf-8',
                'Accept': 'application/json'
            }
            
            data = ''
            for key, value in measurements.items():
                data += f'{key},date={date},time_now={time_now} value={value}\n'
            print(data)
                
            urequests.post(addr, headers = headers, data=data)

            last_sample_time = now
            
            led.off()
            
        continue
    except OSError as e:
        print(f'Error: {e}')
        led.off()
        time.sleep_ms(10)
        continue
