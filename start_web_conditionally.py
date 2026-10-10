#!/usr/bin/env python3
"""Start the prepared local dashboard if autostart is configured."""
import json
import os
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parent

def main():
    config = json.loads((PROJECT / 'config/config.json').read_text())
    if config.get('web_display_autostart') is True:
        os.chdir(PROJECT)
        os.execv(sys.executable, [sys.executable, str(PROJECT / 'web_interface_v2.py')])
    print('Dashboard autostart is disabled.')

if __name__ == '__main__':
    main()
