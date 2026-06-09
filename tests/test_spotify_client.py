import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestSpotifyException(Exception):
    def __init__(self, http_status, message):
        super().__init__(message)
        self.http_status = http_status


try:
    import spotipy  # noqa: F401
except ModuleNotFoundError:
    spotipy_module = types.ModuleType("spotipy")
    spotipy_module.Spotify = Mock()
    spotipy_module.exceptions = types.SimpleNamespace(
        SpotifyException=TestSpotifyException
    )
    oauth_module = types.ModuleType("spotipy.oauth2")
    oauth_module.SpotifyOAuth = Mock()
    sys.modules["spotipy"] = spotipy_module
    sys.modules["spotipy.oauth2"] = oauth_module


from src import spotify_client


class SpotifyClientTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.secrets_path = Path(self.temp_dir.name) / "config_secrets.json"
        self.cache_path = Path(self.temp_dir.name) / "spotify_auth.json"
        self.secrets_path.write_text(json.dumps({
            "music": {
                "SPOTIFY_CLIENT_ID": "client-id",
                "SPOTIFY_CLIENT_SECRET": "client-secret",
                "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8888/callback",
            }
        }))
        self.cache_path.write_text(json.dumps({
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_at": 9999999999,
        }))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _client_patches(self, auth_manager, spotify_api):
        return (
            patch.object(spotify_client, "SECRETS_PATH", str(self.secrets_path)),
            patch.object(
                spotify_client,
                "SPOTIFY_AUTH_CACHE_PATH",
                str(self.cache_path),
            ),
            patch.object(spotify_client, "SpotifyOAuth", return_value=auth_manager),
            patch.object(spotify_client.spotipy, "Spotify", return_value=spotify_api),
            patch.object(
                spotify_client,
                "ensure_spotify_cache_access",
                return_value=True,
            ),
            patch.object(
                spotify_client,
                "log_spotify_cache_diagnostics",
                return_value={
                    "exists": True,
                    "readable": True,
                    "writable": True,
                },
            ),
            patch.object(
                spotify_client.spotipy.exceptions,
                "SpotifyException",
                TestSpotifyException,
            ),
        )

    def _start_patches(self, patches):
        for current_patch in patches:
            current_patch.start()
            self.addCleanup(current_patch.stop)

    @staticmethod
    def _auth_manager():
        auth_manager = Mock()
        auth_manager.cache_handler.get_cached_token.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_at": 9999999999,
        }
        auth_manager.get_access_token.return_value = "access-token"
        return auth_manager

    def test_startup_network_failure_recovers_after_backoff(self):
        auth_manager = self._auth_manager()
        auth_manager.get_access_token.side_effect = [
            ConnectionError("network unavailable"),
            "access-token",
        ]
        spotify_api = Mock()
        expected_track = {"item": {"name": "Track"}, "is_playing": True}
        spotify_api.current_playback.return_value = expected_track
        patches = self._client_patches(auth_manager, spotify_api)

        with patch.object(spotify_client.time, "time", return_value=100.0) as now:
            self._start_patches(patches)
            client = spotify_client.SpotifyClient()

            self.assertEqual(client.get_state(), client.STATE_RETRYABLE)
            self.assertIsNone(client.get_current_track())
            self.assertEqual(auth_manager.get_access_token.call_count, 1)

            now.return_value = 102.0
            self.assertEqual(client.get_current_track(), expected_track)

        self.assertEqual(client.get_state(), client.STATE_READY)
        self.assertEqual(auth_manager.get_access_token.call_count, 2)

    def test_retry_backoff_is_capped_at_sixty_seconds(self):
        client = object.__new__(spotify_client.SpotifyClient)
        client.state = client.STATE_RETRYABLE
        client.retry_attempts = 0
        client.next_retry_at = 0.0
        client.last_error = None

        with patch.object(spotify_client.time, "time", return_value=100.0):
            for _ in range(10):
                client._mark_retryable("temporary failure")

        self.assertEqual(client.retry_attempts, 6)
        self.assertEqual(client.next_retry_at, 160.0)

    def test_401_refreshes_and_retries_playback_once(self):
        auth_manager = self._auth_manager()
        spotify_api = Mock()
        expected_track = {"item": {"name": "Recovered"}, "is_playing": True}
        spotify_api.current_playback.side_effect = [
            TestSpotifyException(401, "expired access token"),
            expected_track,
        ]
        self._start_patches(self._client_patches(auth_manager, spotify_api))
        client = spotify_client.SpotifyClient()

        self.assertEqual(client.get_current_track(), expected_track)

        auth_manager.refresh_access_token.assert_called_once_with("refresh-token")
        self.assertEqual(spotify_api.current_playback.call_count, 2)
        self.assertEqual(client.get_state(), client.STATE_READY)

    def test_rejected_refresh_requires_reauthorization(self):
        auth_manager = self._auth_manager()
        auth_manager.refresh_access_token.side_effect = RuntimeError(
            "invalid_grant: refresh token revoked"
        )
        spotify_api = Mock()
        spotify_api.current_playback.side_effect = TestSpotifyException(
            401,
            "expired access token",
        )
        self._start_patches(self._client_patches(auth_manager, spotify_api))
        client = spotify_client.SpotifyClient()

        self.assertIsNone(client.get_current_track())

        self.assertEqual(client.get_state(), client.STATE_REAUTH_REQUIRED)
        self.assertIsNone(client.sp)

    def test_transient_playback_error_keeps_client_retryable(self):
        auth_manager = self._auth_manager()
        spotify_api = Mock()
        spotify_api.current_playback.side_effect = ConnectionError("offline")
        self._start_patches(self._client_patches(auth_manager, spotify_api))
        client = spotify_client.SpotifyClient()

        self.assertIsNone(client.get_current_track())

        self.assertEqual(client.get_state(), client.STATE_RETRYABLE)
        self.assertIs(client.sp, spotify_api)
        self.assertGreater(client.next_retry_at, 0)

    def test_automatic_refresh_rejection_requires_reauthorization(self):
        auth_manager = self._auth_manager()
        spotify_api = Mock()
        spotify_api.current_playback.side_effect = RuntimeError(
            "invalid_grant: refresh token revoked"
        )
        self._start_patches(self._client_patches(auth_manager, spotify_api))
        client = spotify_client.SpotifyClient()

        self.assertIsNone(client.get_current_track())

        self.assertEqual(client.get_state(), client.STATE_REAUTH_REQUIRED)
        self.assertIsNone(client.sp)


if __name__ == "__main__":
    unittest.main()
