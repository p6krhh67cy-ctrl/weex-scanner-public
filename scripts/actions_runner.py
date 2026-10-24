#!/usr/bin/env python3
"""One-shot runner for WEEX scanner on GitHub Actions."""
import os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
Path('snapshots').mkdir(exist_ok=True)
Path('history').mkdir(exist_ok=True)
os.environ.setdefault('SCANNER_STATE_PATH',str(ROOT/'history'/'scanner_v2_state.json'))

def run(path):
    print(f'RUN {path}',flush=True)
    subprocess.run([sys.executable,path],check=True)

run('scripts/scan_market_v2_compat.py')
run('scripts/scanner_v2_predrop_fix.py')
run('scripts/send_scanner_v2_radar.py')
print('SCANNER_PIPELINE_OK',flush=True)
