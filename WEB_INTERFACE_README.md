# LED Matrix Web Interface

A user-friendly web interface for configuring the LED Matrix display system. This interface replaces raw JSON editing with intuitive forms, toggles, and dropdowns to prevent configuration errors.

## Features

### 🎛️ **Form-Based Configuration**
- **Toggles**: Easy on/off switches for enabling features
- **Dropdowns**: Predefined options for hardware settings
- **Input Fields**: Validated text and number inputs
- **Descriptions**: Helpful tooltips explaining each setting

### 📱 **Organized Tabs**
1. **Schedule**: Set display on/off times
2. **Display Settings**: Hardware configuration (rows, columns, brightness, etc.)
3. **Sports**: Configure favorite teams for MLB, NFL, NBA
4. **Weather**: Location and weather display settings
5. **Stocks & Crypto**: Stock symbols and cryptocurrency settings
6. **Music**: Music source configuration (YouTube Music, Spotify)
7. **Calendar**: Google Calendar integration settings
8. **API Keys**: Secure storage for service API keys
9. **Actions**: System control (start/stop display, reboot, etc.)

### 🔒 **Security Features**
- Password fields for API keys
- Secure form submission
- Input validation
- Error handling with user-friendly messages

### 🎨 **Modern UI**
- Responsive design
- Clean, professional appearance
- Intuitive navigation
- Visual feedback for actions

## Getting Started

### Prerequisites
- Python 3.7+
- Flask
- LED Matrix system running on Raspberry Pi

### Installation

1. **Install Dependencies**
   ```bash
   pip install flask requests
   ```

2. **Start the Web Interface**
   ```bash
   python3 web_interface.py
   ```

3. **Access the Interface**
   - Open a web browser
   - Navigate to: `http://[PI_IP_ADDRESS]:5000`
   - Example: `http://192.168.1.100:5000`

## Configuration Guide

### Schedule Tab
Configure when the display should be active:
- **Enable Schedule**: Toggle to turn automatic scheduling on/off
- **Display On Time**: When the display should turn on (24-hour format)
- **Display Off Time**: When the display should turn off (24-hour format)

### Display Settings Tab
Configure the LED matrix hardware:
- **Rows**: Number of LED rows (typically 32)
- **Columns**: Number of LED columns (typically 64)
- **Chain Length**: Number of LED panels chained together
- **Parallel**: Number of parallel chains
- **Brightness**: LED brightness (1-100)
- **Hardware Mapping**: Type of LED matrix hardware
- **GPIO Slowdown**: GPIO slowdown factor (0-5)

### Sports Tab
Configure sports team preferences:
- **Enable Leagues**: Toggle MLB, NFL, NBA on/off
- **Favorite Teams**: Enter team abbreviations (e.g., "TB, DAL")
- **Team Examples**:
  - MLB: TB (Tampa Bay), TEX (Texas)
  - NFL: TB (Tampa Bay), DAL (Dallas)
  - NBA: DAL (Dallas), BOS (Boston)

### Weather Tab
Configure weather display settings:
- **Enable Weather**: Toggle weather display on/off
- **City**: Your city name
- **State**: Your state/province
- **Units**: Fahrenheit or Celsius
- **Update Interval**: How often to update weather data (seconds)

### Stocks & Crypto Tab
Configure financial data display:
- **Enable Stocks**: Toggle stock display on/off
- **Stock Symbols**: Enter symbols (e.g., "AAPL, GOOGL, MSFT")
- **Enable Crypto**: Toggle cryptocurrency display on/off
- **Crypto Symbols**: Enter symbols (e.g., "BTC-USD, ETH-USD")
- **Update Interval**: How often to update data (seconds)

### Music Tab
Configure music display settings:
- **Enable Music Display**: Toggle music display on/off
- **Preferred Source**: YouTube Music or Spotify
- **YouTube Music Companion URL**: URL for YTM companion app
- **Polling Interval**: How often to check for music updates (seconds)

### Calendar Tab
Configure Google Calendar integration:
- **Enable Calendar**: Toggle calendar display on/off
- **Max Events**: Maximum number of events to display
- **Update Interval**: How often to update calendar data (seconds)
- **Calendars**: Comma-separated calendar names

### API Keys Tab
Securely store API keys for various services:
- **Weather API**: OpenWeatherMap API key
- **YouTube API**: YouTube API key and channel ID
- **Spotify API**: Client ID, Client Secret, and Redirect URI

### Actions Tab
Control the LED Matrix system:
- **Start Display**: Start the LED display service
- **Stop Display**: Stop the LED display service
- **Enable Auto-Start**: Enable automatic startup on boot
- **Disable Auto-Start**: Disable automatic startup
- **Reboot System**: Restart the Raspberry Pi
- **Download Latest Update**: Pull latest code from Git

## API Keys Setup

### OpenWeatherMap API
1. Go to [OpenWeatherMap](https://openweathermap.org/api)
2. Sign up for a free account
3. Get your API key
4. Enter it in the Weather API section

### YouTube API
1. Go to [Google Cloud Console](https://console.developers.google.com/)
2. Create a new project
3. Enable YouTube Data API v3
4. Create credentials (API key)
5. Enter the API key and your channel ID

### Spotify API
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Get your Client ID and Client Secret
4. Set the Redirect URI to: `http://127.0.0.1:8888/callback`

## Testing

Run the test script to verify the web interface is working:

```bash
python3 test_web_interface.py
```

## Troubleshooting

### Common Issues

1. **Web interface not accessible**
   - Check if the service is running: `python3 web_interface.py`
   - Verify the IP address and port
   - Check firewall settings

2. **Configuration not saving**
   - Check file permissions on config files
   - Verify JSON syntax in logs
   - Ensure config directory exists

3. **Actions not working**
   - Check if running on Raspberry Pi
   - Verify sudo permissions
   - Check system service status

### Error Messages

- **"Invalid JSON format"**: Check the configuration syntax
- **"Permission denied"**: Run with appropriate permissions
- **"Connection refused"**: Check if the service is running

## File Structure

```
LEDMatrix/
├── web_interface.py          # Main Flask application
├── templates/
│   └── index.html           # Web interface template
├── config/
│   ├── config.json          # Main configuration
│   └── config_secrets.json  # API keys (secure)
└── test_web_interface.py    # Test script
```

## Security Notes

- API keys are stored securely in `config_secrets.json`
- The web interface runs on port 5000 by default
- Consider using HTTPS in production
- Regularly update API keys and credentials

## Contributing

When adding new configuration options:

1. Update the HTML template with appropriate form fields
2. Add JavaScript handlers for form submission
3. Update the Flask backend to handle new fields
4. Add validation and error handling
5. Update this documentation

## License

This project is part of the LED Matrix display system. 