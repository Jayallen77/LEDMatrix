import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeImage:
    def __init__(self, size):
        self.size = size
        self.width, self.height = size


class FakeDraw:
    def __init__(self, image):
        self.image = image
        self.operations = []
        image.draw_operations = self.operations

    def text(self, position, text, **kwargs):
        self.operations.append(("text", position, text, kwargs))

    def line(self, points, **kwargs):
        self.operations.append(("line", points, kwargs))

    def rectangle(self, points, **kwargs):
        self.operations.append(("rectangle", points, kwargs))


def install_dependency_stubs():
    if "PIL" not in sys.modules:
        pil = types.ModuleType("PIL")
        image_module = types.ModuleType("PIL.Image")
        image_module.Image = FakeImage
        image_module.new = lambda mode, size, color=None: FakeImage(size)
        draw_module = types.ModuleType("PIL.ImageDraw")
        draw_module.Draw = FakeDraw
        pil.Image = image_module
        pil.ImageDraw = draw_module
        sys.modules["PIL"] = pil
        sys.modules["PIL.Image"] = image_module
        sys.modules["PIL.ImageDraw"] = draw_module

    if "requests" not in sys.modules:
        requests = types.ModuleType("requests")
        requests.Session = Mock
        requests.RequestException = Exception
        requests.exceptions = types.SimpleNamespace(RequestException=Exception)
        adapters = types.ModuleType("requests.adapters")
        adapters.HTTPAdapter = Mock
        requests.adapters = adapters
        sys.modules["requests"] = requests
        sys.modules["requests.adapters"] = adapters

    if "urllib3.util.retry" not in sys.modules:
        urllib3 = types.ModuleType("urllib3")
        util = types.ModuleType("urllib3.util")
        retry = types.ModuleType("urllib3.util.retry")
        retry.Retry = Mock
        sys.modules["urllib3"] = urllib3
        sys.modules["urllib3.util"] = util
        sys.modules["urllib3.util.retry"] = retry

    if "src.cache_manager" not in sys.modules:
        cache_module = types.ModuleType("src.cache_manager")
        cache_module.CacheManager = Mock
        sys.modules["src.cache_manager"] = cache_module


install_dependency_stubs()
from src import stock_manager


class MemoryCache:
    def __init__(self, initial=None):
        self.records = initial or {}

    def load_cache(self, key):
        return self.records.get(key)

    def set(self, key, data):
        self.records[key] = {"data": data, "timestamp": 100}


class FakeDisplay:
    width = 64
    height = 64
    extra_small_font = object()
    small_font = object()

    def __init__(self):
        self.image = None
        self.draw = None
        self.updated = 0
        self.cleared = 0

    @staticmethod
    def get_text_width(text, font):
        del font
        return len(text) * 4

    def clear(self):
        self.cleared += 1

    def update_display(self):
        self.updated += 1


class MarketPulseTests(unittest.TestCase):
    def make_manager(self, cache=None, include_btc=True):
        config = {
            "stocks": {"enabled": True, "update_interval": 600},
            "crypto": {"enabled": include_btc},
            "display": {"display_durations": {"stocks": 30}},
        }
        with (
            patch.object(stock_manager, "CacheManager", return_value=cache or MemoryCache()),
            patch.object(
                stock_manager.StockManager,
                "update_stock_data",
                return_value=False,
            ),
        ):
            return stock_manager.StockManager(config, FakeDisplay())

    @staticmethod
    def render(manager):
        with (
            patch.object(
                stock_manager.Image,
                "new",
                side_effect=lambda mode, size, color=None: FakeImage(size),
            ),
            patch.object(
                stock_manager.ImageDraw,
                "Draw",
                side_effect=FakeDraw,
            ),
        ):
            return manager._render_market_pulse()

    def test_formats_market_rows_and_renders_64_square(self):
        manager = self.make_manager()
        manager.market_data = {
            "sp500": {"price": 6000, "change_percent": 0.6},
            "nasdaq": {"price": 19000, "change_percent": 1.1},
            "dow": {"price": 42000, "change_percent": -0.2},
            "btc": {"price": 104200, "change_percent": 2.0},
            "vix": {"price": 18.4, "change_percent": 3.0},
        }

        image = self.render(manager)

        self.assertEqual(image.size, (64, 64))
        self.assertEqual(manager._format_row("sp500", "S&P")[0], "S&P +0.6%")
        self.assertEqual(manager._format_row("btc", "BTC")[0], "BTC $104K")
        self.assertEqual(
            manager._format_row("vix", "VIX")[1],
            manager.VIX_NORMAL_COLOR,
        )
        text_operations = [
            operation
            for operation in image.draw_operations
            if operation[0] == "text"
        ]
        labels = {
            operation[2]: operation[3]["fill"]
            for operation in text_operations
            if operation[2] in {"MARKETS", "S&P", "NAS", "DOW", "BTC", "VIX"}
        }
        self.assertEqual(labels["MARKETS"], manager.LABEL_COLOR)
        self.assertEqual(labels["S&P"], manager.LABEL_COLOR)
        self.assertEqual(labels["NAS"], manager.LABEL_COLOR)
        self.assertEqual(labels["DOW"], manager.LABEL_COLOR)
        self.assertEqual(labels["BTC"], manager.LABEL_COLOR)
        self.assertEqual(labels["VIX"], manager.LABEL_COLOR)
        values = {
            operation[2]: operation[3]["fill"]
            for operation in text_operations
            if operation[2] in {"+0.6%", "+1.1%", "-0.2%", "$104K", "18.4"}
        }
        value_positions = {
            operation[2]: operation[1]
            for operation in text_operations
            if operation[2] in {"+0.6%", "+1.1%", "-0.2%", "$104K", "18.4"}
        }
        self.assertEqual(values["+0.6%"], manager.POSITIVE_COLOR)
        self.assertEqual(values["-0.2%"], manager.NEGATIVE_COLOR)
        self.assertEqual(values["18.4"], manager.VIX_NORMAL_COLOR)
        self.assertEqual(value_positions["+0.6%"][0], 36)
        self.assertEqual(value_positions["18.4"][0], 40)
        positions = {
            operation[2]: operation[1]
            for operation in text_operations
            if operation[2] in {"MARKETS", "S&P", "NAS", "DOW", "BTC", "VIX"}
        }
        self.assertEqual(positions["MARKETS"], (18, 2))
        self.assertEqual(
            [positions[label][1] for label in ("S&P", "NAS", "DOW", "BTC", "VIX")],
            [14, 24, 34, 44, 54],
        )
        self.assertTrue(
            all(positions[label][0] == 1 for label in ("S&P", "NAS", "DOW", "BTC", "VIX"))
        )
        line_operations = [
            operation
            for operation in image.draw_operations
            if operation[0] == "line"
        ]
        self.assertGreaterEqual(len(line_operations), 16)
        self.assertIn(
            ("line", (5, 10, 58, 10), {"fill": manager.ACCENT_COLOR}),
            line_operations,
        )
        self.assertIn(
            ("line", (60, 14, 58, 16), {"fill": manager.POSITIVE_COLOR}),
            line_operations,
        )
        trend_operations = [
            operation
            for operation in image.draw_operations
            if operation[0] == "rectangle"
            and operation[1][0] == operation[1][2]
            and 18 <= operation[1][0] <= 30
        ]
        self.assertEqual(len(trend_operations), 35)
        self.assertEqual(
            [operation[1][0] for operation in trend_operations[:7]],
            [18, 20, 22, 24, 26, 28, 30],
        )
        self.assertTrue(
            all(
                operation[2]["fill"] == manager.VIX_NORMAL_COLOR
                for operation in trend_operations[-7:]
            )
        )
        self.assertTrue(
            all(
                operation[2]["fill"] == manager.VIX_NORMAL_COLOR
                for operation in line_operations[-3:]
            )
        )

    def test_vix_uses_risk_level_color_and_actual_direction(self):
        manager = self.make_manager()
        cases = (
            (18.4, 2.0, "18.4", manager.VIX_NORMAL_COLOR, 1),
            (32.0, -2.0, "32.0", manager.VIX_HIGH_COLOR, -1),
            (45.0, 3.0, "45.0", manager.VIX_PANIC_COLOR, 1),
        )
        for level, change, value, expected_color, expected_direction in cases:
            manager.market_data = {
                "vix": {"price": level, "change_percent": change},
            }

            formatted, color, direction = manager._format_value("vix")

            self.assertEqual(formatted, value)
            self.assertEqual(color, expected_color)
            self.assertEqual(direction, expected_direction)

    def test_vix_risk_color_boundaries(self):
        manager = self.make_manager()
        self.assertEqual(manager._vix_risk_color(12.9), manager.VIX_CALM_COLOR)
        self.assertEqual(manager._vix_risk_color(13), manager.VIX_NORMAL_COLOR)
        self.assertEqual(manager._vix_risk_color(20), manager.VIX_ELEVATED_COLOR)
        self.assertEqual(manager._vix_risk_color(30), manager.VIX_HIGH_COLOR)
        self.assertEqual(manager._vix_risk_color(40), manager.VIX_PANIC_COLOR)

    def test_cached_and_fallback_trends_render_seven_bars(self):
        manager = self.make_manager()
        self.assertEqual(len(manager._sample_trend([1, 2, 3, 4])), 7)
        self.assertEqual(manager._fallback_trend(1), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(manager._fallback_trend(-1), [7, 6, 5, 4, 3, 2, 1])
        self.assertEqual(manager._fallback_trend(0), [4, 4, 4, 4, 4, 4, 4])

    def test_status_dot_is_spaced_from_centered_header_and_within_bounds(self):
        manager = self.make_manager()
        manager.market_data = {
            "sp500": {"price": 6000, "change_percent": 0.0},
        }
        manager.is_stale = True

        image = self.render(manager)

        header = next(
            operation
            for operation in image.draw_operations
            if operation[0] == "text" and operation[2] == "MARKETS"
        )
        dot_lines = [
            operation
            for operation in image.draw_operations
            if operation[0] == "line"
            and operation[1] in {(48, 4, 49, 4), (48, 5, 49, 5)}
        ]
        self.assertEqual(header[1], (18, 2))
        self.assertEqual(len(dot_lines), 2)
        self.assertTrue(
            all(
                operation[2]["fill"] == manager.STATUS_ERROR_COLOR
                for operation in dot_lines
            )
        )
        for operation in image.draw_operations:
            if operation[0] == "text":
                x, y = operation[1]
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLess(x, 64)
                self.assertLess(y, 64)
            elif operation[0] == "line":
                points = operation[1]
                self.assertTrue(all(0 <= coordinate < 64 for coordinate in points))
            elif operation[0] == "rectangle":
                points = operation[1]
                self.assertTrue(all(0 <= coordinate < 64 for coordinate in points))

    def test_status_dot_colors_describe_market_and_refresh_state(self):
        manager = self.make_manager()

        manager.market_data = {
            "sp500": {"session_state": "open"},
            "btc": {"session_state": "continuous"},
        }
        manager.is_stale = False
        manager.refresh_error = False
        self.assertEqual(
            manager._status_dot_color(),
            manager.STATUS_OPEN_COLOR,
        )

        manager.market_data["sp500"]["session_state"] = "closed"
        self.assertEqual(
            manager._status_dot_color(),
            manager.STATUS_CLOSED_COLOR,
        )

        manager.market_data["sp500"]["session_state"] = "previous"
        manager.is_stale = True
        self.assertEqual(
            manager._status_dot_color(),
            manager.STATUS_CLOSED_COLOR,
        )

        manager.refresh_error = True
        self.assertEqual(
            manager._status_dot_color(),
            manager.STATUS_ERROR_COLOR,
        )

        manager.market_data = {}
        self.assertEqual(
            manager._status_dot_color(),
            manager.STATUS_NO_DATA_COLOR,
        )

    def test_regular_session_change_uses_open_latest_and_session_state(self):
        manager = self.make_manager()
        session_date = datetime(2026, 6, 10, tzinfo=timezone.utc)
        start = session_date.replace(hour=14, minute=30).timestamp()
        end = session_date.replace(hour=21).timestamp()
        points = [
            (int(start), 100.0, 100.5),
            (int(start + 3600), 100.5, 101.0),
            (int(start + 7200), 101.0, 102.0),
            (int(start + 10800), 102.0, 103.0),
        ]
        meta = {
            "exchangeTimezoneName": "UTC",
            "currentTradingPeriod": {
                "regular": {"start": start, "end": end}
            },
        }

        with patch.object(
            stock_manager.time,
            "time",
            return_value=start + 12000,
        ):
            open_row = manager._build_regular_session_row(
                "sp500", "S&P", "^GSPC", meta, points
            )

        self.assertEqual(open_row["session_state"], "open")
        self.assertAlmostEqual(open_row["change_percent"], 3.0)
        self.assertEqual(len(open_row["trend"]), 7)
        self.assertEqual(open_row["trend"][0], 100.5)
        self.assertEqual(open_row["trend"][-1], 103.0)

        with patch.object(
            stock_manager.time,
            "time",
            return_value=end + 60,
        ):
            closed_row = manager._build_regular_session_row(
                "sp500", "S&P", "^GSPC", meta, points
            )

        self.assertEqual(closed_row["session_state"], "closed")
        self.assertAlmostEqual(closed_row["change_percent"], 3.0)

    def test_before_open_uses_previous_completed_session(self):
        manager = self.make_manager()
        previous_date = datetime(2026, 6, 9, tzinfo=timezone.utc)
        current_date = datetime(2026, 6, 10, tzinfo=timezone.utc)
        previous_start = previous_date.replace(hour=14, minute=30).timestamp()
        current_start = current_date.replace(hour=14, minute=30).timestamp()
        current_end = current_date.replace(hour=21).timestamp()
        points = [
            (int(previous_start), 200.0, 201.0),
            (int(previous_start + 3600), 201.0, 198.0),
        ]
        meta = {
            "exchangeTimezoneName": "UTC",
            "currentTradingPeriod": {
                "regular": {"start": current_start, "end": current_end}
            },
        }

        with patch.object(
            stock_manager.time,
            "time",
            return_value=current_start - 3600,
        ):
            row = manager._build_regular_session_row(
                "dow", "DOW", "^DJI", meta, points
            )

        self.assertEqual(row["session_state"], "previous")
        self.assertAlmostEqual(row["change_percent"], -1.0)
        self.assertEqual(len(row["trend"]), 7)

    def test_previous_session_rows_mark_market_data_stale(self):
        manager = self.make_manager()
        manager.last_update = 0
        manager._fetch_instrument = Mock(
            side_effect=[
                ({
                    "price": 100,
                    "change_percent": 1,
                    "trend": [1, 2, 3, 4],
                    "session_state": "previous",
                }, None)
                for _ in manager.INSTRUMENTS
            ]
        )

        self.assertTrue(manager.update_stock_data())
        self.assertTrue(manager.is_stale)

    def test_fetch_requests_five_days_without_premarket(self):
        manager = self.make_manager()
        start = datetime(
            2026, 6, 10, 14, 30, tzinfo=timezone.utc
        ).timestamp()
        response = Mock(status_code=200)
        response.json.return_value = {
            "chart": {
                "result": [{
                    "meta": {
                        "exchangeTimezoneName": "UTC",
                        "currentTradingPeriod": {
                            "regular": {
                                "start": start,
                                "end": start + 23400,
                            }
                        },
                    },
                    "timestamp": [int(start), int(start + 300)],
                    "indicators": {
                        "quote": [{
                            "open": [100.0, None],
                            "close": [100.5, 101.0],
                        }]
                    },
                }]
            }
        }
        manager.session.get = Mock(return_value=response)

        with patch.object(
            stock_manager.time,
            "time",
            return_value=start + 600,
        ):
            row, status = manager._fetch_instrument(
                "sp500", "S&P", "^GSPC"
            )

        self.assertIsNone(status)
        self.assertEqual(row["session_state"], "open")
        self.assertEqual(
            manager.session.get.call_args.kwargs["params"],
            {
                "interval": "5m",
                "range": "5d",
                "includePrePost": "false",
            },
        )

    def test_partial_refresh_merges_cached_rows(self):
        manager = self.make_manager()
        manager.market_data = {
            "dow": {"price": 40000, "change_percent": -0.1},
        }
        manager.last_update = 0
        manager._fetch_instrument = Mock(
            side_effect=[
                ({"price": 6100, "change_percent": 0.5}, None),
                (None, 429),
            ]
        )

        self.assertTrue(manager.update_stock_data())
        self.assertIn("sp500", manager.market_data)
        self.assertIn("dow", manager.market_data)
        self.assertTrue(manager.is_stale)
        self.assertTrue(manager.refresh_error)

    def test_rate_limit_keeps_cached_data_and_sets_bounded_retry(self):
        manager = self.make_manager()
        manager.market_data = {
            "sp500": {"price": 6000, "change_percent": 0.1},
        }
        manager.last_update = 0
        manager._fetch_instrument = Mock(return_value=(None, 429))

        with patch.object(stock_manager.time, "time", return_value=100.0):
            self.assertFalse(manager.update_stock_data())

        self.assertEqual(manager.market_data["sp500"]["price"], 6000)
        self.assertEqual(manager.next_retry_at, 130.0)
        self.assertTrue(manager.is_stale)
        self.assertTrue(manager.refresh_error)

    def test_no_data_renders_unavailable_rows_instead_of_blank_frame(self):
        manager = self.make_manager()
        manager.market_data = {}
        manager.next_retry_at = float("inf")

        self.assertTrue(manager.display_stocks(force_clear=True))
        self.assertEqual(manager.display_manager.image.size, (64, 64))
        self.assertEqual(manager.display_manager.updated, 1)


if __name__ == "__main__":
    unittest.main()
