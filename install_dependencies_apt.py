#!/usr/bin/env python3
"""Compatibility check for dashboard setup; it needs no third-party packages."""
import sys

if __name__ == '__main__':
    if sys.version_info < (3, 9):
        raise SystemExit('Python 3.9 or newer is required.')
    print('Dashboard dependencies ready: Python standard library only.')
