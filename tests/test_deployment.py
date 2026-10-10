import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('apply_update', ROOT / 'scripts/apply_update.py')
updater = importlib.util.module_from_spec(spec); spec.loader.exec_module(updater)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.before = b'print("old")\n'; self.after = b'print("new")\n'
        (self.root / 'app.py').write_bytes(self.before)
        self.settings = {'clock': {'enabled': True}, 'music': {'enabled': True, 'preferred_source': 'spotify'},
                         'stocks': {'enabled': True, 'symbols': ['USER']}, 'stock_news': {'enabled': False},
                         'display': {'hardware': {'brightness': 61}, 'display_durations': {'clock': 42, 'stock_news': 20}}}
        (self.root / 'config/config.json').write_text(json.dumps(self.settings))
        self.bundle = self.root / 'update.zip'

    def bundle_with(self, path='app.py', before=None, after=None):
        old = self.before if before is None else before
        new = self.after if after is None else after
        rows = [{'path': path, 'before': updater.digest(old), 'after': updater.digest(new), 'mode': 0o644},
                {'path': 'config/config.json', 'before': 'old-settings-hash', 'after': updater.digest(b'{}'), 'mode': 0o644}]
        with zipfile.ZipFile(self.bundle, 'w') as archive:
            archive.writestr('manifest.json', json.dumps({'base_commit': 'baseline', 'files': rows}))
            archive.writestr('files/' + path, new)
            archive.writestr('files/config/config.json', b'{}')
        return self.bundle

    def prepare(self):
        with patch.object(updater.subprocess, 'check_output', return_value='baseline\n'):
            return updater.prepare(self.root, self.bundle)

    def test_preflight_preserves_current_pi_settings_and_private_files(self):
        self.bundle_with()
        secret = self.root / 'config/spotify_auth.json'; secret.write_text('private-token')
        updates = self.prepare()
        config = json.loads(next(row[3] for row in updates if row[0] == 'config/config.json'))
        self.assertEqual(config['display']['hardware']['brightness'], 61)
        self.assertEqual(config['display']['display_durations']['clock'], 42)
        self.assertEqual(config['music'], self.settings['music'])
        self.assertNotIn('stock_news', config)
        self.assertNotIn('symbols', config['stocks'])
        self.assertEqual(secret.read_text(), 'private-token')
        self.assertEqual((self.root / 'app.py').read_bytes(), self.before)

    def test_modified_file_refuses_before_any_mutation(self):
        self.bundle_with(); (self.root / 'app.py').write_bytes(b'new-user-work')
        with self.assertRaisesRegex(ValueError, 'changed or is unexpected'):
            self.prepare()
        self.assertEqual((self.root / 'app.py').read_bytes(), b'new-user-work')

    def test_invalid_python_refuses_preflight(self):
        self.bundle_with(after=b'invalid python :')
        with self.assertRaises(SyntaxError):self.prepare()

    def test_unwritable_directory_refuses_before_service_or_file_changes(self):
        self.bundle_with()
        with patch.object(updater.os, 'access', return_value=False), self.assertRaises(PermissionError):
            self.prepare()
        self.assertEqual((self.root / 'app.py').read_bytes(), self.before)

    def test_private_path_and_traversal_are_refused(self):
        for name in ('config/spotify_auth.json', 'config/config_secrets.json', '../elsewhere', '.git/config'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                updater.safe_target(self.root, name)

    def test_backup_restores_original_source_and_settings(self):
        self.bundle_with(); updates = self.prepare(); backup = updater.backup(self.root, updates)
        for name, target, old, data, mode in updates:
            updater.write_file(target, data, mode)
        updater.restore(self.root, backup)
        self.assertEqual((self.root / 'app.py').read_bytes(), self.before)
        self.assertEqual(json.loads((self.root / 'config/config.json').read_text()), self.settings)

    def test_rollback_refuses_later_user_changes(self):
        self.bundle_with(); updates = self.prepare(); backup = updater.backup(self.root, updates)
        (self.root / 'app.py').write_bytes(b'later-user-change')
        with self.assertRaisesRegex(ValueError, 'Changed since deployment'):
            updater.restore(self.root, backup)
        self.assertEqual((self.root / 'app.py').read_bytes(), b'later-user-change')


if __name__ == '__main__':unittest.main()
