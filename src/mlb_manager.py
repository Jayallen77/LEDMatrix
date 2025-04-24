import time
import logging
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from .cache_manager import CacheManager
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
        base_size = 4
        base_spacing = 6
        
        # Draw diamond outline
        diamond_points = [
            (center_x, y),  # Home
            (center_x - base_spacing, y - base_spacing),  # First
            (center_x, y - 2 * base_spacing),  # Second
            (center_x + base_spacing, y - base_spacing)  # Third
        ]
        draw.polygon(diamond_points, outline=(255, 255, 255))
        
        # Draw occupied bases
        for i, occupied in enumerate(bases_occupied):
            if occupied:
                x = diamond_points[i+1][0] - base_size//2
                y = diamond_points[i+1][1] - base_size//2
                draw.ellipse([x, y, x + base_size, y + base_size], fill=(255, 255, 255))

    def _create_game_display(self, game_data: Dict[str, Any]) -> Image.Image:
        """Create a display image for an MLB game with team logos, score, and game state."""
        width = self.display_manager.matrix.width
        height = self.display_manager.matrix.height
        image = Image.new('RGB', (width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Load team logos
        away_logo = self._get_team_logo(game_data['away_team'])
        home_logo = self._get_team_logo(game_data['home_team'])
        
        # Logo size and positioning
        logo_size = (16, 16)
        if away_logo and home_logo:
            away_logo = away_logo.resize(logo_size, Image.Resampling.LANCZOS)
            home_logo = home_logo.resize(logo_size, Image.Resampling.LANCZOS)
            
            # Position logos on left and right sides
            image.paste(away_logo, (2, height//2 - logo_size[1]//2), away_logo)
            image.paste(home_logo, (width - logo_size[0] - 2, height//2 - logo_size[1]//2), home_logo)
        
        # Draw scores
        score_y = height//2 - 4
        away_score = str(game_data['away_score'])
        home_score = str(game_data['home_score'])
        
        # Use small font for scores
        draw.text((20, score_y), away_score, fill=(255, 255, 255), font=self.display_manager.small_font)
        draw.text((width - 20 - len(home_score)*4, score_y), home_score, fill=(255, 255, 255), font=self.display_manager.small_font)
        
        # Draw game status
        if game_data['status'] == 'live':
            # Draw inning indicator at top
            inning = game_data['inning']
            inning_half = '▲' if game_data['inning_half'] == 'top' else '▼'
            inning_text = f"{inning_half}{inning}"
            
            # Center the inning text
            inning_bbox = draw.textbbox((0, 0), inning_text, font=self.display_manager.small_font)
            inning_width = inning_bbox[2] - inning_bbox[0]
            inning_x = (width - inning_width) // 2
            draw.text((inning_x, 2), inning_text, fill=(255, 255, 255), font=self.display_manager.small_font)
            
            # Draw base indicators
            self._draw_base_indicators(draw, game_data['bases_occupied'], width//2, 12)
            
            # Draw count (balls-strikes) at bottom
            count_text = f"{game_data['balls']}-{game_data['strikes']}"
            count_bbox = draw.textbbox((0, 0), count_text, font=self.display_manager.small_font)
            count_width = count_bbox[2] - count_bbox[0]
            count_x = (width - count_width) // 2
            draw.text((count_x, height - 10), count_text, fill=(255, 255, 255), font=self.display_manager.small_font)
        else:
            # Show game time for upcoming games or "Final" for completed games
            status_text = "Final" if game_data['status'] == 'final' else self._format_game_time(game_data['start_time'])
            status_bbox = draw.textbbox((0, 0), status_text, font=self.display_manager.small_font)
            status_width = status_bbox[2] - status_bbox[0]
            status_x = (width - status_width) // 2
            draw.text((status_x, 2), status_text, fill=(255, 255, 255), font=self.display_manager.small_font)
        
        return image

    def _format_game_time(self, game_time: str) -> str:
        """Format game time for display."""
        try:
            dt = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
            return dt.strftime("%I:%M %p")
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
                        'inning': 7,
                        'inning_half': 'bottom',
                        'balls': 2,
                        'strikes': 1,
                        'bases_occupied': [True, False, True],  # Runner on 1st and 3rd
                        'start_time': datetime.now().isoformat()
                    }
                }
            
            # ESPN API endpoint for MLB games
            url = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
            
            # Try to get cached data first
            cache_key = f"mlb_games_{datetime.now().strftime('%Y%m%d')}"
            cached_data = self.cache_manager.get_cached_data(cache_key)
            
            if cached_data:
                self.logger.info("Using cached MLB game data")
                return cached_data
            
            self.logger.info("Fetching MLB games from ESPN API")
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            games = {}
            
            for event in data.get('events', []):
                game_id = event['id']
                status = event['status']['type']['name'].lower()
                
                # Get team information
                competitors = event['competitions'][0]['competitors']
                home_team = next(c for c in competitors if c['homeAway'] == 'home')
                away_team = next(c for c in competitors if c['homeAway'] == 'away')
                
                # Get game state information
                if status == 'in':
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
                
                games[game_id] = {
                    'away_team': away_team['team']['abbreviation'],
                    'home_team': home_team['team']['abbreviation'],
                    'away_score': away_team['score'],
                    'home_score': home_team['score'],
                    'status': status,
                    'inning': inning,
                    'inning_half': inning_half,
                    'balls': balls,
                    'strikes': strikes,
                    'bases_occupied': bases_occupied,
                    'start_time': event['date']
                }
            
            # Cache the results with different expiration times based on game status
            cache_duration = 300  # 5 minutes for live games
            if not any(game['status'] == 'in' for game in games.values()):
                cache_duration = 3600  # 1 hour for non-live games
            
            self.cache_manager.save_cache(cache_key, games)
            return games
            
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
                "inning": 5,
                "inning_half": "top",
                "balls": 2,
                "strikes": 1,
                "outs": 1,
                "bases_occupied": [True, False, True],  # 1st and 3rd base occupied
                "home_logo_path": os.path.join(self.logo_dir, "TB.png"),
                "away_logo_path": os.path.join(self.logo_dir, "TEX.png"),
                "game_time": "7:30 PM",
                "game_date": "Apr 17",
                "status": "live"
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

    def display(self, force_clear: bool = False):
        """Display live game information."""
        if not self.current_game:
            return
            
        try:
            # Create and display the game image
            game_image = self._create_game_display(self.current_game)
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
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = self.mlb_config.get('recent_update_interval', 3600)
        self.recent_hours = self.mlb_config.get('recent_game_hours', 48)
        self.last_game_switch = 0
        self.game_display_duration = 20  # Display each game for 20 seconds
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
            if games:
                # Process games
                new_recent_games = []
                now = datetime.now()
                recent_cutoff = now - timedelta(hours=self.recent_hours)
                
                for game in games.values():
                    game_time = datetime.fromisoformat(game['start_time'].replace('Z', '+00:00'))
                    if game['status'] == 'final' and game_time >= recent_cutoff:
                        new_recent_games.append(game)
                
                # Filter for favorite teams
                new_team_games = [game for game in new_recent_games 
                             if game['home_team'] in self.favorite_teams or 
                                game['away_team'] in self.favorite_teams]
                
                if new_team_games:
                    logger.info(f"[MLB] Found {len(new_team_games)} recent games for favorite teams")
                    self.recent_games = new_team_games
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
            image_array = np.array(game_image)
            self.display_manager.update_display(image_array)
            
        except Exception as e:
            logger.error(f"[MLB] Error displaying recent game: {e}", exc_info=True)

class MLBUpcomingManager(BaseMLBManager):
    """Manager for displaying upcoming MLB games."""
    def __init__(self, config: Dict[str, Any], display_manager):
        super().__init__(config, display_manager)
        self.logger.info("Initialized MLB Upcoming Manager")
        self.upcoming_games = []
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = self.mlb_config.get('upcoming_update_interval', 3600)
        self.last_warning_time = 0
        self.warning_cooldown = 300  # Only show warning every 5 minutes
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
                now = datetime.now()
                upcoming_cutoff = now + timedelta(hours=24)
                
                for game in games.values():
                    game_time = datetime.fromisoformat(game['start_time'].replace('Z', '+00:00'))
                    if game['status'] == 'preview' and game_time <= upcoming_cutoff:
                        new_upcoming_games.append(game)
                
                # Filter for favorite teams
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
            # Create and display the game image
            game_image = self._create_game_display(self.current_game)
            image_array = np.array(game_image)
            self.display_manager.update_display(image_array)
            
            # Move to next game
            self.current_game_index = (self.current_game_index + 1) % len(self.upcoming_games)
            self.current_game = self.upcoming_games[self.current_game_index]
            
        except Exception as e:
            logger.error(f"[MLB] Error displaying upcoming game: {e}", exc_info=True) 