# System Architecture

The LEDMatrix system is built with a modular, extensible architecture that separates concerns and allows for easy maintenance and extension. This guide explains how all components work together.

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    LEDMatrix System                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Display   │  │   Display   │  │   Display   │      │
│  │ Controller  │  │  Manager    │  │  Managers   │      │
│  │             │  │             │  │             │      │
│  │ • Main Loop │  │ • Hardware  │  │ • Weather   │      │
│  │ • Rotation  │  │ • Rendering │  │ • Stocks    │      │
│  │ • Scheduling│  │ • Fonts     │  │ • Sports    │      │
│  │ • Live Mode │  │ • Graphics  │  │ • Music     │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Config    │  │   Cache     │  │   Web       │      │
│  │  Manager    │  │  Manager    │  │ Interface   │      │
│  │             │  │             │  │             │      │
│  │ • Settings  │  │ • Data      │  │ • Control   │      │
│  │ • Validation│  │ • Persistence│  │ • Status    │      │
│  │ • Loading   │  │ • Fallbacks │  │ • Settings  │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Display Controller (`src/display_controller.py`)

**Purpose**: Main orchestrator that manages the entire display system.

**Responsibilities**:
- Initialize all display managers
- Control display rotation and timing
- Handle live game priority
- Manage system scheduling
- Coordinate data updates
- Handle error recovery

**Key Methods**:
```python
class DisplayController:
    def __init__(self):
        # Initialize all managers and configuration
        
    def run(self):
        # Main display loop
        
    def _update_modules(self):
        # Update all enabled modules
        
    def _check_live_games(self):
        # Check for live games and prioritize
        
    def _rotate_team_games(self, sport):
        # Rotate through team games
```

**Data Flow**:
1. Load configuration
2. Initialize display managers
3. Start main loop
4. Check for live games
5. Rotate through enabled displays
6. Handle scheduling and timing

### 2. Display Manager (`src/display_manager.py`)

**Purpose**: Low-level hardware interface and graphics rendering.

**Responsibilities**:
- Initialize RGB LED matrix hardware
- Handle font loading and management
- Provide drawing primitives
- Manage display buffers
- Handle hardware configuration
- Provide text rendering utilities

**Key Features**:
```python
class DisplayManager:
    def __init__(self, config):
        # Initialize hardware and fonts
        
    def draw_text(self, text, x, y, color, font):
        # Draw text on display
        
    def update_display(self):
        # Update physical display
        
    def clear(self):
        # Clear display
        
    def draw_weather_icon(self, condition, x, y, size):
        # Draw weather icons
```

**Hardware Interface**:
- RGB Matrix library integration
- GPIO pin management
- PWM timing control
- Double buffering for smooth updates
- Font rendering (TTF and BDF)

### 3. Configuration Manager (`src/config_manager.py`)

**Purpose**: Load, validate, and manage system configuration.

**Responsibilities**:
- Load JSON configuration files
- Validate configuration syntax
- Provide default values
- Handle configuration updates
- Manage secrets and API keys

**Configuration Sources**:
```python
class ConfigManager:
    def load_config(self):
        # Load main config.json
        
    def load_secrets(self):
        # Load config_secrets.json
        
    def validate_config(self):
        # Validate configuration
        
    def get_defaults(self):
        # Provide default values
```

**Configuration Structure**:
- Main settings in `config/config.json`
- API keys in `config/config_secrets.json`
- Validation and error handling
- Default value fallbacks

### 4. Cache Manager (`src/cache_manager.py`)

**Purpose**: Intelligent data caching to reduce API calls and improve performance.

**Responsibilities**:
- Store API responses
- Manage cache expiration
- Handle cache persistence
- Provide fallback data
- Optimize storage usage

**Cache Strategy**:
```python
class CacheManager:
    def get(self, key):
        # Retrieve cached data
        
    def set(self, key, data, ttl):
        # Store data with expiration
        
    def is_valid(self, key):
        # Check if cache is still valid
        
    def clear_expired(self):
        # Remove expired cache entries
```

**Cache Locations** (in order of preference):
1. `~/.ledmatrix_cache/` (user's home directory)
2. `/var/cache/ledmatrix/` (system cache directory)
3. `/tmp/ledmatrix_cache/` (temporary directory)

## Display Manager Architecture

### Manager Interface

All display managers follow a consistent interface:

```python
class BaseManager:
    def __init__(self, config, display_manager):
        self.config = config
        self.display_manager = display_manager
        self.cache_manager = CacheManager()
        
    def update_data(self):
        """Fetch and process new data"""
        pass
        
    def display(self, force_clear=False):
        """Render content to display"""
        pass
        
    def is_enabled(self):
        """Check if manager is enabled"""
        return self.config.get('enabled', False)
        
    def get_duration(self):
        """Get display duration"""
        return self.config.get('duration', 30)
```

### Data Flow Pattern

Each manager follows this pattern:

1. **Initialization**: Load configuration and setup
2. **Data Fetching**: Retrieve data from APIs or local sources
3. **Caching**: Store data using CacheManager
4. **Processing**: Transform raw data into display format
5. **Rendering**: Use DisplayManager to show content
6. **Cleanup**: Return control to main controller

### Error Handling

- **API Failures**: Fall back to cached data
- **Network Issues**: Use last known good data
- **Invalid Data**: Filter out bad entries
- **Hardware Errors**: Graceful degradation
- **Configuration Errors**: Use safe defaults

## Sports Manager Architecture

### Sports Manager Pattern

Each sport follows a three-manager pattern:

```python
# Live games (currently playing)
class NHLLiveManager(BaseSportsManager):
    def fetch_games(self):
        # Get currently playing games
        
    def display_games(self):
        # Show live scores and status

# Recent games (completed)
class NHLRecentManager(BaseSportsManager):
    def fetch_games(self):
        # Get recently completed games
        
    def display_games(self):
        # Show final scores

# Upcoming games (scheduled)
class NHLUpcomingManager(BaseSportsManager):
    def fetch_games(self):
        # Get scheduled games
        
    def display_games(self):
        # Show game times and matchups
```

### Base Sports Manager

Common functionality shared by all sports:

```python
class BaseSportsManager:
    def __init__(self, config, display_manager):
        # Common initialization
        
    def fetch_espn_data(self, sport, endpoint):
        # Fetch from ESPN API
        
    def process_game_data(self, games):
        # Process raw game data
        
    def display_game(self, game):
        # Display individual game
        
    def get_team_logo(self, team_abbr):
        # Load team logo
        
    def format_score(self, score):
        # Format score display
```

### ESPN API Integration

All sports use ESPN's API for data:

```python
def fetch_espn_data(self, sport, endpoint):
    url = f"http://site.api.espn.com/apis/site/v2/sports/{sport}/{endpoint}"
    response = requests.get(url)
    return response.json()
```

**Supported Sports**:
- NHL (hockey)
- NBA (basketball)
- MLB (baseball)
- NFL (football)
- NCAA Football
- NCAA Basketball
- NCAA Baseball
- Soccer (multiple leagues)
- MiLB (minor league baseball)

## Financial Data Architecture

### Stock Manager

```python
class StockManager:
    def __init__(self, config, display_manager):
        # Initialize stock and crypto settings
        
    def fetch_stock_data(self, symbol):
        # Fetch from Yahoo Finance
        
    def fetch_crypto_data(self, symbol):
        # Fetch crypto data
        
    def display_stocks(self):
        # Show stock ticker
        
    def display_crypto(self):
        # Show crypto prices
```

### Stock News Manager

```python
class StockNewsManager:
    def __init__(self, config, display_manager):
        # Initialize news settings
        
    def fetch_news(self, symbols):
        # Fetch financial news
        
    def display_news(self):
        # Show news headlines
```

## Weather Architecture

### Weather Manager

```python
class WeatherManager:
    def __init__(self, config, display_manager):
        # Initialize weather settings
        
    def fetch_weather(self):
        # Fetch from OpenWeatherMap
        
    def display_current_weather(self):
        # Show current conditions
        
    def display_hourly_forecast(self):
        # Show hourly forecast
        
    def display_daily_forecast(self):
        # Show daily forecast
```

### Weather Icons

```python
class WeatherIcons:
    def __init__(self):
        # Load weather icon definitions
        
    def get_icon(self, condition):
        # Get icon for weather condition
        
    def draw_icon(self, condition, x, y, size):
        # Draw weather icon
```

## Music Architecture

### Music Manager

```python
class MusicManager:
    def __init__(self, display_manager, config):
        # Initialize music settings
        
    def start_polling(self):
        # Start background polling
        
    def update_music_display(self):
        # Update music information
        
    def display_spotify(self):
        # Display Spotify info
        
    def display_ytm(self):
        # Display YouTube Music info
```

### Spotify Client

```python
class SpotifyClient:
    def __init__(self, config):
        # Initialize Spotify API
        
    def authenticate(self):
        # Handle OAuth authentication
        
    def get_current_track(self):
        # Get currently playing track
```

### YouTube Music Client

```python
class YTMClient:
    def __init__(self, config):
        # Initialize YTM companion server
        
    def get_current_track(self):
        # Get current track from YTMD
```

## Web Interface Architecture

### Web Interface

```python
class WebInterface:
    def __init__(self, config):
        # Initialize Flask app
        
    def start_server(self):
        # Start web server
        
    def get_status(self):
        # Get system status
        
    def control_display(self, action):
        # Control display actions
```

**Features**:
- System status monitoring
- Display control (start/stop)
- Configuration management
- Service management
- Real-time status updates

## Service Architecture

### Systemd Service

```ini
[Unit]
Description=LEDMatrix Display Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/ledpi/LEDMatrix
ExecStart=/usr/bin/python3 display_controller.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Service Features**:
- Automatic startup
- Crash recovery
- Log management
- Resource monitoring

## Data Flow Architecture

### 1. Configuration Loading

```
config.json → ConfigManager → DisplayController → Display Managers
```

### 2. Data Fetching

```
API Sources → CacheManager → Display Managers → Display Manager
```

### 3. Display Rendering

```
Display Managers → Display Manager → RGB Matrix → LED Display
```

### 4. User Control

```
Web Interface → Display Controller → Display Managers
```

## Performance Architecture

### Caching Strategy

1. **API Response Caching**: Store API responses with TTL
2. **Processed Data Caching**: Cache processed display data
3. **Font Caching**: Cache loaded fonts
4. **Image Caching**: Cache team logos and icons

### Resource Management

1. **Memory Usage**: Monitor and optimize memory usage
2. **CPU Usage**: Minimize processing overhead
3. **Network Usage**: Optimize API calls
4. **Storage Usage**: Manage cache storage

### Error Recovery

1. **API Failures**: Use cached data
2. **Network Issues**: Retry with exponential backoff
3. **Hardware Errors**: Graceful degradation
4. **Configuration Errors**: Use safe defaults

## Extension Architecture

### Adding New Display Managers

1. **Create Manager Class**: Extend base manager pattern
2. **Add Configuration**: Add to config.json
3. **Register in Controller**: Add to DisplayController
4. **Add Assets**: Include logos, icons, fonts
5. **Test Integration**: Verify with main system

### Example New Manager

```python
class CustomManager(BaseManager):
    def __init__(self, config, display_manager):
        super().__init__(config, display_manager)
        
    def update_data(self):
        # Fetch custom data
        
    def display(self, force_clear=False):
        # Display custom content
```

## Security Architecture

### API Key Management

1. **Separate Secrets**: Store in config_secrets.json
2. **Environment Variables**: Support for env vars
3. **Access Control**: Restrict file permissions
4. **Key Rotation**: Support for key updates

### Network Security

1. **HTTPS Only**: Use secure API endpoints
2. **Rate Limiting**: Respect API limits
3. **Error Handling**: Don't expose sensitive data
4. **Logging**: Secure log management

## Monitoring Architecture

### Logging System

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s:%(name)s:%(message)s'
)
```

### Health Monitoring

1. **API Health**: Monitor API availability
2. **Display Health**: Monitor display functionality
3. **Cache Health**: Monitor cache performance
4. **System Health**: Monitor system resources

---

*This architecture provides a solid foundation for the LEDMatrix system while maintaining flexibility for future enhancements and customizations.* 