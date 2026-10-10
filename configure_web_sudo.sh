#!/bin/bash
# Optional: allow the dashboard to apply settings by restarting only the display.
set -euo pipefail
DASHBOARD_USER="${SUDO_USER:-$(id -un)}"
if [ "$DASHBOARD_USER" = root ]; then
    echo "Run sudo bash configure_web_sudo.sh from your normal Pi account."
    exit 1
fi
SYSTEMCTL_BIN="$(command -v systemctl)"
SUDOERS_TMP="$(mktemp)"
trap 'rm -f "$SUDOERS_TMP"' EXIT
printf '%s ALL=(root) NOPASSWD: %s restart ledmatrix.service\n' "$DASHBOARD_USER" "$SYSTEMCTL_BIN" > "$SUDOERS_TMP"
sudo visudo -cf "$SUDOERS_TMP"
sudo install -m 440 "$SUDOERS_TMP" /etc/sudoers.d/ledmatrix_web
echo "Dashboard can now apply settings. Only display restart is permitted."
