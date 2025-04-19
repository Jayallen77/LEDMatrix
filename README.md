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

## Caching System

The LEDMatrix system includes a robust caching mechanism to optimize API calls and reduce network traffic:

### Cache Location
- Default cache directory: `/tmp/ledmatrix_cache`
- Cache files are stored with proper permissions (755 for directories, 644 for files)
- When running as root/sudo, cache ownership is automatically adjusted to the real user

### Cached Data Types
- Weather data (current conditions and forecasts)
- Stock prices and market data
- Stock news headlines
- NHL game information

### Cache Behavior
- Data is cached based on update intervals defined in `config.json`
- Cache is automatically invalidated when:
  - Update interval has elapsed
  - Market is closed (for stock data)
  - Data has changed significantly
- Failed API calls fall back to cached data when available
- Cache files use atomic operations to prevent corruption

### Cache Management
- Cache files are automatically created and managed
- No manual intervention required
- Cache directory is created with proper permissions on first run
- Temporary files are used for safe updates
- JSON serialization handles all data types including timestamps

## NHL Scoreboard Display

The LEDMatrix system includes a comprehensive NHL scoreboard display system with three display modes:

### Display Modes
- **Live Games**: Shows currently playing games with live scores and game status
- **Recent Games**: Displays completed games from the last 48 hours (configurable)
- **Upcoming Games**: Shows scheduled games for favorite teams

### Features
- Real-time score updates from ESPN API
- Team logo display
- Game status indicators (period, time remaining)
- Power play and penalty information
- Configurable favorite teams
- Automatic game switching
- Built-in caching to reduce API calls
- Test mode for development

### Configuration
In `config.json`, under the `nhl_scoreboard` section:
```json
{
    "nhl_scoreboard": {
        "enabled": true,
        "test_mode": false,
        "update_interval_seconds": 300,
        "live_update_interval": 60,
        "recent_update_interval": 1800,
        "upcoming_update_interval": 1800,
        "recent_game_hours": 48,
        "favorite_teams": ["TB", "DAL"],
        "logo_dir": "assets/sports/nhl_logos",
        "display_modes": {
            "nhl_live": true,
            "nhl_recent": true,
            "nhl_upcoming": true
        }
    }
}
```

### Running without Sudo (Optional)

To run the display script without `sudo`, the user executing the script needs access to GPIO pins. Add the user to the `gpio` group:

This is required to download the Stock Symbol icons into assets/stocks.

```bash
sudo usermod -a -G gpio <your_username>
# Example for user 'ledpi':
# sudo usermod -a -G gpio ledpi
```

**Important:** You must **reboot** the Raspberry Pi after adding the user to the group for the change to take effect.

You also need to disable hardware pulsing in the code (see `src/display_manager.py`, set `options.disable_hardware_pulsing = True`). This has already been done in the repository if you are up-to-date.

If configured correctly, you can then run:

```bash
python3 display_controller.py
```

## Running the Display

(This is how I used to run the command, I may remove this in the future)

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
LEDMatrix/
├── config/                 # Configuration files
│   ├── config.json         # Main configuration
│   └── config_secrets.json # API keys and sensitive data
├── src/                    # Source code
│   ├── config_manager.py   # Configuration loading
│   ├── display_manager.py  # LED matrix display handling
│   ├── clock.py            # Clock display module
│   ├── weather_manager.py  # Weather display module
│   ├── stock_manager.py    # Stock ticker display module
│   └── stock_news_manager.py # Stock news display module
└── display_controller.py   # Main application controller
```
## Project Structure

- `src/`
  - `display_controller.py` - Main application controller
  - `config_manager.py` - Configuration management
  - `display_manager.py` - LED matrix display handling
  - `clock.py` - Clock display module
  - `weather_manager.py` - Weather display module
  - `stock_manager.py` - Stock ticker display module
  - `stock_news_manager.py` - Stock news display module
- `config/`
  - `config.json` - Configuration settings
  - `config_secrets.json` - Private settings (not in git) 


## Fonts
You can add any font to the assets/fonts/ folder but they need to be .ttf and updated in display_manager.py

## Systemd Service Installation

The LEDMatrix can be installed as a systemd service to run automatically at boot and be managed easily. The service runs as root to ensure proper hardware timing access for the LED matrix.

### Installing the Service

1. Make the install script executable:
```bash
chmod +x install_service.sh
```

2. Run the install script with sudo:
```bash
sudo ./install_service.sh
```

The script will:
- Detect your user account and home directory
- Install the service file with the correct paths
- Enable the service to start on boot
- Start the service immediately

### Managing the Service

The following commands are available to manage the service:

```bash
# Stop the display
sudo systemctl stop ledmatrix.service

# Start the display
sudo systemctl start ledmatrix.service

# Check service status
sudo systemctl status ledmatrix.service

# View logs
journalctl -u ledmatrix.service

# Disable autostart
sudo systemctl disable ledmatrix.service

# Enable autostart
sudo systemctl enable ledmatrix.service
```

### Convenience Scripts

Two convenience scripts are provided for easy service management:

- `start_display.sh` - Starts the LED matrix display service
- `stop_display.sh` - Stops the LED matrix display service

Make them executable with:
```bash
chmod +x start_display.sh stop_display.sh
```

Then use them to control the service:
```bash
sudo ./start_display.sh
sudo ./stop_display.sh
```

