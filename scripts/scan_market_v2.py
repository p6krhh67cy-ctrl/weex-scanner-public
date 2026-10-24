import concurrent.futures, datetime as dt, json, math, os, time, urllib.request
from pathlib import Path

BASE='https://api-contract.weex.com'; UA='weex-market-monitor/3.1'; NOW=int(time.time()*1000)
def get_json(url,timeout=20):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode('utf-8'))
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except:return None
def ema(vals,n):
    if len(vals)<n:return None
    a=2/(n+1); z=sum(vals[:n])/n
    for v in vals[n:]:z=a*v+(1-a)*z
    return z
def rsi(vals,n=14):
    if len(vals)<n+1:return None
    ds=[vals[i]-vals[i-1] for i in range(1,len(vals))]; ups=[max(d,0) for d in ds[-n:]]; dns=[max(-d,0) for d in ds[-n:]]; up=sum(ups)/n; dn=sum(dns)/n
    return 100.0 if dn==0 else 100-100/(1+up/dn)
def closed_bars(rows):
    if isinstance(rows,dict):rows=rows.get('data',rows.get('rows',[]))
    out=[x for x in (rows or []) if isinstance(x,list) and len(x)>=8 and int(x[6])<=NOW]; out.sort(key=lambda x:int(x[0])); return out
def klines(sym,interval,limit):return closed_bars(get_json(f'{BASE}/capi/v3/market/klines?symbol={sym}&interval={interval}&limit={limit}'))
def pct(a,b):return (a/b-1.0) if a is not None and b not in (None,0) else None
def clamp(x,a=0,b=100):return max(a,min(b,x))
def label_score(v):return 'VERY HIGH' if v>=80 else ('HIGH' if v>=65 else ('MEDIUM' if v>=48 else 'LOW'))
def phase_icon(p):return {'PUMPING':'▲','EXHAUSTION':'◇','FIRST DROP':'▼','RETEST':'↗','SECOND LEG':'⇊','LATE CORRECTION':'⧗'}.get(p,'?')
def status_icon(s):return {'IGNORE':'×','DEVELOPING':'…','WATCH':'◎','ARMED':'⚡','IN-PLAY / ENTRY NOW':'●'}.get(s,'?')

def analyze(t):
    sym=t['symbol']; h1=klines(sym,'1h',120); h4=klines(sym,'4h',90); m15=klines(sym,'15m',120)
    if len(h1)<72 or len(h4)<42 or len(m15)<40:raise ValueError('insufficient candles')
    c1=[float(x[4]) for x in h1]; hi1=[float(x[2]) for x in h1]; lo1=[float(x[3]) for x in h1]; c4=[float(x[4]) for x in h4]; hi4=[float(x[2]) for x in h4]; lo4=[float(x[3]) for x in h4]; c15=[float(x[4]) for x in m15]; hi15=[float(x[2]) for x in m15]; lo15=[float(x[3]) for x in m15]; v1=[float(x[5]) for x in h1]; v15=[float(x[5]) for x in m15]
    last=c15[-1]; high10=max(hi4[-60:]); low10=min(lo4[-60:]); span=max(high10-low10,1e-12); pump10=high10/low10-1; dist10=(high10-last)/high10; range_pos=(last-low10)/span
    high48=max(hi1[-48:]); low24=min(lo1[-24:]); low12=min(lo1[-12:]); first_drop=(high48-low24)/high48; bounce=last/low12-1; prior12_hi=max(hi1[-24:-12]); recent12_hi=max(hi1[-12:]); recent12_lo=min(lo1[-12:]); prior12_lo=min(lo1[-24:-12]); lower_high=recent12_hi<prior12_hi; lower_low=recent12_lo<prior12_lo
    e20=ema(c1,20); e50=ema(c1,50); e20_4=ema(c4,20); r1=rsi(c1); r4=rsi(c4); r15=rsi(c15); avg_v1=sum(v1[-25:-1])/24; avg_v15=sum(v15[-33:-1])/32; rel_vol_1h=v1[-1]/avg_v1 if avg_v1 else None; rel_vol_15m=v15[-1]/avg_v15 if avg_v15 else None; vol_recent=sum(v1[-6:])/6; vol_prior=sum(v1[-18:-6])/12; volume_trend_ratio=vol_recent/vol_prior if vol_prior else None
    lower_high_4h=max(hi4[-6:])<max(hi4[-12:-6]); lower_low_4h=min(lo4[-6:])<min(lo4[-12:-6]); lower_high_15m=max(hi15[-12:])<max(hi15[-24:-12]); lower_low_15m=min(lo15[-12:])<min(lo15[-24:-12]); prev_hi=max(hi1[-24:-12]); curr_hi=max(hi1[-12:]); prev_rsi=rsi(c1[:-12]) if len(c1)>26 else None; bearish_rsi_div_1h=bool(prev_rsi is not None and r1 is not None and curr_hi>=prev_hi and r1<prev_rsi-2)
    prev15_hi=max(hi15[-16:-8]); recent15_hi=max(hi15[-8:]); prev15_rsi=rsi(c15[:-8]) if len(c15)>30 else None; bearish_rsi_div_15m=bool(prev15_rsi is not None and r15 is not None and recent15_hi>=prev15_hi*.997 and r15<prev15_rsi-3); near_high_compression=bool(dist10<=.075 and max(c15[-8:])/max(min(c15[-8:]),1e-12)-1<=.045); failed_high_15m=bool(dist10<=.10 and recent15_hi<prev15_hi and c15[-1]<max(c15[-4:-1])); momentum_fade_15m=bool(pct(c15[-1],c15[-5])<pct(c15[-5],c15[-9]))
    ch24=pct(last,c1[-25]); ch72=pct(last,c1[-73]); m15_1h=pct(last,c15[-5]); m15_3h=pct(last,c15[-13]); m15_30m=pct(last,c15[-3]); m15_45m=pct(last,c15[-4]); recent_red_15m=sum(1 for i in range(len(c15)-3,len(c15)) if c15[i]<c15[i-1]); retrace=(last-low24)/(high48-low24) if high48>low24 else None
    if pump10>=.20 and dist10<=.035 and (ch24 or 0)>.06 and not lower_high:phase='PUMPING'
    elif pump10>=.20 and dist10<=.10 and ((r1 or 50)>=62 or lower_high or ((ch72 or 0)>=.18 and (ch24 or 0)<=.05)):phase='EXHAUSTION'
    elif first_drop>=.045 and bounce<.02 and (m15_3h or 0)<0:phase='FIRST DROP'
    elif first_drop>=.05 and .02<=bounce<=.14 and retrace is not None and .20<=retrace<=.78:phase='RETEST'
    elif first_drop>=.07 and lower_low and (m15_3h or 0)<-.025 and bounce<.035:phase='SECOND LEG'
    elif dist10>=.18 or range_pos<.48:phase='LATE CORRECTION'
    else:phase='DEVELOPING'
    potential=20+min(28,max(0,pump10-.12)*55)+(12 if range_pos>=.58 else 0)+(9 if lower_high else 0)+(6 if (r1 or 50)>=60 else 0)+(12 if phase in ('EXHAUSTION','RETEST') else 0)+(7 if phase=='FIRST DROP' else 0)+(5 if phase=='SECOND LEG' else 0)-(22 if phase=='LATE CORRECTION' else 0)-(12 if dist10>.28 else 0); potential=clamp(round(potential))
    thesis=35+(12 if pump10>=.25 else 0)+(10 if lower_high else 0)+(7 if lower_low else 0)+(7 if lower_high_4h else 0)+(5 if lower_low_4h else 0)+(6 if bearish_rsi_div_1h else 0)+(4 if volume_trend_ratio is not None and volume_trend_ratio<.75 else 0)+(7 if e20 and last<e20 else 0)+(8 if e20 and e50 and e20<e50 else 0)+(6 if e20_4 and last<e20_4 else 0)+(7 if (ch72 or 0)>=.18 and (ch24 or 0)<=.03 else 0)-(14 if phase=='PUMPING' and (ch24 or 0)>.10 else 0); thesis=clamp(round(thesis))
    entry=30+(30 if phase=='RETEST' else 18 if phase=='EXHAUSTION' else 5 if phase=='FIRST DROP' else -4 if phase=='SECOND LEG' else -18 if phase=='LATE CORRECTION' else 0)+(12 if retrace is not None and .30<=retrace<=.65 else 0)+(8 if e20 and abs(last/e20-1)<=.035 else 0)-(12 if bounce>.16 else 0)-(10 if t.get('spread') is not None and t['spread']>.004 else 0); entry=clamp(round(entry))
    squeeze=30+(28 if phase=='PUMPING' else 0)+(5 if not lower_high_4h else 0)+(6 if rel_vol_1h is not None and rel_vol_1h>1.8 and (ch24 or 0)>0 else 0)+(14 if (ch24 or 0)>.10 else 0)+(10 if (m15_3h or 0)>.05 else 0)+(8 if (r15 or 50)>=70 else 0)+(8 if (r1 or 50)>=68 else 0)+(8 if bounce>.12 else 0)+(8 if not lower_high else -8)-(6 if lower_low else 0)-(8 if phase in ('RETEST','SECOND LEG') else 0); squeeze=clamp(round(squeeze))
    vol=t.get('volume_24h_usdt') or 0; spr=t.get('spread'); execution=45+(30 if vol>=50e6 else 22 if vol>=10e6 else 14 if vol>=2e6 else 6 if vol>=.5e6 else -12)+(18 if spr is not None and spr<=.0003 else 12 if spr is not None and spr<=.001 else 5 if spr is not None and spr<=.0025 else -28 if spr is not None and spr>.006 else -16 if spr is not None and spr>.004 else 0); execution=clamp(round(execution)); opportunity=clamp(round(potential*.30+entry*.25+thesis*.25+execution*.10+(100-squeeze)*.10))
    if potential<45 or thesis<45 or phase=='LATE CORRECTION':status='IGNORE'
    elif phase=='PUMPING':status='DEVELOPING'
    elif phase in ('EXHAUSTION','FIRST DROP'):status='WATCH' if potential>=60 else 'DEVELOPING'
    elif phase=='RETEST' and entry>=68 and thesis>=58 and opportunity>=68 and squeeze<=65:status='ARMED'
    elif phase=='RETEST':status='WATCH'
    elif phase=='SECOND LEG' and entry>=55:status='WATCH'
    else:status='DEVELOPING'
    legacy=[]
    if t['distance_from_high']<=.03 and ((t['change_24h'] or 0)>=.08 or t['amplitude_24h']>=.15):legacy.append('A')
    if pump10>=.30 and dist10<=.16 and range_pos>=.64:legacy.append('A2')
    if last<(e20 or last*2) and lower_high and lower_low and bounce>=.018:legacy.append('B')
    return {**t,'phase':phase,'phase_icon':phase_icon(phase),'status':status,'status_icon':status_icon(status),'correction_potential':{'score':potential,'label':label_score(potential)},'entry_quality':entry,'thesis_strength':thesis,'squeeze_risk':squeeze,'execution_quality':execution,'opportunity_score':opportunity,'legacy_setup':legacy,'metrics':{'pump_10d_pct':round(pump10*100,2),'distance_from_10d_high_pct':round(dist10*100,2),'high_10d_price':high10,'low_10d_price':low10,'current_price':last,'first_drop_pct':round(first_drop*100,2),'bounce_from_12h_low_pct':round(bounce*100,2),'retrace_first_drop':round(retrace,3) if retrace is not None else None,'rsi_15m':round(r15,2) if r15 is not None else None,'rsi_1h':round(r1,2) if r1 is not None else None,'rsi_4h':round(r4,2) if r4 is not None else None,'change_24h_calc_pct':round((ch24 or 0)*100,2),'change_72h_pct':round((ch72 or 0)*100,2),'momentum_30m_pct':round((m15_30m or 0)*100,2),'momentum_45m_pct':round((m15_45m or 0)*100,2),'recent_red_15m':recent_red_15m,'momentum_1h_pct':round((m15_1h or 0)*100,2),'momentum_3h_pct':round((m15_3h or 0)*100,2),'ema20_1h':e20,'ema50_1h':e50,'lower_high_1h':lower_high,'lower_low_1h':lower_low,'lower_high_4h':lower_high_4h,'lower_low_4h':lower_low_4h,'lower_high_15m':lower_high_15m,'lower_low_15m':lower_low_15m,'relative_volume_1h':round(rel_vol_1h,3) if rel_vol_1h is not None else None,'relative_volume_15m':round(rel_vol_15m,3) if rel_vol_15m is not None else None,'volume_trend_1h_ratio':round(volume_trend_ratio,3) if volume_trend_ratio is not None else None,'bearish_rsi_divergence_1h':bearish_rsi_div_1h,'bearish_rsi_divergence_15m':bearish_rsi_div_15m,'near_high_compression_15m':near_high_compression,'failed_high_15m':failed_high_15m,'momentum_fade_15m':momentum_fade_15m},'reasons':[],'required_followup':['fresh_dynamic_dom','order_flow_cvd','open_interest','cross_exchange_futures','catalyst_red_flags']}

def main():
    rows=get_json(f'{BASE}/capi/v2/market/tickers',45); clean=[]
    for x in rows:
        sym=str(x.get('symbol','')).upper().replace('CMT_','');
        if not sym.endswith('USDT'):continue
        last,hi,lo=num(x.get('last')),num(x.get('high_24h')),num(x.get('low_24h')); ask,bid=num(x.get('best_ask')),num(x.get('best_bid')); vol=num(x.get('volume_24h')); ch=num(x.get('priceChangePercent'))
        if not all(v is not None and v>0 for v in (last,hi,lo)):continue
        spread=(ask-bid)/last if ask and bid else None; clean.append({'symbol':sym,'last':last,'high_24h':hi,'low_24h':lo,'change_24h':ch,'volume_24h_usdt':vol,'distance_from_high':(hi-last)/hi,'amplitude_24h':hi/lo-1,'spread':spread})
    liquid=[x for x in clean if (x['volume_24h_usdt'] or 0)>=250000 and (x['spread'] is None or x['spread']<=.006)]
    pool=list(liquid); results=[]; errors={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        fut={ex.submit(analyze,x):x['symbol'] for x in pool}
        for f in concurrent.futures.as_completed(fut):
            s=fut[f]
            try:results.append(f.result())
            except Exception as e:errors[s]=f'{type(e).__name__}: {e}'
    rank={'ARMED':4,'WATCH':3,'DEVELOPING':2,'IGNORE':1}; results.sort(key=lambda x:(rank.get(x['status'],0),x.get('opportunity_score',0),x['correction_potential']['score'],x['entry_quality'],x['thesis_strength']),reverse=True); actionable=[x for x in results if x['status']!='IGNORE']
    out={'scanner_version':'4.2-full-liquid-universe','fetched_at_ms':int(time.time()*1000),'counts':{'all_usdt':len(clean),'liquid':len(liquid),'analyzed':len(results),'actionable':len(actionable),'errors':len(errors)},'analyzed_all':results,'candidates':actionable[:120],'by_status':{s:[x for x in actionable if x['status']==s][:40] for s in ['ARMED','WATCH','DEVELOPING']},'ignored_top':sorted([x for x in results if x['status']=='IGNORE'],key=lambda x:x['correction_potential']['score'],reverse=True)[:40],'errors':errors}
    Path('snapshots').mkdir(exist_ok=True); Path('history/market-scans').mkdir(parents=True,exist_ok=True); Path('snapshots/market_scan.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d/%H-%M-%S'); hp=Path('history/market-scans')/f'{stamp}.json'; hp.parent.mkdir(parents=True,exist_ok=True); hp.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
