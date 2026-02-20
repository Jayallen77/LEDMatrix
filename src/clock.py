import time
import logging
import math
from datetime import datetime
import pytz
from typing import Optional
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
            logger.info("Loaded fonts from 5by7.regular.ttf")
        except Exception as e:
            logger.warning(f"Failed to load custom fonts: {e}. Using default fonts.")
            try:
                # Fallback to system fonts
                self.time_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
                self.date_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            except Exception:
                # Last resort: default PIL font
                self.time_font = ImageFont.load_default()
                self.date_font = ImageFont.load_default()
                logger.warning("Using default PIL font as fallback")

    def get_current_time(self) -> tuple[str, str]:
        """
        Get current time and date in the configured timezone.

        Returns:
            tuple: (time_str, date_str) where time_str is "H:MM" (12-hour format) and date_str is "MON DD"
        """
        try:
            current = datetime.now(self.timezone)

            # Format time as 12-hour format
            time_str = current.strftime('%I:%M')

            # Format date as "SEP 09"
            date_str = current.strftime('%b %d').upper()

            return time_str, date_str

        except Exception as e:
            logger.error(f"Error getting current time: {e}")
            return "00:00", "ERR"

    def display_time(self, force_clear: bool = False) -> None:
        """
        Display the current time and date on the LED matrix.

        Args:
            force_clear: If True, update display even if time hasn't changed
        """
        try:
            time_str, date_str = self.get_current_time()

            # Only update if time or date has changed, or forced
            if not force_clear and hasattr(self, '_last_time') and hasattr(self, '_last_date'):
                if time_str == self._last_time and date_str == self._last_date:
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

            # Update the display manager's image
            self.display_manager.image = image
            self.display_manager.draw = draw

            # Update the display
            self.display_manager.update_display()

            # Store last displayed values
            self._last_time = time_str
            self._last_date = date_str

            logger.debug(f"Displayed time: {time_str}, date: {date_str}")

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
            y = self.time_section_height + (self.date_section_height - text_height) // 2 - 6

            # Draw the date
            draw.text((x, y), date_str, font=self.date_font, fill=self.date_color)

        except Exception as e:
            logger.error(f"Error drawing date: {e}")

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