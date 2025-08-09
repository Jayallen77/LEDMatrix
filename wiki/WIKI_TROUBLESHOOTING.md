# Troubleshooting Guide

This guide covers common issues you may encounter with your LEDMatrix system and their solutions.

## Quick Diagnosis

### Check System Status
```bash
# Check service status
sudo systemctl status ledmatrix.service

# Check logs
journalctl -u ledmatrix.service -f

# Check display manually
sudo python3 display_controller.py
```

### Check Hardware
```bash
# Check GPIO access
sudo python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); print('GPIO OK')"

# Check RGB matrix library
python3 -c 'from rgbmatrix import RGBMatrix, RGBMatrixOptions; print("RGB Matrix OK")'
```

## Common Issues

### 1. No Display Output

**Symptoms**: LED matrix shows no output or remains dark

**Possible Causes**:
- Hardware connection issues
- Incorrect hardware configuration
- Power supply problems
- GPIO conflicts

**Solutions**:

1. **Check Hardware Connections**:
   ```bash
   # Verify Adafruit HAT is properly seated
   # Check ribbon cable connections
   # Ensure power supply is 5V 4A
   ```

2. **Verify Hardware Configuration**:
   ```json
   {
     "display": {
       "hardware": {
         "rows": 32,
         "cols": 64,
         "chain_length": 2,
         "hardware_mapping": "adafruit-hat-pwm"
       }
     }
   }
   ```

3. **Test Basic Display**:
   ```bash
   # Test minimal configuration
   sudo python3 -c "
   from rgbmatrix import RGBMatrix, RGBMatrixOptions
   options = RGBMatrixOptions()
   options.rows = 32
   options.cols = 64
   options.chain_length = 2
   options.hardware_mapping = 'adafruit-hat-pwm'
   matrix = RGBMatrix(options=options)
   print('Matrix initialized successfully')
   "
   ```

4. **Check Audio Conflicts**:
   ```bash
   # Remove audio services
   sudo apt-get remove bluez bluez-firmware pi-bluetooth triggerhappy pigpio
   
   # Blacklist sound module
   echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
   sudo update-initramfs -u
   sudo reboot
   ```

### 2. Permission Errors

**Symptoms**: `Permission denied` or `Access denied` errors

**Solutions**:

1. **Set Home Directory Permissions**:
   ```bash
   sudo chmod o+x /home/ledpi
   ```

2. **Check File Permissions**:
   ```bash
   # Check config file permissions
   ls -la config/
   
   # Fix permissions if needed
   sudo chown ledpi:ledpi config/config.json
   sudo chmod 644 config/config.json
   ```

3. **Cache Directory Permissions**:
   ```bash
   chmod +x fix_cache_permissions.sh
   ./fix_cache_permissions.sh
   ```

### 3. Import Errors

**Symptoms**: `ModuleNotFoundError` or `ImportError`

**Solutions**:

1. **Reinstall RGB Matrix Library**:
   ```bash
   cd rpi-rgb-led-matrix-master
   sudo make build-python PYTHON=$(which python3)
   cd bindings/python
   sudo python3 setup.py install
   ```

2. **Check Python Path**:
   ```bash
   python3 -c "import sys; print(sys.path)"
   ```

3. **Reinstall Dependencies**:
   ```bash
   sudo pip3 install --break-system-packages -r requirements.txt
   ```

### 4. No Data Displayed

**Symptoms**: Display shows but no content appears

**Solutions**:

1. **Check Configuration**:
   ```bash
   # Validate JSON syntax
   python3 -m json.tool config/config.json
   
   # Check if features are enabled
   grep -A 5 '"enabled"' config/config.json
   ```

2. **Check API Keys**:
   ```bash
   # Verify secrets file exists
   ls -la config/config_secrets.json
   
   # Check API key format
   cat config/config_secrets.json
   ```

3. **Test Individual Components**:
   ```bash
   # Test clock
   python3 -c "from src.clock import Clock; from src.display_manager import DisplayManager; c = Clock(DisplayManager({})); c.display()"
   
   # Test weather (requires API key)
   python3 -c "from src.weather_manager import WeatherManager; from src.display_manager import DisplayManager; w = WeatherManager({'weather': {'enabled': True}}, DisplayManager({})); w.display_weather()"
   ```

### 5. Performance Issues

**Symptoms**: Flickering, slow updates, or system lag

**Solutions**:

1. **Optimize Hardware Settings**:
   ```json
   {
     "display": {
       "hardware": {
         "gpio_slowdown": 3,
         "limit_refresh_rate_hz": 120,
         "pwm_bits": 9
       }
     }
   }
   ```

2. **Reduce Update Frequency**:
   ```json
   {
     "weather": {
       "update_interval": 3600
     },
     "stocks": {
       "update_interval": 1800
     }
   }
   ```

3. **Disable Unused Features**:
   ```json
   {
     "stock_news": {
       "enabled": false
     },
     "odds_ticker": {
       "enabled": false
     }
   }
   ```

### 6. Network/API Issues

**Symptoms**: No weather, stocks, or sports data

**Solutions**:

1. **Check Internet Connection**:
   ```bash
   ping -c 3 google.com
   curl -I https://api.openweathermap.org
   ```

2. **Verify API Keys**:
   ```bash
   # Test OpenWeatherMap API
   curl "http://api.openweathermap.org/data/2.5/weather?q=London&appid=YOUR_API_KEY"
   
   # Test Yahoo Finance
   curl "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
   ```

3. **Check Rate Limits**:
   - OpenWeatherMap: 1000 calls/day
   - Yahoo Finance: 2000 calls/hour
   - ESPN API: No documented limits

### 7. Service Issues

**Symptoms**: Service won't start or stops unexpectedly

**Solutions**:

1. **Check Service Status**:
   ```bash
   sudo systemctl status ledmatrix.service
   sudo journalctl -u ledmatrix.service -f
   ```

2. **Reinstall Service**:
   ```bash
   sudo systemctl stop ledmatrix.service
   sudo systemctl disable ledmatrix.service
   chmod +x install_service.sh
   sudo ./install_service.sh
   ```

3. **Check Service File**:
   ```bash
   cat /etc/systemd/system/ledmatrix.service
   ```

### 8. Cache Issues

**Symptoms**: Data not updating or cache warnings

**Solutions**:

1. **Setup Persistent Cache**:
   ```bash
   chmod +x setup_cache.sh
   ./setup_cache.sh
   ```

2. **Clear Cache**:
   ```bash
   sudo rm -rf /var/cache/ledmatrix/*
   sudo rm -rf /tmp/ledmatrix_cache/*
   ```

3. **Check Cache Permissions**:
   ```bash
   ls -la /var/cache/ledmatrix/
   ls -la /tmp/ledmatrix_cache/
   ```

### 9. Font/Display Issues

**Symptoms**: Text not displaying correctly or missing fonts

**Solutions**:

1. **Check Font Files**:
   ```bash
   ls -la assets/fonts/
   ```

2. **Reinstall Fonts**:
   ```bash
   # Copy fonts from repository
   sudo cp assets/fonts/* /usr/share/fonts/truetype/
   sudo fc-cache -fv
   ```

3. **Test Font Loading**:
   ```bash
   python3 -c "from PIL import ImageFont; font = ImageFont.truetype('assets/fonts/PressStart2P-Regular.ttf', 8); print('Font loaded')"
   ```

### 10. Music Integration Issues

**Symptoms**: Spotify or YouTube Music not working

**Solutions**:

1. **Spotify Authentication**:
   ```bash
   sudo python3 src/authenticate_spotify.py
   sudo chmod 644 config/spotify_auth.json
   ```

2. **YouTube Music Setup**:
   ```bash
   # Ensure YTMD companion server is running
   # Check URL in config
   sudo python3 src/authenticate_ytm.py
   ```

3. **Check Music Configuration**:
   ```json
   {
     "music": {
       "enabled": true,
       "preferred_source": "ytm",
       "YTM_COMPANION_URL": "http://192.168.1.100:9863"
     }
   }
   ```

## Advanced Troubleshooting

### Debug Mode

Enable detailed logging:
```bash
# Edit display_controller.py
# Change logging level to DEBUG
logging.basicConfig(level=logging.DEBUG)
```

### Test Individual Managers

```bash
# Test weather manager
python3 -c "
from src.weather_manager import WeatherManager
from src.display_manager import DisplayManager
config = {'weather': {'enabled': True}}
w = WeatherManager(config, DisplayManager(config))
w.display_weather()
"

# Test stock manager
python3 -c "
from src.stock_manager import StockManager
from src.display_manager import DisplayManager
config = {'stocks': {'enabled': True, 'symbols': ['AAPL']}}
s = StockManager(config, DisplayManager(config))
s.display_stocks()
"
```

### Hardware Diagnostics

```bash
# Check GPIO pins
sudo python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
pins = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
for pin in pins:
    try:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        print(f'Pin {pin}: OK')
    except:
        print(f'Pin {pin}: ERROR')
"
```

### Performance Monitoring

```bash
# Monitor system resources
htop

# Check memory usage
free -h

# Monitor network
iftop

# Check disk usage
df -h
```

## Recovery Procedures

### Complete Reset

If all else fails, perform a complete reset:

1. **Backup Configuration**:
   ```bash
   cp config/config.json config/config.json.backup
   cp config/config_secrets.json config/config_secrets.json.backup
   ```

2. **Reinstall System**:
   ```bash
   sudo systemctl stop ledmatrix.service
   sudo systemctl disable ledmatrix.service
   sudo rm -rf /var/cache/ledmatrix
   sudo rm -rf /tmp/ledmatrix_cache
   ```

3. **Fresh Installation**:
   ```bash
   cd ~
   rm -rf LEDMatrix
   git clone https://github.com/ChuckBuilds/LEDMatrix.git
   cd LEDMatrix
   # Follow installation steps again
   ```

### Emergency Mode

If the system won't start, try emergency mode:

```bash
# Stop all services
sudo systemctl stop ledmatrix.service

# Run with minimal config
sudo python3 display_controller.py --emergency

# Or run individual components
sudo python3 -c "
from src.clock import Clock
from src.display_manager import DisplayManager
c = Clock(DisplayManager({}))
while True:
    c.display()
    import time
    time.sleep(1)
"
```

## Getting Help

### Before Asking for Help

1. **Collect Information**:
   ```bash
   # System info
   uname -a
   cat /etc/os-release
   
   # Service status
   sudo systemctl status ledmatrix.service
   
   # Recent logs
   journalctl -u ledmatrix.service --since "1 hour ago"
   
   # Configuration
   cat config/config.json
   ```

2. **Test Basic Functionality**:
   ```bash
   # Test RGB matrix
   python3 -c 'from rgbmatrix import RGBMatrix, RGBMatrixOptions; print("RGB Matrix OK")'
   
   # Test display
   sudo python3 display_controller.py
   ```

3. **Check Common Issues**:
   - Verify hardware connections
   - Check API keys
   - Validate configuration
   - Test network connectivity

### Where to Get Help

1. **Discord Community**: [ChuckBuilds Discord](https://discord.com/invite/uW36dVAtcT)
2. **GitHub Issues**: [LEDMatrix Issues](https://github.com/ChuckBuilds/LEDMatrix/issues)
3. **YouTube**: [ChuckBuilds Channel](https://www.youtube.com/@ChuckBuilds)
4. **Project Website**: [ChuckBuilds.com](https://www.chuck-builds.com/led-matrix/)

### When Reporting Issues

Include the following information:
- Hardware setup (Pi model, matrix type)
- Software version (OS, Python version)
- Error messages and logs
- Steps to reproduce
- What you've already tried

---

*This troubleshooting guide covers the most common issues. If you're still having problems, check the community resources for additional help.* 