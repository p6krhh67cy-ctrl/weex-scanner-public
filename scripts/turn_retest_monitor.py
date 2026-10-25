#!/usr/bin/env python3
"""10-minute monitor for WATCH candidates.

Lifecycle rules:
- base WATCH lifetime: 6 active hours from admission/reset,
- a fresh observed high resets the 6h clock,
- strong multi-day PUMP candidates remain alive while still near their high,
- WATCH state survives the overnight shutdown and is revalidated after 08:00,
- READY alerts are emitted by this monitor; the workflow controls the 08:00-23:00 window.
"""
import importlib.util,json,os,time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RADAR=ROOT/'snapshots/scanner_v2_radar.json'; MARKET=ROOT/'snapshots/market_scan.json'; STATE=Path(os.environ.get('TURN_MONITOR_STATE_PATH','/data/history/turn_monitor_state.json'))
TTL_MS=6*60*60*1000
OVERNIGHT_GRACE_MS=16*60*60*1000
WARSAW=ZoneInfo('Europe/Warsaw')
def loadmod(name,path):
    s=importlib.util.spec_from_file_location(name,str(path)); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
scan=loadmod('scan_market_v2_live',ROOT/'scripts/scan_market_v2.py'); early=loadmod('scanner_v2_early_live',ROOT/'scripts/scanner_v2_early_warning.py'); overlay=loadmod('scanner_v2_overlay_live',ROOT/'scripts/scanner_v2_predrop_fix.py'); sender=loadmod('scanner_v2_sender_live',ROOT/'scripts/send_scanner_v2_radar.py')
def n(v,d=0.0):
    try:return float(v)
    except:return d
def readj(p,d):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except:return d
def writej(p,x):p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sigs(x):return list(dict.fromkeys((x.get('pre_drop_signals') or [])+(x.get('confirmation_signals') or [])))
def reward(x):
    c=x.get('correction_model') or {}; p=n(x.get('price')); b=n(c.get('base_target_price_estimate')); return round(max(0,((p-b)/p*100) if p>0 and 0<b<p else n(c.get('remaining_move_base_pct'))),2)
def classify_live(x,lane):
    sig=sigs(x); sl=[str(s).lower() for s in sig]; m=x.get('metrics') or {}; pump=max(0,n(m.get('pump_10d_pct'))); dist=max(0,abs(n(m.get('distance_from_10d_high_pct'),999))); timing=n(x.get('timing_readiness'),n(x.get('pre_drop_score'))); tech=n(x.get('technical_confirmation')); setup=n(x.get('setup_quality')); sq=n(x.get('squeeze_risk'),50); rw=reward(x); has_lh=any('_lh' in s or s.endswith('lh') or 'failed_high' in s or 'failed_reclaim' in s for s in sl); has_ll=any('_ll' in s or s.endswith('ll') for s in sl); failed=any(k in s for s in sl for k in ('failed_high','failed_reclaim')); exhaust=any(k in s for s in sl for k in ('div','fading','fade','compression','exhaust','momentum_fade'))
    live_retest=('RETEST' in str(x.get('legacy_phase') or '').upper() or str(x.get('discovery_lane') or '').upper()=='RETEST' or any('retest' in s for s in sl)); lane='RETEST' if live_retest and rw>=2.5 else lane
    dg,dump_score,dump_evidence=overlay.dump_gate(x,lane,failed,has_lh,has_ll,exhaust); extreme_ready,extreme_evidence=overlay.extreme_gate(x,pump,dist,rw,setup,timing,tech,sq,failed,has_lh,has_ll,exhaust,dump_evidence) if lane=='PUMP' else (False,{})
    if lane=='PUMP':normal=dist<=10 and (failed or has_lh) and exhaust and timing>=50 and tech>=50 and not has_ll and dg; trigger=normal or extreme_ready
    else:normal=has_lh and failed and exhaust and timing>=55 and tech>=52 and not has_ll and dg; trigger=normal
    mode='EXTREME_PUMP_EARLY' if extreme_ready else ('NORMAL_DUMP_GATE' if normal else None)
    return rw>=2.5 and sq<=88 and setup>=45 and trigger,rw,timing,tech,setup,sq,sig,dump_score,dump_evidence,mode,lane
def lifecycle_alive(prev,now):
    reset=int(prev.get('watch_reset_ms') or prev.get('first_watch_ms') or prev.get('last_seen_ms') or 0)
    age=now-reset if reset else 10**18
    if age<=TTL_MS:return True,False
    # The scanner is intentionally off overnight. At the first morning revalidation,
    # preserve yesterday's WATCH long enough to inspect it rather than dropping it by clock time.
    hour=datetime.now(WARSAW).hour
    if hour==8 and age<=OVERNIGHT_GRACE_MS:return True,True
    # A2/multi-day pump: no hard TTL while the structure remains high and extended.
    if bool(prev.get('multi_day_hold')):return True,False
    return False,False
def main():
    radar=readj(RADAR,{}); market=readj(MARKET,{}); raw_by_symbol={str(x.get('symbol') or ''):x for x in (market.get('analyzed_all') or market.get('candidates') or [])}; src=(radar.get('pump_watch_all') or [])+(radar.get('retest_watch_all') or []); old=readj(STATE,{'symbols':{}}); oldsym=old.get('symbols') or {}; now=int(time.time()*1000); watched=[]; seen=set(); overnight={}
    for x in src:
        sym=str(x.get('symbol') or ''); lane=str(x.get('radar_lane') or '').upper()
        if sym and sym not in seen and lane in ('PUMP','RETEST') and str(x.get('cycle_state') or '').upper() in ('WATCH_PUMP','WATCH_RETEST'):seen.add(sym); watched.append({'symbol':sym,'lane':lane,'fresh':True})
    for sym,prev in oldsym.items():
        lane=str(prev.get('lane') or '').upper(); alive,carry=lifecycle_alive(prev,now)
        if sym not in seen and sym in raw_by_symbol and lane in ('PUMP','RETEST') and alive:
            seen.add(sym); watched.append({'symbol':sym,'lane':lane,'fresh':False}); overnight[sym]=carry
    watched=watched[:30]; results=[]; sent=[]; errors={}; scan.NOW=now
    kept={}
    for source in watched:
        sym=str(source.get('symbol') or ''); lane=str(source.get('lane') or '').upper()
        try:
            seed=raw_by_symbol.get(sym)
            if not seed:errors[sym]='missing_full_market_seed'; continue
            raw=scan.analyze(seed); x=early.classify(raw)
            if not x:errors[sym]='classify_returned_none'; continue
            ready,rw,timing,tech,setup,sq,sig,dump_score,dump_evidence,mode,lane=classify_live(x,lane); prev=oldsym.get(sym) or {}; prev_ready=bool(prev.get('ready')); material=(not prev_ready and ready) or abs(timing-n(prev.get('timing'),timing))>=8 or abs(tech-n(prev.get('confidence'),tech))>=8; state='READY_FOR_CHAT' if ready else ('WATCH_PUMP' if lane=='PUMP' else 'WATCH_RETEST'); rank=round(timing*.27+tech*.23+dump_score*.25+min(100,rw*12)*.15+min(100,setup)*.10,2); x.update({'cycle_state':state,'radar_lane':lane,'expected_drop_pct':rw,'canonical_timing':round(timing,1),'canonical_technical':round(tech,1),'canonical_opportunity':rank,'dump_likelihood_score':dump_score,'dump_evidence':dump_evidence,'trigger_mode':mode,'bucket':'SHORT_SETUP' if ready else ('PUMP_WATCH' if lane=='PUMP' else 'RETEST_WATCH')})
            last_alert=int(prev.get('last_ready_alert_ms') or 0); cooldown=(now-last_alert)>=60*60*1000; trigger=ready and material and (not prev_ready or cooldown)
            if trigger:
                msg=sender.rich(x,False); res=sender.send(sym,msg,'ARMED',x) if sender.ENABLED else {'ok':True,'skipped':True}; sent.append({'symbol':sym,'state':state,'reward':rw,'dump_score':dump_score,'trigger_mode':mode,'result':res}); last_alert=now
            price=n(x.get('price')); old_high=n(prev.get('watch_high_price')); new_high=price>0 and (old_high<=0 or price>old_high*1.001)
            reset=int(prev.get('watch_reset_ms') or prev.get('first_watch_ms') or now)
            if source.get('fresh') and not prev: reset=now
            if new_high or overnight.get(sym): reset=now
            watch_high=max(old_high,price)
            metrics=x.get('metrics') or {}; pump10=max(0,n(metrics.get('pump_10d_pct'))); dist10=max(0,abs(n(metrics.get('distance_from_10d_high_pct'),999)))
            # A2: strongly extended multi-day PUMP still trading near its 10d high.
            multi_day_hold=(lane=='PUMP' and pump10>=30 and dist10<=15)
            results.append({'symbol':sym,'lane':lane,'state':state,'timing':timing,'technical':tech,'dump_score':dump_score,'reward':rw,'trigger_mode':mode,'ready':ready,'watch_reset':new_high or bool(overnight.get(sym)),'multi_day_hold':multi_day_hold}); kept[sym]={'cycle_state':state,'lane':lane,'ready':ready,'timing':timing,'confidence':tech,'dump_score':dump_score,'price':x.get('price'),'first_watch_ms':int(prev.get('first_watch_ms') or now),'watch_reset_ms':reset,'watch_high_price':watch_high,'multi_day_hold':multi_day_hold,'last_seen_ms':now,'last_ready_alert_ms':last_alert}
        except Exception as e:errors[sym]=f'{type(e).__name__}: {e}'
    writej(STATE,{'updated_at_ms':now,'symbols':kept}); print(json.dumps({'turn_monitor':True,'watched':len(watched),'checked':len(results),'ready_alerts':[x['symbol'] for x in sent],'errors':errors,'results':results},ensure_ascii=False))
if __name__=='__main__':main()
