import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config_manager import ConfigManager
from src.dashboard_settings import SettingsStore
from src.runtime_state import atomic_write_json
from web_interface_v2 import DashboardServer


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'config.json'
        self.config = {'clock': {'enabled': True}, 'weather': {'enabled': True},
                       'music': {'enabled': True, 'preferred_source': 'spotify', 'POLLING_INTERVAL_SECONDS': 1},
                       'nfl_scoreboard': {'enabled': False, 'favorite_teams': ['TB']},
                       'display': {'hardware': {'rows': 64, 'brightness': 95},
                                   'display_durations': {'weather_current': 15, 'weather_daily': 10}},
                       'unknown_future_setting': {'preserve': True}}
        self.path.write_text(json.dumps(self.config))
        os.chmod(self.path, 0o640)
        self.store = SettingsStore(self.path)

    def test_save_preserves_music_hardware_and_unknown_fields_with_rollback(self):
        before = self.store.read()
        self.store.save({'revision': before['revision'], 'values': {'brightness': 70, 'weather_seconds': 20}})
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['music'], self.config['music'])
        self.assertEqual(saved['nfl_scoreboard'], self.config['nfl_scoreboard'])
        self.assertEqual(saved['unknown_future_setting'], self.config['unknown_future_setting'])
        self.assertEqual(saved['display']['hardware']['rows'], 64)
        self.assertEqual(saved['display']['hardware']['brightness'], 70)
        self.assertEqual(saved['display']['display_durations']['weather_current'], 20)
        self.assertEqual(saved['display']['display_durations']['weather'], 20)
        self.assertEqual(json.loads(self.path.with_name('config.dashboard-backup.json').read_text()), self.config)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)

    def test_stale_tab_cannot_overwrite_new_settings(self):
        revision = self.store.read()['revision']
        self.store.save({'revision': revision, 'values': {'brightness': 60}})
        with self.assertRaisesRegex(ValueError, 'changed elsewhere'):
            self.store.save({'revision': revision, 'values': {'brightness': 50}})
        self.assertEqual(self.store.read()['values']['brightness'], 60)

    def test_conditional_content_cannot_be_the_only_fallback(self):
        with self.assertRaisesRegex(ValueError, 'ordinary rotation'):
            self.store.save({'revision': self.store.read()['revision'], 'values': {
                'clock_enabled': False, 'weather_enabled': False, 'stocks_enabled': False,
            }})

    def test_invalid_settings_leave_file_unchanged(self):
        original = self.path.read_bytes()
        for changes in ({'brightness': 101}, {'brightness': True}, {'timezone': 'bad/zone'},
                        {'schedule_start': '25:00'}, {'weather_units': 'kelvin'},
                        {'music': {'enabled': False}}, {'stocks_enabled': 'false'},
                        {'sports_refresh_seconds': 300}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.store.save({'revision': self.store.read()['revision'], 'values': changes})
            self.assertEqual(self.path.read_bytes(), original)

    def test_dashboard_returns_only_allowed_settings(self):
        self.config['music']['SPOTIFY_CLIENT_SECRET'] = 'do-not-display'
        self.path.write_text(json.dumps(self.config))
        serialized = json.dumps(self.store.read())
        self.assertNotIn('do-not-display', serialized)
        self.assertNotIn('SPOTIFY_CLIENT_SECRET', serialized)

    def test_failed_atomic_replace_preserves_previous_file(self):
        original = self.path.read_bytes()
        with patch('src.runtime_state.os.replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                atomic_write_json(self.path, {'broken': True})
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('.config.json.*')), [])

    def test_config_manager_refuses_save_when_secrets_cannot_be_stripped(self):
        secret_path = self.path.with_name('secrets.json')
        secret_path.write_text('invalid json')
        manager = ConfigManager(str(self.path), str(secret_path))
        original = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'safely save'):
            manager.save_config({'music': {'SPOTIFY_CLIENT_SECRET': 'private'}})
        self.assertEqual(self.path.read_bytes(), original)


class DashboardHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.path = base / 'config.json'
        self.path.write_text(json.dumps({'clock': {'enabled': True}, 'music': {'enabled': True}}))
        self.status = base / 'status.json'
        self.restart = Mock()
        self.server = DashboardServer(('127.0.0.1', 0), self.path, self.status, base / 'preview.png', self.restart)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.port = self.server.server_port

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, payload=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        body = json.dumps(payload) if payload is not None else None
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def authorized(self):
        return {'Origin': f'http://127.0.0.1:{self.port}', 'X-CSRF-Token': self.server.csrf, 'Content-Type': 'application/json'}

    def test_dashboard_and_settings_load_without_hardware_or_credentials(self):
        code, html = self.request('GET', '/')
        self.assertEqual(code, 200)
        self.assertIn(b'LED Matrix', html)
        code, settings = self.request('GET', '/api/settings')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(settings)['csrf'], self.server.csrf)
        self.assertNotIn(b'SPOTIFY_CLIENT_SECRET', settings)
        self.assertEqual(self.request('GET', '/preview.png')[0], 404)

    def test_rebinding_and_cross_origin_writes_are_rejected(self):
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        payload = {'revision': self.server.settings.read()['revision'], 'values': {'brightness': 40}}
        self.assertEqual(self.request('POST', '/api/save', payload)[0], 403)
        headers = self.authorized(); headers['Origin'] = 'http://evil.example'
        self.assertEqual(self.request('POST', '/api/save', payload, headers)[0], 403)
        self.assertEqual(self.server.settings.read()['values']['brightness'], 95)

    def test_save_and_explicit_apply_are_separate(self):
        settings = self.server.settings.read()
        code, data = self.request('POST', '/api/save', {'revision': settings['revision'], 'values': {'brightness': 50}}, self.authorized())
        self.assertEqual(code, 200)
        self.restart.assert_not_called()
        saved = json.loads(data)
        code, _ = self.request('POST', '/api/restart', {'revision': saved['revision']}, self.authorized())
        self.assertEqual(code, 200)
        self.restart.assert_called_once()

    def test_apply_rejects_old_revision_and_restart_errors_are_visible(self):
        code, _ = self.request('POST', '/api/restart', {'revision': 'old'}, self.authorized())
        self.assertEqual(code, 400)
        self.restart.assert_not_called()
        self.restart.side_effect = RuntimeError('denied')
        code, body = self.request('POST', '/api/restart', {'revision': self.server.settings.read()['revision']}, self.authorized())
        self.assertEqual(code, 503)
        self.assertIn(b'Pi terminal', body)

    def test_stale_health_is_not_reported_as_running(self):
        self.status.write_text(json.dumps({'timestamp': time.time() - 60, 'mode': 'clock'}))
        code, body = self.request('GET', '/api/status')
        self.assertEqual(code, 200)
        self.assertFalse(json.loads(body)['running'])
        self.status.write_text(json.dumps({'timestamp': time.time(), 'mode': 'clock', 'active': True,
                                          'applied_revision': self.server.settings.read()['revision']}))
        _, body = self.request('GET', '/api/status')
        self.assertTrue(json.loads(body)['running'])
        self.assertFalse(json.loads(body)['pending_restart'])

    def test_public_bind_is_refused(self):
        with self.assertRaises(ValueError):
            DashboardServer(('0.0.0.0', 0), self.path)


if __name__ == '__main__':
    unittest.main()
