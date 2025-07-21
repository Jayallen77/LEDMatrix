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
        self.scroll_position = 0
        self.last_scroll_time = 0
        self.games_data = []
        self.current_game_index = 0
        self.ticker_image = None # This will hold the single, wide image
        self.last_display_time = 0
        
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

    def _fetch_team_record(self, team_abbr: str, league: str) -> str:
        """Fetch team record from ESPN API."""
        # This is a simplified implementation; a more robust solution would cache team data
        try:
            sport = 'baseball' if league == 'mlb' else 'football' if league in ['nfl', 'college-football'] else 'basketball'
            
            # Use a more specific endpoint for college sports
            if league == 'college-football':
                url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_abbr}"
            else:
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams/{team_abbr}"

            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Different path for college sports records
            if league == 'college-football':
                 record_items = data.get('team', {}).get('record', {}).get('items', [])
                 if record_items:
                     return record_items[0].get('summary', 'N/A')
                 else:
                    return 'N/A'
            else:
                record = data.get('team', {}).get('record', {}).get('summary', 'N/A')
                return record

        except Exception as e:
            logger.error(f"Error fetching record for {team_abbr} in league {league}: {e}")
            return "N/A"

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
        
        logger.debug(f"Fetching upcoming games for {len(self.enabled_leagues)} enabled leagues")
        
        for league_key in self.enabled_leagues:
            if league_key not in self.league_configs:
                logger.warning(f"Unknown league: {league_key}")
                continue
                
            league_config = self.league_configs[league_key]
            logger.debug(f"Processing league {league_key}: enabled={league_config['enabled']}")
            
            if not league_config['enabled']:
                logger.debug(f"League {league_key} is disabled, skipping")
                continue
            
            try:
                # Fetch upcoming games for this league
                games = self._fetch_league_games(league_config, now)
                logger.debug(f"Found {len(games)} games for {league_key}")
                games_data.extend(games)
                
            except Exception as e:
                logger.error(f"Error fetching games for {league_key}: {e}")
        
        # Sort games by start time
        games_data.sort(key=lambda x: x.get('start_time', datetime.max))
        
        # Filter for favorite teams if enabled (now handled in _fetch_league_games)
        # This filtering is now redundant since we filter before fetching odds
        if self.show_favorite_teams_only:
            logger.debug("Favorite team filtering already applied during game fetching")
        
        logger.debug(f"Total games found: {len(games_data)}")
        
        # Log details about found games
        if games_data:
            logger.debug("Games found:")
            for i, game in enumerate(games_data):
                odds_status = "Has odds" if game.get('odds') else "No odds"
                logger.debug(f"  {i+1}. {game['away_team']} @ {game['home_team']} - {odds_status}")
        
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
                            
                            # Get records directly from the scoreboard feed
                            home_record = home_team.get('records', [{}])[0].get('summary', '') if home_team.get('records') else ''
                            away_record = away_team.get('records', [{}])[0].get('summary', '') if away_team.get('records') else ''

                            # Check if this game involves favorite teams BEFORE fetching odds
                            if self.show_favorite_teams_only:
                                favorite_teams = league_config.get('favorite_teams', [])
                                if home_abbr not in favorite_teams and away_abbr not in favorite_teams:
                                    logger.debug(f"Skipping game {home_abbr} vs {away_abbr} - no favorite teams involved")
                                    continue
                            
                            logger.debug(f"Found upcoming game: {away_abbr} @ {home_abbr} on {game_time}")
                            
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
                                'logo_dir': league_config['logo_dir'],
                                'home_record': home_record,
                                'away_record': away_record
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

    def _create_game_display(self, game: Dict[str, Any]) -> Image.Image:
        """Create a display image for a game in the new format."""
        width = self.display_manager.matrix.width
        height = self.display_manager.matrix.height
        
        # Create a wider image for scrolling. The width will be determined by the content.
        # Let's start with a placeholder and calculate the actual width.
        
        # --- Pre-calculate widths ---
        logo_size = 24  # Assuming square logos
        logo_padding = 5
        vs_padding = 8
        section_padding = 12

        # Fonts
        team_font = self.fonts['medium']
        odds_font = self.fonts['medium']
        vs_font = self.fonts['medium']
        datetime_font = self.fonts['small'] # Use small font for date/time

        # Get team logos
        home_logo = self._get_team_logo(game['home_team'], game['logo_dir'])
        away_logo = self._get_team_logo(game['away_team'], game['logo_dir'])

        if home_logo:
            home_logo = home_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        if away_logo:
            away_logo = away_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # Create a temporary draw object to measure text
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))

        # "vs." text
        vs_text = "vs."
        vs_width = int(temp_draw.textlength(vs_text, font=vs_font))

        # Format date and time
        game_time = game['start_time']
        timezone_str = self.config.get('timezone', 'UTC')
        try:
            tz = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            tz = pytz.UTC
        
        if game_time.tzinfo is None:
            game_time = game_time.replace(tzinfo=pytz.UTC)
        local_time = game_time.astimezone(tz)
        
        datetime_text = local_time.strftime("%a %-m/%d %-I:%M%p").lower()

        # Team and record text
        away_team_text = f"{game.get('away_team', 'N/A')} ({game.get('away_record', '') or 'N/A'})"
        home_team_text = f"{game.get('home_team', 'N/A')} ({game.get('home_record', '') or 'N/A'})"
        
        away_team_width = int(temp_draw.textlength(away_team_text, font=team_font))
        home_team_width = int(temp_draw.textlength(home_team_text, font=team_font))
        datetime_width = int(temp_draw.textlength(datetime_text, font=datetime_font))
        team_info_width = max(away_team_width, home_team_width, datetime_width)

        # Odds text
        odds = game.get('odds') or {}
        home_team_odds = odds.get('home_team_odds', {})
        away_team_odds = odds.get('away_team_odds', {})
        
        # Determine the favorite and get the spread
        home_spread = home_team_odds.get('spread_odds')
        away_spread = away_team_odds.get('spread_odds')
        
        # Fallback to top-level spread from odds_manager
        top_level_spread = odds.get('spread')
        if top_level_spread is not None:
            if home_spread is None or home_spread == 0.0:
                home_spread = top_level_spread
            if away_spread is None:
                away_spread = -top_level_spread

        # Check for valid spread values before comparing
        home_favored = isinstance(home_spread, (int, float)) and home_spread < 0
        away_favored = isinstance(away_spread, (int, float)) and away_spread < 0

        over_under = odds.get('over_under')
        
        away_odds_text = ""
        home_odds_text = ""
        
        # Simplified odds placement logic
        if home_favored:
            home_odds_text = f"{home_spread}"
            if over_under:
                away_odds_text = f"O/U {over_under}"
        elif away_favored:
            away_odds_text = f"{away_spread}"
            if over_under:
                home_odds_text = f"O/U {over_under}"
        elif over_under:
            home_odds_text = f"O/U {over_under}"
        
        away_odds_width = int(temp_draw.textlength(away_odds_text, font=odds_font))
        home_odds_width = int(temp_draw.textlength(home_odds_text, font=odds_font))
        odds_width = max(away_odds_width, home_odds_width)

        # --- Calculate total width ---
        total_width = (logo_size + logo_padding + vs_width + vs_padding + logo_size + section_padding +
                       team_info_width + section_padding + odds_width + section_padding)

        # --- Create final image ---
        image = Image.new('RGB', (int(total_width), height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # --- Draw elements ---
        current_x = logo_padding

        # Away Logo
        if away_logo:
            y_pos = (height - logo_size) // 2
            image.paste(away_logo, (int(current_x), y_pos), away_logo if away_logo.mode == 'RGBA' else None)
        current_x += logo_size + vs_padding

        # "vs."
        y_pos = (height - vs_font.size) // 2 if hasattr(vs_font, 'size') else (height - 8) // 2 # Added fallback for default font
        draw.text((current_x, y_pos), vs_text, font=vs_font, fill=(255, 255, 255))
        current_x += vs_width + vs_padding

        # Home Logo
        if home_logo:
            y_pos = (height - logo_size) // 2
            image.paste(home_logo, (int(current_x), y_pos), home_logo if home_logo.mode == 'RGBA' else None)
        current_x += logo_size + section_padding

        # Team Info (stacked)
        team_font_height = team_font.size if hasattr(team_font, 'size') else 8
        datetime_font_height = datetime_font.size if hasattr(datetime_font, 'size') else 6
        
        total_text_height = team_font_height + datetime_font_height + team_font_height
        padding_y = (height - total_text_height) // 2 # Center the whole block vertically
        
        away_y = padding_y
        datetime_y = away_y + team_font_height
        home_y = datetime_y + datetime_font_height

        draw.text((current_x, away_y), away_team_text, font=team_font, fill=(255, 255, 255))
        draw.text((current_x, datetime_y), datetime_text, font=datetime_font, fill=(255, 255, 255))
        draw.text((current_x, home_y), home_team_text, font=team_font, fill=(255, 255, 255))
        current_x += team_info_width + section_padding

        # Odds (stacked)
        odds_font_height = odds_font.size if hasattr(odds_font, 'size') else 8
        odds_y_away = 2
        odds_y_home = height - odds_font_height - 2
        
        # Use a consistent color for all odds text
        odds_color = (255, 255, 0) # Yellow

        draw.text((current_x, odds_y_away), away_odds_text, font=odds_font, fill=odds_color)
        draw.text((current_x, odds_y_home), home_odds_text, font=odds_font, fill=odds_color)

        return image

    def _create_ticker_image(self):
        """Create a single wide image containing all game tickers."""
        if not self.games_data:
            self.ticker_image = None
            return

        game_images = [self._create_game_display(game) for game in self.games_data]
        if not game_images:
            self.ticker_image = None
            return

        gap_width = 24  # Reduced gap between games
        total_width = sum(img.width for img in game_images) + gap_width * (len(game_images))
        height = self.display_manager.matrix.height

        self.ticker_image = Image.new('RGB', (total_width, height), color=(0, 0, 0))
        
        current_x = 0
        for img in game_images:
            self.ticker_image.paste(img, (current_x, 0))
            current_x += img.width + gap_width

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
            logger.debug(f"Enabled leagues: {self.enabled_leagues}")
            logger.debug(f"Show favorite teams only: {self.show_favorite_teams_only}")
            
            self.games_data = self._fetch_upcoming_games()
            self.last_update = current_time
            self.scroll_position = 0
            self.current_game_index = 0
            self._create_ticker_image() # Create the composite image
            
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
        
        if self.ticker_image is None:
            logger.warning("Ticker image is not available. Attempting to create it.")
            self._create_ticker_image()
            if self.ticker_image is None:
                logger.error("Failed to create ticker image.")
                self._display_fallback_message()
                return

        try:
            current_time = time.time()
            
            # Scroll the image
            if current_time - self.last_scroll_time >= self.scroll_delay:
                self.scroll_position += self.scroll_speed
                self.last_scroll_time = current_time
            
            # Calculate crop region
            width = self.display_manager.matrix.width
            height = self.display_manager.matrix.height
            
            # Reset position when we've scrolled past the end for a continuous loop
            if self.scroll_position >= self.ticker_image.width:
                self.scroll_position = 0
            
            # Create the visible part of the image by pasting from the ticker_image
            visible_image = Image.new('RGB', (width, height))
            
            # Main part
            visible_image.paste(self.ticker_image, (-self.scroll_position, 0))

            # Handle wrap-around for continuous scroll
            if self.scroll_position + width > self.ticker_image.width:
                wrap_around_width = (self.scroll_position + width) - self.ticker_image.width
                wrap_around_image = self.ticker_image.crop((0, 0, wrap_around_width, height))
                visible_image.paste(wrap_around_image, (self.ticker_image.width - self.scroll_position, 0))
            
            # Display the cropped image
            self.display_manager.image = visible_image
            self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
            self.display_manager.update_display()
            
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