import requests
import time
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List
from PIL import Image, ImageDraw
import freetype
from .weather_icons import WeatherIcons
from .cache_manager import CacheManager

# Get logger without configuring
logger = logging.getLogger(__name__)

# Import the API counter function from web interface
try:
    from web_interface_v2 import increment_api_counter
except ImportError:
    # Fallback if web interface is not available
    def increment_api_counter(kind: str, count: int = 1):
        pass

class WeatherManager:

    def __init__(self, config: Dict[str, Any], display_manager, cache_manager=None):
        self.config = config
        self.display_manager = display_manager
        self.weather_config = config.get('weather', {})
        self.location = config.get('location', {})
        self.last_update = 0
        self.weather_data = None
        self.forecast_data = None
        self.daily_forecast = None
        self.last_draw_time = 0
        self.cache_manager = cache_manager or CacheManager()

        # Load secrets file (not needed for Open-Meteo but kept for compatibility)
        self.secrets = {}
        try:
            secrets_path = os.path.join('config', 'config_secrets.json')
            with open(secrets_path, 'r') as f:
                self.secrets = json.load(f)
        except Exception as e:
            logger.error(f"Error loading secrets file: {e}")
            self.secrets = {}
        
        # Error handling and throttling
        self.consecutive_errors = 0
        self.last_error_time = 0
        self.error_backoff_time = 60  # Start with 1 minute backoff
        self.max_consecutive_errors = 5  # Stop trying after 5 consecutive errors
        self.error_log_throttle = 300  # Only log errors every 5 minutes
        self.last_error_log_time = 0
        
        # Layout constants for 64x64 matrix
        self.PADDING = 1
        self.COLORS = {
            'text': (255, 255, 255),
            'highlight': (255, 255, 0),
            'dim': (128, 128, 128),
        }
        
        # State tracking for efficient updates
        self.last_weather_state = None
        self.last_daily_state = None
        
        # Initialize with first update
        self.update_weather()

    def _fetch_weather(self) -> None:
        """Fetch current weather and forecast data from Open-Meteo API."""
        current_time = time.time()
        
        # Check if we're in error backoff period
        if self.consecutive_errors >= self.max_consecutive_errors:
            if current_time - self.last_error_time < self.error_backoff_time:
                # Still in backoff period, don't attempt fetch
                if current_time - self.last_error_log_time > self.error_log_throttle:
                    print(f"Weather API disabled due to {self.consecutive_errors} consecutive errors. Retrying in {self.error_backoff_time - (current_time - self.last_error_time):.0f} seconds")
                    self.last_error_log_time = current_time
                return
            else:
                # Backoff period expired, reset error count and try again
                self.consecutive_errors = 0
                self.error_backoff_time = 60  # Reset to initial backoff
        
        # Open-Meteo doesn't require an API key

        # Try to get cached data first
        cached_data = self.cache_manager.get('weather')
        if cached_data:
            self.weather_data = cached_data.get('current')
            self.forecast_data = cached_data.get('forecast')
            if self.weather_data and self.forecast_data:
                self._process_forecast_data(self.forecast_data)

        city = self.location['city']
        state = self.location['state']
        country = self.location['country']
        units = self.weather_config.get('units', 'imperial')

        # Open-Meteo API calls (no API key required)
        try:
            # First get coordinates using Open-Meteo geocoding
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"

            response = requests.get(geo_url)
            response.raise_for_status()
            geo_data = response.json()

            # Increment API counter for geocoding call
            increment_api_counter('weather', 1)

            if not geo_data.get('results'):
                print(f"Could not find coordinates for {city}")
                return

            lat = geo_data['results'][0]['latitude']
            lon = geo_data['results'][0]['longitude']

            # Get weather data using Open-Meteo weather API
            # Convert units: imperial = fahrenheit, metric = celsius
            temperature_unit = "fahrenheit" if units == "imperial" else "celsius"
            wind_speed_unit = "mph" if units == "imperial" else "kmh"

            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,showers,snowfall,weather_code,pressure_msl,cloud_cover,wind_speed_10m,wind_direction_10m,uv_index&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,showers_sum,snowfall_sum,uv_index_max&temperature_unit={temperature_unit}&wind_speed_unit={wind_speed_unit}&timezone=auto"

            response = requests.get(weather_url)
            response.raise_for_status()
            weather_data = response.json()

            # Increment API counter for weather data call
            increment_api_counter('weather', 1)
            
            # Store current weather data (Open-Meteo format)
            current = weather_data['current']
            daily = weather_data['daily']

            # Convert Open-Meteo weather code to weather description
            weather_description = self._weather_code_to_description(current['weather_code'])

            self.weather_data = {
                'main': {
                    'temp': current['temperature_2m'],
                    'temp_max': daily['temperature_2m_max'][0],
                    'temp_min': daily['temperature_2m_min'][0],
                    'humidity': current['relative_humidity_2m'],
                    'pressure': current['pressure_msl'],
                    'uvi': current['uv_index']
                },
                'weather': [{
                    'main': weather_description['main'],
                    'description': weather_description['description'],
                    'icon': weather_description['icon']
                }],
                'wind': {
                    'speed': current['wind_speed_10m'],
                    'deg': current['wind_direction_10m']
                }
            }

            # Store forecast data (Open-Meteo format)
            self.forecast_data = weather_data
            
            # Process forecast data
            self._process_forecast_data(self.forecast_data)
            
            # Cache the new data
            cache_data = {
                'current': self.weather_data,
                'forecast': self.forecast_data
            }
            self.cache_manager.update_cache('weather', cache_data)
            
            self.last_update = time.time()
            # Reset error count on successful fetch
            self.consecutive_errors = 0
            print("Weather data updated successfully")

        except Exception as e:
            self.consecutive_errors += 1
            self.last_error_time = current_time
            
            # Exponential backoff: double the backoff time (max 1 hour)
            self.error_backoff_time = min(self.error_backoff_time * 2, 3600)
            
            # Only log errors periodically to avoid spam
            if current_time - self.last_error_log_time > self.error_log_throttle:
                print(f"Error fetching weather data (attempt {self.consecutive_errors}/{self.max_consecutive_errors}): {e}")
                if self.consecutive_errors >= self.max_consecutive_errors:
                    print(f"Weather API disabled for {self.error_backoff_time} seconds due to repeated failures")
                self.last_error_log_time = current_time
            
            # If we have cached data, use it as fallback
            if cached_data:
                self.weather_data = cached_data.get('current')
                self.forecast_data = cached_data.get('forecast')
                if self.weather_data and self.forecast_data:
                    self._process_forecast_data(self.forecast_data)
                    print("Using cached weather data as fallback")
            else:
                self.weather_data = None
                self.forecast_data = None

    def _process_forecast_data(self, forecast_data: Dict[str, Any]) -> None:
        """Process forecast data into daily forecasts (Open-Meteo format)."""
        if not forecast_data:
            return

        # Process daily forecast - Open-Meteo format
        daily_data = forecast_data.get('daily', {})
        if daily_data and 'time' in daily_data:
            self.daily_forecast = []

            # Skip today (index 0) and get next 4 days
            for i in range(1, min(5, len(daily_data['time']))):
                dt = datetime.fromisoformat(daily_data['time'][i])
                temp_high = round(daily_data['temperature_2m_max'][i])
                temp_low = round(daily_data['temperature_2m_min'][i])

                # Get weather description for this day
                weather_code = daily_data.get('weather_code', [0] * len(daily_data['time']))[i]
                weather_desc = self._weather_code_to_description(weather_code)

                self.daily_forecast.append({
                    'date': dt.strftime('%a'),  # Day name (Mon, Tue, etc.)
                    'date_str': dt.strftime('%m/%d'),  # Date (4/8, 4/9, etc.)
                    'temp_high': temp_high,
                    'temp_low': temp_low,
                    'condition': weather_desc['main'],
                    'icon': weather_desc['icon']
                })

    def _weather_code_to_description(self, weather_code: int) -> Dict[str, str]:
        """Convert Open-Meteo weather code to weather description."""
        # Open-Meteo weather codes: https://open-meteo.com/en/docs
        weather_codes = {
            0: {'main': 'Clear', 'description': 'Sunny', 'icon': '01d'},  # Clear sky
            1: {'main': 'Clear', 'description': 'Mostly Sunny', 'icon': '01d'},  # Mainly clear
            2: {'main': 'Clouds', 'description': 'Partly Cloudy', 'icon': '02d'},  # Partly cloudy
            3: {'main': 'Clouds', 'description': 'Overcast', 'icon': '04d'},  # Overcast
            45: {'main': 'Fog', 'description': 'Foggy', 'icon': '50d'},  # Fog
            48: {'main': 'Fog', 'description': 'Freezing Fog', 'icon': '50d'},  # Depositing rime fog
            51: {'main': 'Drizzle', 'description': 'Light Drizzle', 'icon': '09d'},  # Light drizzle
            53: {'main': 'Drizzle', 'description': 'Drizzle', 'icon': '09d'},  # Moderate drizzle
            55: {'main': 'Drizzle', 'description': 'Heavy Drizzle', 'icon': '09d'},  # Dense drizzle
            56: {'main': 'Drizzle', 'description': 'Light Freezing Drizzle', 'icon': '09d'},  # Light freezing drizzle
            57: {'main': 'Drizzle', 'description': 'Freezing Drizzle', 'icon': '09d'},  # Dense freezing drizzle
            61: {'main': 'Rain', 'description': 'Light Rain', 'icon': '10d'},  # Slight rain
            63: {'main': 'Rain', 'description': 'Rain', 'icon': '10d'},  # Moderate rain
            65: {'main': 'Rain', 'description': 'Heavy Rain', 'icon': '10d'},  # Heavy rain
            66: {'main': 'Rain', 'description': 'Light Freezing Rain', 'icon': '10d'},  # Light freezing rain
            67: {'main': 'Rain', 'description': 'Freezing Rain', 'icon': '10d'},  # Heavy freezing rain
            71: {'main': 'Snow', 'description': 'Light Snow', 'icon': '13d'},  # Slight snow fall
            73: {'main': 'Snow', 'description': 'Snow', 'icon': '13d'},  # Moderate snow fall
            75: {'main': 'Snow', 'description': 'Heavy Snow', 'icon': '13d'},  # Heavy snow fall
            77: {'main': 'Snow', 'description': 'Snow Grains', 'icon': '13d'},  # Snow grains
            80: {'main': 'Rain', 'description': 'Light Showers', 'icon': '09d'},  # Slight rain showers
            81: {'main': 'Rain', 'description': 'Showers', 'icon': '09d'},  # Moderate rain showers
            82: {'main': 'Rain', 'description': 'Heavy Showers', 'icon': '09d'},  # Violent rain showers
            85: {'main': 'Snow', 'description': 'Light Snow Showers', 'icon': '13d'},  # Slight snow showers
            86: {'main': 'Snow', 'description': 'Snow Showers', 'icon': '13d'},  # Heavy snow showers
            95: {'main': 'Thunderstorm', 'description': 'Thunderstorm', 'icon': '11d'},  # Thunderstorm
            96: {'main': 'Thunderstorm', 'description': 'Light Hail', 'icon': '11d'},  # Thunderstorm with slight hail
            99: {'main': 'Thunderstorm', 'description': 'Heavy Hail', 'icon': '11d'},  # Thunderstorm with heavy hail
        }

        return weather_codes.get(weather_code, {'main': 'Unknown', 'description': 'Unknown', 'icon': '01d'})

    def get_weather(self) -> Dict[str, Any]:
        """Get current weather data, fetching new data if needed."""
        current_time = time.time()
        update_interval = self.weather_config.get('update_interval', 300)
        # Add a throttle for log spam
        log_throttle_interval = 600  # 10 minutes
        if not hasattr(self, '_last_weather_log_time'):
            self._last_weather_log_time = 0
        # Check if we need to update based on time or if we have no data
        if (not self.weather_data or
            current_time - self.last_update > update_interval):
            self._fetch_weather()
        return self.weather_data

    def _get_weather_state(self) -> Dict[str, Any]:
        """Get current weather state for comparison."""
        if not self.weather_data:
            return None
        return {
            'temp': round(self.weather_data['main']['temp']),
            'condition': self.weather_data['weather'][0]['main'],
            'humidity': self.weather_data['main']['humidity'],
            'uvi': round(self.weather_data['main'].get('uvi', 0))
        }

    def _get_daily_state(self) -> List[Dict[str, Any]]:
        """Get current daily forecast state for comparison."""
        if not self.daily_forecast:
            return None
        return [
            {
                'date': f['date'],
                'temp_high': f['temp_high'],
                'temp_low': f['temp_low'],
                'condition': f['condition']
            }
            for f in self.daily_forecast[:4]  # Changed to 4 days
        ]

    def display_weather(self, force_clear: bool = False) -> None:
        """Display current weather information optimized for 64x64 LED matrix."""
        try:
            weather_data = self.get_weather()
            if not weather_data:
                print("No weather data available")
                # Create image with message to ensure display updates
                width = self.display_manager.matrix.width
                height = self.display_manager.matrix.height
                image = Image.new('RGB', (width, height))
                draw = ImageDraw.Draw(image)
                draw.text((10, 20), "No weather data", font=self.display_manager.regular_font, fill=self.COLORS['text'])
                self.display_manager.image = image
                self.display_manager.update_display()
                return

            # Check if state has changed
            current_state = self._get_weather_state()
            if not force_clear and current_state == self.last_weather_state:
                return  # No need to redraw if nothing changed

            # Clear the display
            self.display_manager.clear()

            # Create a new image for drawing
            width = self.display_manager.matrix.width  # 64
            height = self.display_manager.matrix.height  # 64
            image = Image.new('RGB', (width, height))
            draw = ImageDraw.Draw(image)

            # Get weather data
            temp = round(weather_data['main']['temp'])
            temp_max = round(weather_data['main']['temp_max'])
            temp_min = round(weather_data['main']['temp_min'])
            condition = weather_data['weather'][0]['main']
            icon_code = weather_data['weather'][0]['icon']
            humidity = weather_data['main']['humidity']

            # === TOP SECTION: Weather Icon + Condition ===
            # Weather icon (top-left corner) - Reduced by 15%, moved up 7px and left 7px total
            icon_size = 37  # 15% smaller than 43 (43 * 0.85 ≈ 37)
            icon_x = -4  # Move 4 pixels left from edge (was -7, now -4)
            icon_y = -7  # Move up 7 pixels total (was -11, now -7)
            WeatherIcons.draw_weather_icon(image, icon_code, icon_x, icon_y, size=icon_size)

            # Condition text (right side, top) - Made smaller font, fine-tuned position
            condition_text = condition[:7]  # Truncate to fit better
            condition_font = self.display_manager.extra_small_font  # Smaller font
            condition_x = 33  # Moved 6 pixels left (was 39, now 33)
            condition_y = 8   # Moved 1 pixel up (was 9, now 8)
            draw.text((condition_x, condition_y), condition_text,
                     font=condition_font, fill=self.COLORS['text'])

            # === MIDDLE SECTION: Temperature ===
            # Main temperature (center + 4px right) - moved down 6 pixels, with degree symbol, 30% bigger
            temp_text = f"{temp}°"  # Bring back degree symbol for current temp
            
            # Create a larger font (20% bigger than current size 12)
            try:
                from PIL import ImageFont
                temp_font = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 14)  # 20% bigger (12 * 1.2 ≈ 14)
            except:
                # Fallback to regular font if loading fails
                temp_font = self.display_manager.regular_font
            
            temp_bbox = draw.textbbox((0, 0), temp_text, font=temp_font)
            temp_width = temp_bbox[2] - temp_bbox[0]
            temp_x = (width - temp_width) // 2 + 7  # Center horizontally + 7px right (4 + 3)
            temp_y = 26  # Moved down 6 pixels from 20 to 26
            draw.text((temp_x, temp_y), temp_text,
                     font=temp_font, fill=self.COLORS['highlight'])

            # High/Low temps (below main temp) - moved down 6 pixels total
            hl_font = self.display_manager.extra_small_font
            hl_y = temp_y + 18  # Moved down 3 more pixels (was +15, now +18)
            
            # Create high/low displays with simple geometric icons
            try:
                # Use simple geometric shapes that look clean
                from PIL import Image as PILImage, ImageDraw as PILImageDraw
                
                icon_size = 4  # 30% smaller geometric icons (6 * 0.7 ≈ 4)
                
                # Low temperature section (left side) with down arrow shape
                low_section_x = (width // 2) - 18

                # Draw a small down arrow for low temp
                arrow_img = PILImage.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
                arrow_draw = PILImageDraw.Draw(arrow_img)
                # Draw down arrow: triangle pointing down
                arrow_draw.polygon([(icon_size//2, icon_size-1), (0, 0), (icon_size-1, 0)],
                                 fill=(100, 150, 255, 255))
                image.paste(arrow_img, (low_section_x, hl_y), arrow_img)

                # Low temperature text
                low_text_x = low_section_x + icon_size + 2
                draw.text((low_text_x, hl_y), f"{temp_min}",
                         font=hl_font, fill=(100, 150, 255))

                # High temperature section (right side) with up arrow shape
                high_section_x = (width // 2) + 6
                
                # Draw a small up arrow for high temp
                arrow_img_up = PILImage.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
                arrow_draw_up = PILImageDraw.Draw(arrow_img_up)
                # Draw up arrow: triangle pointing up
                arrow_draw_up.polygon([(icon_size//2, 0), (0, icon_size-1), (icon_size-1, icon_size-1)], 
                                    fill=(255, 100, 100, 255))
                image.paste(arrow_img_up, (high_section_x, hl_y), arrow_img_up)
                
                # High temperature text
                high_text_x = high_section_x + icon_size + 2
                draw.text((high_text_x, hl_y), f"{temp_max}",
                         font=hl_font, fill=(255, 100, 100))
                
            except Exception as e:
                # Simple fallback with basic characters
                low_full = f"L {temp_min}"
                high_full = f"H {temp_max}"
                
                low_bbox = draw.textbbox((0, 0), low_full, font=hl_font)
                high_bbox = draw.textbbox((0, 0), high_full, font=hl_font)
                low_width = low_bbox[2] - low_bbox[0]
                high_width = high_bbox[2] - high_bbox[0]
                
                spacing = 12
                total_width = low_width + spacing + high_width
                start_x = (width - total_width) // 2
                
                # Draw with simple L/H indicators
                draw.text((start_x, hl_y), low_full,
                         font=hl_font, fill=(100, 150, 255))
                draw.text((start_x + low_width + spacing, hl_y), high_full,
                         font=hl_font, fill=(255, 100, 100))

            # === BOTTOM SECTION: Additional Info with Labels ===
            bottom_font = self.display_manager.extra_small_font
            bottom_y = height - 12
            label_y = height - 8
            
            # Humidity (bottom left) with RH label
            hum_value = f"{humidity}%"
            hum_rh_label = "RH"
            hum_x = 2
            
            # Draw humidity percentage
            draw.text((hum_x, label_y), hum_value,
                     font=bottom_font, fill=self.COLORS['text'])
            
            # Calculate position for RH label (right of percentage)
            hum_value_bbox = draw.textbbox((0, 0), hum_value, font=bottom_font)
            hum_value_width = hum_value_bbox[2] - hum_value_bbox[0]
            rh_x = hum_x + hum_value_width + 2  # 2px spacing
            
            # Draw RH label
            draw.text((rh_x, label_y), hum_rh_label,
                     font=bottom_font, fill=self.COLORS['dim'])

            # UV Index (bottom right) - color-coded value
            uv_index = weather_data['main'].get('uvi', 0)
            uv_text = f"UV :{uv_index:.0f}"
            uv_bbox = draw.textbbox((0, 0), uv_text, font=bottom_font)
            uv_width = uv_bbox[2] - uv_bbox[0]
            uv_x = width - uv_width - 2
            uv_color = self._get_uv_color(uv_index)
            draw.text((uv_x, label_y), uv_text,
                     font=bottom_font, fill=uv_color)

            # Update the display
            self.display_manager.image = image
            self.display_manager.update_display()
            self.last_weather_state = current_state

        except Exception as e:
            print(f"Error displaying weather: {e}")

    def _get_uv_color(self, uv_index: float) -> tuple:
        """Get color for UV index display."""
        if uv_index <= 2:
            return (0, 255, 0)  # Green - Low
        elif uv_index <= 5:
            return (255, 255, 0)  # Yellow - Moderate
        elif uv_index <= 7:
            return (255, 165, 0)  # Orange - High
        elif uv_index <= 10:
            return (255, 0, 0)  # Red - Very High
        else:
            return (128, 0, 128)  # Purple - Extreme

    def display_daily_forecast(self, force_clear: bool = False):
        """Display daily forecast optimized for 64x64 LED matrix."""
        try:
            if not self.daily_forecast:
                print("No daily forecast data available")
                # Create image with message to ensure display updates
                width = self.display_manager.matrix.width
                height = self.display_manager.matrix.height
                image = Image.new('RGB', (width, height))
                draw = ImageDraw.Draw(image)
                draw.text((10, 20), "No forecast data", font=self.display_manager.regular_font, fill=self.COLORS['text'])
                self.display_manager.image = image
                self.display_manager.update_display()
                return

            # Check if state has changed
            current_state = self._get_daily_state()
            if not force_clear and current_state == self.last_daily_state:
                return  # No need to redraw if nothing changed

            # Clear the display
            self.display_manager.clear()

            # Create a new image for drawing
            width = self.display_manager.matrix.width  # 64
            height = self.display_manager.matrix.height  # 64
            image = Image.new('RGB', (width, height))
            draw = ImageDraw.Draw(image)

            # Display up to 4 days of forecast
            forecast_to_show = self.daily_forecast[:4]
            y_start = 7  # Adjusted for 4 days without title, moved down 5 pixels
            row_height = 15  # Reduced to fit 4 days in 64px height

            for i, day_data in enumerate(forecast_to_show):
                y = y_start + (i * row_height)

                # Day name (left) - moved down 3 pixels
                day_text = day_data['date'][:3]  # Mon, Tue, etc.
                draw.text((2, y), day_text, font=self.display_manager.extra_small_font,
                         fill=self.COLORS['text'])

                # Weather icon (center-left) - repositioned and 20% larger, moved up 2 pixels
                icon_x = 17  # Moved 3 pixels left (was 20, now 17)
                icon_y = y - 10  # Adjusted for new y_start to center icon, moved up 2 pixels
                WeatherIcons.draw_weather_icon(image, day_data['icon'], icon_x, icon_y, size=24)  # 20% larger (20 * 1.2 = 24)

                # High/Low temps (right) - moved down 3 pixels
                temp_text = f"{day_data['temp_low']}/{day_data['temp_high']}"
                temp_bbox = draw.textbbox((0, 0), temp_text, font=self.display_manager.extra_small_font)
                temp_width = temp_bbox[2] - temp_bbox[0]
                temp_x = width - temp_width - 2
                draw.text((temp_x, y), temp_text, font=self.display_manager.extra_small_font,
                         fill=self.COLORS['highlight'])

            # Update the display
            self.display_manager.image = image
            self.display_manager.update_display()
            self.last_daily_state = current_state

        except Exception as e:
            print(f"Error displaying daily forecast: {e}")

    def update_weather(self):
        """Update weather data."""
        self._fetch_weather()