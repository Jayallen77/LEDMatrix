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
from src.mlb_manager import MLBLiveManager, MLBRecentManager, MLBUpcomingManager
from src.soccer_managers import SoccerLiveManager, SoccerRecentManager, SoccerUpcomingManager
from src.youtube_display import YouTubeDisplay
from src.calendar_manager import CalendarManager
from src.text_display import TextDisplay

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
        self.text_display = TextDisplay(self.display_manager, self.config) if self.config.get('text_display', {}).get('enabled', False) else None
        logger.info(f"Calendar Manager initialized: {'Object' if self.calendar else 'None'}")
        logger.info(f"Text Display initialized: {'Object' if self.text_display else 'None'}")
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
        logger.info("NHL managers initialized in %.3f seconds", time.time() - nhl_time)
            
        # Initialize NBA managers if enabled
        nba_time = time.time()
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
        logger.info("NBA managers initialized in %.3f seconds", time.time() - nba_time)

        # Initialize MLB managers if enabled
        mlb_time = time.time()
        mlb_enabled = self.config.get('mlb', {}).get('enabled', False)
        mlb_display_modes = self.config.get('mlb', {}).get('display_modes', {})
        
        if mlb_enabled:
            self.mlb_live = MLBLiveManager(self.config, self.display_manager) if mlb_display_modes.get('mlb_live', True) else None
            self.mlb_recent = MLBRecentManager(self.config, self.display_manager) if mlb_display_modes.get('mlb_recent', True) else None
            self.mlb_upcoming = MLBUpcomingManager(self.config, self.display_manager) if mlb_display_modes.get('mlb_upcoming', True) else None
        else:
            self.mlb_live = None
            self.mlb_recent = None
            self.mlb_upcoming = None
        logger.info("MLB managers initialized in %.3f seconds", time.time() - mlb_time)
            
        # Initialize Soccer managers if enabled
        soccer_time = time.time()
        soccer_enabled = self.config.get('soccer_scoreboard', {}).get('enabled', False)
        soccer_display_modes = self.config.get('soccer_scoreboard', {}).get('display_modes', {})
        
        if soccer_enabled:
            self.soccer_live = SoccerLiveManager(self.config, self.display_manager) if soccer_display_modes.get('soccer_live', True) else None
            self.soccer_recent = SoccerRecentManager(self.config, self.display_manager) if soccer_display_modes.get('soccer_recent', True) else None
            self.soccer_upcoming = SoccerUpcomingManager(self.config, self.display_manager) if soccer_display_modes.get('soccer_upcoming', True) else None
        else:
            self.soccer_live = None
            self.soccer_recent = None
            self.soccer_upcoming = None
        logger.info("Soccer managers initialized in %.3f seconds", time.time() - soccer_time)
            
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
        if self.text_display: self.available_modes.append('text_display')
        
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
            if self.mlb_recent: self.available_modes.append('mlb_recent') # Use recent if mode enabled
            if self.mlb_upcoming: self.available_modes.append('mlb_upcoming') # Use upcoming if mode enabled
            # mlb_live is handled separately when live games are available

        # Add Soccer display modes if enabled
        if soccer_enabled:
            if self.soccer_recent: self.available_modes.append('soccer_recent')
            if self.soccer_upcoming: self.available_modes.append('soccer_upcoming')
            # soccer_live is handled separately when live games are available
        
        # Set initial display to first available mode (clock)
        self.current_mode_index = 0
        self.current_display_mode = self.available_modes[0] if self.available_modes else 'none'
        self.last_switch = time.time()
        self.force_clear = True
        self.update_interval = 0.01  # Reduced from 0.1 to 0.01 for smoother scrolling
        
        # Track team-based rotation states (Add Soccer)
        self.nhl_current_team_index = 0
        self.nhl_showing_recent = True
        self.nhl_favorite_teams = self.config.get('nhl_scoreboard', {}).get('favorite_teams', [])
        self.in_nhl_rotation = False
        
        self.nba_current_team_index = 0
        self.nba_showing_recent = True
        self.nba_favorite_teams = self.config.get('nba_scoreboard', {}).get('favorite_teams', [])
        self.in_nba_rotation = False
        
        self.soccer_current_team_index = 0 # Soccer rotation state
        self.soccer_showing_recent = True
        self.soccer_favorite_teams = self.config.get('soccer_scoreboard', {}).get('favorite_teams', [])
        self.in_soccer_rotation = False
        
        # Update display durations to include all modes
        self.display_durations = self.config['display'].get('display_durations', {})
        # Add defaults for soccer if missing
        default_durations = {
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
            'mlb_upcoming': 20,
            'soccer_live': 30, # Soccer durations
            'soccer_recent': 20,
            'soccer_upcoming': 20
        }
        # Merge loaded durations with defaults
        for key, value in default_durations.items():
            if key not in self.display_durations:
                 self.display_durations[key] = value
        
        logger.info("DisplayController initialized with display_manager: %s", id(self.display_manager))
        logger.info(f"Available display modes: {self.available_modes}")
        logger.info(f"NHL Favorite teams: {self.nhl_favorite_teams}")
        logger.info(f"NBA Favorite teams: {self.nba_favorite_teams}")
        logger.info(f"MLB Favorite teams: {self.mlb_favorite_teams}")
        logger.info(f"Soccer Favorite teams: {self.soccer_favorite_teams}") # Log Soccer teams
        # Removed redundant NHL/MLB init time logs

    def get_current_duration(self) -> int:
        """Get the duration for the current display mode."""
        mode_key = self.current_display_mode
        # Simplify weather key handling
        if mode_key.startswith('weather_'):
            return self.display_durations.get(mode_key, 15)
            # duration_key = mode_key.split('_', 1)[1]
            # if duration_key == 'current': duration_key = 'weather_current' # Keep specific keys
            # elif duration_key == 'hourly': duration_key = 'weather_hourly'
            # elif duration_key == 'daily': duration_key = 'weather_daily'
            # else: duration_key = 'weather_current' # Default to current
            # return self.display_durations.get(duration_key, 15)
        
        return self.display_durations.get(mode_key, 15)

    def _update_modules(self):
        """Call update methods on active managers."""
        if self.weather: self.weather.get_weather()
        if self.stocks: self.stocks.update_stock_data()
        if self.news: self.news.update_news_data()
        if self.calendar: self.calendar.update(time.time())
        if self.youtube: self.youtube.update()
        if self.text_display: self.text_display.update()
        
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
        
        # Update Soccer managers
        if self.soccer_live: self.soccer_live.update()
        if self.soccer_recent: self.soccer_recent.update()
        if self.soccer_upcoming: self.soccer_upcoming.update()

    def _check_live_games(self) -> tuple[bool, str]:
        """
        Check if there are any live games available.
        Returns:
            tuple[bool, str]: (has_live_games, sport_type)
            sport_type will be 'nhl', 'nba', 'mlb', 'soccer' or None
        """
        # Prioritize sports (e.g., Soccer > NHL > NBA > MLB)
        if self.soccer_live and self.soccer_live.live_games:
            return True, 'soccer'
            
        if self.nhl_live and self.nhl_live.live_games:
            return True, 'nhl'
            
        if self.nba_live and self.nba_live.live_games:
            return True, 'nba'
            
        if self.mlb_live and self.mlb_live.live_games:
            return True, 'mlb'
            
        return False, None

    def _get_team_games(self, team: str, sport: str = 'nhl', is_recent: bool = True) -> bool:
        """
        Get games for a specific team and update the current game.
        Args:
            team: Team abbreviation
            sport: 'nhl', 'nba', 'mlb', or 'soccer'
            is_recent: Whether to look for recent or upcoming games
        Returns:
            bool: True if games were found and set
        """
        manager_recent = None
        manager_upcoming = None
        games_list_attr = 'games_list' # Default for NHL/NBA
        abbr_key_home = 'home_abbr'
        abbr_key_away = 'away_abbr'

        if sport == 'nhl':
            manager_recent = self.nhl_recent
            manager_upcoming = self.nhl_upcoming
        elif sport == 'nba':
            manager_recent = self.nba_recent
            manager_upcoming = self.nba_upcoming
        elif sport == 'mlb':
            manager_recent = self.mlb_recent
            manager_upcoming = self.mlb_upcoming
            games_list_attr = 'recent_games' if is_recent else 'upcoming_games'
            abbr_key_home = 'home_team' # MLB uses different keys
            abbr_key_away = 'away_team'
        elif sport == 'soccer':
            manager_recent = self.soccer_recent
            manager_upcoming = self.soccer_upcoming
            games_list_attr = 'games_list' if is_recent else 'upcoming_games' # Soccer uses games_list/upcoming_games

        manager = manager_recent if is_recent else manager_upcoming

        if manager and hasattr(manager, games_list_attr):
            game_list = getattr(manager, games_list_attr, [])
            for game in game_list:
                # Need to handle potential missing keys gracefully
                home_team_abbr = game.get(abbr_key_home)
                away_team_abbr = game.get(abbr_key_away)
                if home_team_abbr == team or away_team_abbr == team:
                    manager.current_game = game
                    return True
        return False


    def _has_team_games(self, sport: str = 'nhl') -> bool:
        """Check if there are any games for favorite teams."""
        favorite_teams = []
        manager_recent = None
        manager_upcoming = None
        
        if sport == 'nhl':
            favorite_teams = self.nhl_favorite_teams
            manager_recent = self.nhl_recent
            manager_upcoming = self.nhl_upcoming
        elif sport == 'nba':
            favorite_teams = self.nba_favorite_teams
            manager_recent = self.nba_recent
            manager_upcoming = self.nba_upcoming
        elif sport == 'mlb':
            favorite_teams = self.mlb_favorite_teams
            manager_recent = self.mlb_recent
            manager_upcoming = self.mlb_upcoming
        elif sport == 'soccer':
            favorite_teams = self.soccer_favorite_teams
            manager_recent = self.soccer_recent
            manager_upcoming = self.soccer_upcoming
            
        return bool(favorite_teams and (manager_recent or manager_upcoming))

    def _rotate_team_games(self, sport: str = 'nhl') -> None:
        """Rotate through games for favorite teams. (No longer used directly in loop)"""
        # This logic is now mostly handled within each manager's display/update
        # Keeping the structure in case direct rotation is needed later.
        if not self._has_team_games(sport):
            return

        if sport == 'nhl':
            if not self.nhl_favorite_teams: return
            current_team = self.nhl_favorite_teams[self.nhl_current_team_index]
            # ... (rest of NHL rotation logic - now less relevant)
        elif sport == 'nba':
             if not self.nba_favorite_teams: return
             current_team = self.nba_favorite_teams[self.nba_current_team_index]
             # ... (rest of NBA rotation logic)
        elif sport == 'mlb':
            if not self.mlb_favorite_teams: return
            current_team = self.mlb_favorite_teams[self.mlb_current_team_index]
            # ... (rest of MLB rotation logic)
        elif sport == 'soccer':
            if not self.soccer_favorite_teams: return
            current_team = self.soccer_favorite_teams[self.soccer_current_team_index]
            # Try to find games for current team (recent first)
            found_games = self._get_team_games(current_team, 'soccer', self.soccer_showing_recent)
            if not found_games:
                # Try opposite type (upcoming/recent)
                self.soccer_showing_recent = not self.soccer_showing_recent
                found_games = self._get_team_games(current_team, 'soccer', self.soccer_showing_recent)
            
            if not found_games:
                # Move to next team if no games found for current one
                self.soccer_current_team_index = (self.soccer_current_team_index + 1) % len(self.soccer_favorite_teams)
                self.soccer_showing_recent = True # Reset to recent for the new team
                # Maybe try finding game for the *new* team immediately? Optional.

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
                
                # Check for live games (priority: Soccer > NHL > NBA > MLB)
                has_live_games, live_sport_type = self._check_live_games()
                
                # --- Live Game Handling ---
                if has_live_games:
                    target_mode = "" # The mode we intend to display this iteration
                    needs_state_update = False

                    is_currently_live = self.current_display_mode.endswith('_live')

                    if not is_currently_live:
                        # Switching INTO live mode from a non-live mode
                        target_mode = f"{live_sport_type}_live" # Use highest priority sport
                        needs_state_update = True
                        logger.info(f"Switching into LIVE mode: {target_mode}")
                    else:
                        # Already in a live mode, check timer for rotation
                        if current_time - self.last_switch > self.get_current_duration():
                            # Timer expired, check for rotation possibility
                            active_live_sports = []
                            priority_order = ['soccer', 'nhl', 'nba', 'mlb'] 
                            for sport in priority_order:
                                live_attr = f"{sport}_live"
                                if hasattr(self, live_attr) and getattr(self, live_attr) and getattr(self, live_attr).live_games:
                                    active_live_sports.append(sport)
                            
                            if len(active_live_sports) > 1:
                                try:
                                    current_sport = self.current_display_mode.replace('_live', '')
                                    current_index = active_live_sports.index(current_sport)
                                    next_index = (current_index + 1) % len(active_live_sports)
                                    next_sport = active_live_sports[next_index]
                                    target_mode = f"{next_sport}_live"
                                    if target_mode != self.current_display_mode:
                                         needs_state_update = True
                                         logger.info(f"Rotating live sports: {self.current_display_mode} -> {target_mode}")
                                    else: 
                                         # Target is same as current, reset timer but no mode change needed
                                         self.last_switch = current_time 
                                         self.force_clear = False
                                except ValueError: 
                                    logger.warning(f"Could not find current live mode {self.current_display_mode} in active list {active_live_sports}. Defaulting.")
                                    target_mode = f"{active_live_sports[0]}_live" 
                                    needs_state_update = True # Force update to default
                            else:
                                 # Timer expired, but only one/zero active sports. Stay on current or switch if needed.
                                 if active_live_sports:
                                     target_mode = f"{active_live_sports[0]}_live"
                                 else: # No live sports anymore? Fallback handled later.
                                     target_mode = self.current_display_mode # Tentatively stay
                                     
                                 if target_mode != self.current_display_mode:
                                      needs_state_update = True # Switch to the single active one if needed
                                 else:
                                      # Still on the same single live sport, just reset its timer
                                      self.last_switch = current_time
                                      self.force_clear = False # No visual change
                        else:
                            # Timer has not expired, continue with current live mode
                            target_mode = self.current_display_mode
                            needs_state_update = False # No state change needed

                    # --- Update State if Required ---
                    if needs_state_update and target_mode:
                        self.current_display_mode = target_mode
                        self.last_switch = current_time # Reset timer whenever mode changes
                        self.force_clear = True
                    elif not target_mode and is_currently_live:
                         # We were live, but target couldn't be determined (e.g., all games ended)
                         # Let execution fall through to regular mode rotation logic
                         has_live_games = False 
                         logger.info("Exiting live mode as no target live mode determined.")
                    
                    # --- Select Manager and Display --- 
                    manager_to_display = None
                    if has_live_games: # Check again in case we bailed above
                        current_sport_type = self.current_display_mode.replace('_live', '')
                        manager_attr = f"{current_sport_type}_live"
                        if hasattr(self, manager_attr):
                            manager_to_display = getattr(self, manager_attr)
                        else:
                             logger.error(f"Could not find manager attribute {manager_attr} for current mode {self.current_display_mode}")
                             has_live_games = False # Fallback
                    
                    if manager_to_display:
                        manager_to_display.display(force_clear=self.force_clear)
                        self.force_clear = False # Reset clear flag after display
                        continue # Skip regular mode display logic if live game was shown
                    # else: Fall through to regular rotation
                    
                # --- Regular Mode Rotation (only if NO live games OR fallback from live) ---
                if not has_live_games:
                    # Check if we were just in live mode and need to switch back
                    if self.current_display_mode.endswith('_live'):
                         logger.info(f"Switching back to regular rotation from {self.current_display_mode}")
                         # Find the next available mode in the regular list
                         self.current_mode_index = (self.current_mode_index + 1) % len(self.available_modes)
                         self.current_display_mode = self.available_modes[self.current_mode_index]
                         self.force_clear = True
                         self.last_switch = current_time
                         logger.info(f"Switching to: {self.current_display_mode}")
                         
                    # Check if it's time to switch modes based on duration
                    elif current_time - self.last_switch > self.get_current_duration():
                        # Advance calendar event before switching away
                        if self.current_display_mode == 'calendar' and self.calendar:
                            self.calendar.advance_event()
                        
                        self.current_mode_index = (self.current_mode_index + 1) % len(self.available_modes)
                        self.current_display_mode = self.available_modes[self.current_mode_index]
                        logger.info(f"Switching to: {self.current_display_mode}")
                        self.force_clear = True
                        self.last_switch = current_time

                    # Display current mode frame
                    try:
                        display_updated = False # Flag to track if display was handled
                        if self.current_display_mode == 'clock' and self.clock:
                            self.clock.display_time(force_clear=self.force_clear)
                            display_updated = True
                                
                        elif self.current_display_mode == 'weather_current' and self.weather:
                            self.weather.display_weather(force_clear=self.force_clear)
                            display_updated = True
                        elif self.current_display_mode == 'weather_hourly' and self.weather:
                            self.weather.display_hourly_forecast(force_clear=self.force_clear)
                            display_updated = True
                        elif self.current_display_mode == 'weather_daily' and self.weather:
                            self.weather.display_daily_forecast(force_clear=self.force_clear)
                            display_updated = True
                                
                        elif self.current_display_mode == 'stocks' and self.stocks:
                            self.stocks.display_stocks(force_clear=self.force_clear)
                            display_updated = True
                                
                        elif self.current_display_mode == 'stock_news' and self.news:
                            self.news.display_news() # Assumes news handles its own clearing/drawing
                            display_updated = True
                                
                        elif self.current_display_mode == 'calendar' and self.calendar:
                            self.calendar.display(force_clear=self.force_clear)
                            display_updated = True
                                
                        elif self.current_display_mode == 'nhl_recent' and self.nhl_recent:
                            self.nhl_recent.display(force_clear=self.force_clear)
                            display_updated = True
                        elif self.current_display_mode == 'nhl_upcoming' and self.nhl_upcoming:
                            self.nhl_upcoming.display(force_clear=self.force_clear)
                            display_updated = True
                                
                        elif self.current_display_mode == 'nba_recent' and self.nba_recent:
                            self.nba_recent.display(force_clear=self.force_clear)
                            display_updated = True
                        elif self.current_display_mode == 'nba_upcoming' and self.nba_upcoming:
                            self.nba_upcoming.display(force_clear=self.force_clear)
                            display_updated = True
                                
                        elif self.current_display_mode == 'mlb_recent' and self.mlb_recent:
                            self.mlb_recent.display(force_clear=self.force_clear)
                            display_updated = True
                        elif self.current_display_mode == 'mlb_upcoming' and self.mlb_upcoming:
                            self.mlb_upcoming.display(force_clear=self.force_clear)
                            display_updated = True
                                    
                        elif self.current_display_mode == 'soccer_recent' and self.soccer_recent:
                            self.soccer_recent.display(force_clear=self.force_clear)
                            display_updated = True
                        elif self.current_display_mode == 'soccer_upcoming' and self.soccer_upcoming:
                            self.soccer_upcoming.display(force_clear=self.force_clear)
                            display_updated = True
                                
                        elif self.current_display_mode == 'youtube' and self.youtube:
                            self.youtube.display(force_clear=self.force_clear)
                            display_updated = True
                                
                        elif self.current_display_mode == 'text_display' and self.text_display:
                            self.text_display.display() # Assumes text handles its own drawing
                            display_updated = True
                            
                        # Reset force_clear only if a display method was actually called
                        if display_updated:
                             self.force_clear = False
                                
                    except Exception as e:
                        logger.error(f"Error updating display for mode {self.current_display_mode}: {e}", exc_info=True)
                        # Continue to next iteration after error

                # Small sleep to prevent high CPU usage
                #time.sleep(self.update_interval) 

        except KeyboardInterrupt:
            logger.info("Display controller stopped by user")
        except Exception as e:
            logger.error(f"Critical error in display controller run loop: {e}", exc_info=True)
        finally:
            logger.info("Cleaning up display manager...")
            self.display_manager.cleanup()
            logger.info("Cleanup complete.")

def main():
    controller = DisplayController()
    controller.run()

if __name__ == "__main__":
    main() 