import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def install_controller_stubs():
    class Dummy:
        SPOTIFY_PLAYING = "playing"
        SPOTIFY_PAUSED = "paused"
        SPOTIFY_STOPPED = "stopped"

    modules = {
        "src.clock": {"Clock": Dummy},
        "src.weather_manager": {"WeatherManager": Dummy},
        "src.display_manager": {"DisplayManager": Dummy},
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
    saved_modules = {}
    for name, attrs in modules.items():
        saved_modules[name] = sys.modules.get(name)
        module = types.ModuleType(name)
        for attr, value in attrs.items():
            setattr(module, attr, value)
        sys.modules[name] = module
    return saved_modules


SAVED_MODULES = install_controller_stubs()
from src.display_controller import DisplayController

for module_name, original_module in SAVED_MODULES.items():
    if original_module is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = original_module


class ContentManager:
    def __init__(self, available):
        self.available = available

    def has_display_content(self):
        return self.available


class WeatherContentManager:
    def __init__(self, current=False, daily=False):
        self.current = current
        self.daily = daily

    def has_current_weather(self):
        return self.current

    def has_daily_forecast(self):
        return self.daily


class DynamicDisplayModeTests(unittest.TestCase):
    def make_controller(self):
        controller = object.__new__(DisplayController)
        controller.available_modes = [
            "clock",
            "weather_current",
            "weather_daily",
            "stocks",
            "music",
        ]
        controller.current_display_mode = "weather_current"
        controller.current_mode_index = 1
        controller.news_manager = ContentManager(True)
        controller.calendar = ContentManager(False)
        controller.colorado_sports = ContentManager(True)
        controller.music_manager = Mock(enabled=True)
        controller.music_manager.preferred_source = "spotify"
        controller.music_manager.spotify_playback_state = "stopped"
        controller.music_return_mode = None
        controller.music_return_index = None
        controller.display_manager = Mock()
        controller.force_clear = False
        controller.last_switch = 0
        return controller

    def test_inserts_eligible_modes_after_stocks_and_keeps_music_last(self):
        controller = self.make_controller()

        controller._sync_dynamic_modes()

        self.assertEqual(
            controller.available_modes,
            [
                "clock",
                "weather_current",
                "weather_daily",
                "stocks",
                "news_manager",
                "sports_live",
                "music",
            ],
        )
        self.assertEqual(controller.current_display_mode, "weather_current")
        self.assertEqual(controller.current_mode_index, 1)

    def test_removes_empty_current_mode_without_selecting_idle_music(self):
        controller = self.make_controller()
        controller.available_modes.insert(4, "news_manager")
        controller.current_display_mode = "news_manager"
        controller.current_mode_index = 4
        controller.news_manager.available = False
        controller.colorado_sports.available = False
        controller._is_music_playing = Mock(return_value=False)

        controller._sync_dynamic_modes()

        self.assertEqual(controller.current_display_mode, "clock")
        self.assertEqual(controller.current_mode_index, 0)
        self.assertTrue(controller.force_clear)

    def test_disabled_or_empty_news_never_enters_rotation(self):
        controller = self.make_controller()
        controller.news_manager = None

        controller._sync_dynamic_modes()

        self.assertNotIn("news_manager", controller.available_modes)

        controller.news_manager = ContentManager(False)
        controller.available_modes.insert(4, "news_manager")
        controller._sync_dynamic_modes()

        self.assertNotIn("news_manager", controller.available_modes)

    def test_weather_without_cache_is_skipped_while_clock_remains_available(self):
        controller = self.make_controller()
        controller.weather = WeatherContentManager()
        controller.current_display_mode = "clock"
        controller.current_mode_index = 0
        controller._is_music_playing = Mock(return_value=False)

        controller._sync_dynamic_modes()

        self.assertNotIn("weather_current", controller.available_modes)
        self.assertNotIn("weather_daily", controller.available_modes)
        self.assertIn("clock", controller.available_modes)
        self.assertEqual(controller.current_display_mode, "clock")

        controller.weather.current = True
        controller.weather.daily = True
        controller._sync_dynamic_modes()
        self.assertEqual(
            controller.available_modes[:4],
            ["clock", "weather_current", "weather_daily", "stocks"],
        )

    def test_poll_callback_never_changes_or_clears_display(self):
        controller = self.make_controller()

        controller._handle_music_update(
            {"title": "Track", "is_playing": True},
            significant_change=True,
        )

        self.assertEqual(controller.current_display_mode, "weather_current")
        controller.display_manager.clear.assert_not_called()

    def test_music_returns_to_interrupted_mode_after_stop(self):
        controller = self.make_controller()

        self.assertTrue(controller._enter_music_mode(10))
        self.assertEqual(controller.current_display_mode, "music")
        self.assertEqual(controller.music_return_mode, "weather_current")
        controller.display_manager.clear.assert_not_called()

        self.assertTrue(controller._return_from_music(20, "playback stopped"))

        self.assertEqual(controller.current_display_mode, "weather_current")
        self.assertEqual(controller.current_mode_index, 1)
        self.assertTrue(controller.force_clear)
        controller.music_manager.deactivate_music_display.assert_called_once()

    def test_music_uses_next_normal_mode_if_interrupted_mode_is_gone(self):
        controller = self.make_controller()
        controller._enter_music_mode(10)
        controller.available_modes.remove("weather_current")

        controller._return_from_music(20, "playback stopped")

        self.assertEqual(controller.current_display_mode, "weather_daily")
        self.assertNotEqual(controller.current_display_mode, "music")

    def test_playing_and_pause_grace_hold_music_outside_normal_rotation(self):
        controller = self.make_controller()
        controller.current_display_mode = "music"

        self.assertTrue(controller._music_holds_display("playing"))
        self.assertTrue(controller._music_holds_display("paused"))
        self.assertFalse(controller._music_holds_display("stopped"))

    def test_non_spotify_source_keeps_legacy_playback_detection(self):
        controller = self.make_controller()
        controller.music_manager.preferred_source = "ytm"
        controller._is_music_playing = Mock(return_value=True)

        self.assertEqual(
            controller._get_music_playback_state(10),
            "playing",
        )


if __name__ == "__main__":
    unittest.main()
