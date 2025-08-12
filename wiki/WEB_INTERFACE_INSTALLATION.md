# Web Interface Installation Guide

The LEDMatrix system includes a modern web interface that allows you to control and configure the display remotely. This guide covers installation, configuration, and troubleshooting.

## Overview

The web interface provides:
- **Real-time Display Preview**: See what's currently displayed on the LED matrix
- **Configuration Management**: Edit settings through a web interface
- **On-Demand Controls**: Start specific displays (weather, stocks, sports) on demand
- **Service Management**: Start/stop the main display service
- **System Controls**: Restart, update code, and manage the system
- **API Metrics**: Monitor API usage and system performance
- **Logs**: View system logs in real-time

## Installation

### Prerequisites

- LEDMatrix system already installed and configured (or run `first_time_install.sh` first)
- Python 3.7+ installed
- Network access to the Raspberry Pi

### Step 1: Install the Web Interface Service

1. Navigate to your LEDMatrix directory:
```bash
cd /home/ledpi/LEDMatrix
```

2. Make the install script executable:
```bash
chmod +x install_web_service.sh
```

3. Run the install script with sudo:
```bash
sudo ./install_web_service.sh
```

The script will:
- Copy the web service file to `/etc/systemd/system/`
- Reload systemd to recognize the new service
- Enable the service to start on boot
- Start the service immediately
- Show the service status

**Note**: The first time the service starts, it will automatically:
- Create a Python virtual environment (`venv_web_v2`)
- Install required dependencies (Flask, numpy, requests, Google APIs, Spotify, etc.)
- Install the rgbmatrix module from the local source

This process may take several minutes on the first run as it installs all dependencies needed by the LEDMatrix system.

### Step 2: Configure Web Interface Autostart

1. Edit your configuration file:
```bash
sudo nano config/config.json
```

2. Ensure the web interface autostart is enabled:
```json
{
    "web_display_autostart": true
}
```

3. Save and exit (Ctrl+X, Y, Enter)

### Step 3: Access the Web Interface

Once installed, you can access the web interface at:
```
http://your-pi-ip:5001
```

Replace `your-pi-ip` with your Raspberry Pi's IP address.

## Service Management

### Check Service Status
```bash
sudo systemctl status ledmatrix-web.service
```

### View Service Logs
```bash
journalctl -u ledmatrix-web.service -f
```

### Start/Stop the Service
```bash
# Start the service
sudo systemctl start ledmatrix-web.service

# Stop the service
sudo systemctl stop ledmatrix-web.service

# Restart the service
sudo systemctl restart ledmatrix-web.service
```

### Enable/Disable Autostart
```bash
# Enable autostart on boot
sudo systemctl enable ledmatrix-web.service

# Disable autostart on boot
sudo systemctl disable ledmatrix-web.service
```

## Web Interface Features

### Overview Tab
- System status and uptime
- Current display mode
- API usage metrics
- Quick controls for starting/stopping services

### Configuration Tab
- Edit main configuration settings
- Modify display durations
- Configure sports teams and preferences
- Update API keys and endpoints

### Sports Tab
- Configure individual sports leagues
- Set favorite teams
- Enable/disable specific display modes
- On-demand controls for each sport

### Weather Tab
- Configure weather settings
- Set location and units
- On-demand weather display controls

### Stocks Tab
- Configure stock and crypto symbols
- Set update intervals
- On-demand stock display controls

### On-Demand Controls
- Start specific displays immediately
- Stop on-demand displays
- View current on-demand status

## Troubleshooting

### Web Interface Not Accessible After Restart

**Symptoms:**
- Can't access `http://your-pi-ip:5001` after system restart
- Service appears to be running but web interface doesn't respond

**Diagnosis:**
1. Check if the web service is running:
```bash
sudo systemctl status ledmatrix-web.service
```

2. Verify the service is enabled:
```bash
sudo systemctl is-enabled ledmatrix-web.service
```

3. Check logs for errors:
```bash
journalctl -u ledmatrix-web.service -f
```

4. Ensure `web_display_autostart` is set to `true` in `config/config.json`

**Solutions:**
1. If service is not running, start it:
```bash
sudo systemctl start ledmatrix-web.service
```

2. If service is not enabled, enable it:
```bash
sudo systemctl enable ledmatrix-web.service
```

3. If configuration is incorrect, fix it:
```bash
sudo nano config/config.json
# Set "web_display_autostart": true
```

### Port 5001 Not Accessible

**Symptoms:**
- Connection refused on port 5001
- Service running but can't connect

**Diagnosis:**
1. Check if the service is running on the correct port:
```bash
sudo netstat -tlnp | grep 5001
```

2. Verify firewall settings:
```bash
sudo ufw status
```

3. Check if another service is using port 5001:
```bash
sudo lsof -i :5001
```

**Solutions:**
1. If port is blocked by firewall, allow it:
```bash
sudo ufw allow 5001
```

2. If another service is using the port, stop it or change the web interface port

### Service Fails to Start

**Symptoms:**
- Service shows as failed in systemctl status
- Error messages in logs
- Common errors: 
  - `ModuleNotFoundError: No module named 'numpy'`
  - `ModuleNotFoundError: No module named 'google'`
  - `ModuleNotFoundError: No module named 'spotipy'`

**Diagnosis:**
1. Check service logs:
```bash
journalctl -u ledmatrix-web.service -n 50
```

2. Verify Python dependencies:
```bash
python3 -c "import flask, flask_socketio, PIL, numpy, google, spotipy"
```

3. Check virtual environment:
```bash
ls -la venv_web_v2/
```

**Solutions:**
1. **Most Common Fix**: The service will automatically create the virtual environment and install dependencies on first run. If it fails, restart the service:
```bash
sudo systemctl restart ledmatrix-web.service
```

2. If dependencies are missing, install them manually:
```bash
# Create virtual environment
python3 -m venv venv_web_v2
source venv_web_v2/bin/activate
pip install -r requirements_web_v2.txt

# Install rgbmatrix module
pip install -e rpi-rgb-led-matrix-master/bindings/python
```

3. If virtual environment is corrupted, recreate it:
```bash
rm -rf venv_web_v2
sudo systemctl restart ledmatrix-web.service
```

4. If permissions are wrong, fix them:
```bash
sudo chown -R ledpi:ledpi /home/ledpi/LEDMatrix
sudo chmod +x install_web_service.sh
```

### Missing Dependencies

**Symptoms:**
- Import errors for specific modules (google, spotipy, numpy, etc.)
- Service fails during startup with ModuleNotFoundError

**Cause:**
The web interface imports all LEDMatrix modules, which require the same dependencies as the main system.

**Solution:**
The updated `requirements_web_v2.txt` now includes all necessary dependencies. If you're still seeing issues:

1. Ensure you're using the latest requirements file
2. Recreate the virtual environment:
```bash
rm -rf venv_web_v2
sudo systemctl restart ledmatrix-web.service
```

3. If specific modules are still missing, install them manually:
```bash
source venv_web_v2/bin/activate
pip install google-auth-oauthlib google-api-python-client spotipy
```

### Import Errors

**Symptoms:**
- Service fails with ImportError messages
- Main display service also fails to start

**Cause:**
The source modules try to import from `web_interface_v2`, which can fail when the web interface isn't running.

**Solution:**
The import errors have been fixed with try/except blocks. If you still see issues, ensure all source files have the proper import handling:

```python
try:
    from web_interface_v2 import increment_api_counter
except ImportError:
    # Fallback if web interface is not available
    def increment_api_counter(kind: str, count: int = 1):
        pass
```

## Manual Installation (Alternative)

If the automated installation script doesn't work, you can install manually:

1. Copy the service file:
```bash
sudo cp ledmatrix-web.service /etc/systemd/system/
```

2. Reload systemd:
```bash
sudo systemctl daemon-reload
```

3. Enable and start the service:
```bash
sudo systemctl enable ledmatrix-web.service
sudo systemctl start ledmatrix-web.service
```

## Security Considerations

- The web interface runs on port 5001 by default
- Consider using a reverse proxy (nginx) for production use
- Change default ports if needed
- Use HTTPS in production environments
- Restrict access to trusted networks

## Uninstallation

To remove the web interface service:

1. Stop and disable the service:
```bash
sudo systemctl stop ledmatrix-web.service
sudo systemctl disable ledmatrix-web.service
```

2. Remove the service file:
```bash
sudo rm /etc/systemd/system/ledmatrix-web.service
```

3. Reload systemd:
```bash
sudo systemctl daemon-reload
```

4. Set `web_display_autostart` to `false` in `config/config.json` if desired

## Support

If you continue to have issues:

1. Check the main README.md for general troubleshooting
2. Review the service logs for specific error messages
3. Verify your system meets all prerequisites
4. Ensure all dependencies are properly installed
