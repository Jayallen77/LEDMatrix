#!/bin/bash
# Install only the dashboard service; do not reinstall display dependencies.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$EUID" -ne 0 ]; then
    echo "Run sudo bash install_web_service.sh"
    exit 1
fi
DASHBOARD_USER="${SUDO_USER:-$(stat -c '%U' "$PROJECT_DIR/config/config.json")}"
if [ "$DASHBOARD_USER" = root ]; then
    echo "Run this installer with sudo from the account that owns the project."
    exit 1
fi
UNIT_TMP="$(mktemp)"
trap 'rm -f "$UNIT_TMP"' EXIT
cat > "$UNIT_TMP" <<EOF
[Unit]
Description=LED Matrix Local Settings Dashboard
After=network.target

[Service]
Type=simple
User=$DASHBOARD_USER
WorkingDirectory="$PROJECT_DIR"
ExecStart=/usr/bin/python3 "$PROJECT_DIR/start_web_conditionally.py"
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
install -m 644 "$UNIT_TMP" /etc/systemd/system/ledmatrix-web.service
systemctl daemon-reload
systemctl enable ledmatrix-web.service
systemctl restart ledmatrix-web.service
systemctl status ledmatrix-web.service --no-pager
