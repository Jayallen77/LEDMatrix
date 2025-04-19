import requests
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw
from .weather_icons import WeatherIcons
from .cache_manager import CacheManager
import logging
import threading

class WeatherManager:
    # Weather condition to larger colored icons (we'll use these as placeholders until you provide custom ones)
    WEATHER_ICONS = {
        'Clear': '🌞',      # Larger sun with rays
        'Clouds': '☁️',     # Cloud
        'Rain': '🌧️',      # Rain cloud
        'Snow': '❄️',      # Snowflake
        'Thunderstorm': '⛈️', # Storm cloud
        'Drizzle': '🌦️',    # Sun behind rain cloud
        'Mist': '🌫️',      # Fog
        'Fog': '🌫️',       # Fog
        'Haze': '🌫️',      # Fog
        'Smoke': '🌫️',     # Fog
        'Dust': '🌫️',      # Fog
        'Sand': '🌫️',      # Fog
        'Ash': '🌫️',       # Fog
        'Squall': '💨',     # Dash symbol
        'Tornado': '🌪️'     # Tornado
    }

    def __init__(self, config: Dict[str, Any], display_manager):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.display_manager = display_manager
        self.weather_config = config.get('weather', {})
        self.location = config.get('location', {})
        self._last_update = 0
        self._update_interval = config.get('update_interval', 600)  # 10 minutes default
        self._last_state = None
        self._processing_lock = threading.Lock()
        self._cached_processed_data = None
        self._cache_timestamp = 0
        self.weather_data = None
        self.forecast_data = None
        self.hourly_forecast = None
        self.daily_forecast = None
        self.last_draw_time = 0
        self.cache_manager = CacheManager()
        # Layout constants
        self.PADDING = 1
        self.ICON_SIZE = {
            'extra_large': 40, # Changed from 30
            'large': 30,
            'medium': 24,
            'small': 14
        }
        self.COLORS = {
            'text': (255, 255, 255),
            'highlight': (255, 200, 0),
            'separator': (64, 64, 64),
            'temp_high': (255, 100, 100),
            'temp_low': (100, 100, 255),
            'dim': (180, 180, 180),
            'extra_dim': (120, 120, 120)  # Even dimmer for smallest text
        }
        # Add caching for last drawn states
        self.last_weather_state = None
        self.last_hourly_state = None
        self.last_daily_state = None

    def _process_forecast_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process forecast data with caching."""
        current_time = time.time()
        
        # Check if we have valid cached processed data
        if (self._cached_processed_data and 
            current_time - self._cache_timestamp < 60):  # Cache for 1 minute
            return self._cached_processed_data

        with self._processing_lock:
            # Double check after acquiring lock
            if (self._cached_processed_data and 
                current_time - self._cache_timestamp < 60):
                return self._cached_processed_data

            try:
                # Process the data
                processed_data = {
                    'current': self._process_current_conditions(data.get('current', {})),
                    'hourly': self._process_hourly_forecast(data.get('hourly', [])),
                    'daily': self._process_daily_forecast(data.get('daily', []))
                }

                # Cache the processed data
                self._cached_processed_data = processed_data
                self._cache_timestamp = current_time
                return processed_data
            except Exception as e:
                self.logger.error(f"Error processing forecast data: {e}")
                return {}

    def _fetch_weather(self) -> Optional[Dict[str, Any]]:
        """Fetch weather data with optimized caching."""
        current_time = time.time()
        
        # Check if we need to update
        if current_time - self._last_update < self._update_interval:
            cached_data = self.cache_manager.get_cached_data('weather', max_age=self._update_interval)
            if cached_data:
                self.logger.info("Using cached weather data")
                return self._process_forecast_data(cached_data)
            return None

        try:
            # Fetch new data from OpenWeatherMap API
            api_key = self.weather_config.get('api_key')
            location = self.location.get('city')  # Get city from location config
            if not location:
                self.logger.error("No location configured for weather")
                return None
                
            units = self.weather_config.get('units', 'imperial')
            
            # Fetch current weather
            current_url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": location,
                "appid": api_key,
                "units": units
            }
            
            response = requests.get(current_url, params=params, timeout=10)
            response.raise_for_status()
            current_data = response.json()
            
            # Fetch forecast
            forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
            response = requests.get(forecast_url, params=params, timeout=10)
            response.raise_for_status()
            forecast_data = response.json()
            
            # Combine the data
            data = {
                "current": current_data,
                "hourly": forecast_data.get("list", []),
                "daily": []  # Daily forecast will be processed from hourly data
            }
            
            self._last_update = current_time
            self.cache_manager.save_cache('weather', data)
            return self._process_forecast_data(data)
            
        except Exception as e:
            self.logger.error(f"Error fetching weather data: {e}")
            # Try to use cached data as fallback
            cached_data = self.cache_manager.get_cached_data('weather', max_age=self._update_interval)
            if cached_data:
                self.logger.info("Using cached weather data as fallback")
                return self._process_forecast_data(cached_data)
            return None

    def _process_current_conditions(self, current: Dict[str, Any]) -> Dict[str, Any]:
        """Process current conditions with minimal processing."""
        if not current:
            return {}
        
        return {
            'temp': current.get('temp', 0),
            'feels_like': current.get('feels_like', 0),
            'humidity': current.get('humidity', 0),
            'wind_speed': current.get('wind_speed', 0),
            'description': current.get('weather', [{}])[0].get('description', ''),
            'icon': current.get('weather', [{}])[0].get('icon', '')
        }

    def _process_hourly_forecast(self, hourly: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process hourly forecast with minimal processing."""
        if not hourly:
            return []
        
        return [{
            'time': hour.get('dt', 0),
            'temp': hour.get('temp', 0),
            'description': hour.get('weather', [{}])[0].get('description', ''),
            'icon': hour.get('weather', [{}])[0].get('icon', '')
        } for hour in hourly[:24]]  # Only process next 24 hours

    def _process_daily_forecast(self, daily: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process daily forecast with minimal processing."""
        if not daily:
            return []
        
        return [{
            'time': day.get('dt', 0),
            'temp_min': day.get('temp', {}).get('min', 0),
            'temp_max': day.get('temp', {}).get('max', 0),
            'description': day.get('weather', [{}])[0].get('description', ''),
            'icon': day.get('weather', [{}])[0].get('icon', '')
        } for day in daily[:7]]  # Only process next 7 days

    def get_weather(self) -> Dict[str, Any]:
        """Get current weather data, fetching new data if needed."""
        current_time = time.time()
        update_interval = self.weather_config.get('update_interval', 300)
        
        # Check if we need to update based on time or if we have no data
        if (not self.weather_data or 
            current_time - self._last_update > update_interval):
            
            # Check if data has changed before fetching
            current_state = self._get_weather_state()
            if current_state and not self.cache_manager.has_data_changed('weather', current_state):
                print("Weather data hasn't changed, using existing data")
                return self.weather_data
                
            self._fetch_weather()
            
        return self.weather_data

    def _get_weather_state(self) -> Dict[str, Any]:
        """Get current weather state for comparison."""
        if not self.weather_data:
            return None
        return {
            'temp': round(self.weather_data['main']['temp']),
            'condition': self.weather_data['weather'][0]['main'],
            'humidity': self.weather_data['main']['humidity']
        }

    def _get_hourly_state(self) -> List[Dict[str, Any]]:
        """Get current hourly forecast state for comparison."""
        if not self.hourly_forecast:
            return None
        return [
            {'hour': f['hour'], 'temp': round(f['temp']), 'condition': f['condition']}
            for f in self.hourly_forecast[:3]
        ]

    def _get_daily_state(self) -> List[Dict[str, Any]]:
        """Get current daily forecast state for comparison."""
        if not self.daily_forecast:
            return None
        return [
            {
                'date': f['date'],
                'temp_high': round(f['temp_high']),
                'temp_low': round(f['temp_low']),
                'condition': f['condition']
            }
            for f in self.daily_forecast[:4]  # Changed to 4 days
        ]

    def display_weather(self, force_clear: bool = False) -> None:
        """Display current weather information using a modern layout."""
        try:
            weather_data = self.get_weather()
            if not weather_data:
                print("No weather data available")
                return

            # Check if state has changed
            current_state = self._get_weather_state()
            if not force_clear and current_state == self.last_weather_state:
                return  # No need to redraw if nothing changed

            # Clear the display once at the start
            self.display_manager.clear()
            
            # Create a new image for drawing
            image = Image.new('RGB', (self.display_manager.matrix.width, self.display_manager.matrix.height))
            draw = ImageDraw.Draw(image)
            
            # --- Top Left: Icon ---
            condition = weather_data['weather'][0]['main']
            icon_size = self.ICON_SIZE['extra_large'] # Use extra_large size
            icon_x = 1 # Small padding from left edge
            # Center the icon vertically in the top two-thirds of the display
            available_height = (self.display_manager.matrix.height * 2) // 3  # Use top 2/3 of screen
            icon_y = (available_height - icon_size) // 2
            WeatherIcons.draw_weather_icon(image, condition, icon_x, icon_y, size=icon_size)
            
            # --- Top Right: Condition Text ---
            condition_text = condition
            condition_font = self.display_manager.small_font
            condition_text_width = draw.textlength(condition_text, font=condition_font)
            condition_x = self.display_manager.matrix.width - condition_text_width - 1 # Align right
            condition_y = 1 # Align top
            draw.text((condition_x, condition_y), 
                     condition_text, 
                     font=condition_font, 
                     fill=self.COLORS['text'])

            # --- Right Side (Below Condition): Current Temp ---
            temp = round(weather_data['main']['temp'])
            temp_text = f"{temp}°"
            temp_font = self.display_manager.small_font # Using small font
            temp_text_width = draw.textlength(temp_text, font=temp_font)
            temp_x = self.display_manager.matrix.width - temp_text_width - 1 # Align right
            temp_y = condition_y + 8 # Position below condition text (adjust 8 based on font size)
            draw.text((temp_x, temp_y),
                     temp_text,
                     font=temp_font,
                     fill=self.COLORS['highlight'])
            
            # --- Right Side (Below Current Temp): High/Low Temp ---
            temp_max = round(weather_data['main']['temp_max'])
            temp_min = round(weather_data['main']['temp_min'])
            high_low_text = f"{temp_min}°/{temp_max}°"
            high_low_font = self.display_manager.small_font # Using small font
            high_low_width = draw.textlength(high_low_text, font=high_low_font)
            high_low_x = self.display_manager.matrix.width - high_low_width - 1 # Align right
            high_low_y = temp_y + 8 # Position below current temp text (adjust 8 based on font size)
            draw.text((high_low_x, high_low_y),
                     high_low_text,
                     font=high_low_font,
                     fill=self.COLORS['dim'])
            
            # --- Bottom: Additional Metrics (Unchanged) ---
            display_width = self.display_manager.matrix.width
            section_width = display_width // 3
            y_pos = self.display_manager.matrix.height - 7 # Position near bottom for 6px font
            font = self.display_manager.extra_small_font # The 4x6 font

            # --- Pressure (Section 1) ---
            pressure = weather_data['main']['pressure'] * 0.02953
            pressure_text = f"P:{pressure:.1f}in"
            pressure_width = draw.textlength(pressure_text, font=font)
            pressure_x = (section_width - pressure_width) // 2 # Center in first third
            draw.text((pressure_x, y_pos),
                     pressure_text,
                     font=font,
                     fill=self.COLORS['dim'])
            
            # --- Humidity (Section 2) ---
            humidity = weather_data['main']['humidity']
            humidity_text = f"H:{humidity}%"
            humidity_width = draw.textlength(humidity_text, font=font)
            humidity_x = section_width + (section_width - humidity_width) // 2 # Center in second third
            draw.text((humidity_x, y_pos),
                     humidity_text,
                     font=font,
                     fill=self.COLORS['dim'])

            # --- Wind (Section 3) ---
            wind_speed = weather_data['wind']['speed']
            wind_deg = weather_data.get('wind', {}).get('deg', 0)
            wind_dir = self._get_wind_direction(wind_deg)
            wind_text = f"W:{wind_speed:.0f}{wind_dir}"
            wind_width = draw.textlength(wind_text, font=font)
            wind_x = (2 * section_width) + (section_width - wind_width) // 2 # Center in third third
            draw.text((wind_x, y_pos),
                     wind_text,
                     font=font,
                     fill=self.COLORS['dim'])
            
            # Update the display
            self.display_manager.image = image
            self.display_manager.update_display()
            self.last_weather_state = current_state

        except Exception as e:
            print(f"Error displaying weather: {e}")

    def _get_wind_direction(self, degrees: float) -> str:
        """Convert wind degrees to cardinal direction."""
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / 45) % 8
        return directions[index]

    def display_hourly_forecast(self, force_clear: bool = False):
        """Display the next few hours of weather forecast."""
        try:
            if not self.hourly_forecast:
                print("No hourly forecast data available")
                return
            
            # Check if state has changed
            current_state = self._get_hourly_state()
            if not force_clear and current_state == self.last_hourly_state:
                return
            
            # Clear the display
            self.display_manager.clear()
            
            # Create a new image for drawing
            image = Image.new('RGB', (self.display_manager.matrix.width, self.display_manager.matrix.height))
            draw = ImageDraw.Draw(image)
            
            # Calculate layout based on matrix dimensions
            hours_to_show = min(4, len(self.hourly_forecast))
            total_width = self.display_manager.matrix.width
            section_width = total_width // hours_to_show
            padding = max(2, section_width // 6)  # Increased padding for more space
            
            for i in range(hours_to_show):
                forecast = self.hourly_forecast[i]
                x = i * section_width + padding
                center_x = x + (section_width - 2 * padding) // 2
                
                # Draw hour at top
                hour_text = forecast['hour']
                hour_text = hour_text.replace(":00 ", "").replace("PM", "p").replace("AM", "a")
                hour_width = draw.textlength(hour_text, font=self.display_manager.small_font)
                draw.text((center_x - hour_width // 2, 1),
                         hour_text,
                         font=self.display_manager.small_font,
                         fill=self.COLORS['text'])
                
                # Draw weather icon centered vertically between top/bottom text
                icon_size = self.ICON_SIZE['large'] # Changed from medium to large (28)
                top_text_height = 8 # Approx height reservation for top text
                bottom_text_y = self.display_manager.matrix.height - 8 # Starting Y for bottom text
                available_height_for_icon = bottom_text_y - top_text_height
                # Ensure calculated y is not negative if space is very tight
                calculated_y = top_text_height + (available_height_for_icon - icon_size) // 2
                icon_y = (self.display_manager.matrix.height // 2) - 16
                icon_x = center_x - icon_size // 2
                WeatherIcons.draw_weather_icon(image, forecast['condition'], icon_x, icon_y, icon_size)
                
                # Draw temperature at bottom
                temp_text = f"{forecast['temp']}°"
                temp_width = draw.textlength(temp_text, font=self.display_manager.small_font)
                temp_y = self.display_manager.matrix.height - 8  # Position at bottom with small margin
                draw.text((center_x - temp_width // 2, temp_y),
                         temp_text,
                         font=self.display_manager.small_font,
                         fill=self.COLORS['text'])
            
            # Update the display
            self.display_manager.image = image
            self.display_manager.update_display()
            self.last_hourly_state = current_state

        except Exception as e:
            print(f"Error displaying hourly forecast: {e}")

    def display_daily_forecast(self, force_clear: bool = False):
        """Display the daily weather forecast."""
        try:
            if not self.daily_forecast:
                print("No daily forecast data available")
                return
            
            # Check if state has changed
            current_state = self._get_daily_state()
            if not force_clear and current_state == self.last_daily_state:
                return
            
            # Clear the display
            self.display_manager.clear()
            
            # Create a new image for drawing
            image = Image.new('RGB', (self.display_manager.matrix.width, self.display_manager.matrix.height))
            draw = ImageDraw.Draw(image)
            
            # Calculate layout based on matrix dimensions for 3 days
            days_to_show = min(3, len(self.daily_forecast)) # Changed from 4 to 3
            if days_to_show == 0:
                # Handle case where there's no forecast data after filtering
                draw.text((2, 2), "No daily forecast", font=self.display_manager.small_font, fill=self.COLORS['dim'])
            else:
                total_width = self.display_manager.matrix.width
                section_width = total_width // days_to_show # Divide by 3 (or fewer if less data)
                padding = max(2, section_width // 6)
                
                for i in range(days_to_show):
                    forecast = self.daily_forecast[i]
                    x = i * section_width # No need for padding here, centering handles spacing
                    center_x = x + section_width // 2 # Center within the section
                    
                    # Draw day name at top
                    day_text = forecast['date']
                    day_width = draw.textlength(day_text, font=self.display_manager.small_font)
                    draw.text((center_x - day_width // 2, 1),
                             day_text,
                             font=self.display_manager.small_font,
                             fill=self.COLORS['text'])
                    
                    # Draw weather icon centered vertically between top/bottom text
                    icon_size = self.ICON_SIZE['large'] # Changed from medium to large (28)
                    top_text_height = 8 # Approx height reservation for top text
                    bottom_text_y = self.display_manager.matrix.height - 8 # Starting Y for bottom text
                    available_height_for_icon = bottom_text_y - top_text_height
                    # Ensure calculated y is not negative if space is very tight
                    calculated_y = top_text_height + (available_height_for_icon - icon_size) // 2
                    icon_y = (self.display_manager.matrix.height // 2) - 16
                    icon_x = center_x - icon_size // 2
                    WeatherIcons.draw_weather_icon(image, forecast['condition'], icon_x, icon_y, icon_size)
                    
                    # Draw high/low temperatures at bottom (without degree symbol)
                    temp_text = f"{forecast['temp_low']} / {forecast['temp_high']}" # Removed degree symbols
                    temp_width = draw.textlength(temp_text, font=self.display_manager.extra_small_font)
                    temp_y = self.display_manager.matrix.height - 8  # Position at bottom with small margin
                    draw.text((center_x - temp_width // 2, temp_y),
                             temp_text,
                             font=self.display_manager.extra_small_font,
                             fill=self.COLORS['text'])
            
            # Update the display
            self.display_manager.image = image
            self.display_manager.update_display()
            self.last_daily_state = current_state

        except Exception as e:
            print(f"Error displaying daily forecast: {e}") 