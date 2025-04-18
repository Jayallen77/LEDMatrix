import os
import time
import logging
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime, timedelta, timezone

class BaseNHLManager:
    """Base class for NHL managers with common functionality."""
    def __init__(self, config: dict, display_manager):
        self.display_manager = display_manager
        self.config = config
        self.nhl_config = config.get("nhl_scoreboard", {})
        self.is_enabled = self.nhl_config.get("enabled", False)
        self.logo_dir = Path(config.get("nhl_scoreboard", {}).get("logo_dir", "assets/sports/nhl_logos"))
        self.update_interval = self.nhl_config.get("update_interval_seconds", 60)
        self.last_update = 0
        self.current_game = None
        self.fonts = self._load_fonts()

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

    def _extract_game_details(self, game_event):
        """Extract game details from an event."""
        if not game_event:
            return None

        details = {}
        try:
            competition = game_event["competitions"][0]
            status = competition["status"]
            competitors = competition["competitors"]
            game_date_str = game_event["date"]

            try:
                details["start_time_utc"] = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
            except ValueError:
                logging.warning(f"[NHL] Could not parse game date: {game_date_str}")
                details["start_time_utc"] = None

            home_team = next(c for c in competitors if c.get("homeAway") == "home")
            away_team = next(c for c in competitors if c.get("homeAway") == "away")

            details["status_text"] = status["type"]["shortDetail"]
            details["period"] = status.get("period", 0)
            details["clock"] = status.get("displayClock", "0:00")
            details["is_live"] = status["type"]["state"] in ("in", "halftime")
            details["is_final"] = status["type"]["state"] == "post"
            details["is_upcoming"] = status["type"]["state"] == "pre"

            details["home_abbr"] = home_team["team"]["abbreviation"]
            details["home_score"] = home_team.get("score", "0")
            details["home_logo_path"] = self.logo_dir / f"{details['home_abbr']}.png"

            details["away_abbr"] = away_team["team"]["abbreviation"]
            details["away_score"] = away_team.get("score", "0")
            details["away_logo_path"] = self.logo_dir / f"{details['away_abbr']}.png"

            # Validate logo files
            for logo_type in ['home', 'away']:
                logo_path = details[f"{logo_type}_logo_path"]
                if not logo_path.is_file():
                    logging.warning(f"[NHL] {logo_type.title()} logo not found: {logo_path}")
                    details[f"{logo_type}_logo_path"] = None
                else:
                    try:
                        with Image.open(logo_path) as img:
                            logging.debug(f"[NHL] {logo_type.title()} logo is valid: {img.format}, size: {img.size}")
                    except Exception as e:
                        logging.error(f"[NHL] {logo_type.title()} logo file exists but is not valid: {e}")
                        details[f"{logo_type}_logo_path"] = None

            return details

        except Exception as e:
            logging.error(f"[NHL] Error parsing game details: {e}")
            return None

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

class NHLLiveManager(BaseNHLManager):
    """Manager for live NHL games."""
    def __init__(self, config: dict, display_manager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("live_update_interval", 30)  # More frequent updates for live games

    def update(self):
        """Update live game data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

        # TODO: Implement live game data fetching
        self.last_update = current_time

    def display(self, force_clear: bool = False):
        """Display live game information."""
        if not self.current_game:
            return

        try:
            img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
            draw = ImageDraw.Draw(img)

            # Load and resize logos
            max_size = (self.display_manager.width // 3, self.display_manager.height // 2)
            home_logo = self._load_and_resize_logo(self.current_game["home_logo_path"], max_size)
            away_logo = self._load_and_resize_logo(self.current_game["away_logo_path"], max_size)

            # Draw logos
            if home_logo:
                home_x = self.display_manager.width // 4 - home_logo.width // 2
                home_y = self.display_manager.height // 4 - home_logo.height // 2
                temp_img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(home_logo, (home_x, home_y), home_logo)
                draw.im.paste(temp_img, (0, 0))

            if away_logo:
                away_x = self.display_manager.width // 4 - away_logo.width // 2
                away_y = 3 * self.display_manager.height // 4 - away_logo.height // 2
                temp_img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(away_logo, (away_x, away_y), away_logo)
                draw.im.paste(temp_img, (0, 0))

            # Draw scores
            home_score = str(self.current_game["home_score"])
            away_score = str(self.current_game["away_score"])
            
            home_score_x = self.display_manager.width // 2 - 10
            home_score_y = self.display_manager.height // 4 - 8
            away_score_x = self.display_manager.width // 2 - 10
            away_score_y = 3 * self.display_manager.height // 4 - 8

            draw.text((home_score_x, home_score_y), home_score, font=self.fonts['score'], fill=(255, 255, 255))
            draw.text((away_score_x, away_score_y), away_score, font=self.fonts['score'], fill=(255, 255, 255))

            # Draw game status (period and time)
            period = self.current_game["period"]
            clock = self.current_game["clock"]
            period_str = f"{period}{'st' if period==1 else 'nd' if period==2 else 'rd' if period==3 else 'th'}"
            
            status_x = self.display_manager.width // 2 - 20
            status_y = self.display_manager.height // 2 - 8
            draw.text((status_x, status_y), f"{period_str} {clock}", font=self.fonts['status'], fill=(255, 255, 255))

            self.display_manager.display_image(img)

        except Exception as e:
            logging.error(f"[NHL] Error displaying live game: {e}")

class NHLRecentManager(BaseNHLManager):
    """Manager for recently completed NHL games."""
    def __init__(self, config: dict, display_manager):
        super().__init__(config, display_manager)
        self.recent_hours = self.nhl_config.get("recent_game_hours", 48)
        self.update_interval = self.nhl_config.get("recent_update_interval", 300)  # 5 minutes

    def update(self):
        """Update recent game data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

        # TODO: Implement recent game data fetching
        self.last_update = current_time

    def display(self, force_clear: bool = False):
        """Display recent game information."""
        if not self.current_game:
            return

        try:
            img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
            draw = ImageDraw.Draw(img)

            # Load and resize logos
            max_size = (self.display_manager.width // 3, self.display_manager.height // 2)
            home_logo = self._load_and_resize_logo(self.current_game["home_logo_path"], max_size)
            away_logo = self._load_and_resize_logo(self.current_game["away_logo_path"], max_size)

            # Draw logos
            if home_logo:
                home_x = self.display_manager.width // 4 - home_logo.width // 2
                home_y = self.display_manager.height // 4 - home_logo.height // 2
                temp_img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(home_logo, (home_x, home_y), home_logo)
                draw.im.paste(temp_img, (0, 0))

            if away_logo:
                away_x = self.display_manager.width // 4 - away_logo.width // 2
                away_y = 3 * self.display_manager.height // 4 - away_logo.height // 2
                temp_img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(away_logo, (away_x, away_y), away_logo)
                draw.im.paste(temp_img, (0, 0))

            # Draw scores
            home_score = str(self.current_game["home_score"])
            away_score = str(self.current_game["away_score"])
            
            home_score_x = self.display_manager.width // 2 - 10
            home_score_y = self.display_manager.height // 4 - 8
            away_score_x = self.display_manager.width // 2 - 10
            away_score_y = 3 * self.display_manager.height // 4 - 8

            draw.text((home_score_x, home_score_y), home_score, font=self.fonts['score'], fill=(255, 255, 255))
            draw.text((away_score_x, away_score_y), away_score, font=self.fonts['score'], fill=(255, 255, 255))

            # Draw "FINAL" status
            status_x = self.display_manager.width // 2 - 20
            status_y = self.display_manager.height // 2 - 8
            draw.text((status_x, status_y), "FINAL", font=self.fonts['status'], fill=(255, 0, 0))

            self.display_manager.display_image(img)

        except Exception as e:
            logging.error(f"[NHL] Error displaying recent game: {e}")

class NHLUpcomingManager(BaseNHLManager):
    """Manager for upcoming NHL games."""
    def __init__(self, config: dict, display_manager):
        super().__init__(config, display_manager)
        self.update_interval = self.nhl_config.get("upcoming_update_interval", 300)  # 5 minutes

    def update(self):
        """Update upcoming game data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

        # TODO: Implement upcoming game data fetching
        self.last_update = current_time

    def display(self, force_clear: bool = False):
        """Display upcoming game information."""
        if not self.current_game:
            return

        try:
            img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
            draw = ImageDraw.Draw(img)

            # Load and resize logos
            max_size = (self.display_manager.width // 3, self.display_manager.height // 2)
            home_logo = self._load_and_resize_logo(self.current_game["home_logo_path"], max_size)
            away_logo = self._load_and_resize_logo(self.current_game["away_logo_path"], max_size)

            # Draw logos
            if home_logo:
                home_x = self.display_manager.width // 4 - home_logo.width // 2
                home_y = self.display_manager.height // 4 - home_logo.height // 2
                temp_img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(home_logo, (home_x, home_y), home_logo)
                draw.im.paste(temp_img, (0, 0))

            if away_logo:
                away_x = self.display_manager.width // 4 - away_logo.width // 2
                away_y = 3 * self.display_manager.height // 4 - away_logo.height // 2
                temp_img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(away_logo, (away_x, away_y), away_logo)
                draw.im.paste(temp_img, (0, 0))

            # Draw game time
            start_time = self.current_game["start_time_utc"]
            if start_time:
                local_time = start_time.astimezone()
                time_str = local_time.strftime("%I:%M %p").lstrip('0')
                date_str = local_time.strftime("%a %b %d")
                
                time_x = self.display_manager.width // 2 - 20
                time_y = self.display_manager.height // 2 - 8
                draw.text((time_x, time_y), time_str, font=self.fonts['time'], fill=(0, 255, 255))
                
                date_x = self.display_manager.width // 2 - 20
                date_y = time_y + 10
                draw.text((date_x, date_y), date_str, font=self.fonts['status'], fill=(0, 255, 255))

            self.display_manager.display_image(img)

        except Exception as e:
            logging.error(f"[NHL] Error displaying upcoming game: {e}") 