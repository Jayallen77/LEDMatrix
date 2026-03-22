import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.web_config_utils import apply_config_fragment, apply_secrets_update


class WebConfigUtilsTests(unittest.TestCase):
    def test_apply_config_fragment_merges_v2_music_payload(self):
        existing_config = {
            "clock": {"enabled": True},
            "music": {
                "enabled": False,
                "preferred_source": "ytm",
                "YTM_COMPANION_URL": "http://old-host:9863",
                "POLLING_INTERVAL_SECONDS": 5,
            },
        }
        fragment = json.dumps({
            "music": {
                "enabled": True,
                "preferred_source": "spotify",
                "YTM_COMPANION_URL": "http://new-host:9863",
                "POLLING_INTERVAL_SECONDS": 2,
            }
        })

        updated = apply_config_fragment(existing_config, fragment)

        self.assertTrue(updated["music"]["enabled"])
        self.assertEqual(updated["music"]["preferred_source"], "spotify")
        self.assertEqual(updated["music"]["YTM_COMPANION_URL"], "http://new-host:9863")
        self.assertEqual(updated["music"]["POLLING_INTERVAL_SECONDS"], 2)
        self.assertTrue(updated["clock"]["enabled"])

    def test_apply_secrets_update_merges_json_payload_without_dropping_existing_keys(self):
        existing_secrets = {
            "weather": {"api_key": "old-weather"},
            "youtube": {
                "api_key": "old-youtube",
                "channel_id": "existing-channel",
            },
            "music": {
                "SPOTIFY_CLIENT_ID": "old-id",
                "SPOTIFY_CLIENT_SECRET": "old-secret",
                "SPOTIFY_REDIRECT_URI": "http://old/callback",
            },
            "news": {"api_key": "keep-me"},
        }
        fragment = json.dumps({
            "weather": {"api_key": "new-weather"},
            "youtube": {"api_key": "new-youtube"},
            "music": {
                "SPOTIFY_CLIENT_ID": "new-id",
                "SPOTIFY_CLIENT_SECRET": "new-secret",
                "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8888/callback",
            },
        })

        updated = apply_secrets_update(existing_secrets=existing_secrets, config_data_str=fragment)

        self.assertEqual(updated["weather"]["api_key"], "new-weather")
        self.assertEqual(updated["youtube"]["api_key"], "new-youtube")
        self.assertEqual(updated["youtube"]["channel_id"], "existing-channel")
        self.assertEqual(updated["music"]["SPOTIFY_CLIENT_ID"], "new-id")
        self.assertEqual(updated["music"]["SPOTIFY_CLIENT_SECRET"], "new-secret")
        self.assertEqual(updated["music"]["SPOTIFY_REDIRECT_URI"], "http://127.0.0.1:8888/callback")
        self.assertEqual(updated["news"]["api_key"], "keep-me")

    def test_apply_secrets_update_supports_direct_form_fields(self):
        existing_secrets = {
            "youtube": {"channel_id": "existing-channel"},
        }
        form_data = {
            "weather_api_key": "weather-from-form",
            "youtube_api_key": "youtube-from-form",
            "spotify_client_id": "spotify-id",
            "spotify_client_secret": "spotify-secret",
            "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
        }

        updated = apply_secrets_update(existing_secrets=existing_secrets, form_data=form_data)

        self.assertEqual(updated["weather"]["api_key"], "weather-from-form")
        self.assertEqual(updated["youtube"]["api_key"], "youtube-from-form")
        self.assertEqual(updated["youtube"]["channel_id"], "existing-channel")
        self.assertEqual(updated["music"]["SPOTIFY_CLIENT_ID"], "spotify-id")
        self.assertEqual(updated["music"]["SPOTIFY_CLIENT_SECRET"], "spotify-secret")
        self.assertEqual(updated["music"]["SPOTIFY_REDIRECT_URI"], "http://127.0.0.1:8888/callback")


if __name__ == "__main__":
    unittest.main()
