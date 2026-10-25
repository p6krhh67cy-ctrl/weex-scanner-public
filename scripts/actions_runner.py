#!/usr/bin/env python3
"""GitHub Actions runner for the WEEX scanner."""
import os, subprocess, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
Path('snapshots').mkdir(exist_ok=True)
Path('history').mkdir(exist_ok=True)
os.environ.setdefault('SCANNER_STATE_PATH',str(ROOT/'history'/'scanner_v2_state.json'))
os.environ.setdefault('TURN_MONITOR_STATE_PATH',str(ROOT/'history'/'turn_monitor_state.json'))
REQUESTED=os.environ.get('SCANNER_RUN_MODE','full').strip().lower()
OWNER_GENERATION='20261025-v3'

# Old already-running watchdogs pull new code, but keep their old environment.
# Only the current owner generation may scan, write state/archive, or notify.
if os.environ.get('SCANNER_OWNER_GENERATION') != OWNER_GENERATION:
    print('STALE_SCANNER_RUN_BLOCKED owner generation mismatch', flush=True)
    raise SystemExit(0)

def run(path):
    print(f'RUN {path}',flush=True)
    subprocess.run([sys.executable,path],check=True)

def warsaw_full_slot():
    now=datetime.now(ZoneInfo('Europe/Warsaw'))
    return now.minute in (0,30) and now.second < 180

if REQUESTED not in ('full','monitor'):
    raise SystemExit(f'Unknown SCANNER_RUN_MODE={REQUESTED!r}')

EFFECTIVE='full' if REQUESTED=='full' and warsaw_full_slot() else 'monitor'
os.environ['SCANNER_EFFECTIVE_MODE']=EFFECTIVE
print(f'REQUESTED_MODE={REQUESTED} EFFECTIVE_MODE={EFFECTIVE}',flush=True)

run('scripts/scan_market_v2_compat.py')
run('scripts/scanner_v2_predrop_fix.py')
try:
    if EFFECTIVE=='full':
        run('scripts/send_scanner_v2_radar.py')
        print('SCANNER_FULL_OK',flush=True)
    else:
        run('scripts/turn_retest_monitor.py')
        print('SCANNER_MONITOR_OK',flush=True)
finally:
    try: run('scripts/archive_cycle.py')
    except Exception as e: print(f'ARCHIVE_FAILED: {e}',flush=True)
