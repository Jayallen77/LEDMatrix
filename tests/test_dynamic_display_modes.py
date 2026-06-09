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
        pass

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


if __name__ == "__main__":
    unittest.main()
