import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests
from PIL import Image, ImageDraw
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cache_manager import CacheManager


logger = logging.getLogger(__name__)


class ColoradoSportsManager:
    """Aggregate live score cards for Colorado professional teams."""

    CACHE_KEY = "colorado_sports_live"
    LOGO_DIRS = {
        "NHL": "assets/sports/nhl_logos",
        "NBA": "assets/sports/nba_logos",
        "NFL": "assets/sports/nfl_logos",
        "MLB": "assets/sports/mlb_logos",
        "MLS": "assets/sports/soccer_logos",
    }
    LEAGUE_COLORS = {
        "NHL": (80, 170, 255),
        "NBA": (255, 120, 35),
        "NFL": (255, 130, 30),
        "MLB": (90, 150, 255),
        "MLS": (60, 210, 120),
    }
    COLORADO_COLOR = (255, 210, 35)
    DIVIDER_COLOR = (40, 150, 255)
    ROCKIES_LOGO_BACKDROP = (255, 255, 255)
    CARD_LOGO_SIZE = 17
    TEAMS = (
        {
            "league": "NHL",
            "abbr": "COL",
            "name": "AVS",
            "url": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
        },
        {
            "league": "NBA",
            "abbr": "DEN",
            "name": "NUG",
            "url": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        },
        {
            "league": "NFL",
            "abbr": "DEN",
            "name": "DEN",
            "url": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        },
        {
            "league": "MLB",
            "abbr": "COL",
            "name": "COL",
            "url": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
        },
        {
            "league": "MLS",
            "abbr": "COL",
            "name": "RAP",
            "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
        },
    )

    def __init__(self, config: Dict[str, Any], display_manager):
        self.config = config
        self.display_manager = display_manager
        self.sports_config = config.get("colorado_sports", {})
        self.enabled = self.sports_config.get("enabled", False)
        self.update_interval = int(
            self.sports_config.get("polling_interval", 30)
        )
        self.stale_timeout = int(
            self.sports_config.get("stale_timeout", 120)
        )
        self.cache_manager = CacheManager()
        self.live_games: List[Dict[str, Any]] = []
        self.last_update = 0.0
        self.last_success = 0.0
        self.is_stale = False
        self.current_game_index = 0
        self.last_game_switch = 0.0
        self._logo_cache: Dict[Any, Optional[Image.Image]] = {}

        self.session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self._load_cache()

    def _load_cache(self) -> None:
        cached = self.cache_manager.load_cache(self.CACHE_KEY)
        if not isinstance(cached, dict):
            return
        payload = cached.get("data", cached)
        games = payload.get("games", []) if isinstance(payload, dict) else []
        updated_at = float(
            payload.get("updated_at", cached.get("timestamp", 0))
            if isinstance(payload, dict)
            else 0
        )
        now = time.time()
        usable_games = [
            game
            for game in games
            if now - game.get("observed_at", updated_at) <= self.stale_timeout
        ]
        if usable_games:
            self.live_games = usable_games
            self.last_success = updated_at
            self.is_stale = True

    @staticmethod
    def _is_live_status(status: Dict[str, Any]) -> bool:
        status_type = status.get("type", {})
        state = str(status_type.get("state", "")).lower()
        name = str(status_type.get("name", "")).upper()
        return state in {"in", "halftime"} or name in {
            "STATUS_IN_PROGRESS",
            "STATUS_HALFTIME",
            "STATUS_FIRST_HALF",
            "STATUS_SECOND_HALF",
        }

    def _parse_event(
        self,
        event: Dict[str, Any],
        team: Dict[str, str],
    ) -> Optional[Dict[str, Any]]:
        competition = (event.get("competitions") or [{}])[0]
        status = competition.get("status", event.get("status", {}))
        if not self._is_live_status(status):
            return None
        competitors = competition.get("competitors", [])
        parsed = {}
        contains_colorado = False
        for competitor in competitors:
            side = competitor.get("homeAway")
            abbr = competitor.get("team", {}).get("abbreviation", "")
            if abbr == team["abbr"]:
                contains_colorado = True
            if side in {"home", "away"}:
                parsed[side] = {
                    "abbr": abbr,
                    "score": str(competitor.get("score", "0")),
                    "is_colorado": abbr == team["abbr"],
                }
        if not contains_colorado or "home" not in parsed or "away" not in parsed:
            return None
        status_type = status.get("type", {})
        return {
            "id": str(event.get("id", "")),
            "league": team["league"],
            "colorado_team": team["name"],
            "home": parsed["home"],
            "away": parsed["away"],
            "clock": status.get("displayClock", ""),
            "period": status.get("period"),
            "status": status_type.get(
                "shortDetail",
                status_type.get("detail", "LIVE"),
            ),
            "outs": (
                competition.get("situation", {}).get("outs")
                if team["league"] == "MLB"
                else None
            ),
            "observed_at": time.time(),
        }

    def _fetch_league(self, team: Dict[str, str]) -> List[Dict[str, Any]]:
        response = self.session.get(
            team["url"],
            headers={"User-Agent": "Mozilla/5.0 (compatible; LEDMatrix/1.0)"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        games = []
        for event in payload.get("events", []):
            parsed = self._parse_event(event, team)
            if parsed:
                games.append(parsed)
        return games

    def _save_cache(self) -> None:
        self.cache_manager.set(
            self.CACHE_KEY,
            {"games": self.live_games, "updated_at": self.last_success},
        )

    def update(self) -> bool:
        if not self.enabled:
            self.live_games = []
            return False
        now = time.time()
        if self.last_update and now - self.last_update < self.update_interval:
            return False
        self.last_update = now

        fresh_games: List[Dict[str, Any]] = []
        successful_leagues = 0
        failed_leagues = set()
        for team in self.TEAMS:
            try:
                fresh_games.extend(self._fetch_league(team))
                successful_leagues += 1
            except Exception as exc:
                failed_leagues.add(team["league"])
                logger.warning(
                    "Colorado %s scores are unavailable: %s",
                    team["league"],
                    exc,
                )

        if failed_leagues and self.live_games:
            retained = [
                game
                for game in self.live_games
                if game.get("league") in failed_leagues
                and now - game.get("observed_at", self.last_success)
                <= self.stale_timeout
            ]
            known_ids = {game.get("id") for game in fresh_games}
            fresh_games.extend(
                game for game in retained if game.get("id") not in known_ids
            )

        if successful_leagues:
            self.live_games = fresh_games
            self.last_success = now
            self.is_stale = bool(failed_leagues and fresh_games)
            self.current_game_index %= max(1, len(self.live_games))
            self._save_cache()
            return True

        retained = [
            game
            for game in self.live_games
            if now - game.get("observed_at", self.last_success)
            <= self.stale_timeout
        ]
        if retained:
            self.live_games = retained
            self.is_stale = True
            return False

        self.live_games = []
        self.is_stale = False
        return False

    def has_display_content(self) -> bool:
        return bool(self.enabled and self.live_games)

    def _load_team_logo(
        self,
        league: str,
        abbreviation: str,
    ) -> Optional[Image.Image]:
        cache_key = (league, abbreviation)
        if cache_key in self._logo_cache:
            return self._logo_cache[cache_key]
        logo_directory = self.LOGO_DIRS.get(league)
        if not logo_directory:
            self._logo_cache[cache_key] = None
            return None
        logo_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                logo_directory,
                f"{abbreviation}.png",
            )
        )
        try:
            if not os.path.isfile(logo_path):
                self._logo_cache[cache_key] = None
                return None
            with Image.open(logo_path) as source:
                logo = source.convert("RGBA")
                resampling = getattr(
                    getattr(Image, "Resampling", Image),
                    "LANCZOS",
                    getattr(Image, "LANCZOS", 1),
                )
                logo_size = (
                    self.CARD_LOGO_SIZE - 2
                    if league == "MLB" and abbreviation.upper() == "COL"
                    else self.CARD_LOGO_SIZE
                )
                logo.thumbnail((logo_size, logo_size), resampling)
                logo = logo.copy()
            self._logo_cache[cache_key] = logo
            return logo
        except Exception as exc:
            logger.debug(
                "Could not render %s %s logo: %s",
                league,
                abbreviation,
                exc,
            )
            self._logo_cache[cache_key] = None
            return None

    def _is_colorado_team(
        self,
        game: Dict[str, Any],
        team: Dict[str, Any],
    ) -> bool:
        if "is_colorado" in team:
            return bool(team["is_colorado"])
        league = game.get("league")
        return any(
            configured["league"] == league
            and configured["abbr"] == team.get("abbr")
            for configured in self.TEAMS
        )

    def _draw_team_badge(
        self,
        draw,
        team: Dict[str, Any],
        game: Dict[str, Any],
        x: int,
        y: int,
        font,
    ) -> None:
        is_colorado = self._is_colorado_team(game, team)
        color = (
            self.COLORADO_COLOR
            if is_colorado
            else self.LEAGUE_COLORS.get(game.get("league"), (130, 130, 130))
        )
        size = self.CARD_LOGO_SIZE
        draw.rectangle((x, y, x + size - 1, y + size - 1), outline=color)
        abbreviation = str(team.get("abbr", "?"))[:3]
        bbox = draw.textbbox((0, 0), abbreviation, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = x + ((size - text_width) // 2) - bbox[0]
        text_y = y + ((size - text_height) // 2) - bbox[1]
        draw.text(
            (text_x, text_y),
            abbreviation,
            font=font,
            fill=color,
        )

    @staticmethod
    def _format_game_state(game: Dict[str, Any]):
        league = str(game.get("league", ""))
        status = str(game.get("status") or "LIVE").strip()
        status_upper = status.upper()
        clock = str(game.get("clock") or "").strip()
        period = game.get("period")
        if "HALF" in status_upper or status_upper == "HT":
            return "HT", None
        if league == "MLB":
            half = "BOT" if "BOT" in status_upper else "TOP"
            inning = str(period or "").strip()
            primary = f"{half} {inning}".strip()
            outs = game.get("outs")
            secondary = (
                f"{int(outs)} OUT"
                if outs not in (None, 0, "0")
                else None
            )
            return primary, secondary
        if league in {"NBA", "NFL"} and period:
            primary = f"Q{period}"
            return f"{primary} {clock}".strip(), None
        if league == "NHL" and period:
            try:
                period_number = int(period)
            except (TypeError, ValueError):
                period_number = 0
            ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(period_number, "OT")
            return f"{ordinal} {clock}".strip(), None
        return (status[:12] or clock or "LIVE"), None

    def _compose_game_state(
        self,
        game: Dict[str, Any],
        font,
        width: int,
    ) -> str:
        primary, secondary = self._format_game_state(game)
        if not secondary:
            return primary
        combined = f"{primary} - {secondary}"
        if self.display_manager.get_text_width(combined, font) <= width - 4:
            return combined
        return primary

    def _render_game(self, game: Dict[str, Any]) -> Image.Image:
        width = int(getattr(self.display_manager, "width", 64))
        height = int(getattr(self.display_manager, "height", 64))
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = getattr(
            self.display_manager,
            "extra_small_font",
            self.display_manager.small_font,
        )
        header_font = getattr(self.display_manager, "small_font", font)
        league = game["league"]
        header = league
        marker = "*" if self.is_stale else ""
        header_width = self.display_manager.get_text_width(
            header,
            header_font,
        )
        header_x = (width - header_width) // 2
        league_color = self.LEAGUE_COLORS.get(league, (80, 180, 255))
        draw.text(
            (header_x, 1),
            header,
            font=header_font,
            fill=(255, 255, 255),
        )
        if marker:
            draw.text(
                (header_x + header_width + 1, 1),
                marker,
                font=font,
                fill=(255, 180, 0),
            )
        draw.line(
            (4, 10, width - 5, 10),
            fill=self.DIVIDER_COLOR,
        )
        draw.line(
            (4, 52, width - 5, 52),
            fill=self.DIVIDER_COLOR,
        )

        away = game["away"]
        home = game["home"]
        logo_size = self.CARD_LOGO_SIZE
        logo_x = (width - logo_size) // 2
        for team, logo_y in ((away, 13), (home, 33)):
            logo = self._load_team_logo(league, team.get("abbr", ""))
            if logo:
                logo_width, logo_height = logo.size
                paste_x = logo_x + ((logo_size - logo_width) // 2)
                paste_y = logo_y + ((logo_size - logo_height) // 2)
                if (
                    league == "MLB"
                    and str(team.get("abbr", "")).upper() == "COL"
                ):
                    draw.ellipse(
                        (
                            logo_x,
                            logo_y,
                            logo_x + logo_size - 1,
                            logo_y + logo_size - 1,
                        ),
                        fill=self.ROCKIES_LOGO_BACKDROP,
                    )
                image.paste(logo, (paste_x, paste_y), logo)
            else:
                self._draw_team_badge(
                    draw,
                    team,
                    game,
                    logo_x,
                    logo_y,
                    font,
                )
            is_colorado = self._is_colorado_team(game, team)
            team_color = (
                self.COLORADO_COLOR
                if is_colorado
                else (255, 255, 255)
            )
            abbreviation = str(team.get("abbr", ""))[:3]
            team_bbox = draw.textbbox((0, 0), abbreviation, font=font)
            team_height = team_bbox[3] - team_bbox[1]
            text_y = (
                logo_y
                + ((logo_size - team_height) // 2)
                - team_bbox[1]
            )
            draw.text(
                (4, text_y),
                abbreviation,
                font=font,
                fill=team_color,
            )
            score = str(team.get("score", "0"))
            score_width = self.display_manager.get_text_width(score, font)
            score_bbox = draw.textbbox((0, 0), score, font=font)
            score_height = score_bbox[3] - score_bbox[1]
            score_y = (
                logo_y
                + ((logo_size - score_height) // 2)
                - score_bbox[1]
            )
            score_region_left = logo_x + logo_size
            score_region_width = width - score_region_left
            score_x = (
                score_region_left
                + ((score_region_width - score_width) // 2)
            )
            draw.text(
                (score_x, score_y),
                score,
                font=font,
                fill=team_color,
            )

        state = self._compose_game_state(game, font, width)
        state_width = self.display_manager.get_text_width(state, font)
        state_bbox = draw.textbbox((0, 0), state, font=font)
        state_y = height - 1 - state_bbox[3]
        state_x = (width - state_width) // 2
        if " - " in state:
            primary, secondary = state.split(" - ", 1)
            primary_text = f"{primary} "
            dash_text = "- "
            draw.text(
                (state_x, state_y),
                primary_text,
                font=font,
                fill=league_color,
            )
            dash_x = state_x + self.display_manager.get_text_width(
                primary_text,
                font,
            )
            draw.text(
                (dash_x, state_y),
                dash_text,
                font=font,
                fill=(255, 255, 255),
            )
            secondary_x = dash_x + self.display_manager.get_text_width(
                dash_text,
                font,
            )
            draw.text(
                (secondary_x, state_y),
                secondary,
                font=font,
                fill=league_color,
            )
        else:
            draw.text(
                (state_x, state_y),
                state,
                font=font,
                fill=league_color,
            )
        return image

    def display(self, force_clear: bool = False) -> bool:
        self.update()
        if not self.has_display_content():
            return False
        now = time.time()
        if len(self.live_games) > 1 and now - self.last_game_switch >= 10:
            self.current_game_index = (
                self.current_game_index + 1
            ) % len(self.live_games)
            self.last_game_switch = now
        if force_clear:
            self.display_manager.clear()
        game = self.live_games[self.current_game_index]
        self.display_manager.image = self._render_game(game)
        self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
        self.display_manager.update_display()
        return True
