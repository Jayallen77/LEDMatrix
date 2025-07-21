import time
import logging
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import os
from PIL import Image, ImageDraw, ImageFont
import pytz
from src.display_manager import DisplayManager
from src.cache_manager import CacheManager
from src.config_manager import ConfigManager
from src.odds_manager import OddsManager

# Get logger
logger = logging.getLogger(__name__)

class OddsTickerManager:
    """Manager for displaying scrolling odds ticker for multiple sports leagues."""
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        self.config = config
        self.display_manager = display_manager
        self.odds_ticker_config = config.get('odds_ticker', {})
        self.is_enabled = self.odds_ticker_config.get('enabled', False)
        self.show_favorite_teams_only = self.odds_ticker_config.get('show_favorite_teams_only', False)
        self.enabled_leagues = self.odds_ticker_config.get('enabled_leagues', ['nfl', 'nba', 'mlb'])
        self.update_interval = self.odds_ticker_config.get('update_interval', 3600)
        self.scroll_speed = self.odds_ticker_config.get('scroll_speed', 2)
        self.scroll_delay = self.odds_ticker_config.get('scroll_delay', 0.05)
        self.display_duration = self.odds_ticker_config.get('display_duration', 30)
        
        # Initialize managers
        self.cache_manager = CacheManager()
        self.odds_manager = OddsManager(self.cache_manager, ConfigManager())
        
        # State variables
        self.last_update = 0
        self.current_position = 0
        self.last_scroll_time = 0
        self.games_data = []
        self.current_game_index = 0
        self.current_image = None
        
        # Font setup
        self.fonts = self._load_fonts()
        
        # League configurations
        self.league_configs = {
            'nfl': {
                'sport': 'football',
                'league': 'nfl',
                'logo_dir': 'assets/sports/nfl_logos',
                'favorite_teams': config.get('nfl_scoreboard', {}).get('favorite_teams', []),
                'enabled': config.get('nfl_scoreboard', {}).get('enabled', False)
            },
            'nba': {
                'sport': 'basketball',
                'league': 'nba',
                'logo_dir': 'assets/sports/nba_logos',
                'favorite_teams': config.get('nba_scoreboard', {}).get('favorite_teams', []),
                'enabled': config.get('nba_scoreboard', {}).get('enabled', False)
            },
            'mlb': {
                'sport': 'baseball',
                'league': 'mlb',
                'logo_dir': 'assets/sports/mlb_logos',
                'favorite_teams': config.get('mlb', {}).get('favorite_teams', []),
                'enabled': config.get('mlb', {}).get('enabled', False)
            },
            'ncaa_fb': {
                'sport': 'football',
                'league': 'college-football',
                'logo_dir': 'assets/sports/ncaa_fbs_logos',
                'favorite_teams': config.get('ncaa_fb_scoreboard', {}).get('favorite_teams', []),
                'enabled': config.get('ncaa_fb_scoreboard', {}).get('enabled', False)
            }
        }
        
        logger.info(f"OddsTickerManager initialized with enabled leagues: {self.enabled_leagues}")
        logger.info(f"Show favorite teams only: {self.show_favorite_teams_only}")

    def _load_fonts(self) -> Dict[str, ImageFont.FreeTypeFont]:
        """Load fonts for the ticker display."""
        try:
            return {
                'small': ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 6),
                'medium': ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8),
                'large': ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10)
            }
        except Exception as e:
            logger.error(f"Error loading fonts: {e}")
            return {
                'small': ImageFont.load_default(),
                'medium': ImageFont.load_default(),
                'large': ImageFont.load_default()
            }

    def _get_team_logo(self, team_abbr: str, logo_dir: str) -> Optional[Image.Image]:
        """Get team logo from the configured directory."""
        try:
            logo_path = os.path.join(logo_dir, f"{team_abbr}.png")
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                return logo
            else:
                logger.debug(f"Logo not found: {logo_path}")
                return None
        except Exception as e:
            logger.error(f"Error loading logo for {team_abbr}: {e}")
            return None

    def _fetch_upcoming_games(self) -> List[Dict[str, Any]]:
        """Fetch upcoming games with odds for all enabled leagues."""
        games_data = []
        now = datetime.now(timezone.utc)
        
        logger.info(f"Fetching upcoming games for {len(self.enabled_leagues)} enabled leagues")
        
        for league_key in self.enabled_leagues:
            if league_key not in self.league_configs:
                logger.warning(f"Unknown league: {league_key}")
                continue
                
            league_config = self.league_configs[league_key]
            logger.info(f"Processing league {league_key}: enabled={league_config['enabled']}")
            
            if not league_config['enabled']:
                logger.debug(f"League {league_key} is disabled, skipping")
                continue
            
            try:
                # Fetch upcoming games for this league
                games = self._fetch_league_games(league_config, now)
                logger.info(f"Found {len(games)} games for {league_key}")
                games_data.extend(games)
                
            except Exception as e:
                logger.error(f"Error fetching games for {league_key}: {e}")
        
        # Sort games by start time
        games_data.sort(key=lambda x: x.get('start_time', datetime.max))
        
        # Filter for favorite teams if enabled (now handled in _fetch_league_games)
        # This filtering is now redundant since we filter before fetching odds
        if self.show_favorite_teams_only:
            logger.debug("Favorite team filtering already applied during game fetching")
        
        logger.info(f"Total games found: {len(games_data)}")
        
        # Log details about found games
        if games_data:
            logger.info("Games found:")
            for i, game in enumerate(games_data):
                odds_status = "Has odds" if game.get('odds') else "No odds"
                logger.info(f"  {i+1}. {game['away_team']} @ {game['home_team']} - {odds_status}")
        
        return games_data

    def _fetch_league_games(self, league_config: Dict[str, Any], now: datetime) -> List[Dict[str, Any]]:
        """Fetch upcoming games for a specific league."""
        games = []
        
        # Get dates for API request (yesterday, today, tomorrow - same as MLB manager)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        dates = [
            yesterday.strftime("%Y%m%d"),
            now.strftime("%Y%m%d"),
            tomorrow.strftime("%Y%m%d")
        ]
        
        for date in dates:
            try:
                # ESPN API endpoint for games with date parameter
                sport = league_config['sport']
                league = league_config['league']
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={date}"
                
                logger.debug(f"Fetching {league} games from ESPN API for date: {date}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                for event in data.get('events', []):
                    game_id = event['id']
                    status = event['status']['type']['name'].lower()
                    logger.debug(f"Event {game_id}: status={status}")
                    
                    # Only include upcoming games (handle both 'scheduled' and 'status_scheduled')
                    if status in ['scheduled', 'pre-game', 'status_scheduled']:
                        game_time = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                        
                        # Only include games in the next 3 days (same as MLB manager)
                        if now <= game_time <= now + timedelta(days=3):
                            # Get team information
                            competitors = event['competitions'][0]['competitors']
                            home_team = next(c for c in competitors if c['homeAway'] == 'home')
                            away_team = next(c for c in competitors if c['homeAway'] == 'away')
                            
                            home_abbr = home_team['team']['abbreviation']
                            away_abbr = away_team['team']['abbreviation']
                            
                            # Check if this game involves favorite teams BEFORE fetching odds
                            if self.show_favorite_teams_only:
                                favorite_teams = league_config.get('favorite_teams', [])
                                if home_abbr not in favorite_teams and away_abbr not in favorite_teams:
                                    logger.debug(f"Skipping game {home_abbr} vs {away_abbr} - no favorite teams involved")
                                    continue
                            
                            logger.info(f"Found upcoming game: {away_abbr} @ {home_abbr} on {game_time}")
                            
                            # Fetch odds for this game (only if it involves favorite teams)
                            odds_data = self.odds_manager.get_odds(
                                sport=sport,
                                league=league,
                                event_id=game_id,
                                update_interval_seconds=7200  # Cache for 2 hours instead of 1 hour
                            )
                            
                            # Check if odds data has actual values (similar to MLB manager)
                            has_odds = False
                            if odds_data and not odds_data.get('no_odds'):
                                # Check if the odds data has any non-null values
                                if odds_data.get('spread') is not None:
                                    has_odds = True
                                if odds_data.get('home_team_odds', {}).get('spread_odds') is not None:
                                    has_odds = True
                                if odds_data.get('away_team_odds', {}).get('spread_odds') is not None:
                                    has_odds = True
                                if odds_data.get('over_under') is not None:
                                    has_odds = True
                            
                            if not has_odds:
                                logger.debug(f"Game {game_id} has no valid odds data, setting odds to None")
                                odds_data = None
                            
                            game_data = {
                                'id': game_id,
                                'league': league_config['league'],
                                'league_key': league_config['sport'],
                                'home_team': home_abbr,
                                'away_team': away_abbr,
                                'start_time': game_time,
                                'odds': odds_data,
                                'logo_dir': league_config['logo_dir']
                            }
                            
                            games.append(game_data)
                        else:
                            logger.debug(f"Game {game_id} is outside 3-day window: {game_time}")
                    else:
                        logger.debug(f"Game {game_id} has status '{status}', skipping")
                
            except Exception as e:
                logger.error(f"Error fetching {league_config['league']} games for date {date}: {e}")
        
        return games

    def _format_odds_text(self, game: Dict[str, Any]) -> str:
        """Format the odds text for display."""
        odds = game.get('odds', {})
        if not odds:
            # Show just the game info without odds
            game_time = game['start_time']
            timezone_str = self.config.get('timezone', 'UTC')
            try:
                tz = pytz.timezone(timezone_str)
            except pytz.exceptions.UnknownTimeZoneError:
                tz = pytz.UTC
            
            if game_time.tzinfo is None:
                game_time = game_time.replace(tzinfo=pytz.UTC)
            local_time = game_time.astimezone(tz)
            time_str = local_time.strftime("%I:%M %p")
            
            return f"[{time_str}] {game['away_team']} vs {game['home_team']} (No odds)"
        
        # Extract odds data
        home_team_odds = odds.get('home_team_odds', {})
        away_team_odds = odds.get('away_team_odds', {})
        
        home_spread = home_team_odds.get('spread_odds')
        away_spread = away_team_odds.get('spread_odds')
        home_ml = home_team_odds.get('money_line')
        away_ml = away_team_odds.get('money_line')
        over_under = odds.get('over_under')
        
        # Format time
        game_time = game['start_time']
        timezone_str = self.config.get('timezone', 'UTC')
        try:
            tz = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            tz = pytz.UTC
        
        if game_time.tzinfo is None:
            game_time = game_time.replace(tzinfo=pytz.UTC)
        local_time = game_time.astimezone(tz)
        time_str = local_time.strftime("%I:%M %p")
        
        # Build odds string
        odds_parts = [f"[{time_str}]"]
        
        # Add away team and odds
        odds_parts.append(game['away_team'])
        if away_spread is not None:
            spread_str = f"{away_spread:+.1f}" if away_spread > 0 else f"{away_spread:.1f}"
            odds_parts.append(spread_str)
        if away_ml is not None:
            ml_str = f"ML {away_ml:+d}" if away_ml > 0 else f"ML {away_ml}"
            odds_parts.append(ml_str)
        
        odds_parts.append("vs")
        
        # Add home team and odds
        odds_parts.append(game['home_team'])
        if home_spread is not None:
            spread_str = f"{home_spread:+.1f}" if home_spread > 0 else f"{home_spread:.1f}"
            odds_parts.append(spread_str)
        if home_ml is not None:
            ml_str = f"ML {home_ml:+d}" if home_ml > 0 else f"ML {home_ml}"
            odds_parts.append(ml_str)
        
        # Add over/under
        if over_under is not None:
            odds_parts.append(f"O/U {over_under}")
        
        return " ".join(odds_parts)

    def _create_ticker_image(self, game: Dict[str, Any]) -> Image.Image:
        """Create a scrolling ticker image for a game."""
        width = self.display_manager.matrix.width
        height = self.display_manager.matrix.height
        
        logger.info(f"Creating ticker image for {width}x{height} display")
        
        # Create a wider image for scrolling
        scroll_width = width * 3  # 3x width for smooth scrolling
        image = Image.new('RGB', (scroll_width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Format the odds text
        odds_text = self._format_odds_text(game)
        logger.info(f"Formatted odds text: '{odds_text}'")
        
        # Load team logos
        home_logo = self._get_team_logo(game['home_team'], game['logo_dir'])
        away_logo = self._get_team_logo(game['away_team'], game['logo_dir'])
        
        # Calculate text position (start off-screen to the right)
        text_width = draw.textlength(odds_text, font=self.fonts['medium'])
        text_x = scroll_width - text_width - 10  # Start off-screen right
        text_y = (height - self.fonts['medium'].size) // 2
        
        logger.info(f"Drawing text at position ({text_x}, {text_y})")
        
        # Draw the text
        self._draw_text_with_outline(draw, odds_text, (text_x, text_y), self.fonts['medium'])
        
        # Add team logos if available
        logo_size = 16
        logo_y = (height - logo_size) // 2
        
        if away_logo:
            away_logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
            away_x = int(text_x - logo_size - 5)
            image.paste(away_logo, (away_x, logo_y), away_logo)
            logger.info(f"Added away team logo at ({away_x}, {logo_y})")
        
        if home_logo:
            home_logo.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
            home_x = int(text_x + text_width + 5)
            image.paste(home_logo, (home_x, logo_y), home_logo)
            logger.info(f"Added home team logo at ({home_x}, {logo_y})")
        
        logger.info(f"Created ticker image with size {image.size}")
        return image

    def _draw_text_with_outline(self, draw: ImageDraw.Draw, text: str, position: tuple, font: ImageFont.FreeTypeFont, 
                               fill: tuple = (255, 255, 255), outline_color: tuple = (0, 0, 0)) -> None:
        """Draw text with a black outline for better readability."""
        x, y = position
        # Draw outline
        for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
        # Draw main text
        draw.text((x, y), text, font=font, fill=fill)

    def update(self):
        """Update odds ticker data."""
        if not self.is_enabled:
            logger.debug("Odds ticker is disabled, skipping update")
            return
            
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            logger.debug(f"Odds ticker update interval not reached. Next update in {self.update_interval - (current_time - self.last_update)} seconds")
            return
        
        try:
            logger.info("Updating odds ticker data")
            logger.info(f"Enabled leagues: {self.enabled_leagues}")
            logger.info(f"Show favorite teams only: {self.show_favorite_teams_only}")
            
            self.games_data = self._fetch_upcoming_games()
            self.last_update = current_time
            self.current_position = 0
            self.current_game_index = 0
            
            if self.games_data:
                logger.info(f"Updated odds ticker with {len(self.games_data)} games")
                for i, game in enumerate(self.games_data[:3]):  # Log first 3 games
                    logger.info(f"Game {i+1}: {game['away_team']} @ {game['home_team']} - {game['start_time']}")
            else:
                logger.warning("No games found for odds ticker")
                logger.info("This could be due to:")
                logger.info("- No upcoming games in the next 7 days")
                logger.info("- No favorite teams have upcoming games (if show_favorite_teams_only is True)")
                logger.info("- API is not returning data")
                logger.info("- Leagues are disabled in config")
                
        except Exception as e:
            logger.error(f"Error updating odds ticker: {e}", exc_info=True)

    def display(self, force_clear: bool = False):
        """Display the odds ticker."""
        if not self.is_enabled:
            logger.debug("Odds ticker is disabled")
            return
        
        if not self.games_data:
            logger.warning("Odds ticker has no games data. Attempting to update...")
            self.update()
            if not self.games_data:
                logger.warning("Still no games data after update. Displaying fallback message.")
                self._display_fallback_message()
                return
        
        try:
            current_time = time.time()
            
            # Check if it's time to switch games
            if current_time - self.last_update >= self.display_duration:
                self.current_game_index = (self.current_game_index + 1) % len(self.games_data)
                self.current_position = 0
                self.last_update = current_time
                force_clear = True
            
            # Get current game
            current_game = self.games_data[self.current_game_index]
            logger.info(f"Displaying game: {current_game['away_team']} @ {current_game['home_team']}")
            
            # Create ticker image if needed
            if force_clear or self.current_image is None:
                logger.info("Creating new ticker image")
                self.current_image = self._create_ticker_image(current_game)
                logger.info(f"Created ticker image with size: {self.current_image.size}")
            
            # Scroll the image
            if current_time - self.last_scroll_time >= self.scroll_delay:
                self.current_position += self.scroll_speed
                self.last_scroll_time = current_time
            
            # Calculate crop region
            width = self.display_manager.matrix.width
            height = self.display_manager.matrix.height
            
            # Reset position when we've scrolled past the end
            if self.current_position >= self.current_image.width - width:
                self.current_position = 0
            
            # Crop the scrolling region
            crop_x = self.current_position
            crop_y = 0
            crop_width = width
            crop_height = height
            
            # Ensure we don't go out of bounds
            if crop_x + crop_width > self.current_image.width:
                crop_x = self.current_image.width - crop_width
            
            logger.info(f"Cropping image at position ({crop_x}, {crop_y}) with size ({crop_width}, {crop_height})")
            cropped_image = self.current_image.crop((crop_x, crop_y, crop_x + crop_width, crop_y + crop_height))
            logger.info(f"Cropped image size: {cropped_image.size}")
            
            # Display the cropped image
            self.display_manager.image = cropped_image
            self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
            logger.info("Calling display_manager.update_display()")
            self.display_manager.update_display()
            logger.info("Display update completed")
            
        except Exception as e:
            logger.error(f"Error displaying odds ticker: {e}", exc_info=True)
            self._display_fallback_message()

    def _display_fallback_message(self):
        """Display a fallback message when no games data is available."""
        try:
            width = self.display_manager.matrix.width
            height = self.display_manager.matrix.height
            
            logger.info(f"Displaying fallback message on {width}x{height} display")
            
            # Create a simple fallback image with a brighter background
            image = Image.new('RGB', (width, height), color=(50, 50, 50))  # Dark gray instead of black
            draw = ImageDraw.Draw(image)
            
            # Draw a simple message with larger font
            message = "No odds data"
            font = self.fonts['large']  # Use large font for better visibility
            text_width = draw.textlength(message, font=font)
            text_x = (width - text_width) // 2
            text_y = (height - font.size) // 2
            
            logger.info(f"Drawing fallback message: '{message}' at position ({text_x}, {text_y})")
            
            # Draw with bright white text and black outline
            self._draw_text_with_outline(draw, message, (text_x, text_y), font, fill=(255, 255, 255), outline_color=(0, 0, 0))
            
            # Display the fallback image
            self.display_manager.image = image
            self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
            self.display_manager.update_display()
            
            logger.info("Fallback message display completed")
            
        except Exception as e:
            logger.error(f"Error displaying fallback message: {e}", exc_info=True) 