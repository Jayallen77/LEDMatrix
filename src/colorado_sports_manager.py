import logging
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
        header = f"{game['league']} LIVE"
        if self.is_stale:
            header += "*"
        header_width = self.display_manager.get_text_width(header, font)
        draw.text(
            ((width - header_width) // 2, 1),
            header,
            font=font,
            fill=(255, 190, 0) if self.is_stale else (255, 50, 50),
        )

        status = str(game.get("status") or "LIVE")[:12]
        status_width = self.display_manager.get_text_width(status, font)
        draw.text(
            ((width - status_width) // 2, 12),
            status,
            font=font,
            fill=(180, 180, 180),
        )

        away = game["away"]
        home = game["home"]
        draw.text(
            (4, 27),
            f"{away['abbr']:<3} {away['score']:>3}",
            font=font,
            fill=(255, 255, 255),
        )
        draw.text(
            (4, 39),
            f"{home['abbr']:<3} {home['score']:>3}",
            font=font,
            fill=(255, 255, 255),
        )
        clock = str(game.get("clock") or "")
        period = game.get("period")
        detail = f"P{period} {clock}".strip() if period else clock
        detail_width = self.display_manager.get_text_width(detail, font)
        draw.text(
            ((width - detail_width) // 2, 54),
            detail,
            font=font,
            fill=(80, 180, 255),
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
