#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
exec python3 web_interface_v2.py "$@"
