#!/bin/bash

# Exit on error
set -e

# Get the actual user who invoked sudo
if [ -n "$SUDO_USER" ]; then
    ACTUAL_USER="$SUDO_USER"
else
    ACTUAL_USER=$(whoami)
fi

# Get the home directory of the actual user
USER_HOME=$(eval echo ~$ACTUAL_USER)

echo "Installing LED Matrix Display Service for user: $ACTUAL_USER"
echo "Using home directory: $USER_HOME"

# Create a temporary service file with the correct paths
sed "s|/home/ledpi|$USER_HOME|g" ledmatrix.service > /tmp/ledmatrix.service.tmp

# Copy the service file to the systemd directory
sudo cp /tmp/ledmatrix.service.tmp /etc/systemd/system/ledmatrix.service

# Clean up
rm /tmp/ledmatrix.service.tmp

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable ledmatrix.service

# Start the service now
sudo systemctl start ledmatrix.service

# Check the status
echo "Service status:"
sudo systemctl status ledmatrix.service

echo ""
echo "LED Matrix Display Service has been installed and started."
echo ""
echo "To stop the display when you SSH in:"
echo "  sudo systemctl stop ledmatrix.service"
echo ""
echo "To check if the service is running:"
echo "  sudo systemctl status ledmatrix.service"
echo ""
echo "To restart the service:"
echo "  sudo systemctl restart ledmatrix.service"
echo ""
echo "To view logs:"
echo "  journalctl -u ledmatrix.service"
echo ""
echo "To disable autostart:"
echo "  sudo systemctl disable ledmatrix.service" 