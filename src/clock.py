import time
import logging
import math
from datetime import datetime, timedelta
import pytz
from typing import Any, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from src.config_manager import ConfigManager
from src.display_manager import DisplayManager

# Get logger
logger = logging.getLogger(__name__)


class Clock:
    """
    A modern, elegant digital clock display for 64x64 LED matrix.

    Features:
    - Real-time time display in 12-hour format
    - Month and date display below time
    - Clean, centered layout optimized for 64x64 resolution
    - Automatic timezone handling
    - Error handling and logging
    """

    PHASE_COLORS = {
        "sunrise": ((255, 235, 165), (255, 210, 95)),
        "day": ((220, 240, 255), (190, 225, 255)),
        "sunset": ((255, 145, 45), (190, 105, 225)),
        "night": ((70, 110, 180), (55, 85, 145)),
        "late_night": ((135, 50, 35), (130, 75, 25)),
    }
    TEMPERATURE_ANCHORS = (
        (32.0, (45, 100, 255)),
        (50.0, (65, 220, 255)),
        (72.0, (205, 255, 215)),
        (80.0, (255, 225, 55)),
        (88.0, (255, 135, 30)),
        (89.0, (255, 45, 35)),
    )

    def __init__(self, display_manager: Optional[DisplayManager] = None):
        """
        Initialize the digital clock.

        Args:
            display_manager: Optional DisplayManager instance. If None, creates a new one.
        """
        try:
            self.config_manager = ConfigManager()
            self.config = self.config_manager.load_config()

            # Initialize display manager
            self.display_manager = display_manager or DisplayManager(self.config.get('display', {}))
            logger.info("Clock initialized with display_manager")

            # Get configuration
            self.location = self.config.get('location', {})
            self.clock_config = self.config.get('clock', {})
            self.weather_provider = None

            # Setup timezone
            self.timezone = self._get_timezone()

            # Load fonts
            self._load_fonts()

            # Display dimensions
            self.width = self.display_manager.width
            self.height = self.display_manager.height

            # Colors
            self.time_color = (255, 255, 255)  # White
            self.date_color = (180, 180, 180)  # Light gray

            # Layout constants
            self.time_section_height = int(self.height * 2 / 3)  # Top 2/3 for time
            self.date_section_height = self.height - self.time_section_height  # Bottom 1/3 for date

            logger.info(f"Clock setup complete. Display: {self.width}x{self.height}")

        except Exception as e:
            logger.error(f"Failed to initialize Clock: {e}", exc_info=True)
            raise

    def _get_timezone(self) -> pytz.timezone:
        """Get timezone from configuration with fallback to UTC."""
        config_timezone = self.config_manager.get_timezone()
        try:
            return pytz.timezone(config_timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(
                f"Invalid timezone '{config_timezone}' in config. "
                "Falling back to UTC. Please check your config.json file."
            )
            return pytz.utc

    def _load_fonts(self):
        """Load fonts for time and date display."""
        try:
            # Try to load a clean sans-serif font
            font_path = "assets/fonts/5by7.regular.ttf"
            self.time_font = ImageFont.truetype(font_path, 24)
            self.date_font = ImageFont.truetype(font_path, 16)
            self.temperature_font = ImageFont.truetype(font_path, 10)
            logger.info("Loaded fonts from 5by7.regular.ttf")
        except Exception as e:
            logger.warning(f"Failed to load custom fonts: {e}. Using default fonts.")
            try:
                # Fallback to system fonts
                self.time_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
                self.date_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
                self.temperature_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            except Exception:
                # Last resort: default PIL font
                self.time_font = ImageFont.load_default()
                self.date_font = ImageFont.load_default()
                self.temperature_font = ImageFont.load_default()
                logger.warning("Using default PIL font as fallback")

    def set_weather_provider(self, weather_provider) -> None:
        """Attach an existing WeatherManager without initiating a fetch."""
        self.weather_provider = weather_provider
        self._last_display_state = None

    def _get_current_datetime(self) -> datetime:
        return datetime.now(self.timezone)

    def get_current_time(
        self,
        current: Optional[datetime] = None,
    ) -> tuple[str, str]:
        """
        Get current time and date in the configured timezone.

        Returns:
            tuple: (time_str, date_str) where time_str is "H:MM" (12-hour format) and date_str is "MON DD"
        """
        try:
            current = current or self._get_current_datetime()

            # Format time as 12-hour format
            time_str = current.strftime('%I:%M')

            # Format date as "SEP 09"
            date_str = current.strftime('%b %d').upper()

            return time_str, date_str

        except Exception as e:
            logger.error(f"Error getting current time: {e}")
            return "00:00", "ERR"

    @staticmethod
    def _interpolate_color(
        start: Tuple[int, int, int],
        end: Tuple[int, int, int],
        ratio: float,
    ) -> Tuple[int, int, int]:
        ratio = max(0.0, min(1.0, ratio))
        return tuple(
            round(start[index] + ((end[index] - start[index]) * ratio))
            for index in range(3)
        )

    def _temperature_color(self, fahrenheit: float) -> Tuple[int, int, int]:
        anchors = self.TEMPERATURE_ANCHORS
        if fahrenheit <= anchors[0][0]:
            return anchors[0][1]
        for (start_temp, start_color), (end_temp, end_color) in zip(
            anchors,
            anchors[1:],
        ):
            if fahrenheit <= end_temp:
                ratio = (fahrenheit - start_temp) / (end_temp - start_temp)
                return self._interpolate_color(start_color, end_color, ratio)
        return anchors[-1][1]

    @staticmethod
    def _dim_color(
        color: Tuple[int, int, int],
        brightness: float = 0.5,
    ) -> Tuple[int, int, int]:
        return tuple(round(channel * brightness) for channel in color)

    def _get_temperature(self) -> Optional[Dict[str, Any]]:
        provider = self.weather_provider
        weather_data = getattr(provider, "weather_data", None)
        try:
            raw_temperature = weather_data["main"]["temp"]
            temperature = float(raw_temperature)
        except (TypeError, ValueError, KeyError):
            return None
        if not math.isfinite(temperature):
            return None

        units = str(
            getattr(provider, "weather_config", {}).get(
                "units",
                self.config.get("weather", {}).get("units", "imperial"),
            )
        ).lower()
        fahrenheit = (
            (temperature * 9 / 5) + 32
            if units == "metric"
            else temperature
        )
        return {
            "text": f"{round(temperature)}°",
            "fahrenheit": fahrenheit,
        }

    def _parse_sun_time(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return self.timezone.localize(parsed)
            return parsed.astimezone(self.timezone)
        except (TypeError, ValueError):
            return None

    def _get_sun_times(
        self,
        current: datetime,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        forecast_data = getattr(self.weather_provider, "forecast_data", None)
        daily = (
            forecast_data.get("daily", {})
            if isinstance(forecast_data, dict)
            else {}
        )
        sunrises = daily.get("sunrise") or []
        sunsets = daily.get("sunset") or []
        if not sunrises or not sunsets:
            return None, None

        index = 0
        dates = daily.get("time") or []
        if dates:
            index = -1
            for candidate_index, candidate_date in enumerate(dates):
                try:
                    if (
                        datetime.fromisoformat(str(candidate_date)).date()
                        == current.date()
                    ):
                        index = candidate_index
                        break
                except (TypeError, ValueError):
                    continue
            if index < 0:
                return None, None
        if index >= len(sunrises) or index >= len(sunsets):
            return None, None
        return (
            self._parse_sun_time(sunrises[index]),
            self._parse_sun_time(sunsets[index]),
        )

    def _get_day_phase(
        self,
        current: datetime,
        sunrise: Optional[datetime] = None,
        sunset: Optional[datetime] = None,
    ) -> str:
        if sunrise and sunset:
            sunrise_start = sunrise - timedelta(minutes=30)
            sunrise_end = sunrise + timedelta(minutes=90)
            sunset_start = sunset - timedelta(minutes=90)
            sunset_end = sunset + timedelta(minutes=30)
            if sunrise_start <= current < sunrise_end:
                return "sunrise"
            if sunrise_end <= current < sunset_start:
                return "day"
            if sunset_start <= current < sunset_end:
                return "sunset"
            if current >= sunset_end:
                return "night"
            return "late_night"

        minutes = (current.hour * 60) + current.minute
        if 300 <= minutes < 450:
            return "sunrise"
        if 450 <= minutes < 1110:
            return "day"
        if 1110 <= minutes < 1260:
            return "sunset"
        if 1260 <= minutes < 1440:
            return "night"
        return "late_night"

    @staticmethod
    def _is_after_sunset(
        current: datetime,
        phase: str,
        sunrise: Optional[datetime],
        sunset: Optional[datetime],
    ) -> bool:
        if sunrise and sunset:
            return current >= sunset or current < sunrise
        return phase in {"night", "late_night"}

    def display_time(self, force_clear: bool = False) -> None:
        """
        Display the current time and date on the LED matrix.

        Args:
            force_clear: If True, update display even if time hasn't changed
        """
        try:
            current = self._get_current_datetime()
            time_str, date_str = self.get_current_time(current)
            sunrise, sunset = self._get_sun_times(current)
            phase = self._get_day_phase(current, sunrise, sunset)
            self.time_color, self.date_color = self.PHASE_COLORS[phase]
            temperature = self._get_temperature()
            temperature_text = temperature["text"] if temperature else None
            temperature_color = None
            if temperature:
                temperature_color = self._temperature_color(
                    temperature["fahrenheit"]
                )
                if self._is_after_sunset(
                    current,
                    phase,
                    sunrise,
                    sunset,
                ):
                    temperature_color = self._dim_color(temperature_color)

            display_state = (
                time_str,
                date_str,
                temperature_text,
                temperature_color,
                phase,
            )
            if (
                not force_clear
                and getattr(self, "_last_display_state", None) == display_state
            ):
                return

            # Clear the display
            self.display_manager.clear()

            # Create a new image for rendering
            image = Image.new('RGB', (self.width, self.height), (0, 0, 0))
            draw = ImageDraw.Draw(image)

            # Draw time in top 2/3 section
            self._draw_time(draw, time_str)

            # Draw date in bottom 1/3 section
            self._draw_date(draw, date_str)
            if temperature_text and temperature_color:
                self._draw_temperature(
                    draw,
                    temperature_text,
                    temperature_color,
                )

            # Update the display manager's image
            self.display_manager.image = image
            self.display_manager.draw = draw

            # Update the display
            self.display_manager.update_display()

            # Store last displayed values
            self._last_time = time_str
            self._last_date = date_str
            self._last_display_state = display_state

            logger.debug(
                "Displayed time=%s date=%s temp=%s phase=%s",
                time_str,
                date_str,
                temperature_text,
                phase,
            )

        except Exception as e:
            logger.error(f"Error displaying time: {e}", exc_info=True)

    def _draw_time(self, draw: ImageDraw.Draw, time_str: str) -> None:
        """Draw the time in the top section of the display."""
        try:
            # Get text bounding box
            bbox = draw.textbbox((0, 0), time_str, font=self.time_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Center horizontally and vertically in top 2/3
            x = (self.width - text_width) // 2
            y = (self.time_section_height - text_height) // 2

            # Draw the time
            draw.text((x, y), time_str, font=self.time_font, fill=self.time_color)

        except Exception as e:
            logger.error(f"Error drawing time: {e}")

    def _draw_date(self, draw: ImageDraw.Draw, date_str: str) -> None:
        """Draw the date in the bottom section of the display."""
        try:
            # Get text bounding box
            bbox = draw.textbbox((0, 0), date_str, font=self.date_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Center horizontally in bottom 1/3
            x = (self.width - text_width) // 2
            y = self.time_section_height + (self.date_section_height - text_height) // 2 - 9

            # Draw the date
            draw.text((x, y), date_str, font=self.date_font, fill=self.date_color)

        except Exception as e:
            logger.error(f"Error drawing date: {e}")

    def _draw_temperature(
        self,
        draw: ImageDraw.Draw,
        temperature_text: str,
        color: Tuple[int, int, int],
    ) -> None:
        """Draw the current outside temperature below the date."""
        try:
            bbox = draw.textbbox(
                (0, 0),
                temperature_text,
                font=self.temperature_font,
            )
            text_width = bbox[2] - bbox[0]
            x = (self.width - text_width) // 2
            y = self.height - 2 - bbox[3]
            draw.text(
                (x, y),
                temperature_text,
                font=self.temperature_font,
                fill=color,
            )
        except Exception as e:
            logger.error(f"Error drawing temperature: {e}")

    def run(self) -> None:
        """Run the clock display loop with real-time updates."""
        logger.info("Starting digital clock display loop")

        try:
            update_interval = self.clock_config.get('update_interval', 1)

            while True:
                self.display_time()
                time.sleep(update_interval)

        except KeyboardInterrupt:
            logger.info("Clock display stopped by user")
        except Exception as e:
            logger.error(f"Error in clock display loop: {e}", exc_info=True)
        finally:
            try:
                self.display_manager.cleanup()
                logger.info("Display manager cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    try:
        clock = Clock()
        clock.run()
    except Exception as e:
        logger.error(f"Failed to start clock: {e}", exc_info=True)
        print(f"Error starting clock: {e}")
