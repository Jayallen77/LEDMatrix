# Dynamic Duration Implementation for Stocks and Stock News

## Overview

This document describes the implementation of dynamic duration functionality for the `stock_manager` and `stock_news_manager` classes, following the same pattern as the existing `news_manager`.

## What Was Implemented

### 1. Configuration Updates

Added dynamic duration settings to both `stocks` and `stock_news` sections in `config/config.json`:

```json
"stocks": {
    "enabled": true,
    "update_interval": 600,
    "scroll_speed": 1,
    "scroll_delay": 0.01,
    "toggle_chart": true,
    "dynamic_duration": true,
    "min_duration": 30,
    "max_duration": 300,
    "duration_buffer": 0.1,
    "symbols": [...],
    "display_format": "{symbol}: ${price} ({change}%)"
},
"stock_news": {
    "enabled": true,
    "update_interval": 3600,
    "scroll_speed": 1,
    "scroll_delay": 0.01,
    "max_headlines_per_symbol": 1,
    "headlines_per_rotation": 2,
    "dynamic_duration": true,
    "min_duration": 30,
    "max_duration": 300,
    "duration_buffer": 0.1
}
```

### 2. Stock Manager Updates (`src/stock_manager.py`)

#### Added Dynamic Duration Properties
```python
# Dynamic duration settings
self.dynamic_duration_enabled = self.stocks_config.get('dynamic_duration', True)
self.min_duration = self.stocks_config.get('min_duration', 30)
self.max_duration = self.stocks_config.get('max_duration', 300)
self.duration_buffer = self.stocks_config.get('duration_buffer', 0.1)
self.dynamic_duration = 60  # Default duration in seconds
self.total_scroll_width = 0  # Track total width for dynamic duration calculation
```

#### Added `calculate_dynamic_duration()` Method
This method calculates the exact time needed to display all stocks based on:
- Total scroll width of the content
- Display width
- Scroll speed and delay settings
- Configurable buffer time
- Min/max duration limits

#### Added `get_dynamic_duration()` Method
Returns the calculated dynamic duration for use by the display controller.

#### Updated `display_stocks()` Method
The method now calculates and stores the total scroll width and calls `calculate_dynamic_duration()` when creating the scrolling image.

### 3. Stock News Manager Updates (`src/stock_news_manager.py`)

#### Added Dynamic Duration Properties
```python
# Dynamic duration settings
self.dynamic_duration_enabled = self.stock_news_config.get('dynamic_duration', True)
self.min_duration = self.stock_news_config.get('min_duration', 30)
self.max_duration = self.stock_news_config.get('max_duration', 300)
self.duration_buffer = self.stock_news_config.get('duration_buffer', 0.1)
self.dynamic_duration = 60  # Default duration in seconds
self.total_scroll_width = 0  # Track total width for dynamic duration calculation
```

#### Added `calculate_dynamic_duration()` Method
Similar to the stock manager, calculates duration based on content width and scroll settings.

#### Added `get_dynamic_duration()` Method
Returns the calculated dynamic duration for use by the display controller.

#### Updated `display_news()` Method
The method now calculates and stores the total scroll width and calls `calculate_dynamic_duration()` when creating the scrolling image.

### 4. Display Controller Updates (`src/display_controller.py`)

#### Updated `get_current_duration()` Method
Added dynamic duration handling for both `stocks` and `stock_news` modes:

```python
# Handle dynamic duration for stocks
if mode_key == 'stocks' and self.stocks:
    try:
        dynamic_duration = self.stocks.get_dynamic_duration()
        # Only log if duration has changed or we haven't logged this duration yet
        if not hasattr(self, '_last_logged_duration') or self._last_logged_duration != dynamic_duration:
            logger.info(f"Using dynamic duration for stocks: {dynamic_duration} seconds")
            self._last_logged_duration = dynamic_duration
        return dynamic_duration
    except Exception as e:
        logger.error(f"Error getting dynamic duration for stocks: {e}")
        # Fall back to configured duration
        return self.display_durations.get(mode_key, 60)

# Handle dynamic duration for stock_news
if mode_key == 'stock_news' and self.news:
    try:
        dynamic_duration = self.news.get_dynamic_duration()
        # Only log if duration has changed or we haven't logged this duration yet
        if not hasattr(self, '_last_logged_duration') or self._last_logged_duration != dynamic_duration:
            logger.info(f"Using dynamic duration for stock_news: {dynamic_duration} seconds")
            self._last_logged_duration = dynamic_duration
        return dynamic_duration
    except Exception as e:
        logger.error(f"Error getting dynamic duration for stock_news: {e}")
        # Fall back to configured duration
        return self.display_durations.get(mode_key, 60)
```

## How It Works

### Dynamic Duration Calculation

The dynamic duration is calculated using the following formula:

1. **Total Scroll Distance**: `display_width + total_scroll_width`
2. **Frames Needed**: `total_scroll_distance / scroll_speed`
3. **Base Time**: `frames_needed * scroll_delay`
4. **Buffer Time**: `base_time * duration_buffer`
5. **Final Duration**: `int(base_time + buffer_time)`

The final duration is then clamped between `min_duration` and `max_duration`.

### Integration with Display Controller

1. When the display controller needs to determine how long to show a particular mode, it calls `get_current_duration()`
2. For `stocks` and `stock_news` modes, it calls the respective manager's `get_dynamic_duration()` method
3. The manager returns the calculated duration based on the current content width
4. The display controller uses this duration to determine how long to display the content

### Benefits

1. **Consistent Display Time**: Content is displayed for an appropriate amount of time based on its length
2. **Configurable**: Users can adjust min/max durations and buffer percentages
3. **Fallback Support**: If dynamic duration fails, it falls back to configured fixed durations
4. **Performance**: Duration is calculated once when content is created, not on every frame

## Configuration Options

### Dynamic Duration Settings

- **`dynamic_duration`**: Enable/disable dynamic duration calculation (default: `true`)
- **`min_duration`**: Minimum display duration in seconds (default: `30`)
- **`max_duration`**: Maximum display duration in seconds (default: `300`)
- **`duration_buffer`**: Buffer percentage to add for smooth cycling (default: `0.1` = 10%)

### Example Configuration

```json
{
    "dynamic_duration": true,
    "min_duration": 20,
    "max_duration": 180,
    "duration_buffer": 0.15
}
```

This would:
- Enable dynamic duration
- Set minimum display time to 20 seconds
- Set maximum display time to 3 minutes
- Add 15% buffer time for smooth cycling

## Testing

The implementation has been tested to ensure:
- Configuration is properly loaded
- Dynamic duration calculation works correctly
- Display controller integration is functional
- Fallback behavior works when dynamic duration is disabled

## Compatibility

This implementation follows the exact same pattern as the existing `news_manager` dynamic duration functionality, ensuring consistency across the codebase and making it easy to maintain and extend.
