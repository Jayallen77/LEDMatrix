import os
import time
import logging
import requests
import json
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Constants
ESPN_NHL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"

class BaseNHLManager:
    """Base class for NHL managers with common functionality."""
    def __init__(self, config: dict, display_manager):
        self.display_manager = display_manager
        self.config = config
        self.nhl_config = config.get("nhl_scoreboard", {})
        self.is_enabled = self.nhl_config.get("enabled", False)
        self.test_mode = self.nhl_config.get("test_mode", False)
        self.logo_dir = Path(config.get("nhl_scoreboard", {}).get("logo_dir", "assets/sports/nhl_logos"))
        self.update_interval = self.nhl_config.get("update_interval_seconds", 60)
        self.last_update = 0
        self.current_game = None
        self.fonts = self._load_fonts()
        self.favorite_teams = self.nhl_config.get("favorite_teams", [])

        # Get display dimensions from config
        display_config = config.get("display", {})
        hardware_config = display_config.get("hardware", {})
        cols = hardware_config.get("cols", 64)
        chain = hardware_config.get("chain_length", 1)
        self.display_width = int(cols * chain)
        self.display_height = hardware_config.get("rows", 32)
        
        logging.info(f"[NHL] Test mode: {'enabled' if self.test_mode else 'disabled'}")
        logging.info(f"[NHL] Favorite teams: {self.favorite_teams}")
        logging.info(f"[NHL] Display dimensions: {self.display_width}x{self.display_height}")

    def _load_fonts(self):
        """Load fonts used by the scoreboard."""
        fonts = {}
        try:
            fonts['score'] = ImageFont.truetype("arial.ttf", 12)
            fonts['time'] = ImageFont.truetype("arial.ttf", 10)
            fonts['team'] = ImageFont.truetype("arial.ttf", 8)
            fonts['status'] = ImageFont.truetype("arial.ttf", 9)
        except IOError:
            logging.warning("[NHL] Arial font not found, using default PIL font.")
            fonts['score'] = ImageFont.load_default()
            fonts['time'] = ImageFont.load_default()
            fonts['team'] = ImageFont.load_default()
            fonts['status'] = ImageFont.load_default()
        return fonts

    def _load_and_resize_logo(self, logo_path: Path, max_size: tuple) -> Optional[Image.Image]:
        """Load and resize a logo image."""
        if not logo_path or not logo_path.is_file():
            return None

        try:
            logo = Image.open(logo_path)
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')
            logo.thumbnail(max_size, Image.Resampling.LANCZOS)
            return logo
        except Exception as e:
            logging.error(f"[NHL] Error loading logo {logo_path}: {e}")
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
                "home_logo_path": self.logo_dir / f"{home_team['team']['abbreviation']}.png",
                "away_abbr": away_team["team"]["abbreviation"],
                "away_score": away_team.get("score", "0"),
                "away_logo_path": self.logo_dir / f"{away_team['team']['abbreviation']}.png"
            }

            # Validate logo files
            for team in ["home", "away"]:
                logo_path = details[f"{team}_logo_path"]
                if not logo_path.is_file():
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

    def display(self, force_clear: bool = False):
        """Display game information."""
        if not self.current_game:
            logging.warning("[NHL] No game data available to display")
            return

        try:
            # Create a new black image
            img = Image.new('RGB', (self.display_width, self.display_height), 'black')
            draw = ImageDraw.Draw(img)

            # Calculate logo sizes
            max_size = (self.display_width // 3, self.display_height // 2)

            # Load and resize logos
            home_logo = self._load_and_resize_logo(self.current_game["home_logo_path"], max_size)
            away_logo = self._load_and_resize_logo(self.current_game["away_logo_path"], max_size)

            # Draw home team logo
            if home_logo:
                home_x = self.display_width // 4 - home_logo.width // 2
                home_y = self.display_height // 4 - home_logo.height // 2
                temp_img = Image.new('RGB', (self.display_width, self.display_height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_img.paste(home_logo, (home_x, home_y), home_logo)
                img.paste(temp_img, (0, 0))

            # Draw away team logo
            if away_logo:
                away_x = self.display_width // 4 - away_logo.width // 2
                away_y = 3 * self.display_height // 4 - away_logo.height // 2
                temp_img = Image.new('RGB', (self.display_width, self.display_height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_img.paste(away_logo, (away_x, away_y), away_logo)
                img.paste(temp_img, (0, 0))

            # Draw scores
            home_score = str(self.current_game["home_score"])
            away_score = str(self.current_game["away_score"])
            
            home_score_x = self.display_width // 2 - 10
            home_score_y = self.display_height // 4 - 8
            away_score_x = self.display_width // 2 - 10
            away_score_y = 3 * self.display_height // 4 - 8

            draw.text((home_score_x, home_score_y), home_score, font=self.fonts['score'], fill=(255, 255, 255))
            draw.text((away_score_x, away_score_y), away_score, font=self.fonts['score'], fill=(255, 255, 255))

            # Draw game status
            status_x = self.display_width // 2 - 20
            status_y = self.display_height // 2 - 8
            draw.text((status_x, status_y), self.current_game["status_text"], font=self.fonts['status'], fill=(255, 255, 255))

            # Display the image
            self.display_manager.image.paste(img, (0, 0))
            self.display_manager.update_display()
            logging.debug("[NHL] Successfully displayed game")

        except Exception as e:
            logging.error(f"[NHL] Error displaying game: {e}", exc_info=True)

class NHLLiveManager(BaseNHLManager):
    """Manager for live NHL games."""
    def __init__(self, config: dict, display_manager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("live_update_interval", 30)  # More frequent updates for live games
        
        # Initialize with test game only if test mode is enabled
        if self.test_mode:
            self.current_game = {
                "home_abbr": "TBL",
                "away_abbr": "DAL",
                "home_score": "3",
                "away_score": "2",
                "period": 2,
                "clock": "12:34",
                "home_logo_path": self.logo_dir / "TBL.png",
                "away_logo_path": self.logo_dir / "DAL.png"
            }
            logging.info("[NHL] Initialized NHLLiveManager with test game: TBL vs DAL")
        else:
            logging.info("[NHL] Initialized NHLLiveManager in live mode")

    def update(self):
        """Update live game data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

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

        self.last_update = current_time

    def display(self, force_clear: bool = False):
        """Display live game information."""
        if not self.current_game:
            logging.warning("[NHL] No game data available to display")
            return

        try:
            # Create a new black image
            img = Image.new('RGB', (self.display_width, self.display_height), 'black')
            draw = ImageDraw.Draw(img)

            # Calculate logo sizes
            max_size = (self.display_width // 3, self.display_height // 2)

            # Load and resize logos
            home_logo = self._load_and_resize_logo(self.current_game["home_logo_path"], max_size)
            away_logo = self._load_and_resize_logo(self.current_game["away_logo_path"], max_size)

            # Draw home team logo
            if home_logo:
                home_x = self.display_width // 4 - home_logo.width // 2
                home_y = self.display_height // 4 - home_logo.height // 2
                temp_img = Image.new('RGB', (self.display_width, self.display_height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_img.paste(home_logo, (home_x, home_y), home_logo)
                img.paste(temp_img, (0, 0))

            # Draw away team logo
            if away_logo:
                away_x = self.display_width // 4 - away_logo.width // 2
                away_y = 3 * self.display_height // 4 - away_logo.height // 2
                temp_img = Image.new('RGB', (self.display_width, self.display_height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_img.paste(away_logo, (away_x, away_y), away_logo)
                img.paste(temp_img, (0, 0))

            # Draw scores
            home_score = str(self.current_game["home_score"])
            away_score = str(self.current_game["away_score"])
            
            home_score_x = self.display_width // 2 - 10
            home_score_y = self.display_height // 4 - 8
            away_score_x = self.display_width // 2 - 10
            away_score_y = 3 * self.display_height // 4 - 8

            draw.text((home_score_x, home_score_y), home_score, font=self.fonts['score'], fill=(255, 255, 255))
            draw.text((away_score_x, away_score_y), away_score, font=self.fonts['score'], fill=(255, 255, 255))

            # Draw game status (period and time)
            period = self.current_game["period"]
            clock = self.current_game["clock"]
            period_str = f"{period}{'st' if period==1 else 'nd' if period==2 else 'rd' if period==3 else 'th'}"
            
            status_x = self.display_width // 2 - 20
            status_y = self.display_height // 2 - 8
            draw.text((status_x, status_y), f"{period_str} {clock}", font=self.fonts['status'], fill=(255, 255, 255))

            # Display the image
            self.display_manager.image.paste(img, (0, 0))
            self.display_manager.update_display()
            logging.debug("[NHL] Successfully displayed test game")

        except Exception as e:
            logging.error(f"[NHL] Error displaying live game: {e}", exc_info=True)

class NHLRecentManager(BaseNHLManager):
    """Manager for recently completed NHL games."""
    def __init__(self, config: dict, display_manager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("recent_update_interval", 3600)  # 1 hour
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
                "home_logo_path": self.logo_dir / "TBL.png",
                "away_logo_path": self.logo_dir / "DAL.png"
            }
            logging.info("[NHL] Initialized NHLRecentManager with test game: TBL vs DAL")
        else:
            logging.info("[NHL] Initialized NHLRecentManager in live mode")

    def update(self):
        """Update recent game data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

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

        self.last_update = current_time

    def display(self, force_clear: bool = False):
        """Display recent game information."""
        if not self.current_game:
            logging.warning("[NHL] No recent game data available to display")
            return

        try:
            # Create a new black image
            img = Image.new('RGB', (self.display_width, self.display_height), 'black')
            draw = ImageDraw.Draw(img)

            # Calculate logo sizes
            max_size = (self.display_width // 3, self.display_height // 2)

            # Load and resize logos
            home_logo = self._load_and_resize_logo(self.current_game["home_logo_path"], max_size)
            away_logo = self._load_and_resize_logo(self.current_game["away_logo_path"], max_size)

            # Draw home team logo
            if home_logo:
                home_x = self.display_width // 4 - home_logo.width // 2
                home_y = self.display_height // 4 - home_logo.height // 2
                temp_img = Image.new('RGB', (self.display_width, self.display_height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(home_logo, (home_x, home_y), home_logo)
                draw.im.paste(temp_img, (0, 0))

            # Draw away team logo
            if away_logo:
                away_x = self.display_width // 4 - away_logo.width // 2
                away_y = 3 * self.display_height // 4 - away_logo.height // 2
                temp_img = Image.new('RGB', (self.display_width, self.display_height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(away_logo, (away_x, away_y), away_logo)
                draw.im.paste(temp_img, (0, 0))

            # Draw scores
            home_score = str(self.current_game["home_score"])
            away_score = str(self.current_game["away_score"])
            
            home_score_x = self.display_width // 2 - 10
            home_score_y = self.display_height // 4 - 8
            away_score_x = self.display_width // 2 - 10
            away_score_y = 3 * self.display_height // 4 - 8

            draw.text((home_score_x, home_score_y), home_score, font=self.fonts['score'], fill=(255, 255, 255))
            draw.text((away_score_x, away_score_y), away_score, font=self.fonts['score'], fill=(255, 255, 255))

            # Draw "FINAL" status
            status_x = self.display_width // 2 - 20
            status_y = self.display_height // 2 - 8
            draw.text((status_x, status_y), "FINAL", font=self.fonts['status'], fill=(255, 255, 255))

            # Display the image
            self.display_manager.image.paste(img, (0, 0))
            self.display_manager.update_display()
            logging.debug("[NHL] Successfully displayed recent game")

        except Exception as e:
            logging.error(f"[NHL] Error displaying recent game: {e}", exc_info=True)

class NHLUpcomingManager(BaseNHLManager):
    """Manager for upcoming NHL games."""
    def __init__(self, config: dict, display_manager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("upcoming_update_interval", 3600)  # 1 hour
        self.current_game = None
        
        if self.test_mode:
            # Initialize with a test game
            self.current_game = {
                "home_abbr": "TBL",
                "away_abbr": "DAL",
                "status_text": "7:30 PM ET",
                "home_logo_path": self.logo_dir / "TBL.png",
                "away_logo_path": self.logo_dir / "DAL.png"
            }
            logging.info("[NHL] Initialized NHLUpcomingManager with test game: TBL vs DAL")
        else:
            logging.info("[NHL] Initialized NHLUpcomingManager in live mode")

    def update(self):
        """Update upcoming game data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

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

        self.last_update = current_time

    def display(self, force_clear: bool = False):
        """Display upcoming game information."""
        if not self.current_game:
            logging.warning("[NHL] No upcoming game data available to display")
            return

        try:
            # Create a new black image
            img = Image.new('RGB', (self.display_width, self.display_height), 'black')
            draw = ImageDraw.Draw(img)

            # Calculate logo sizes
            max_size = (self.display_width // 3, self.display_height // 2)

            # Load and resize logos
            home_logo = self._load_and_resize_logo(self.current_game["home_logo_path"], max_size)
            away_logo = self._load_and_resize_logo(self.current_game["away_logo_path"], max_size)

            # Draw home team logo
            if home_logo:
                home_x = self.display_width // 4 - home_logo.width // 2
                home_y = self.display_height // 4 - home_logo.height // 2
                temp_img = Image.new('RGB', (self.display_width, self.display_height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(home_logo, (home_x, home_y), home_logo)
                draw.im.paste(temp_img, (0, 0))

            # Draw away team logo
            if away_logo:
                away_x = self.display_width // 4 - away_logo.width // 2
                away_y = 3 * self.display_height // 4 - away_logo.height // 2
                temp_img = Image.new('RGB', (self.display_width, self.display_height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(away_logo, (away_x, away_y), away_logo)
                draw.im.paste(temp_img, (0, 0))

            # Draw game time
            status_x = self.display_width // 2 - 20
            status_y = self.display_height // 2 - 8
            draw.text((status_x, status_y), self.current_game["status_text"], font=self.fonts['status'], fill=(255, 255, 255))

            # Display the image
            self.display_manager.image.paste(img, (0, 0))
            self.display_manager.update_display()
            logging.debug("[NHL] Successfully displayed upcoming game")

        except Exception as e:
            logging.error(f"[NHL] Error displaying upcoming game: {e}", exc_info=True) 