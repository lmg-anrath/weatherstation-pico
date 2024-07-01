import env, lib.requests, lib.logger, lib.requests, lib.timew, time, machine

led = machine.Pin('LED', machine.Pin.OUT)
led.off()

t = lib.timew.Time(time=time)

# Configure Logger
logger = lib.logger.config(enabled=env.settings['debug'], include=env.settings['logInclude'], exclude=env.settings['logExclude'], time=t)
log = logger(append='test')
log('The current time is %s' % t.human())

try:
    import src.main as app
    app.Main(env=env, requests=lib.requests, logger=logger, time=t, updater=updater)
except Exception as e:
	log('Failed to start main app:', e)
	pass