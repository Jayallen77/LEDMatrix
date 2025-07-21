#!/bin/bash

# LEDMatrix Cache Permissions Fix Script
# This script fixes permissions on the cache directory so it's writable by the daemon user

echo "Fixing LEDMatrix cache directory permissions..."

CACHE_DIR="/var/cache/ledmatrix"

if [ ! -d "$CACHE_DIR" ]; then
    echo "Cache directory does not exist. Run setup_cache.sh first."
    exit 1
fi

# Get the real user (not root when running with sudo)
REAL_USER=${SUDO_USER:-$USER}

echo "Current cache directory permissions:"
ls -la "$CACHE_DIR"

echo ""
echo "Fixing permissions..."

# Make the directory writable by the daemon user (which the system runs as)
sudo chmod 777 "$CACHE_DIR"

# Also set ownership to daemon:daemon to match the cache files
sudo chown daemon:daemon "$CACHE_DIR"

echo ""
echo "Updated cache directory permissions:"
ls -la "$CACHE_DIR"

echo ""
echo "Testing write access..."
if sudo -u daemon test -w "$CACHE_DIR"; then
    echo "✓ Cache directory is now writable by daemon user"
else
    echo "✗ Cache directory is still not writable by daemon user"
    exit 1
fi

echo ""
echo "Permissions fix complete! LEDMatrix should now use persistent caching."
echo "The cache will survive system restarts." 