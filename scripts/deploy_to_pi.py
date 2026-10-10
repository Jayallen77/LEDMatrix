#!/usr/bin/env python3
"""Build a checksummed update; optionally transfer/apply it using interactive SSH.
Only run this from the Mac checkout. No credentials are read or bundled.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import stat
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
GIT = '/Applications/Xcode.app/Contents/Developer/usr/bin/git' if Path('/Applications/Xcode.app/Contents/Developer/usr/bin/git').exists() else 'git'
PRIVATE = {'config/config_secrets.json', 'config/spotify_auth.json', 'credentials.json', 'token.pickle'}


def git(*args):
    return subprocess.check_output([GIT, *args], cwd=ROOT)


def build_bundle(destination):
    base = git('rev-parse', 'HEAD').decode().strip()
    changed = git('diff', '--name-only', '-z', 'HEAD').decode().split('\0')
    added = git('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')
    entries = []
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(changed + added) - {''}):
            if name in PRIVATE or name.startswith(('.git/', '.deployment-backups/')):
                raise ValueError(f'Private or unsafe bundle path: {name}')
            path = ROOT / name
            if path.is_symlink():
                raise ValueError(f'Symlink cannot be deployed: {name}')
            result = subprocess.run([GIT, 'show', f'HEAD:{name}'], cwd=ROOT, capture_output=True)
            old = result.stdout if result.returncode == 0 else None
            new = path.read_bytes() if path.is_file() else None
            if new is not None:
                archive.writestr('files/' + name, new)
            entries.append({'path': name, 'before': hashlib.sha256(old).hexdigest() if old is not None else None,
                            'after': hashlib.sha256(new).hexdigest() if new is not None else None,
                            'mode': stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644})
        archive.writestr('manifest.json', json.dumps({'base_commit': base, 'files': entries}))
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Transfer and apply to the Pi, prompting through SSH as needed.')
    parser.add_argument('--target', default='jayallen7@ledmatrix.local')
    parser.add_argument('--project', default='/home/jayallen7/LEDMatrix')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    directory = Path(tempfile.mkdtemp(prefix='ledmatrix-update-'))
    bundle = args.output or directory / 'update.zip'
    entries = build_bundle(bundle)
    print(f'Prepared {len(entries)} changed files: {bundle}', flush=True)
    if not args.apply:
        print('Nothing deployed. Add --apply to transfer and apply over interactive SSH.')
        return
    # Unique names avoid overwriting another pending update. SSH handles authentication.
    remote_bundle = f'/tmp/{directory.name}.zip'
    remote_apply = f'/tmp/{directory.name}-apply.py'
    subprocess.run(['scp', str(bundle), f'{args.target}:{remote_bundle}'], check=True)
    subprocess.run(['scp', str(ROOT / 'scripts/apply_update.py'), f'{args.target}:{remote_apply}'], check=True)
    command = shlex.join(['python3', remote_apply, '--project', args.project,
                          '--bundle', remote_bundle, '--dashboard'])
    subprocess.run(['ssh', '-t', args.target, command], check=True)
    print('Update applied. Open an SSH tunnel to use the dashboard.')


if __name__ == '__main__':
    main()
