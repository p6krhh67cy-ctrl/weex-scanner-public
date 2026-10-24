#!/usr/bin/env python3
"""Telegram radar: concise WATCH and READY-for-analysis notifications."""
import json,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
SRC=Path('snapshots/scanner_v2_radar.json'); OUT=Path('snapshots/scanner_v2_alerts.json'); ARCH=Path('history/scanner-v2-alerts')
BASE=os.environ.get('RADAR_ALERT_BASE','https://weex-live-market-gateway.c5wkwhzwg4.workers.dev').rstrip('/'); ENABLED=str(os.environ.get('ALERTS_ENABLED','false')).lower() in ('1','true','yes','y')
def n(v,d=None):
    try:return float(v)
    except Exception:return d
def fmt(v,d=2):
    z=n(v); return (f'{z:.{d}f}'.rstrip('0').rstrip('.')) if z is not None else 'BRAK'
def target(label,x,key):
    c=x.get('correction_model') or {}; p=n(x.get('price')); t=n(c.get(key))
    if t is None:return f'{label}: BRAK DANYCH'
    delta=(t/p-1)*100 if p else None; return f'{label}: {delta:.2f}% → {fmt(t,8)}' if delta is not None and delta<0 else f'{label}: → {fmt(t,8)}'
def sigs(x):return list(dict.fromkeys((x.get('pre_drop_signals') or [])+(x.get('confirmation_signals') or [])))[:8]
def rich(x,watch=False):
    opp=n(x.get('canonical_opportunity')); tech=n(x.get('canonical_technical')); reward=n(x.get('expected_drop_pct')); lane=str(x.get('radar_lane') or '').upper(); sym=x.get('symbol')
    if watch:return f"🟡 WATCH {lane or ''} — {sym}\n💰 Cena: {fmt(x.get('price'),8)}\n🎯 BASE: -{fmt(reward,2)}%\n➡️ WEEX ANALIZA {sym}"
    head=f"🟠 {'RETEST REJECTION' if lane=='RETEST' else 'TURN'} → ANALIZA WEEX — {sym}"
    return f"{head}\nGOTOWY DO PEŁNEJ ANALIZY NA CHACIE — TO NIE JEST SYGNAŁ WEJŚCIA\n\n💰 Cena: {fmt(x.get('price'),8)}\n\n🎯 {target('BASE',x,'base_target_price_estimate')}\n🎯 {target('DEEP',x,'deep_target_price_estimate')}\n\n➡️ WEEX ANALIZA {sym}\nOcena okazji: {fmt(opp,0)}/100\nSygnał techniczny: {fmt(tech,1)}/100\nNiezależne potwierdzenia: {len(sigs(x))}\nPara jest gotowa do śledzenia przez szybki follow-up. To jeszcze nie jest sygnał wejścia."
def aggregate_watch(watches):
    lines=[f'🟡 WATCH — {len(watches)} PAR']; pumps=[x for x in watches if str(x.get('radar_lane') or '').upper()=='PUMP']; retests=[x for x in watches if str(x.get('radar_lane') or '').upper()=='RETEST']
    if pumps:
        lines.append('\nPUMP')
        for x in pumps:lines.append(f"• {x.get('symbol')} | BASE {fmt(x.get('expected_drop_pct'),2)}%")
    if retests:
        lines.append('\nRETEST')
        for x in retests:lines.append(f"• {x.get('symbol')} | BASE {fmt(x.get('expected_drop_pct'),2)}%")
    lines.append('\nCzekamy na trigger do WEEX ANALIZA.'); return '\n'.join(lines)
def send(symbol,message,status,x=None,scanner_status=None):
    params={'action':'radar-alert','contract_version':'3.0','radar_status':status,'scanner_status':scanner_status or str((x or {}).get('cycle_state') or status),'phase':message,'entry_now':'false','analysis_command':f'WEEX ANALIZA {symbol}','warning':'RADAR — pełna analiza przed decyzją.','message':message}
    if x:params.update({'opportunity':fmt(x.get('canonical_opportunity'),1),'technical_score':fmt(x.get('canonical_technical'),1),'confirmations':str(len(sigs(x))),'price':fmt(x.get('price'),8)})
    url=f'{BASE}/trade-watch/{symbol}?'+urllib.parse.urlencode(params); req=urllib.request.Request(url,headers={'Accept':'application/json','Cache-Control':'no-cache','User-Agent':'WEEX-Radar-V5/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=12) as r:return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:b=e.read().decode('utf-8','replace')[:500]
        except Exception:b=''
        return {'ok':False,'error':f'HTTP {e.code}','body':b}
    except Exception as e:return {'ok':False,'error':f'{type(e).__name__}: {e}'}
def main():
    src=json.loads(SRC.read_text(encoding='utf-8')); ready=(src.get('short_setup_candidates') or [])+(src.get('short_setup_overflow') or []); watches=(src.get('pump_watch_candidates') or [])+(src.get('pump_watch_overflow') or [])
    seen=set(); ready=[x for x in ready if not (x.get('symbol') in seen or seen.add(x.get('symbol')))]; seen=set(); watches=[x for x in watches if not (x.get('symbol') in seen or seen.add(x.get('symbol')))]
    out={'generated_at_ms':int(time.time()*1000),'radar_version':'5.5-concise','alerts_enabled':ENABLED,'selected':[],'watch':None}
    for x in ready:
        msg=rich(x); res=send(x.get('symbol'),msg,'ARMED',x,scanner_status='READY_FOR_CHAT') if ENABLED else {'ok':True,'skipped':True}; out['selected'].append({'symbol':x.get('symbol'),'bucket':'READY_FOR_CHAT','rendered_message':msg,'notification':res})
    if watches:
        msg=aggregate_watch(watches); anchor=watches[0]; slot=time.strftime('%Y%m%d%H%M',time.gmtime()); scanner_status=f'WATCH_SLOT_{slot}'; res=send(anchor.get('symbol'),msg,'WATCH',anchor,scanner_status=scanner_status) if ENABLED else {'ok':True,'skipped':True}; out['watch']={'count':len(watches),'rendered_message':msg,'notification':res,'scanner_status':scanner_status}
    body=json.dumps(out,ensure_ascii=False,indent=2)+'\n'; OUT.write_text(body,encoding='utf-8'); stamp=time.strftime('%Y-%m-%d/%H-%M-%S',time.gmtime()); p=ARCH/(stamp+'.json'); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(body,encoding='utf-8'); print(body)
if __name__=='__main__':main()
