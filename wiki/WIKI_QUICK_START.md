# Quick Start Guide

Get your LEDMatrix system up and running in minutes! This guide covers the essential steps to get your display working.

## Prerequisites

### Hardware Requirements
- Raspberry Pi 3B+ or 4 (NOT Pi 5)
- Adafruit RGB Matrix Bonnet/HAT
- 2x LED Matrix panels (64x32 each)
- 5V 4A DC Power Supply
- Micro SD card (8GB or larger)

### Software Requirements
- Internet connection
- SSH access to Raspberry Pi
- Basic command line knowledge

## Step 1: Prepare Raspberry Pi

### 1.1 Create Raspberry Pi Image
1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Choose your Raspberry Pi model
3. Select "Raspbian OS Lite (64-bit)"
4. Choose your micro SD card
5. Click "Next" then "Edit Settings"

### 1.2 Configure OS Settings
1. **General Tab**:
   - Set hostname: `ledpi`
   - Enable SSH
   - Set username and password
   - Configure WiFi

2. **Services Tab**:
   - Enable SSH
   - Use password authentication

3. Click "Save" and write the image

### 1.3 Boot and Connect
1. Insert SD card into Raspberry Pi
2. Power on and wait for boot
3. Connect via SSH:
   ```bash
   ssh ledpi@ledpi
   ```

## Step 2: Install LEDMatrix

### 2.1 Update System
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-pip cython3 build-essential python3-dev python3-pillow scons
```

### 2.2 Clone Repository
```bash
git clone https://github.com/ChuckBuilds/LEDMatrix.git
cd LEDMatrix
```

### 2.3 Install Dependencies
```bash
sudo pip3 install --break-system-packages -r requirements.txt
```

### 2.4 Install RGB Matrix Library
```bash
cd rpi-rgb-led-matrix-master
sudo make build-python PYTHON=$(which python3)
cd bindings/python
sudo python3 setup.py install
```

### 2.5 Test Installation
```bash
python3 -c 'from rgbmatrix import RGBMatrix, RGBMatrixOptions; print("Success!")'
```

## Step 3: Configure Hardware

### 3.1 Remove Audio Services
```bash
sudo apt-get remove bluez bluez-firmware pi-bluetooth triggerhappy pigpio
```

### 3.2 Blacklist Sound Module
```bash
cat <<EOF | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
blacklist snd_bcm2835
EOF

sudo update-initramfs -u
sudo reboot
```

### 3.3 Optimize Performance
```bash
# Edit cmdline.txt
sudo nano /boot/firmware/cmdline.txt
# Add "isolcpus=3" at the end

# Edit config.txt
sudo nano /boot/firmware/config.txt
# Change "dtparam=audio=on" to "dtparam=audio=off"

sudo reboot
```

## Step 4: Configure LEDMatrix

### 4.1 Basic Configuration
```bash
sudo nano config/config.json
```

**Minimal Configuration**:
```json
{
  "display": {
    "hardware": {
      "rows": 32,
      "cols": 64,
      "chain_length": 2,
      "brightness": 90,
      "hardware_mapping": "adafruit-hat-pwm"
    }
  },
  "clock": {
    "enabled": true
  },
  "weather": {
    "enabled": true
  }
}
```

### 4.2 Set Permissions
```bash
sudo chmod o+x /home/ledpi
```

### 4.3 Setup Cache (Optional)
```bash
chmod +x setup_cache.sh
./setup_cache.sh
```

## Step 5: Test Basic Display

### 5.1 Run Display
```bash
sudo python3 display_controller.py
```

**Expected Behavior**:
- Display should show "Initializing" message
- Clock should display current time
- Weather should show current conditions (if API key configured)

### 5.2 Stop Display
Press `Ctrl+C` to stop the display

## Step 6: Configure APIs (Optional)

### 6.1 Weather API
1. Get free API key from [OpenWeatherMap](https://openweathermap.org/api)
2. Create secrets file:
   ```bash
   cp config/config_secrets.template.json config/config_secrets.json
   sudo nano config/config_secrets.json
   ```
3. Add your API key:
   ```json
   {
     "weather": {
       "api_key": "your_api_key_here"
     }
   }
   ```

### 6.2 Test Weather Display
```bash
sudo python3 display_controller.py
```

## Step 7: Install as Service

### 7.1 Install Service
```bash
chmod +x install_service.sh
sudo ./install_service.sh
```

### 7.2 Control Service
```bash
# Start display
sudo systemctl start ledmatrix.service

# Stop display
sudo systemctl stop ledmatrix.service

# Check status
sudo systemctl status ledmatrix.service

# Enable autostart
sudo systemctl enable ledmatrix.service
```

### 7.3 Convenience Scripts
```bash
chmod +x start_display.sh stop_display.sh

# Start display
sudo ./start_display.sh

# Stop display
sudo ./stop_display.sh
```

## Step 8: Add More Features

### 8.1 Enable Stocks
Edit `config/config.json`:
```json
{
  "stocks": {
    "enabled": true,
    "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA"]
  }
}
```

### 8.2 Enable Sports
```json
{
  "nhl_scoreboard": {
    "enabled": true,
    "favorite_teams": ["TB"]
  }
}
```

### 8.3 Enable Music
```json
{
  "music": {
    "enabled": true,
    "preferred_source": "ytm"
  }
}
```

## Troubleshooting

### Common Issues

1. **No Display**:
   - Check hardware connections
   - Verify `hardware_mapping` setting
   - Ensure power supply is adequate

2. **Permission Errors**:
   ```bash
   sudo chmod o+x /home/ledpi
   ```

3. **Import Errors**:
   ```bash
   cd rpi-rgb-led-matrix-master/bindings/python
   sudo python3 setup.py install
   ```

4. **Cache Issues**:
   ```bash
   chmod +x fix_cache_permissions.sh
   ./fix_cache_permissions.sh
   ```

### Test Individual Components

```bash
# Test clock
python3 -c "from src.clock import Clock; from src.display_manager import DisplayManager; c = Clock(DisplayManager({})); c.display()"

# Test weather (requires API key)
python3 -c "from src.weather_manager import WeatherManager; from src.display_manager import DisplayManager; w = WeatherManager({'weather': {'enabled': True}}, DisplayManager({})); w.display_weather()"
```

## Next Steps

### 1. Configure Your Preferences
- Edit `config/config.json` to enable desired features
- Add API keys to `config/config_secrets.json`
- Customize display durations and settings

### 2. Add Sports Teams
- Configure favorite teams for each sport
- Set up odds ticker for betting information
- Customize display modes

### 3. Set Up Music Integration
- Configure Spotify or YouTube Music
- Set up authentication
- Test music display

### 4. Customize Display
- Add custom text messages
- Configure YouTube stats
- Set up "of the day" content

### 5. Web Interface
- Access web interface at `http://ledpi:5001`
- Control display remotely
- Monitor system status

## Quick Reference

### Essential Commands
```bash
# Start display manually
sudo python3 display_controller.py

# Start service
sudo systemctl start ledmatrix.service

# Stop service
sudo systemctl stop ledmatrix.service

# Check status
sudo systemctl status ledmatrix.service

# View logs
journalctl -u ledmatrix.service

# Edit configuration
sudo nano config/config.json

# Edit secrets
sudo nano config/config_secrets.json
```

### Configuration Files
- `config/config.json` - Main configuration
- `config/config_secrets.json` - API keys
- `ledmatrix.service` - Systemd service

### Important Directories
- `/var/cache/ledmatrix/` - Cache directory
- `assets/` - Logos, fonts, icons
- `src/` - Source code
- `config/` - Configuration files

---

**Congratulations!** Your LEDMatrix system is now running. Check out the other wiki pages for detailed configuration options and advanced features.

## Need Help?

- [YouTube Setup Video](https://www.youtube.com/watch?v=_HaqfJy1Y54)
- [Discord Community](https://discord.com/invite/uW36dVAtcT)
- [Project Website](https://www.chuck-builds.com/led-matrix/)
- [GitHub Issues](https://github.com/ChuckBuilds/LEDMatrix/issues) 