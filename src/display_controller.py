import time
import logging
from typing import Dict, Any
from src.clock import Clock
from src.weather_manager import WeatherManager
from src.display_manager import DisplayManager
from src.config_manager import ConfigManager
from src.stock_manager import StockManager
from src.stock_news_manager import StockNewsManager
from src.nhl_scoreboard import NHLScoreboardManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DisplayController:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        self.display_manager = DisplayManager(self.config.get('display', {}))
        
        # Only initialize enabled modules
        self.clock = Clock(display_manager=self.display_manager) if self.config.get('clock', {}).get('enabled', False) else None
        self.weather = WeatherManager(self.config, self.display_manager) if self.config.get('weather', {}).get('enabled', False) else None
        self.stocks = StockManager(self.config, self.display_manager) if self.config.get('stocks', {}).get('enabled', False) else None
        self.news = StockNewsManager(self.config, self.display_manager) if self.config.get('stock_news', {}).get('enabled', False) else None
        self.nhl = NHLScoreboardManager(self.config, self.display_manager) if self.config.get('nhl_scoreboard', {}).get('enabled', False) else None
        
        # List of available display modes (adjust order as desired)
        self.available_modes = []
        if self.clock: self.available_modes.append('clock')
        if self.weather: self.available_modes.extend(['weather_current', 'weather_hourly', 'weather_daily']) # Treat weather modes separately
        if self.stocks: self.available_modes.append('stocks')
        if self.nhl: self.available_modes.append('nhl') # Add NHL to the rotation
        if self.news: self.available_modes.append('stock_news')
        
        # Set initial display to first available mode
        self.current_mode_index = 0
        self.current_display_mode = self.available_modes[0] if self.available_modes else 'none' # Default if nothing enabled
        self.last_switch = time.time()
        self.force_clear = True  # Start with a clear screen
        self.update_interval = 0.1 # Faster check loop
        # Update display durations to include NHL
        self.display_durations = self.config['display'].get('display_durations', {
            'clock': 15,
            'weather_current': 15,
            'weather_hourly': 15,
            'weather_daily': 15,
            'stocks': 45,
            'nhl': 30, # Default NHL duration
            'stock_news': 30
        })
        logger.info("DisplayController initialized with display_manager: %s", id(self.display_manager))
        logger.info(f"Available display modes: {self.available_modes}")

    def get_current_duration(self) -> int:
        """Get the duration for the current display mode."""
        # Use the unified current_display_mode
        mode_key = self.current_display_mode
        # Map weather sub-modes if needed for duration lookup
        if mode_key.startswith('weather_'):
             duration_key = mode_key.split('_', 1)[1] # current, hourly, daily
             if duration_key == 'current': duration_key = 'weather' # Match config key
             elif duration_key == 'hourly': duration_key = 'hourly_forecast'
             elif duration_key == 'daily': duration_key = 'daily_forecast'
             else: duration_key = 'weather' # Fallback
             return self.display_durations.get(duration_key, 15)
        
        return self.display_durations.get(mode_key, 15) # Default duration 15s

    def _update_modules(self):
        """Call update methods on active managers."""
        # Update methods might have different frequencies, but call here for simplicity
        # Could add timers per module later if needed
        if self.weather: self.weather.get_weather() # weather update fetches data
        if self.stocks: self.stocks.update_stock_data() # Correct method name
        if self.news: self.news.update_news_data() # Correct method name
        if self.nhl: self.nhl.update()
        # Clock updates itself during display typically

    def run(self):
        """Run the display controller, switching between displays."""
        if not self.available_modes:
             logger.warning("No display modes are enabled. Exiting.")
             self.display_manager.cleanup()
             return
             
        try:
            while True:
                current_time = time.time()
                
                # --- Update Data for Modules ---
                # Call update method for all relevant modules periodically
                # (Frequency can be optimized later if needed)
                self._update_modules() 
                
                # --- Check for Mode Switch ---
                if current_time - self.last_switch > self.get_current_duration():
                    self.current_mode_index = (self.current_mode_index + 1) % len(self.available_modes)
                    self.current_display_mode = self.available_modes[self.current_mode_index]
                    
                    logger.info(f"Switching display to: {self.current_display_mode}")
                    self.last_switch = current_time
                    self.force_clear = True # Force clear on mode switch
                    # Clearing is likely handled by the display method or display_manager now
                    # self.display_manager.clear() 

                # --- Display Current Mode Frame ---
                try:
                    # Simplified display logic based on mode string
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
                        
                    elif self.current_display_mode == 'nhl' and self.nhl:
                        self.nhl.display(force_clear=self.force_clear)
                        
                    elif self.current_display_mode == 'stock_news' and self.news:
                        self.news.display_news() # Removed force_clear argument
                        
                except Exception as e:
                    logger.error(f"Error updating display for mode {self.current_display_mode}: {e}", exc_info=True)
                    # Avoid busy-looping on error, maybe skip frame or wait?
                    time.sleep(1) 
                    continue # Skip rest of loop iteration

                # Reset force clear flag after the first successful display in a mode
                self.force_clear = False 
                
                # Main loop delay - REMOVED for faster processing/scrolling
                # time.sleep(self.update_interval) 

        except KeyboardInterrupt:
            print("\nDisplay stopped by user")
        finally:
            self.display_manager.cleanup()

def main():
    controller = DisplayController()
    controller.run()

if __name__ == "__main__":
    main() 