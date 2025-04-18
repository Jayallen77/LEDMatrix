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

# Constants
ESPN_NHL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"

class BaseNHLManager:
    """Base class for NHL managers with common functionality."""
    # Class variables for warning tracking
    _no_data_warning_logged = False
    _last_warning_time = 0
    _warning_cooldown = 60  # Only log warnings once per minute
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        self.display_manager = display_manager
        self.config = config
        self.nhl_config = config.get("nhl_scoreboard", {})
        self.is_enabled = self.nhl_config.get("enabled", False)
        self.test_mode = True  # Force test mode to be enabled
        self.logo_dir = self.nhl_config.get("logo_dir", "assets/sports/nhl_logos")
        self.update_interval = self.nhl_config.get("update_interval_seconds", 60)
        self.last_update = 0
        self.current_game = None
        self.fonts = self._load_fonts()
        self.favorite_teams = self.nhl_config.get("favorite_teams", [])
        self.logger = logging.getLogger('NHL')
        
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

    def _load_fonts(self):
        """Load fonts used by the scoreboard."""
        fonts = {}
        try:
            # Try to load the 4x6 font for scores
            fonts['score'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 12)
            fonts['time'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 8)
            fonts['team'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 8)
            fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 9)
            logging.info("[NHL] Successfully loaded 4x6 font for all text elements")
        except IOError:
            logging.warning("[NHL] 4x6 font not found, trying PressStart2P font.")
            try:
                # Try to load the PressStart2P font as a fallback
                fonts['score'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 12)
                fonts['time'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
                fonts['team'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
                fonts['status'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 9)
                logging.info("[NHL] Successfully loaded PressStart2P font for all text elements")
            except IOError:
                logging.warning("[NHL] PressStart2P font not found, using default PIL font.")
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

    def _fetch_data(self, date_str: str = None) -> Optional[Dict]:
        """Fetch data from ESPN API or load test data."""
        url = ESPN_NHL_SCOREBOARD_URL
        params = {}
        if date_str:
            params['dates'] = date_str

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.info(f"[NHL] Successfully fetched data from ESPN API")
            return data
        except requests.exceptions.RequestException as e:
            logging.error(f"[NHL] Error fetching data from ESPN: {e}")
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

            details = {
                "start_time_utc": start_time_utc,
                "status_text": status["type"]["shortDetail"],
                "period": status.get("period", 0),
                "clock": status.get("displayClock", "0:00"),
                "is_live": status["type"]["state"] in ("in", "halftime"),
                "is_final": status["type"]["state"] == "post",
                "is_upcoming": status["type"]["state"] == "pre",
                "home_abbr": home_team["team"]["abbreviation"],
                "home_score": home_team.get("score", "0"),
                "home_logo_path": os.path.join(self.logo_dir, f"{home_team['team']['abbreviation']}.png"),
                "away_abbr": away_team["team"]["abbreviation"],
                "away_score": away_team.get("score", "0"),
                "away_logo_path": os.path.join(self.logo_dir, f"{away_team['team']['abbreviation']}.png"),
                "game_time": game_time,
                "game_date": game_date
            }

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

    def _draw_scorebug_layout(self):
        """Draw the scorebug layout for the current game."""
        try:
            # Create a new black image for the main display
            main_img = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 255))
            
            # Load logos once
            home_logo = self._load_and_resize_logo(self.current_game["home_abbr"])
            away_logo = self._load_and_resize_logo(self.current_game["away_abbr"])
            
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
            is_upcoming = self.current_game.get("is_upcoming", False)
            
            if is_upcoming:
                # For upcoming games, show date and time
                game_date = self.current_game.get("game_date", "")
                game_time = self.current_game.get("game_time", "")
                date_time_text = f"{game_date} {game_time}"
                
                # Calculate position for the date/time text (centered at the bottom)
                date_time_width = draw.textlength(date_time_text, font=self.fonts['time'])
                date_time_x = (self.display_width - date_time_width) // 2
                date_time_y = self.display_height - 15
                draw.text((date_time_x, date_time_y), date_time_text, font=self.fonts['time'], fill=(255, 255, 255))
                
                # Show "Next Game" at the top
                status_text = "Next Game"
                status_width = draw.textlength(status_text, font=self.fonts['status'])
                status_x = (self.display_width - status_width) // 2
                status_y = 5
                draw.text((status_x, status_y), status_text, font=self.fonts['status'], fill=(255, 255, 255))
            else:
                # For live/final games, show scores and period/time
                home_score = str(self.current_game.get("home_score", "0"))
                away_score = str(self.current_game.get("away_score", "0"))
                score_text = f"{away_score} - {home_score}"
                
                # Calculate position for the score text (centered at the bottom)
                score_width = draw.textlength(score_text, font=self.fonts['score'])
                score_x = (self.display_width - score_width) // 2
                score_y = self.display_height - 15
                draw.text((score_x, score_y), score_text, font=self.fonts['score'], fill=(255, 255, 255))

                # Draw period and time or Final
                if self.current_game.get("is_final", False):
                    status_text = "Final"
                else:
                    period = self.current_game.get("period", 0)
                    clock = self.current_game.get("clock", "0:00")
                    
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
            
        self._draw_scorebug_layout()

class NHLLiveManager(BaseNHLManager):
    """Manager for live NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("live_update_interval", 30)  # 30 seconds for live games
        self.no_data_interval = 300  # 5 minutes when no live games
        self.last_update = 0
        self.logger.info("Initialized NHL Live Manager")
        
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
            logging.info("[NHL] Initialized NHLLiveManager with test game: TB vs DAL")
        else:
            logging.info("[NHL] Initialized NHLLiveManager in live mode")

    def update(self):
        """Update live game data."""
        current_time = time.time()
        # Use longer interval if no game data
        interval = self.no_data_interval if not self.current_game else self.update_interval
        
        if current_time - self.last_update >= interval:
            self.logger.debug("Updating live game data")
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
                    logging.debug(f"[NHL] Updated test game clock: {self.current_game['clock']}")
            else:
                # Fetch live game data from ESPN API
                data = self._fetch_data()
                if data and "events" in data:
                    # Find the first live game involving favorite teams
                    for event in data["events"]:
                        details = self._extract_game_details(event)
                        if details and details["is_live"]:
                            if not self.favorite_teams or (
                                details["home_abbr"] in self.favorite_teams or 
                                details["away_abbr"] in self.favorite_teams
                            ):
                                self.current_game = details
                                logging.info(f"[NHL] Found live game: {details['away_abbr']} vs {details['home_abbr']}")
                                break
                    else:
                        # No live games found
                        self.current_game = None
                        logging.info("[NHL] No live games found")

    def display(self, force_clear: bool = False):
        """Display live game information."""
        if not self.current_game:
            return
        super().display(force_clear)  # Call parent class's display method

class NHLRecentManager(BaseNHLManager):
    """Manager for recently completed NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("recent_update_interval", 300)  # 5 minutes
        self.no_data_interval = 900  # 15 minutes when no recent games
        self.last_update = 0
        self.logger.info("Initialized NHL Recent Manager")
        self.recent_hours = self.nhl_config.get("recent_game_hours", 48)  # Default 48 hours
        self.current_game = None
        self.games_list = []  # List to store all recent games
        self.current_game_index = 0  # Index to track which game to show
        # Override test_mode to always use real data for recent games
        self.test_mode = False
        logging.info("[NHL] Initialized NHLRecentManager in live mode")

    def update(self):
        """Update recent game data."""
        current_time = time.time()
        # Use longer interval if no game data
        interval = self.no_data_interval if not self.games_list else self.update_interval
        
        if current_time - self.last_update >= interval:
            self.logger.debug("Updating recent game data")
            self.last_update = current_time
            
            # Fetch data for the last few days
            today = datetime.now(timezone.utc).date()
            dates_to_fetch = [
                (today - timedelta(days=2)).strftime('%Y%m%d'),
                (today - timedelta(days=1)).strftime('%Y%m%d'),
                today.strftime('%Y%m%d')
            ]
            
            # Fetch and combine data from all days
            all_events = []
            for date_str in dates_to_fetch:
                data = self._fetch_data(date_str)
                if data and "events" in data:
                    all_events.extend(data["events"])
            
            if all_events:
                # Find all recent completed games involving favorite teams
                recent_games = []
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.recent_hours)
                
                # Debug: Print all events to see what we're getting
                print("\nDEBUG - All events from ESPN:")
                for event in all_events:
                    try:
                        home_team = next(c for c in event["competitions"][0]["competitors"] if c.get("homeAway") == "home")
                        away_team = next(c for c in event["competitions"][0]["competitors"] if c.get("homeAway") == "away")
                        home_abbr = home_team["team"]["abbreviation"]
                        away_abbr = away_team["team"]["abbreviation"]
                        print(f"Game: {away_abbr} vs {home_abbr}")
                    except Exception as e:
                        print(f"Error parsing event: {e}")
                
                for event in all_events:
                    details = self._extract_game_details(event)
                    if details and details["is_final"] and details["start_time_utc"]:
                        # Check if game is within our time window
                        if details["start_time_utc"] > cutoff_time:
                            # Check if it involves favorite teams (if any are configured)
                            if not self.favorite_teams or (
                                details["home_abbr"] in self.favorite_teams or 
                                details["away_abbr"] in self.favorite_teams
                            ):
                                recent_games.append(details)
                
                # Sort games by start time, most recent first
                recent_games.sort(key=lambda x: x["start_time_utc"], reverse=True)
                
                if recent_games:
                    self.games_list = recent_games
                    # If we don't have a current game or it's not in the new list, start from the beginning
                    if not self.current_game or self.current_game not in self.games_list:
                        self.current_game_index = 0
                    else:
                        # Keep the same index if possible, otherwise reset to 0
                        try:
                            self.current_game_index = self.games_list.index(self.current_game)
                        except ValueError:
                            self.current_game_index = 0
                    
                    # Rotate to the next game
                    self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
                    self.current_game = self.games_list[self.current_game_index]
                    logging.info(f"[NHL] Rotating to recent game: {self.current_game['away_abbr']} vs {self.current_game['home_abbr']}")
                else:
                    logging.info("[NHL] No recent games found")
            else:
                logging.info("[NHL] No events found in the last few days")

    def display(self, force_clear: bool = False):
        """Display recent game information."""
        if not self.current_game:
            return
        super().display(force_clear)  # Call parent class's display method

class NHLUpcomingManager(BaseNHLManager):
    """Manager for upcoming NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("upcoming_update_interval", 300)  # 5 minutes
        self.no_data_interval = 900  # 15 minutes when no upcoming games
        self.last_update = 0
        self.logger.info("Initialized NHL Upcoming Manager")
        self.current_game = None
        self.games_list = []  # List to store all upcoming games
        self.current_game_index = 0  # Index to track which game to show

    def update(self):
        """Update upcoming game data."""
        current_time = time.time()
        # Use longer interval if no game data
        interval = self.no_data_interval if not self.games_list else self.update_interval
        
        if current_time - self.last_update >= interval:
            self.logger.debug("Updating upcoming game data")
            self.last_update = current_time
            
            # Fetch today's and tomorrow's data
            today = datetime.now(timezone.utc).date()
            tomorrow = today + timedelta(days=1)
            
            # Format dates for API (YYYYMMDD)
            today_str = today.strftime('%Y%m%d')
            tomorrow_str = tomorrow.strftime('%Y%m%d')
            
            # Fetch data for both days
            today_data = self._fetch_data(today_str)
            tomorrow_data = self._fetch_data(tomorrow_str)
            
            # Combine events from both days
            all_events = []
            if today_data and "events" in today_data:
                all_events.extend(today_data["events"])
            if tomorrow_data and "events" in tomorrow_data:
                all_events.extend(tomorrow_data["events"])
            
            # Find all upcoming games involving favorite teams
            upcoming_games = []
            
            for event in all_events:
                details = self._extract_game_details(event)
                if details and details["is_upcoming"] and details["start_time_utc"]:
                    # Check if it involves favorite teams (if any are configured)
                    if not self.favorite_teams or (
                        details["home_abbr"] in self.favorite_teams or 
                        details["away_abbr"] in self.favorite_teams
                    ):
                        upcoming_games.append(details)
            
            # Sort games by start time
            upcoming_games.sort(key=lambda x: x["start_time_utc"])
            
            if upcoming_games:
                self.games_list = upcoming_games
                # If we don't have a current game or it's not in the new list, start from the beginning
                if not self.current_game or self.current_game not in self.games_list:
                    self.current_game_index = 0
                else:
                    # Keep the same index if possible, otherwise reset to 0
                    try:
                        self.current_game_index = self.games_list.index(self.current_game)
                    except ValueError:
                        self.current_game_index = 0
                
                # Rotate to the next game
                self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
                self.current_game = self.games_list[self.current_game_index]
                logging.info(f"[NHL] Rotating to upcoming game: {self.current_game['away_abbr']} vs {self.current_game['home_abbr']}")
            else:
                logging.info("[NHL] No upcoming games found")

    def display(self, force_clear: bool = False):
        """Display upcoming game information."""
        if not self.current_game:
            return
        super().display(force_clear)  # Call parent class's display method 