import time
import logging
import sys
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s:%(name)s:%(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout
)

from src.clock import Clock
from src.weather_manager import WeatherManager
from src.display_manager import DisplayManager
from src.config_manager import ConfigManager
from src.stock_manager import StockManager
from src.stock_news_manager import StockNewsManager
from src.nhl_managers import NHLLiveManager, NHLRecentManager, NHLUpcomingManager
from src.nba_managers import NBALiveManager, NBARecentManager, NBAUpcomingManager
from src.mlb_manager import MBLLiveManager, MLBRecentManager, MLBUpcomingManager
from src.youtube_display import YouTubeDisplay
from src.calendar_manager import CalendarManager

# Get logger without configuring
logger = logging.getLogger(__name__)

class DisplayController:
    def __init__(self):
        start_time = time.time()
        logger.info("Starting DisplayController initialization")
        
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        logger.info("Config loaded in %.3f seconds", time.time() - start_time)
        
        config_time = time.time()
        self.display_manager = DisplayManager(self.config)
        logger.info("DisplayManager initialized in %.3f seconds", time.time() - config_time)
        
        # Initialize display modes
        init_time = time.time()
        self.clock = Clock(self.display_manager) if self.config.get('clock', {}).get('enabled', True) else None
        self.weather = WeatherManager(self.config, self.display_manager) if self.config.get('weather', {}).get('enabled', False) else None
        self.stocks = StockManager(self.config, self.display_manager) if self.config.get('stocks', {}).get('enabled', False) else None
        self.news = StockNewsManager(self.config, self.display_manager) if self.config.get('stock_news', {}).get('enabled', False) else None
        self.calendar = CalendarManager(self.display_manager, self.config) if self.config.get('calendar', {}).get('enabled', False) else None
        self.youtube = YouTubeDisplay(self.display_manager, self.config) if self.config.get('youtube', {}).get('enabled', False) else None
        logger.info(f"Calendar Manager initialized: {'Object' if self.calendar else 'None'}")
        logger.info("Display modes initialized in %.3f seconds", time.time() - init_time)
        
        # Initialize NHL managers if enabled
        nhl_time = time.time()
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
            
        # Initialize NBA managers if enabled
        nba_enabled = self.config.get('nba_scoreboard', {}).get('enabled', False)
        nba_display_modes = self.config.get('nba_scoreboard', {}).get('display_modes', {})
        
        if nba_enabled:
            self.nba_live = NBALiveManager(self.config, self.display_manager) if nba_display_modes.get('nba_live', True) else None
            self.nba_recent = NBARecentManager(self.config, self.display_manager) if nba_display_modes.get('nba_recent', True) else None
            self.nba_upcoming = NBAUpcomingManager(self.config, self.display_manager) if nba_display_modes.get('nba_upcoming', True) else None
        else:
            self.nba_live = None
            self.nba_recent = None
            self.nba_upcoming = None

        # Initialize MLB managers if enabled
        mlb_time = time.time()
        mlb_enabled = self.config.get('mlb', {}).get('enabled', False)
        mlb_display_modes = self.config.get('mlb', {}).get('display_modes', {})
        
        if mlb_enabled:
            self.mlb_live = MBLLiveManager(self.config, self.display_manager) if mlb_display_modes.get('mlb_live', True) else None
            self.mlb_recent = MLBRecentManager(self.config, self.display_manager) if mlb_display_modes.get('mlb_recent', True) else None
            self.mlb_upcoming = MLBUpcomingManager(self.config, self.display_manager) if mlb_display_modes.get('mlb_upcoming', True) else None
        else:
            self.mlb_live = None
            self.mlb_recent = None
            self.mlb_upcoming = None
            
        # Track MLB rotation state
        self.mlb_current_team_index = 0
        self.mlb_showing_recent = True
        self.mlb_favorite_teams = self.config.get('mlb', {}).get('favorite_teams', [])
        self.in_mlb_rotation = False
        
        # List of available display modes (adjust order as desired)
        self.available_modes = []
        if self.clock: self.available_modes.append('clock')
        if self.weather: self.available_modes.extend(['weather_current', 'weather_hourly', 'weather_daily'])
        if self.stocks: self.available_modes.append('stocks')
        if self.news: self.available_modes.append('stock_news')
        if self.calendar: self.available_modes.append('calendar')
        if self.youtube: self.available_modes.append('youtube')
        
        # Add NHL display modes if enabled
        if nhl_enabled:
            if self.nhl_recent: self.available_modes.append('nhl_recent')
            if self.nhl_upcoming: self.available_modes.append('nhl_upcoming')
            # nhl_live is handled separately when live games are available
        
        # Add NBA display modes if enabled
        if nba_enabled:
            if self.nba_recent: self.available_modes.append('nba_recent')
            if self.nba_upcoming: self.available_modes.append('nba_upcoming')
            # nba_live is handled separately when live games are available
            
        # Add MLB display modes if enabled
        if mlb_enabled:
            if mlb_display_modes.get('mlb_recent', True): self.available_modes.append('mlb_recent')
            if mlb_display_modes.get('mlb_upcoming', True): self.available_modes.append('mlb_upcoming')
            # mlb_live is handled separately when live games are available
        
        # Set initial display to first available mode (clock)
        self.current_mode_index = 0
        self.current_display_mode = self.available_modes[0] if self.available_modes else 'none'
        self.last_switch = time.time()
        self.force_clear = True
        self.update_interval = 0.01  # Reduced from 0.1 to 0.01 for smoother scrolling
        
        # Track team-based rotation states
        self.nhl_current_team_index = 0
        self.nhl_showing_recent = True
        self.nhl_favorite_teams = self.config.get('nhl_scoreboard', {}).get('favorite_teams', [])
        self.in_nhl_rotation = False
        
        self.nba_current_team_index = 0
        self.nba_showing_recent = True
        self.nba_favorite_teams = self.config.get('nba_scoreboard', {}).get('favorite_teams', [])
        self.in_nba_rotation = False
        
        self.mlb_current_team_index = 0
        self.mlb_showing_recent = True
        self.mlb_favorite_teams = self.config.get('mlb', {}).get('favorite_teams', [])
        self.in_mlb_rotation = False
        
        # Update display durations to include all modes
        self.display_durations = self.config['display'].get('display_durations', {
            'clock': 15,
            'weather_current': 15,
            'weather_hourly': 15,
            'weather_daily': 15,
            'stocks': 45,
            'stock_news': 30,
            'calendar': 30,
            'youtube': 30,
            'nhl_live': 30,
            'nhl_recent': 20,
            'nhl_upcoming': 20,
            'nba_live': 30,
            'nba_recent': 20,
            'nba_upcoming': 20,
            'mlb_live': 30,
            'mlb_recent': 20,
            'mlb_upcoming': 20
        })
        
        logger.info("DisplayController initialized with display_manager: %s", id(self.display_manager))
        logger.info(f"Available display modes: {self.available_modes}")
        logger.info(f"NHL Favorite teams: {self.nhl_favorite_teams}")
        logger.info(f"NBA Favorite teams: {self.nba_favorite_teams}")
        logger.info(f"MLB Favorite teams: {self.mlb_favorite_teams}")
        logger.info("NHL managers initialized in %.3f seconds", time.time() - nhl_time)
        logger.info("MLB managers initialized in %.3f seconds", time.time() - mlb_time)

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
        if self.calendar: self.calendar.update(time.time())
        if self.youtube: self.youtube.update()
        
        # Update NHL managers
        if self.nhl_live: self.nhl_live.update()
        if self.nhl_recent: self.nhl_recent.update()
        if self.nhl_upcoming: self.nhl_upcoming.update()
        
        # Update NBA managers
        if self.nba_live: self.nba_live.update()
        if self.nba_recent: self.nba_recent.update()
        if self.nba_upcoming: self.nba_upcoming.update()
        
        # Update MLB managers
        if self.mlb_live: self.mlb_live.update()
        if self.mlb_recent: self.mlb_recent.update()
        if self.mlb_upcoming: self.mlb_upcoming.update()

    def _check_live_games(self) -> tuple[bool, str]:
        """
        Check if there are any live games available.
        Returns:
            tuple[bool, str]: (has_live_games, sport_type)
            sport_type will be 'nhl', 'nba', 'mlb' or None
        """
        # Check NHL live games
        if self.nhl_live and self.nhl_live.live_games:
            return True, 'nhl'
            
        # Check NBA live games
        if self.nba_live and self.nba_live.live_games:
            return True, 'nba'
            
        # Check MLB live games
        if self.mlb_live and self.mlb_live.live_games:
            return True, 'mlb'
            
        return False, None

    def _get_team_games(self, team: str, sport: str = 'nhl', is_recent: bool = True) -> bool:
        """
        Get games for a specific team and update the current game.
        Args:
            team: Team abbreviation
            sport: 'nhl', 'nba', or 'mlb'
            is_recent: Whether to look for recent or upcoming games
        Returns:
            bool: True if games were found and set
        """
        if sport == 'nhl':
            if is_recent and self.nhl_recent:
                # Find recent games for this team
                for game in self.nhl_recent.games_list:
                    if game["home_abbr"] == team or game["away_abbr"] == team:
                        self.nhl_recent.current_game = game
                        return True
            elif not is_recent and self.nhl_upcoming:
                # Find upcoming games for this team
                for game in self.nhl_upcoming.games_list:
                    if game["home_abbr"] == team or game["away_abbr"] == team:
                        self.nhl_upcoming.current_game = game
                        return True
        elif sport == 'nba':
            if is_recent and self.nba_recent:
                # Find recent games for this team
                for game in self.nba_recent.games_list:
                    if game["home_abbr"] == team or game["away_abbr"] == team:
                        self.nba_recent.current_game = game
                        return True
            elif not is_recent and self.nba_upcoming:
                # Find upcoming games for this team
                for game in self.nba_upcoming.games_list:
                    if game["home_abbr"] == team or game["away_abbr"] == team:
                        self.nba_upcoming.current_game = game
                        return True
        elif sport == 'mlb':
            if is_recent and self.mlb_recent:
                # Find recent games for this team
                for game in self.mlb_recent.recent_games:
                    if game['home_team'] == team or game['away_team'] == team:
                        self.mlb_recent.current_game = game
                        return True
            elif not is_recent and self.mlb_upcoming:
                # Find upcoming games for this team
                for game in self.mlb_upcoming.upcoming_games:
                    if game['home_team'] == team or game['away_team'] == team:
                        self.mlb_upcoming.current_game = game
                        return True
        return False

    def _has_team_games(self, sport: str = 'nhl') -> bool:
        """Check if there are any games for favorite teams."""
        if sport == 'nhl':
            return bool(self.nhl_favorite_teams and (self.nhl_recent or self.nhl_upcoming))
        elif sport == 'nba':
            return bool(self.nba_favorite_teams and (self.nba_recent or self.nba_upcoming))
        elif sport == 'mlb':
            return bool(self.mlb_favorite_teams and self.mlb_live)
        return False

    def _rotate_team_games(self, sport: str = 'nhl') -> None:
        """Rotate through games for favorite teams."""
        if sport == 'nhl':
            if not self._has_team_games('nhl'): return
            
            # Try to find games for current team
            current_team = self.nhl_favorite_teams[self.nhl_current_team_index]
            found_games = self._get_team_games(current_team, 'nhl', self.nhl_showing_recent)
            
            if not found_games:
                # Try opposite type (recent/upcoming) for same team
                self.nhl_showing_recent = not self.nhl_showing_recent
                found_games = self._get_team_games(current_team, 'nhl', self.nhl_showing_recent)
            
            if not found_games:
                # Move to next team
                self.nhl_current_team_index = (self.nhl_current_team_index + 1) % len(self.nhl_favorite_teams)
                self.nhl_showing_recent = True  # Reset to recent games for next team
                
        elif sport == 'nba':
            if not self._has_team_games('nba'): return
            
            # Try to find games for current team
            current_team = self.nba_favorite_teams[self.nba_current_team_index]
            found_games = self._get_team_games(current_team, 'nba', self.nba_showing_recent)
            
            if not found_games:
                # Try opposite type (recent/upcoming) for same team
                self.nba_showing_recent = not self.nba_showing_recent
                found_games = self._get_team_games(current_team, 'nba', self.nba_showing_recent)
            
            if not found_games:
                # Move to next team
                self.nba_current_team_index = (self.nba_current_team_index + 1) % len(self.nba_favorite_teams)
                self.nba_showing_recent = True  # Reset to recent games for next team
                
        elif sport == 'mlb':
            if not self._has_team_games('mlb'): return
            
            # Try to find games for current team
            current_team = self.mlb_favorite_teams[self.mlb_current_team_index]
            found_games = self._get_team_games(current_team, 'mlb', self.mlb_showing_recent)
            
            if not found_games:
                # Try opposite type (recent/upcoming) for same team
                self.mlb_showing_recent = not self.mlb_showing_recent
                found_games = self._get_team_games(current_team, 'mlb', self.mlb_showing_recent)
            
            if not found_games:
                # Move to next team
                self.mlb_current_team_index = (self.mlb_current_team_index + 1) % len(self.mlb_favorite_teams)
                self.mlb_showing_recent = True  # Reset to recent games for next team

    def run(self):
        """Main display loop."""
        try:
            while True:
                current_time = time.time()
                
                # Check for live games first
                has_live_games, sport_type = self._check_live_games()
                
                if has_live_games:
                    # Handle live game display
                    if sport_type == 'nhl' and self.nhl_live:
                        self.nhl_live.display_games(self.force_clear)
                        self.current_display_mode = 'nhl_live'
                    elif sport_type == 'nba' and self.nba_live:
                        self.nba_live.display_games(self.force_clear)
                        self.current_display_mode = 'nba_live'
                    elif sport_type == 'mlb' and self.mlb_live:
                        self.mlb_live.display_games(self.force_clear)
                        self.current_display_mode = 'mlb_live'
                else:
                    # Regular display rotation
                    if current_time - self.last_switch >= self.get_current_duration():
                        self.current_mode_index = (self.current_mode_index + 1) % len(self.available_modes)
                        self.current_display_mode = self.available_modes[self.current_mode_index]
                        self.last_switch = current_time
                        self.force_clear = True
                        
                        # Reset rotation flags when switching modes
                        if not self.current_display_mode.startswith('nhl_'):
                            self.in_nhl_rotation = False
                        if not self.current_display_mode.startswith('nba_'):
                            self.in_nba_rotation = False
                        if not self.current_display_mode.startswith('mlb_'):
                            self.in_mlb_rotation = False
                    
                    # Handle current display mode
                    if self.current_display_mode == 'clock' and self.clock:
                        self.clock.display_time()
                    elif self.current_display_mode.startswith('weather_') and self.weather:
                        mode = self.current_display_mode.split('_')[1]
                        self.weather.display_weather(mode)
                    elif self.current_display_mode == 'stocks' and self.stocks:
                        done = self.stocks.display_stocks(self.force_clear)
                        if done: self.force_clear = True
                    elif self.current_display_mode == 'stock_news' and self.news:
                        done = self.news.display_news(self.force_clear)
                        if done: self.force_clear = True
                    elif self.current_display_mode == 'calendar' and self.calendar:
                        self.calendar.display()
                    elif self.current_display_mode == 'youtube' and self.youtube:
                        self.youtube.display()
                    elif self.current_display_mode.startswith('nhl_'):
                        self._handle_nhl_display()
                    elif self.current_display_mode.startswith('nba_'):
                        self._handle_nba_display()
                    elif self.current_display_mode.startswith('mlb_'):
                        self._handle_mlb_display()
                
                # Update modules periodically
                self._update_modules()
                
                # Reset force clear flag
                self.force_clear = False
                
                # Small delay to prevent excessive CPU usage
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("Display loop interrupted by user")
        except Exception as e:
            logger.error(f"Error in display loop: {e}", exc_info=True)
        finally:
            self.display_manager.clear()

    def _handle_mlb_display(self):
        """Handle MLB display modes."""
        if self.current_display_mode == 'mlb_live' and self.mlb_live:
            self.mlb_live.display(self.force_clear)
        elif self.current_display_mode == 'mlb_recent' and self.mlb_recent:
            self.mlb_recent.display(self.force_clear)
        elif self.current_display_mode == 'mlb_upcoming' and self.mlb_upcoming:
            self.mlb_upcoming.display(self.force_clear)

def main():
    controller = DisplayController()
    controller.run()

if __name__ == "__main__":
    main() 