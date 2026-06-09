import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List

import requests
from PIL import Image, ImageDraw
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.cache_manager import CacheManager
from src.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class NewsManager:
    """RSS headline cards optimized for a 64x64 square display."""

    CACHE_KEY = "news_cards"

    def __init__(self, config: Dict[str, Any], display_manager):
        self.config = config
        self.config_manager = ConfigManager()
        self.display_manager = display_manager
        self.news_config = config.get("news_manager", {})
        self.enabled = self.news_config.get("enabled", False)
        self.update_interval = int(self.news_config.get("update_interval", 300))
        self.headlines_per_feed = int(
            self.news_config.get("headlines_per_feed", 2)
        )
        self.enabled_feeds = list(self.news_config.get("enabled_feeds", []))
        self.custom_feeds = dict(self.news_config.get("custom_feeds", {}))
        self.rotation_enabled = self.news_config.get("rotation_enabled", True)
        self.text_color = tuple(
            self.news_config.get("text_color", [255, 255, 255])
        )
        self.header_color = tuple(
            self.news_config.get("separator_color", [255, 0, 0])
        )
        self.default_feeds = {
            "MLB": "http://espn.com/espn/rss/mlb/news",
            "NFL": "http://espn.go.com/espn/rss/nfl/news",
            "NCAA FB": "https://www.espn.com/espn/rss/ncf/news",
            "NHL": "https://www.espn.com/espn/rss/nhl/news",
            "NBA": "https://www.espn.com/espn/rss/nba/news",
            "TOP SPORTS": "https://www.espn.com/espn/rss/news",
            "BIG10": "https://www.espn.com/blog/feed?blog=bigten",
            "NCAA": "https://www.espn.com/espn/rss/ncaa/news",
            "Other": "https://www.coveringthecorner.com/rss/current.xml",
        }
        self.cache_manager = CacheManager()
        self.current_headlines: List[Dict[str, Any]] = []
        self.news_data: Dict[str, List[Dict[str, Any]]] = {}
        self.current_headline_index = 0
        self.last_update = 0.0
        self.is_stale = False
        self._has_displayed = False
        self.dynamic_duration = int(
            config.get("display", {})
            .get("display_durations", {})
            .get("news_manager", 60)
        )

        self.session = requests.Session()
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self._load_cache()

    def _load_cache(self) -> None:
        cached = self.cache_manager.load_cache(self.CACHE_KEY)
        if not isinstance(cached, dict):
            return
        payload = cached.get("data", cached)
        headlines = payload.get("headlines", []) if isinstance(payload, dict) else []
        if isinstance(headlines, list):
            self.current_headlines = headlines
            self.is_stale = bool(headlines)

    def _save_cache(self) -> None:
        self.cache_manager.set(
            self.CACHE_KEY,
            {
                "headlines": self.current_headlines,
                "updated_at": time.time(),
            },
        )

    def get_available_feeds(self) -> Dict[str, str]:
        return {**self.default_feeds, **self.custom_feeds}

    def parse_rss_feed(
        self,
        url: str,
        feed_name: str,
    ) -> List[Dict[str, Any]]:
        response = self.session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LEDMatrix/1.0)"},
            timeout=10,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{*}entry")

        headlines = []
        for item in items:
            title_element = item.find("title")
            if title_element is None:
                title_element = item.find("{*}title")
            title = html.unescape(title_element.text or "").strip() if title_element is not None else ""
            title = re.sub(r"<[^>]+>", "", title)
            title = re.sub(r"\s+", " ", title)
            if len(title) < 5:
                continue
            headlines.append(
                {
                    "title": title,
                    "feed": feed_name,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            if len(headlines) >= self.headlines_per_feed:
                break
        return headlines

    def fetch_news_data(self) -> bool:
        if not self.enabled or not self.enabled_feeds:
            self.current_headlines = []
            self.news_data = {}
            return False

        available = self.get_available_feeds()
        all_headlines: List[Dict[str, Any]] = []
        attempted = 0
        failed = False
        for feed_name in self.enabled_feeds:
            url = available.get(feed_name)
            if not url:
                logger.warning("Configured news feed '%s' has no URL", feed_name)
                continue
            attempted += 1
            try:
                all_headlines.extend(self.parse_rss_feed(url, feed_name))
            except Exception as exc:
                failed = True
                logger.warning("News feed %s is unavailable: %s", feed_name, exc)

        self.last_update = time.time()
        if all_headlines:
            self.current_headlines = all_headlines
            self.current_headline_index %= len(self.current_headlines)
            self.news_data = {}
            for headline in all_headlines:
                self.news_data.setdefault(headline["feed"], []).append(headline)
            self.is_stale = failed or attempted == 0
            self._save_cache()
            return True

        if failed and self.current_headlines:
            self.is_stale = True
            return False

        self.current_headlines = []
        self.news_data = {}
        self.is_stale = False
        return False

    def update(self) -> bool:
        if not self.enabled:
            return False
        if time.time() - self.last_update < self.update_interval:
            return False
        return self.fetch_news_data()

    def should_update(self) -> bool:
        return time.time() - self.last_update >= self.update_interval

    def has_display_content(self) -> bool:
        return bool(self.enabled and self.enabled_feeds and self.current_headlines)

    def prepare_headlines_for_display(self) -> None:
        self.current_headline_index %= max(1, len(self.current_headlines))

    def _wrap_text(self, text: str, max_width: int, max_lines: int) -> List[str]:
        font = getattr(
            self.display_manager,
            "extra_small_font",
            self.display_manager.small_font,
        )
        words = text.split()
        lines: List[str] = []
        current = ""
        while words and len(lines) < max_lines:
            word = words.pop(0)
            candidate = f"{current} {word}".strip()
            if self.display_manager.get_text_width(candidate, font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = word
            else:
                current = word
                while (
                    current
                    and self.display_manager.get_text_width(
                        current + "...",
                        font,
                    )
                    > max_width
                ):
                    current = current[:-1]
                lines.append((current + "...") if current else "")
                current = ""
        if current and len(lines) < max_lines:
            lines.append(current)
        if words and lines:
            last = lines[-1]
            while (
                last
                and self.display_manager.get_text_width(last + "...", font)
                > max_width
            ):
                last = last[:-1]
            lines[-1] = last + "..."
        return lines

    def _render_card(self) -> Image.Image:
        width = int(getattr(self.display_manager, "width", 64))
        height = int(getattr(self.display_manager, "height", 64))
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = getattr(
            self.display_manager,
            "extra_small_font",
            self.display_manager.small_font,
        )
        headline = self.current_headlines[self.current_headline_index]
        feed = str(headline.get("feed", "NEWS")).upper()[:10]
        header = f"{feed}*" if self.is_stale else feed
        header_width = self.display_manager.get_text_width(header, font)
        draw.text(
            ((width - header_width) // 2, 1),
            header,
            font=font,
            fill=(255, 190, 0) if self.is_stale else self.header_color,
        )
        draw.line((2, 9, width - 3, 9), fill=self.header_color)
        for index, line in enumerate(
            self._wrap_text(str(headline.get("title", "")), width - 4, 6)
        ):
            draw.text((2, 12 + index * 8), line, font=font, fill=self.text_color)
        return image

    def display_news(self, force_clear: bool = False) -> bool:
        self.update()
        if not self.has_display_content():
            return False
        if force_clear and self._has_displayed and self.rotation_enabled:
            self.current_headline_index = (
                self.current_headline_index + 1
            ) % len(self.current_headlines)
        if force_clear:
            self.display_manager.clear()
        self.display_manager.image = self._render_card()
        self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
        self.display_manager.update_display()
        self._has_displayed = True
        return True

    def get_news_display(self) -> Image.Image:
        if not self.has_display_content():
            width = int(getattr(self.display_manager, "width", 64))
            height = int(getattr(self.display_manager, "height", 64))
            return Image.new("RGB", (width, height), (0, 0, 0))
        return self._render_card()

    def add_custom_feed(self, name: str, url: str) -> None:
        self.custom_feeds[name] = url
        self.config.setdefault("news_manager", {})["custom_feeds"] = self.custom_feeds
        self.config_manager.save_config(self.config)

    def remove_custom_feed(self, name: str) -> None:
        self.custom_feeds.pop(name, None)
        self.config.setdefault("news_manager", {})["custom_feeds"] = self.custom_feeds
        self.config_manager.save_config(self.config)

    def set_enabled_feeds(self, feeds: List[str]) -> None:
        self.enabled_feeds = feeds
        self.config.setdefault("news_manager", {})["enabled_feeds"] = feeds
        self.config_manager.save_config(self.config)
        self.last_update = 0

    def get_feed_status(self) -> Dict[str, Any]:
        return {
            "enabled_feeds": self.enabled_feeds,
            "available_feeds": list(self.get_available_feeds()),
            "headlines_per_feed": self.headlines_per_feed,
            "last_update": self.last_update,
            "total_headlines": len(self.current_headlines),
            "rotation_enabled": self.rotation_enabled,
            "current_headline_index": self.current_headline_index,
            "stale": self.is_stale,
        }

    def get_dynamic_duration(self) -> int:
        return self.dynamic_duration
