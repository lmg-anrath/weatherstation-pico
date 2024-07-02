# Emergency boot script for when the main app fails to start

# update.py

class IO:
  def __init__(self, os=None, logger=None):
    self.os = os
    self.log = logger(append='io')

  def rmtree(self, path):
    if not self.exists(path):
      return

    self.log('Removing directory [%s]' % path)
    for entry in self.os.ilistdir(path):
      isDir = entry[1] == 0x4000
      if isDir:
        self.rmtree(path + '/' + entry[0])
      else:
        self.os.remove(path + '/' + entry[0])
    self.os.rmdir(path)

  def move(self, fromPath, toPath):
    self.log('Moving [%s] to [%s]' % (fromPath, toPath))
    self.os.rename(fromPath, toPath)

  def copy(self, fromPath, toPath):
    self.log('Copying [%s] to [%s]' % (fromPath, toPath))
    if not self.exists(toPath):
      self.mkdir(toPath)

    for entry in self.os.ilistdir(fromPath):
      self.copy(fromPath + '/' + entry[0], toPath + '/' + entry[0])

    with open(fromPath) as fromFile:
      with open(toPath, 'w') as toFile:
        CHUNK_SIZE = 512 # bytes
        data = fromFile.read(CHUNK_SIZE)
        while data:
          toFile.write(data)
          data = fromFile.read(CHUNK_SIZE)
      toFile.close()
    fromFile.close()

  def exists(self, path) -> bool:
    try:
      self.os.listdir(path)
      return True
    except:
      return False

  def mkdir(self, path):
    self.log('Making directory [%s]' % path)
    self.os.mkdir(path)

  def readFile(self, path):
    with open(path) as f:
      return f.read()

  def writeFile(self, path, contents):
    self.log('Writing file %s' % path)
    with open(path, 'w') as file:
      file.write(contents)
      file.close()

  def path(self, *args):
    return '/'.join(args).replace('//', '/').lstrip('/').rstrip('/')

class OTAUpdater:

  def __init__(
    self,
    mainDir='src',
    nextDir='next',
    versionFile='.version',
    machine=None,
    io=None,
    github=None,
    logger=None,
  ):
    self.github = github
    self.mainDir = mainDir
    self.nextDir = nextDir
    self.versionFile = versionFile
    self.machine = machine
    self.io = io
    self.log = logger

  def compare(self):
    self.log('Pulling down remote... ')
    localSha = None
    try:
      localSha = self.io.readFile('%s/%s' % (self.mainDir, self.versionFile))
    except:
      self.log('No version file found.', name="compare")

    remoteSha = self.github.sha()

    self.log('Local SHA: ', localSha)
    self.log('Remote SHA: ', remoteSha)
    return (localSha, remoteSha)

  def checkForUpdate(self):
    (localSha, remoteSha) = self.compare()
    if localSha != remoteSha:
      # Reset the device so we don't have to worry about the watchdog
      self.machine.reset()

  def update(self):
    (localSha, remoteSha) = self.compare()
    if localSha == remoteSha:
      return

    self.io.rmtree(self.nextDir)
    self.io.mkdir(self.nextDir)
    self.github.download(remoteSha, self.nextDir, base=self.mainDir)
    self.io.writeFile(self.nextDir + '/' + self.versionFile, remoteSha)
    self.io.rmtree(self.mainDir)
    self.io.move(self.nextDir, self.mainDir)

class GitHub:
  def __init__(self, remote=None, io=None, logger=None, branch='master', username='', token=''):
    self.remote = remote.rstrip('/').replace('https://github.com', 'https://api.github.com/repos')
    self.io = io
    self.log = logger(append='github')
    self.branch = branch
    self.logger = logger

    if username and token:
      self.headers = {'Authentication': 'Basic %s' % b64encode(b'%s:%s' % (username, token))}
    else:
      self.headers = {}

  def sha(self):    
    result = get('%s/commits?per_page=1&sha=%s' % (self.remote, self.branch), logger=self.logger, headers=self.headers)
    if result.status_code == 200:
      sha = result.json()[0]['sha']
    else:
      raise Exception('Unexpected response from GitHub: %d:%s' % (result.status_code, result.reason))
    result.close()
    return sha
    
  def download(self, sha=None, destination=None, currentDir='', base=''):
    fileList = get('%s/contents/%s?ref=%s' % (self.remote, self.io.path(base, currentDir), sha), logger=self.logger, headers=self.headers)

    for file in fileList.json():
      if file['type'] == 'file':
        result = get(file['download_url'], logger=self.logger, headers=self.headers)
        result.save(self.io.path(destination, currentDir, file['name']))
      elif file['type'] == 'dir':
        self.io.mkdir(self.io.path(destination, currentDir, file['name']))
        self.download(sha=sha, destination=destination, currentDir=self.io.path(currentDir, file['name']), base=base)

    fileList.close()

# requests.py

class Response:
  def __init__(self, f):
    self.raw = f
    self.encoding = "utf-8"
    self._cached = None

  def close(self):
    if self.raw:
      self.raw.close()
      self.raw = None
    self._cached = None

  def save(self, file):
    CHUNK_SIZE = 512 # bytes
    with open(file, 'w') as outfile:
      data = self.raw.read(CHUNK_SIZE)
      while data:
        outfile.write(data)
        data = self.raw.read(CHUNK_SIZE)
      outfile.close()  
    self.close()

  @property
  def content(self):
    if self._cached is None:
      try:
        self._cached = self.raw.read()
      finally:
        self.raw.close()
        self.raw = None
    return self._cached

  @property
  def text(self):
    return str(self.content, self.encoding)

  def json(self):
    import ujson
    return ujson.loads(self.content)


def request(method, url, data=None, json=None, headers={}, stream=None, timeout=5, logger=None):
  import usocket

  log = lambda *args, **kargs: args
  if logger:
    log = logger(append='request')

  try:
    proto, dummy, host, path = url.split("/", 3)
  except ValueError:
    proto, dummy, host = url.split("/", 2)
    path = ""
  if proto == "http:":
    port = 80
  elif proto == "https:":
    import ssl
    port = 443
  else:
    raise ValueError("Unsupported protocol: " + proto)

  if ":" in host:
    host, port = host.split(":", 1)
    port = int(port)

  ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
  ai = ai[0]

  s = usocket.socket(ai[0], ai[1], ai[2])
  s.settimeout(timeout)
  try:
    log('%s %s %s' % (method, host, path), name='connect')
    s.connect(ai[-1])
    if proto == "https:":
      s = ssl.wrap_socket(s, server_hostname=host)
    s.write(b"%s /%s HTTP/1.0\r\n" % (method, path))
    if not "Host" in headers:
      s.write(b"Host: %s\r\n" % host)
    # Iterate over keys to avoid tuple alloc
    for k in headers:
      s.write(k)
      s.write(b": ")
      s.write(headers[k])
      s.write(b"\r\n")
    s.write(b'User-Agent: MicroPython Client\r\n')
    if json is not None:
      assert data is None
      import ujson
      data = ujson.dumps(json)
      s.write(b"Content-Type: application/json\r\n")
    if data:
      s.write(b"Content-Length: %d\r\n" % len(data))
    s.write(b"\r\n")
    if data:
      s.write(data)

    l = s.readline()
    #print(l)
    l = l.split(None, 2)
    status = int(l[1])
    reason = ""
    if len(l) > 2:
      reason = l[2].rstrip()
    while True:
      l = s.readline()
      if not l or l == b"\r\n":
        break
      #print(l)
      if l.startswith(b"Transfer-Encoding:"):
        if b"chunked" in l:
          raise ValueError("Unsupported " + l)
      elif l.startswith(b"Location:") and not 200 <= status <= 299:
        raise NotImplementedError("Redirects not yet supported")
  except OSError:
    s.close()
    raise

  resp = Response(s)
  resp.status_code = status
  resp.reason = reason
  return resp


def head(url, **kw):
  return request("HEAD", url, **kw)

def get(url, **kw):
  return request("GET", url, **kw)

def post(url, **kw):
  return request("POST", url, **kw)

def put(url, **kw):
  return request("PUT", url, **kw)

def patch(url, **kw):
  return request("PATCH", url, **kw)

def delete(url, **kw):
  return request("DELETE", url, **kw)

# logger.py

import re
import io

def config(time=None, enabled=False, include=None, exclude=None):
  logger = Logger(time=time, enabled=enabled, include=include, exclude=exclude)

  def log(*args, append=None, existing='', name=''):
    if append:
      existing = existing + ':' + append
      return lambda *args, append=None, name='': log(*args, name=name, append=append, existing=existing)
    
    name = (existing + ':' + name).lstrip(':').rstrip(':')
    return logger(*args, name=name)
    
  return log

class Logger:
  def __init__(self, time=None, enabled=False, include=None, exclude=None):
    self.print = print
    self.time = time
    self.enabled = enabled
    self.include = list(map(re.compile, include))
    self.exclude = list(map(re.compile, exclude))

  def __call__(self, *args, name=''):
    if not self.enabled:
      return

    included = False
    excluded = False
    for include in self.include:
      if include.search(name):
        included = True
    for exclude in self.exclude:
      if exclude.search(name):
        excluded = True

    if not included and not excluded:
      return
    elif not included and excluded:
      return
    elif included and not excluded:
      pass
    elif included and excluded:
      return

    statement = []
    for arg in args:
      statement.append('%s' % arg)
    
    statement = "[%s][%s] %s" % (self.time.dateTimeIso(), name, ' '.join(statement))
    self.print(statement)
    return statement

# env.py

days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

class Time:
  def __init__(self, time=None):
    self._time = time

  def time(self):
    return self._time.time()

  def sleep(self, n):
    return self._time.sleep(n)

  def localtime(self):
    return self._time.localtime()

  def dateTimeIso(self):
    t = self._time.localtime()  
    return "%d-%02d-%02dT%02d:%02d:%02dZ" % (t[0], t[1], t[2], t[3], t[4], t[5])

  def human(self):
    t = self._time.localtime()  
    return "%s, %d %s %d %02d:%02d:%02d UTC" % (days[t[6]], t[2], months[t[1]-1], t[0], t[3], t[4], t[5])

  def sleep_us(self, n):
    return self._time.sleep_us(n)

# base64.py

import binascii

bytes_types = (bytes, bytearray)  # Types acceptable as binary data

def b64encode(s, altchars=None):
    """Encode a byte string using Base64.
    s is the byte string to encode.  Optional altchars must be a byte
    string of length 2 which specifies an alternative alphabet for the
    '+' and '/' characters.  This allows an application to
    e.g. generate url or filesystem safe Base64 strings.
    The encoded byte string is returned.
    """
    if not isinstance(s, bytes_types):
        raise TypeError("expected bytes, not %s" % s.__class__.__name__)
    # Strip off the trailing newline
    encoded = binascii.b2a_base64(s)[:-1]
    if altchars is not None:
        if not isinstance(altchars, bytes_types):
            raise TypeError("expected bytes, not %s"
                            % altchars.__class__.__name__)
        assert len(altchars) == 2, repr(altchars)
        return encoded.translate(bytes.maketrans(b'+/', altchars))
    return encoded


# main.py

import time, os, machine

led = machine.Pin('LED', machine.Pin.OUT)
led.off()

t = Time(time=time)

# Configure Logger
logger = config(enabled=True, include=['.*'], exclude=[], time=t)
log = logger(append='boot')

loggerOta = logger(append='OTAUpdater')

io = IO(os=os, logger=loggerOta)
github = GitHub(
	io=io,
	remote='https://github.com/lmg-anrath/weatherstation-pico',
	branch='main',
	logger=loggerOta,
)
updater = OTAUpdater(io=io, github=github, logger=loggerOta, machine=machine)

try:
	updater.update()
	time.sleep(30)
	machine.reset()
except Exception as e:
	log('Failed to OTA update:', e)
	time.sleep(30)
	machine.reset()
	pass