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
        self.games_per_favorite_team = self.odds_ticker_config.get('games_per_favorite_team', 1)
        self.max_games_per_league = self.odds_ticker_config.get('max_games_per_league', 5)
        self.show_odds_only = self.odds_ticker_config.get('show_odds_only', False)
        self.sort_order = self.odds_ticker_config.get('sort_order', 'soonest')
        self.enabled_leagues = self.odds_ticker_config.get('enabled_leagues', ['nfl', 'nba', 'mlb'])
        self.update_interval = self.odds_ticker_config.get('update_interval', 3600)
        self.scroll_speed = self.odds_ticker_config.get('scroll_speed', 2)
        self.scroll_delay = self.odds_ticker_config.get('scroll_delay', 0.05)
        self.display_duration = self.odds_ticker_config.get('display_duration', 30)
        self.future_fetch_days = self.odds_ticker_config.get('future_fetch_days', 7)
        self.loop = self.odds_ticker_config.get('loop', True)
        
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
        """Fetch upcoming games with odds for all enabled leagues, with user-defined granularity."""
        games_data = []
        now = datetime.now(timezone.utc)
        
        logger.debug(f"Fetching upcoming games for {len(self.enabled_leagues)} enabled leagues")
        
        for league_key in self.enabled_leagues:
            if league_key not in self.league_configs:
                logger.warning(f"Unknown league: {league_key}")
                continue
                
            league_config = self.league_configs[league_key]
            logger.debug(f"Processing league {league_key}: enabled={league_config['enabled']}")
            
            try:
                # Fetch all upcoming games for this league
                all_games = self._fetch_league_games(league_config, now)
                logger.debug(f"Found {len(all_games)} games for {league_key}")
                league_games = []
                
                if self.show_favorite_teams_only:
                    # For each favorite team, find their next N games
                    favorite_teams = league_config.get('favorite_teams', [])
                    seen_game_ids = set()
                    for team in favorite_teams:
                        # Find games where this team is home or away
                        team_games = [g for g in all_games if (g['home_team'] == team or g['away_team'] == team)]
                        # Sort by start_time
                        team_games.sort(key=lambda x: x.get('start_time', datetime.max))
                        # Only keep games with odds if show_odds_only is set
                        if self.show_odds_only:
                            team_games = [g for g in team_games if g.get('odds')]
                        # Take the next N games for this team
                        for g in team_games[:self.games_per_favorite_team]:
                            if g['id'] not in seen_game_ids:
                                league_games.append(g)
                                seen_game_ids.add(g['id'])
                    # Cap at max_games_per_league
                    league_games = league_games[:self.max_games_per_league]
                else:
                    # Show all games, optionally only those with odds
                    league_games = all_games
                    if self.show_odds_only:
                        league_games = [g for g in league_games if g.get('odds')]
                    # Sort by start_time
                    league_games.sort(key=lambda x: x.get('start_time', datetime.max))
                    league_games = league_games[:self.max_games_per_league]
                
                # Sorting (default is soonest)
                if self.sort_order == 'soonest':
                    league_games.sort(key=lambda x: x.get('start_time', datetime.max))
                # (Other sort options can be added here)
                
                games_data.extend(league_games)
                
            except Exception as e:
                logger.error(f"Error fetching games for {league_key}: {e}")
        
        logger.debug(f"Total games found: {len(games_data)}")
        return games_data

    def _fetch_league_games(self, league_config: Dict[str, Any], now: datetime) -> List[Dict[str, Any]]:
        """Fetch upcoming games for a specific league."""
        games = []
        yesterday = now - timedelta(days=1)
        future_window = now + timedelta(days=self.future_fetch_days)
        num_days = (future_window - yesterday).days + 1
        dates = [(yesterday + timedelta(days=i)).strftime("%Y%m%d") for i in range(num_days)]

        # Optimization: If showing favorite teams only, track games found per team
        favorite_teams = league_config.get('favorite_teams', []) if self.show_favorite_teams_only else []
        team_games_found = {team: 0 for team in favorite_teams}
        max_games = self.games_per_favorite_team if self.show_favorite_teams_only else None
        all_games = []
        
        # Optimization: Track total games found when not showing favorite teams only
        games_found = 0
        max_games_per_league = self.max_games_per_league if not self.show_favorite_teams_only else None

        for date in dates:
            # Stop if we have enough games for favorite teams
            if self.show_favorite_teams_only and all(team_games_found[t] >= max_games for t in favorite_teams):
                break  # All favorite teams have enough games, stop searching
            # Stop if we have enough games for the league (when not showing favorite teams only)
            if not self.show_favorite_teams_only and max_games_per_league and games_found >= max_games_per_league:
                break  # We have enough games for this league, stop searching
            try:
                sport = league_config['sport']
                league = league_config['league']
                url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={date}"
                logger.debug(f"Fetching {league} games from ESPN API for date: {date}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                for event in data.get('events', []):
                    # Stop if we have enough games for the league (when not showing favorite teams only)
                    if not self.show_favorite_teams_only and max_games_per_league and games_found >= max_games_per_league:
                        break
                    game_id = event['id']
                    status = event['status']['type']['name'].lower()
                    if status in ['scheduled', 'pre-game', 'status_scheduled']:
                        game_time = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                        if now <= game_time <= future_window:
                            competitors = event['competitions'][0]['competitors']
                            home_team = next(c for c in competitors if c['homeAway'] == 'home')
                            away_team = next(c for c in competitors if c['homeAway'] == 'away')
                            home_abbr = home_team['team']['abbreviation']
                            away_abbr = away_team['team']['abbreviation']
                            # Only process favorite teams if enabled
                            if self.show_favorite_teams_only:
                                # Skip if both teams have already met their quota
                                for team in [home_abbr, away_abbr]:
                                    if team in team_games_found and team_games_found[team] >= max_games:
                                        continue
                                # Only add if at least one team still needs games
                                if not ((home_abbr in team_games_found and team_games_found[home_abbr] < max_games) or (away_abbr in team_games_found and team_games_found[away_abbr] < max_games)):
                                    continue
                            # Build game dict (existing logic)
                            home_record = home_team.get('records', [{}])[0].get('summary', '') if home_team.get('records') else ''
                            away_record = away_team.get('records', [{}])[0].get('summary', '') if away_team.get('records') else ''
                            odds_data = self.odds_manager.get_odds(
                                sport=sport,
                                league=league,
                                event_id=game_id,
                                update_interval_seconds=7200
                            )
                            has_odds = False
                            if odds_data and not odds_data.get('no_odds'):
                                if odds_data.get('spread') is not None:
                                    has_odds = True
                                if odds_data.get('home_team_odds', {}).get('spread_odds') is not None:
                                    has_odds = True
                                if odds_data.get('away_team_odds', {}).get('spread_odds') is not None:
                                    has_odds = True
                                if odds_data.get('over_under') is not None:
                                    has_odds = True
                            game = {
                                'id': game_id,
                                'home_team': home_abbr,
                                'away_team': away_abbr,
                                'start_time': game_time,
                                'home_record': home_record,
                                'away_record': away_record,
                                'odds': odds_data if has_odds else None,
                                'logo_dir': league_config.get('logo_dir', f'assets/sports/{league.lower()}_logos')
                            }
                            all_games.append(game)
                            games_found += 1
                            # If favorite teams only, increment counters
                            if self.show_favorite_teams_only:
                                for team in [home_abbr, away_abbr]:
                                    if team in team_games_found and team_games_found[team] < max_games:
                                        team_games_found[team] += 1
                # Stop if we have enough games for the league (when not showing favorite teams only)
                if not self.show_favorite_teams_only and max_games_per_league and games_found >= max_games_per_league:
                    break
            except Exception as e:
                logger.error(f"Error fetching games for {league_config.get('league', 'unknown')} on {date}: {e}", exc_info=True)
        return all_games

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
            time_str = local_time.strftime("%I:%M %p").lstrip('0')
            
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
        time_str = local_time.strftime("%I:%M %p").lstrip('0')
        
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
        
        # Make logos use most of the display height, with a small margin
        logo_margin = 0
        logo_size = int(height * 1.2)
        logo_padding = 2
        vs_padding = 8
        section_padding = 12

        # Fonts
        team_font = self.fonts['medium']
        odds_font = self.fonts['medium']
        vs_font = self.fonts['medium']
        datetime_font = self.fonts['medium'] # Use large font for date/time

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

        # Format date and time into 3 parts
        game_time = game['start_time']
        timezone_str = self.config.get('timezone', 'UTC')
        try:
            tz = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            tz = pytz.UTC
        
        if game_time.tzinfo is None:
            game_time = game_time.replace(tzinfo=pytz.UTC)
        local_time = game_time.astimezone(tz)
        
        # Capitalize full day name, e.g., 'Tuesday'
        day_text = local_time.strftime("%A")
        date_text = local_time.strftime("%-m/%d")
        time_text = local_time.strftime("%I:%M %p").lstrip('0')

        # Team and record text
        away_team_text = f"{game.get('away_team', 'N/A')} ({game.get('away_record', '') or 'N/A'})"
        home_team_text = f"{game.get('home_team', 'N/A')} ({game.get('home_record', '') or 'N/A'})"
        
        away_team_width = int(temp_draw.textlength(away_team_text, font=team_font))
        home_team_width = int(temp_draw.textlength(home_team_text, font=team_font))
        team_info_width = max(away_team_width, home_team_width)
        
        # Datetime column width
        day_width = int(temp_draw.textlength(day_text, font=datetime_font))
        date_width = int(temp_draw.textlength(date_text, font=datetime_font))
        time_width = int(temp_draw.textlength(time_text, font=datetime_font))
        datetime_col_width = max(day_width, date_width, time_width)

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
                       team_info_width + section_padding + odds_width + section_padding + datetime_col_width + section_padding)

        # --- Create final image ---
        image = Image.new('RGB', (int(total_width), height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # --- Draw elements ---
        current_x = logo_padding

        # Away Logo
        if away_logo:
            y_pos = (height - logo_size) // 2  # Center the logo vertically
            image.paste(away_logo, (int(current_x), y_pos), away_logo if away_logo.mode == 'RGBA' else None)
        current_x += logo_size + vs_padding

        # "vs."
        y_pos = (height - vs_font.size) // 2 if hasattr(vs_font, 'size') else (height - 8) // 2 # Added fallback for default font
        draw.text((current_x, y_pos), vs_text, font=vs_font, fill=(255, 255, 255))
        current_x += vs_width + vs_padding

        # Home Logo
        if home_logo:
            y_pos = (height - logo_size) // 2  # Center the logo vertically
            image.paste(home_logo, (int(current_x), y_pos), home_logo if home_logo.mode == 'RGBA' else None)
        current_x += logo_size + section_padding

        # Team Info (stacked)
        team_font_height = team_font.size if hasattr(team_font, 'size') else 8
        away_y = 2
        home_y = height - team_font_height - 2
        draw.text((current_x, away_y), away_team_text, font=team_font, fill=(255, 255, 255))
        draw.text((current_x, home_y), home_team_text, font=team_font, fill=(255, 255, 255))
        current_x += team_info_width + section_padding

        # Odds (stacked)
        odds_font_height = odds_font.size if hasattr(odds_font, 'size') else 8
        odds_y_away = 2
        odds_y_home = height - odds_font_height - 2
        
        # Use a consistent color for all odds text
        odds_color = (0, 255, 0) # Green

        draw.text((current_x, odds_y_away), away_odds_text, font=odds_font, fill=odds_color)
        draw.text((current_x, odds_y_home), home_odds_text, font=odds_font, fill=odds_color)
        current_x += odds_width + section_padding
        
        # Datetime (stacked, 3 rows)
        datetime_font_height = datetime_font.size if hasattr(datetime_font, 'size') else 6
        total_dt_height = 3 * datetime_font_height + 4 # Padding between lines
        dt_padding_y = (height - total_dt_height) // 2

        day_y = dt_padding_y
        date_y = day_y + datetime_font_height + 2
        time_y = date_y + datetime_font_height + 2

        draw.text((current_x, day_y), day_text, font=datetime_font, fill=(255, 255, 255))
        draw.text((current_x, date_y), date_text, font=datetime_font, fill=(255, 255, 255))
        draw.text((current_x, time_y), time_text, font=datetime_font, fill=(255, 255, 255))

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
        for idx, img in enumerate(game_images):
            self.ticker_image.paste(img, (current_x, 0))
            current_x += img.width
            # Draw a 1px white vertical bar between games, except after the last one
            if idx < len(game_images) - 1:
                bar_x = current_x + gap_width // 2
                for y in range(height):
                    self.ticker_image.putpixel((bar_x, y), (255, 255, 255))
            current_x += gap_width

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
            
            # Handle looping based on configuration
            if self.loop:
                # Reset position when we've scrolled past the end for a continuous loop
                if self.scroll_position >= self.ticker_image.width:
                    self.scroll_position = 0
            else:
                # Stop scrolling when we reach the end
                if self.scroll_position >= self.ticker_image.width - width:
                    self.scroll_position = self.ticker_image.width - width
            
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