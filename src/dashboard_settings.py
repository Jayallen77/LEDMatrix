"""Validated quick settings; never load or return the separate secrets file."""

import copy
import hashlib
import json
from pathlib import Path
import re
import threading
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.runtime_state import atomic_write_json, config_revision


# name: (path, default, kind, lower bound, upper bound)
FIELDS = {
    'brightness': (('display', 'hardware', 'brightness'), 95, 'int', 1, 100),
    'clock_seconds': (('display', 'display_durations', 'clock'), 60, 'int', 1, 600),
    'weather_seconds': (('display', 'display_durations', 'weather'), 15, 'int', 1, 600),
    'forecast_seconds': (('display', 'display_durations', 'daily_forecast'), 10, 'int', 1, 600),
    'markets_seconds': (('display', 'display_durations', 'stocks'), 30, 'int', 1, 600),
    'sports_seconds': (('display', 'display_durations', 'sports_live'), 20, 'int', 1, 600),
    'calendar_seconds': (('display', 'display_durations', 'calendar'), 30, 'int', 1, 600),
    'weather_refresh_seconds': (('weather', 'update_interval'), 1800, 'int', 60, 86400),
    'market_refresh_seconds': (('stocks', 'update_interval'), 600, 'int', 30, 86400),
    'sports_refresh_seconds': (('colorado_sports', 'polling_interval'), 30, 'int', 10, 600),
    'schedule_enabled': (('schedule', 'enabled'), True, 'bool', None, None),
    'schedule_start': (('schedule', 'start_time'), '00:01', 'time', None, None),
    'schedule_end': (('schedule', 'end_time'), '23:59', 'time', None, None),
    'weather_units': (('weather', 'units'), 'imperial', 'units', None, None),
    'city': (('location', 'city'), 'Denver', 'text', None, None),
    'state': (('location', 'state'), 'Colorado', 'text', None, None),
    'country': (('location', 'country'), 'US', 'country', None, None),
    'timezone': (('timezone',), 'America/Denver', 'timezone', None, None),
    'bitcoin_enabled': (('crypto', 'enabled'), True, 'bool', None, None),
}
for module in ('clock', 'weather', 'stocks', 'colorado_sports', 'calendar'):
    FIELDS[f'{module}_enabled'] = ((module, 'enabled'), True, 'bool', None, None)


def read_value(config, path, default):
    value = config
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def validated_value(name, value):
    _, _, kind, lower, upper = FIELDS[name]
    if kind == 'bool':
        if type(value) is not bool:
            raise ValueError(f'{name} must be true or false.')
    elif kind == 'int':
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f'{name} must be a whole number from {lower} to {upper}.')
    else:
        if not isinstance(value, str) or not value.strip() or len(value) > 100:
            raise ValueError(f'{name} must be a nonempty value of at most 100 characters.')
        value = value.strip()
        if any(ord(char) < 32 for char in value):
            raise ValueError(f'{name} contains unsupported characters.')
        if kind == 'time' and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
            raise ValueError(f'{name} must be HH:MM in 24-hour time.')
        if kind == 'units' and value not in ('imperial', 'metric'):
            raise ValueError('Choose imperial or metric units.')
        if kind == 'country':
            value = value.upper()
            if not re.fullmatch(r'[A-Z]{2}', value):
                raise ValueError('Country must be a two-letter code.')
        if kind == 'timezone':
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError):
                raise ValueError('Choose a valid timezone, such as America/Denver.') from None
    return value


class SettingsStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def read(self):
        raw = self.path.read_bytes()
        config = json.loads(raw)
        values = {name: read_value(config, spec[0], spec[1]) for name, spec in FIELDS.items()}
        # Current weather keys take precedence in the controller if explicitly present.
        durations = config.get('display', {}).get('display_durations', {})
        values['weather_seconds'] = durations.get('weather_current', values['weather_seconds'])
        values['forecast_seconds'] = durations.get('weather_daily', values['forecast_seconds'])
        return {'revision': hashlib.sha256(raw).hexdigest(), 'values': values}

    def save(self, payload):
        if not isinstance(payload, dict) or set(payload) != {'revision', 'values'}:
            raise ValueError('Supply a settings revision and values.')
        values = payload['values']
        if not isinstance(values, dict) or not values or set(values) - FIELDS.keys():
            raise ValueError('Unknown or empty settings. Reload this page.')
        validated = {name: validated_value(name, value) for name, value in values.items()}
        with self.lock:
            if payload['revision'] != config_revision(self.path):
                raise ValueError('Settings changed elsewhere. Reload before saving.')
            config = json.loads(self.path.read_text())
            updated = copy.deepcopy(config)
            for name, value in validated.items():
                path = FIELDS[name][0]
                target = updated
                for key in path[:-1]:
                    target = target.setdefault(key, {})
                target[path[-1]] = value
            durations = updated.get('display', {}).get('display_durations', {})
            for field, alias in (('weather_seconds', 'weather_current'), ('forecast_seconds', 'weather_daily')):
                if field in validated and alias in durations:
                    durations[alias] = validated[field]
            if not any(updated.get(module, {}).get('enabled', False) for module in ('clock', 'weather', 'stocks')):
                raise ValueError('Keep Clock, Weather, or Markets enabled for the ordinary rotation.')
            stale = updated.get('colorado_sports', {}).get('stale_timeout', 120)
            if updated.get('colorado_sports', {}).get('polling_interval', 30) > stale:
                raise ValueError(f'Sports refresh must be at most the {stale}-second stale window.')
            # One local rollback copy; no credential file is read or backed up.
            atomic_write_json(self.path.with_name('config.dashboard-backup.json'), config)
            atomic_write_json(self.path, updated)
            return self.read()
