import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeImage:
    def __init__(self, size):
        self.size = size
        self.width, self.height = size
        self.paste_operations = []

    def paste(self, image, position, mask=None):
        self.paste_operations.append((image, position, mask))


class FakeDraw:
    def __init__(self, image):
        self.operations = []
        image.draw_operations = self.operations

    def text(self, position, text, **kwargs):
        self.operations.append(("text", position, text, kwargs))

    def point(self, position, **kwargs):
        self.operations.append(("point", position, kwargs))

    def line(self, points, **kwargs):
        self.operations.append(("line", points, kwargs))

    def polygon(self, points, **kwargs):
        self.operations.append(("polygon", points, kwargs))

    @staticmethod
    def textbbox(position, text, **kwargs):
        del position, kwargs
        return (0, 0, len(text) * 4, 7)


def install_weather_stubs():
    image_module = types.ModuleType("PIL.Image")
    image_module.new = lambda mode, size, color=None: FakeImage(size)
    draw_module = types.ModuleType("PIL.ImageDraw")
    draw_module.Draw = FakeDraw
    pil_module = types.ModuleType("PIL")
    pil_module.Image = image_module
    pil_module.ImageDraw = draw_module

    weather_icons_module = types.ModuleType("src.weather_icons")

    class StubWeatherIcons:
        calls = []

        @classmethod
        def draw_weather_icon(cls, image, icon, x, y, size):
            cls.calls.append((image, icon, x, y, size))

    weather_icons_module.WeatherIcons = StubWeatherIcons

    cache_module = types.ModuleType("src.cache_manager")
    cache_module.CacheManager = Mock
    web_module = types.ModuleType("web_interface_v2")
    web_module.increment_api_counter = Mock()
    requests_module = types.ModuleType("requests")
    requests_module.get = Mock()

    modules = {
        "PIL": pil_module,
        "PIL.Image": image_module,
        "PIL.ImageDraw": draw_module,
        "freetype": types.ModuleType("freetype"),
        "requests": requests_module,
        "src.weather_icons": weather_icons_module,
        "src.cache_manager": cache_module,
        "web_interface_v2": web_module,
    }
    saved = {name: sys.modules.get(name) for name in modules}
    for name, module in modules.items():
        sys.modules[name] = module
    return saved, StubWeatherIcons


SAVED_MODULES, StubWeatherIcons = install_weather_stubs()
sys.modules.pop("src.weather_manager", None)
from src.weather_manager import WeatherManager

for module_name, original_module in SAVED_MODULES.items():
    if original_module is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = original_module


class FakeMatrix:
    width = 64
    height = 64


class FakeDisplay:
    matrix = FakeMatrix()
    extra_small_font = object()
    regular_font = object()

    def __init__(self):
        self.image = None
        self.updated = 0
        self.cleared = 0

    def clear(self):
        self.cleared += 1

    def update_display(self):
        self.updated += 1


class WeatherForecastTests(unittest.TestCase):
    def make_manager(self):
        manager = object.__new__(WeatherManager)
        manager.display_manager = FakeDisplay()
        manager.COLORS = {
            "text": (255, 255, 255),
            "highlight": (255, 255, 0),
            "dim": (128, 128, 128),
        }
        manager.daily_forecast = [
            {
                "date": day,
                "temp_low": low,
                "temp_high": high,
                "icon": "01d",
                "condition": "Clear",
            }
            for day, low, high in (
                ("Mon", 41, 68),
                ("Tue", 42, 69),
                ("Wed", 43, 70),
                ("Thu", 44, 71),
            )
        ]
        manager.last_daily_state = None
        StubWeatherIcons.calls = []
        return manager

    def test_forecast_preserves_geometry_and_splits_temperature_colors(self):
        manager = self.make_manager()

        manager.display_daily_forecast(force_clear=True)

        image = manager.display_manager.image
        self.assertEqual(image.size, (64, 64))
        self.assertEqual(manager.display_manager.cleared, 1)
        self.assertEqual(manager.display_manager.updated, 1)
        self.assertEqual(
            [
                (call[2], call[3], call[4])
                for call in StubWeatherIcons.calls
            ],
            [(17, -3, 24), (17, 12, 24), (17, 27, 24), (17, 42, 24)],
        )

        text_operations = image.draw_operations
        day_operations = [
            operation
            for operation in text_operations
            if (
                operation[0] == "text"
                and operation[2] in {"Mon", "Tue", "Wed", "Thu"}
            )
        ]
        self.assertEqual(
            [operation[1] for operation in day_operations],
            [(2, 7), (2, 22), (2, 37), (2, 52)],
        )
        self.assertTrue(
            all(
                operation[3]["fill"] == (255, 255, 255)
                for operation in day_operations
            )
        )

        high = next(operation for operation in text_operations if operation[2] == "68")
        low = next(operation for operation in text_operations if operation[2] == "41")
        separator = next(
            operation
            for operation in text_operations
            if operation[0] == "line"
        )
        self.assertEqual(high[1], (42, 7))
        self.assertEqual(separator[1], (51, 10, 52, 10))
        self.assertEqual(low[1], (54, 7))
        self.assertEqual(high[3]["fill"], (255, 90, 35))
        self.assertEqual(separator[2]["fill"], (255, 255, 255))
        self.assertEqual(low[3]["fill"], (60, 150, 255))

    def test_current_weather_places_high_left_and_low_right(self):
        manager = self.make_manager()
        manager.weather_data = {
            "main": {
                "temp": 76,
                "temp_max": 85,
                "temp_min": 70,
                "humidity": 35,
                "uvi": 3,
            },
            "weather": [{"main": "Clear", "icon": "01d"}],
        }
        manager.get_weather = Mock(return_value=manager.weather_data)
        manager.last_weather_state = None
        runtime_pil = types.ModuleType("PIL")
        runtime_pil.Image = sys.modules["src.weather_manager"].Image
        runtime_pil.ImageDraw = sys.modules["src.weather_manager"].ImageDraw

        with unittest.mock.patch.dict(sys.modules, {"PIL": runtime_pil}):
            manager.display_weather(force_clear=True)

        text_operations = [
            operation
            for operation in manager.display_manager.image.draw_operations
            if operation[0] == "text"
        ]
        high = next(operation for operation in text_operations if operation[2] == "85")
        low = next(operation for operation in text_operations if operation[2] == "70")
        self.assertEqual(high[1], (20, 44))
        self.assertEqual(low[1], (44, 44))
        self.assertEqual(high[3]["fill"], (255, 100, 100))
        self.assertEqual(low[3]["fill"], (100, 150, 255))
        self.assertEqual(
            [operation[1] for operation in manager.display_manager.image.paste_operations],
            [(14, 44), (38, 44)],
        )
        self.assertEqual(StubWeatherIcons.calls[-1][2:], (-3, -5, 33))


if __name__ == "__main__":
    unittest.main()
