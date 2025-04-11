import time
import logging
from typing import Dict, Any
from src.clock import Clock
from src.weather_manager import WeatherManager
from src.display_manager import DisplayManager
from src.config_manager import ConfigManager
from src.stock_manager import StockManager
from src.stock_news_manager import StockNewsManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DisplayController:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        self.display_manager = DisplayManager(self.config.get('display', {}))
        self.clock = Clock(display_manager=self.display_manager)
        self.weather = WeatherManager(self.config, self.display_manager)
        self.stocks = StockManager(self.config, self.display_manager)
        self.news = StockNewsManager(self.config, self.display_manager)
        self.current_display = 'clock'
        self.weather_mode = 'current'  # current, hourly, or daily
        self.last_switch = time.time()
        self.force_clear = True  # Start with a clear screen
        self.update_interval = 0.5  # Slower updates for better stability
        self.display_durations = self.config['display'].get('display_durations', {
            'clock': 15,
            'weather': 15,
            'stocks': 45,
            'hourly_forecast': 15,
            'daily_forecast': 15,
            'stock_news': 30
        })
        logger.info("DisplayController initialized with display_manager: %s", id(self.display_manager))

    def get_current_duration(self) -> int:
        """Get the duration for the current display mode."""
        if self.current_display == 'weather':
            if self.weather_mode == 'hourly':
                return self.display_durations.get('hourly_forecast', 15)
            elif self.weather_mode == 'daily':
                return self.display_durations.get('daily_forecast', 15)
            return self.display_durations.get('weather', 15)
        return self.display_durations.get(self.current_display, 15)

    def run(self):
        """Run the display controller, switching between displays."""
        try:
            while True:
                current_time = time.time()
                
                # Check if we need to switch display mode
                if current_time - self.last_switch > self.get_current_duration():
                    # Find next enabled display mode
                    next_display = None
                    
                    if self.current_display == 'clock':
                        if self.config.get('weather', {}).get('enabled', False):
                            next_display = 'weather'
                            self.weather_mode = 'current'
                        elif self.config.get('stocks', {}).get('enabled', False):
                            next_display = 'stocks'
                        elif self.config.get('stock_news', {}).get('enabled', False):
                            next_display = 'stock_news'
                        else:
                            next_display = 'clock'
                            
                    elif self.current_display == 'weather':
                        if self.weather_mode == 'current':
                            next_display = 'weather'
                            self.weather_mode = 'hourly'
                        elif self.weather_mode == 'hourly':
                            next_display = 'weather'
                            self.weather_mode = 'daily'
                        else:  # daily
                            if self.config.get('stocks', {}).get('enabled', False):
                                next_display = 'stocks'
                            elif self.config.get('stock_news', {}).get('enabled', False):
                                next_display = 'stock_news'
                            elif self.config.get('clock', {}).get('enabled', False):
                                next_display = 'clock'
                            else:
                                next_display = 'weather'
                                self.weather_mode = 'current'
                                
                    elif self.current_display == 'stocks':
                        if self.config.get('stock_news', {}).get('enabled', False):
                            next_display = 'stock_news'
                        elif self.config.get('clock', {}).get('enabled', False):
                            next_display = 'clock'
                        elif self.config.get('weather', {}).get('enabled', False):
                            next_display = 'weather'
                            self.weather_mode = 'current'
                        else:
                            next_display = 'stocks'
                            
                    else:  # stock_news
                        if self.config.get('clock', {}).get('enabled', False):
                            next_display = 'clock'
                        elif self.config.get('weather', {}).get('enabled', False):
                            next_display = 'weather'
                            self.weather_mode = 'current'
                        elif self.config.get('stocks', {}).get('enabled', False):
                            next_display = 'stocks'
                        else:
                            next_display = 'stock_news'
                    
                    # Update current display
                    self.current_display = next_display
                    logger.info(f"Switching display to: {self.current_display} {self.weather_mode if self.current_display == 'weather' else ''}")
                    self.last_switch = current_time
                    self.force_clear = True
                    self.display_manager.clear()

                # Display current screen
                try:
                    if self.current_display == 'clock' and self.config.get('clock', {}).get('enabled', False):
                        self.clock.display_time(force_clear=self.force_clear)
                        time.sleep(self.update_interval)
                    elif self.current_display == 'weather' and self.config.get('weather', {}).get('enabled', False):
                        if self.weather_mode == 'current':
                            self.weather.display_weather(force_clear=self.force_clear)
                        elif self.weather_mode == 'hourly':
                            self.weather.display_hourly_forecast(force_clear=self.force_clear)
                        else:  # daily
                            self.weather.display_daily_forecast(force_clear=self.force_clear)
                        time.sleep(self.update_interval)
                    elif self.current_display == 'stocks' and self.config.get('stocks', {}).get('enabled', False):
                        self.stocks.display_stocks(force_clear=self.force_clear)
                        time.sleep(self.update_interval)
                    elif self.current_display == 'stock_news' and self.config.get('stock_news', {}).get('enabled', False):
                        # For news, we want to update as fast as possible without delay
                        self.news.display_news()
                except Exception as e:
                    logger.error(f"Error updating display: {e}")
                    time.sleep(1)  # Wait a bit before retrying
                    continue

                # Reset force clear flag after use
                self.force_clear = False

        except KeyboardInterrupt:
            print("\nDisplay stopped by user")
        finally:
            self.display_manager.cleanup()

def main():
    controller = DisplayController()
    controller.run()

if __name__ == "__main__":
    main() 