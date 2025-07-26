# Display Managers Guide

The LEDMatrix system uses a modular architecture where each feature is implemented as a separate "Display Manager". This guide covers all available display managers and their configuration options.

## Overview

Each display manager is responsible for:
1. **Data Fetching**: Retrieving data from APIs or local sources
2. **Data Processing**: Transforming raw data into displayable format
3. **Display Rendering**: Creating visual content for the LED matrix
4. **Caching**: Storing data to reduce API calls
5. **Configuration**: Managing settings and preferences

## Core Display Managers

### 🕐 Clock Manager (`src/clock.py`)
**Purpose**: Displays current time in various formats

**Configuration**:
```json
{
  "clock": {
    "enabled": true,
    "format": "%I:%M %p",
    "update_interval": 1
  }
}
```

**Features**:
- Real-time clock display
- Configurable time format
- Automatic timezone handling
- Minimal resource usage

**Display Format**: `12:34 PM`

---

### 🌤️ Weather Manager (`src/weather_manager.py`)
**Purpose**: Displays current weather, hourly forecasts, and daily forecasts

**Configuration**:
```json
{
  "weather": {
    "enabled": true,
    "update_interval": 1800,
    "units": "imperial",
    "display_format": "{temp}°F\n{condition}"
  }
}
```

**Features**:
- Current weather conditions
- Hourly forecast (next 24 hours)
- Daily forecast (next 7 days)
- Weather icons and animations
- UV index display
- Wind speed and direction
- Humidity and pressure data

**Display Modes**:
- Current weather with icon
- Hourly forecast with temperature trend
- Daily forecast with high/low temps

---

### 💰 Stock Manager (`src/stock_manager.py`)
**Purpose**: Displays stock prices, crypto prices, and financial data

**Configuration**:
```json
{
  "stocks": {
    "enabled": true,
    "update_interval": 600,
    "scroll_speed": 1,
    "scroll_delay": 0.01,
    "toggle_chart": false,
    "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA"]
  },
  "crypto": {
    "enabled": true,
    "update_interval": 600,
    "symbols": ["BTC-USD", "ETH-USD"]
  }
}
```

**Features**:
- Real-time stock prices
- Cryptocurrency prices
- Price change indicators (green/red)
- Percentage change display
- Optional mini charts
- Scrolling ticker format
- Company/crypto logos

**Data Sources**:
- Yahoo Finance API for stocks
- Yahoo Finance API for crypto
- Automatic market hours detection

---

### 📰 Stock News Manager (`src/stock_news_manager.py`)
**Purpose**: Displays financial news headlines for configured stocks

**Configuration**:
```json
{
  "stock_news": {
    "enabled": true,
    "update_interval": 3600,
    "scroll_speed": 1,
    "scroll_delay": 0.01,
    "max_headlines_per_symbol": 1,
    "headlines_per_rotation": 2
  }
}
```

**Features**:
- Financial news headlines
- Stock-specific news filtering
- Scrolling text display
- Configurable headline limits
- Automatic rotation

---

### 🎵 Music Manager (`src/music_manager.py`)
**Purpose**: Displays currently playing music from Spotify or YouTube Music

**Configuration**:
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

**Features**:
- Spotify integration
- YouTube Music integration
- Album art display
- Song title and artist
- Playback status
- Real-time updates

**Supported Sources**:
- Spotify (requires API credentials)
- YouTube Music (requires YTMD companion server)

---

### 📅 Calendar Manager (`src/calendar_manager.py`)
**Purpose**: Displays upcoming Google Calendar events

**Configuration**:
```json
{
  "calendar": {
    "enabled": true,
    "credentials_file": "credentials.json",
    "token_file": "token.pickle",
    "update_interval": 3600,
    "max_events": 3,
    "calendars": ["birthdays"]
  }
}
```

**Features**:
- Google Calendar integration
- Event date and time display
- Event title (wrapped to fit display)
- Multiple calendar support
- Configurable event limits

---

### 🏈 Sports Managers

The system includes separate managers for each sports league:

#### NHL Managers (`src/nhl_managers.py`)
- **NHLLiveManager**: Currently playing games
- **NHLRecentManager**: Completed games (last 48 hours)
- **NHLUpcomingManager**: Scheduled games

#### NBA Managers (`src/nba_managers.py`)
- **NBALiveManager**: Currently playing games
- **NBARecentManager**: Completed games
- **NBAUpcomingManager**: Scheduled games

#### MLB Managers (`src/mlb_manager.py`)
- **MLBLiveManager**: Currently playing games
- **MLBRecentManager**: Completed games
- **MLBUpcomingManager**: Scheduled games

#### NFL Managers (`src/nfl_managers.py`)
- **NFLLiveManager**: Currently playing games
- **NFLRecentManager**: Completed games
- **NFLUpcomingManager**: Scheduled games

#### NCAA Managers
- **NCAA Football** (`src/ncaa_fb_managers.py`)
- **NCAA Baseball** (`src/ncaa_baseball_managers.py`)
- **NCAA Basketball** (`src/ncaam_basketball_managers.py`)

#### Soccer Managers (`src/soccer_managers.py`)
- **SoccerLiveManager**: Currently playing games
- **SoccerRecentManager**: Completed games
- **SoccerUpcomingManager**: Scheduled games

#### MiLB Managers (`src/milb_manager.py`)
- **MiLBLiveManager**: Currently playing games
- **MiLBRecentManager**: Completed games
- **MiLBUpcomingManager**: Scheduled games

**Common Sports Configuration**:
```json
{
  "nhl_scoreboard": {
    "enabled": true,
    "live_priority": true,
    "live_game_duration": 20,
    "show_odds": true,
    "test_mode": false,
    "update_interval_seconds": 3600,
    "live_update_interval": 30,
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

**Sports Features**:
- Live game scores and status
- Team logos and records
- Game times and venues
- Odds integration (where available)
- Favorite team filtering
- Automatic game switching
- ESPN API integration

---

### 🎲 Odds Ticker Manager (`src/odds_ticker_manager.py`)
**Purpose**: Displays betting odds for upcoming sports games

**Configuration**:
```json
{
  "odds_ticker": {
    "enabled": true,
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

**Features**:
- Multi-league support (NFL, NBA, MLB, NCAA)
- Spread, money line, and over/under odds
- Team logos display
- Scrolling text format
- Game time display
- ESPN API integration

---

### 🎨 Custom Display Managers

#### Text Display Manager (`src/text_display.py`)
**Purpose**: Displays custom text messages

**Configuration**:
```json
{
  "text_display": {
    "enabled": true,
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

**Features**:
- Custom text messages
- Configurable fonts and colors
- Scrolling text support
- Static text display
- Background color options

#### YouTube Display Manager (`src/youtube_display.py`)
**Purpose**: Displays YouTube channel statistics

**Configuration**:
```json
{
  "youtube": {
    "enabled": true,
    "update_interval": 3600
  }
}
```

**Features**:
- Subscriber count display
- Video count display
- View count display
- YouTube API integration

#### Of The Day Manager (`src/of_the_day_manager.py`)
**Purpose**: Displays various "of the day" content

**Configuration**:
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

**Features**:
- Word of the day
- Slovenian word of the day
- Bible verse of the day
- Rotating display categories
- Local JSON data files

---

## Display Manager Architecture

### Common Interface
All display managers follow a consistent interface:

```python
class DisplayManager:
    def __init__(self, config, display_manager):
        # Initialize with configuration and display manager
        
    def update_data(self):
        # Fetch and process new data
        
    def display(self, force_clear=False):
        # Render content to the display
        
    def is_enabled(self):
        # Check if manager is enabled
```

### Data Flow
1. **Configuration**: Manager reads settings from `config.json`
2. **Data Fetching**: Retrieves data from APIs or local sources
3. **Caching**: Stores data using `CacheManager`
4. **Processing**: Transforms data into display format
5. **Rendering**: Uses `DisplayManager` to show content
6. **Rotation**: Returns to main display controller

### Error Handling
- API failures fall back to cached data
- Network timeouts are handled gracefully
- Invalid data is filtered out
- Logging provides debugging information

## Configuration Best Practices

### Enable/Disable Managers
```json
{
  "weather": {
    "enabled": true  // Set to false to disable
  }
}
```

### Set Display Durations
```json
{
  "display": {
    "display_durations": {
      "weather": 30,      // 30 seconds
      "stocks": 60,       // 1 minute
      "nhl_live": 20      // 20 seconds
    }
  }
}
```

### Configure Update Intervals
```json
{
  "weather": {
    "update_interval": 1800  // Update every 30 minutes
  }
}
```

### Set Favorite Teams
```json
{
  "nhl_scoreboard": {
    "show_favorite_teams_only": true,
    "favorite_teams": ["TB", "DAL"]
  }
}
```

## Performance Considerations

### API Rate Limits
- Weather: 1000 calls/day (OpenWeatherMap)
- Stocks: 2000 calls/hour (Yahoo Finance)
- Sports: ESPN API (no documented limits)
- Music: Spotify/YouTube Music APIs

### Caching Strategy
- Data cached based on `update_interval`
- Cache persists across restarts
- Failed API calls use cached data
- Automatic cache invalidation

### Resource Usage
- Each manager runs independently
- Disabled managers use no resources
- Memory usage scales with enabled features
- CPU usage minimal during idle periods

## Troubleshooting Display Managers

### Common Issues
1. **No Data Displayed**: Check API keys and network connectivity
2. **Outdated Data**: Verify update intervals and cache settings
3. **Display Errors**: Check font files and display configuration
4. **Performance Issues**: Reduce update frequency or disable unused managers

### Debugging
- Enable logging for specific managers
- Check cache directory for data files
- Verify API credentials in `config_secrets.json`
- Test individual managers in isolation

---

*For detailed technical information about each display manager, see the [Display Manager Details](WIKI_DISPLAY_MANAGER_DETAILS.md) page.* 