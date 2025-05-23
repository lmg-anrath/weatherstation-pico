import json, machine, urequests, json, gc, asyncio
from machine import Pin
import src.app.lib.sds011 as lib_sds011, src.app.lib.bmp280 as lib_bmp280, dht as lib_dht22

class Main:
	def __init__(self, env, requests, logger, time, updater):
		# Setting global variables
		self.env = env
		self.requests = requests
		self.time = time
		self.updater = updater

		# Setting up logger
		self.log = logger(append='weatherstation')
		self.log('The current time is %s' % self.time.human())


		self.led = machine.Pin('LED', machine.Pin.OUT)
		self.led.on()

		gc.enable()

		# Setting up sensors and starting main loop
		self.setup()
		self.start()

	def setup(self):
		#blink = asyncio.create_task(blink(self.led, 1))
		setup_log = self.log(append='setup')
		setup_log('Setting up sensors...')

		# Setup of SDS011 sensor (dust sensor)
		log = setup_log(append='sds011')
		try:
			log('Setting up SDS011...')
			self.sds011 = lib_sds011.SDS011(machine.UART(1, baudrate=9600, tx=8, rx=9))
			self.sds011.sleep()
			log('SDS011 setup complete.')
		except Exception as e:
			log('Failed to setup SDS011:', e)
			self.sds011 = None

		# Setup of BMP280 sensor (temperature and pressure sensor)
		log = setup_log(append='bmp280')
		try:
			log('Setting up BMP280...')
			self.bmp280 = lib_bmp280.BMP280(machine.I2C(0, scl=21, sda=20))

			self.bmp280.use_case(lib_bmp280.BMP280_CASE_WEATHER)
			self.bmp280.oversample(lib_bmp280.BMP280_OS_HIGH)

			self.bmp280.temp_os = lib_bmp280.BMP280_TEMP_OS_8
			self.bmp280.press_os = lib_bmp280.BMP280_PRES_OS_4

			self.bmp280.standby = lib_bmp280.BMP280_STANDBY_250
			self.bmp280.iir = lib_bmp280.BMP280_IIR_FILTER_2
			self.bmp280.spi3w = lib_bmp280.BMP280_SPI3W_ON

			self.bmp280.sleep()
			log('BMP280 setup complete.')
		except Exception as e:
			log('Failed to setup BMP280:', e)
			self.bmp280 = None

		# Setup of DHT22 sensor (humidity and temperature sensor)
		log = setup_log(append='dht22')
		try:
			log('Setting up DHT22...')
			self.dht22 = lib_dht22.DHT22(Pin(15, Pin.IN, Pin.PULL_UP))
			log('DHT22 setup complete.')
		except Exception as e:
			log('Failed to setup DHT22:', e)
			self.dht22 = None

		self.time.sleep(5)
		#blink.cancel()
		self.led.on()
		setup_log('Sensor setup complete')

	def start(self):
		log = self.log(append='loop')
		log('Starting main loop...')
		loop = self.env.settings['onlyRunOnce'] != 'True'
		runs = 0

		if not loop:
			log('[WARN] The program will only run once due to onlyRunOnce being set to True.')

		while True:
			if loop:
				# Wait for the next 15 minute interval
				(year, month, day, hour, minute, second, wday, yday) = self.time.localtime()
				wait_time = ((minute // 15 + 1) * 15 - minute) * 60 - second
				log('Waiting %s seconds...' %wait_time)
				self.led.off()

				# Wait until 30 seconds before the next 15 minute interval to wake up sensors
				if wait_time > 30:
					self.time.sleep(wait_time - 30)
				else:
					self.time.sleep(wait_time)

			log('Waking up sensors...')
			self.led.on()
			try:
				self.sds011.wake()
			except Exception as e:
				log('Failed to wake up SDS011: ', e)
			try:
				self.bmp280.force_measure()
			except Exception as e:
				log('Failed to wake up BMP280: ', e)

			if loop:
				self.time.sleep(30)
			else:
				self.time.sleep(10)

			#blink = asyncio.create_task(blink(self.led, 0.5))

			# Reading sensor data
			data = self.read()

			# Upload data to server
			self.upload(data)

			#blink.cancel()
			self.led.on()

			# Sleeping sensors
			log('Sleeping sensors...')
			try:
				self.sds011.sleep()
			except Exception as e:
				log('Failed to sleep SDS011: ', e)
			try:
				self.bmp280.sleep()
			except Exception as e:
				log('Failed to sleep BMP280: ', e)

			# Collecting garbage
			gc.collect()

			runs += 1
			log('Run %s complete' % runs)

			# Rebooting every 6 hours
			if runs >= 24: # 24 runs / 15 minutes = 6 hours
				log('Ran 24 times, rebooting...')
				machine.reset()
				break

			# Checking for updates
			if self.updater is not None:
				self.updater.checkForUpdate()

			# Break loop if onlyRunOnce is set to True
			if not loop:
				self.led.off()
				log('Exiting...')
				break

	def read(self):
		read_log = self.log(append='read')
		read_log('Reading sensor data...')
		data = {
			'timestamp': str(round(self.time.time())),
		}
    
		if self.sds011 is not None:
			log = read_log(append='sds011')
			log('-- SDS011 Sensor --')
			# Returns NOK if no measurement found in reasonable time
			log('Reading data...')
			status = self.sds011.read()
			# Returns NOK if checksum failed
			pkt_status = self.sds011.packet_status
			# Stop fan
			log('Data read, sleep sensor...')
			self.sds011.sleep()

			if status == False:
				log('Measurement failed.')
			elif pkt_status == False:
				log('Received corrupted data.')
			else:
				data['air_particle_pm25'] = self.sds011.pm25
				data['air_particle_pm10'] = self.sds011.pm10
				log('PM2.5: %s' % data['air_particle_pm25'])
				log('PM10: %s' % data['air_particle_pm10'])

		if self.bmp280 is not None:
			log = read_log(append='bmp280')
			log('-- BMP280 Sensor --')
			log('Reading data...')
			data['temperature'] = self.bmp280.temperature
			data['air_pressure'] = self.bmp280.pressure / 100

			log('Data read, sleep sensor...')
			self.bmp280.sleep()

			log('Temperature: %s C' % data['temperature'])
			log('Pressure: %s hPa' % data['air_pressure'])

		if self.dht22 is not None:
			log = read_log(append='dht22')
			log('-- DHT22 Sensor --')
			self.dht22.measure()
			try:
				data['humidity'] = self.dht22.humidity()
				data['temperature'] = self.dht22.temperature()
				log('Temperature: %s C' % data['temperature'])
				log('Humidity: %s %%' % data['humidity'])
			except Exception as e:
				log('Measurement failed.', e)

		read_log('Finished reading sensor data.')
		return data

	def upload(self, data):
		log = self.log(append='upload')
		log('Uploading data...')
		log('Data:', data)

		headers = {
			'Content-Type': 'application/json',
            'Authorization': self.env.settings['accessToken']
        }

		res = urequests.post(self.env.settings['serverURL'] + '/v2/stations/' + str(self.env.settings['stationId']), data = json.dumps(data), headers = headers)
		log('Upload completed with status code %s!' %res.status_code)
		log('Response from server: ' + res.text)
		res.close()

async def blink(led, delay):
	while True:
		led.on()
		await asyncio.sleep(delay)
		led.off()
		await asyncio.sleep(delay)
