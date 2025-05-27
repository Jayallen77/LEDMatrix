# LEDMatrix
An LED matrix display system that provides real-time information display capabilities for various data sources. The system is highly configurable and supports multiple display modes that can be enabled or disabled based on user preferences.

Special Thanks to:
- Hzeller @ https://github.com/hzeller/rpi-rgb-led-matrix for his groundwork on controlling an LED Matrix from the Raspberry Pi
- Basmilius @ https://github.com/basmilius/weather-icons/ for his free and extensive weather icons
- nvstly @ https://github.com/nvstly/icons for their Stock and Crypto Icons
- ESPN for their sports API
- Yahoo Finance for their Stock API
- OpenWeatherMap for their Free Weather API
- Randomwire @ https://www.thingiverse.com/thing:5169867 for their 4mm Pixel Pitch LED Matrix Stand 


## Core Features
Modular, rotating Displays that can be individually enabled or disabled per the user's needs with some configuration around display durations, teams, stocks, weather, timezones, and more. Displays include:

### Time and Weather
- Real-time clock display
- ![DSC01342](https://github.com/user-attachments/assets/a3c9d678-b812-4977-8aa8-f0c3d1663f05)
- Current Weather, Daily Weather, and Hourly Weather Forecasts
- ![DSC01332](https://github.com/user-attachments/assets/19b2182c-463c-458a-bf4e-5d04acd8d120)
- ![DSC01335](https://github.com/user-attachments/assets/4bcae193-cbea-49da-aac4-72d6fc9a7acd)
- ![DSC01333](https://github.com/user-attachments/assets/f0be5cf2-600e-4fae-a956-97327ef11d70)

- Google Calendar event display

### Sports Information
The system supports live, recent, and upcoming game information for multiple sports leagues:
- NHL (Hockey)
- ![DSC01347](https://github.com/user-attachments/assets/854b3e63-43f5-4bf9-8fed-14a96cf3e7dd)
- ![DSC01339](https://github.com/user-attachments/assets/13aacd18-c912-439b-a2f4-82a7ec7a2831)
- ![DSC01338](https://github.com/user-attachments/assets/8fbc8251-f573-4e2b-b981-428d6ff3ac61)
- NBA (Basketball)
- MLB (Baseball)
- ![DSC01346](https://github.com/user-attachments/assets/fb82b662-98f8-499c-aaf8-f9241dc3d634)
- ![DSC01341](https://github.com/user-attachments/assets/f79cbf2e-f3b4-4a14-8482-01f2a3d53963)
- NFL (Football)
- NCAA Football
- NCAA Men's Basketball
- NCAA Men's Baseball
- Soccer
- (Note, some of these sports seasons were not active during development and might need fine tuning when games are active)

### Financial Information
- Near real-time stock & crypto price updates
- Stock news headlines
- Customizable stock & crypto watchlists
- ![DSC01317](https://github.com/user-attachments/assets/01a01ecf-bef1-4f61-a7b2-d6658622f73d)


### Entertainment
- Music playback information from multiple sources:
  - Spotify integration
  - YouTube Music integration
- Album art display
- Now playing information with scrolling text
- ![DSC01354](https://github.com/user-attachments/assets/41b9e45f-8946-4213-87d2-6657b7f05757)


### Custom Display Features
- Custom Text display 
- Youtube Subscriber Count Display
- ![DSC01319](https://github.com/user-attachments/assets/4d80fe99-839b-4d5e-9908-149cf1cce107)
- Font testing and customization
- Configurable display modes

## System Architecture

The system is built with a modular architecture that allows for easy extension and maintenance:
- `DisplayController`: Main orchestrator managing all display modes
- Individual managers for each feature (sports, weather, music, etc.)
- Separate authentication handlers for different services
- Configurable display modes and rotation patterns from one file - config.json

## Configuration

The system can be configured through a JSON configuration file that allows users to:
- Enable/disable specific features
- Set display durations
- Configure API keys and endpoints
- Customize display modes and rotation patterns
- Set preferred music sources
- Configure sports team preferences


## Hardware Requirements
- Raspberry Pi 3b or 4 (NOT RPI5!)
-- Amazon Affiliate Link: Raspberry Pi 4 4GB (https://amzn.to/4dJixuX)
- Adafruit RGB Matrix Bonnet/HAT 
-- https://www.adafruit.com/product/3211
- 2x LED Matrix panels (64x32) (Designed for 128x32 but has a lot of dynamic scaling elements that could work on a variety of displays, pixel pitch is user preference)
-- https://www.adafruit.com/product/2278 
- 5V 4A DC Power Supply for Adafruit RGB HAT
-- https://www.adafruit.com/product/1466

## Optional but recommended mod for Adafruit RGB Matrix Bonnet
- By soldering a jumper between pins 4 and 18, you can run a specialized command for polling the matrix display. This provides better brightness, less flicker, and better color.
- If you do the mod, we will use the command: --led-gpio-mapping=adafruit-hat-pwm, otherwise just use --led-gpio-mapping=adafruit-hat
- More information available: https://github.com/hzeller/rpi-rgb-led-matrix/tree/master?tab=readme-ov-file
![DSC00079](https://github.com/user-attachments/assets/4282d07d-dfa2-4546-8422-ff1f3a9c0703)



Overall 2 Matrix display with Rpi connected.
![DSC00073](https://github.com/user-attachments/assets/a0e167ae-37c6-4db9-b9ce-a2b957ca1a67)




-----------------------------------------------------------------------------------

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

# Configuration

1.Edit `config/config.json` with your preferences via `sudo nano config/config.json`


## API Keys

For sensitive settings like API keys:
1. Copy the template: `cp config/config_secrets.template.json config/config_secrets.json`

2. Edit `config/config_secrets.json` with your API keys via `sudo nano config/config_secrets.json`

3. Ctrl + X to exit, Y to overwrite, Enter to save 

## NHL, NBA, MLB, Soccer, NCAA FB, NCAA Men's Baseball, NCAA Men's Basketball Scoreboard Display
The LEDMatrix system includes a comprehensive scoreboard display system with three display modes:

### Display Modes
- **Live Games**: Shows currently playing games with live scores and game status
- **Recent Games**: Displays completed games from the last 48 hours (configurable)
- **Upcoming Games**: Shows scheduled games for favorite teams

### Features
- Real-time score updates from ESPN API
- Team logo display
- Game status indicators (period, time remaining)
- Configurable favorite teams
- Automatic game switching
- Built-in caching to reduce API calls
- Test mode for development


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

### Music Display Configuration

The Music Display module shows information about the currently playing track from either Spotify or YouTube Music (via the [YouTube Music Desktop App](https://ytmdesktop.app/) companion server).

**Setup Requirements:**

1.  **Spotify:**
    *   Requires a Spotify account (for API access).
    *   You need to register an application on the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/) to get API credentials.
        *   Go to the dashboard, log in, and click "Create App".
        *   Give it a name (e.g., "LEDMatrix Display") and description.
        *   For the "Redirect URI", enter `http://127.0.0.1:8888/callback` (or another unused port if 8888 is taken). You **must** add this exact URI in your app settings on the Spotify dashboard.
        *   Note down the `Client ID` and `Client Secret`.

2.  **YouTube Music (YTM):**
    *   Requires the [YouTube Music Desktop App](https://ytmdesktop.app/) (YTMD) to be installed and running on a computer on the *same network* as the Raspberry Pi.
    *   In YTMD settings, enable the "Companion Server" under Integration options. Note the URL it provides (usually `http://localhost:9863` if running on the same machine, or `http://<YTMD-Computer-IP>:9863` if running on a different computer).

**`preferred_source` Options:**
*   `"spotify"`: Only uses Spotify. Ignores YTM.
*   `"ytm"`: Only uses the YTM Companion Server. Ignores Spotify.

## Spotify Authentication for Music Display

If you are using the Spotify integration to display currently playing music, you will need to authenticate with Spotify. This project uses an authentication flow that requires a one-time setup. Due to how the display controller script may run with specific user permissions (even when using `sudo`), the following steps are crucial:

1.  **Initial Setup & Secrets:**
    *   Ensure you have your Spotify API Client ID, Client Secret, and Redirect URI.
    *   The Redirect URI should be set to `http://127.0.0.1:8888/callback` in your Spotify Developer Dashboard.
    *   Copy `config/config_secrets.template.json` to `config/config_secrets.json`.
    *   Edit `config/config_secrets.json` and fill in your Spotify credentials under the `"music"` section:
        ```json
        {
          "music": {
            "SPOTIFY_CLIENT_ID": "YOUR_SPOTIFY_CLIENT_ID",
            "SPOTIFY_CLIENT_SECRET": "YOUR_SPOTIFY_CLIENT_SECRET",
            "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8888/callback"
          }
        }
        ```

2.  **Run the Authentication Script:**
    *   Execute the authentication script using `sudo`. This is important because it needs to create an authentication cache file (`spotify_auth.json`) that will be owned by root.
        ```bash
        sudo python3 src/authenticate_spotify.py
        ```
    *   The script will output a URL. Copy this URL and paste it into a web browser on any device.
    *   Log in to Spotify and authorize the application.
    *   Your browser will be redirected to a URL starting with `http://127.0.0.1:8888/callback?code=...`. It will likely show an error page like "This site can't be reached" – this is expected.
    *   Copy the **entire** redirected URL from your browser's address bar.
    *   Paste this full URL back into the terminal when prompted by the script.
    *   If successful, it will indicate that token info has been cached.

3.  **Adjust Cache File Permissions:**
    *   The main display script (`display_controller.py`), even when run with `sudo`, might operate with an effective User ID (e.g., UID 1 for 'daemon') that doesn't have permission to read the `spotify_auth.json` file created by `root` (which has -rw------- permissions by default).
    *   To allow the display script to read this cache file, change its permissions:
        ```bash
        sudo chmod 644 config/spotify_auth.json
        ```
    This makes the file readable by all users, including the effective user of the display script.

4.  **Run the Main Application:**
    *   You should now be able to run your main display controller script using `sudo`:
        ```bash
        sudo python3 display_controller.py
        ```
    *   The Spotify client should now authenticate successfully using the cached token.

**Why these specific permissions steps?**

The `authenticate_spotify.py` script, when run with `sudo`, creates `config/spotify_auth.json` owned by `root`. If the main `display_controller.py` (also run with `sudo`) effectively runs as a different user (e.g., UID 1/daemon, as observed during troubleshooting), that user won't be able to read the `root`-owned file unless its permissions are relaxed (e.g., to `644`). The `chmod 644` command allows the owner (`root`) to read/write, and everyone else (including the `daemon` user) to read.

### Music Display (YouTube Music)

The system can display currently playing music information from YouTube Music Desktop (YTMD) via its Companion server API.

**Setup:**

1.  **Enable Companion Server in YTMD:**
    *   In the YouTube Music Desktop application, go to `Settings` -> `Integrations`.
    *   Enable the "Companion Server".
    *   Note the IP address and Port it's listening on (default is usually `http://localhost:9863`), you'll need to know the local ip address if playing music on a device other than your rpi (probably are).

2.  **Configure `config/config.json`:**
    *   Update the `music` section in your `config/config.json`:
        ```json
        "music": {
            "enabled": true,
            "preferred_source": "ytm",
            "YTM_COMPANION_URL": "http://YOUR_YTMD_IP_ADDRESS:PORT", // e.g., "http://localhost:9863" or "http://192.168.1.100:9863"
            "POLLING_INTERVAL_SECONDS": 1
        }
        ```

3.  **Initial Authentication & Token Storage:**
    *   The first time you run ` python3 src/authenticate_ytm.py` after enabling YTM, it will attempt to register itself with the YTMD Companion Server.
    *   You will see log messages in the terminal prompting you to **approve the "LEDMatrixController" application within the YouTube Music Desktop app.** You typically have 30 seconds to do this.
    *   Once approved, an authentication token is saved to your `config/ytm_auth.json`.
    *   This ensures the `ledpi` user owns the config directory and file, and has the necessary write permissions.

**Troubleshooting:**
*   "No authorized companions" in YTMD: Ensure you've approved the `LEDMatrixController` in YTMD settings after the first run.
*   Connection errors: Double-check the `YTM_COMPANION_URL` in `config.json` matches what YTMD's companion server is set to.
*   Ensure your firewall (Windows Firewall) allows YTM Desktop app to access local networks.

## Project Structure

```
LEDMatrix/
├── assets/                  # Static assets like fonts and icons
├── config/                  # Configuration files
│   ├── config.json         # Main configuration
│   └── config_secrets.template.json # Template for API keys and sensitive data
├── src/                    # Source code
│   ├── display_controller.py    # Main application controller
│   ├── config_manager.py        # Configuration management
│   ├── display_manager.py       # LED matrix display handling
│   ├── cache_manager.py         # Caching system for API data
│   ├── clock.py                 # Clock display module
│   ├── weather_manager.py       # Weather display module
│   ├── weather_icons.py         # Weather icon definitions
│   ├── stock_manager.py         # Stock ticker display module
│   ├── stock_news_manager.py    # Stock news display module
│   ├── music_manager.py         # Music display orchestration
│   ├── spotify_client.py        # Spotify API integration
│   ├── ytm_client.py           # YouTube Music integration
│   ├── authenticate_spotify.py  # Spotify authentication
│   ├── authenticate_ytm.py      # YouTube Music authentication
│   ├── calendar_manager.py      # Google Calendar integration
│   ├── youtube_display.py       # YouTube channel stats display
│   ├── text_display.py          # Custom text display module
│   ├── font_test_manager.py     # Font testing utility
│   ├── nhl_managers.py          # NHL game display
│   ├── nba_managers.py          # NBA game display
│   ├── mlb_manager.py           # MLB game display
│   ├── nfl_managers.py          # NFL game display
│   ├── soccer_managers.py       # Soccer game display
│   ├── ncaa_fb_managers.py      # NCAA Football display
│   ├── ncaa_baseball_managers.py # NCAA Baseball display
│   └── ncaam_basketball_managers.py # NCAA Basketball display
├── rpi-rgb-led-matrix-master/  # LED matrix library
├── run.py                      # Main entry point
├── display_controller.py       # Legacy entry point
├── calendar_registration.py    # Calendar API setup
├── run_font_test.py           # Font testing entry point
├── ChuckBuilds.py             # Custom display module
├── start_display.sh           # Service start script
├── stop_display.sh            # Service stop script
├── install_service.sh         # Service installation script
├── ledmatrix.service          # Systemd service definition
├── requirements.txt           # Python dependencies
└── config.example.json        # Example configuration
```

The project is organized into several key components:

- `src/`: Contains all the Python source code, organized by feature
- `config/`: Configuration files for the application
- `assets/`: Static assets like fonts and icons
- `rpi-rgb-led-matrix-master/`: The LED matrix control library
- Various utility scripts for running and managing the service

Each display module in `src/` is responsible for a specific feature (weather, sports, music, etc.) and follows a consistent pattern of data fetching, processing, and display rendering.

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
- ESPN game information

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
You can add any font to the assets/fonts/ folder but they need to be .ttf or .btf(less support) and updated in display_manager.py

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
