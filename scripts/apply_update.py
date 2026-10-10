#!/usr/bin/env python3
"""Apply a verified local update bundle on the Pi, with a source/config backup.
Never reads, replaces, or removes private credentials or authorization caches.
"""
import argparse
import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tempfile
import time
import zipfile

RETIRED = {'stock_news', 'odds_ticker', 'news_manager', 'of_the_day', 'youtube', 'text_display'}
PRIVATE = {'config/config_secrets.json', 'config/spotify_auth.json', 'credentials.json', 'token.pickle'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_target(root, name):
    root = root.resolve()
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] in {'.git', '.deployment-backups'} or name in PRIVATE:
        raise ValueError(f'Unsafe update path: {name}')
    target = root.joinpath(*path.parts)
    if target.resolve().is_relative_to(root.resolve()) is False:
        raise ValueError(f'Update path leaves project: {name}')
    if any(root.joinpath(*path.parts[:length]).is_symlink() for length in range(1, len(path.parts) + 1)):
        raise ValueError(f'Symlink update target: {name}')
    return target


def validate_write_access(target):
    if target.exists() and not target.is_file():
        raise ValueError(f'Update target is not a regular file: {target}')
    parent = target.parent
    while not parent.exists():
        parent = parent.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
        raise PermissionError(f'Project directory is not writable: {parent}. Nothing has been updated.')


def migrate_config(config):
    """Remove obsolete settings while retaining actual Pi settings and music."""
    durations = config.get('display', {}).get('display_durations', {})
    for key in RETIRED:
        config.pop(key, None)
        durations.pop(key, None)
    for key in ('display_format', 'scroll_delay', 'scroll_speed', 'toggle_chart', 'dynamic_duration',
                'min_duration', 'max_duration', 'duration_buffer', 'symbols'):
        config.get('stocks', {}).pop(key, None)
    for key in ('display_format', 'symbols', 'update_interval'):
        config.get('crypto', {}).pop(key, None)
    return config


def write_file(target, data, mode):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare(root, bundle):
    """Validate the entire bundle and deployment before any file/service change."""
    root = Path(root)
    with zipfile.ZipFile(bundle) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        if head != manifest['base_commit']:
            raise ValueError('Pi commit differs from the reviewed baseline. Stop and review before updating.')
        updates = []
        for entry in manifest['files']:
            name = entry['path']; target = safe_target(root, name)
            validate_write_access(target)
            old = target.read_bytes() if target.is_file() else None
            if name != 'config/config.json' and (digest(old) if old is not None else None) != entry['before']:
                raise ValueError(f'Pi file changed or is unexpected: {name}. Nothing has been updated.')
            data = None if entry['after'] is None else archive.read('files/' + name)
            if data is not None and digest(data) != entry['after']:
                raise ValueError(f'Bundle checksum failed: {name}')
            if name == 'config/config.json':
                if old is None:
                    raise ValueError('Pi main configuration is missing.')
                data = (json.dumps(migrate_config(json.loads(old)), indent=4) + '\n').encode()
            if data is not None and name.endswith('.py'):
                ast.parse(data, filename=name)
            mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else entry['mode']
            updates.append((name, target, old, data, mode))
    if len({row[0] for row in updates}) != len(updates):
        raise ValueError('Duplicate update targets.')
    return updates


def backup(root, updates):
    directory = Path(root) / '.deployment-backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=datetime.now().strftime('%Y%m%d-%H%M%S-'), suffix='.zip', dir=directory)
    os.close(fd)
    entries = []
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, target, old, data, mode in updates:
            entries.append({'path': name, 'existed': old is not None, 'mode': mode,
                            'applied': digest(data) if data is not None else None})
            if old is not None:
                archive.writestr('before/' + name, old)
        archive.writestr('rollback.json', json.dumps(entries))
    return Path(path)


def restore(root, backup_path, check_current=True):
    with zipfile.ZipFile(backup_path) as archive:
        rows = []
        for entry in json.loads(archive.read('rollback.json')):
            target = safe_target(Path(root), entry['path'])
            validate_write_access(target)
            current = target.read_bytes() if target.is_file() else None
            if check_current and (digest(current) if current is not None else None) != entry['applied']:
                raise ValueError(f'Changed since deployment: {entry["path"]}. Review before rollback.')
            data = archive.read('before/' + entry['path']) if entry['existed'] else None
            rows.append((target, data, entry['mode']))
    for target, data, mode in rows:
        if data is None:
            target.unlink(missing_ok=True)
        else:
            write_file(target, data, mode)


def control(action):
    subprocess.run(['sudo', 'systemctl', action, 'ledmatrix.service'], check=True)


def healthy_since(started):
    try:
        state = json.loads(Path('/tmp/led_matrix_status.json').read_text())
        return state.get('timestamp', 0) >= started
    except (OSError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path('/home/jayallen7/LEDMatrix'))
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--rollback', type=Path)
    parser.add_argument('--dashboard', action='store_true')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if bool(args.bundle) == bool(args.rollback):
        parser.error('Choose --bundle or --rollback.')
    if args.rollback:
        # Verify first, before interrupting the service.
        with zipfile.ZipFile(args.rollback) as archive:
            for entry in json.loads(archive.read('rollback.json')):
                target = safe_target(args.project, entry['path'])
                validate_write_access(target)
                current = target.read_bytes() if target.is_file() else None
                if (digest(current) if current is not None else None) != entry['applied']:
                    raise ValueError(f'Changed since deployment: {entry["path"]}')
        if args.check_only:
            print('Rollback preflight passed. Nothing changed.')
            return
        control('stop')
        try:
            restore(args.project, args.rollback)
        finally:
            control('start')
        print('Source and configuration rolled back. Reinstall the desired dashboard service separately.')
        return
    updates = prepare(args.project, args.bundle)
    print(f'Preflight passed for {len(updates)} files. Private credentials and Spotify cache are excluded.', flush=True)
    if args.check_only:
        return
    backup_path = backup(args.project, updates)
    print(f'Rollback backup: {backup_path}', flush=True)
    control('stop')
    started = time.time()
    try:
        for name, target, old, data, mode in updates:
            if data is None:
                target.unlink(missing_ok=True)
            else:
                write_file(target, data, mode)
        control('start')
        for _ in range(45):
            if healthy_since(started):
                break
            time.sleep(1)
        else:
            raise RuntimeError('New display did not publish health within 45 seconds.')
    except Exception:
        print('Update failed; restoring previous source and settings.', flush=True)
        control('stop')
        restore(args.project, backup_path, check_current=False)
        control('start')
        raise
    print('Display is reporting healthy after the update.', flush=True)
    if args.dashboard:
        try:
            subprocess.run(['sudo', 'bash', str(args.project / 'configure_web_sudo.sh')], check=True)
            subprocess.run(['sudo', 'bash', str(args.project / 'install_web_service.sh')], check=True)
        except subprocess.CalledProcessError:
            print('Display update succeeded; dashboard setup failed. Complete the README dashboard steps manually.')
            raise SystemExit(2)
    print('Verify clock, weather, markets, sports, and Spotify on the physical panel.')


if __name__ == '__main__':
    main()
