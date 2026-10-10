# Updating the existing Pi

The implementation is first prepared and tested locally. This document does not imply the Pi or GitHub has been updated.

## Preferred workflow: GitHub to Pi

Publish the tested changes from the Mac checkout to GitHub's `cleanup-market-pulse` branch. The Pi and Mac working baseline use this branch; `main` is older. No laptop package installation or file-transfer utility is required.

In the existing **Pi SSH terminal**, run the block below. It refuses a different branch or local changes, backs up the main configuration, pulls a fast-forward update, runs the offline regression suite, and restarts the display only if those steps pass:

```bash
(
    set -e
    cd /home/jayallen7/LEDMatrix
    if [ "$(git branch --show-current)" != "cleanup-market-pulse" ]; then
        echo "Unexpected branch. Stop and review before updating."
        exit 1
    fi
    if [ -n "$(git status --porcelain)" ]; then
        echo "Local changes found. Stop and review before updating."
        git status --short
        exit 1
    fi
    mkdir -p .deployment-backups
    chmod 700 .deployment-backups
    UPDATE_STAMP="$(date +%Y%m%d-%H%M%S)"
    git rev-parse HEAD > ".deployment-backups/$UPDATE_STAMP-before-commit.txt"
    cp -p config/config.json ".deployment-backups/$UPDATE_STAMP-config.json"
    git pull --ff-only origin cleanup-market-pulse
    python3 scripts/run_tests.py
    sudo systemctl restart ledmatrix.service
    sudo systemctl status ledmatrix.service --no-pager
    git log -1 --format='%h %s'
)
```

Keep the terminal output for verification. If a pull or test fails, the block stops before restarting. Do not reset, stash, force-pull, or install dependencies automatically; review the failure first. The existing display process may continue using its loaded code until restart, so complete verification promptly.

The main configuration is tracked in Git even though `.gitignore` lists it. This first pull applies the cleaned reviewed configuration. The reported Pi baseline matched that configuration. If any tracked setting changed since the report, the clean-worktree guard stops for reconciliation. Future dashboard changes to tracked configuration also require reconciliation before another pull. Private secrets and Spotify authorization caches are ignored files and are outside this update.

After the display starts successfully, install the dashboard service **on the Pi**:

```bash
sudo bash configure_web_sudo.sh
sudo bash install_web_service.sh
systemctl is-active ledmatrix.service ledmatrix-web.service
```

This sets up service files and permission for the Apply button; it does not install Python packages. The dashboard uses the existing Pi Python standard library. Its optional sudo rule permits only restarting the display service. System files `/etc/systemd/system/ledmatrix-web.service` and `/etc/sudoers.d/ledmatrix_web` are outside the project configuration backup.

## Optional bundle tooling

The repository also contains checksummed bundle/rollback helpers in `scripts/deploy_to_pi.py` and `scripts/apply_update.py`. These were used for an offline update/rollback rehearsal. They are optional and are not part of the preferred GitHub-to-Pi workflow above. Do not combine the two update methods on the same checkout without reconciling local changes.

## SSH dashboard access

After deployment, use a separate Mac terminal:

```bash
ssh -N -L 127.0.0.1:5001:127.0.0.1:5001 jayallen7@ledmatrix.local
```

Open http://127.0.0.1:5001. The Pi service is intentionally inaccessible directly from other computers without the tunnel. Keep the tunnel running. The dashboard needs `web_display_autostart: true` for service startup, as in the current configuration.

## Recovery

The Git workflow records the previous commit and main configuration in `.deployment-backups/`. If live verification fails, keep the logs and review a rollback using that recorded commit. Avoid a blind hard reset, which can discard later settings or code changes. Removed project modules remain recoverable from Git history. Dashboard systemd/sudoers files need separate inspection if reverting its implementation.

## Physical verification

Confirm the existing clock/weather appearance and timings, the VIX label, Colorado live content when a game is available, and Spotify play/pause/stop transitions. Verify dashboard Save/Apply and inspect `sudo journalctl -u ledmatrix.service --since '10 minutes ago' --no-pager` if something is unexpected. Tests use simulated services and cannot establish Pi performance or upstream API availability.
