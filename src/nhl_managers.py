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
        # Initialize with a test game
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

    def update(self):
        """Update live game data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

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

        self.last_update = current_time

    def display(self, force_clear: bool = False):
        """Display live game information."""
        if not self.current_game:
            logging.warning("[NHL] No game data available to display")
            return

        try:
            # Create a new black image
            img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
            draw = ImageDraw.Draw(img)

            # Calculate logo sizes
            max_size = (self.display_manager.width // 3, self.display_manager.height // 2)

            # Load and resize logos
            home_logo = self._load_and_resize_logo(self.current_game["home_logo_path"], max_size)
            away_logo = self._load_and_resize_logo(self.current_game["away_logo_path"], max_size)

            # Draw home team logo
            if home_logo:
                home_x = self.display_manager.width // 4 - home_logo.width // 2
                home_y = self.display_manager.height // 4 - home_logo.height // 2
                temp_img = Image.new('RGB', (self.display_manager.width, self.display_manager.height), 'black')
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.im.paste(home_logo, (home_x, home_y), home_logo)
                draw.im.paste(temp_img, (0, 0))

            # Draw away team logo
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

            # Display the image
            self.display_manager.display_image(img)
            logging.debug("[NHL] Successfully displayed test game")

        except Exception as e:
            logging.error(f"[NHL] Error displaying live game: {e}", exc_info=True) 