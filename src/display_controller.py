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
from src.nba_managers import NBALiveManager, NBARecentManager, NBAUpcomingManager
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
        self.calendar = CalendarManager(self.display_manager.matrix, self.display_manager.current_canvas, self.config) if self.config.get('calendar', {}).get('enabled', False) else None
        self.youtube = YouTubeDisplay() if self.config.get('youtube', {}).get('enabled', False) else None
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
        
        # Set initial display to first available mode (clock)
        self.current_mode_index = 0
        self.current_display_mode = self.available_modes[0] if self.available_modes else 'none'
        self.last_switch = time.time()
        self.force_clear = True
        self.update_interval = 0.01  # Reduced from 0.1 to 0.01 for smoother scrolling
        
        # Track team-based rotation state for NHL
        self.nhl_current_team_index = 0
        self.nhl_showing_recent = True  # True for recent, False for upcoming
        self.nhl_favorite_teams = self.config.get('nhl_scoreboard', {}).get('favorite_teams', [])
        self.in_nhl_rotation = False  # Track if we're in NHL rotation
        
        # Track team-based rotation state for NBA
        self.nba_current_team_index = 0
        self.nba_showing_recent = True  # True for recent, False for upcoming
        self.nba_favorite_teams = self.config.get('nba_scoreboard', {}).get('favorite_teams', [])
        self.in_nba_rotation = False  # Track if we're in NBA rotation
        
        # Update display durations to include NHL and NBA modes
        self.display_durations = self.config['display'].get('display_durations', {
            'clock': 15,
            'weather_current': 15,
            'weather_hourly': 15,
            'weather_daily': 15,
            'stocks': 45,
            'stock_news': 30,
            'calendar': 30,
            'youtube': 30
        })
        logger.info("DisplayController initialized with display_manager: %s", id(self.display_manager))
        logger.info(f"Available display modes: {self.available_modes}")
        logger.info(f"NHL Favorite teams: {self.nhl_favorite_teams}")
        logger.info(f"NBA Favorite teams: {self.nba_favorite_teams}")
        logger.info("NHL managers initialized in %.3f seconds", time.time() - nhl_time)

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
        if self.youtube: self.youtube.run()
        
        # Update NHL managers
        if self.nhl_live: self.nhl_live.update()
        if self.nhl_recent: self.nhl_recent.update()
        if self.nhl_upcoming: self.nhl_upcoming.update()
        
        # Update NBA managers
        if self.nba_live: self.nba_live.update()
        if self.nba_recent: self.nba_recent.update()
        if self.nba_upcoming: self.nba_upcoming.update()

    def _check_live_games(self) -> tuple[bool, str]:
        """
        Check if there are any live games available.
        Returns:
            tuple[bool, str]: (has_live_games, sport_type)
            sport_type will be 'nhl' or 'nba' or None
        """
        # Check NHL live games
        if self.nhl_live and self.nhl_live.live_games:
            return True, 'nhl'
            
        # Check NBA live games
        if self.nba_live and self.nba_live.live_games:
            return True, 'nba'
            
        return False, None

    def _get_team_games(self, team: str, sport: str = 'nhl', is_recent: bool = True) -> bool:
        """
        Get games for a specific team and update the current game.
        Args:
            team: Team abbreviation
            sport: 'nhl' or 'nba'
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
        return False

    def _has_team_games(self, sport: str = 'nhl') -> bool:
        """
        Check if there are any games available for favorite teams.
        Args:
            sport: 'nhl' or 'nba'
        Returns:
            bool: True if games are available
        """
        if sport == 'nhl':
            favorite_teams = self.nhl_favorite_teams
            recent_manager = self.nhl_recent
            upcoming_manager = self.nhl_upcoming
        else:
            favorite_teams = self.nba_favorite_teams
            recent_manager = self.nba_recent
            upcoming_manager = self.nba_upcoming
            
        if not favorite_teams:
            return False
            
        # Check recent games
        if recent_manager and recent_manager.games_list:
            for game in recent_manager.games_list:
                if game["home_abbr"] in favorite_teams or game["away_abbr"] in favorite_teams:
                    return True
                    
        # Check upcoming games
        if upcoming_manager and upcoming_manager.games_list:
            for game in upcoming_manager.games_list:
                if game["home_abbr"] in favorite_teams or game["away_abbr"] in favorite_teams:
                    return True
                    
        return False

    def _rotate_team_games(self, sport: str = 'nhl') -> None:
        """
        Rotate through games for favorite teams.
        Args:
            sport: 'nhl' or 'nba'
        """
        if sport == 'nhl':
            current_team_index = self.nhl_current_team_index
            showing_recent = self.nhl_showing_recent
            favorite_teams = self.nhl_favorite_teams
            in_rotation = self.in_nhl_rotation
        else:
            current_team_index = self.nba_current_team_index
            showing_recent = self.nba_showing_recent
            favorite_teams = self.nba_favorite_teams
            in_rotation = self.in_nba_rotation
            
        if not favorite_teams:
            return
            
        # Try to find games for current team
        team = favorite_teams[current_team_index]
        found_games = self._get_team_games(team, sport, showing_recent)
        
        if not found_games:
            # If no games found for current team, try next team
            current_team_index = (current_team_index + 1) % len(favorite_teams)
            if sport == 'nhl':
                self.nhl_current_team_index = current_team_index
            else:
                self.nba_current_team_index = current_team_index
                
            # If we've tried all teams, switch between recent and upcoming
            if current_team_index == 0:
                if sport == 'nhl':
                    self.nhl_showing_recent = not self.nhl_showing_recent
                else:
                    self.nba_showing_recent = not self.nba_showing_recent
                showing_recent = not showing_recent
                
            # Try again with new team
            team = favorite_teams[current_team_index]
            found_games = self._get_team_games(team, sport, showing_recent)
            
        if found_games:
            # Set the appropriate display mode
            if sport == 'nhl':
                self.current_display_mode = 'nhl_recent' if showing_recent else 'nhl_upcoming'
                self.in_nhl_rotation = True
            else:
                self.current_display_mode = 'nba_recent' if showing_recent else 'nba_upcoming'
                self.in_nba_rotation = True
        else:
            # No games found for any team, exit rotation
            if sport == 'nhl':
                self.in_nhl_rotation = False
            else:
                self.in_nba_rotation = False

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
                has_live_games, sport_type = self._check_live_games()
                
                # If we have live games, cycle through them
                if has_live_games:
                    # Check if it's time to switch live games
                    if current_time - self.last_switch > self.get_current_duration():
                        # Switch between NHL and NBA live games if both are available
                        if sport_type == 'nhl' and self.nhl_live and self.nba_live and self.nba_live.live_games:
                            sport_type = 'nba'
                            self.last_switch = current_time
                            self.force_clear = True
                        elif sport_type == 'nba' and self.nba_live and self.nhl_live and self.nhl_live.live_games:
                            sport_type = 'nhl'
                            self.last_switch = current_time
                            self.force_clear = True
                    
                    # Display the current live game
                    if sport_type == 'nhl' and self.nhl_live:
                        self.nhl_live.update()  # Force update to get latest data
                        self.nhl_live.display(force_clear=self.force_clear)
                    elif sport_type == 'nba' and self.nba_live:
                        self.nba_live.update()  # Force update to get latest data
                        self.nba_live.display(force_clear=self.force_clear)
                    
                    self.force_clear = False
                    continue  # Skip the rest of the loop to stay on live games
                
                # Only proceed with mode switching if no live games
                if current_time - self.last_switch > self.get_current_duration():
                    # No live games, continue with regular rotation
                    self.current_mode_index = (self.current_mode_index + 1) % len(self.available_modes)
                    self.current_display_mode = self.available_modes[self.current_mode_index]
                    logger.info(f"Switching to: {self.current_display_mode}")
                    self.force_clear = True
                    self.last_switch = current_time
                    if self.current_display_mode != 'calendar' and self.calendar:
                        self.calendar.advance_event()

                # Display current mode frame (only for non-live modes)
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
                            
                    elif self.current_display_mode == 'stock_news' and self.news:
                        self.news.display_news()
                            
                    elif self.current_display_mode == 'calendar' and self.calendar:
                        self.calendar.display()
                            
                    elif self.current_display_mode == 'nhl_recent' and self.nhl_recent:
                        self.nhl_recent.display(force_clear=self.force_clear)
                    elif self.current_display_mode == 'nhl_upcoming' and self.nhl_upcoming:
                        self.nhl_upcoming.display(force_clear=self.force_clear)
                            
                    elif self.current_display_mode == 'nba_recent' and self.nba_recent:
                        self.nba_recent.display(force_clear=self.force_clear)
                    elif self.current_display_mode == 'nba_upcoming' and self.nba_upcoming:
                        self.nba_upcoming.display(force_clear=self.force_clear)
                            
                    elif self.current_display_mode == 'youtube' and self.youtube:
                        self.youtube.display()
                            
                except Exception as e:
                    logger.error(f"Error updating display for mode {self.current_display_mode}: {e}", exc_info=True)
                    continue

                self.force_clear = False

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