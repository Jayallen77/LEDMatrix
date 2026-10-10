# LED Matrix

A Raspberry Pi information display customized for one 64×64 RGB matrix. The working baseline is `cleanup-market-pulse`; the deployed version before this cleanup was `1ea95a2`.

## Current screens

- **Clock:** centered time/date and temperature; time-of-day palettes and temperature-based colors.
- **Weather:** current conditions, humidity, UV, today's high/low, and a separate four-day forecast. Open-Meteo, refreshed every 30 minutes.
- **Market Pulse:** S&P 500, Nasdaq, Dow, optional Bitcoin, and VIX; cached values, trends, market-state indicator, and ten-minute refresh.
- **Colorado sports:** live Avalanche, Nuggets, Broncos, Rockies, and Rapids score cards; 30-second polling and a conditional 20-second rotation slot.
- **Music:** Spotify album artwork, scrolling title/artist, rainbow progress bar, and continuous takeover while playing. Pause grace is three seconds. Spotify behavior and authorization code are unchanged by this cleanup.
- **Calendar:** next-event card. Enabled in configuration, but requires authorization. The renderer currently uses the primary calendar and shows one event.

The legacy NHL/NBA/NFL/MLB/MiLB/NCAA/soccer managers are retained, disabled. Their live-priority behavior and square layouts need review before activation. YouTube Music remains an alternate music source.

Stock news, odds ticker, RSS news, Of the Day, YouTube channel statistics, and custom text have been removed, including their dedicated settings, UI, tests, and content. Shared sports odds support is retained because the legacy league managers depend on it. Removed source/content remains recoverable from Git history.

## Rotation and appearance

Normal cycle: Clock **60s** → current weather **15s** → forecast **10s** → Markets **30s**. Colorado live games add **20s**; authorized Calendar content adds **30s**. Spotify holds the display while playing. Schedule is enabled from **00:01 to 23:59 America/Denver**.

Physical settings remain 64×64, brightness 95, GPIO slowdown 3, PWM bits 9, dither 1, and 120 Hz hardware refresh limit. The clock/weather/sports/music layouts and normal slot durations remain intact. Non-music controller work is paced at up to 20 frames/checks per second; music keeps its existing pacing.

VIX's trend/arrow area now contains a volatility label: **CALM** below 13, **NORM** below 20, **HIGH** below 30, **VERY** below 40, **EXT** at 40 and above. These are this application's display thresholds, not official trading signals. Color reflects the level. VIX measures expected near-term volatility; it is not a stock return. [Cboe explanation](https://www.cboe.com/tradable-products/vix).

Index percentages are measured from the regular session's opening price. Bitcoin's percentage reference comes from Yahoo metadata; its trend uses recent samples. Market instrument selection is fixed. The unused watchlist, chart-toggle, scrolling and dynamic-duration settings have been removed.

## Local dashboard over SSH

No hosting, account, matrix driver, or web package installation is needed. The dashboard uses Python 3.9+ standard-library modules and binds **only to 127.0.0.1:5001**. It reads the service's preview and health files without creating a second hardware controller.

On the Pi:

```bash
cd /home/jayallen7/LEDMatrix
python3 web_interface_v2.py
```

In a separate Mac terminal:

```bash
ssh -N -L 127.0.0.1:5001:127.0.0.1:5001 jayallen7@ledmatrix.local
```

Open **http://127.0.0.1:5001** in your Mac browser. Keep the tunnel open. Use the same port at both ends because the dashboard validates its Host/Origin. Stop a local preview on that port before opening the tunnel.

Quick controls: brightness, schedule/timezone, current module switches, screen durations, weather location/units, Bitcoin inclusion, and refresh intervals. Spotify settings and credentials are outside this interface. Use a full state/region name for weather, such as Colorado.

**Save settings** stores validated values atomically and retains a local `config/config.dashboard-backup.json` rollback copy. It preserves unrelated configuration and never reads the separate secrets file. **Apply saved settings** explicitly restarts the display, applying startup settings consistently. Settings reload in the controller can apply schedule earlier; other settings should be treated as needing Apply. Conflicting saves from outdated browser tabs are rejected.

To make the dashboard start on boot, and optionally permit its Apply button:

```bash
sudo bash install_web_service.sh
sudo bash configure_web_sudo.sh
```

The installer runs the dashboard as the project-owning user. The optional sudo rule permits only restarting `ledmatrix.service`; it does not grant reboot, shutdown, or arbitrary commands. `web_display_autostart` must be true. If restart permission is unavailable, use `sudo systemctl restart ledmatrix.service` in the Pi terminal after saving.

## Configuration and service

- Main settings: `config/config.json`.
- Private credentials: `config/config_secrets.json`, ignored by Git.
- Spotify token cache: `config/spotify_auth.json`, ignored by Git; retain daemon ownership and mode 600.
- Calendar credentials/token are private, ignored files.
- Display entry point: `display_controller.py` → `src/display_controller.py`.
- Dashboard entry points: `web_interface_v2.py`, with compatibility wrappers.
- Preview: `/tmp/led_matrix_preview.png`; status: `/tmp/led_matrix_status.json`.

Never run recursive permission/ownership fixes over the project to repair the dashboard: that can damage Spotify cache access. The dashboard must have write access to the main configuration's parent directory for atomic saves.

New Pi installations use `first_time_install.sh` and display dependencies in `requirements.txt`. Existing working installations should pull the reviewed GitHub branch and use the verification procedure in [Deployment](docs/DEPLOYMENT.md), rather than rerunning the entire installation.

## Verification

Run each test file in its own process; retained tests install simulated dependencies and are not designed to share one discovery process:

```bash
python3 scripts/run_tests.py
```

The regression suite covers playback/controller transitions, current square layouts, data recovery, dashboard validation, HTTP access protection, atomic saves, and deployment safeguards. It does not replace live Pi/hardware testing. Legacy `test/` utilities are manual diagnostics and can call external APIs; they are not part of the offline suite.

Read [Cleanup notes](docs/CLEANUP_NOTES.md) for exact behavior changes and remaining limitations, and [Deployment](docs/DEPLOYMENT.md) for GitHub-to-Pi updates, verification, and recovery.

## Credits

The Python framework credits ChuckBuilds/LEDMatrix; Raspberry Pi matrix control uses hzeller/rpi-rgb-led-matrix. Weather icons derive from basmilius/weather-icons. Data integrations include Open-Meteo, Yahoo Finance, ESPN, Spotify, and Google Calendar. This checkout is separate from the C++ games/automata application zcqsntr/retro_matrix.
