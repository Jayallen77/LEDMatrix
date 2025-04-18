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
            fonts['time'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 10)
            fonts['team'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 8)
            fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 9)
            logging.info("[NHL] Successfully loaded 4x6 font for all text elements")
        except IOError:
            logging.warning("[NHL] 4x6 font not found, trying PressStart2P font.")
            try:
                # Try to load the PressStart2P font as a fallback
                fonts['score'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 12)
                fonts['time'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10)
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
                if team_abbrev == "TBL":
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
            max_width = self.display_width // 3  # Increased from 4 to 3 for larger logos
            max_height = self.display_height // 2  # Half of display height
            
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
                game_time = local_time.strftime("%I:%M %p")
                game_date = local_time.strftime("%b %d")

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

    def display(self, force_clear: bool = False) -> None:
        """Common display method for all NHL managers"""
        self.logger.info(f"BaseNHLManager.display() called with force_clear={force_clear}")
        if not self.current_game:
            current_time = time.time()
            if not hasattr(self, '_last_warning_time'):
                self._last_warning_time = 0
            if current_time - self._last_warning_time > 300:  # 5 minutes cooldown
                self.logger.warning("[NHL] No game data available to display")
                self._last_warning_time = current_time
            return
            
        self._draw_scorebug_layout()

    def _draw_scorebug_layout(self):
        """Draw the scorebug layout for the current game."""
        try:
            self.logger.info("=== Starting scorebug layout ===")
            # Create a new black image for the main display
            main_img = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 255))
            
            # Load logos once
            home_logo = self._load_and_resize_logo(self.current_game["home_abbr"])
            away_logo = self._load_and_resize_logo(self.current_game["away_abbr"])
            
            self.logger.info(f"Display dimensions: {self.display_width}x{self.display_height}")
            self.logger.info(f"Home team ({self.current_game['home_abbr']}) logo loaded: {home_logo is not None}")
            self.logger.info(f"Away team ({self.current_game['away_abbr']}) logo loaded: {away_logo is not None}")
            
            if home_logo:
                self.logger.info(f"Home logo size: {home_logo.size}, mode: {home_logo.mode}")
            if away_logo:
                self.logger.info(f"Away logo size: {away_logo.size}, mode: {away_logo.mode}")

            # Create a single overlay for both logos
            overlay = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 0))

            # Calculate vertical center line for alignment
            center_y = self.display_height // 2
            self.logger.info(f"Vertical center line: {center_y}")

            # Draw home team logo (far right)
            if home_logo:
                # Position home logo at the far right with padding
                home_x = self.display_width - home_logo.width - 10  # Increased padding to 10 pixels
                home_y = center_y - (home_logo.height // 2)  # Center vertically
                self.logger.info(f"Home logo position: ({home_x}, {home_y})")
                
                # Check if logo fits within display bounds
                if home_x < 0 or home_y < 0 or home_x + home_logo.width > self.display_width or home_y + home_logo.height > self.display_height:
                    self.logger.warning(f"Home logo may be out of bounds: x={home_x}, y={home_y}, width={home_logo.width}, height={home_logo.height}")
                
                # Create a blue-tinted version of the home logo
                home_tinted = home_logo.copy()
                home_tinted_data = home_tinted.load()
                for x in range(home_tinted.width):
                    for y in range(home_tinted.height):
                        r, g, b, a = home_tinted_data[x, y]
                        if a > 0:  # Only modify non-transparent pixels
                            # Strong blue tint
                            home_tinted_data[x, y] = (r, g, min(255, b + 200), a)
                
                # Create stronger glow effect
                glow_draw = ImageDraw.Draw(overlay)
                glow_color = (0, 0, 255, 180)  # More opaque blue glow
                glow_draw.ellipse([
                    home_x - 10, home_y - 10,
                    home_x + home_logo.width + 10,
                    home_y + home_logo.height + 10
                ], fill=glow_color)
                
                # Paste the home logo onto the overlay
                overlay.paste(home_tinted, (home_x, home_y), home_tinted)
            else:
                self.logger.error(f"Home logo is None for team {self.current_game['home_abbr']}")

            # Draw away team logo (far left)
            if away_logo:
                # Position away logo at the far left with padding
                away_x = 10  # Increased padding to 10 pixels
                away_y = center_y - (away_logo.height // 2)  # Center vertically
                self.logger.info(f"Away logo position: ({away_x}, {away_y})")
                
                # Check if logo fits within display bounds
                if away_x < 0 or away_y < 0 or away_x + away_logo.width > self.display_width or away_y + away_logo.height > self.display_height:
                    self.logger.warning(f"Away logo may be out of bounds: x={away_x}, y={away_y}, width={away_logo.width}, height={away_logo.height}")
                
                # Create a red-tinted version of the away logo
                away_tinted = away_logo.copy()
                away_tinted_data = away_tinted.load()
                for x in range(away_tinted.width):
                    for y in range(away_tinted.height):
                        r, g, b, a = away_tinted_data[x, y]
                        if a > 0:  # Only modify non-transparent pixels
                            # Strong red tint
                            away_tinted_data[x, y] = (min(255, r + 200), g, b, a)
                
                # Create stronger glow effect
                glow_draw = ImageDraw.Draw(overlay)
                glow_color = (255, 0, 0, 180)  # More opaque red glow
                glow_draw.ellipse([
                    away_x - 10, away_y - 10,
                    away_x + away_logo.width + 10,
                    away_y + away_logo.height + 10
                ], fill=glow_color)
                
                # Paste the away logo onto the overlay
                overlay.paste(away_tinted, (away_x, away_y), away_tinted)
            else:
                self.logger.error(f"Away logo is None for team {self.current_game['away_abbr']}")

            # Composite the overlay with the main image
            main_img = Image.alpha_composite(main_img, overlay)

            # Save debug image to check logo positions (in the same directory as the script)
            debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_layout.png")
            try:
                main_img.save(debug_path)
                self.logger.info(f"Debug layout saved to: {debug_path}")
            except Exception as e:
                self.logger.warning(f"Could not save debug image: {e}")

            # Convert to RGB for final display
            main_img = main_img.convert('RGB')
            draw = ImageDraw.Draw(main_img)

            # Draw scores in the format "AWAY - HOME"
            home_score = str(self.current_game["home_score"])
            away_score = str(self.current_game["away_score"])
            score_text = f"{away_score} - {home_score}"
            
            # Calculate position for the score text (centered at the bottom)
            score_width = draw.textlength(score_text, font=self.fonts['score'])
            score_x = (self.display_width - score_width) // 2
            score_y = self.display_height - 15  # Position at bottom with padding
            self.logger.info(f"Score text position: ({score_x}, {score_y})")
            draw.text((score_x, score_y), score_text, font=self.fonts['score'], fill=(255, 255, 255))

            # Draw game status
            status_text = self.current_game.get("status_text", "")
            status_width = draw.textlength(status_text, font=self.fonts['status'])
            status_x = (self.display_width - status_width) // 2
            status_y = 5  # Position at top with padding
            self.logger.info(f"Status text position: ({status_x}, {status_y})")
            draw.text((status_x, status_y), status_text, font=self.fonts['status'], fill=(255, 255, 255))

            # Display the image
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display()
            self.logger.info("=== Scorebug layout completed ===")

        except Exception as e:
            self.logger.error(f"Error displaying game: {e}", exc_info=True)

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
                "home_abbr": "TBL",
                "away_abbr": "DAL",
                "home_score": "3",
                "away_score": "2",
                "period": 2,
                "clock": "12:34",
                "home_logo_path": os.path.join(self.logo_dir, "TBL.png"),
                "away_logo_path": os.path.join(self.logo_dir, "DAL.png"),
                "game_time": "7:30 PM",
                "game_date": "Apr 17"
            }
            logging.info("[NHL] Initialized NHLLiveManager with test game: TBL vs DAL")
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
        self.logger.info("NHLLiveManager.display() called")
        if not self.current_game:
            logging.warning("[NHL] No game data available to display")
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
        
        if self.test_mode:
            # Initialize with a test game
            self.current_game = {
                "home_abbr": "TBL",
                "away_abbr": "DAL",
                "home_score": "4",
                "away_score": "2",
                "status_text": "Final",
                "home_logo_path": os.path.join(self.logo_dir, "TBL.png"),
                "away_logo_path": os.path.join(self.logo_dir, "DAL.png"),
                "game_time": "7:30 PM",
                "game_date": "Apr 17"
            }
            logging.info("[NHL] Initialized NHLRecentManager with test game: TBL vs DAL")
        else:
            logging.info("[NHL] Initialized NHLRecentManager in live mode")

    def update(self):
        """Update recent game data."""
        current_time = time.time()
        # Use longer interval if no game data
        interval = self.no_data_interval if not self.current_game else self.update_interval
        
        if current_time - self.last_update >= interval:
            self.logger.debug("Updating recent game data")
            self.last_update = current_time
            if self.test_mode:
                # In test mode, just keep the test game
                pass
            else:
                # Fetch data for the last 48 hours
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.recent_hours)
                data = self._fetch_data()
                
                if data and "events" in data:
                    # Find the most recent completed game involving favorite teams
                    most_recent_game = None
                    most_recent_time = None
                    
                    for event in data["events"]:
                        details = self._extract_game_details(event)
                        if details and details["is_final"] and details["start_time_utc"]:
                            # Check if game is within our time window
                            if details["start_time_utc"] > cutoff_time:
                                # Check if it involves favorite teams (if any are configured)
                                if not self.favorite_teams or (
                                    details["home_abbr"] in self.favorite_teams or 
                                    details["away_abbr"] in self.favorite_teams
                                ):
                                    # Keep the most recent game
                                    if most_recent_time is None or details["start_time_utc"] > most_recent_time:
                                        most_recent_game = details
                                        most_recent_time = details["start_time_utc"]
                    
                    self.current_game = most_recent_game
                    if most_recent_game:
                        logging.info(f"[NHL] Found recent game: {most_recent_game['away_abbr']} vs {most_recent_game['home_abbr']}")
                    else:
                        logging.info("[NHL] No recent games found")

    def display(self, force_clear: bool = False):
        """Display recent game information."""
        self.logger.info("NHLRecentManager.display() called")
        if not self.current_game:
            logging.warning("[NHL] No recent game data available to display")
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
        
        if self.test_mode:
            # Initialize with a test game
            self.current_game = {
                "home_abbr": "TBL",
                "away_abbr": "DAL",
                "status_text": "7:30 PM ET",
                "home_logo_path": os.path.join(self.logo_dir, "TBL.png"),
                "away_logo_path": os.path.join(self.logo_dir, "DAL.png"),
                "game_time": "7:30 PM",
                "game_date": "Apr 17"
            }
            logging.info("[NHL] Initialized NHLUpcomingManager with test game: TBL vs DAL")
        else:
            logging.info("[NHL] Initialized NHLUpcomingManager in live mode")

    def update(self):
        """Update upcoming game data."""
        current_time = time.time()
        # Use longer interval if no game data
        interval = self.no_data_interval if not self.current_game else self.update_interval
        
        if current_time - self.last_update >= interval:
            self.logger.debug("Updating upcoming game data")
            self.last_update = current_time
            if self.test_mode:
                # In test mode, just keep the test game
                pass
            else:
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
                
                # Find the next upcoming game involving favorite teams
                next_game = None
                next_game_time = None
                
                for event in all_events:
                    details = self._extract_game_details(event)
                    if details and details["is_upcoming"] and details["start_time_utc"]:
                        # Check if it involves favorite teams (if any are configured)
                        if not self.favorite_teams or (
                            details["home_abbr"] in self.favorite_teams or 
                            details["away_abbr"] in self.favorite_teams
                        ):
                            # Keep the soonest upcoming game
                            if next_game_time is None or details["start_time_utc"] < next_game_time:
                                next_game = details
                                next_game_time = details["start_time_utc"]
                
                self.current_game = next_game
                if next_game:
                    logging.info(f"[NHL] Found upcoming game: {next_game['away_abbr']} vs {next_game['home_abbr']}")
                else:
                    logging.info("[NHL] No upcoming games found")

    def display(self, force_clear: bool = False):
        """Display upcoming game information."""
        self.logger.info("NHLUpcomingManager.display() called")
        if not self.current_game:
            logging.warning("[NHL] No upcoming game data available to display")
            return
        super().display(force_clear)  # Call parent class's display method 