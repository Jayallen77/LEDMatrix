# LEDMatrix

A modular LED matrix display system for sports information using Raspberry Pi and RGB LED matrices.

## Hardware Requirements
- Raspberry Pi 3 or newer
- Adafruit RGB Matrix Bonnet/HAT
- LED Matrix panels (64x32)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/ChuckBuilds/LEDMatrix.git
cd LEDMatrix
```


2. Install dependencies:
```bash
pip3 install --break-system-packages -r requirements.txt
```
--break-system-packages allows us to install without a virtual environment

## Configuration

1. Copy the example configuration:
```bash
cp config/config.example.json config/config.json
```

2. Edit `config/config.json` with your preferences

## API Keys

For sensitive settings like API keys:
1. Copy the template: `cp config/config_secrets.template.json config/config_secrets.json`

2. Edit `config/config_secrets.json` with your API keys via `sudo nano config/config_secrets.json`

3. Ctrl + X to exit, Y to overwrite, Enter to save 


## Important: Sound Module Configuration

1. Remove unnecessary services that might interfere with the LED matrix:
```bash
sudo apt-get remove bluez bluez-firmware pi-bluetooth triggerhappy pigpio
```

2. Blacklist the sound module:
```bash
cat <<EOF | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
blacklist snd_bcm2835
EOF

sudo update-initramfs -u
```

3. Reboot:
```bash
sudo reboot
```

## Performance Optimization

To reduce flickering and improve display quality:

1. Edit `/boot/firmware/cmdline.txt`:
```bash
sudo nano /boot/firmware/cmdline.txt
```

2. Add `isolcpus=3` at the end of the line

3. Add `dtparam=audio=off` at the end of the line

4. Ctrl + X to exit, Y to save 

5. Save and reboot:
```bash
sudo reboot
```


## Running the Display

From the project root directory:
```bash
sudo python3 display_controller.py
```

The display will alternate between showing:
- Current time
- Weather information (requires API key configuration)

## Development

The project structure is organized as follows:
```
LEDSportsMatrix/
├── config/                 # Configuration files
│   ├── config.json        # Main configuration
│   └── config_secrets.json# API keys and sensitive data
├── src/                   # Source code
│   ├── display_manager.py # LED matrix display handling
│   ├── clock.py          # Clock display module
│   └── weather.py        # Weather display module
└── display_controller.py  # Main entry point
```


## Project Structure

- `src/`
  - `clock.py` - Main clock application
  - `config_manager.py` - Configuration management
  - `display_manager.py` - LED matrix display handling
- `config/`
  - `config.json` - Configuration settings
  - `config_secrets.json` - Private settings (not in git) 


## Fonts
You can add any font to the assets/fonts/ folder but they need to be .ttf and updated in display_manager.py