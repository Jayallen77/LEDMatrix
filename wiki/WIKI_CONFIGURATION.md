# Configuration Guide

The LEDMatrix system is configured through JSON files that control every aspect of the display. This guide covers all configuration options and their effects.

## Configuration Files

### Main Configuration (`config/config.json`)
Contains all non-sensitive settings for the system.

### Secrets Configuration (`config/config_secrets.json`)
Contains API keys and sensitive credentials.

## System Configuration

### Display Hardware Settings

```json
{
  "display": {
    "hardware": {
      "rows": 32,
      "cols": 64,
      "chain_length": 2,
      "parallel": 1,
      "brightness": 95,
      "hardware_mapping": "adafruit-hat-pwm",
      "scan_mode": 0,
      "pwm_bits": 9,
      "pwm_dither_bits": 1,
      "pwm_lsb_nanoseconds": 130,
      "disable_hardware_pulsing": false,
      "inverse_colors": false,
      "show_refresh_rate": false,
      "limit_refresh_rate_hz": 120
    },
    "runtime": {
      "gpio_slowdown": 3
    }
  }
}
```

**Hardware Settings Explained**:
- **`rows`/`cols`**: Physical LED matrix dimensions (32x64 for 2 panels)
- **`chain_length`**: Number of LED panels connected (2 for 128x32 total)
- **`parallel`**: Number of parallel chains (usually 1)
- **`brightness`**: Display brightness (0-100)
- **`hardware_mapping`**: 
  - `"adafruit-hat-pwm"`: With jumper mod (recommended)
  - `"adafruit-hat"`: Without jumper mod
- **`pwm_bits`**: Color depth (8-11, higher = better colors)
- **`gpio_slowdown`**: Timing adjustment (3 for Pi 3, 4 for Pi 4)

### Display Durations

```json
{
  "display": {
    "display_durations": {
      "clock": 15,
      "weather": 30,
      "stocks": 30,
      "hourly_forecast": 30,
      "daily_forecast": 30,
      "stock_news": 20,
      "odds_ticker": 60,
      "nhl_live": 30,
      "nhl_recent": 30,
      "nhl_upcoming": 30,
      "nba_live": 30,
      "nba_recent": 30,
      "nba_upcoming": 30,
      "nfl_live": 30,
      "nfl_recent": 30,
      "nfl_upcoming": 30,
      "ncaa_fb_live": 30,
      "ncaa_fb_recent": 30,
      "ncaa_fb_upcoming": 30,
      "ncaa_baseball_live": 30,
      "ncaa_baseball_recent": 30,
      "ncaa_baseball_upcoming": 30,
      "calendar": 30,
      "youtube": 30,
      "mlb_live": 30,
      "mlb_recent": 30,
      "mlb_upcoming": 30,
      "milb_live": 30,
      "milb_recent": 30,
      "milb_upcoming": 30,
      "text_display": 10,
      "soccer_live": 30,
      "soccer_recent": 30,
      "soccer_upcoming": 30,
      "ncaam_basketball_live": 30,
      "ncaam_basketball_recent": 30,
      "ncaam_basketball_upcoming": 30,
      "music": 30,
      "of_the_day": 40
    }
  }
}
```

**Duration Settings**:
- Each value controls how long (in seconds) that display mode shows
- Higher values = more time for that content
- Total rotation time = sum of all enabled durations

### System Settings

```json
{
  "web_display_autostart": true,
  "schedule": {
    "enabled": true,
    "start_time": "07:00",
    "end_time": "23:00"
  },
  "timezone": "America/Chicago",
  "location": {
    "city": "Dallas",
    "state": "Texas",
    "country": "US"
  }
}
```

**System Settings Explained**:
- **`web_display_autostart`**: Start web interface automatically
- **`schedule`**: Control when display is active
- **`timezone`**: System timezone for accurate times
- **`location`**: Default location for weather and other location-based services

## Display Manager Configurations

### Clock Configuration

```json
{
  "clock": {
    "enabled": false,
    "format": "%I:%M %p",
    "update_interval": 1
  }
}
```

**Clock Settings**:
- **`enabled`**: Enable/disable clock display
- **`format`**: Time format string (Python strftime)
- **`update_interval`**: Update frequency in seconds

**Common Time Formats**:
- `"%I:%M %p"` → `12:34 PM`
- `"%H:%M"` → `14:34`
- `"%I:%M:%S %p"` → `12:34:56 PM`

### Weather Configuration

```json
{
  "weather": {
    "enabled": false,
    "update_interval": 1800,
    "units": "imperial",
    "display_format": "{temp}°F\n{condition}"
  }
}
```

**Weather Settings**:
- **`enabled`**: Enable/disable weather display
- **`update_interval`**: Update frequency in seconds (1800 = 30 minutes)
- **`units`**: `"imperial"` (Fahrenheit) or `"metric"` (Celsius)
- **`display_format`**: Custom format string for weather display

**Weather Display Modes**:
- Current weather with icon
- Hourly forecast (next 24 hours)
- Daily forecast (next 7 days)

### Stocks Configuration

```json
{
  "stocks": {
    "enabled": false,
    "update_interval": 600,
    "scroll_speed": 1,
    "scroll_delay": 0.01,
    "toggle_chart": false,
    "symbols": ["ASTS", "SCHD", "INTC", "NVDA", "T", "VOO", "SMCI"]
  },
  "crypto": {
    "enabled": false,
    "update_interval": 600,
    "symbols": ["BTC-USD", "ETH-USD"]
  }
}
```

**Stock Settings**:
- **`enabled`**: Enable/disable stock display
- **`update_interval`**: Update frequency in seconds (600 = 10 minutes)
- **`scroll_speed`**: Pixels per scroll update
- **`scroll_delay`**: Delay between scroll updates
- **`toggle_chart`**: Show/hide mini price charts
- **`symbols`**: Array of stock symbols to display

**Crypto Settings**:
- **`enabled`**: Enable/disable crypto display
- **`symbols`**: Array of crypto symbols (use `-USD` suffix)

### Stock News Configuration

```json
{
  "stock_news": {
    "enabled": false,
    "update_interval": 3600,
    "scroll_speed": 1,
    "scroll_delay": 0.01,
    "max_headlines_per_symbol": 1,
    "headlines_per_rotation": 2
  }
}
```

**News Settings**:
- **`enabled`**: Enable/disable news display
- **`update_interval`**: Update frequency in seconds
- **`max_headlines_per_symbol`**: Max headlines per stock
- **`headlines_per_rotation`**: Headlines shown per rotation

### Music Configuration

```json
{
  "music": {
    "enabled": true,
    "preferred_source": "ytm",
    "YTM_COMPANION_URL": "http://192.168.86.12:9863",
    "POLLING_INTERVAL_SECONDS": 1
  }
}
```

**Music Settings**:
- **`enabled`**: Enable/disable music display
- **`preferred_source`**: `"spotify"` or `"ytm"`
- **`YTM_COMPANION_URL`**: YouTube Music companion server URL
- **`POLLING_INTERVAL_SECONDS`**: How often to check for updates

### Calendar Configuration

```json
{
  "calendar": {
    "enabled": false,
    "credentials_file": "credentials.json",
    "token_file": "token.pickle",
    "update_interval": 3600,
    "max_events": 3,
    "calendars": ["birthdays"]
  }
}
```

**Calendar Settings**:
- **`enabled`**: Enable/disable calendar display
- **`credentials_file`**: Google API credentials file
- **`token_file`**: Authentication token file
- **`update_interval`**: Update frequency in seconds
- **`max_events`**: Maximum events to display
- **`calendars`**: Array of calendar IDs to monitor

## Sports Configurations

### Common Sports Settings

All sports managers share these common settings:

```json
{
  "nhl_scoreboard": {
    "enabled": false,
    "live_priority": true,
    "live_game_duration": 20,
    "show_odds": true,
    "test_mode": false,
    "update_interval_seconds": 3600,
    "live_update_interval": 30,
    "recent_update_interval": 3600,
    "upcoming_update_interval": 3600,
    "show_favorite_teams_only": true,
    "favorite_teams": ["TB"],
    "logo_dir": "assets/sports/nhl_logos",
    "show_records": true,
    "display_modes": {
      "nhl_live": true,
      "nhl_recent": true,
      "nhl_upcoming": true
    }
  }
}
```

**Common Sports Settings**:
- **`enabled`**: Enable/disable this sport
- **`live_priority`**: Give live games priority over other content
- **`live_game_duration`**: How long to show live games
- **`show_odds`**: Display betting odds (where available)
- **`test_mode`**: Use test data instead of live API
- **`update_interval_seconds`**: How often to fetch new data
- **`live_update_interval`**: How often to update live games
- **`show_favorite_teams_only`**: Only show games for favorite teams
- **`favorite_teams`**: Array of team abbreviations
- **`logo_dir`**: Directory containing team logos
- **`show_records`**: Display team win/loss records
- **`display_modes`**: Enable/disable specific display modes

### Football-Specific Settings

NFL and NCAA Football use game-based fetching:

```json
{
  "nfl_scoreboard": {
    "enabled": false,
    "recent_games_to_show": 0,
    "upcoming_games_to_show": 2,
    "favorite_teams": ["TB", "DAL"]
  }
}
```

**Football Settings**:
- **`recent_games_to_show`**: Number of recent games to display
- **`upcoming_games_to_show`**: Number of upcoming games to display

### Soccer Configuration

```json
{
  "soccer_scoreboard": {
    "enabled": false,
    "recent_game_hours": 168,
    "favorite_teams": ["LIV"],
    "leagues": ["eng.1", "esp.1", "ger.1", "ita.1", "fra.1", "uefa.champions", "usa.1"]
  }
}
```

**Soccer Settings**:
- **`recent_game_hours`**: Hours back to show recent games
- **`leagues`**: Array of league codes to monitor

## Odds Ticker Configuration

```json
{
  "odds_ticker": {
    "enabled": false,
    "show_favorite_teams_only": true,
    "games_per_favorite_team": 1,
    "max_games_per_league": 5,
    "show_odds_only": false,
    "sort_order": "soonest",
    "enabled_leagues": ["nfl", "mlb", "ncaa_fb", "milb"],
    "update_interval": 3600,
    "scroll_speed": 1,
    "scroll_delay": 0.01,
    "loop": true,
    "future_fetch_days": 50,
    "show_channel_logos": true
  }
}
```

**Odds Ticker Settings**:
- **`enabled`**: Enable/disable odds ticker
- **`show_favorite_teams_only`**: Only show odds for favorite teams
- **`games_per_favorite_team`**: Games per team to show
- **`max_games_per_league`**: Maximum games per league
- **`enabled_leagues`**: Leagues to include in ticker
- **`sort_order`**: `"soonest"` or `"latest"`
- **`future_fetch_days`**: Days ahead to fetch games
- **`show_channel_logos`**: Display broadcast network logos

## Custom Display Configurations

### Text Display

```json
{
  "text_display": {
    "enabled": false,
    "text": "Subscribe to ChuckBuilds",
    "font_path": "assets/fonts/press-start-2p.ttf",
    "font_size": 8,
    "scroll": true,
    "scroll_speed": 40,
    "text_color": [255, 0, 0],
    "background_color": [0, 0, 0],
    "scroll_gap_width": 32
  }
}
```

**Text Display Settings**:
- **`enabled`**: Enable/disable text display
- **`text`**: Text to display
- **`font_path`**: Path to TTF font file
- **`font_size`**: Font size in pixels
- **`scroll`**: Enable/disable scrolling
- **`scroll_speed`**: Scroll speed in pixels
- **`text_color`**: RGB color for text
- **`background_color`**: RGB color for background
- **`scroll_gap_width`**: Gap between text repetitions

### YouTube Display

```json
{
  "youtube": {
    "enabled": false,
    "update_interval": 3600
  }
}
```

**YouTube Settings**:
- **`enabled`**: Enable/disable YouTube stats
- **`update_interval`**: Update frequency in seconds

### Of The Day Display

```json
{
  "of_the_day": {
    "enabled": true,
    "display_rotate_interval": 20,
    "update_interval": 3600,
    "subtitle_rotate_interval": 10,
    "category_order": ["word_of_the_day", "slovenian_word_of_the_day", "bible_verse_of_the_day"],
    "categories": {
      "word_of_the_day": {
        "enabled": true,
        "data_file": "of_the_day/word_of_the_day.json",
        "display_name": "Word of the Day"
      },
      "slovenian_word_of_the_day": {
        "enabled": true,
        "data_file": "of_the_day/slovenian_word_of_the_day.json",
        "display_name": "Slovenian Word of the Day"
      },
      "bible_verse_of_the_day": {
        "enabled": true,
        "data_file": "of_the_day/bible_verse_of_the_day.json",
        "display_name": "Bible Verse of the Day"
      }
    }
  }
}
```

**Of The Day Settings**:
- **`enabled`**: Enable/disable of the day display
- **`display_rotate_interval`**: How long to show each category
- **`update_interval`**: Update frequency in seconds
- **`subtitle_rotate_interval`**: How long to show subtitles
- **`category_order`**: Order of categories to display
- **`categories`**: Configuration for each category

## API Configuration (config_secrets.json)

### Weather API

```json
{
  "weather": {
    "api_key": "your_openweathermap_api_key"
  }
}
```

### YouTube API

```json
{
  "youtube": {
    "api_key": "your_youtube_api_key",
    "channel_id": "your_channel_id"
  }
}
```

### Music APIs

```json
{
  "music": {
    "SPOTIFY_CLIENT_ID": "your_spotify_client_id",
    "SPOTIFY_CLIENT_SECRET": "your_spotify_client_secret",
    "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8888/callback"
  }
}
```

## Configuration Best Practices

### Performance Optimization

1. **Update Intervals**: Balance between fresh data and API limits
   - Weather: 1800 seconds (30 minutes)
   - Stocks: 600 seconds (10 minutes)
   - Sports: 3600 seconds (1 hour)
   - Music: 1 second (real-time)

2. **Display Durations**: Balance content visibility
   - Live sports: 20-30 seconds
   - Weather: 30 seconds
   - Stocks: 30-60 seconds
   - Clock: 15 seconds

3. **Favorite Teams**: Reduce API calls by focusing on specific teams

### Caching Strategy

```json
{
  "cache_settings": {
    "persistent_cache": true,
    "cache_directory": "/var/cache/ledmatrix",
    "fallback_cache": "/tmp/ledmatrix_cache"
  }
}
```

### Error Handling

- Failed API calls use cached data
- Network timeouts are handled gracefully
- Invalid data is filtered out
- Logging provides debugging information

## Configuration Validation

### Required Settings

1. **Hardware Configuration**: Must match your physical setup
2. **API Keys**: Required for enabled services
3. **Location**: Required for weather and timezone
4. **Team Abbreviations**: Must match official team codes

### Optional Settings

1. **Display Durations**: Defaults provided if missing
2. **Update Intervals**: Defaults provided if missing
3. **Favorite Teams**: Can be empty for all teams
4. **Custom Text**: Can be any string

## Configuration Examples

### Minimal Configuration

```json
{
  "display": {
    "hardware": {
      "rows": 32,
      "cols": 64,
      "chain_length": 2,
      "brightness": 90,
      "hardware_mapping": "adafruit-hat-pwm"
    }
  },
  "clock": {
    "enabled": true
  },
  "weather": {
    "enabled": true
  }
}
```

### Full Sports Configuration

```json
{
  "nhl_scoreboard": {
    "enabled": true,
    "favorite_teams": ["TB", "DAL"],
    "show_favorite_teams_only": true
  },
  "nba_scoreboard": {
    "enabled": true,
    "favorite_teams": ["DAL"],
    "show_favorite_teams_only": true
  },
  "nfl_scoreboard": {
    "enabled": true,
    "favorite_teams": ["TB", "DAL"],
    "show_favorite_teams_only": true
  },
  "odds_ticker": {
    "enabled": true,
    "enabled_leagues": ["nfl", "nba", "mlb"]
  }
}
```

### Financial Focus Configuration

```json
{
  "stocks": {
    "enabled": true,
    "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
    "update_interval": 300
  },
  "crypto": {
    "enabled": true,
    "symbols": ["BTC-USD", "ETH-USD", "ADA-USD"]
  },
  "stock_news": {
    "enabled": true,
    "update_interval": 1800
  }
}
```

## Troubleshooting Configuration

### Common Issues

1. **No Display**: Check hardware configuration
2. **No Data**: Verify API keys and network
3. **Wrong Times**: Check timezone setting
4. **Performance Issues**: Reduce update frequencies

### Validation Commands

```bash
# Validate JSON syntax
python3 -m json.tool config/config.json

# Check configuration loading
python3 -c "from src.config_manager import ConfigManager; c = ConfigManager(); print('Config valid')"
```

---

*For detailed information about specific display managers, see the [Display Managers](WIKI_DISPLAY_MANAGERS.md) page.* 