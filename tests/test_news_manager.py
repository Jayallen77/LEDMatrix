import sys
import types
import unittest
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

    def text(self, *args, **kwargs):
        pass

    def line(self, *args, **kwargs):
        pass


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
        sys.modules["requests"] = requests
        sys.modules["requests.adapters"] = adapters
    if "urllib3.util.retry" not in sys.modules:
        retry = types.ModuleType("urllib3.util.retry")
        retry.Retry = Mock
        sys.modules["urllib3"] = types.ModuleType("urllib3")
        sys.modules["urllib3.util"] = types.ModuleType("urllib3.util")
        sys.modules["urllib3.util.retry"] = retry
    if "src.cache_manager" not in sys.modules:
        cache_module = types.ModuleType("src.cache_manager")
        cache_module.CacheManager = Mock
        sys.modules["src.cache_manager"] = cache_module


install_dependency_stubs()
from src import news_manager


class MemoryCache:
    def __init__(self, cached=None):
        self.cached = cached

    def load_cache(self, key):
        return self.cached

    def set(self, key, data):
        self.cached = {"data": data}


class FakeDisplay:
    width = 64
    height = 64
    extra_small_font = object()
    small_font = object()

    @staticmethod
    def get_text_width(text, font):
        del font
        return len(text) * 4

    def clear(self):
        pass

    def update_display(self):
        pass


class NewsManagerTests(unittest.TestCase):
    def make_manager(self, cache=None, enabled=True, feeds=None):
        config = {
            "news_manager": {
                "enabled": enabled,
                "update_interval": 300,
                "headlines_per_feed": 2,
                "enabled_feeds": feeds if feeds is not None else ["TEST"],
                "custom_feeds": {"TEST": "https://example.test/rss"},
                "rotation_enabled": True,
            },
            "display": {"display_durations": {"news_manager": 60}},
        }
        with patch.object(
            news_manager,
            "CacheManager",
            return_value=cache or MemoryCache(),
        ):
            return news_manager.NewsManager(config, FakeDisplay())

    def test_skips_when_no_feed_is_configured(self):
        manager = self.make_manager(feeds=[])
        manager.update()

        self.assertFalse(manager.has_display_content())

    def test_network_failure_retains_cached_headline(self):
        cached = MemoryCache({
            "data": {
                "headlines": [{"feed": "TEST", "title": "Cached headline"}]
            }
        })
        manager = self.make_manager(cache=cached)
        manager.parse_rss_feed = Mock(side_effect=RuntimeError("offline"))

        manager.fetch_news_data()

        self.assertTrue(manager.has_display_content())
        self.assertTrue(manager.is_stale)

    def test_renders_one_wrapped_64_square_card(self):
        manager = self.make_manager()
        manager.current_headlines = [{
            "feed": "TEST",
            "title": "A compact headline that wraps across the square display",
        }]

        image = manager._render_card()

        self.assertEqual(image.size, (64, 64))


if __name__ == "__main__":
    unittest.main()
