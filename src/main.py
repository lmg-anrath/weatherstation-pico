import src.lib.update as update, env, src.lib.requests as requests, src.lib.logger as logger, src.lib.timew as timew, time, os, machine
from src.lib import base64

#gc.enable()

led = machine.Pin('LED', machine.Pin.OUT)
led.off()

t = timew.Time(time=time)

# Configure Logger
logger = logger.config(enabled=env.settings['debug'], include=env.settings['logInclude'], exclude=env.settings['logExclude'], time=t)
log = logger(append='boot')

loggerOta = logger(append='OTAUpdater')

io = update.IO(os=os, logger=loggerOta)
github = update.GitHub(
	io=io,
	remote=env.settings['githubRemote'],
	branch=env.settings['githubRemoteBranch'],
	logger=loggerOta,
	requests=requests,
	username=env.settings['githubUsername'],
	token=env.settings['githubToken'],
	base64=base64,
)
updater = update.OTAUpdater(io=io, github=github, logger=loggerOta, machine=machine)

try:
	updater.update()
except Exception as e:
	log('Failed to OTA update:', e)
	time.sleep(5)
	machine.reset()
	pass

try:
	import src.app.main as app
	app.Main(env=env, requests=requests, logger=logger, time=t, updater=updater)
except Exception as e:
	log('Failed to start main app:', e)
	time.sleep(5)
	machine.reset()
	pass