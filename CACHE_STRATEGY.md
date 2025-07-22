# LEDMatrix Cache Strategy Analysis

## Current Implementation

Your LEDMatrix system uses a sophisticated multi-tier caching strategy that balances data freshness with API efficiency.

### Cache Duration Categories

#### 1. **Ultra Time-Sensitive Data (15-60 seconds)**
- **Live Sports Scores**: Now respects sport-specific `live_update_interval` configuration
  - Soccer live data: Uses `soccer_scoreboard.live_update_interval` (default: 60 seconds)
  - NFL live data: Uses `nfl_scoreboard.live_update_interval` (default: 60 seconds)
  - NHL live data: Uses `nhl_scoreboard.live_update_interval` (default: 60 seconds)
  - NBA live data: Uses `nba_scoreboard.live_update_interval` (default: 60 seconds)
  - MLB live data: Uses `mlb.live_update_interval` (default: 60 seconds)
  - NCAA sports: Use respective `live_update_interval` configurations (default: 60 seconds)
- **Current Weather**: 5 minutes (300 seconds)

#### 2. **Market Data (5-10 minutes)**
- **Stocks**: 10 minutes (600 seconds) - market hours aware
- **Crypto**: 5 minutes (300 seconds) - 24/7 trading
- **Stock News**: 1 hour (3600 seconds)

#### 3. **Sports Data (5 minutes to 24 hours)**
- **Recent Games**: 5 minutes (300 seconds)
- **Upcoming Games**: 1 hour (3600 seconds)
- **Season Schedules**: 24 hours (86400 seconds)
- **Team Information**: 1 week (604800 seconds)

#### 4. **Static Data (1 week to 30 days)**
- **Team Logos**: 30 days (2592000 seconds)
- **Configuration Data**: 1 week (604800 seconds)

### Smart Cache Invalidation

Beyond time limits, the system uses content-based invalidation:

```python
def has_data_changed(self, data_type: str, new_data: Dict[str, Any]) -> bool:
    """Check if data has changed from cached version."""
```

- **Weather**: Compares temperature and conditions
- **Stocks**: Compares prices (only during market hours)
- **Sports**: Compares scores, game status, inning details
- **News**: Compares headlines and article IDs

### Market-Aware Caching

For stocks, the system extends cache duration during off-hours:

```python
def _is_market_open(self) -> bool:
    """Check if the US stock market is currently open."""
    # Only invalidates cache during market hours
```

## Enhanced Cache Strategy

### Sport-Specific Live Update Intervals

The cache manager now automatically respects the `live_update_interval` configuration for each sport:

```python
def get_sport_live_interval(self, sport_key: str) -> int:
    """Get the live_update_interval for a specific sport from config."""
    config = self.config_manager.get_config()
    sport_config = config.get(f"{sport_key}_scoreboard", {})
    return sport_config.get("live_update_interval", 30)
```

### Automatic Sport Detection

The cache manager automatically detects the sport from cache keys:

```python
def get_sport_key_from_cache_key(self, key: str) -> Optional[str]:
    """Extract sport key from cache key to determine appropriate live_update_interval."""
    # Maps cache key patterns to sport keys
    sport_patterns = {
        'nfl': ['nfl', 'football'],
        'nba': ['nba', 'basketball'],
        'mlb': ['mlb', 'baseball'],
        'nhl': ['nhl', 'hockey'],
        'soccer': ['soccer', 'football'],
        # ... etc
    }
```

### Configuration Examples

**Current Configuration (config/config.json):**
```json
{
    "nfl_scoreboard": {
        "live_update_interval": 30,
        "enabled": true
    },
    "soccer_scoreboard": {
        "live_update_interval": 30,
        "enabled": false
    },
    "mlb": {
        "live_update_interval": 30,
        "enabled": true
    }
}
```

**Cache Behavior:**
- NFL live data: 30-second cache (from config)
- Soccer live data: 30-second cache (from config)
- MLB live data: 30-second cache (from config)

### Fallback Strategy

If configuration is unavailable, the system uses sport-specific defaults:

```python
default_intervals = {
    'soccer': 60,      # Soccer default
    'nfl': 60,         # NFL default
    'nhl': 60,         # NHL default
    'nba': 60,         # NBA default
    'mlb': 60,         # MLB default
    'milb': 60,        # Minor league default
    'ncaa_fb': 60,    # College football default
    'ncaa_baseball': 60,  # College baseball default
    'ncaam_basketball': 60,  # College basketball default
}
```

## Usage Examples

### Automatic Sport Detection
```python
# Cache manager automatically detects NFL and uses nfl_scoreboard.live_update_interval
cached_data = cache_manager.get_with_auto_strategy("nfl_live_20241201")

# Cache manager automatically detects soccer and uses soccer_scoreboard.live_update_interval
cached_data = cache_manager.get_with_auto_strategy("soccer_live_20241201")
```

### Manual Sport Specification
```python
# Explicitly specify sport for custom cache keys
cached_data = cache_manager.get_cached_data_with_strategy("custom_live_key", "sports_live")
```

## Benefits

1. **Configuration-Driven**: Cache respects your sport-specific settings
2. **Automatic Detection**: No manual cache duration management needed
3. **Sport-Optimized**: Each sport uses its appropriate update interval
4. **Backward Compatible**: Existing code continues to work
5. **Flexible**: Easy to adjust intervals per sport in config

## Migration

The enhanced cache manager is backward compatible. Existing code will automatically benefit from sport-specific intervals without any changes needed.

To customize intervals for specific sports, simply update the `live_update_interval` in your `config/config.json`:

```json
{
    "nfl_scoreboard": {
        "live_update_interval": 15  // More aggressive for NFL
    },
    "mlb": {
        "live_update_interval": 45  // Slower pace for MLB
    }
}
``` 