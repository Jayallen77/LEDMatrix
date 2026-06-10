import sys
import types
import unittest
from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from unittest.mock import Mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeTimezone(tzinfo):
    def utcoffset(self, dt):
        del dt
        return timedelta(0)

    def dst(self, dt):
        del dt
        return timedelta(0)

    def tzname(self, dt):
        del dt
        return "UTC"

    def localize(self, value):
        return value.replace(tzinfo=self)


class FakeFont:
    def __init__(self, kind):
        self.kind = kind


class FakeImage:
    def __init__(self, size):
        self.size = size
        self.width, self.height = size


class FakeDraw:
    def __init__(self, image):
        self.operations = []
        image.draw_operations = self.operations

    @staticmethod
    def textbbox(position, text, font):
        del position
        dimensions = {
            "time": (len(text) * 8, 20),
            "date": (len(text) * 5, 12),
            "temperature": (len(text) * 5, 8),
        }
        width, height = dimensions[font.kind]
        return (0, 0, width, height)

    def text(self, position, text, **kwargs):
        self.operations.append(("text", position, text, kwargs))


def install_clock_stubs():
    image_module = types.ModuleType("PIL.Image")
    image_module.new = lambda mode, size, color=None: FakeImage(size)
    draw_module = types.ModuleType("PIL.ImageDraw")
    draw_module.Draw = FakeDraw
    font_module = types.ModuleType("PIL.ImageFont")
    font_module.truetype = Mock()
    font_module.load_default = Mock()
    pil_module = types.ModuleType("PIL")
    pil_module.Image = image_module
    pil_module.ImageDraw = draw_module
    pil_module.ImageFont = font_module

    pytz_module = types.ModuleType("pytz")
    pytz_module.utc = FakeTimezone()
    pytz_module.timezone = lambda name: FakeTimezone()
    pytz_module.exceptions = types.SimpleNamespace(
        UnknownTimeZoneError=ValueError
    )

    config_module = types.ModuleType("src.config_manager")
    config_module.ConfigManager = Mock
    display_module = types.ModuleType("src.display_manager")
    display_module.DisplayManager = Mock

    modules = {
        "PIL": pil_module,
        "PIL.Image": image_module,
        "PIL.ImageDraw": draw_module,
        "PIL.ImageFont": font_module,
        "pytz": pytz_module,
        "src.config_manager": config_module,
        "src.display_manager": display_module,
    }
    saved = {name: sys.modules.get(name) for name in modules}
    for name, module in modules.items():
        sys.modules[name] = module
    return saved


SAVED_CLOCK_MODULES = install_clock_stubs()
sys.modules.pop("src.clock", None)
from src.clock import Clock

for module_name, original_module in SAVED_CLOCK_MODULES.items():
    if original_module is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = original_module


def install_controller_stubs():
    class Dummy:
        SPOTIFY_PLAYING = "playing"
        SPOTIFY_PAUSED = "paused"
        SPOTIFY_STOPPED = "stopped"

    modules = {
        "src.clock": {"Clock": Dummy},
        "src.weather_manager": {"WeatherManager": Dummy},
        "src.display_manager": {"DisplayManager": Dummy},
        "src.config_manager": {"ConfigManager": Dummy},
        "src.cache_manager": {"CacheManager": Dummy},
        "src.stock_manager": {"StockManager": Dummy},
        "src.stock_news_manager": {"StockNewsManager": Dummy},
        "src.odds_ticker_manager": {"OddsTickerManager": Dummy},
        "src.nhl_managers": {
            "NHLLiveManager": Dummy,
            "NHLRecentManager": Dummy,
            "NHLUpcomingManager": Dummy,
        },
        "src.nba_managers": {
            "NBALiveManager": Dummy,
            "NBARecentManager": Dummy,
            "NBAUpcomingManager": Dummy,
        },
        "src.mlb_manager": {
            "MLBLiveManager": Dummy,
            "MLBRecentManager": Dummy,
            "MLBUpcomingManager": Dummy,
        },
        "src.milb_manager": {
            "MiLBLiveManager": Dummy,
            "MiLBRecentManager": Dummy,
            "MiLBUpcomingManager": Dummy,
        },
        "src.soccer_managers": {
            "SoccerLiveManager": Dummy,
            "SoccerRecentManager": Dummy,
            "SoccerUpcomingManager": Dummy,
        },
        "src.nfl_managers": {
            "NFLLiveManager": Dummy,
            "NFLRecentManager": Dummy,
            "NFLUpcomingManager": Dummy,
        },
        "src.ncaa_fb_managers": {
            "NCAAFBLiveManager": Dummy,
            "NCAAFBRecentManager": Dummy,
            "NCAAFBUpcomingManager": Dummy,
        },
        "src.ncaa_baseball_managers": {
            "NCAABaseballLiveManager": Dummy,
            "NCAABaseballRecentManager": Dummy,
            "NCAABaseballUpcomingManager": Dummy,
        },
        "src.ncaam_basketball_managers": {
            "NCAAMBasketballLiveManager": Dummy,
            "NCAAMBasketballRecentManager": Dummy,
            "NCAAMBasketballUpcomingManager": Dummy,
        },
        "src.youtube_display": {"YouTubeDisplay": Dummy},
        "src.calendar_manager": {"CalendarManager": Dummy},
        "src.text_display": {"TextDisplay": Dummy},
        "src.music_manager": {
            "MusicManager": Dummy,
            "MusicSource": types.SimpleNamespace(NONE="none"),
        },
        "src.of_the_day_manager": {"OfTheDayManager": Dummy},
        "src.news_manager": {"NewsManager": Dummy},
        "src.colorado_sports_manager": {"ColoradoSportsManager": Dummy},
    }
    saved = {}
    for name, attrs in modules.items():
        saved[name] = sys.modules.get(name)
        module = types.ModuleType(name)
        for attr, value in attrs.items():
            setattr(module, attr, value)
        sys.modules[name] = module
    return saved


SAVED_CONTROLLER_MODULES = install_controller_stubs()
sys.modules.pop("src.display_controller", None)
from src.display_controller import DisplayController

sys.modules.pop("src.display_controller", None)
for module_name, original_module in SAVED_CONTROLLER_MODULES.items():
    if original_module is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = original_module


class FakeDisplay:
    def __init__(self):
        self.image = None
        self.draw = None
        self.cleared = 0
        self.updated = 0

    def clear(self):
        self.cleared += 1

    def update_display(self):
        self.updated += 1


class ClockTests(unittest.TestCase):
    def make_clock(self):
        clock = object.__new__(Clock)
        clock.config = {"weather": {"units": "imperial"}}
        clock.clock_config = {"update_interval": 1}
        clock.display_manager = FakeDisplay()
        clock.weather_provider = None
        clock.timezone = FakeTimezone()
        clock.width = 64
        clock.height = 64
        clock.time_section_height = 42
        clock.date_section_height = 22
        clock.time_font = FakeFont("time")
        clock.date_font = FakeFont("date")
        clock.temperature_font = FakeFont("temperature")
        clock.time_color = (255, 255, 255)
        clock.date_color = (180, 180, 180)
        return clock

    @staticmethod
    def operation(image, text):
        return next(
            operation
            for operation in image.draw_operations
            if operation[0] == "text" and operation[2] == text
        )

    def test_layout_preserves_time_and_adds_centered_temperature(self):
        clock = self.make_clock()
        clock.weather_provider = types.SimpleNamespace(
            weather_data={"main": {"temp": 72}},
            weather_config={"units": "imperial"},
            forecast_data=None,
        )
        clock._get_current_datetime = Mock(
            return_value=datetime(2026, 6, 10, 12, 22, tzinfo=clock.timezone)
        )

        clock.display_time(force_clear=True)

        image = clock.display_manager.image
        time_operation = self.operation(image, "12:22")
        date_operation = self.operation(image, "JUN 10")
        temperature_operation = self.operation(image, "72°")
        self.assertEqual(time_operation[1], (12, 11))
        self.assertEqual(date_operation[1], (17, 36))
        self.assertEqual(temperature_operation[1], (24, 54))
        self.assertEqual(temperature_operation[1][1] + 8, 62)
        self.assertEqual(time_operation[3]["fill"], (220, 240, 255))
        self.assertEqual(date_operation[3]["fill"], (190, 225, 255))

    def test_phase_colors_keep_time_and_date_in_matching_palettes(self):
        expected = {
            "sunrise": ((255, 235, 165), (255, 210, 95)),
            "day": ((220, 240, 255), (190, 225, 255)),
            "sunset": ((255, 145, 45), (190, 105, 225)),
            "night": ((70, 110, 180), (55, 85, 145)),
            "late_night": ((135, 50, 35), (130, 75, 25)),
        }

        self.assertEqual(Clock.PHASE_COLORS, expected)
        self.assertNotEqual(Clock.PHASE_COLORS["day"][0], (255, 255, 255))

    def test_missing_temperature_hides_temperature_line(self):
        clock = self.make_clock()
        clock._get_current_datetime = Mock(
            return_value=datetime(2026, 6, 10, 12, 22, tzinfo=clock.timezone)
        )

        clock.display_time(force_clear=True)

        rendered_text = [
            operation[2]
            for operation in clock.display_manager.image.draw_operations
            if operation[0] == "text"
        ]
        self.assertEqual(rendered_text, ["12:22", "JUN 10"])

    def test_temperature_units_gradient_and_night_dimming(self):
        clock = self.make_clock()
        clock.weather_provider = types.SimpleNamespace(
            weather_data={"main": {"temp": 0}},
            weather_config={"units": "metric"},
        )

        temperature = clock._get_temperature()

        self.assertEqual(temperature["text"], "0°")
        self.assertEqual(temperature["fahrenheit"], 32)
        self.assertEqual(clock._temperature_color(20), (45, 100, 255))
        self.assertEqual(clock._temperature_color(32), (45, 100, 255))
        self.assertEqual(clock._temperature_color(72), (205, 255, 215))
        self.assertEqual(clock._temperature_color(89), (255, 45, 35))
        middle = clock._temperature_color(41)
        self.assertNotEqual(middle, clock._temperature_color(32))
        self.assertNotEqual(middle, clock._temperature_color(50))
        self.assertEqual(
            clock._dim_color((255, 45, 35)),
            (128, 22, 18),
        )

    def test_fallback_day_phases_match_requested_boundaries(self):
        clock = self.make_clock()
        phases = {
            (5, 0): "sunrise",
            (7, 30): "day",
            (18, 30): "sunset",
            (21, 0): "night",
            (0, 0): "late_night",
        }
        for (hour, minute), expected in phases.items():
            current = datetime(
                2026,
                6,
                10,
                hour,
                minute,
                tzinfo=clock.timezone,
            )
            self.assertEqual(clock._get_day_phase(current), expected)

    def test_cached_sun_times_are_parsed_without_weather_fetch(self):
        clock = self.make_clock()
        provider = types.SimpleNamespace(
            forecast_data={
                "daily": {
                    "time": ["2026-06-10"],
                    "sunrise": ["2026-06-10T06:00"],
                    "sunset": ["2026-06-10T20:30"],
                }
            },
            get_weather=Mock(),
        )
        clock.set_weather_provider(provider)
        current = datetime(
            2026,
            6,
            10,
            6,
            15,
            tzinfo=clock.timezone,
        )

        sunrise, sunset = clock._get_sun_times(current)

        self.assertEqual((sunrise.hour, sunrise.minute), (6, 0))
        self.assertEqual((sunset.hour, sunset.minute), (20, 30))
        self.assertEqual(
            clock._get_day_phase(current, sunrise, sunset),
            "sunrise",
        )
        provider.get_weather.assert_not_called()

    def test_stale_cached_sun_times_fall_back_to_local_phases(self):
        clock = self.make_clock()
        clock.weather_provider = types.SimpleNamespace(
            forecast_data={
                "daily": {
                    "time": ["2026-06-09"],
                    "sunrise": ["2026-06-09T06:00"],
                    "sunset": ["2026-06-09T20:30"],
                }
            }
        )
        current = datetime(
            2026,
            6,
            10,
            12,
            0,
            tzinfo=clock.timezone,
        )

        sunrise, sunset = clock._get_sun_times(current)

        self.assertIsNone(sunrise)
        self.assertIsNone(sunset)
        self.assertEqual(clock._get_day_phase(current, sunrise, sunset), "day")

    def test_redraw_state_tracks_temperature_and_phase(self):
        clock = self.make_clock()
        provider = types.SimpleNamespace(
            weather_data={"main": {"temp": 72}},
            weather_config={"units": "imperial"},
            forecast_data=None,
        )
        clock.set_weather_provider(provider)
        moments = [
            datetime(2026, 6, 10, 12, 22, tzinfo=clock.timezone),
            datetime(2026, 6, 10, 12, 22, tzinfo=clock.timezone),
            datetime(2026, 6, 10, 12, 22, tzinfo=clock.timezone),
            datetime(2026, 6, 10, 0, 22, tzinfo=clock.timezone),
        ]
        clock._get_current_datetime = Mock(side_effect=moments)

        clock.display_time()
        clock.display_time()
        self.assertEqual(clock.display_manager.updated, 1)

        provider.weather_data["main"]["temp"] = 73
        clock.display_time()
        self.assertEqual(clock.display_manager.updated, 2)

        clock.display_time()
        self.assertEqual(clock.display_manager.updated, 3)

    def test_controller_attaches_existing_weather_without_fetching(self):
        controller = object.__new__(DisplayController)
        controller.clock = Mock()
        controller.weather = types.SimpleNamespace(get_weather=Mock())

        controller._attach_clock_weather()

        controller.clock.set_weather_provider.assert_called_once_with(
            controller.weather
        )
        controller.weather.get_weather.assert_not_called()


if __name__ == "__main__":
    unittest.main()
