import network, ntptime, machine, env, time

led = machine.Pin('LED', machine.Pin.OUT)
led.on()

sta_if = network.WLAN(network.STA_IF)
if not sta_if.isconnected():
  print('Connecting to network...')
  sta_if.active(True)
  #sta_if.config(dhcp_hostname=env.settings['controllerName'])
  sta_if.connect(env.settings['wifiAP'], env.settings['wifiPassword'])
  count = 0
  while not sta_if.isconnected():
    print('Waiting for connection...')
    led.toggle()
    time.sleep(1)
    count += 1
    if count >= 45:
      print('Failed to connect to network')
      machine.reset()
      break
    pass
  print('Connected to network:', sta_if.ifconfig())

  # Get current time from the internet
  ntptime.settime()