import json
import os
import time
from datetime import datetime
import pytz
from typing import Any, Dict, Optional
import logging
import stat
import threading
import tempfile

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class CacheManager:
    def __init__(self, cache_dir: str = None):
        self.logger = logging.getLogger(__name__)
        self._memory_cache = {}
        self._memory_cache_timestamps = {}
        self._cache_lock = threading.Lock()
        
        # Try to determine the best cache directory location
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            # Try user's home directory first
            home_dir = os.path.expanduser("~")
            if os.access(home_dir, os.W_OK):
                self.cache_dir = os.path.join(home_dir, ".ledmatrix_cache")
            else:
                # Fall back to system temp directory
                self.cache_dir = os.path.join(tempfile.gettempdir(), "ledmatrix_cache")
        
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists with proper permissions."""
        try:
            if not os.path.exists(self.cache_dir):
                # Create directory with 755 permissions (rwxr-xr-x)
                os.makedirs(self.cache_dir, mode=0o755, exist_ok=True)
                self.logger.info(f"Created cache directory: {self.cache_dir}")
            
            # Verify we have write permissions
            if not os.access(self.cache_dir, os.W_OK):
                raise PermissionError(f"No write access to cache directory: {self.cache_dir}")
                
        except Exception as e:
            self.logger.error(f"Error setting up cache directory: {e}")
            # Fall back to system temp directory
            self.cache_dir = os.path.join(tempfile.gettempdir(), "ledmatrix_cache")
            try:
                os.makedirs(self.cache_dir, mode=0o755, exist_ok=True)
                self.logger.info(f"Using temporary cache directory: {self.cache_dir}")
            except Exception as e:
                self.logger.error(f"Failed to create temporary cache directory: {e}")
                raise

    def _get_cache_path(self, key: str) -> str:
        """Get the path for a cache file."""
        return os.path.join(self.cache_dir, f"{key}.json")

    def load_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Load data from cache with memory caching."""
        current_time = time.time()
        
        # Check memory cache first
        if key in self._memory_cache:
            if current_time - self._memory_cache_timestamps.get(key, 0) < 60:  # 1 minute TTL
                return self._memory_cache[key]
            else:
                # Clear expired memory cache
                del self._memory_cache[key]
                del self._memory_cache_timestamps[key]

        cache_path = self._get_cache_path(key)
        if not os.path.exists(cache_path):
            return None

        try:
            with self._cache_lock:
                with open(cache_path, 'r') as f:
                    try:
                        data = json.load(f)
                        # Update memory cache
                        self._memory_cache[key] = data
                        self._memory_cache_timestamps[key] = current_time
                        return data
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Error parsing cache file for {key}: {e}")
                        # If the file is corrupted, remove it
                        os.remove(cache_path)
                        return None
        except Exception as e:
            self.logger.error(f"Error loading cache for {key}: {e}")
            return None

    def save_cache(self, key: str, data: Dict[str, Any]) -> None:
        """Save data to cache with memory caching."""
        cache_path = self._get_cache_path(key)
        current_time = time.time()

        try:
            with self._cache_lock:
                # Update memory cache first
                self._memory_cache[key] = data
                self._memory_cache_timestamps[key] = current_time

                # Create a temporary file first
                temp_path = f"{cache_path}.tmp"
                with open(temp_path, 'w') as f:
                    json.dump(data, f, cls=DateTimeEncoder)
                
                # Atomic rename to avoid corruption
                os.replace(temp_path, cache_path)
        except Exception as e:
            self.logger.error(f"Error saving cache for {key}: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

    def get_cached_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data with memory cache priority."""
        current_time = time.time()
        
        # Check memory cache first
        if key in self._memory_cache:
            if current_time - self._memory_cache_timestamps.get(key, 0) < 60:  # 1 minute TTL
                return self._memory_cache[key]
            else:
                # Clear expired memory cache
                del self._memory_cache[key]
                del self._memory_cache_timestamps[key]

        # Fall back to disk cache
        return self.load_cache(key)

    def clear_cache(self, key: Optional[str] = None) -> None:
        """Clear cache for a specific key or all keys."""
        with self._cache_lock:
            if key:
                # Clear specific key
                if key in self._memory_cache:
                    del self._memory_cache[key]
                    del self._memory_cache_timestamps[key]
                cache_path = self._get_cache_path(key)
                if os.path.exists(cache_path):
                    os.remove(cache_path)
            else:
                # Clear all keys
                self._memory_cache.clear()
                self._memory_cache_timestamps.clear()
                for file in os.listdir(self.cache_dir):
                    if file.endswith('.json'):
                        os.remove(os.path.join(self.cache_dir, file))

    def has_data_changed(self, data_type: str, new_data: Dict[str, Any]) -> bool:
        """Check if data has changed from cached version."""
        cached_data = self.load_cache(data_type)
        if not cached_data:
            return True

        if data_type == 'weather':
            return self._has_weather_changed(cached_data, new_data)
        elif data_type == 'stocks':
            return self._has_stocks_changed(cached_data, new_data)
        elif data_type == 'stock_news':
            return self._has_news_changed(cached_data, new_data)
        elif data_type == 'nhl':
            return self._has_nhl_changed(cached_data, new_data)
        
        return True

    def _has_weather_changed(self, cached: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Check if weather data has changed."""
        return (cached.get('temp') != new.get('temp') or 
                cached.get('condition') != new.get('condition'))

    def _has_stocks_changed(self, cached: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Check if stock data has changed."""
        if not self._is_market_open():
            return False
        return cached.get('price') != new.get('price')

    def _has_news_changed(self, cached: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Check if news data has changed."""
        # Handle both dictionary and list formats
        if isinstance(new, list):
            # If new data is a list, cached data should also be a list
            if not isinstance(cached, list):
                return True
            # Compare lengths and content
            if len(cached) != len(new):
                return True
            # Compare titles since they're unique enough for our purposes
            cached_titles = set(item.get('title', '') for item in cached)
            new_titles = set(item.get('title', '') for item in new)
            return cached_titles != new_titles
        else:
            # Original dictionary format handling
            cached_headlines = set(h.get('id') for h in cached.get('headlines', []))
            new_headlines = set(h.get('id') for h in new.get('headlines', []))
            return not cached_headlines.issuperset(new_headlines)

    def _has_nhl_changed(self, cached: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """Check if NHL data has changed."""
        return (cached.get('game_status') != new.get('game_status') or
                cached.get('score') != new.get('score'))

    def _is_market_open(self) -> bool:
        """Check if the US stock market is currently open."""
        et_tz = pytz.timezone('America/New_York')
        now = datetime.now(et_tz)
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            return False
            
        # Convert current time to ET
        current_time = now.time()
        market_open = datetime.strptime('09:30', '%H:%M').time()
        market_close = datetime.strptime('16:00', '%H:%M').time()
        
        return market_open <= current_time <= market_close

    def update_cache(self, data_type: str, data: Dict[str, Any]) -> bool:
        """Update cache with new data."""
        cache_data = {
            'data': data,
            'timestamp': time.time()
        }
        return self.save_cache(data_type, cache_data) 