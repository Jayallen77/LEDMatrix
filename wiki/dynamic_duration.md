# Dynamic Duration Implementation

## Overview

Dynamic Duration is a feature that calculates the exact time needed to display scrolling content (like news headlines or stock tickers) based on the content's length, scroll speed, and display characteristics, rather than using a fixed duration. This ensures optimal viewing time for users while maintaining smooth content flow.

## How It Works

The dynamic duration calculation considers several factors:

1. **Content Width**: The total width of the text/image content to be displayed
2. **Display Width**: The width of the LED matrix display
3. **Scroll Speed**: How many pixels the content moves per frame
4. **Scroll Delay**: Time between each frame update
5. **Buffer Time**: Additional time added for smooth cycling (configurable percentage)

### Calculation Formula

```
Total Scroll Distance = Display Width + Content Width
Frames Needed = Total Scroll Distance / Scroll Speed
Base Time = Frames Needed × Scroll Delay
Buffer Time = Base Time × Duration Buffer
Calculated Duration = Base Time + Buffer Time
```

The final duration is then capped between the configured minimum and maximum values.

## Configuration

Add the following settings to your `config/config.json` file:

### For Stocks (`stocks` section)
```json
{
  "stocks": {
    "dynamic_duration": true,
    "min_duration": 30,
    "max_duration": 300,
    "duration_buffer": 0.1,
    // ... other existing settings
  }
}
```

### For Stock News (`stock_news` section)
```json
{
  "stock_news": {
    "dynamic_duration": true,
    "min_duration": 30,
    "max_duration": 300,
    "duration_buffer": 0.1,
    // ... other existing settings
  }
}
```

### For Odds Ticker (`odds_ticker` section)
```json
{
  "odds_ticker": {
    "dynamic_duration": true,
    "min_duration": 30,
    "max_duration": 300,
    "duration_buffer": 0.1,
    // ... other existing settings
  }
}
```

### Configuration Options

- **`dynamic_duration`** (boolean): Enable/disable dynamic duration calculation
- **`min_duration`** (seconds): Minimum display time regardless of content length
- **`max_duration`** (seconds): Maximum display time to prevent excessive delays
- **`duration_buffer`** (decimal): Additional time as a percentage of calculated time (e.g., 0.1 = 10% extra)

## Implementation Details

### StockManager Updates

The `StockManager` class has been enhanced with dynamic duration capabilities:

```python
# In __init__ method
self.dynamic_duration_enabled = self.stocks_config.get('dynamic_duration', True)
self.min_duration = self.stocks_config.get('min_duration', 30)
self.max_duration = self.stocks_config.get('max_duration', 300)
self.duration_buffer = self.stocks_config.get('duration_buffer', 0.1)
self.dynamic_duration = 60  # Default duration in seconds
self.total_scroll_width = 0  # Track total width for calculation
```

#### New Methods

**`calculate_dynamic_duration()`**
- Calculates the exact time needed to display all stock information
- Considers display width, content width, scroll speed, and delays
- Applies min/max duration limits
- Includes detailed debug logging

**`get_dynamic_duration()`**
- Returns the calculated dynamic duration for external use
- Used by the DisplayController to determine display timing

### StockNewsManager Updates

Similar enhancements have been applied to the `StockNewsManager`:

```python
# In __init__ method
self.dynamic_duration_enabled = self.stock_news_config.get('dynamic_duration', True)
self.min_duration = self.stock_news_config.get('min_duration', 30)
self.max_duration = self.stock_news_config.get('max_duration', 300)
self.duration_buffer = self.stock_news_config.get('duration_buffer', 0.1)
self.dynamic_duration = 60  # Default duration in seconds
self.total_scroll_width = 0  # Track total width for calculation
```

#### New Methods

**`calculate_dynamic_duration()`**
- Calculates display time for news headlines
- Uses the same logic as StockManager but with stock news configuration
- Handles text width calculation from cached images

**`get_dynamic_duration()`**
- Returns the calculated duration for news display

### OddsTickerManager Updates

The `OddsTickerManager` class has been enhanced with dynamic duration capabilities:

```python
# In __init__ method
self.dynamic_duration_enabled = self.odds_ticker_config.get('dynamic_duration', True)
self.min_duration = self.odds_ticker_config.get('min_duration', 30)
self.max_duration = self.odds_ticker_config.get('max_duration', 300)
self.duration_buffer = self.odds_ticker_config.get('duration_buffer', 0.1)
self.dynamic_duration = 60  # Default duration in seconds
self.total_scroll_width = 0  # Track total width for calculation
```

#### New Methods

**`calculate_dynamic_duration()`**
- Calculates display time for odds ticker content
- Uses the same logic as other managers but with odds ticker configuration
- Handles width calculation from the composite ticker image

**`get_dynamic_duration()`**
- Returns the calculated duration for odds ticker display

### DisplayController Integration

The `DisplayController` has been updated to use dynamic durations:

```python
# In get_current_duration() method
# Handle dynamic duration for stocks
if mode_key == 'stocks' and self.stocks:
    try:
        dynamic_duration = self.stocks.get_dynamic_duration()
        logger.info(f"Using dynamic duration for stocks: {dynamic_duration} seconds")
        return dynamic_duration
    except Exception as e:
        logger.error(f"Error getting dynamic duration for stocks: {e}")
        return self.display_durations.get(mode_key, 60)

# Handle dynamic duration for stock_news
if mode_key == 'stock_news' and self.news:
    try:
        dynamic_duration = self.news.get_dynamic_duration()
        logger.info(f"Using dynamic duration for stock_news: {dynamic_duration} seconds")
        return dynamic_duration
    except Exception as e:
        logger.error(f"Error getting dynamic duration for stock_news: {e}")
        return self.display_durations.get(mode_key, 60)

# Handle dynamic duration for odds_ticker
if mode_key == 'odds_ticker' and self.odds_ticker:
    try:
        dynamic_duration = self.odds_ticker.get_dynamic_duration()
        logger.info(f"Using dynamic duration for odds_ticker: {dynamic_duration} seconds")
        return dynamic_duration
    except Exception as e:
        logger.error(f"Error getting dynamic duration for odds_ticker: {e}")
        return self.display_durations.get(mode_key, 60)

## Benefits

1. **Optimal Viewing Time**: Content is displayed for exactly the right amount of time
2. **Smooth Transitions**: Buffer time ensures smooth cycling between content
3. **Configurable Limits**: Min/max durations prevent too short or too long displays
4. **Consistent Experience**: All scrolling content uses the same timing logic
5. **Debug Visibility**: Detailed logging helps troubleshoot timing issues

## Testing

The implementation includes comprehensive logging to verify calculations:

```
Stock dynamic duration calculation:
  Display width: 128px
  Text width: 450px
  Total scroll distance: 578px
  Frames needed: 578.0
  Base time: 5.78s
  Buffer time: 0.58s (10%)
  Calculated duration: 6s
  Final duration: 30s (capped to minimum)
```

## Troubleshooting

### Duration Always at Minimum
If your calculated duration is always capped at the minimum value, check:
- Scroll speed settings (higher speed = shorter duration)
- Scroll delay settings (lower delay = shorter duration)
- Content width calculation
- Display width configuration

### Duration Too Long
If content displays for too long:
- Reduce the `duration_buffer` percentage
- Increase `scroll_speed` or decrease `scroll_delay`
- Lower the `max_duration` limit

### Dynamic Duration Not Working
If dynamic duration isn't being used:
- Verify `dynamic_duration: true` in configuration
- Check that the manager instances are properly initialized
- Review error logs for calculation failures

## Related Files

- `config/config.json` - Configuration settings
- `src/stock_manager.py` - Stock display with dynamic duration
- `src/stock_news_manager.py` - Stock news with dynamic duration
- `src/odds_ticker_manager.py` - Odds ticker with dynamic duration
- `src/display_controller.py` - Integration and duration management
- `src/news_manager.py` - Original implementation reference
