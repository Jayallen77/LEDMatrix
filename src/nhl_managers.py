import os
import time
import logging
import requests
import json
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime, timedelta, timezone
from src.display_manager import DisplayManager
from src.cache_manager import CacheManager

# Constants
ESPN_NHL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"

# Configure logging to match main configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s:%(name)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class CacheManager:
    """Manages caching of ESPN API responses."""
    _instance = None
    _cache = {}
    _cache_timestamps = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def get(cls, key: str, max_age: int = 60) -> Optional[Dict]:
        """
        Get data from cache if it exists and is not stale.
        Args:
            key: Cache key (usually the date string)
            max_age: Maximum age of cached data in seconds
        Returns:
            Cached data if valid, None if missing or stale
        """
        if key not in cls._cache:
            return None
            
        timestamp = cls._cache_timestamps.get(key, 0)
        if time.time() - timestamp > max_age:
            # Data is stale, remove it
            del cls._cache[key]
            del cls._cache_timestamps[key]
            return None
            
        return cls._cache[key]
    
    @classmethod
    def set(cls, key: str, data: Dict) -> None:
        """
        Store data in cache with current timestamp.
        Args:
            key: Cache key (usually the date string)
            data: Data to cache
        """
        cls._cache[key] = data
        cls._cache_timestamps[key] = time.time()
    
    @classmethod
    def clear(cls) -> None:
        """Clear all cached data."""
        cls._cache.clear()
        cls._cache_timestamps.clear()

class BaseNHLManager:
    """Base class for NHL managers with common functionality."""
    # Class variables for warning tracking
    _no_data_warning_logged = False
    _last_warning_time = 0
    _warning_cooldown = 60  # Only log warnings once per minute
    _shared_data = None
    _last_shared_update = 0
    cache_manager = CacheManager()  # Make cache_manager a class attribute
    logger = logging.getLogger('NHL')  # Make logger a class attribute
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        self.display_manager = display_manager
        self.config = config
        self.nhl_config = config.get("nhl_scoreboard", {})
        self.is_enabled = self.nhl_config.get("enabled", False)
        self.test_mode = self.nhl_config.get("test_mode", False)  # Use test_mode from config
        self.logo_dir = self.nhl_config.get("logo_dir", "assets/sports/nhl_logos")
        self.update_interval = self.nhl_config.get("update_interval_seconds", 60)
        self.last_update = 0
        self.current_game = None
        self.fonts = self._load_fonts()
        self.favorite_teams = self.nhl_config.get("favorite_teams", [])
        self.recent_hours = self.nhl_config.get("recent_game_hours", 48)  # Default 48 hours
        
        # Set logging level to INFO to reduce noise
        self.logger.setLevel(logging.INFO)
        
        # Get display dimensions from config
        display_config = config.get("display", {})
        hardware_config = display_config.get("hardware", {})
        cols = hardware_config.get("cols", 64)
        chain = hardware_config.get("chain_length", 1)
        self.display_width = int(cols * chain)
        self.display_height = hardware_config.get("rows", 32)
        
        # Cache for loaded logos
        self._logo_cache = {}
        
        self.logger.info(f"Initialized NHL manager with display dimensions: {self.display_width}x{self.display_height}")
        self.logger.info(f"Logo directory: {self.logo_dir}")

    @classmethod
    def _fetch_shared_data(cls, date_str: str = None) -> Optional[Dict]:
        """Fetch and cache data for all managers to share."""
        current_time = time.time()
        
        # If we have recent data, use it
        if cls._shared_data and (current_time - cls._last_shared_update) < 300:  # 5 minutes
            return cls._shared_data
            
        try:
            # Check cache first
            cache_key = date_str if date_str else 'today'
            cached_data = cls.cache_manager.get(cache_key, max_age=300)  # 5 minutes cache
            if cached_data:
                cls.logger.info(f"[NHL] Using cached data for {cache_key}")
                cls._shared_data = cached_data
                cls._last_shared_update = current_time
                return cached_data
                
            # If not in cache or stale, fetch from API
            url = ESPN_NHL_SCOREBOARD_URL
            params = {}
            if date_str:
                params['dates'] = date_str
                
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            cls.logger.info(f"[NHL] Successfully fetched data from ESPN API")
            
            # Cache the response
            cls.cache_manager.set(cache_key, data)
            cls._shared_data = data
            cls._last_shared_update = current_time
            
            # If no date specified, fetch data from multiple days
            if not date_str:
                # Get today's date in YYYYMMDD format
                today = datetime.now(timezone.utc).date()
                dates_to_fetch = [
                    (today - timedelta(days=2)).strftime('%Y%m%d'),
                    (today - timedelta(days=1)).strftime('%Y%m%d'),
                    today.strftime('%Y%m%d')
                ]
                
                # Fetch data for each date
                all_events = []
                for fetch_date in dates_to_fetch:
                    if fetch_date != today.strftime('%Y%m%d'):  # Skip today as we already have it
                        # Check cache for this date
                        cached_date_data = cls.cache_manager.get(fetch_date, max_age=300)
                        if cached_date_data:
                            cls.logger.info(f"[NHL] Using cached data for date {fetch_date}")
                            if "events" in cached_date_data:
                                all_events.extend(cached_date_data["events"])
                            continue
                            
                        params['dates'] = fetch_date
                        response = requests.get(url, params=params)
                        response.raise_for_status()
                        date_data = response.json()
                        if date_data and "events" in date_data:
                            all_events.extend(date_data["events"])
                            cls.logger.info(f"[NHL] Fetched {len(date_data['events'])} events for date {fetch_date}")
                            # Cache the response
                            cls.cache_manager.set(fetch_date, date_data)
                
                # Combine events from all dates
                if all_events:
                    data["events"].extend(all_events)
                    cls.logger.info(f"[NHL] Combined {len(data['events'])} total events from all dates")
                    cls._shared_data = data
                    cls._last_shared_update = current_time
            
            return data
        except requests.exceptions.RequestException as e:
            cls.logger.error(f"[NHL] Error fetching data from ESPN: {e}")
            return None

    def _fetch_data(self, date_str: str = None) -> Optional[Dict]:
        """Fetch data using shared data mechanism."""
        # For live games, bypass the shared cache to ensure fresh data
        if isinstance(self, NHLLiveManager):
            try:
                url = ESPN_NHL_SCOREBOARD_URL
                params = {}
                if date_str:
                    params['dates'] = date_str
                    
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                self.logger.info(f"[NHL] Successfully fetched live game data from ESPN API")
                return data
            except requests.exceptions.RequestException as e:
                self.logger.error(f"[NHL] Error fetching live game data from ESPN: {e}")
                return None
        else:
            # For non-live games, use the shared cache
            return self._fetch_shared_data(date_str)

    def _load_fonts(self):
        """Load fonts used by the scoreboard."""
        fonts = {}
        try:
            # Try to load the Press Start 2P font first
            fonts['score'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 12)
            fonts['time'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['team'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
            logging.info("[NHL] Successfully loaded Press Start 2P font for all text elements")
        except IOError:
            logging.warning("[NHL] Press Start 2P font not found, trying 4x6 font.")
            try:
                # Try to load the 4x6 font as a fallback
                fonts['score'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 12)
                fonts['time'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 8)
                fonts['team'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 8)
                fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 9)
                logging.info("[NHL] Successfully loaded 4x6 font for all text elements")
            except IOError:
                logging.warning("[NHL] 4x6 font not found, using default PIL font.")
                # Use default PIL font as a last resort
                fonts['score'] = ImageFont.load_default()
                fonts['time'] = ImageFont.load_default()
                fonts['team'] = ImageFont.load_default()
                fonts['status'] = ImageFont.load_default()
        return fonts

    def _load_and_resize_logo(self, team_abbrev: str) -> Optional[Image.Image]:
        """Load and resize a team logo, with caching."""
        self.logger.debug(f"Loading logo for {team_abbrev}")
        
        if team_abbrev in self._logo_cache:
            self.logger.debug(f"Using cached logo for {team_abbrev}")
            return self._logo_cache[team_abbrev]
            
        logo_path = os.path.join(self.logo_dir, f"{team_abbrev}.png")
        self.logger.debug(f"Logo path: {logo_path}")
        
        try:
            # Create test logos if they don't exist
            if not os.path.exists(logo_path):
                self.logger.info(f"Creating test logo for {team_abbrev}")
                os.makedirs(os.path.dirname(logo_path), exist_ok=True)
                # Create a simple colored rectangle as a test logo
                logo = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
                draw = ImageDraw.Draw(logo)
                # Use team abbreviation to determine color
                if team_abbrev == "TB":
                    color = (0, 0, 255, 255)  # Blue for Tampa Bay
                else:
                    color = (255, 0, 0, 255)  # Red for Dallas
                draw.rectangle([4, 4, 28, 28], fill=color)
                # Add team abbreviation
                draw.text((8, 8), team_abbrev, fill=(255, 255, 255, 255))
                logo.save(logo_path)
                self.logger.info(f"Created test logo at {logo_path}")
            
            logo = Image.open(logo_path)
            self.logger.debug(f"Opened logo for {team_abbrev}, size: {logo.size}, mode: {logo.mode}")
            
            # Convert to RGBA if not already
            if logo.mode != 'RGBA':
                self.logger.debug(f"Converting {team_abbrev} logo from {logo.mode} to RGBA")
                logo = logo.convert('RGBA')
            
            # Calculate max size based on display dimensions
            # Make logos 150% of display width to allow them to extend off screen
            max_width = int(self.display_width * 1.5)
            max_height = int(self.display_height * 1.5)
            
            # Resize maintaining aspect ratio
            logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            self.logger.debug(f"Resized {team_abbrev} logo to {logo.size}")
            
            # Cache the resized logo
            self._logo_cache[team_abbrev] = logo
            return logo
            
        except Exception as e:
            self.logger.error(f"Error loading logo for {team_abbrev}: {e}", exc_info=True)
            return None

    def _extract_game_details(self, game_event: Dict) -> Optional[Dict]:
        """Extract relevant game details from ESPN API response."""
        if not game_event:
            return None

        try:
            competition = game_event["competitions"][0]
            status = competition["status"]
            competitors = competition["competitors"]
            game_date_str = game_event["date"]

            # Parse game date/time
            try:
                start_time_utc = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
                self.logger.debug(f"[NHL] Parsed game time: {start_time_utc}")
            except ValueError:
                logging.warning(f"[NHL] Could not parse game date: {game_date_str}")
                start_time_utc = None

            home_team = next(c for c in competitors if c.get("homeAway") == "home")
            away_team = next(c for c in competitors if c.get("homeAway") == "away")

            # Format game time and date for display
            game_time = ""
            game_date = ""
            if start_time_utc:
                # Convert to local time
                local_time = start_time_utc.astimezone()
                game_time = local_time.strftime("%-I:%M %p")
                game_date = local_time.strftime("%-m/%-d")

            # Calculate if game is within recent window
            is_within_window = False
            if start_time_utc:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.recent_hours)
                is_within_window = start_time_utc > cutoff_time
                self.logger.debug(f"[NHL] Game time: {start_time_utc}, Cutoff time: {cutoff_time}, Within window: {is_within_window}")

            details = {
                "start_time_utc": start_time_utc,
                "status_text": status["type"]["shortDetail"],
                "period": status.get("period", 0),
                "clock": status.get("displayClock", "0:00"),
                "is_live": status["type"]["state"] in ("in", "halftime"),
                "is_final": status["type"]["state"] == "post",
                "is_upcoming": status["type"]["state"] == "pre",
                "is_within_window": is_within_window,
                "home_abbr": home_team["team"]["abbreviation"],
                "home_score": home_team.get("score", "0"),
                "home_logo_path": os.path.join(self.logo_dir, f"{home_team['team']['abbreviation']}.png"),
                "away_abbr": away_team["team"]["abbreviation"],
                "away_score": away_team.get("score", "0"),
                "away_logo_path": os.path.join(self.logo_dir, f"{away_team['team']['abbreviation']}.png"),
                "game_time": game_time,
                "game_date": game_date
            }

            # Log game details for debugging
            self.logger.debug(f"[NHL] Extracted game details: {details['away_abbr']} vs {details['home_abbr']}")
            self.logger.debug(f"[NHL] Game status: is_final={details['is_final']}, is_within_window={details['is_within_window']}")

            # Validate logo files
            for team in ["home", "away"]:
                logo_path = details[f"{team}_logo_path"]
                if not os.path.isfile(logo_path):
                    logging.warning(f"[NHL] {team.title()} logo not found: {logo_path}")
                    details[f"{team}_logo_path"] = None
                else:
                    try:
                        with Image.open(logo_path) as img:
                            logging.debug(f"[NHL] {team.title()} logo is valid: {img.format}, size: {img.size}")
                    except Exception as e:
                        logging.error(f"[NHL] {team.title()} logo file exists but is not valid: {e}")
                        details[f"{team}_logo_path"] = None

            return details
        except Exception as e:
            logging.error(f"[NHL] Error extracting game details: {e}")
            return None

    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:
        """Draw the scorebug layout for the current game."""
        try:
            # Create a new black image for the main display
            main_img = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 255))
            
            # Load logos once
            home_logo = self._load_and_resize_logo(game["home_abbr"])
            away_logo = self._load_and_resize_logo(game["away_abbr"])
            
            if not home_logo or not away_logo:
                self.logger.error("Failed to load one or both team logos")
                return

            # Create a single overlay for both logos
            overlay = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 0))

            # Calculate vertical center line for alignment
            center_y = self.display_height // 2

            # Draw home team logo (far right, extending beyond screen)
            home_x = self.display_width - home_logo.width + 12  # Shifted in by 3 pixels (from 15 to 12)
            home_y = center_y - (home_logo.height // 2)
            
            # Paste the home logo onto the overlay
            overlay.paste(home_logo, (home_x, home_y), home_logo)

            # Draw away team logo (far left, extending beyond screen)
            away_x = -12  # Shifted in by 3 pixels (from -15 to -12)
            away_y = center_y - (away_logo.height // 2)
            
            # Paste the away logo onto the overlay
            overlay.paste(away_logo, (away_x, away_y), away_logo)

            # Composite the overlay with the main image
            main_img = Image.alpha_composite(main_img, overlay)

            # Convert to RGB for final display
            main_img = main_img.convert('RGB')
            draw = ImageDraw.Draw(main_img)

            # Check if this is an upcoming game
            is_upcoming = game.get("is_upcoming", False)
            
            if is_upcoming:
                # For upcoming games, show date and time stacked in the center
                game_date = game.get("game_date", "")
                game_time = game.get("game_time", "")
                
                # Show "Next Game" at the top
                status_text = "Next Game"
                status_width = draw.textlength(status_text, font=self.fonts['status'])
                status_x = (self.display_width - status_width) // 2
                status_y = 2
                draw.text((status_x, status_y), status_text, font=self.fonts['status'], fill=(255, 255, 255))
                
                # Calculate position for the date text (centered horizontally, below "Next Game")
                date_width = draw.textlength(game_date, font=self.fonts['time'])
                date_x = (self.display_width - date_width) // 2
                date_y = center_y - 5  # Position in center
                draw.text((date_x, date_y), game_date, font=self.fonts['time'], fill=(255, 255, 255))
                
                # Calculate position for the time text (centered horizontally, in center)
                time_width = draw.textlength(game_time, font=self.fonts['time'])
                time_x = (self.display_width - time_width) // 2
                time_y = date_y + 10  # Position below date
                draw.text((time_x, time_y), game_time, font=self.fonts['time'], fill=(255, 255, 255))
            else:
                # For live/final games, show scores and period/time
                home_score = str(game.get("home_score", "0"))
                away_score = str(game.get("away_score", "0"))
                score_text = f"{away_score}-{home_score}"
                
                # Calculate position for the score text (centered at the bottom)
                score_width = draw.textlength(score_text, font=self.fonts['score'])
                score_x = (self.display_width - score_width) // 2
                score_y = self.display_height - 15
                draw.text((score_x, score_y), score_text, font=self.fonts['score'], fill=(255, 255, 255))

                # Draw period and time or Final
                if game.get("is_final", False):
                    status_text = "Final"
                else:
                    period = game.get("period", 0)
                    clock = game.get("clock", "0:00")
                    
                    # Format period text
                    if period > 3:
                        period_text = "OT"
                    else:
                        period_text = f"{period}{'st' if period == 1 else 'nd' if period == 2 else 'rd'}"
                    
                    status_text = f"{period_text} {clock}"
                
                # Calculate position for the status text (centered at the top)
                status_width = draw.textlength(status_text, font=self.fonts['time'])
                status_x = (self.display_width - status_width) // 2
                status_y = 5
                draw.text((status_x, status_y), status_text, font=self.fonts['time'], fill=(255, 255, 255))

            # Display the image
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"Error displaying game: {e}", exc_info=True)

    def display(self, force_clear: bool = False) -> None:
        """Common display method for all NHL managers"""
        if not self.current_game:
            current_time = time.time()
            if not hasattr(self, '_last_warning_time'):
                self._last_warning_time = 0
            if current_time - self._last_warning_time > 300:  # 5 minutes cooldown
                self.logger.warning("[NHL] No game data available to display")
                self._last_warning_time = current_time
            return
            
        self._draw_scorebug_layout(self.current_game, force_clear)

class NHLLiveManager(BaseNHLManager):
    """Manager for live NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("live_update_interval", 15)  # 15 seconds for live games
        self.no_data_interval = 300  # 5 minutes when no live games
        self.last_update = 0
        self.logger.info("Initialized NHL Live Manager")
        self.live_games = []  # List to store all live games
        self.current_game_index = 0  # Index to track which game to show
        self.last_game_switch = 0  # Track when we last switched games
        self.game_display_duration = self.nhl_config.get("live_game_duration", 20)  # Display each live game for 20 seconds
        self.last_display_update = 0  # Track when we last updated the display
        
        # Initialize with test game only if test mode is enabled
        if self.test_mode:
            self.current_game = {
                "home_abbr": "TB",
                "away_abbr": "DAL",
                "home_score": "3",
                "away_score": "2",
                "period": 2,
                "clock": "12:34",
                "home_logo_path": os.path.join(self.logo_dir, "TB.png"),
                "away_logo_path": os.path.join(self.logo_dir, "DAL.png"),
                "game_time": "7:30 PM",
                "game_date": "Apr 17"
            }
            self.live_games = [self.current_game]
            logging.info("[NHL] Initialized NHLLiveManager with test game: TB vs DAL")
        else:
            logging.info("[NHL] Initialized NHLLiveManager in live mode")

    def update(self):
        """Update live game data."""
        current_time = time.time()
        # Use longer interval if no game data
        interval = self.no_data_interval if not self.live_games else self.update_interval
        
        if current_time - self.last_update >= interval:
            self.logger.info("[NHL] Fetching new live game data...")
            self.last_update = current_time
            
            if self.test_mode:
                # For testing, we'll just update the clock to show it's working
                if self.current_game:
                    minutes = int(self.current_game["clock"].split(":")[0])
                    seconds = int(self.current_game["clock"].split(":")[1])
                    seconds -= 1
                    if seconds < 0:
                        seconds = 59
                        minutes -= 1
                        if minutes < 0:
                            minutes = 19
                            if self.current_game["period"] < 3:
                                self.current_game["period"] += 1
                            else:
                                self.current_game["period"] = 1
                    self.current_game["clock"] = f"{minutes:02d}:{seconds:02d}"
                    self.logger.info(f"[NHL] Updated test game clock: {self.current_game['clock']}")
                    # Always update display in test mode
                    self.display(force_clear=True)
            else:
                # Fetch live game data from ESPN API
                data = self._fetch_data()
                if data and "events" in data:
                    # Find all live games involving favorite teams
                    new_live_games = []
                    for event in data["events"]:
                        details = self._extract_game_details(event)
                        if details and details["is_live"]:
                            if not self.favorite_teams or (
                                details["home_abbr"] in self.favorite_teams or 
                                details["away_abbr"] in self.favorite_teams
                            ):
                                new_live_games.append(details)
                                self.logger.info(f"[NHL] Found live game: {details['away_abbr']} vs {details['home_abbr']} - Period {details['period']}, {details['clock']}")
                    
                    if new_live_games:
                        # Update the current game with the latest data
                        for new_game in new_live_games:
                            if self.current_game and (
                                (new_game["home_abbr"] == self.current_game["home_abbr"] and 
                                 new_game["away_abbr"] == self.current_game["away_abbr"]) or
                                (new_game["home_abbr"] == self.current_game["away_abbr"] and 
                                 new_game["away_abbr"] == self.current_game["home_abbr"])
                            ):
                                self.current_game = new_game
                                self.logger.info(f"[NHL] Updated current game: {self.current_game['away_abbr']} vs {self.current_game['home_abbr']} - Period {self.current_game['period']}, {self.current_game['clock']}")
                                break
                        
                        # Only update the games list if we have new games
                        if not self.live_games or set(game["away_abbr"] + game["home_abbr"] for game in new_live_games) != set(game["away_abbr"] + game["home_abbr"] for game in self.live_games):
                            self.live_games = new_live_games
                            # If we don't have a current game or it's not in the new list, start from the beginning
                            if not self.current_game or self.current_game not in self.live_games:
                                self.current_game_index = 0
                                self.current_game = self.live_games[0]
                                self.last_game_switch = current_time
                                self.logger.info(f"[NHL] Starting with live game: {self.current_game['away_abbr']} vs {self.current_game['home_abbr']}")
                        
                        # Always update display when we have new data, but limit to once per second
                        if current_time - self.last_display_update >= 1.0:
                            self.display(force_clear=True)
                            self.last_display_update = current_time
                    else:
                        # No live games found
                        self.live_games = []
                        self.current_game = None
                        self.logger.info("[NHL] No live games found")
                
                # Check if it's time to switch games
                if len(self.live_games) > 1 and (current_time - self.last_game_switch) >= self.game_display_duration:
                    self.current_game_index = (self.current_game_index + 1) % len(self.live_games)
                    self.current_game = self.live_games[self.current_game_index]
                    self.last_game_switch = current_time
                    self.logger.info(f"[NHL] Switching to live game: {self.current_game['away_abbr']} vs {self.current_game['home_abbr']} - Period {self.current_game['period']}, {self.current_game['clock']}")
                    # Force display update when switching games
                    self.display(force_clear=True)
                    self.last_display_update = current_time

    def display(self, force_clear: bool = False):
        """Display live game information."""
        if not self.current_game:
            return
        super().display(force_clear)  # Call parent class's display method

class NHLRecentManager(BaseNHLManager):
    """Manager for recently completed NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.recent_games = []
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = 300  # 5 minutes
        self.recent_hours = self.nhl_config.get("recent_game_hours", 48)
        self.last_game_switch = 0
        self.game_display_duration = 15  # Display each game for 15 seconds
        self.logger.info(f"Initialized NHLRecentManager with {len(self.favorite_teams)} favorite teams")
        
    def update(self):
        """Update recent games data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return
            
        try:
            # Fetch data from ESPN API
            data = self._fetch_data()
            if not data or 'events' not in data:
                self.logger.warning("[NHL] No events found in ESPN API response")
                return
                
            events = data['events']
            self.logger.info(f"[NHL] Successfully fetched {len(events)} events from ESPN API")
            
            # Process games
            self.recent_games = []
            for event in events:
                game = self._extract_game_details(event)
                if game:
                    self.recent_games.append(game)
                    self.logger.debug(f"Processing game: {game['away_abbr']} vs {game['home_abbr']} - Final: {game['is_final']}, Within window: {game['is_within_window']}")
            
            # Filter for favorite teams
            team_games = [game for game in self.recent_games 
                         if game['home_abbr'] in self.favorite_teams or 
                            game['away_abbr'] in self.favorite_teams]
            
            self.logger.info(f"[NHL] Found {len(team_games)} recent games for favorite teams")
            if not team_games:
                self.logger.info("[NHL] No recent games found for favorite teams")
                return
                
            self.games_list = team_games
            self.current_game = team_games[0]
            self.last_update = current_time
            
        except Exception as e:
            self.logger.error(f"[NHL] Error updating recent games: {e}", exc_info=True)

    def display(self, force_clear=False):
        """Display recent games."""
        if not self.games_list:
            self.logger.info("[NHL] No recent games to display")
            self.display_manager.clear()
            return
            
        try:
            current_time = time.time()
            
            # Check if it's time to switch games
            if current_time - self.last_game_switch >= self.game_display_duration:
                # Move to next game
                self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
                self.current_game = self.games_list[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True  # Force clear when switching games
            
            # Draw the scorebug layout
            self._draw_scorebug_layout(self.current_game, force_clear)
            
            # Update display
            self.display_manager.update_display()
            
        except Exception as e:
            self.logger.error(f"[NHL] Error displaying recent game: {e}", exc_info=True)

class NHLUpcomingManager(BaseNHLManager):
    """Manager for upcoming NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.upcoming_games = []
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = 300  # 5 minutes
        self.logger.info(f"Initialized NHLUpcomingManager with {len(self.favorite_teams)} favorite teams")
        
    def update(self):
        """Update upcoming games data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return
            
        try:
            # Fetch data from ESPN API
            data = self._fetch_data()
            if not data or 'events' not in data:
                self.logger.warning("[NHL] No events found in ESPN API response")
                return
                
            events = data['events']
            self.logger.info(f"[NHL] Successfully fetched {len(events)} events from ESPN API")
            
            # Process games
            self.upcoming_games = []
            for event in events:
                game = self._extract_game_details(event)
                if game and not game['is_final'] and game['is_within_window']:
                    self.upcoming_games.append(game)
                    self.logger.debug(f"Processing upcoming game: {game['away_abbr']} vs {game['home_abbr']}")
            
            # Filter for favorite teams
            team_games = [game for game in self.upcoming_games 
                         if game['home_abbr'] in self.favorite_teams or 
                            game['away_abbr'] in self.favorite_teams]
            
            self.logger.info(f"[NHL] Found {len(team_games)} upcoming games for favorite teams")
            if not team_games:
                self.logger.info("[NHL] No upcoming games found for favorite teams")
                return
                
            self.games_list = team_games
            self.current_game = team_games[0]
            self.last_update = current_time
            
        except Exception as e:
            self.logger.error(f"[NHL] Error updating upcoming games: {e}", exc_info=True)

    def display(self, force_clear=False):
        """Display upcoming games."""
        if not self.games_list:
            self.logger.info("[NHL] No upcoming games to display")
            self.display_manager.clear()
            return
            
        try:
            # Draw the scorebug layout
            self._draw_scorebug_layout(self.current_game, force_clear)
            
            # Update display
            self.display_manager.update_display()
            
            # Move to next game
            self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
            self.current_game = self.games_list[self.current_game_index]
            
        except Exception as e:
            self.logger.error(f"[NHL] Error displaying upcoming game: {e}", exc_info=True) 