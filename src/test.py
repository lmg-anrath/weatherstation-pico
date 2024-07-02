import env, src.lib.requests as requests, src.lib.logger as logger, src.lib.timew as timew, time, machine

led = machine.Pin('LED', machine.Pin.OUT)
led.off()

t = timew.Time(time=time)

# Configure Logger
logger = logger.config(enabled=env.settings['debug'], include=env.settings['logInclude'], exclude=env.settings['logExclude'], time=t)
log = logger(append='test')
log('The current time is %s' % t.human())

try:
    import src.app.main as app
    app.Main(env=env, requests=requests, logger=logger, time=t, updater=None)
except Exception as e:
	log('Failed to start main app:', e)
	pass