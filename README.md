# Weatherstation MicroPython Client

This repository contains the MicroPython script for the Raspberry Pi Pico W weather station.

## Contributing
To contribute to this repository, please create a pull request.

## OTA Update
The microcontroller is capable of updating itself through GitHub releases. It automatically searches for updates when starting up and after every push. If a new latest release is found, the script clones the project into the `/next` directory. Once all the files are downloaded, the current files are removed, and the files from the `/next` directory are moved into the main directory.

**Warning**: If there is an error in the `main.py` or `boot.py` file, the Pico W won't start anymore and will have to be manually updated by connecting it via the MicroUSB port to a computer. After that, the script can be updated using an editor such as [Thonny](https://thonny.org/).

## Installation
To install and run the weather station script on your Raspberry Pi Pico W, clone the repo and upload it via Thonny on the microcontroller.