import queue
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def install_music_stubs():
    saved_modules = {}

    try:
        import requests  # noqa: F401
    except ImportError:
        requests_module = types.ModuleType("requests")
        requests_module.exceptions = types.SimpleNamespace(
            RequestException=Exception
        )
        saved_modules["requests"] = sys.modules.get("requests")
        sys.modules["requests"] = requests_module

    try:
        from PIL import Image, ImageEnhance  # noqa: F401
    except ImportError:
        pil_module = types.ModuleType("PIL")
        image_module = types.ModuleType("PIL.Image")
        image_enhance_module = types.ModuleType("PIL.ImageEnhance")
        image_module.Image = object
        pil_module.Image = image_module
        pil_module.ImageEnhance = image_enhance_module
        for name, module in (
            ("PIL", pil_module),
            ("PIL.Image", image_module),
            ("PIL.ImageEnhance", image_enhance_module),
        ):
            saved_modules[name] = sys.modules.get(name)
            sys.modules[name] = module

    spotify_module = types.ModuleType("src.spotify_client")

    class StubSpotifyClient:
        STATE_REAUTH_REQUIRED = "reauth_required"

    spotify_module.SpotifyClient = StubSpotifyClient

    ytm_module = types.ModuleType("src.ytm_client")
    ytm_module.YTMClient = Mock

    for name, module in (
        ("src.spotify_client", spotify_module),
        ("src.ytm_client", ytm_module),
    ):
        saved_modules[name] = sys.modules.get(name)
        sys.modules[name] = module
    return saved_modules


SAVED_MODULES = install_music_stubs()
from src.music_manager import MusicManager, MusicSource

for module_name, original_module in SAVED_MODULES.items():
    if original_module is None:
        sys.modules.pop(module_name, None)
    else:
        sys.modules[module_name] = original_module


def spotify_track(
    title="First Track",
    artist="Artist",
    album="Album",
    is_playing=True,
):
    return {
        "item": {
            "name": title,
            "artists": [{"name": artist}],
            "album": {
                "name": album,
                "images": [{"url": "https://example.invalid/art.jpg"}],
            },
            "duration_ms": 180000,
        },
        "progress_ms": 5000,
        "is_playing": is_playing,
    }


class MusicManagerTests(unittest.TestCase):
    def make_manager(self):
        manager = object.__new__(MusicManager)
        manager.display_manager = Mock()
        manager.spotify = Mock()
        manager.ytm = None
        manager.current_track_info = None
        manager.current_source = MusicSource.NONE
        manager.update_callback = Mock()
        manager.polling_interval = 1
        manager.enabled = True
        manager.preferred_source = "spotify"
        manager.stop_event = threading.Event()
        manager.track_info_lock = threading.Lock()
        manager.spotify_playback_state = MusicManager.SPOTIFY_STOPPED
        manager.spotify_paused_at = None
        manager.album_art_image = None
        manager.last_album_art_url = None
        manager._needs_immediate_full_refresh = False
        manager.ytm_event_data_queue = queue.Queue(maxsize=1)
        manager.is_music_display_active = False
        return manager

    def test_start_and_track_change_update_playback_state(self):
        manager = self.make_manager()

        first_info, first_changed = manager._apply_spotify_playback(
            spotify_track(),
            now=10,
        )
        second_info, second_changed = manager._apply_spotify_playback(
            spotify_track(title="Second Track"),
            now=11,
        )

        self.assertTrue(first_changed)
        self.assertEqual(first_info["title"], "First Track")
        self.assertTrue(second_changed)
        self.assertEqual(second_info["title"], "Second Track")
        self.assertEqual(
            manager.spotify_playback_state,
            MusicManager.SPOTIFY_PLAYING,
        )
        self.assertEqual(manager.current_source, MusicSource.SPOTIFY)

    def test_short_pause_retains_track_and_resume_clears_grace(self):
        manager = self.make_manager()
        manager._apply_spotify_playback(spotify_track(), now=10)

        paused_info, paused_changed = manager._apply_spotify_playback(
            spotify_track(is_playing=False),
            now=20,
        )

        self.assertTrue(paused_changed)
        self.assertEqual(paused_info["title"], "First Track")
        self.assertFalse(paused_info["is_playing"])
        self.assertEqual(
            manager.get_playback_state(now=22.9),
            MusicManager.SPOTIFY_PAUSED,
        )
        self.assertEqual(
            manager.get_playback_state(now=23),
            MusicManager.SPOTIFY_STOPPED,
        )

        manager._apply_spotify_playback(
            spotify_track(is_playing=True),
            now=22.5,
        )

        self.assertEqual(
            manager.get_playback_state(now=30),
            MusicManager.SPOTIFY_PLAYING,
        )
        self.assertIsNone(manager.spotify_paused_at)

    def test_pause_timestamp_is_not_extended_by_repeated_polls(self):
        manager = self.make_manager()
        paused = spotify_track(is_playing=False)

        manager._apply_spotify_playback(paused, now=20)
        manager._apply_spotify_playback(paused, now=22)

        self.assertEqual(manager.spotify_paused_at, 20)
        self.assertEqual(
            manager.get_playback_state(now=23),
            MusicManager.SPOTIFY_STOPPED,
        )

    def test_stop_or_no_playback_deactivates_immediately(self):
        manager = self.make_manager()
        manager._apply_spotify_playback(spotify_track(), now=10)

        stopped_info, changed = manager._apply_spotify_playback(None, now=11)

        self.assertTrue(changed)
        self.assertEqual(stopped_info["title"], "Nothing Playing")
        self.assertEqual(
            manager.get_playback_state(now=11),
            MusicManager.SPOTIFY_STOPPED,
        )
        self.assertEqual(manager.current_source, MusicSource.NONE)

    def test_transient_spotify_error_preserves_last_valid_frame(self):
        manager = self.make_manager()
        manager._apply_spotify_playback(spotify_track(), now=10)
        previous_info = manager.current_track_info.copy()
        manager.update_callback.reset_mock()
        manager.spotify.get_current_track.return_value = None
        manager.spotify.should_retry.return_value = True

        callback_info, changed = manager._poll_spotify_once(now=11)

        self.assertIsNone(callback_info)
        self.assertFalse(changed)
        self.assertEqual(manager.current_track_info, previous_info)
        self.assertEqual(
            manager.spotify_playback_state,
            MusicManager.SPOTIFY_PLAYING,
        )
        manager.update_callback.assert_not_called()

    def test_confirmed_no_playback_notifies_controller(self):
        manager = self.make_manager()
        manager._apply_spotify_playback(spotify_track(), now=10)
        manager.update_callback.reset_mock()
        manager.spotify.get_current_track.return_value = None
        manager.spotify.should_retry.return_value = False

        manager._poll_spotify_once(now=11)

        manager.update_callback.assert_called_once()
        callback_info = manager.update_callback.call_args.args[0]
        self.assertEqual(callback_info["title"], "Nothing Playing")

    def test_spotify_nothing_playing_frame_is_not_drawn_or_cleared(self):
        manager = self.make_manager()
        manager.current_track_info = manager.get_simplified_track_info(
            None,
            MusicSource.NONE,
        )

        self.assertFalse(manager.display(force_clear=True))
        manager.display_manager.clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()
