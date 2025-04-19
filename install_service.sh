#!/bin/bash

# Exit on error
set -e

# Get the current user
CURRENT_USER=$(whoami)

echo "Installing LED Matrix Display Service for user: $CURRENT_USER..."

# Copy the service file to the systemd directory
sudo cp ledmatrix.service /etc/systemd/system/

# Create a systemd override to set the user
sudo mkdir -p /etc/systemd/system/ledmatrix.service.d/
echo "[Service]" | sudo tee /etc/systemd/system/ledmatrix.service.d/override.conf
echo "User=$CURRENT_USER" | sudo tee -a /etc/systemd/system/ledmatrix.service.d/override.conf

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