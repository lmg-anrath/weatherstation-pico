try:
	import src.boot
except Exception as e:
	print('Failed to run src/boot.py: ', e)
	print('[Emergency Boot] Falling back to emergency boot sequence...')

	import network, ntptime, machine, time

	sta_if = network.WLAN(network.STA_IF)
	if not sta_if.isconnected():
		print('[Emergency Boot] Connecting to network...')
		sta_if.active(True)
		sta_if.connect('Emergency', 'password')
		count = 0
		while not sta_if.isconnected():
			print('Waiting for connection...')
			time.sleep(1)
			count += 1
			if count >= 45:
				print('[Emergency Boot] Failed to connect to network')
				time.sleep(30)
				machine.reset()
				break
			pass
		print('[Emergency Boot] Connected to network: %s' % sta_if.ifconfig())

		time.sleep(1)
		# Get current time from the internet
		ntptime.settime()
	else: 
		print('[Emergency Boot] Already connected via %s.' % sta_if.ifconfig()[0])