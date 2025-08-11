#!/bin/bash

# LED Matrix First-Time Installation Script
# This script handles the complete setup for a new LED Matrix installation

set -e

echo "=========================================="
echo "LED Matrix First-Time Installation Script"
echo "=========================================="
echo ""

# Get the actual user who invoked sudo
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
else
    ACTUAL_USER=$(whoami)
fi

# Get the home directory of the actual user
USER_HOME=$(eval echo ~$ACTUAL_USER)

# Determine the Project Root Directory (where this script is located)
PROJECT_ROOT_DIR=$(cd "$(dirname "$0")" && pwd)

echo "Detected user: $ACTUAL_USER"
echo "User home directory: $USER_HOME"
echo "Project directory: $PROJECT_ROOT_DIR"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "✓ Running as root (required for installation)"
else
    echo "✗ This script must be run as root (use sudo)"
    echo "Usage: sudo ./first_time_install.sh"
    exit 1
fi

echo ""
echo "This script will perform the following steps:"
echo "1. Install system dependencies"
echo "2. Fix cache permissions"
echo "3. Install main LED Matrix service"
echo "4. Install web interface service"
echo "5. Configure web interface permissions"
echo "6. Configure passwordless sudo access"
echo "7. Set up proper file ownership"
echo "8. Test the installation"
echo ""

# Ask for confirmation
read -p "Do you want to proceed with the installation? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 0
fi

echo ""
echo "Step 1: Installing system dependencies..."
echo "----------------------------------------"

# Update package list
apt update

# Install required system packages
echo "Installing Python packages and dependencies..."
apt install -y python3-pip python3-venv python3-dev python3-pil python3-pil.imagetk

# Install additional system dependencies that might be needed
echo "Installing additional system dependencies..."
apt install -y git curl wget unzip

echo "✓ System dependencies installed"
echo ""

echo "Step 2: Fixing cache permissions..."
echo "----------------------------------"

# Run the cache permissions fix
if [ -f "$PROJECT_ROOT_DIR/fix_cache_permissions.sh" ]; then
    echo "Running cache permissions fix..."
    bash "$PROJECT_ROOT_DIR/fix_cache_permissions.sh"
    echo "✓ Cache permissions fixed"
else
    echo "⚠ Cache permissions script not found, creating cache directories manually..."
    mkdir -p /var/cache/ledmatrix
    chown "$ACTUAL_USER:$ACTUAL_USER" /var/cache/ledmatrix
    chmod 777 /var/cache/ledmatrix
    echo "✓ Cache directories created manually"
fi
echo ""

echo "Step 3: Installing main LED Matrix service..."
echo "---------------------------------------------"

# Run the main service installation
if [ -f "$PROJECT_ROOT_DIR/install_service.sh" ]; then
    echo "Running main service installation..."
    bash "$PROJECT_ROOT_DIR/install_service.sh"
    echo "✓ Main LED Matrix service installed"
else
    echo "✗ Main service installation script not found"
    exit 1
fi
echo ""

echo "Step 4: Installing web interface dependencies..."
echo "------------------------------------------------"

# Install web interface dependencies
echo "Installing Python dependencies for web interface..."
cd "$PROJECT_ROOT_DIR"

# Try to install dependencies using the smart installer if available
if [ -f "$PROJECT_ROOT_DIR/install_dependencies_apt.py" ]; then
    echo "Using smart dependency installer..."
    python3 "$PROJECT_ROOT_DIR/install_dependencies_apt.py"
else
    echo "Using pip to install dependencies..."
    python3 -m pip install --break-system-packages -r requirements_web_v2.txt
    
    # Install rgbmatrix module from local source
    echo "Installing rgbmatrix module..."
    python3 -m pip install --break-system-packages -e rpi-rgb-led-matrix-master/bindings/python
fi

echo "✓ Web interface dependencies installed"
echo ""

echo "Step 5: Configuring web interface permissions..."
echo "------------------------------------------------"

# Add user to required groups
echo "Adding user to systemd-journal group..."
usermod -a -G systemd-journal "$ACTUAL_USER"

echo "Adding user to adm group..."
usermod -a -G adm "$ACTUAL_USER"

echo "✓ User added to required groups"
echo ""

echo "Step 6: Configuring passwordless sudo access..."
echo "------------------------------------------------"

# Create sudoers configuration for the web interface
echo "Creating sudoers configuration..."
SUDOERS_FILE="/etc/sudoers.d/ledmatrix_web"

# Get command paths
PYTHON_PATH=$(which python3)
SYSTEMCTL_PATH=$(which systemctl)
REBOOT_PATH=$(which reboot)
POWEROFF_PATH=$(which poweroff)
BASH_PATH=$(which bash)

# Create sudoers content
cat > /tmp/ledmatrix_web_sudoers << EOF
# LED Matrix Web Interface passwordless sudo configuration
# This allows the web interface user to run specific commands without a password

# Allow $ACTUAL_USER to run specific commands without a password for the LED Matrix web interface
$ACTUAL_USER ALL=(ALL) NOPASSWD: $REBOOT_PATH
$ACTUAL_USER ALL=(ALL) NOPASSWD: $POWEROFF_PATH
$ACTUAL_USER ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH start ledmatrix.service
$ACTUAL_USER ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH stop ledmatrix.service
$ACTUAL_USER ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH restart ledmatrix.service
$ACTUAL_USER ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH enable ledmatrix.service
$ACTUAL_USER ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH disable ledmatrix.service
$ACTUAL_USER ALL=(ALL) NOPASSWD: $SYSTEMCTL_PATH status ledmatrix.service
$ACTUAL_USER ALL=(ALL) NOPASSWD: $PYTHON_PATH $PROJECT_ROOT_DIR/display_controller.py
$ACTUAL_USER ALL=(ALL) NOPASSWD: $BASH_PATH $PROJECT_ROOT_DIR/start_display.sh
$ACTUAL_USER ALL=(ALL) NOPASSWD: $BASH_PATH $PROJECT_ROOT_DIR/stop_display.sh
EOF

# Install the sudoers file
cp /tmp/ledmatrix_web_sudoers "$SUDOERS_FILE"
chmod 440 "$SUDOERS_FILE"
rm /tmp/ledmatrix_web_sudoers

echo "✓ Passwordless sudo access configured"
echo ""

echo "Step 7: Setting proper file ownership..."
echo "----------------------------------------"

# Set ownership of project files to the user
echo "Setting project file ownership..."
chown -R "$ACTUAL_USER:$ACTUAL_USER" "$PROJECT_ROOT_DIR"

# Set proper permissions for config files
if [ -f "$PROJECT_ROOT_DIR/config/config.json" ]; then
    chmod 644 "$PROJECT_ROOT_DIR/config/config.json"
    echo "✓ Config file permissions set"
fi

echo "✓ File ownership configured"
echo ""

echo "Step 8: Testing the installation..."
echo "----------------------------------"

# Test sudo access
echo "Testing sudo access..."
if sudo -u "$ACTUAL_USER" sudo -n systemctl status ledmatrix.service > /dev/null 2>&1; then
    echo "✓ Sudo access test passed"
else
    echo "⚠ Sudo access test failed - may need to log out and back in"
fi

# Test journal access
echo "Testing journal access..."
if sudo -u "$ACTUAL_USER" journalctl --no-pager --lines=1 > /dev/null 2>&1; then
    echo "✓ Journal access test passed"
else
    echo "⚠ Journal access test failed - may need to log out and back in"
fi

# Check service status
echo "Checking service status..."
if systemctl is-active --quiet ledmatrix.service; then
    echo "✓ Main LED Matrix service is running"
else
    echo "⚠ Main LED Matrix service is not running"
fi

if systemctl is-active --quiet ledmatrix-web.service; then
    echo "✓ Web interface service is running"
else
    echo "⚠ Web interface service is not running"
fi

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "IMPORTANT: For group changes to take effect, you need to:"
echo "1. Log out and log back in to your SSH session, OR"
echo "2. Run: newgrp systemd-journal"
echo ""
echo "After logging back in, you can:"
echo ""
echo "Access the web interface at:"
echo "  http://your-pi-ip:5001"
echo ""
echo "Check service status:"
echo "  sudo systemctl status ledmatrix.service"
echo "  sudo systemctl status ledmatrix-web.service"
echo ""
echo "View logs:"
echo "  journalctl -u ledmatrix.service -f"
echo "  journalctl -u ledmatrix-web.service -f"
echo ""
echo "Control the display:"
echo "  sudo systemctl start ledmatrix.service"
echo "  sudo systemctl stop ledmatrix.service"
echo ""
echo "Enable/disable web interface autostart:"
echo "  Edit config/config.json and set 'web_display_autostart': true"
echo ""
echo "Configuration files:"
echo "  Main config: config/config.json"
echo "  Secrets: config/config_secrets.json (create from template if needed)"
echo ""
echo "Enjoy your LED Matrix display!"
