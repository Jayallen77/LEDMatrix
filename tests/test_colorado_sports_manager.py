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
        self.pastes = []

    def paste(self, image, position, mask=None):
        self.pastes.append((image, position, mask))


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

    def ellipse(self, points, **kwargs):
        self.operations.append(("ellipse", points, kwargs))


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
    def event(
        state="in",
        home="COL",
        away="VGK",
        short_detail="2nd 10:00",
        period=2,
        clock="10:00",
        situation=None,
    ):
        return {
            "id": "game-1",
            "competitions": [{
                "status": {
                    "type": {
                        "state": state,
                        "shortDetail": short_detail,
                    },
                    "displayClock": clock,
                    "period": period,
                },
                "situation": situation or {},
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

    @staticmethod
    def render(manager, game):
        with (
            patch.object(
                colorado_sports_manager.Image,
                "new",
                side_effect=lambda mode, size, color=None: FakeImage(size),
            ),
            patch.object(
                colorado_sports_manager.ImageDraw,
                "Draw",
                side_effect=FakeDraw,
            ),
        ):
            return manager._render_game(game)

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
        self.assertTrue(live["home"]["is_colorado"])
        self.assertFalse(live["away"]["is_colorado"])
        self.assertIsNone(final)
        self.assertIsNone(unrelated)

    def test_rendered_score_card_is_64_square_and_emphasizes_colorado(self):
        manager = self.make_manager()
        game = manager._parse_event(self.event(), manager.TEAMS[0])
        manager._load_team_logo = Mock(return_value=None)

        image = self.render(manager, game)

        self.assertEqual(image.size, (64, 64))
        text_operations = [
            operation
            for operation in image.draw_operations
            if operation[0] == "text"
        ]
        header = next(
            operation for operation in text_operations
            if operation[2] == "NHL"
        )
        colorado = next(
            operation for operation in text_operations
            if operation[2] == "COL"
        )
        self.assertEqual(header[3]["fill"], (255, 255, 255))
        self.assertEqual(
            colorado[3]["fill"],
            manager.COLORADO_COLOR,
        )
        self.assertEqual(
            len([
                operation for operation in image.draw_operations
                if operation[0] == "rectangle"
            ]),
            2,
        )

    def test_local_logos_are_cached_and_pasted_when_available(self):
        manager = self.make_manager()

        class FakeLogo:
            def __init__(self):
                self.size = (20, 20)
                self.thumbnail_size = None

            def thumbnail(self, size, resampling):
                del resampling
                self.thumbnail_size = size
                self.size = size

            def copy(self):
                return self

        class FakeSource:
            def __init__(self, logo):
                self.logo = logo

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                del exc_type, exc, traceback

            def convert(self, mode):
                self.mode = mode
                return self.logo

        logo = FakeLogo()
        with (
            patch.object(
                colorado_sports_manager.os.path,
                "isfile",
                return_value=True,
            ),
            patch.object(
                colorado_sports_manager.Image,
                "open",
                return_value=FakeSource(logo),
            ) as image_open,
        ):
            first = manager._load_team_logo("NHL", "COL")
            second = manager._load_team_logo("NHL", "COL")

        self.assertIs(first, logo)
        self.assertIs(second, logo)
        self.assertEqual(logo.thumbnail_size, (11, 11))
        image_open.assert_called_once()

        game = manager._parse_event(self.event(), manager.TEAMS[0])
        manager._load_team_logo = Mock(return_value=logo)
        image = self.render(manager, game)
        self.assertEqual(len(image.pastes), 2)

    def test_mlb_outs_and_league_states_are_compact(self):
        manager = self.make_manager()
        mlb_game = manager._parse_event(
            self.event(
                home="COL",
                away="CHC",
                short_detail="Bot 5th",
                period=5,
                clock="",
                situation={"outs": 1},
            ),
            manager.TEAMS[3],
        )

        self.assertEqual(mlb_game["outs"], 1)
        self.assertEqual(
            manager._format_game_state(mlb_game),
            ("BOT 5", "1 OUT"),
        )
        self.assertEqual(
            manager._format_game_state({
                "league": "NBA",
                "period": 3,
                "clock": "4:22",
                "status": "Q3 4:22",
            }),
            ("Q3 4:22", None),
        )
        self.assertEqual(
            manager._format_game_state({
                "league": "NFL",
                "period": 3,
                "clock": "4:22",
                "status": "3rd Quarter",
            }),
            ("Q3 4:22", None),
        )
        self.assertEqual(
            manager._format_game_state({
                "league": "NHL",
                "period": 2,
                "clock": "08:14",
                "status": "2nd 08:14",
            }),
            ("2nd 08:14", None),
        )
        self.assertEqual(
            manager._format_game_state({
                "league": "MLS",
                "period": 1,
                "clock": "45:00",
                "status": "Halftime",
            }),
            ("HT", None),
        )

    def test_stale_marker_and_geometry_stay_inside_64_square(self):
        manager = self.make_manager()
        game = manager._parse_event(self.event(), manager.TEAMS[0])
        manager.is_stale = True
        manager._load_team_logo = Mock(return_value=None)

        image = self.render(manager, game)

        marker = next(
            operation
            for operation in image.draw_operations
            if operation[0] == "text" and operation[2] == "*"
        )
        self.assertEqual(marker[3]["fill"], (255, 180, 0))
        for operation in image.draw_operations:
            if operation[0] == "text":
                x, y = operation[1]
                self.assertTrue(0 <= x < 64)
                self.assertTrue(0 <= y < 64)
            elif operation[0] in {"line", "rectangle", "ellipse"}:
                self.assertTrue(
                    all(0 <= coordinate < 64 for coordinate in operation[1])
                )

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
