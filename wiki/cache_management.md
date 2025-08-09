# Cache Management

The LEDMatrix application uses caching to improve performance and reduce API calls. However, sometimes cache data can become stale or corrupted, leading to issues like false live game detection or outdated information.

## Cache Clearing Utility

The `clear_cache.py` script provides a command-line interface for managing the LEDMatrix cache. This utility is essential for debugging cache-related issues and ensuring fresh data retrieval.

### Basic Usage

```bash
# Show help and current cache status
python clear_cache.py

# List all available cache keys
python clear_cache.py --list

# Clear all cache data
python clear_cache.py --clear-all

# Clear a specific cache key
python clear_cache.py --clear KEY_NAME

# Show information about a specific cache key
python clear_cache.py --info KEY_NAME
```

### Command Reference

| Command | Short | Description |
|---------|-------|-------------|
| `--list` | `-l` | List all available cache keys |
| `--clear-all` | `-a` | Clear all cache data |
| `--clear KEY` | `-c` | Clear a specific cache key |
| `--info KEY` | `-i` | Show information about a specific cache key |

## Common Cache Keys

### MiLB (Minor League Baseball)
- `milb_live_api_data` - Live game data from MiLB API
- `milb_upcoming_api_data` - Upcoming game schedules
- `milb_recent_api_data` - Recent game results

### MLB (Major League Baseball)
- `mlb_live_api_data` - Live game data from MLB API
- `mlb_upcoming_api_data` - Upcoming game schedules
- `mlb_recent_api_data` - Recent game results

### Soccer
- `soccer_live_api_data` - Live soccer match data
- `soccer_upcoming_api_data` - Upcoming soccer matches

### Other Services
- `weather_api_data` - Weather information
- `news_api_data` - News headlines
- `stocks_api_data` - Stock market data

## Usage Examples

### Scenario 1: False Live Game Detection

**Problem**: The MiLB manager is showing "Tam vs Dun" as a live game when it's actually old data.

**Solution**:
```bash
# First, check what's in the MiLB live cache
python clear_cache.py --info milb_live_api_data

# Clear the problematic cache
python clear_cache.py --clear milb_live_api_data

# Restart the application to fetch fresh data
```

### Scenario 2: Stale Upcoming Games

**Problem**: The display is showing outdated game schedules.

**Solution**:
```bash
# Clear all MiLB cache data
python clear_cache.py --clear milb_upcoming_api_data
python clear_cache.py --clear milb_live_api_data
python clear_cache.py --clear milb_recent_api_data
```

### Scenario 3: Complete Cache Reset

**Problem**: Multiple cache-related issues or corrupted data.

**Solution**:
```bash
# Nuclear option - clear everything
python clear_cache.py --clear-all

# Verify cache is empty
python clear_cache.py --list
```

### Scenario 4: Debugging Cache Issues

**Problem**: Unusual behavior that might be cache-related.

**Solution**:
```bash
# List all cache keys to see what's stored
python clear_cache.py --list

# Inspect specific cache entries
python clear_cache.py --info milb_live_api_data
python clear_cache.py --info weather_api_data

# Clear specific problematic caches
python clear_cache.py --clear milb_live_api_data
```

## Troubleshooting

### Cache Directory Issues

If you encounter errors about cache directories:

```bash
# Check if cache directory exists
ls -la ~/.ledmatrix_cache/

# If it doesn't exist, the application will create it automatically
# You can also manually create it:
mkdir -p ~/.ledmatrix_cache/
```

### Permission Issues

If you get permission errors:

```bash
# Check cache directory permissions
ls -la ~/.ledmatrix_cache/

# Fix permissions if needed
chmod 755 ~/.ledmatrix_cache/
chown $USER:$USER ~/.ledmatrix_cache/
```

### Import Errors

If you get import errors when running the script:

```bash
# Make sure you're in the LEDMatrix root directory
cd /path/to/LEDMatrix

# Check that the src directory exists
ls -la src/

# Run the script from the correct location
python clear_cache.py --list
```

## When to Use Cache Clearing

### Recommended Times to Clear Cache

1. **After configuration changes** - Clear relevant caches when you modify team preferences or display settings
2. **When experiencing false live data** - Clear live game caches if old games appear as "live"
3. **After API changes** - Clear caches if you notice API endpoints have changed
4. **For debugging** - Clear caches when investigating display or data issues
5. **After long periods of inactivity** - Clear caches if the application hasn't been used for days

### Cache Types and Their Impact

| Cache Type | Impact of Clearing | When to Clear |
|------------|-------------------|---------------|
| Live game data | Forces fresh live data fetch | False live game detection |
| Upcoming games | Refreshes schedules | Outdated game times |
| Recent games | Updates final scores | Missing recent results |
| Weather | Gets current conditions | Stale weather data |
| News | Fetches latest headlines | Old news stories |

## Best Practices

1. **Targeted Clearing**: Clear specific cache keys rather than all cache when possible
2. **Verify Results**: Use `--info` to check cache contents before and after clearing
3. **Restart Application**: Restart the LEDMatrix application after clearing caches
4. **Monitor Logs**: Check application logs after cache clearing to ensure fresh data is fetched
5. **Backup Important Data**: Cache data is automatically regenerated, but be aware that clearing will force new API calls

## Integration with Application

The cache clearing utility works independently of the main application. You can run it while the application is running, but for best results:

1. Stop the LEDMatrix application
2. Clear relevant caches
3. Restart the application

This ensures the application starts with fresh data and doesn't immediately re-cache potentially problematic data.

## Advanced Usage

### Scripting Cache Management

You can integrate cache clearing into scripts or cron jobs:

```bash
#!/bin/bash
# Daily cache cleanup script

# Clear old live game data at midnight
python clear_cache.py --clear milb_live_api_data
python clear_cache.py --clear mlb_live_api_data

# Log the cleanup
echo "$(date): Cache cleared" >> /var/log/ledmatrix_cache.log
```

### Conditional Cache Clearing

```bash
#!/bin/bash
# Only clear cache if it's older than 24 hours

# Check cache age and clear if needed
# (This would require additional logic to check cache timestamps)
```

## Related Documentation

- [Configuration Guide](../config/README.md)
- [Troubleshooting Guide](troubleshooting.md)
- [API Integration](api_integration.md)
- [Display Controller](display_controller.md)
