import os
import time
import logging
import requests
import json
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont
import random # Import random for placeholder logo generation
from pathlib import Path
from datetime import datetime, timedelta, timezone
from src.display_manager import DisplayManager
from src.cache_manager import CacheManager

# Constants
ESPN_SOCCER_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/scoreboards"
# Common league slugs (add more as needed)
LEAGUE_SLUGS = {
    "eng.1": "Premier League",
    "esp.1": "La Liga",
    "ger.1": "Bundesliga",
    "ita.1": "Serie A",
    "fra.1": "Ligue 1",
    "uefa.champions": "Champions League",
    "uefa.europa": "Europa League",
    "usa.1": "MLS",
    # Add other leagues here if needed
}

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
            key: Cache key (usually the date string or league)
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
            key: Cache key
            data: Data to cache
        """
        cls._cache[key] = data
        cls._cache_timestamps[key] = time.time()
    
    @classmethod
    def clear(cls) -> None:
        """Clear all cached data."""
        cls._cache.clear()
        cls._cache_timestamps.clear()

class BaseSoccerManager:
    """Base class for Soccer managers with common functionality."""
    # Class variables for warning tracking
    _no_data_warning_logged = False
    _last_warning_time = 0
    _warning_cooldown = 60  # Only log warnings once per minute
    _shared_data = {}  # Dictionary to hold shared data per league/date
    _last_shared_update = {} # Dictionary for update times per league/date
    cache_manager = CacheManager()
    logger = logging.getLogger('Soccer') # Use 'Soccer' logger
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        self.display_manager = display_manager
        self.config = config
        self.soccer_config = config.get("soccer_scoreboard", {}) # Use 'soccer_scoreboard' config
        self.is_enabled = self.soccer_config.get("enabled", False)
        self.test_mode = self.soccer_config.get("test_mode", False)
        self.logo_dir = self.soccer_config.get("logo_dir", "assets/sports/soccer_logos") # Soccer logos
        self.update_interval = self.soccer_config.get("update_interval_seconds", 60)
        self.last_update = 0
        self.current_game = None
        self.fonts = self._load_fonts()
        self.favorite_teams = self.soccer_config.get("favorite_teams", [])
        self.target_leagues = self.soccer_config.get("leagues", list(LEAGUE_SLUGS.keys())) # Get target leagues from config
        self.recent_hours = self.soccer_config.get("recent_game_hours", 48)
        
        self.logger.setLevel(logging.DEBUG)
        
        display_config = config.get("display", {})
        hardware_config = display_config.get("hardware", {})
        cols = hardware_config.get("cols", 64)
        chain = hardware_config.get("chain_length", 1)
        self.display_width = int(cols * chain)
        self.display_height = hardware_config.get("rows", 32)
        
        self._logo_cache = {}
        
        self.logger.info(f"Initialized Soccer manager with display dimensions: {self.display_width}x{self.display_height}")
        self.logger.info(f"Logo directory: {self.logo_dir}")
        self.logger.info(f"Target leagues: {self.target_leagues}")

    @classmethod
    def _fetch_shared_data(cls, date_str: str = None) -> Optional[Dict]:
        """Fetch and cache data for all managers to share."""
        current_time = time.time()
        all_data = {"events": []} # Combine data from multiple dates/leagues

        # Determine dates to fetch
        today = datetime.now(timezone.utc).date()
        dates_to_fetch = [
            (today - timedelta(days=1)).strftime('%Y%m%d'), # Yesterday
            today.strftime('%Y%m%d'),                     # Today
            (today + timedelta(days=1)).strftime('%Y%m%d')      # Tomorrow (for upcoming)
        ]
        if date_str and date_str not in dates_to_fetch:
             dates_to_fetch.append(date_str) # Ensure specific requested date is included


        for fetch_date in dates_to_fetch:
            cache_key = f"soccer_{fetch_date}"
            
            # Check cache first
            cached_data = cls.cache_manager.get(cache_key, max_age=300) # 5 minutes cache
            if cached_data:
                cls.logger.info(f"[Soccer] Using cached data for {fetch_date}")
                if "events" in cached_data:
                    all_data["events"].extend(cached_data["events"])
                continue # Skip fetching if cached

            # If not in cache or stale, fetch from API
            try:
                url = ESPN_SOCCER_SCOREBOARD_URL
                params = {'dates': fetch_date, 'limit': 500} # Fetch more events if needed

                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                cls.logger.info(f"[Soccer] Successfully fetched data from ESPN API for date {fetch_date}")

                # Cache the response
                cls.cache_manager.set(cache_key, data)
                
                if "events" in data:
                    all_data["events"].extend(data["events"])

            except requests.exceptions.RequestException as e:
                cls.logger.error(f"[Soccer] Error fetching data from ESPN for date {fetch_date}: {e}")
                # Continue to try other dates even if one fails

        # Update shared data and timestamp (using a generic key for simplicity)
        cls._shared_data = all_data
        cls._last_shared_update = current_time

        return cls._shared_data


    def _fetch_data(self, date_str: str = None) -> Optional[Dict]:
        """Fetch data using shared data mechanism, ensuring fresh data for live games."""
        if isinstance(self, SoccerLiveManager) and not self.test_mode:
            # Live manager bypasses shared cache for most recent data
            try:
                url = ESPN_SOCCER_SCOREBOARD_URL
                # Fetch only today's data for live games
                today_date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
                params = {'dates': today_date_str, 'limit': 500}

                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                self.logger.info(f"[Soccer] Successfully fetched live game data from ESPN API for {today_date_str}")
                # Filter by target leagues immediately
                if "events" in data:
                     data["events"] = [
                        event for event in data["events"]
                        if event.get("league", {}).get("slug") in self.target_leagues
                    ]
                return data
            except requests.exceptions.RequestException as e:
                self.logger.error(f"[Soccer] Error fetching live game data from ESPN: {e}")
                return None
        else:
            # For non-live games or test mode, use the shared data fetch
            data = self._fetch_shared_data(date_str)
            # Filter shared data by target leagues
            if data and "events" in data:
                filtered_events = [
                    event for event in data["events"]
                    if event.get("league", {}).get("slug") in self.target_leagues
                ]
                # Return a copy to avoid modifying the shared cache
                return {"events": filtered_events}
            return data

    def _load_fonts(self):
        """Load fonts used by the scoreboard."""
        fonts = {}
        try:
            fonts['score'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10) # Slightly larger score
            fonts['time'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['team'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6) # Keep team abbr small
            fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6) # Keep status small
            logging.info("[Soccer] Successfully loaded custom fonts")
        except IOError:
            logging.warning("[Soccer] Custom fonts not found, using default PIL font.")
            fonts['score'] = ImageFont.load_default()
            fonts['time'] = ImageFont.load_default()
            fonts['team'] = ImageFont.load_default()
            fonts['status'] = ImageFont.load_default()
        return fonts

    def _draw_text_with_outline(self, draw, text, position, font, fill=(255, 255, 255), outline_color=(0, 0, 0)):
        """Draw text with a black outline for better readability."""
        x, y = position
        # Draw outline
        for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
        # Draw text
        draw.text((x, y), text, font=font, fill=fill)

    def _load_and_resize_logo(self, team_abbrev: str) -> Optional[Image.Image]:
        """Load and resize a team logo, with caching."""
        if team_abbrev in self._logo_cache:
            return self._logo_cache[team_abbrev]

        logo_path = os.path.join(self.logo_dir, f"{team_abbrev}.png")
        self.logger.debug(f"Logo path: {logo_path}")

        try:
            if not os.path.exists(logo_path):
                self.logger.info(f"Creating placeholder logo for {team_abbrev}")
                os.makedirs(os.path.dirname(logo_path), exist_ok=True)
                logo = Image.new('RGBA', (36, 36), (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200), 255))
                draw = ImageDraw.Draw(logo)
                # Optionally add text to placeholder
                try:
                    placeholder_font = ImageFont.truetype("assets/fonts/4x6-font.ttf", 12)
                    text_width = draw.textlength(team_abbrev, font=placeholder_font)
                    text_x = (36 - text_width) // 2
                    text_y = 10
                    draw.text((text_x, text_y), team_abbrev, fill=(0,0,0,255), font=placeholder_font)
                except IOError:
                    pass # Font not found, skip text
                logo.save(logo_path)
                self.logger.info(f"Created placeholder logo at {logo_path}")

            logo = Image.open(logo_path)
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')

            # Resize logo to target size
            target_size = 36 # Change target size to 36x36
            # Use resize instead of thumbnail to force size if image is smaller
            logo = logo.resize((target_size, target_size), Image.Resampling.LANCZOS)
            self.logger.debug(f"Resized {team_abbrev} logo to {logo.size}")

            self._logo_cache[team_abbrev] = logo
            return logo

        except Exception as e:
            self.logger.error(f"Error loading logo for {team_abbrev}: {e}", exc_info=True)
            return None

    def _format_game_time(self, status: Dict) -> str:
        """Format game time display for soccer (e.g., HT, FT, 45', 90+2')."""
        status_type = status["type"]["name"]
        clock = status.get("displayClock", "0:00")
        period = status.get("period", 0)

        if status_type == "STATUS_FINAL":
            return "FT"
        if status_type == "STATUS_HALFTIME":
            return "HT"
        if status_type == "STATUS_SCHEDULED":
            return "" # Handled by is_upcoming
        if status_type == "STATUS_POSTPONED":
            return "PPD"
        if status_type == "STATUS_CANCELED":
            return "CANC"
        
        # Handle live game time
        if status_type == "STATUS_IN_PROGRESS":
             # Simple clock display, potentially add period info if needed
             # Remove seconds for cleaner display
             if ':' in clock:
                 clock_parts = clock.split(':')
                 return f"{clock_parts[0]}'" # Display as minutes'
             else:
                 # Handle potential stoppage time format like "90:00+2"
                 if '+' in clock:
                     clock = clock.replace(':00', '') # Remove :00 for cleaner look
                 return clock
                 
        return clock # Default fallback

    def _extract_game_details(self, game_event: Dict) -> Optional[Dict]:
        """Extract relevant game details from ESPN Soccer API response."""
        if not game_event:
            return None

        try:
            competition = game_event["competitions"][0]
            status = competition["status"]
            competitors = competition["competitors"]
            game_date_str = game_event["date"]
            league_info = game_event.get("league", {})
            league_slug = league_info.get("slug")
            league_name = league_info.get("name", league_slug) # Use name if available

            # Filter out games not in target leagues (redundant check, but safe)
            if league_slug not in self.target_leagues:
                self.logger.debug(f"[Soccer] Skipping game from league: {league_name} ({league_slug})")
                return None

            try:
                start_time_utc = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
            except ValueError:
                logging.warning(f"[Soccer] Could not parse game date: {game_date_str}")
                start_time_utc = None

            home_team = next(c for c in competitors if c.get("homeAway") == "home")
            away_team = next(c for c in competitors if c.get("homeAway") == "away")

            game_time = ""
            game_date = ""
            if start_time_utc:
                local_time = start_time_utc.astimezone()
                game_time = local_time.strftime("%-I:%M%p").lower() # e.g., 2:30pm
                game_date = local_time.strftime("%-m/%-d")

            status_type = status["type"]["name"]
            is_live = status_type == "STATUS_IN_PROGRESS"
            is_final = status_type == "STATUS_FINAL"
            is_upcoming = status_type == "STATUS_SCHEDULED"
            is_halftime = status_type == "STATUS_HALFTIME"

            # Calculate if game is within recent/upcoming window
            is_within_window = False
            if start_time_utc:
                now_utc = datetime.now(timezone.utc)
                if is_upcoming:
                    cutoff_time = now_utc + timedelta(hours=self.recent_hours)
                    is_within_window = start_time_utc <= cutoff_time
                else: # Recent or live
                    cutoff_time = now_utc - timedelta(hours=self.recent_hours)
                    is_within_window = start_time_utc >= cutoff_time

            details = {
                "id": game_event["id"],
                "start_time_utc": start_time_utc,
                "status_text": status["type"]["shortDetail"],
                "game_clock_display": self._format_game_time(status),
                "period": status.get("period", 0), # 1st half, 2nd half, ET periods?
                "is_live": is_live or is_halftime, # Treat halftime as live for display purposes
                "is_final": is_final,
                "is_upcoming": is_upcoming,
                "is_within_window": is_within_window,
                "home_abbr": home_team["team"]["abbreviation"],
                "home_score": home_team.get("score", "0"),
                "home_logo": self._load_and_resize_logo(home_team["team"]["abbreviation"]),
                "away_abbr": away_team["team"]["abbreviation"],
                "away_score": away_team.get("score", "0"),
                "away_logo": self._load_and_resize_logo(away_team["team"]["abbreviation"]),
                "game_time": game_time, # Formatted local time (e.g., 2:30pm)
                "game_date": game_date, # Formatted local date (e.g., 7/21)
                "league": league_name
            }

            self.logger.debug(f"[Soccer] Extracted game: {details['away_abbr']} {details['away_score']} @ {details['home_abbr']} {details['home_score']} ({details['game_clock_display']}) - League: {details['league']} - Final: {details['is_final']}, Upcoming: {details['is_upcoming']}, Live: {details['is_live']}, Within Window: {details['is_within_window']}")

            # Basic validation (logos handled in loading)
            if not details["home_abbr"] or not details["away_abbr"]:
                 logging.warning(f"[Soccer] Missing team abbreviation in game data: {game_event['id']}")
                 return None

            return details
        except Exception as e:
            logging.error(f"[Soccer] Error extracting game details for event {game_event.get('id', 'N/A')}: {e}", exc_info=True)
            return None

    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:
        """Draw the soccer scorebug layout."""
        try:
            main_img = Image.new('RGB', (self.display_width, self.display_height), (0, 0, 0))
            draw = ImageDraw.Draw(main_img)

            home_logo = game.get("home_logo")
            away_logo = game.get("away_logo")

            # --- Layout Configuration ---
            logo_y = (self.display_height - (home_logo.height if home_logo else 20)) // 2
            away_logo_x = 2
            home_logo_x = self.display_width - (home_logo.width if home_logo else 20) - 2

            center_x = self.display_width // 2
            score_y = logo_y # Align score vertically with logos
            abbr_y = score_y + (self.fonts['score'].size if 'score' in self.fonts else 10) + 1 # Below score
            status_y = 1 # Status/Time at the top center

            # --- Draw Logos ---
            if away_logo:
                main_img.paste(away_logo, (away_logo_x, logo_y), away_logo)
            if home_logo:
                main_img.paste(home_logo, (home_logo_x, logo_y), home_logo)

            # --- Draw Team Abbreviations ---
            away_abbr = game.get("away_abbr", "AWAY")
            home_abbr = game.get("home_abbr", "HOME")
            abbr_font = self.fonts['team']

            away_abbr_width = draw.textlength(away_abbr, font=abbr_font)
            home_abbr_width = draw.textlength(home_abbr, font=abbr_font)

            # Position abbreviations near logos
            away_abbr_x = away_logo_x + (away_logo.width if away_logo else 20) + 2
            home_abbr_x = home_logo_x - home_abbr_width - 2

            self._draw_text_with_outline(draw, away_abbr, (away_abbr_x, abbr_y), abbr_font)
            self._draw_text_with_outline(draw, home_abbr, (home_abbr_x, abbr_y), abbr_font)


            # --- Draw Score / Game Time ---
            score_font = self.fonts['score']
            status_font = self.fonts['time'] # Use 'time' font for status line

            if game.get("is_upcoming"):
                # Display Date and Time for upcoming games
                game_date = game.get("game_date", "")
                game_time = game.get("game_time", "")
                date_time_text = f"{game_date} {game_time}"

                date_time_width = draw.textlength(date_time_text, font=status_font)
                date_time_x = center_x - date_time_width // 2
                # Position below logos/abbrs
                date_time_y = abbr_y + (self.fonts['team'].size if 'team' in self.fonts else 8) + 2

                self._draw_text_with_outline(draw, date_time_text, (date_time_x, date_time_y), status_font)

                # Show "Upcoming" status at the top
                status_text = "Upcoming"
                status_width = draw.textlength(status_text, font=status_font)
                status_x = center_x - status_width // 2
                self._draw_text_with_outline(draw, status_text, (status_x, status_y), status_font)

            else:
                # Display Score for live/final games
                home_score = str(game.get("home_score", "0"))
                away_score = str(game.get("away_score", "0"))
                score_text = f"{away_score} - {home_score}"

                score_width = draw.textlength(score_text, font=score_font)
                score_x = center_x - score_width // 2

                self._draw_text_with_outline(draw, score_text, (score_x, score_y), score_font)

                # --- Draw Game Status/Time ---
                status_text = game.get("game_clock_display", "")
                status_width = draw.textlength(status_text, font=status_font)
                status_x = center_x - status_width // 2
                self._draw_text_with_outline(draw, status_text, (status_x, status_y), status_font)


            # --- Display Image ---
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"Error displaying soccer game: {e}", exc_info=True)

    def display(self, force_clear: bool = False) -> None:
        """Common display method for all Soccer managers"""
        if not self.current_game:
            current_time = time.time()
            if not hasattr(self, '_last_warning_time'):
                self._last_warning_time = 0
            if current_time - self._last_warning_time > 300:
                self.logger.warning("[Soccer] No game data available to display")
                self._last_warning_time = current_time
            return

        self._draw_scorebug_layout(self.current_game, force_clear)

# ===============================================
# Manager Implementations (Live, Recent, Upcoming)
# ===============================================

class SoccerLiveManager(BaseSoccerManager):
    """Manager for live Soccer games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.update_interval = self.soccer_config.get("live_update_interval", 20) # Slightly longer for soccer?
        self.no_data_interval = 300
        self.last_update = 0
        self.logger.info("Initialized Soccer Live Manager")
        self.live_games = []
        self.current_game_index = 0
        self.last_game_switch = 0
        self.game_display_duration = self.soccer_config.get("live_game_duration", 20)
        self.last_display_update = 0
        self.last_log_time = 0
        self.log_interval = 300

        if self.test_mode:
            # Simple test game
            self.current_game = {
                "id": "test001",
                "home_abbr": "FCB", "away_abbr": "RMA", "home_score": "1", "away_score": "1",
                "game_clock_display": "65'", "period": 2, "is_live": True, "is_final": False, "is_upcoming": False,
                "home_logo": self._load_and_resize_logo("FCB"), "away_logo": self._load_and_resize_logo("RMA"),
                "league": "Test League"
            }
            self.live_games = [self.current_game]
            logging.info("[Soccer] Initialized SoccerLiveManager with test game: FCB vs RMA")
        else:
            logging.info("[Soccer] Initialized SoccerLiveManager in live mode")

    def update(self):
        """Update live game data."""
        current_time = time.time()
        interval = self.no_data_interval if not self.live_games else self.update_interval

        if current_time - self.last_update >= interval:
            self.last_update = current_time

            if self.test_mode:
                # Basic test mode clock update
                if self.current_game and self.current_game["is_live"]:
                    try:
                        minutes_str = self.current_game["game_clock_display"].replace("'", "")
                        minutes = int(minutes_str)
                        minutes += 1
                        if minutes == 45: self.current_game["game_clock_display"] = "HT"
                        elif minutes == 46: self.current_game["period"] = 2 # Start 2nd half
                        elif minutes > 90: self.current_game["game_clock_display"] = "FT"; self.current_game["is_live"]=False; self.current_game["is_final"]=True
                        else: self.current_game["game_clock_display"] = f"{minutes}'"
                    except ValueError: # Handle HT, FT states
                         if self.current_game["game_clock_display"] == "HT":
                             self.current_game["game_clock_display"] = "46'" # Start 2nd half after HT
                             self.current_game["period"] = 2
                         pass # Do nothing if FT or other non-numeric
                    # Always update display in test mode
                    # self.display(force_clear=True) # Display handled by controller loop
            else:
                # Fetch live game data
                data = self._fetch_data()
                new_live_games = []
                if data and "events" in data:
                    for event in data["events"]:
                        details = self._extract_game_details(event)
                        # Ensure it's live and involves a favorite team (if specified)
                        if details and details["is_live"]:
                             if not self.favorite_teams or (
                                details["home_abbr"] in self.favorite_teams or
                                details["away_abbr"] in self.favorite_teams
                            ):
                                new_live_games.append(details)

                    # Logging
                    should_log = (current_time - self.last_log_time >= self.log_interval or
                                  len(new_live_games) != len(self.live_games) or
                                  not self.live_games)
                    if should_log:
                        if new_live_games:
                            self.logger.info(f"[Soccer] Found {len(new_live_games)} live games involving favorite teams / all teams.")
                            for game in new_live_games:
                                self.logger.info(f"[Soccer] Live game: {game['away_abbr']} vs {game['home_abbr']} ({game['game_clock_display']}) - {game['league']}")
                        else:
                            self.logger.info("[Soccer] No live games found matching criteria.")
                        self.last_log_time = current_time

                    # Update game list and current game
                    if new_live_games:
                         # Check if the list of games actually changed (based on ID)
                         new_game_ids = {game['id'] for game in new_live_games}
                         current_game_ids = {game['id'] for game in self.live_games}

                         if new_game_ids != current_game_ids:
                             self.live_games = sorted(new_live_games, key=lambda x: x['start_time_utc'] or datetime.now(timezone.utc)) # Sort by time
                             # Reset index if current game is gone or list is new
                             if not self.current_game or self.current_game['id'] not in new_game_ids:
                                 self.current_game_index = 0
                                 if self.live_games:
                                     self.current_game = self.live_games[0]
                                     self.last_game_switch = current_time # Reset switch timer
                                 else:
                                     self.current_game = None
                             else:
                                # Update the currently displayed game data if it still exists
                                 try:
                                     current_game_id = self.current_game['id']
                                     self.current_game = next(g for g in new_live_games if g['id'] == current_game_id)
                                 except StopIteration:
                                     # Should not happen if check above works, but handle defensively
                                     self.current_game_index = 0
                                     self.current_game = self.live_games[0] if self.live_games else None
                                     self.last_game_switch = current_time

                         else: # Games are the same, just update data
                             updated_live_games = []
                             for existing_game in self.live_games:
                                try:
                                    updated_game = next(g for g in new_live_games if g['id'] == existing_game['id'])
                                    updated_live_games.append(updated_game)
                                    # Update current_game if it's the one being displayed
                                    if self.current_game and self.current_game['id'] == updated_game['id']:
                                        self.current_game = updated_game
                                except StopIteration:
                                    pass # Game disappeared between checks?
                             self.live_games = updated_live_games


                         # Limit display updates
                         # if current_time - self.last_display_update >= 1.0:
                         #    self.display(force_clear=True) # Display handled by controller
                         #    self.last_display_update = current_time
                    else:
                        # No live games found
                        if self.live_games: # Log only if previously had games
                            self.logger.info("[Soccer] All live games have ended or no longer match criteria.")
                        self.live_games = []
                        self.current_game = None


                # Check if it's time to switch displayed game
                if len(self.live_games) > 1 and (current_time - self.last_game_switch) >= self.game_display_duration:
                    self.current_game_index = (self.current_game_index + 1) % len(self.live_games)
                    self.current_game = self.live_games[self.current_game_index]
                    self.last_game_switch = current_time
                    # Force display handled by controller on mode switch
                    # self.display(force_clear=True) # Display handled by controller
                    # self.last_display_update = current_time

    def display(self, force_clear: bool = False):
        """Display live game information."""
        # This method might be redundant if controller handles display calls
        # but keep it for potential direct calls or consistency
        if not self.current_game:
            # Optionally clear screen or show 'No Live Games' message
            # self.display_manager.clear_display() # Example
            return
        super().display(force_clear)


class SoccerRecentManager(BaseSoccerManager):
    """Manager for recently completed Soccer games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.recent_games = [] # Holds all fetched recent games matching criteria
        self.games_list = []   # Holds games filtered by favorite teams (if applicable)
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = 300 # 5 minutes for recent games
        self.last_game_switch = 0
        self.game_display_duration = 15 # Short display time for recent/upcoming
        self.logger.info(f"Initialized SoccerRecentManager")

    def update(self):
        """Update recent games data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

        self.last_update = current_time
        try:
            data = self._fetch_data() # Fetches shared data (past/present/future)
            if not data or 'events' not in data:
                self.logger.warning("[Soccer] No recent events found in ESPN API response")
                self.recent_games = []
                self.games_list = []
                self.current_game = None
                return

            # Process and filter games
            new_recent_games = []
            now_utc = datetime.now(timezone.utc)
            cutoff_time = now_utc - timedelta(hours=self.recent_hours)

            for event in data['events']:
                game = self._extract_game_details(event)
                if game and game['is_final'] and game['start_time_utc'] and game['start_time_utc'] >= cutoff_time:
                     # Check favorite teams if list is provided
                     if not self.favorite_teams or (game['home_abbr'] in self.favorite_teams or game['away_abbr'] in self.favorite_teams):
                        new_recent_games.append(game)

            # Sort games by start time, most recent first
            new_recent_games.sort(key=lambda x: x['start_time_utc'], reverse=True)

            # Update only if the list content changes
            new_ids = {g['id'] for g in new_recent_games}
            current_ids = {g['id'] for g in self.games_list}

            if new_ids != current_ids:
                self.logger.info(f"[Soccer] Found {len(new_recent_games)} recent games matching criteria.")
                self.recent_games = new_recent_games # Keep raw filtered list
                self.games_list = new_recent_games   # Use the same list for display rotation
                
                # Reset display index if needed
                if not self.current_game or self.current_game['id'] not in new_ids:
                    self.current_game_index = 0
                    if self.games_list:
                        self.current_game = self.games_list[0]
                        self.last_game_switch = current_time # Reset timer when list changes
                    else:
                        self.current_game = None

        except Exception as e:
            self.logger.error(f"[Soccer] Error updating recent games: {e}", exc_info=True)
            self.games_list = []
            self.current_game = None

    def display(self, force_clear=False):
        """Display recent games, rotating through games_list."""
        if not self.games_list:
            # self.logger.debug("[Soccer] No recent games to display") # Too noisy
            return # Skip display update entirely

        try:
            current_time = time.time()

            # Check if it's time to switch games
            if len(self.games_list) > 1 and current_time - self.last_game_switch >= self.game_display_duration:
                self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
                self.current_game = self.games_list[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True # Force clear when switching games

            # Ensure current_game is set (it might be None initially)
            if not self.current_game and self.games_list:
                 self.current_game = self.games_list[self.current_game_index]
                 force_clear = True # Force clear on first display

            if self.current_game:
                 self._draw_scorebug_layout(self.current_game, force_clear)
                 # Display update handled by controller loop
                 # self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"[Soccer] Error displaying recent game: {e}", exc_info=True)


class SoccerUpcomingManager(BaseSoccerManager):
    """Manager for upcoming Soccer games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        super().__init__(config, display_manager)
        self.upcoming_games = [] # Filtered list for display
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = 300 # 5 minutes
        self.last_log_time = 0
        self.log_interval = 300
        self.last_warning_time = 0
        self.warning_cooldown = 300
        self.last_game_switch = 0
        self.game_display_duration = 15 # Short display time
        self.logger.info(f"Initialized SoccerUpcomingManager")

    def update(self):
        """Update upcoming games data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

        self.last_update = current_time
        try:
            data = self._fetch_data() # Fetches shared data
            if not data or 'events' not in data:
                self.logger.warning("[Soccer] No upcoming events found in ESPN API response")
                self.upcoming_games = []
                self.current_game = None
                return

            # Process and filter games
            new_upcoming_games = []
            now_utc = datetime.now(timezone.utc)
            cutoff_time = now_utc + timedelta(hours=self.recent_hours) # Use recent_hours as upcoming window

            for event in data['events']:
                game = self._extract_game_details(event)
                # Must be upcoming, have a start time, and be within the window
                if game and game['is_upcoming'] and game['start_time_utc'] and \
                   game['start_time_utc'] >= now_utc and game['start_time_utc'] <= cutoff_time:
                    # Check favorite teams if list is provided
                     if not self.favorite_teams or (game['home_abbr'] in self.favorite_teams or game['away_abbr'] in self.favorite_teams):
                        new_upcoming_games.append(game)

            # Sort games by start time, soonest first
            new_upcoming_games.sort(key=lambda x: x['start_time_utc'])

             # Update only if the list content changes
            new_ids = {g['id'] for g in new_upcoming_games}
            current_ids = {g['id'] for g in self.upcoming_games}

            if new_ids != current_ids:
                # Logging
                should_log = (current_time - self.last_log_time >= self.log_interval or
                              len(new_upcoming_games) != len(self.upcoming_games) or
                              not self.upcoming_games)
                if should_log:
                    if new_upcoming_games:
                        self.logger.info(f"[Soccer] Found {len(new_upcoming_games)} upcoming games matching criteria.")
                        # Log first few games for brevity
                        for game in new_upcoming_games[:3]:
                            self.logger.info(f"[Soccer] Upcoming game: {game['away_abbr']} vs {game['home_abbr']} ({game['game_date']} {game['game_time']}) - {game['league']}")
                    else:
                        self.logger.info("[Soccer] No upcoming games found matching criteria.")
                    self.last_log_time = current_time

                self.upcoming_games = new_upcoming_games

                # Reset display index if needed
                if not self.current_game or self.current_game['id'] not in new_ids:
                    self.current_game_index = 0
                    if self.upcoming_games:
                        self.current_game = self.upcoming_games[0]
                        self.last_game_switch = current_time # Reset timer
                    else:
                        self.current_game = None

        except Exception as e:
            self.logger.error(f"[Soccer] Error updating upcoming games: {e}", exc_info=True)
            self.upcoming_games = []
            self.current_game = None

    def display(self, force_clear=False):
        """Display upcoming games, rotating through upcoming_games list."""
        if not self.upcoming_games:
            current_time = time.time()
            if current_time - self.last_warning_time > self.warning_cooldown:
                # self.logger.info("[Soccer] No upcoming games to display") # Too noisy
                self.last_warning_time = current_time
            return # Skip display update entirely

        try:
            current_time = time.time()

            # Check if it's time to switch games
            if len(self.upcoming_games) > 1 and current_time - self.last_game_switch >= self.game_display_duration:
                self.current_game_index = (self.current_game_index + 1) % len(self.upcoming_games)
                self.current_game = self.upcoming_games[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True # Force clear when switching games

            # Ensure current_game is set
            if not self.current_game and self.upcoming_games:
                 self.current_game = self.upcoming_games[self.current_game_index]
                 force_clear = True

            if self.current_game:
                 self._draw_scorebug_layout(self.current_game, force_clear)
                 # Update display handled by controller loop
                 # self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"[Soccer] Error displaying upcoming game: {e}", exc_info=True) 