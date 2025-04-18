import time
import logging
from typing import Dict, Any
from src.clock import Clock
from src.weather_manager import WeatherManager
from src.display_manager import DisplayManager
from src.config_manager import ConfigManager
from src.stock_manager import StockManager
from src.stock_news_manager import StockNewsManager
from src.nhl_managers import NHLLiveManager, NHLRecentManager, NHLUpcomingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

logger = logging.getLogger(__name__)

class DisplayController:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        self.display_manager = DisplayManager(self.config)
        
        # Initialize display modes
        self.clock = Clock(self.config, self.display_manager) if self.config['display'].get('clock_enabled', True) else None
        self.weather = WeatherManager(self.config, self.display_manager) if self.config['display'].get('weather_enabled', True) else None
        self.stocks = StockManager(self.config, self.display_manager) if self.config['display'].get('stocks_enabled', True) else None
        self.news = StockNewsManager(self.config, self.display_manager) if self.config['display'].get('news_enabled', True) else None
        
        # Initialize NHL managers if enabled
        nhl_enabled = self.config.get('nhl_scoreboard', {}).get('enabled', False)
        nhl_display_modes = self.config.get('nhl_scoreboard', {}).get('display_modes', {})
        
        if nhl_enabled:
            self.nhl_live = NHLLiveManager(self.config, self.display_manager) if nhl_display_modes.get('nhl_live', True) else None
            self.nhl_recent = NHLRecentManager(self.config, self.display_manager) if nhl_display_modes.get('nhl_recent', True) else None
            self.nhl_upcoming = NHLUpcomingManager(self.config, self.display_manager) if nhl_display_modes.get('nhl_upcoming', True) else None
        else:
            self.nhl_live = None
            self.nhl_recent = None
            self.nhl_upcoming = None
        
        # List of available display modes (adjust order as desired)
        self.available_modes = []
        if self.clock: self.available_modes.append('clock')
        if self.weather: self.available_modes.extend(['weather_current', 'weather_hourly', 'weather_daily'])
        if self.stocks: self.available_modes.append('stocks')
        if self.news: self.available_modes.append('stock_news')
        
        # Add NHL display modes if enabled
        if nhl_enabled:
            if self.nhl_live: self.available_modes.append('nhl_live')
            if self.nhl_recent: self.available_modes.append('nhl_recent')
            if self.nhl_upcoming: self.available_modes.append('nhl_upcoming')
        
        # Set initial display to first available mode
        self.current_mode_index = 0
        self.current_display_mode = self.available_modes[0] if self.available_modes else 'none'
        self.last_switch = time.time()
        self.force_clear = True
        self.update_interval = 0.1
        
        # Update display durations to include NHL modes
        self.display_durations = self.config['display'].get('display_durations', {
            'clock': 15,
            'weather_current': 15,
            'weather_hourly': 15,
            'weather_daily': 15,
            'stocks': 45,
            'nhl_live': 30,  # Live games update more frequently
            'nhl_recent': 60,  # Recent games - increased to 60 seconds to allow proper cycling
            'nhl_upcoming': 20,  # Upcoming games
            'stock_news': 30
        })
        logger.info("DisplayController initialized with display_manager: %s", id(self.display_manager))
        logger.info(f"Available display modes: {self.available_modes}")

    def get_current_duration(self) -> int:
        """Get the duration for the current display mode."""
        mode_key = self.current_display_mode
        if mode_key.startswith('weather_'):
            duration_key = mode_key.split('_', 1)[1]
            if duration_key == 'current': duration_key = 'weather'
            elif duration_key == 'hourly': duration_key = 'hourly_forecast'
            elif duration_key == 'daily': duration_key = 'daily_forecast'
            else: duration_key = 'weather'
            return self.display_durations.get(duration_key, 15)
        
        return self.display_durations.get(mode_key, 15)

    def _update_modules(self):
        """Call update methods on active managers."""
        if self.weather: self.weather.get_weather()
        if self.stocks: self.stocks.update_stock_data()
        if self.news: self.news.update_news_data()
        
        # Update NHL managers
        if self.nhl_live: self.nhl_live.update()
        if self.nhl_recent: self.nhl_recent.update()
        if self.nhl_upcoming: self.nhl_upcoming.update()

    def _check_live_games(self) -> bool:
        """Check if there are any live games available."""
        if not self.nhl_live:
            return False
        return bool(self.nhl_live.live_games)

    def run(self):
        """Run the display controller, switching between displays."""
        if not self.available_modes:
            logger.warning("No display modes are enabled. Exiting.")
            self.display_manager.cleanup()
            return
             
        try:
            while True:
                current_time = time.time()
                
                # Update data for all modules
                self._update_modules()
                
                # Check for live games
                has_live_games = self._check_live_games()
                
                # If we're in NHL live mode but there are no live games, skip to next mode
                if self.current_display_mode == 'nhl_live' and not has_live_games:
                    self.current_mode_index = (self.current_mode_index + 1) % len(self.available_modes)
                    self.current_display_mode = self.available_modes[self.current_mode_index]
                    logger.info(f"No live games, switching to: {self.current_display_mode}")
                    self.last_switch = current_time
                    self.force_clear = True
                
                # Check for mode switch
                elif current_time - self.last_switch > self.get_current_duration():
                    # If there are live games and we're not in NHL live mode, switch to it
                    if has_live_games and self.current_display_mode != 'nhl_live':
                        live_index = self.available_modes.index('nhl_live')
                        self.current_mode_index = live_index
                        self.current_display_mode = 'nhl_live'
                        logger.info("Live games available, switching to NHL live mode")
                    else:
                        self.current_mode_index = (self.current_mode_index + 1) % len(self.available_modes)
                        self.current_display_mode = self.available_modes[self.current_mode_index]
                        logger.info(f"Switching display to: {self.current_display_mode}")
                    
                    self.last_switch = current_time
                    self.force_clear = True

                # Display current mode frame
                try:
                    if self.current_display_mode == 'clock' and self.clock:
                        self.clock.display_time(force_clear=self.force_clear)
                        
                    elif self.current_display_mode == 'weather_current' and self.weather:
                        self.weather.display_weather(force_clear=self.force_clear)
                    elif self.current_display_mode == 'weather_hourly' and self.weather:
                        self.weather.display_hourly_forecast(force_clear=self.force_clear)
                    elif self.current_display_mode == 'weather_daily' and self.weather:
                        self.weather.display_daily_forecast(force_clear=self.force_clear)
                        
                    elif self.current_display_mode == 'stocks' and self.stocks:
                        self.stocks.display_stocks(force_clear=self.force_clear)
                        
                    elif self.current_display_mode == 'nhl_live' and self.nhl_live:
                        self.nhl_live.display(force_clear=self.force_clear)
                    elif self.current_display_mode == 'nhl_recent' and self.nhl_recent:
                        self.nhl_recent.display(force_clear=self.force_clear)
                    elif self.current_display_mode == 'nhl_upcoming' and self.nhl_upcoming:
                        self.nhl_upcoming.display(force_clear=self.force_clear)
                        
                    elif self.current_display_mode == 'stock_news' and self.news:
                        self.news.display_news()
                        
                except Exception as e:
                    logger.error(f"Error updating display for mode {self.current_display_mode}: {e}", exc_info=True)
                    time.sleep(1)
                    continue

                self.force_clear = False
                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            logger.info("Display controller stopped by user")
        except Exception as e:
            logger.error(f"Error in display controller: {e}", exc_info=True)
        finally:
            self.display_manager.cleanup()

def main():
    controller = DisplayController()
    controller.run()

if __name__ == "__main__":
    main() 