#!/bin/bash
# Avoid recursive ownership/mode changes that can break Spotify's daemon-owned cache.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ ! -w "$PROJECT_DIR/config" ] || [ ! -r "$PROJECT_DIR/config/config.json" ]; then
    echo "Run the dashboard as the project owner; config/ must be writable."
    exit 1
fi
echo "Settings access is ready. For the Apply button, run: sudo bash configure_web_sudo.sh"
