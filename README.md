# LEDMatrix

A modular LED matrix display system for sports information using Raspberry Pi and RGB LED matrices.

# Work in Progress, things may break. I'll try to keep the main branch as stable as I can but this is absolutely in a pre-release state. There are also a ton of commits as it's an easy way to get the changes to the rpi for testing.

## Hardware Requirements
- Raspberry Pi 4 or older
- Adafruit RGB Matrix Bonnet/HAT
- 2x LED Matrix panels (64x32)
- DC Power Supply for Adafruit RGB HAT

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

### Running without Sudo (Optional and not recommended)

To run the display script without `sudo`, the user executing the script needs access to GPIO pins. Add the user to the `gpio` group:

```bash
sudo usermod -a -G gpio <your_username>
# Example for user 'ledpi':
# sudo usermod -a -G gpio ledpi
```

**Important:** You must **reboot** the Raspberry Pi after adding the user to the group for the change to take effect.

You also need to disable hardware pulsing in the code (see `src/display_manager.py`, set `options.disable_hardware_pulsing = True`). This may result in a flickerying display

If configured correctly, you can then run:

```bash
python3 display_controller.py
```

## Running the Display

From the project root directory:
```bash
sudo python3 display_controller.py
```

The display will alternate between showing:
- Current time
- Weather information (requires API key configuration)

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
## API Keys

For sensitive settings like API keys:
1. Copy the template: `cp config/config_secrets.template.json config/config_secrets.json`

2. Edit `config/config_secrets.json` with your API keys via `sudo nano config/config_secrets.json`

3. Ctrl + X to exit, Y to overwrite, Enter to save 

## NHL, NBA, MLB Scoreboard Display

The LEDMatrix system includes a comprehensive NHL, NBA scoreboard display system with three display modes:

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

### YouTube Display Configuration

The YouTube display module shows channel statistics for a specified YouTube channel. To configure it:

1. In `config/config.json`, add the following section:
```json
{
    "youtube": {
        "enabled": true,
        "update_interval": 300  // Update interval in seconds (default: 300)
    }
}
```

2. In `config/config_secrets.json`, add your YouTube API credentials:
```json
{
    "youtube": {
        "api_key": "YOUR_YOUTUBE_API_KEY",
        "channel_id": "YOUR_CHANNEL_ID"
    }
}
```

To get these credentials:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the YouTube Data API v3
4. Create credentials (API key)
5. For the channel ID, you can find it in your YouTube channel URL or use the YouTube Data API to look it up

### Calendar Display Configuration

The calendar display module shows upcoming events from your Google Calendar. To configure it:

1. In `config/config.json`, add the following section:
```json
{
    "calendar": {
        "enabled": true,
        "update_interval": 300,  // Update interval in seconds (default: 300)
        "max_events": 3,         // Maximum number of events to display
        "calendars": ["primary"] // List of calendar IDs to display
    }
}
```

2. Set up Google Calendar API access:
   1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
   2. Create a new project or select an existing one
   3. Enable the Google Calendar API
   4. Create OAuth 2.0 credentials:
      - Application type: Desktop app
      - Download the credentials file as `credentials.json`
   5. Place the `credentials.json` file in your project root directory

3. On first run, the application will:
   - Open a browser window for Google authentication
   - Request calendar read-only access
   - Save the authentication token as `token.pickle`

The calendar display will show:
- Event date and time
- Event title (wrapped to fit the display)
- Up to 3 upcoming events (configurable)

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
- NBA game information

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

## Fonts
You can add any font to the assets/fonts/ folder but they need to be .ttf and updated in display_manager.py

### Music Display Configuration

The Music Display module shows information about the currently playing track from either Spotify or YouTube Music (via the [YouTube Music Desktop App](https://ytmdesktop.app/) companion server).

**Setup Requirements:**

1.  **Spotify:**
    *   Requires a Spotify Premium account (for API access).
    *   You need to register an application on the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) to get API credentials.
        *   Go to the dashboard, log in, and click "Create App".
        *   Give it a name (e.g., "LEDMatrix Display") and description.
        *   For the "Redirect URI", enter `http://localhost:8888/callback` (or another unused port if 8888 is taken). You **must** add this exact URI in your app settings on the Spotify dashboard.
        *   Note down the `Client ID` and `Client Secret`.

2.  **YouTube Music (YTM):**
    *   Requires the [YouTube Music Desktop App](https://ytmdesktop.app/) (YTMD) to be installed and running on a computer on the *same network* as the Raspberry Pi.
    *   In YTMD settings, enable the "Companion Server" under Integration options. Note the URL it provides (usually `http://localhost:9863` if running on the same machine, or `http://<YTMD-Computer-IP>:9863` if running on a different computer).

**Configuration:**

1.  In `config/config_secrets.json`, add your Spotify API credentials under the `music` key:
    ```json
    {
        "music": {
            "SPOTIFY_CLIENT_ID": "YOUR_SPOTIFY_CLIENT_ID_HERE",
            "SPOTIFY_CLIENT_SECRET": "YOUR_SPOTIFY_CLIENT_SECRET_HERE",
            "SPOTIFY_REDIRECT_URI": "http://localhost:8888/callback" 
        }
        // ... other secrets ...
    }
    ```
    *(Ensure the `SPOTIFY_REDIRECT_URI` here matches exactly what you entered in the Spotify Developer Dashboard).*

2.  In `config/config.json`, add/modify the `music` section:
    ```json
    {
        "music": {
            "enabled": true, // Set to false to disable this display
            "preferred_source": "auto", // Options: "auto", "spotify", "ytm"
            "YTM_COMPANION_URL": "http://<YTMD-Computer-IP>:9863", // Replace with actual URL if YTMD is not on the Pi
            "POLLING_INTERVAL_SECONDS": 2 // How often to check for track updates
        }
        // ... other configurations ...
    }
    ```
    Also, ensure the display duration is set in the `display_durations` section:
    ```json
    {
        "display": {
            "display_durations": {
                "music": 20, // Duration in seconds
                // ... other durations ...
            }
        }
        // ... other configurations ...
    }
    ```

**`preferred_source` Options:**

*   `"auto"`: (Default) Checks Spotify first. If Spotify is playing, shows its track. If not, checks YTM.
*   `"spotify"`: Only uses Spotify. Ignores YTM.
*   `"ytm"`: Only uses the YTM Companion Server. Ignores Spotify.

**First Spotify Run (Headless Setup):**

Since the display runs on a headless Raspberry Pi, the Spotify authorization process requires a few manual steps:

1.  **Start the Application:** Run the display controller script (`sudo python3 display_controller.py`).
2.  **Copy Auth URL:** When Spotify needs authorization for the first time (or after a token expires), the application will **print a URL** to the console. Copy this full URL.
3.  **Authorize in Browser (on another device):** Paste the copied URL into a web browser on your computer or phone. Log in to Spotify if prompted and click "Agree" to authorize the application.
4.  **Get Redirected URL:** Your browser will be redirected to a URL starting with your `SPOTIFY_REDIRECT_URI` (e.g., `http://localhost:8888/callback`) followed by `?code=...`. The page will likely show an error like "Site can't be reached" - **this is expected and perfectly fine.**
5.  **Copy Full Redirected URL:** **Immediately copy the complete URL** from your browser's address bar. Make sure you copy the *entire* thing, including the `?code=...` part.
6.  **Paste URL Back to Pi:** Go back to the Raspberry Pi console where the display script is running. It should now be prompting you to "Enter the URL you were redirected to:". **Paste the full URL you just copied** from your browser into the console and press Enter.

The application will then use the provided code to get the necessary tokens and cache them (usually in a `.cache` file). Subsequent runs should not require this process unless the token expires.
