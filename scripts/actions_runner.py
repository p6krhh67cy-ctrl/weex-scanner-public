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
MODE=os.environ.get('SCANNER_RUN_MODE','full').strip().lower()

def run(path):
    print(f'RUN {path}',flush=True)
    subprocess.run([sys.executable,path],check=True)

if MODE=='full':
    run('scripts/scan_market_v2_compat.py')
    run('scripts/scanner_v2_predrop_fix.py')
    run('scripts/send_scanner_v2_radar.py')
    print('SCANNER_FULL_OK',flush=True)
elif MODE=='monitor':
    # A monitor run needs the latest market/radar snapshot. On ephemeral Actions
    # runners rebuild it first, but only WATCH names are re-analysed by the turn monitor.
    run('scripts/scan_market_v2_compat.py')
    run('scripts/scanner_v2_predrop_fix.py')
    run('scripts/turn_retest_monitor.py')
    print('SCANNER_MONITOR_OK',flush=True)
else:
    raise SystemExit(f'Unknown SCANNER_RUN_MODE={MODE!r}')
