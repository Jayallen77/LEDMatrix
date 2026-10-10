#!/usr/bin/env python3
"""Loopback-only quick settings, reachable through an SSH tunnel.
Uses Python's standard library. Never imports display hardware or reads secrets.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import secrets
import subprocess
import time
from urllib.parse import urlsplit
from src.dashboard_settings import SettingsStore

PROJECT = Path(__file__).resolve().parent


def restart_display():
    """The only system action; sudo must be configured separately."""
    result = subprocess.run(['sudo', '-n', 'systemctl', 'restart', 'ledmatrix.service'],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Display restart was denied or failed.')


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, config_path=PROJECT / 'config/config.json',
                 status_path='/tmp/led_matrix_status.json', preview_path='/tmp/led_matrix_preview.png',
                 restart=restart_display):
        if address[0] != '127.0.0.1':
            raise ValueError('The dashboard must bind to 127.0.0.1. Use SSH forwarding.')
        super().__init__(address, DashboardHandler)
        self.settings = SettingsStore(config_path)
        self.status_path = Path(status_path)
        self.preview_path = Path(preview_path)
        self.restart = restart
        self.csrf = secrets.token_urlsafe(32)
        self.action_lock = self.settings.lock


class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def _valid_host(self):
        port = self.server.server_port
        return self.headers.get('Host') in {f'127.0.0.1:{port}', f'localhost:{port}'}

    def _send(self, code, body, content_type='application/json'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, allow_nan=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _status(self):
        try:
            status = json.loads(self.server.status_path.read_text())
        except (OSError, ValueError):
            status = {}
        if not isinstance(status, dict):
            status = {}
        fresh = 0 <= time.time() - status.get('timestamp', 0) < 5
        result = {key: status.get(key) for key in (
            'mode', 'active', 'spotify', 'calendar', 'available_modes',
            'markets_refresh_error', 'markets_updated_at', 'applied_revision',
        )}
        result['running'] = fresh
        result['pending_restart'] = not fresh or status.get('applied_revision') != self.server.settings.read()['revision']
        return result

    def do_GET(self):
        if not self._valid_host():
            self._send(403, {'error': 'Use the local SSH tunnel address.'})
            return
        path = urlsplit(self.path).path
        try:
            if path == '/':
                self._send(200, (PROJECT / 'templates/dashboard.html').read_bytes(), 'text/html; charset=utf-8')
            elif path in ('/dashboard.js', '/dashboard.css'):
                mime = 'application/javascript' if path.endswith('.js') else 'text/css'
                self._send(200, (PROJECT / 'static' / path[1:]).read_bytes(), mime)
            elif path == '/api/settings':
                self._send(200, {**self.server.settings.read(), 'csrf': self.server.csrf})
            elif path == '/api/status':
                self._send(200, self._status())
            elif path == '/preview.png':
                try:
                    image = self.server.preview_path.read_bytes()
                except OSError:
                    self._send(404, {'error': 'Preview appears when the display service is running.'})
                    return
                self._send(200, image, 'image/png')
            else:
                self._send(404, {'error': 'Not found.'})
        except (OSError, ValueError, TypeError):
            logging.exception('Dashboard read failed')
            self._send(503, {'error': 'Display settings or status are unavailable. Check the Pi terminal.'})

    def do_POST(self):
        host = self.headers.get('Host', '')
        if (not self._valid_host()
                or self.headers.get('Origin') != f'http://{host}'
                or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.csrf)):
            self._send(403, {'error': 'Request rejected. Reload the dashboard through your SSH tunnel.'})
            return
        if self.headers.get('Content-Type') != 'application/json':
            self._send(415, {'error': 'Send JSON settings.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('Invalid request size.')
            payload = json.loads(self.rfile.read(length))
            path = urlsplit(self.path).path
            if path == '/api/save':
                result = self.server.settings.save(payload)
                self._send(200, {**result, 'message': 'Saved. Apply settings to restart the display with these values.'})
            elif path == '/api/restart':
                if not isinstance(payload, dict) or set(payload) != {'revision'}:
                    raise ValueError('Supply the revision you want to apply.')
                with self.server.action_lock:
                    if payload['revision'] != self.server.settings.read()['revision']:
                        raise ValueError('Settings changed elsewhere. Reload before applying.')
                    self.server.restart()
                self._send(200, {'message': 'Display restarted. Health will update after initialization.'})
            else:
                self._send(404, {'error': 'Not found.'})
        except ValueError as exc:
            self._send(400, {'error': str(exc)})
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            logging.exception('Dashboard save/apply failed')
            self._send(503, {'error': 'Save or restart failed. Check file permissions, or run sudo systemctl restart ledmatrix.service in the Pi terminal.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    server = DashboardServer(('127.0.0.1', args.port))
    print(f'Dashboard: http://127.0.0.1:{server.server_port} (SSH access only)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
