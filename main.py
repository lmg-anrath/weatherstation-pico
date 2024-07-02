try:
	import src.main
except Exception as e:
	print('Failed to run src/main.py: ', e)
	print('[Emergency] Falling back to emergency updater...')
	try:
		import src.emergency
	except Exception as e:
		print('Failed to run src/emergency.py: ', e)
		print('[Emergency] Failed to run emergency updater. Rebooting...')
		import time, machine
		time.sleep(30)
		machine.reset()