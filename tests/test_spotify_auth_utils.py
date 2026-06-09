import os
import pwd
import stat
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.spotify_auth_utils import (
    ensure_spotify_cache_access,
    invalidate_spotify_cache,
    log_spotify_cache_diagnostics,
)


class SpotifyAuthUtilsTests(unittest.TestCase):
    def test_diagnostics_report_read_and_write_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "spotify_auth.json"
            cache_path.write_text('{"access_token": "token"}')
            os.chmod(cache_path, 0o600)

            diagnostics = log_spotify_cache_diagnostics(
                str(cache_path),
                expected_owner=pwd.getpwuid(os.getuid()).pw_name,
            )

            self.assertTrue(diagnostics["exists"])
            self.assertTrue(diagnostics["readable"])
            self.assertTrue(diagnostics["writable"])
            self.assertEqual(diagnostics["mode"], 0o600)

    def test_ensure_cache_access_sets_runtime_owner_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "spotify_auth.json"
            cache_path.write_text('{"access_token": "token"}')
            os.chmod(cache_path, 0o644)
            current_user = pwd.getpwuid(os.getuid()).pw_name

            result = ensure_spotify_cache_access(
                str(cache_path),
                runtime_user=current_user,
            )

            self.assertTrue(result)
            self.assertEqual(stat.S_IMODE(cache_path.stat().st_mode), 0o600)
            self.assertEqual(cache_path.stat().st_uid, os.getuid())

    def test_invalidate_spotify_cache_removes_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "spotify_auth.json"
            cache_path.write_text('{"access_token": "token"}')

            self.assertTrue(invalidate_spotify_cache(str(cache_path)))
            self.assertFalse(cache_path.exists())


if __name__ == "__main__":
    unittest.main()
