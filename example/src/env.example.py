settings = {
  'wifiAP': 'AccessPointName',
  'wifiPassword': 'password',
  'controllerName': 'weatherstation-test', # Used for DHCP hostname
  'logInclude': ['.*'], # regex supported
  'logExclude': [], # regex supported
  'httpTimeout': 2, # seconds
  'debug': 'True',

  # Auto-Updating
  'githubRemote': 'https://github.com/lmg-anrath/weatherstation-pico',
  'githubRemoteBranch': 'main',
  'githubUsername': '', # Optional: Without this, you may hit API limits
  'githubToken': '', # Optional: Without this, you may hit API limits

  # Station Settings
  'serverURL': 'https://api.wetterstation-lmg.de',
  'stationId': 0,
  'accessToken': 'INSERT_ACCESS_TOKEN',
}