# Cleanup and reliability changes

This update keeps enabled flags, the current schedule, physical panel settings, normal durations, and retained display layouts. The only intentional visual change is the VIX row: its arrow/trend is replaced by a compact volatility label. Spotify rendering, polling, authentication, and transition behavior are unchanged.

## Removed

Six retired modules: stock news, odds ticker, RSS headlines, Of the Day, YouTube channel statistics, and custom text. Their managers, controller routing, config sections/durations, dedicated content, examples, obsolete tests and docs, and old dashboard templates have been removed. The obsolete web configuration helper has been superseded by validated quick settings. Retained sports' shared OddsManager, sports logos, fonts, hardware library, Calendar, and alternate YouTube Music support remain.

Private credentials are not cleaned or deleted. A former YouTube credential in an existing private secrets file may remain unused; the update does not read or rewrite that file.

## Fixed

- Market failures could set a 30-second retry deadline but then wait the full ten-minute normal interval. Both the scheduler and refresh worker now honor failure backoff, including partial refreshes.
- Weather failures now retry on bounded 30–300-second backoff rather than waiting half an hour. Open-Meteo geocoding narrows city lookup using state/region and country, avoiding silently selecting the first identically named city. [Provider documentation](https://open-meteo.com/en/docs/geocoding-api).
- Weather no longer reads an obsolete API-key file it doesn't need.
- Non-music controller work is capped at 20 checks/frames per second. Spotify's frame-driven scrolling is exempt.
- Critical run-loop errors now propagate as a nonzero process exit so systemd can restart the service.
- Schedule checks use the configured timezone, consistent with the clock, rather than implicitly using the OS timezone.
- Failed config reload retains working controller settings; atomic saves avoid truncated JSON during reload.
- ConfigManager refuses a merged-config save if it cannot safely strip secrets, instead of risking writing credentials into the main file.
- The dashboard has one hardware owner, no credential editing, no package installation during startup, loopback binding, Host/Origin checks, a CSRF token, explicit Save/Apply, and revision conflict checks.
- Optional web sudo permission is limited to display restart. The web installer writes paths for the actual project owner instead of copying a hardcoded ledpi/root service.
- Health publishing runs on a separate one-second worker, so status writes do not run in the drawing thread. A report older than five seconds is not treated as a running display.

## Deliberately retained limitations

- Clock color phases still use their current fixed fallback times. Fetching actual sunrise/sunset would change color-transition timing and is deferred to preserve current appearance.
- Calendar is still enabled but needs authorization. It still reads primary and shows the next event; birthdays selection needs a separate functional change.
- Spotify's existing reauthorization/retry/freshness limitations are untouched at the user's request.
- Disabled legacy sports can still take priority over music if activated. Their square rendering and network behavior need review before enabling them.
- Market symbols and Colorado teams remain fixed. No watchlist/favorites redesign was introduced.
- Nominal refresh intervals do not make upstream data real-time. Cached values and prior trading sessions remain intentional fallbacks.
- CPU/latency savings on actual Pi hardware require measurement after deployment; test success is not a live performance claim.
