import time
import logging
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from .cache_manager import CacheManager
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pytz

# Get logger
logger = logging.getLogger(__name__)

class BaseMLBManager:
    """Base class for MLB managers with common functionality."""
    def __init__(self, config: Dict[str, Any], display_manager):
        self.config = config
        self.display_manager = display_manager
        self.mlb_config = config.get('mlb', {})
        self.favorite_teams = self.mlb_config.get('favorite_teams', [])
        self.cache_manager = CacheManager()
        self.logger = logging.getLogger(__name__)
        
        # Logo handling
        self.logo_dir = self.mlb_config.get('logo_dir', os.path.join('assets', 'sports', 'mlb_logos'))
        if not os.path.exists(self.logo_dir):
            self.logger.warning(f"MLB logos directory not found: {self.logo_dir}")
            try:
                os.makedirs(self.logo_dir, exist_ok=True)
                self.logger.info(f"Created MLB logos directory: {self.logo_dir}")
            except Exception as e:
                self.logger.error(f"Failed to create MLB logos directory: {e}")
        
        # Set up session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def _get_team_logo(self, team_abbr: str) -> Optional[Image.Image]:
        """Get team logo from the configured directory."""
        try:
            logo_path = os.path.join(self.logo_dir, f"{team_abbr}.png")
            if os.path.exists(logo_path):
                return Image.open(logo_path)
            else:
                logger.warning(f"Logo not found for team {team_abbr}")
                return None
        except Exception as e:
            logger.error(f"Error loading logo for team {team_abbr}: {e}")
            return None

    def _draw_base_indicators(self, draw: ImageDraw.Draw, bases_occupied: List[bool], center_x: int, y: int) -> None:
        """Draw base indicators on the display."""
        base_size = 8  # Increased from 6 to 8 for better visibility
        base_spacing = 10  # Increased from 8 to 10 for better spacing
        
        # Draw diamond outline with thicker lines
        diamond_points = [
            (center_x, y),  # Home
            (center_x - base_spacing, y - base_spacing),  # First
            (center_x, y - 2 * base_spacing),  # Second
            (center_x + base_spacing, y - base_spacing)  # Third
        ]
        
        # Draw thicker diamond outline
        for i in range(len(diamond_points)):
            start = diamond_points[i]
            end = diamond_points[(i + 1) % len(diamond_points)]
            draw.line([start, end], fill=(255, 255, 255), width=2)  # Added width parameter for thicker lines
        
        # Draw occupied bases with larger circles and outline
        for i, occupied in enumerate(bases_occupied):
            x = diamond_points[i+1][0] - base_size//2
            y = diamond_points[i+1][1] - base_size//2
            
            # Draw base circle with outline
            if occupied:
                # Draw white outline
                draw.ellipse([x-1, y-1, x + base_size+1, y + base_size+1], fill=(255, 255, 255))
                # Draw filled circle
                draw.ellipse([x+1, y+1, x + base_size-1, y + base_size-1], fill=(0, 0, 0))
            else:
                # Draw empty base with outline
                draw.ellipse([x, y, x + base_size, y + base_size], outline=(255, 255, 255), width=1)

    def _create_game_display(self, game_data: Dict[str, Any]) -> Image.Image:
        """Create a display image for an MLB game with team logos, score, and game state."""
        width = self.display_manager.matrix.width
        height = self.display_manager.matrix.height
        image = Image.new('RGB', (width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Set logo size
        logo_size = (24, 24) # Shrink to 24x24
        logo_y_offset = 4    # Move down from top edge
        # center_y = height // 2 # center_y not used for logo placement now
        
        # Load team logos
        away_logo = self._get_team_logo(game_data['away_team'])
        home_logo = self._get_team_logo(game_data['home_team'])
        
        if away_logo and home_logo:
            away_logo = away_logo.resize(logo_size, Image.Resampling.LANCZOS)
            home_logo = home_logo.resize(logo_size, Image.Resampling.LANCZOS)
            
            # Position logos with proper spacing (matching NHL layout)
            # Away logo on left, slightly off screen
            away_x = 0
            away_y = logo_y_offset # Apply offset
            
            # Home logo on right, slightly off screen
            home_x = width - home_logo.width # home_logo.width should be 24 now
            home_y = logo_y_offset # Apply offset
            
            # Paste logos
            image.paste(away_logo, (away_x, away_y), away_logo)
            image.paste(home_logo, (home_x, home_y), home_logo)
        
        # For upcoming games, show date and time stacked in the center
        if game_data['status'] == 'status_scheduled':
            # Show "Next Game" at the top using 5x7 font
            status_text = "Next Game"
            # Set font size for BDF font
            self.display_manager.calendar_font.set_char_size(height=7*64)  # 7 pixels high, 64 units per pixel
            status_width = self.display_manager.get_text_width(status_text, self.display_manager.calendar_font)
            status_x = (width - status_width) // 2
            status_y = 2
            # Draw on the current image
            self.display_manager.draw = draw
            self.display_manager._draw_bdf_text(status_text, status_x, status_y, color=(255, 255, 255), font=self.display_manager.calendar_font)
            # Update the display
            self.display_manager.update_display()
            
            # Format game date and time
            game_time = datetime.fromisoformat(game_data['start_time'].replace('Z', '+00:00'))
            # Get timezone from config
            timezone_str = self.config.get('timezone', 'UTC')
            try:
                tz = pytz.timezone(timezone_str)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Unknown timezone: {timezone_str}, falling back to UTC")
                tz = pytz.UTC
            # Convert to local timezone
            if game_time.tzinfo is None:
                game_time = game_time.replace(tzinfo=pytz.UTC)
            local_time = game_time.astimezone(tz)
            game_date = local_time.strftime("%b %d")  # e.g., "Apr 24"
            game_time_str = self._format_game_time(game_data['start_time'])  # Use the existing method
            
            # Draw date in center using PressStart2P
            date_bbox = draw.textbbox((0, 0), game_date, font=self.display_manager.font)
            date_width = date_bbox[2] - date_bbox[0]
            date_x = (width - date_width) // 2
            date_y = logo_y_offset - 5  # Position in center
            draw.text((date_x, date_y), game_date, fill=(255, 255, 255), font=self.display_manager.font)
            
            # Draw time below date using PressStart2P
            time_bbox = draw.textbbox((0, 0), game_time_str, font=self.display_manager.font)
            time_width = time_bbox[2] - time_bbox[0]
            time_x = (width - time_width) // 2
            time_y = date_y + 10  # Position below date
            draw.text((time_x, time_y), game_time_str, fill=(255, 255, 255), font=self.display_manager.font)
        
        # For recent/final games, show scores and status
        elif game_data['status'] in ['status_final', 'final', 'completed']:
            # Show "Final" at the top using 5x7 font
            status_text = "Final"
            # Set font size for BDF font
            self.display_manager.calendar_font.set_char_size(height=7*64)  # 7 pixels high, 64 units per pixel
            status_width = self.display_manager.get_text_width(status_text, self.display_manager.calendar_font)
            status_x = (width - status_width) // 2
            status_y = 2
            # Draw on the current image
            self.display_manager.draw = draw
            self.display_manager._draw_bdf_text(status_text, status_x, status_y, color=(255, 255, 255), font=self.display_manager.calendar_font)
            # Update the display
            self.display_manager.update_display()
            
            # Draw scores at the bottom (matching NHL layout) using PressStart2P
            away_score = str(game_data['away_score'])
            home_score = str(game_data['home_score'])
            score_text = f"{away_score}-{home_score}"
            
            
            # Calculate position for the score text (centered at the bottom)
            score_bbox = draw.textbbox((0, 0), score_text, font=self.display_manager.font)
            score_width = score_bbox[2] - score_bbox[0]
            score_x = (width - score_width) // 2
            score_y = height - 15  # Position at bottom
            draw.text((score_x, score_y), score_text, fill=(255, 255, 255), font=self.display_manager.font)
        
        return image

    def _format_game_time(self, game_time: str) -> str:
        """Format game time for display."""
        try:
            # Get timezone from config
            timezone_str = self.config.get('timezone', 'UTC')
            try:
                tz = pytz.timezone(timezone_str)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Unknown timezone: {timezone_str}, falling back to UTC")
                tz = pytz.UTC
            
            # Convert game time to local timezone
            dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            local_dt = dt.astimezone(tz)
            
            return local_dt.strftime("%I:%M %p")
        except Exception as e:
            logger.error(f"Error formatting game time: {e}")
            return "TBD"

    def _fetch_mlb_api_data(self) -> Dict[str, Any]:
        """Fetch MLB game data from the ESPN API."""
        try:
            # Check if test mode is enabled
            if self.mlb_config.get('test_mode', False):
                self.logger.info("Using test mode data for MLB")
                return {
                    'test_game_1': {
                        'away_team': 'TB',
                        'home_team': 'TEX',
                        'away_score': 3,
                        'home_score': 2,
                        'status': 'in',
                        'status_state': 'in',
                        'inning': 7,
                        'inning_half': 'bottom',
                        'balls': 2,
                        'strikes': 1,
                        'outs': 1,
                        'bases_occupied': [True, False, True],  # Runner on 1st and 3rd
                        'start_time': datetime.now().isoformat()
                    }
                }
            
            # Get dates for API request
            now = datetime.now(timezone.utc)
            yesterday = now - timedelta(days=1)
            tomorrow = now + timedelta(days=1)
            
            # Format dates for API
            dates = [
                yesterday.strftime("%Y%m%d"),
                now.strftime("%Y%m%d"),
                tomorrow.strftime("%Y%m%d")
            ]
            
            all_games = {}
            
            # Fetch games for each date
            for date in dates:
                # ESPN API endpoint for MLB games with date parameter
                url = f"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={date}"
                
                self.logger.info(f"Fetching MLB games from ESPN API for date: {date}")
                response = self.session.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                for event in data.get('events', []):
                    game_id = event['id']
                    status = event['status']['type']['name'].lower()
                    status_state = event['status']['type']['state'].lower()
                    
                    # Get team information
                    competitors = event['competitions'][0]['competitors']
                    home_team = next(c for c in competitors if c['homeAway'] == 'home')
                    away_team = next(c for c in competitors if c['homeAway'] == 'away')
                    
                    # Get team abbreviations
                    home_abbr = home_team['team']['abbreviation']
                    away_abbr = away_team['team']['abbreviation']
                    
                    # Only log detailed information for favorite teams
                    is_favorite_game = (home_abbr in self.favorite_teams or away_abbr in self.favorite_teams)
                    if is_favorite_game:
                        self.logger.info(f"Found favorite team game: {away_abbr} @ {home_abbr} (Status: {status}, State: {status_state})")
                    
                    # Get game state information
                    if status_state == 'in':
                        # For live games, get detailed state
                        linescore = event['competitions'][0].get('linescores', [{}])[0]
                        inning = linescore.get('value', 1)
                        inning_half = linescore.get('displayValue', '').lower()
                        
                        # Get count and bases from situation
                        situation = event['competitions'][0].get('situation', {})
                        balls = situation.get('balls', 0)
                        strikes = situation.get('strikes', 0)
                        
                        # Get base runners
                        bases_occupied = [
                            situation.get('onFirst', False),
                            situation.get('onSecond', False),
                            situation.get('onThird', False)
                        ]
                    else:
                        # Default values for non-live games
                        inning = 1
                        inning_half = 'top'
                        balls = 0
                        strikes = 0
                        bases_occupied = [False, False, False]
                    
                    all_games[game_id] = {
                        'away_team': away_abbr,
                        'home_team': home_abbr,
                        'away_score': away_team['score'],
                        'home_score': home_team['score'],
                        'status': status,
                        'status_state': status_state,
                        'inning': inning,
                        'inning_half': inning_half,
                        'balls': balls,
                        'strikes': strikes,
                        'bases_occupied': bases_occupied,
                        'start_time': event['date']
                    }
            
            # Only log favorite team games
            favorite_games = [game for game in all_games.values() 
                           if game['home_team'] in self.favorite_teams or 
                              game['away_team'] in self.favorite_teams]
            if favorite_games:
                self.logger.info(f"Found {len(favorite_games)} games for favorite teams: {self.favorite_teams}")
                for game in favorite_games:
                    self.logger.info(f"Favorite team game: {game['away_team']} @ {game['home_team']} (Status: {game['status']}, State: {game['status_state']})")
            
            return all_games
            
        except Exception as e:
            self.logger.error(f"Error fetching MLB data from ESPN API: {e}")
            return {}

class MLBLiveManager(BaseMLBManager):
    """Manager for displaying live MLB games."""
    def __init__(self, config: Dict[str, Any], display_manager):
        super().__init__(config, display_manager)
        self.logger.info("Initialized MLB Live Manager")
        self.live_games = []
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = self.mlb_config.get('live_update_interval', 20)
        self.no_data_interval = 300  # 5 minutes when no live games
        self.last_game_switch = 0  # Track when we last switched games
        self.game_display_duration = self.mlb_config.get('live_game_duration', 30)  # Display each live game for 30 seconds
        self.last_display_update = 0  # Track when we last updated the display
        self.last_log_time = 0
        self.log_interval = 300  # Only log status every 5 minutes
        self.test_mode = self.mlb_config.get('test_mode', False)

        # Initialize with test game only if test mode is enabled
        if self.test_mode:
            self.current_game = {
                "home_team": "TB",
                "away_team": "TEX",
                "home_score": "3",
                "away_score": "2",
                "status": "live",
                "status_state": "live",
                "inning": 5,
                "inning_half": "top",
                "balls": 2,
                "strikes": 1,
                "outs": 1,
                "bases_occupied": [True, False, True],
                "home_logo_path": os.path.join(self.logo_dir, "TB.png"),
                "away_logo_path": os.path.join(self.logo_dir, "TEX.png"),
                "start_time": datetime.now(timezone.utc).isoformat(),
            }
            self.live_games = [self.current_game]
            self.logger.info("Initialized MLBLiveManager with test game: TB vs TEX")
        else:
            self.logger.info("Initialized MLBLiveManager in live mode")

    def update(self):
        """Update live game data."""
        current_time = time.time()
        # Use longer interval if no game data
        interval = self.no_data_interval if not self.live_games else self.update_interval
        
        if current_time - self.last_update >= interval:
            self.last_update = current_time
            
            if self.test_mode:
                # For testing, we'll just update the game state to show it's working
                if self.current_game:
                    # Update inning half
                    if self.current_game["inning_half"] == "top":
                        self.current_game["inning_half"] = "bottom"
                    else:
                        self.current_game["inning_half"] = "top"
                        self.current_game["inning"] += 1
                    
                    # Update count
                    self.current_game["balls"] = (self.current_game["balls"] + 1) % 4
                    self.current_game["strikes"] = (self.current_game["strikes"] + 1) % 3
                    
                    # Update outs
                    self.current_game["outs"] = (self.current_game["outs"] + 1) % 3
                    
                    # Update bases
                    self.current_game["bases_occupied"] = [
                        not self.current_game["bases_occupied"][0],
                        not self.current_game["bases_occupied"][1],
                        not self.current_game["bases_occupied"][2]
                    ]
                    
                    # Update score occasionally
                    if self.current_game["inning"] % 2 == 0:
                        self.current_game["home_score"] = str(int(self.current_game["home_score"]) + 1)
                    else:
                        self.current_game["away_score"] = str(int(self.current_game["away_score"]) + 1)
            else:
                # Fetch live game data from MLB API
                games = self._fetch_mlb_api_data()
                if games:
                    # Find all live games involving favorite teams
                    new_live_games = []
                    for game in games.values():
                        if game['status'] == 'live':
                            if not self.favorite_teams or (
                                game['home_team'] in self.favorite_teams or 
                                game['away_team'] in self.favorite_teams
                            ):
                                new_live_games.append(game)
                    
                    # Only log if there's a change in games or enough time has passed
                    should_log = (
                        current_time - self.last_log_time >= self.log_interval or
                        len(new_live_games) != len(self.live_games) or
                        not self.live_games  # Log if we had no games before
                    )
                    
                    if should_log:
                        if new_live_games:
                            logger.info(f"[MLB] Found {len(new_live_games)} live games")
                            for game in new_live_games:
                                logger.info(f"[MLB] Live game: {game['away_team']} vs {game['home_team']} - {game['inning_half']}{game['inning']}, {game['balls']}-{game['strikes']}")
                        else:
                            logger.info("[MLB] No live games found")
                        self.last_log_time = current_time
                    
                    if new_live_games:
                        # Update the current game with the latest data
                        for new_game in new_live_games:
                            if self.current_game and (
                                (new_game['home_team'] == self.current_game['home_team'] and 
                                 new_game['away_team'] == self.current_game['away_team']) or
                                (new_game['home_team'] == self.current_game['away_team'] and 
                                 new_game['away_team'] == self.current_game['home_team'])
                            ):
                                self.current_game = new_game
                                break
                        
                        # Only update the games list if we have new games
                        if not self.live_games or set(game['away_team'] + game['home_team'] for game in new_live_games) != set(game['away_team'] + game['home_team'] for game in self.live_games):
                            self.live_games = new_live_games
                            # If we don't have a current game or it's not in the new list, start from the beginning
                            if not self.current_game or self.current_game not in self.live_games:
                                self.current_game_index = 0
                                self.current_game = self.live_games[0]
                                self.last_game_switch = current_time
                        
                        # Always update display when we have new data, but limit to once per second
                        if current_time - self.last_display_update >= 1.0:
                            self.display(force_clear=True)
                            self.last_display_update = current_time
                    else:
                        # No live games found
                        self.live_games = []
                        self.current_game = None
            
            # Check if it's time to switch games
            if len(self.live_games) > 1 and (current_time - self.last_game_switch) >= self.game_display_duration:
                self.current_game_index = (self.current_game_index + 1) % len(self.live_games)
                self.current_game = self.live_games[self.current_game_index]
                self.last_game_switch = current_time
                # Force display update when switching games
                self.display(force_clear=True)
                self.last_display_update = current_time

    def _create_live_game_display(self, game_data: Dict[str, Any]) -> Image.Image:
        """Create a display image for a live MLB game."""
        width = self.display_manager.matrix.width
        height = self.display_manager.matrix.height
        image = Image.new('RGB', (width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Set logo size
        logo_size = (24, 24) # Shrink to 24x24
        logo_y_offset = 0    # Move down from top edge
        # center_y = height // 2 # center_y not used for logo placement now
        
        # Load and place team logos (same as base method)
        away_logo = self._get_team_logo(game_data['away_team'])
        home_logo = self._get_team_logo(game_data['home_team'])
        
        if away_logo and home_logo:
            away_logo = away_logo.resize(logo_size, Image.Resampling.LANCZOS)
            home_logo = home_logo.resize(logo_size, Image.Resampling.LANCZOS)
            away_x = 0
            away_y = logo_y_offset # Apply offset
            home_x = width - home_logo.width # home_logo.width should be 24 now
            home_y = logo_y_offset # Apply offset
            image.paste(away_logo, (away_x, away_y), away_logo)
            image.paste(home_logo, (home_x, home_y), home_logo)

        # --- Live Game Specific Elements ---
        
        # Define default text color
        text_color = (255, 255, 255)
        
        # Draw Inning (Top Center)
        inning_half_indicator = "▲" if game_data['inning_half'] == 'top' else "▼"
        inning_text = f"{inning_half_indicator}{game_data['inning']}"
        inning_bbox = draw.textbbox((0, 0), inning_text, font=self.display_manager.font)
        inning_width = inning_bbox[2] - inning_bbox[0]
        inning_x = (width - inning_width) // 2
        inning_y = 2 # Position near top center
        draw.text((inning_x, inning_y), inning_text, fill=(255, 255, 255), font=self.display_manager.font)
        
        # Draw NEW Base Indicators (Compact, below inning)
        base_size = 3
        base_spacing = 2
        bases_occupied = game_data['bases_occupied'] # Should be [bool, bool, bool] for 1st, 2nd, 3rd
        total_bases_width = 3 * base_size + 2 * base_spacing
        base_start_x = inning_x + (inning_width // 2) - (total_bases_width // 2)
        # Use inning_bbox to position below text: inning_bbox[3] is the bottom y-coordinate
        base_y = inning_bbox[3] + 2 # Position 2 pixels below inning text

        for i in range(3):
            x1 = base_start_x + i * (base_size + base_spacing)
            y1 = base_y
            x2 = x1 + base_size
            y2 = y1 + base_size
            if bases_occupied[i]:
                draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 0)) # Yellow fill for occupied
            else:
                draw.rectangle([x1, y1, x2, y2], outline=(100, 100, 100)) # Gray outline for empty

        # Draw Count (Balls-Strikes) using BDF font below bases
        count_text = f"{game_data['balls']}-{game_data['strikes']}"
        bdf_font = self.display_manager.calendar_font
        bdf_font.set_char_size(height=7*64) # Set 7px height
        count_width = self.display_manager.get_text_width(count_text, bdf_font)
        # Center below bases: find center of bases area
        bases_center_x = base_start_x + total_bases_width // 2
        count_x = bases_center_x - count_width // 2
        # Position below bases (base_y is top of bases, add base_size and spacing)
        count_y = base_y + base_size + 2 
        # Ensure display manager has the right draw object before calling _draw_bdf_text
        self.display_manager.draw = draw 
        self.display_manager._draw_bdf_text(count_text, count_x, count_y, text_color, font=bdf_font)
        # Update display (might be redundant if called later, but safe)
        # self.display_manager.update_display() 

        # Draw Team:Score at the bottom
        score_font = self.display_manager.font # Use PressStart2P
        away_abbr = game_data['away_team']
        home_abbr = game_data['home_team']
        away_score_str = str(game_data['away_score'])
        home_score_str = str(game_data['home_score'])

        away_text = f"{away_abbr}:{away_score_str}"
        home_text = f"{home_abbr}:{home_score_str}"
        
        # Calculate Y position (bottom edge)
        # Get font height (approximate or precise)
        try:
            font_height = score_font.getbbox("A")[3] - score_font.getbbox("A")[1]
        except AttributeError:
            font_height = 8 # Fallback for default font
        score_y = height - font_height - 1 # 1 pixel padding from bottom
        
        # Away Team:Score (Bottom Left)
        away_score_x = 2 # 2 pixels padding from left
        draw.text((away_score_x, score_y), away_text, font=score_font, fill=text_color)
        
        # Home Team:Score (Bottom Right)
        home_text_bbox = draw.textbbox((0,0), home_text, font=score_font)
        home_text_width = home_text_bbox[2] - home_text_bbox[0]
        home_score_x = width - home_text_width - 2 # 2 pixels padding from right
        draw.text((home_score_x, score_y), home_text, font=score_font, fill=text_color)

        # TODO: Add Outs display if needed

        return image

    def display(self, force_clear: bool = False):
        """Display live game information."""
        if not self.current_game:
            return
            
        try:
            # Create and display the game image using the new method
            game_image = self._create_live_game_display(self.current_game)
            # Set the image in the display manager
            self.display_manager.image = game_image
            self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
            # Update the display
            self.display_manager.update_display()
        except Exception as e:
            logger.error(f"[MLB] Error displaying live game: {e}", exc_info=True)

class MLBRecentManager(BaseMLBManager):
    """Manager for displaying recent MLB games."""
    def __init__(self, config: Dict[str, Any], display_manager):
        super().__init__(config, display_manager)
        self.logger.info("Initialized MLB Recent Manager")
        self.recent_games = []
        self.current_game = None
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = self.mlb_config.get('recent_update_interval', 3600)
        self.recent_hours = self.mlb_config.get('recent_game_hours', 72)  # Increased from 48 to 72 hours
        self.last_game_switch = 0  # Track when we last switched games
        self.game_display_duration = 10  # Display each game for 10 seconds
        self.last_warning_time = 0
        self.warning_cooldown = 300  # Only show warning every 5 minutes
        logger.info(f"Initialized MLBRecentManager with {len(self.favorite_teams)} favorite teams")

    def update(self):
        """Update recent games data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return
            
        try:
            # Fetch data from MLB API
            games = self._fetch_mlb_api_data()
            if not games:
                logger.warning("[MLB] No games returned from API")
                return
                
            # Process games
            new_recent_games = []
            now = datetime.now(timezone.utc)  # Make timezone-aware
            recent_cutoff = now - timedelta(hours=self.recent_hours)
            
            logger.info(f"[MLB] Time window: {recent_cutoff} to {now}")
            
            for game_id, game in games.items():
                # Convert game time to UTC datetime
                game_time_str = game['start_time'].replace('Z', '+00:00')
                game_time = datetime.fromisoformat(game_time_str)
                if game_time.tzinfo is None:
                    game_time = game_time.replace(tzinfo=timezone.utc)
                
                # Check if this is a favorite team game
                is_favorite_game = (game['home_team'] in self.favorite_teams or 
                                  game['away_team'] in self.favorite_teams)
                
                if is_favorite_game:
                    logger.info(f"[MLB] Checking favorite team game: {game['away_team']} @ {game['home_team']}")
                    logger.info(f"[MLB] Game time (UTC): {game_time}")
                    logger.info(f"[MLB] Game status: {game['status']}, State: {game['status_state']}")
                
                # Use status_state to determine if game is final
                is_final = game['status_state'] in ['post', 'final', 'completed']
                is_within_time = recent_cutoff <= game_time <= now
                
                if is_favorite_game:
                    logger.info(f"[MLB] Is final: {is_final}")
                    logger.info(f"[MLB] Is within time window: {is_within_time}")
                    logger.info(f"[MLB] Time comparison: {recent_cutoff} <= {game_time} <= {now}")
                
                # Only add favorite team games that are final and within time window
                if is_favorite_game and is_final and is_within_time:
                    new_recent_games.append(game)
                    logger.info(f"[MLB] Added favorite team game to recent list: {game['away_team']} @ {game['home_team']}")
            
            if new_recent_games:
                logger.info(f"[MLB] Found {len(new_recent_games)} recent games for favorite teams: {self.favorite_teams}")
                self.recent_games = new_recent_games
                if not self.current_game:
                    self.current_game = self.recent_games[0]
            else:
                logger.info("[MLB] No recent games found for favorite teams")
                self.recent_games = []
                self.current_game = None
            
            self.last_update = current_time
            
        except Exception as e:
            logger.error(f"[MLB] Error updating recent games: {e}", exc_info=True)

    def display(self, force_clear: bool = False):
        """Display recent games."""
        if not self.recent_games:
            current_time = time.time()
            if current_time - self.last_warning_time > self.warning_cooldown:
                logger.info("[MLB] No recent games to display")
                self.last_warning_time = current_time
            return  # Skip display update entirely
            
        try:
            current_time = time.time()
            
            # Check if it's time to switch games
            if current_time - self.last_game_switch >= self.game_display_duration:
                # Move to next game
                self.current_game_index = (self.current_game_index + 1) % len(self.recent_games)
                self.current_game = self.recent_games[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True  # Force clear when switching games
            
            # Create and display the game image
            game_image = self._create_game_display(self.current_game)
            self.display_manager.image = game_image
            self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
            self.display_manager.update_display()
            
        except Exception as e:
            logger.error(f"[MLB] Error displaying recent game: {e}", exc_info=True)

class MLBUpcomingManager(BaseMLBManager):
    """Manager for displaying upcoming MLB games."""
    def __init__(self, config: Dict[str, Any], display_manager):
        super().__init__(config, display_manager)
        self.logger.info("Initialized MLB Upcoming Manager")
        self.upcoming_games = []
        self.current_game = None
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = self.mlb_config.get('upcoming_update_interval', 3600)
        self.last_warning_time = 0
        self.warning_cooldown = 300  # Only show warning every 5 minutes
        self.last_game_switch = 0  # Track when we last switched games
        self.game_display_duration = 10  # Display each game for 10 seconds
        logger.info(f"Initialized MLBUpcomingManager with {len(self.favorite_teams)} favorite teams")

    def update(self):
        """Update upcoming games data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return
            
        try:
            # Fetch data from MLB API
            games = self._fetch_mlb_api_data()
            if games:
                # Process games
                new_upcoming_games = []
                now = datetime.now(timezone.utc)  # Make timezone-aware
                upcoming_cutoff = now + timedelta(hours=24)
                
                logger.info(f"Looking for games between {now} and {upcoming_cutoff}")
                
                for game in games.values():
                    # Check if this is a favorite team game first
                    is_favorite_game = (game['home_team'] in self.favorite_teams or 
                                      game['away_team'] in self.favorite_teams)
                    
                    if not is_favorite_game:
                        continue  # Skip non-favorite team games
                        
                    game_time = datetime.fromisoformat(game['start_time'].replace('Z', '+00:00'))
                    # Ensure game_time is timezone-aware (UTC)
                    if game_time.tzinfo is None:
                        game_time = game_time.replace(tzinfo=timezone.utc)
                    logger.info(f"Checking favorite team game: {game['away_team']} @ {game['home_team']} at {game_time}")
                    logger.info(f"Game status: {game['status']}, State: {game['status_state']}")
                    
                    # Check if game is within our time window
                    is_within_time = now <= game_time <= upcoming_cutoff
                    
                    # For upcoming games, we'll consider any game that:
                    # 1. Is within our time window
                    # 2. Is not final (not 'post' or 'final' state)
                    # 3. Has a future start time
                    is_upcoming = (
                        is_within_time and 
                        game['status_state'] not in ['post', 'final', 'completed'] and
                        game_time > now
                    )
                    
                    logger.info(f"Within time window: {is_within_time}")
                    logger.info(f"Is upcoming: {is_upcoming}")
                    logger.info(f"Game time > now: {game_time > now}")
                    logger.info(f"Status state not final: {game['status_state'] not in ['post', 'final', 'completed']}")
                    
                    if is_upcoming:
                        new_upcoming_games.append(game)
                        logger.info(f"Added favorite team game to upcoming list: {game['away_team']} @ {game['home_team']}")
                
                # Filter for favorite teams (though we already filtered above, this is a safety check)
                new_team_games = [game for game in new_upcoming_games 
                             if game['home_team'] in self.favorite_teams or 
                                game['away_team'] in self.favorite_teams]
                
                if new_team_games:
                    logger.info(f"[MLB] Found {len(new_team_games)} upcoming games for favorite teams")
                    self.upcoming_games = new_team_games
                    if not self.current_game:
                        self.current_game = self.upcoming_games[0]
                else:
                    logger.info("[MLB] No upcoming games found for favorite teams")
                    self.upcoming_games = []
                    self.current_game = None
                
                self.last_update = current_time
                
        except Exception as e:
            logger.error(f"[MLB] Error updating upcoming games: {e}", exc_info=True)

    def display(self, force_clear: bool = False):
        """Display upcoming games."""
        if not self.upcoming_games:
            current_time = time.time()
            if current_time - self.last_warning_time > self.warning_cooldown:
                logger.info("[MLB] No upcoming games to display")
                self.last_warning_time = current_time
            return  # Skip display update entirely
            
        try:
            current_time = time.time()
            
            # Check if it's time to switch games
            if current_time - self.last_game_switch >= self.game_display_duration:
                # Move to next game
                self.current_game_index = (self.current_game_index + 1) % len(self.upcoming_games)
                self.current_game = self.upcoming_games[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True  # Force clear when switching games
            
            # Create and display the game image
            game_image = self._create_game_display(self.current_game)
            self.display_manager.image = game_image
            self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
            self.display_manager.update_display()
            
        except Exception as e:
            logger.error(f"[MLB] Error displaying upcoming game: {e}", exc_info=True) 