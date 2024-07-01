class IO:
  def __init__(self, os=None):
    self.os = os

  def rmtree(self, path):
    if not self.exists(path):
      return

    print('Removing directory [%s]' % path)
    for entry in self.os.ilistdir(path):
      isDir = entry[1] == 0x4000
      if isDir:
        self.rmtree(path + '/' + entry[0])
      else:
        self.os.remove(path + '/' + entry[0])
    self.os.rmdir(path)

  def move(self, fromPath, toPath):
    print('Moving [%s] to [%s]' % (fromPath, toPath))
    self.os.rename(fromPath, toPath)

  def copy(self, fromPath, toPath):
    print('Copying [%s] to [%s]' % (fromPath, toPath))
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
    print('Making directory [%s]' % path)
    self.os.mkdir(path)

  def readFile(self, path):
    with open(path) as f:
      return f.read()

  def writeFile(self, path, contents):
    print('Writing file %s' % path)
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
  ):
    self.github = github
    self.mainDir = mainDir
    self.nextDir = nextDir
    self.versionFile = versionFile
    self.machine = machine
    self.io = io

  def compare(self):
    print('Pulling down remote... ')
    localSha = None
    try:
      localSha = self.io.readFile('%s/%s' % (self.mainDir, self.versionFile))
    except:
      print('No version file found.', name="compare")

    remoteSha = self.github.sha()

    print('Local SHA: ', localSha)
    print('Remote SHA: ', remoteSha)
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
  def __init__(self, remote=None, io=None, branch='master', username='', token='', base64=None):
    self.remote = remote.rstrip('/').replace('https://github.com', 'https://api.github.com/repos')
    self.io = io
    self.branch = branch

    if username and token:
      self.headers = {'Authentication': 'Basic %s' % base64.b64encode(b'%s:%s' % (username, token))}
    else:
      self.headers = {}

  def sha(self):    
    result = get('%s/commits?per_page=1&sha=%s' % (self.remote, self.branch), headers=self.headers)
    if result.status_code == 200:
      sha = result.json()[0]['sha']
    else:
      raise Exception('Unexpected response from GitHub: %d:%s' % (result.status_code, result.reason))
    result.close()
    return sha
    
  def download(self, sha=None, destination=None, currentDir='', base=''):
    fileList = get('%s/contents/%s?ref=%s' % (self.remote, self.io.path(base, currentDir), sha), headers=self.headers)

    for file in fileList.json():
      if file['type'] == 'file':
        result = get(file['download_url'], headers=self.headers)
        result.save(self.io.path(destination, currentDir, file['name']))
      elif file['type'] == 'dir':
        self.io.mkdir(self.io.path(destination, currentDir, file['name']))
        self.download(sha=sha, destination=destination, currentDir=self.io.path(currentDir, file['name']), base=base)

    fileList.close()




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


def request(method, url, data=None, json=None, headers={}, stream=None, timeout=5):
  import usocket

  log = lambda *args, **kargs: args

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