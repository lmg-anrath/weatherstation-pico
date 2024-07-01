try:
	import src.main
except Exception as e:
	print('Failed to run src/main.py: ', e)
	print('[Emergency] Falling back to emergency updater...')

	import time, os, machine
	import emergency

	io = emergency.IO(os=os)
	github =emergency.GitHub(
		io=io,
		remote='https://github.com/lmg-anrath/weatherstation-pico',
		branch='main',
	)
	updater = emergency.OTAUpdater(io=io, github=github, machine=machine)

	try:
		updater.update()
	except Exception as e:
		print('[Emergency] Failed to OTA update:', e)
		time.sleep(5)
		machine.reset()
		pass