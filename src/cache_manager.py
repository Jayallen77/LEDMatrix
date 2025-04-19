import json
import os
import time
from datetime import datetime
import pytz
from typing import Any, Dict, Optional
import logging
import stat

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class CacheManager:
    def __init__(self, cache_dir: str = "cache"):
        self.logger = logging.getLogger(__name__)
        self.cache_dir = cache_dir
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists with proper permissions."""
        if not os.path.exists(self.cache_dir):
            try:
                # If running as root, use /tmp by default
                if os.geteuid() == 0:
                    self.cache_dir = os.path.join("/tmp", "ledmatrix_cache")
                    self.logger.info(f"Running as root, using temporary cache directory: {self.cache_dir}")
                # Try to create in user's home directory if current directory fails
                elif not os.access(os.getcwd(), os.W_OK):
                    home_dir = os.path.expanduser("~")
                    self.cache_dir = os.path.join(home_dir, ".ledmatrix_cache")
                    self.logger.info(f"Using cache directory in home: {self.cache_dir}")
                
                # Create directory with 755 permissions (rwxr-xr-x)
                os.makedirs(self.cache_dir, mode=0o755, exist_ok=True)
                
                # If running as sudo, change ownership to the real user
                if os.geteuid() == 0:  # Check if running as root
                    import pwd
                    # Get the real user (not root)
                    real_user = os.environ.get('SUDO_USER')
                    if real_user:
                        uid = pwd.getpwnam(real_user).pw_uid
                        gid = pwd.getpwnam(real_user).pw_gid
                        os.chown(self.cache_dir, uid, gid)
                        self.logger.info(f"Changed cache directory ownership to {real_user}")
            except Exception as e:
                self.logger.error(f"Error setting up cache directory: {e}")
                # Fall back to /tmp if all else fails
                self.cache_dir = os.path.join("/tmp", "ledmatrix_cache")
                try:
                    os.makedirs(self.cache_dir, mode=0o755, exist_ok=True)
                    self.logger.info(f"Using temporary cache directory: {self.cache_dir}")
                except Exception as e:
                    self.logger.error(f"Failed to create temporary cache directory: {e}")
                    raise

    def _get_cache_path(self, data_type: str) -> str:
        """Get the path for a specific cache file."""
        return os.path.join(self.cache_dir, f"{data_type}_cache.json")

    def load_cache(self, data_type: str) -> Optional[Dict[str, Any]]:
        """Load cached data for a specific type."""
        cache_path = self._get_cache_path(data_type)
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading cache for {data_type}: {e}")
        return None

    def save_cache(self, data_type: str, data: Dict[str, Any]) -> bool:
        """Save data to cache with proper permissions."""
        cache_path = self._get_cache_path(data_type)
        try:
            # Create a temporary file first
            temp_path = cache_path + '.tmp'
            with open(temp_path, 'w') as f:
                json.dump(data, f, cls=DateTimeEncoder)
            
            # Set proper permissions (644 - rw-r--r--)
            os.chmod(temp_path, 0o644)
            
            # If running as sudo, change ownership to the real user
            if os.geteuid() == 0:  # Check if running as root
                import pwd
                real_user = os.environ.get('SUDO_USER')
                if real_user:
                    uid = pwd.getpwnam(real_user).pw_uid
                    gid = pwd.getpwnam(real_user).pw_gid
                    os.chown(temp_path, uid, gid)
            
            # Rename temp file to actual cache file (atomic operation)
            os.replace(temp_path, cache_path)
            return True
        except Exception as e:
            self.logger.error(f"Error saving cache for {data_type}: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False

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

    def get_cached_data(self, data_type: str) -> Optional[Dict[str, Any]]:
        """Get cached data if it exists and is still valid."""
        cached = self.load_cache(data_type)
        if not cached:
            return None

        # Check if cache is still valid based on data type
        if data_type == 'weather' and time.time() - cached['timestamp'] > 600:  # 10 minutes
            return None
        elif data_type == 'stocks' and time.time() - cached['timestamp'] > 300:  # 5 minutes
            return None
        elif data_type == 'stock_news' and time.time() - cached['timestamp'] > 800:  # ~13 minutes
            return None
        elif data_type == 'nhl' and time.time() - cached['timestamp'] > 60:  # 1 minute
            return None

        return cached['data'] 