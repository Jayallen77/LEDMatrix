# LED Matrix Installation Guide

## Quick Start (Recommended for First-Time Installation)

# System Setup & Installation

1. Open PowerShell and ssh into your Raspberry Pi with ledpi@ledpi (or Username@Hostname)
```bash
ssh ledpi@ledpi
```

2. Update repositories, upgrade raspberry pi OS, install git
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-pip cython3 build-essential python3-dev python3-pillow scons
```

3. Clone this repository:
```bash
git clone https://github.com/ChuckBuilds/LEDMatrix.git
cd LEDMatrix
```

4. Install dependencies:
```bash
sudo pip3 install --break-system-packages -r requirements.txt
```
--break-system-packages allows us to install without a virtual environment


5. Install rpi-rgb-led-matrix dependencies:
```bash
cd rpi-rgb-led-matrix-master
```
```bash
sudo make build-python PYTHON=$(which python3)
```
```bash
cd bindings/python
sudo python3 setup.py install
```
Test it with:
```bash
python3 -c 'from rgbmatrix import RGBMatrix, RGBMatrixOptions; print("Success!")'
```

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
```

then execute

```bash
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

3. Ctrl + X to exit, Y to save, Enter to Confirm

4. Edit /boot/firmware/config.txt  with
```bash
sudo nano /boot/firmware/config.txt
```  

6. Edit the `dtparam=audio=on` section to `dtparam=audio=off`

7. Ctrl + X to exit, Y to save, Enter to Confirm

8. Save and reboot:
```bash
sudo reboot
```

9. Run the first_time_install.sh with 
```
sudo ./first_time_install.sh
```
to ensure all the permissions are correct.

-----------------------------------------------------------------------------------

## Configuration

1.Edit `config/config.json` with your preferences via `sudo nano config/config.json`

###API Keys

For sensitive settings like API keys:
Copy the template: `cp config/config_secrets.template.json config/config_secrets.json`
Edit `config/config_secrets.json` with your API keys via `sudo nano config/config_secrets.json`
Ctrl + X to exit, Y to overwrite, Enter to Confirm

Everything is configured via `config/config.json` and `config/config_secrets.json`.


For a complete first-time installation, run:

```bash
chmod +x first_time_install.sh
```
then

```bash
sudo ./first_time_install.sh
```

This single script handles everything you need for a new installation.

## Individual Scripts Explained

### **First-Time Installation Scripts**

#### `first_time_install.sh` ⭐ **RECOMMENDED**
- **When to use**: New installations only
- **What it does**: Complete setup including all steps below
- **Usage**: `sudo ./first_time_install.sh`

### **Service Installation Scripts**

#### `install_service.sh`
- **When to use**: Install main LED Matrix display service
- **What it does**: 
  - Creates systemd service for main display
  - Creates systemd service for web interface
  - Enables services to start on boot
- **Usage**: `sudo ./install_service.sh`

#### `install_web_service.sh`
- **When to use**: Install only the web interface service (legacy)
- **What it does**: Installs the web interface systemd service
- **Usage**: `sudo ./install_web_service.sh`
- **Note**: `install_service.sh` now handles this automatically

### **Permission Fix Scripts**

#### `fix_cache_permissions.sh`
- **When to use**: When you see cache permission errors
- **What it does**:
  - Creates cache directories (`/var/cache/ledmatrix`)
  - Sets proper permissions for cache access
  - Creates placeholder logo directories
- **Usage**: `sudo ./fix_cache_permissions.sh`

#### `fix_web_permissions.sh`
- **When to use**: When web interface can't access logs or system commands
- **What it does**:
  - Adds user to `systemd-journal` group (for log access)
  - Adds user to `adm` group (for system access)
  - Sets proper file ownership
- **Usage**: `./fix_web_permissions.sh` (run as regular user)

#### `configure_web_sudo.sh`
- **When to use**: When web interface buttons don't work (sudo password errors)
- **What it does**:
  - Configures passwordless sudo access for web interface
  - Allows web interface to start/stop services without password
- **Usage**: `./configure_web_sudo.sh` (run as regular user)

### **Dependency Installation Scripts**

#### `install_dependencies_apt.py`
- **When to use**: When you want to install packages via apt first, then pip
- **What it does**:
  - Tries to install packages via apt (system packages)
  - Falls back to pip with `--break-system-packages`
  - Handles externally managed Python environments
- **Usage**: `sudo python3 install_dependencies_apt.py`

#### `start_web_v2.py`
- **When to use**: Manual web interface startup
- **What it does**:
  - Installs dependencies
  - Starts web interface directly
  - Includes comprehensive logging
- **Usage**: `python3 start_web_v2.py`

#### `run_web_v2.sh`
- **When to use**: Manual web interface startup (shell script version)
- **What it does**: Same as `start_web_v2.py` but as a shell script
- **Usage**: `./run_web_v2.sh`

### **Utility Scripts**

#### `cleanup_venv.sh`
- **When to use**: Remove virtual environment if you don't want to use it
- **What it does**: Removes `venv_web_v2` directory
- **Usage**: `./cleanup_venv.sh`

#### `start_web_conditionally.py`
- **When to use**: Called by systemd service (don't run manually)
- **What it does**:
  - Checks config for `web_display_autostart` setting
  - Starts web interface only if enabled
  - Used by the systemd service

## Installation Scenarios

### **Scenario 1: Brand New Installation**
```bash
# One command does everything
sudo ./first_time_install.sh
```

### **Scenario 2: Adding Web Interface to Existing Installation**
```bash
# Install web interface dependencies
sudo python3 install_dependencies_apt.py

# Fix permissions
./fix_web_permissions.sh

# Configure sudo access
./configure_web_sudo.sh

# Install services
sudo ./install_service.sh
```

### **Scenario 3: Fixing Permission Issues**
```bash
# Fix cache permissions
sudo ./fix_cache_permissions.sh

# Fix web interface permissions
./fix_web_permissions.sh

# Configure sudo access
./configure_web_sudo.sh

# Log out and back in for group changes to take effect
```

### **Scenario 4: Manual Web Interface Startup**
```bash
# Start web interface manually (for testing)
python3 start_web_v2.py
```

## Post-Installation Steps

### **1. Log Out and Log Back In**
After running permission scripts, you need to log out and back in for group changes to take effect:
```bash
# Or use this command to apply group changes immediately
newgrp systemd-journal
```

### **2. Configure the Web Interface**
Edit `config/config.json` and set:
```json
{
    "web_display_autostart": true
}
```

### **3. Access the Web Interface**
Open your browser and go to:
```
http://your-pi-ip:5001
```

### **4. Test Everything**
- Check if services are running: `sudo systemctl status ledmatrix.service`
- Check web interface: `sudo systemctl status ledmatrix-web.service`
- View logs: `journalctl -u ledmatrix.service -f`

## Troubleshooting

### **Web Interface Not Accessible**
1. Check if service is running: `sudo systemctl status ledmatrix-web.service`
2. Check logs: `journalctl -u ledmatrix-web.service -f`
3. Ensure `web_display_autostart` is `true` in config

### **Permission Errors**
1. Run: `./fix_web_permissions.sh`
2. Run: `./configure_web_sudo.sh`
3. Log out and back in

### **Cache Permission Errors**
1. Run: `sudo ./fix_cache_permissions.sh`

### **Sudo Password Prompts**
1. Run: `./configure_web_sudo.sh`
2. Log out and back in

### **Dependency Installation Errors**
1. Run: `sudo python3 install_dependencies_apt.py`

## Summary

For **first-time installations**: Use `first_time_install.sh`

For **existing installations with issues**: Use the individual permission and configuration scripts as needed.

The `first_time_install.sh` script is designed to handle everything automatically, so you typically only need to run individual scripts if you're troubleshooting specific issues.
