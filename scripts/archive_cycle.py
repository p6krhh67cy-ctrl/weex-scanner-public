#!/usr/bin/env python3
"""Append one durable JSONL record for every scanner/monitor cycle."""
import json, os, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
HISTORY=ROOT/'history'
ARCHIVE=HISTORY/'scanner_cycles.jsonl'
RADAR=ROOT/'snapshots'/'scanner_v2_radar.json'
MARKET=ROOT/'snapshots'/'market_scan.json'
TURN=Path(os.environ.get('TURN_MONITOR_STATE_PATH',str(HISTORY/'turn_monitor_state.json')))
MODE=os.environ.get('SCANNER_EFFECTIVE_MODE',os.environ.get('SCANNER_RUN_MODE','unknown'))

def readj(p,d):
    try:return json.loads(Path(p).read_text(encoding='utf-8'))
    except:return d

def slim(x):
    return {k:x.get(k) for k in ('symbol','cycle_state','radar_lane','bucket','price','canonical_timing','canonical_technical','canonical_opportunity','dump_likelihood_score','expected_drop_pct','squeeze_risk','setup_quality','trigger_mode') if k in x}

now=datetime.now(ZoneInfo('Europe/Warsaw'))
radar=readj(RADAR,{})
market=readj(MARKET,{})
turn=readj(TURN,{})
pump=radar.get('pump_watch_all') or []
retest=radar.get('retest_watch_all') or []
ready=radar.get('ready_for_chat') or radar.get('ready') or []
turn_symbols=turn.get('symbols') or {}
record={
 'ts_ms':int(time.time()*1000),'warsaw_time':now.isoformat(timespec='seconds'),'slot':now.strftime('%H:%M'),
 'mode':MODE,'market_count':len(market.get('analyzed_all') or market.get('candidates') or []),
 'watch_count':len(pump)+len(retest),'pump_watch':[slim(x) for x in pump],
 'retest_watch':[slim(x) for x in retest],'radar_ready':[slim(x) for x in ready],
 'monitor_count':len(turn_symbols),'monitor_symbols':turn_symbols,
}
HISTORY.mkdir(parents=True,exist_ok=True)
with ARCHIVE.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'archive_written':True,'slot':record['slot'],'mode':MODE,'watch_count':record['watch_count'],'monitor_count':record['monitor_count']},ensure_ascii=False))
