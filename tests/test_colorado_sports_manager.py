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
from src import colorado_sports_manager


class MemoryCache:
    def load_cache(self, key):
        return None

    def set(self, key, data):
        pass


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


class ColoradoSportsManagerTests(unittest.TestCase):
    def make_manager(self):
        config = {
            "colorado_sports": {
                "enabled": True,
                "polling_interval": 30,
                "stale_timeout": 120,
            }
        }
        with patch.object(
            colorado_sports_manager,
            "CacheManager",
            return_value=MemoryCache(),
        ):
            return colorado_sports_manager.ColoradoSportsManager(
                config,
                FakeDisplay(),
            )

    @staticmethod
    def event(state="in", home="COL", away="VGK"):
        return {
            "id": "game-1",
            "competitions": [{
                "status": {
                    "type": {
                        "state": state,
                        "shortDetail": "2nd 10:00",
                    },
                    "displayClock": "10:00",
                    "period": 2,
                },
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": "3",
                        "team": {"abbreviation": home},
                    },
                    {
                        "homeAway": "away",
                        "score": "2",
                        "team": {"abbreviation": away},
                    },
                ],
            }],
        }

    def test_filters_to_live_colorado_team(self):
        manager = self.make_manager()
        team = manager.TEAMS[0]

        live = manager._parse_event(self.event(), team)
        final = manager._parse_event(self.event(state="post"), team)
        unrelated = manager._parse_event(
            self.event(home="VGK", away="DAL"),
            team,
        )

        self.assertEqual(live["league"], "NHL")
        self.assertIsNone(final)
        self.assertIsNone(unrelated)

    def test_rendered_score_card_is_64_square(self):
        manager = self.make_manager()
        game = manager._parse_event(self.event(), manager.TEAMS[0])

        image = manager._render_game(game)

        self.assertEqual(image.size, (64, 64))

    def test_network_failure_expires_old_live_game(self):
        manager = self.make_manager()
        manager.live_games = [{"id": "old", "league": "NHL"}]
        manager.last_success = 1
        manager.last_update = 0
        manager._fetch_league = Mock(side_effect=RuntimeError("offline"))

        with patch.object(
            colorado_sports_manager.time,
            "time",
            return_value=500,
        ):
            manager.update()

        self.assertFalse(manager.has_display_content())


if __name__ == "__main__":
    unittest.main()
