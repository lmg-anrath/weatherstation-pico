import json, machine, urequests, json
from machine import Pin
import lib.sds011, lib.bmp280, dht

class Main:
  def __init__(self, env, requests, logger, time, updater):
    # Setting global variables
    self.env = env
    self.requests = requests
    self.time = time
    self.updater = updater

    # Setting up logger
    self.log = logger(append='main')
    self.log("The current time is %s" % self.time.human())

    # Setting up sensors and starting main loop
    self.setup()
    self.start()

  def setup(self):
    self.log('Setting up sensors...')

    # Setup of SDS011 sensor (dust sensor)
    try:
      self.log('Setting up SDS011...')
      self.sds011 = lib.sds011.SDS011(UART(1, baudrate=9600, tx=8, rx=9))
      self.sds011.sleep()
      self.log('SDS011 setup complete')
    except Exception as e:
        self.log('Failed to setup SDS011:', e)
        self.sds011 = None
    
    # Setup of BMP280 sensor (temperature and pressure sensor)
    try:
        self.log('Setting up BMP280...')
        self.bmp280 = lib.bmp280.BMP280(I2C(0, scl=21, sda=20))
        
        self.bmp280.use_case(lib.bmp280.BMP280_CASE_WEATHER)
        self.bmp280.oversample(lib.bmp280.BMP280_OS_HIGH)

        self.bmp280.temp_os = lib.bmp280.BMP280_TEMP_OS_8
        self.bmp280.press_os = lib.bmp280.BMP280_PRES_OS_4

        self.bmp280.standby = lib.bmp280.BMP280_STANDBY_250
        self.bmp280 = lib.bmp280.BMP280_IIR_FILTER_2
        self.bmp280.spi3w = lib.bmp280.BMP280_SPI3W_ON

        self.bmp280.sleep()
        self.log('BMP280 setup complete')
    except Exception as e:
        self.log('Failed to setup BMP280:', e)
        self.bmp280 = None
    
    # Setup of DHT22 sensor (humidity and temperature sensor)
    try:
        self.dht22 = dht.DHT22(Pin(15, Pin.IN, Pin.PULL_UP))
    except Exception as e:
        self.log('Failed to setup DHT22:', e)
        self.dht22 = None

    self.log('Sensor setup complete')

    def start(self):
      self.log('Starting main loop...')
      runs = 0

      while True:
        # Wait for the next 15 minute interval
        (year, month, day, hour, minute, second, wday, yday) = self.time.localtime()
        wait_time = ((minute // 15 + 1) * 15 - minute) * 60 - second
        self.log('Waiting %s seconds...' %wait_time)

        # Wait until 30 seconds before the next 15 minute interval to wake up sensors
        if wait_time > 30:
          self.time.sleep(wait_time - 30)
        else:
          self.time.sleep(wait_time)
        self.log('Waking up sensors...')
        self.sds011.wake()
        self.bmp280.force_measure()
        self.time.sleep(30)

        # Reading sensor data
        data = self.read()

        # Upload data to server
        self.upload(data)

        # Sleeping sensors
        self.log('Sleeping sensors...')
        self.sds011.sleep()
        self.bmp280.sleep()

        runs += 1
        self.log('Run %s complete' % runs)

        # Rebooting every 6 hours
        if runs >= 24: # 24 runs / 15 minutes = 6 hours
          self.log('Ran 24 times, rebooting...')
          machine.reset()
          break

        # Updating firmware
        try:
          self.updater.update()
        except Exception as e:
          self.log('Failed to OTA update:', e)

    def read(self):
        self.log('Reading sensor data...')
        data = {
           'timestamp': str(round(self.time.time())),
        }
    
        if self.sds011 is not None:
            self.log('-- SDS011 Sensor --')
            # Returns NOK if no measurement found in reasonable time
            self.log('Reading data...')
            status = self.sds011.read()
            # Returns NOK if checksum failed
            pkt_status = self.sds011.packet_status
            # Stop fan
            self.log('Data read, sleep sensor...')
            self.sds011.sleep()

            if status == False:
               self.log('Measurement failed.')
            elif pkt_status == False:
               self.log('Received corrupted data.')
            else:
               data['air_particle_pm25'] = self.sds011.pm25
               data['air_particle_pm10'] = self.sds011.pm10
               self.log('PM2.5: %s' % data['air_particle_pm25'])
               self.log('PM10: %s' % data['air_particle_pm10'])
    
        if self.bmp280 is not None:
            self.log('-- BMP280 Sensor --')
            self.log('Reading data...')
            data['temperature'] = self.bmp280.temperature()
            data['air_pressure'] = self.bmp280.pressure()

            self.log('Data read, sleep sensor...')
            self.bmp280.sleep()

            self.log('Temperature: %s C' % data['temperature'])
            self.log('Pressure: %s hPa' % data['air_pressure'])
    
        if self.dht22 is not None:
            self.log('-- DHT22 Sensor --')
            self.dht22.measure()
            data['humidity'] = self.dht22.humidity()
            data['temperature'] = self.dht22.temperature()
            self.log('Temperature: %s C' % data['temperature'])
            self.log('Humidity: %s %%' % data['humidity'])
        
        self.log('Finished reading sensor data.')
        return data
    
    def upload(self, data):
        self.log('Uploading data...')
        self.log('Data:', data)

        headers = {
            'Content-Type': 'application/json',
            'Authorization': self.env.settings['accessToken']
        }

        res = urequests.post(self.env.settings['serverURL'] + '/v2/stations/' + str(self.env.settings['stationId']), data = json.dumps(data), headers = headers)
        print('Upload completed with status code %s!' %res.status_code)
        print('Response from server: ' + res.text)
        res.close()