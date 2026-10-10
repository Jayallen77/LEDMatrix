#!/usr/bin/env python3
"""Run offline tests in isolated processes because fixtures stub dependencies."""
import concurrent.futures
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent

def run(path):
    result = subprocess.run([sys.executable, str(path)], cwd=ROOT, capture_output=True,
                            text=True, timeout=60, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    output = result.stdout + result.stderr
    count = re.search(r'Ran (\d+) tests?', output)
    return path.name, result.returncode, int(count.group(1)) if count else 0, output

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, sorted((ROOT / 'tests').glob('test_*.py'))))
    for name, code, count, output in results:
        print(f'{name}: {count} tests — {"PASS" if not code else "FAIL"}')
        if code:
            print(output)
    print(f'Total: {sum(r[2] for r in results)} tests, {sum(r[1] != 0 for r in results)} failing files.')
    sys.exit(any(r[1] for r in results))
