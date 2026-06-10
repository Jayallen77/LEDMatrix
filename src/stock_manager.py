import logging
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cache_manager import CacheManager


logger = logging.getLogger(__name__)


class StockManager:
    """Display a compact broad-market summary behind the legacy stocks mode."""

    CACHE_KEY = "market_pulse"
    LABEL_COLOR = (255, 255, 255)
    POSITIVE_COLOR = (0, 255, 70)
    NEGATIVE_COLOR = (255, 45, 45)
    NEUTRAL_COLOR = (255, 210, 0)
    UNAVAILABLE_COLOR = (115, 115, 115)
    ACCENT_COLOR = (40, 150, 255)
    STALE_COLOR = (255, 180, 0)
    TREND_COLOR = (90, 170, 255)
    VIX_CALM_COLOR = (0, 190, 255)
    VIX_NORMAL_COLOR = (0, 255, 70)
    VIX_ELEVATED_COLOR = (255, 190, 0)
    VIX_HIGH_COLOR = (255, 95, 35)
    VIX_PANIC_COLOR = (255, 30, 110)
    INSTRUMENTS = (
        ("sp500", "S&P", "^GSPC"),
        ("nasdaq", "NAS", "^IXIC"),
        ("dow", "DOW", "^DJI"),
        ("btc", "BTC", "BTC-USD"),
        ("vix", "VIX", "^VIX"),
    )

    def __init__(self, config: Dict[str, Any], display_manager):
        self.config = config
        self.display_manager = display_manager
        self.stocks_config = config.get("stocks", {})
        self.crypto_config = config.get("crypto", {})
        self.toggle_chart = bool(self.stocks_config.get("toggle_chart", False))
        self.scroll_speed = self.stocks_config.get("scroll_speed", 1)
        self.scroll_delay = self.stocks_config.get("scroll_delay", 0.01)
        self.cached_text_image = None
        self.cache_manager = CacheManager()
        self.market_data: Dict[str, Dict[str, Any]] = {}
        self.stock_data = self.market_data  # Backward-compatible attribute.
        self.last_update = 0.0
        self.data_timestamp = 0.0
        self.is_stale = False
        self.retry_attempts = 0
        self.next_retry_at = 0.0
        self.dynamic_duration = int(
            config.get("display", {})
            .get("display_durations", {})
            .get("stocks", 30)
        )

        self.session = requests.Session()
        retry_strategy = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LEDMatrix/1.0)",
            "Accept": "application/json",
        }

        self._load_cached_data()
        self.update_stock_data()

    @property
    def include_btc(self) -> bool:
        return self.crypto_config.get("enabled", True)

    def _load_cached_data(self) -> None:
        cached = self.cache_manager.load_cache(self.CACHE_KEY)
        if not isinstance(cached, dict):
            return
        payload = cached.get("data", cached)
        if not isinstance(payload, dict):
            return
        instruments = payload.get("instruments", {})
        if isinstance(instruments, dict):
            self.market_data = instruments
            self.stock_data = self.market_data
            self.data_timestamp = float(
                payload.get("updated_at", cached.get("timestamp", 0)) or 0
            )
            self.is_stale = bool(self.market_data)
            logger.info(
                "Loaded %d Market Pulse rows from persistent cache",
                len(self.market_data),
            )

    def _cache_current_data(self) -> None:
        self.cache_manager.set(
            self.CACHE_KEY,
            {
                "instruments": self.market_data,
                "updated_at": self.data_timestamp,
            },
        )

    def _mark_retryable(self, message: str) -> None:
        self.retry_attempts = min(self.retry_attempts + 1, 5)
        delay = min(30 * (2 ** (self.retry_attempts - 1)), 300)
        self.next_retry_at = time.time() + delay
        self.is_stale = bool(self.market_data)
        logger.warning("%s Retrying Market Pulse in %d seconds.", message, delay)

    def _fetch_instrument(
        self,
        key: str,
        label: str,
        symbol: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
        encoded_symbol = urllib.parse.quote(symbol, safe="")
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{encoded_symbol}"
        )
        response = self.session.get(
            url,
            headers=self.headers,
            params={
                "interval": "5m",
                "range": "5d",
                "includePrePost": "false",
            },
            timeout=8,
        )
        if response.status_code != 200:
            logger.warning(
                "Market Pulse request failed for %s: HTTP %s",
                symbol,
                response.status_code,
            )
            return None, response.status_code

        payload = response.json()
        results = payload.get("chart", {}).get("result") or []
        if not results:
            raise ValueError(f"No chart result for {symbol}")
        chart = results[0]
        meta = chart.get("meta", {})
        timestamps = chart.get("timestamp") or []
        quote = (
            chart.get("indicators", {})
            .get("quote", [{}])[0]
        )
        closes = quote.get("close") or []
        opens = quote.get("open") or []
        points = []
        for index, timestamp in enumerate(timestamps):
            close_value = closes[index] if index < len(closes) else None
            if close_value is None:
                continue
            open_value = opens[index] if index < len(opens) else None
            points.append((int(timestamp), open_value, close_value))
        if key == "btc":
            return self._build_crypto_row(
                key,
                label,
                symbol,
                meta,
                points,
            ), None
        return self._build_regular_session_row(
            key,
            label,
            symbol,
            meta,
            points,
        ), None

    @staticmethod
    def _sample_trend(values, sample_count: int = 7):
        cleaned = [float(value) for value in values if value is not None]
        if not cleaned:
            return []
        last_index = len(cleaned) - 1
        return [
            cleaned[round(index * last_index / (sample_count - 1))]
            for index in range(sample_count)
        ]

    @staticmethod
    def _exchange_timezone(meta: Dict[str, Any]):
        timezone_name = meta.get("exchangeTimezoneName")
        try:
            return ZoneInfo(timezone_name) if timezone_name else ZoneInfo("UTC")
        except Exception:
            return ZoneInfo("UTC")

    def _build_regular_session_row(
        self,
        key: str,
        label: str,
        symbol: str,
        meta: Dict[str, Any],
        points,
    ) -> Dict[str, Any]:
        if not points:
            raise ValueError(f"No regular-session chart points for {symbol}")
        exchange_timezone = self._exchange_timezone(meta)
        sessions: Dict[Any, list] = {}
        for timestamp, open_value, close_value in points:
            session_date = datetime.fromtimestamp(
                timestamp,
                exchange_timezone,
            ).date()
            sessions.setdefault(session_date, []).append(
                (timestamp, open_value, float(close_value))
            )

        now = time.time()
        trading_period = meta.get("currentTradingPeriod", {}).get("regular", {})
        regular_start = float(trading_period.get("start", 0) or 0)
        regular_end = float(trading_period.get("end", 0) or 0)
        today = datetime.fromtimestamp(now, exchange_timezone).date()
        if regular_start <= now < regular_end:
            target_date = datetime.fromtimestamp(
                regular_start,
                exchange_timezone,
            ).date()
            session_state = "open"
        elif now >= regular_end and today in sessions:
            target_date = today
            session_state = "closed"
        else:
            prior_dates = [session_date for session_date in sessions if session_date < today]
            target_date = max(prior_dates) if prior_dates else max(sessions)
            session_state = "previous"

        session_points = sessions.get(target_date)
        if not session_points:
            target_date = max(sessions)
            session_points = sessions[target_date]
            session_state = "previous"
        session_points.sort(key=lambda point: point[0])
        opening_price = next(
            (
                float(open_value)
                for _, open_value, _ in session_points
                if open_value not in (None, 0)
            ),
            session_points[0][2],
        )
        current = session_points[-1][2]
        if opening_price == 0:
            raise ValueError(f"Invalid regular-session open for {symbol}")
        return {
            "key": key,
            "label": label,
            "symbol": symbol,
            "price": current,
            "change_percent": ((current - opening_price) / opening_price) * 100,
            "trend": self._sample_trend(
                [point[2] for point in session_points]
            ),
            "session_state": session_state,
            "updated_at": time.time(),
        }

    def _build_crypto_row(
        self,
        key: str,
        label: str,
        symbol: str,
        meta: Dict[str, Any],
        points,
    ) -> Dict[str, Any]:
        current = meta.get("regularMarketPrice")
        if current is None and points:
            current = points[-1][2]
        previous = meta.get("previousClose", meta.get("chartPreviousClose"))
        if current is None or previous in (None, 0):
            raise ValueError(f"Incomplete quote metadata for {symbol}")
        cutoff = time.time() - (24 * 60 * 60)
        recent_closes = [
            float(close_value)
            for timestamp, _, close_value in points
            if timestamp >= cutoff
        ]
        if not recent_closes:
            recent_closes = [float(point[2]) for point in points]
        current = float(current)
        previous = float(previous)
        return {
            "key": key,
            "label": label,
            "symbol": symbol,
            "price": current,
            "change_percent": ((current - previous) / previous) * 100,
            "trend": self._sample_trend(recent_closes),
            "session_state": "continuous",
            "updated_at": time.time(),
        }

    def update_stock_data(self) -> bool:
        """Refresh Market Pulse data while preserving last-known-good rows."""
        now = time.time()
        update_interval = int(self.stocks_config.get("update_interval", 600))
        if now < self.next_retry_at:
            return False
        if self.last_update and now - self.last_update < update_interval:
            return False

        fresh_rows: Dict[str, Dict[str, Any]] = {}
        attempted = 0
        failed = False
        try:
            for key, label, symbol in self.INSTRUMENTS:
                if key == "btc" and not self.include_btc:
                    continue
                attempted += 1
                row, status = self._fetch_instrument(key, label, symbol)
                if row:
                    fresh_rows[key] = row
                    continue
                failed = True
                if status == 429:
                    break
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            failed = True
            logger.warning("Market Pulse refresh failed: %s", exc)
        except Exception as exc:
            failed = True
            logger.exception("Unexpected Market Pulse refresh failure: %s", exc)

        self.last_update = now
        if fresh_rows:
            merged = dict(self.market_data)
            merged.update(fresh_rows)
            if not self.include_btc:
                merged.pop("btc", None)
            self.market_data = merged
            self.stock_data = self.market_data
            self.data_timestamp = now
            uses_previous_session = any(
                row.get("session_state") == "previous"
                for key, row in fresh_rows.items()
                if key != "btc"
            )
            self.is_stale = (
                failed
                or len(fresh_rows) < attempted
                or uses_previous_session
            )
            self.retry_attempts = 0
            self.next_retry_at = 0.0
            self._cache_current_data()
            logger.info(
                "Market Pulse refreshed %d/%d rows%s",
                len(fresh_rows),
                attempted,
                " with cached fallback" if self.is_stale else "",
            )
            return True

        self._mark_retryable("Market Pulse data is temporarily unavailable.")
        return False

    @staticmethod
    def _movement_color(change: float, invert: bool = False) -> Tuple[int, int, int]:
        if change == 0:
            return StockManager.NEUTRAL_COLOR
        positive = change > 0
        if invert:
            positive = not positive
        return (
            StockManager.POSITIVE_COLOR
            if positive
            else StockManager.NEGATIVE_COLOR
        )

    @staticmethod
    def _compact_price(value: float) -> str:
        absolute = abs(value)
        if absolute >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        if absolute >= 100_000:
            return f"${value / 1_000:.0f}K"
        if absolute >= 10_000:
            return f"${value / 1_000:.1f}K"
        if absolute >= 1_000:
            return f"${value:,.0f}"
        return f"${value:.0f}"

    @staticmethod
    def _vix_risk_color(level: float) -> Tuple[int, int, int]:
        if level < 13:
            return StockManager.VIX_CALM_COLOR
        if level < 20:
            return StockManager.VIX_NORMAL_COLOR
        if level < 30:
            return StockManager.VIX_ELEVATED_COLOR
        if level < 40:
            return StockManager.VIX_HIGH_COLOR
        return StockManager.VIX_PANIC_COLOR

    def _format_value(
        self,
        key: str,
    ) -> Tuple[str, Tuple[int, int, int], Optional[int]]:
        row = self.market_data.get(key)
        if not row:
            return "--", self.UNAVAILABLE_COLOR, None
        change = float(row.get("change_percent", 0))
        if key == "btc":
            value = self._compact_price(float(row.get("price", 0)))
            color = self._movement_color(change)
        elif key == "vix":
            level = float(row.get("price", 0))
            value = f"{level:.1f}"
            color = self._vix_risk_color(level)
        else:
            value = f"{change:+.1f}%"
            color = self._movement_color(change)
        direction = 1 if change > 0 else -1 if change < 0 else 0
        return value, color, direction

    def _format_row(
        self,
        key: str,
        label: str,
    ) -> Tuple[str, Tuple[int, int, int]]:
        value, color, _ = self._format_value(key)
        return f"{label} {value}", color

    @staticmethod
    def _draw_direction_indicator(
        draw,
        x: int,
        y: int,
        direction: Optional[int],
        color: Tuple[int, int, int],
    ) -> None:
        if direction is None or direction == 0:
            draw.line((x, y + 2, x + 4, y + 2), fill=color)
            return
        if direction > 0:
            draw.line((x + 2, y, x, y + 2), fill=color)
            draw.line((x + 2, y, x + 4, y + 2), fill=color)
            draw.line((x + 2, y, x + 2, y + 5), fill=color)
            return
        draw.line((x, y + 2, x + 2, y + 4), fill=color)
        draw.line((x + 4, y + 2, x + 2, y + 4), fill=color)
        draw.line((x + 2, y, x + 2, y + 4), fill=color)

    @staticmethod
    def _fallback_trend(direction: Optional[int]):
        if direction is None:
            return []
        if direction > 0:
            return [1, 2, 3, 4, 5, 6, 7]
        if direction < 0:
            return [7, 6, 5, 4, 3, 2, 1]
        return [4, 4, 4, 4, 4, 4, 4]

    def _draw_trend(
        self,
        draw,
        x: int,
        y: int,
        values,
        direction: Optional[int],
        color: Tuple[int, int, int],
    ) -> None:
        samples = self._sample_trend(values)
        if not samples:
            samples = self._fallback_trend(direction)
        if not samples:
            return
        minimum = min(samples)
        maximum = max(samples)
        span = maximum - minimum
        for index, sample in enumerate(samples[:7]):
            height = (
                3
                if span == 0
                else 1 + round(((sample - minimum) / span) * 5)
            )
            left = x + (index * 2)
            draw.rectangle(
                (left, y + 6 - height, left, y + 6),
                fill=color,
            )

    def _render_market_pulse(self) -> Image.Image:
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

        unavailable = not self.market_data
        header = "MARKETS"
        header_width = self.display_manager.get_text_width(header, header_font)
        marker = "*" if self.is_stale else "?" if unavailable else ""
        marker_width = self.display_manager.get_text_width(marker, header_font)
        total_header_width = header_width + (1 + marker_width if marker else 0)
        header_x = (width - total_header_width) // 2
        draw.text(
            (header_x, 2),
            header,
            font=header_font,
            fill=self.LABEL_COLOR,
        )
        if marker:
            draw.text(
                (header_x + header_width + 1, 2),
                marker,
                font=header_font,
                fill=self.STALE_COLOR,
            )
        draw.line((5, 10, width - 6, 10), fill=self.ACCENT_COLOR)

        rows = [item for item in self.INSTRUMENTS if item[0] != "btc" or self.include_btc]
        y_positions = (14, 24, 34, 44, 54)
        trend_x = 18
        arrow_x = width - 6
        value_right = arrow_x - 2
        for (key, label, _), y in zip(rows, y_positions):
            value, color, direction = self._format_value(key)
            draw.text((1, y), label, font=font, fill=self.LABEL_COLOR)
            row = self.market_data.get(key, {})
            self._draw_trend(
                draw,
                trend_x,
                y,
                row.get("trend", []),
                direction,
                color if row else self.UNAVAILABLE_COLOR,
            )
            value_width = self.display_manager.get_text_width(value, font)
            draw.text(
                (max(32, value_right - value_width), y),
                value,
                font=font,
                fill=color,
            )
            self._draw_direction_indicator(
                draw,
                arrow_x,
                y,
                direction,
                color,
            )
        return image

    def display_stocks(self, force_clear: bool = False) -> bool:
        if not self.stocks_config.get("enabled", False):
            return False
        self.update_stock_data()
        if force_clear:
            self.display_manager.clear()
        self.display_manager.image = self._render_market_pulse()
        self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
        self.display_manager.update_display()
        return True

    def get_dynamic_duration(self) -> int:
        return self.dynamic_duration

    def set_toggle_chart(self, enabled: bool) -> None:
        self.toggle_chart = bool(enabled)
        self.stocks_config["toggle_chart"] = self.toggle_chart
        self.cached_text_image = None

    def set_scroll_speed(self, speed: int) -> None:
        self.scroll_speed = speed
        self.stocks_config["scroll_speed"] = speed

    def set_scroll_delay(self, delay: float) -> None:
        self.scroll_delay = delay
        self.stocks_config["scroll_delay"] = delay

    def _reload_config(self) -> None:
        self.stocks_config = self.config.get("stocks", {})
        self.crypto_config = self.config.get("crypto", {})
        self.toggle_chart = bool(self.stocks_config.get("toggle_chart", False))
        self.scroll_speed = self.stocks_config.get("scroll_speed", 1)
        self.scroll_delay = self.stocks_config.get("scroll_delay", 0.01)
        self.cached_text_image = None
