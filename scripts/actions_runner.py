#!/usr/bin/env python3
"""GitHub Actions runner for the WEEX scanner."""
import os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
Path('snapshots').mkdir(exist_ok=True)
Path('history').mkdir(exist_ok=True)
os.environ.setdefault('SCANNER_STATE_PATH',str(ROOT/'history'/'scanner_v2_state.json'))
os.environ.setdefault('TURN_MONITOR_STATE_PATH',str(ROOT/'history'/'turn_monitor_state.json'))
REQUESTED=os.environ.get('SCANNER_RUN_MODE','full').strip().lower()
OWNER_GENERATION='20261026-v6'

if os.environ.get('SCANNER_OWNER_GENERATION') != OWNER_GENERATION:
    print(f"STALE_SCANNER_RUN_BLOCKED owner={os.environ.get('SCANNER_OWNER_GENERATION')!r} expected={OWNER_GENERATION!r}", flush=True)
    raise SystemExit(2)

def run(path):
    print(f'RUN {path}',flush=True)
    subprocess.run([sys.executable,path],check=True)

if REQUESTED not in ('full','monitor'):
    raise SystemExit(f'Unknown SCANNER_RUN_MODE={REQUESTED!r}')

# The workflow owns slot classification. Do not silently downgrade FULL based on
# the wall clock: scheduled GitHub jobs can start a few minutes late.
EFFECTIVE=REQUESTED
os.environ['SCANNER_EFFECTIVE_MODE']=EFFECTIVE
print(f'REQUESTED_MODE={REQUESTED} EFFECTIVE_MODE={EFFECTIVE}',flush=True)

try:
    if EFFECTIVE=='full':
        run('scripts/scan_market_v2_compat.py')
        run('scripts/scanner_v2_predrop_fix.py')
        run('scripts/send_scanner_v2_radar.py')
        print('SCANNER_FULL_OK',flush=True)
    else:
        run('scripts/turn_retest_monitor.py')
        print('SCANNER_MONITOR_OK',flush=True)
finally:
    try: run('scripts/archive_cycle.py')
    except Exception as e: print(f'ARCHIVE_FAILED: {e}',flush=True)
