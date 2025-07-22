#!/bin/bash

# LEDMatrix Cache Permissions Fix Script
# This script fixes permissions on all known cache directories so they're writable by the daemon or current user

echo "Fixing LEDMatrix cache directory permissions..."

CACHE_DIRS=(
    "/var/cache/ledmatrix"
    "/home/ledpi/.ledmatrix_cache"
)

# Get the real user (not root when running with sudo)
REAL_USER=${SUDO_USER:-$USER}
REAL_GROUP=$(id -gn "$REAL_USER")

for CACHE_DIR in "${CACHE_DIRS[@]}"; do
    echo ""
    echo "Checking cache directory: $CACHE_DIR"
    if [ ! -d "$CACHE_DIR" ]; then
        echo "  - Directory does not exist. Skipping."
        continue
    fi
    echo "  - Current permissions:"
    ls -ld "$CACHE_DIR"
    echo "  - Fixing permissions..."
    sudo chmod 777 "$CACHE_DIR"
    sudo chown "$REAL_USER":"$REAL_GROUP" "$CACHE_DIR"
    echo "  - Updated permissions:"
    ls -ld "$CACHE_DIR"
    echo "  - Testing write access as $REAL_USER..."
    if sudo -u "$REAL_USER" test -w "$CACHE_DIR"; then
        echo "    ✓ $CACHE_DIR is now writable by $REAL_USER"
    else
        echo "    ✗ $CACHE_DIR is still not writable by $REAL_USER"
    fi
    echo "  - Permissions fix complete for $CACHE_DIR."
done

echo ""
echo "All cache directory permission fixes attempted."
echo "If you still see errors, check which user is running the LEDMatrix service and ensure it matches the owner above." 