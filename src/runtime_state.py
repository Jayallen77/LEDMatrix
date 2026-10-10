"""Small atomic files shared by the display and the local settings server."""

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import logging
import threading
import time


def config_revision(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_write_json(path, data, default_mode=0o600):
    path = Path(path)
    previous = path.stat() if path.exists() else None
    mode = stat.S_IMODE(previous.st_mode) if previous else default_mode
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, indent=4, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
            if previous and os.geteuid() == 0:
                os.fchown(stream.fileno(), previous.st_uid, previous.st_gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class RuntimeReporter:
    """Publish health off the drawing thread, without owning matrix hardware."""

    def __init__(self, snapshot, path='/tmp/led_matrix_status.json'):
        self.snapshot = snapshot
        self.path = path
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run, name='matrix-health', daemon=True)
        self.thread.start()

    def _run(self):
        reported_error = False
        while not self.stop_event.is_set():
            try:
                data = self.snapshot()
                data['timestamp'] = time.time()
                atomic_write_json(self.path, data, default_mode=0o644)
                reported_error = False
            except Exception as exc:
                if not reported_error:
                    logging.getLogger(__name__).warning('Could not publish display health: %s', exc)
                    reported_error = True
            self.stop_event.wait(1)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
