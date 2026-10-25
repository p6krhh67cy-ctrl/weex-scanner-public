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
MODE=os.environ.get('SCANNER_RUN_MODE','full').strip().lower()

def run(path):
    print(f'RUN {path}',flush=True)
    subprocess.run([sys.executable,path],check=True)

def warsaw_full_slot():
    now=datetime.now(ZoneInfo('Europe/Warsaw'))
    # Hard safety gate independent of workflow mode: aggregate WATCH sender
    # can run only at the real Warsaw :00 or :30 boundary (small execution window).
    return now.minute in (0,30) and now.second < 180

if MODE=='full':
    run('scripts/scan_market_v2_compat.py')
    run('scripts/scanner_v2_predrop_fix.py')
    if warsaw_full_slot():
        run('scripts/send_scanner_v2_radar.py')
        print('SCANNER_FULL_OK',flush=True)
    else:
        print('WATCH_SENDER_BLOCKED_OUTSIDE_REAL_FULL_SLOT',flush=True)
        run('scripts/turn_retest_monitor.py')
        print('SCANNER_MONITOR_OK',flush=True)
elif MODE=='monitor':
    run('scripts/scan_market_v2_compat.py')
    run('scripts/scanner_v2_predrop_fix.py')
    run('scripts/turn_retest_monitor.py')
    print('SCANNER_MONITOR_OK',flush=True)
else:
    raise SystemExit(f'Unknown SCANNER_RUN_MODE={MODE!r}')
