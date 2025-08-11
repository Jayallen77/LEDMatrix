# LED Matrix Installation Guide

## Quick Start (Recommended for First-Time Installation)

For a complete first-time installation, run:

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
