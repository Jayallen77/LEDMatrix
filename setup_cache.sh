#!/bin/bash

# LEDMatrix Cache Setup Script
# This script sets up a persistent cache directory for LEDMatrix

echo "Setting up LEDMatrix persistent cache directory..."

# Create the cache directory
sudo mkdir -p /var/cache/ledmatrix

# Get the real user (not root when running with sudo)
REAL_USER=${SUDO_USER:-$USER}

# Set ownership to the real user
sudo chown $REAL_USER:$REAL_USER /var/cache/ledmatrix

# Set permissions
sudo chmod 755 /var/cache/ledmatrix

echo "Cache directory created: /var/cache/ledmatrix"
echo "Ownership set to: $REAL_USER"
echo "Permissions set to: 755"

# Test if the directory is writable
if [ -w /var/cache/ledmatrix ]; then
    echo "✓ Cache directory is writable"
else
    echo "✗ Cache directory is not writable"
    exit 1
fi

echo ""
echo "Setup complete! LEDMatrix will now use persistent caching."
echo "The cache will survive system restarts." 