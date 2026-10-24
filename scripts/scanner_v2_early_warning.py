#!/usr/bin/env python3
"""Scanner v2 early-warning overlay.

Additive-only: reads snapshots/market_scan.json and writes separate v2 outputs.
It never modifies DOM/history archives or the legacy scanner output.
"""
import datetime as dt
import json
from pathlib import Path

SRC=Path("snapshots/market_scan.json")
OUT=Path("snapshots/scanner_v2_radar.json")
ARCH=Path("history/scanner-v2-radar")

def n(v, default=0.0):
    try: return float(v)
    except Exception: return default

def classify(c):
    m=c.get("metrics") or {}
    pump=n(m.get("pump_10d_pct")); dist=n(m.get("distance_from_10d_high_pct"),999); ch24=n(m.get("change_24h_calc_pct")); ch72=n(m.get("change_72h_pct")); r1=n(m.get("rsi_1h"),50); r15=n(m.get("rsi_15m"),50); execution=n(c.get("execution_quality")); potential=n((c.get("correction_potential") or {}).get("score")); mom30=n(m.get("momentum_30m_pct")); mom45=n(m.get("momentum_45m_pct")); red15=int(n(m.get("recent_red_15m"))); phase_hint=str(c.get("phase") or ""); price=n(c.get("last")); high24=n(c.get("high_24h")); post_peak_drop24=((high24-price)/high24*100.0) if high24>0 and price>0 else 0.0
    move_in_progress=(mom30<=-2.5 or mom45<=-3.5 or (red15>=3 and mom45<=-2.0) or (post_peak_drop24>=3.0 and phase_hint!="RETEST"))
    phase=str(c.get("phase") or ""); early_lane=(pump>=25 and dist<=7.5 and (ch24>=6 or ch72>=18) and (r1>=60 or r15>=68 or pump>=40)); retest_lane=(pump>=30 and phase in ("EXHAUSTION","FIRST DROP","RETEST") and dist<=18 and potential>=62); legacy_a2=("A2" in (c.get("legacy_setup") or [])); multiday_lane=((legacy_a2 or (pump>=40 and dist<=16)) and potential>=55); discovery_lane=(pump>=25 and dist<=18 and execution>=45 and potential>=48); extended=(early_lane or retest_lane or multiday_lane or discovery_lane) and execution>=45 and potential>=48
    if not extended:return None
    early=round(min(100,min(30,max(0,pump-20)*.75)+max(0,22-dist*2.5)+min(18,max(0,r1-55)*.8)+min(12,max(0,r15-60)*.6)+min(10,max(0,ch24-5)*.5)+min(8,max(0,execution-50)*.2)),1)
    lh1=bool(m.get("lower_high_1h")); ll1=bool(m.get("lower_low_1h")); lh4=bool(m.get("lower_high_4h")); lh15=bool(m.get("lower_high_15m")); ll15=bool(m.get("lower_low_15m")); bear_div=bool(m.get("bearish_rsi_divergence_1h")); bear_div15=bool(m.get("bearish_rsi_divergence_15m")); compression15=bool(m.get("near_high_compression_15m")); failed_high15=bool(m.get("failed_high_15m")); momentum_fade15=bool(m.get("momentum_fade_15m")); vol_fade=n(m.get("volume_trend_1h_ratio"),1)<.78
    pre=[]
    for ok,s in [(bear_div,"1h_bearish_RSI_div"),(bear_div15,"15m_bearish_RSI_div"),(vol_fade,"volume_fading"),(failed_high15,"15m_failed_high"),(momentum_fade15,"15m_momentum_fade"),(compression15,"near_high_compression")]:
        if ok:pre.append(s)
    ps=(24 if bear_div else 0)+(18 if bear_div15 else 0)+(16 if vol_fade else 0)+(18 if failed_high15 else 0)+(14 if momentum_fade15 else 0)+(10 if compression15 else 0)+(10 if pump>=40 and dist<=7.5 else 0); ps=round(min(100,ps),1); pg=bool((((bear_div or failed_high15) and ps>=34) or (len(pre)>=2 and ps>=38)) and dist<=10 and phase in ("PUMPING","EXHAUSTION"))
    technical=10; conf=[]
    if phase=="PUMPING":technical-=10
    elif phase=="EXHAUSTION":technical+=16;conf.append("exhaustion")
    elif phase=="FIRST DROP":technical+=22;conf.append("first_drop")
    elif phase=="RETEST":technical+=26;conf.append("retest")
    for ok,val,s in [(lh1,12,"1h_LH"),(ll1,8,"1h_LL"),(lh4,14,"4h_LH"),(lh15,6,"15m_LH"),(ll15,5,"15m_LL"),(bear_div,10,"1h_bearish_RSI_div"),(bear_div15,8,"15m_bearish_RSI_div"),(failed_high15,8,"15m_failed_high"),(momentum_fade15,6,"15m_momentum_fade"),(compression15,4,"near_high_compression"),(vol_fade,7,"volume_fading")]:
        if ok:technical+=val;conf.append(s)
    if r1>=75 and not(lh1 or bear_div):technical-=8
    cg=pg or lh4 or (lh1 and ll1) or phase in ("FIRST DROP","RETEST") or (lh15 and ll15) or (phase=="EXHAUSTION" and (bear_div or vol_fade or lh1)); technical=round(max(0,min(100,technical)),1)
    squeeze=n(c.get("squeeze_risk"),50); setup=round(min(100,potential*.35+early*.35+execution*.15+(100-squeeze)*.15),1); timing=20+(22 if phase=="EXHAUSTION" else 30 if phase=="RETEST" else 0)+(18 if pg else 0)+(8 if r15<55 else 0)+(10 if n(m.get("momentum_1h_pct"))<=0 else 0)+(8 if n(m.get("momentum_3h_pct"))<=0 else 0)+(12 if c.get("legacy_status")=="ARMED" or c.get("status")=="ARMED" else 0); timing=round(min(100,timing),1)
    high10=n(m.get("high_10d_price")); low10=n(m.get("low_10d_price")); valid=high10>low10>0; observed=max(0,n(m.get("first_drop_pct"))); retr=max(0,min(1.5,n(m.get("retrace_first_drop"),0))); d=max(0,dist)
    if valid:
        span=high10-low10; f236=high10-.236*span; f382=high10-.382*span; f500=high10-.5*span; f618=high10-.618*span; cons=(high10-f236)/high10*100;base=(high10-f382)/high10*100;deep=(high10-f500)/high10*100;deep618=(high10-f618)/high10*100
    else:
        f236=f382=f500=f618=None;cons=max(6,min(40,max(observed*.85,pump*.236)));base=max(cons,min(45,max(observed*1.1,pump*.382)));deep=max(base,min(55,max(observed*1.35,pump*.5)));deep618=deep
    progress=max(d,observed*(1-min(.85,retr)*.35)) if phase=="RETEST" and observed>0 else max(d,observed if phase=="FIRST DROP" else d); spent=round(min(100,(progress/base)*100),1); room=round(max(0,100-spent),1); value=setup*room/100; rank=room*.28+technical*.27+setup*.2+value*.12+timing*.08+(100-squeeze)*.05
    if room<55:rank-=(55-room)*.35
    if room<40:rank-=10
    rank=round(max(0,min(100,rank)),1); early_alert=early_lane and pg and ps>=34 and setup>=53 and room>=52 and squeeze<=72; multi=multiday_lane and len(pre)>=1 and ps>=18 and setup>=55 and room>=55 and squeeze<=78; ret=retest_lane and phase=="RETEST" and technical>=52 and cg and timing>=48 and room>=45 and squeeze<=72; first=move_in_progress and setup>=58 and technical>=48 and cg and room>=45 and squeeze<=72 and rank>=58; discovery=round(min(100,potential*.32+early*.28+execution*.14+room*.18+(100-squeeze)*.08),1); da=discovery_lane and discovery>=68 and room>=35 and squeeze<=78; eligible=da or (((early_alert or ret) and rank>=58) or (multi and rank>=54) or first)
    state="FIRST-DROP" if move_in_progress and first else "MOVE_IN_PROGRESS" if move_in_progress else "LATE" if room<25 else "PRE-SETUP" if setup<55 or timing<50 else "WATCH" if timing<68 else "ARMED" if timing<82 else "ENTRY-READY"
    return {"symbol":c.get("symbol"),"price":c.get("last"),"high_24h":c.get("high_24h"),"reference_high_10d":high10 if valid else None,"reference_low_10d":low10 if valid else None,"status":state,"entry_now":False,"early_warning_score":early,"setup_quality":setup,"timing_readiness":timing,"technical_confirmation":technical,"technical_confirmation_gate":cg,"confirmation_signals":conf,"pre_drop_score":ps,"pre_drop_gate":pg,"pre_drop_signals":pre,"move_in_progress":move_in_progress,"alert_eligible":eligible,"discovery_score":discovery,"discovery_alert":da,"radar_rank":rank,"remaining_value_score":round(value,1),"correction_spent_pct":spent,"remaining_correction_room_pct":room,"correction_model":{"observed_first_drop_pct":round(observed,2),"retrace_first_drop":round(retr,3),"target_conservative_pct":round(cons,2),"target_base_pct":round(base,2),"target_deep_pct":round(deep,2),"effective_progress_pct":round(progress,2),"remaining_move_base_pct":round(max(0,base-d),2),"remaining_move_deep_pct":round(max(0,deep-d),2),"fib_236_price":round(f236,12) if f236 else None,"fib_382_price":round(f382,12) if f382 else None,"fib_500_price":round(f500,12) if f500 else None,"fib_618_price":round(f618,12) if f618 else None,"base_target_price_estimate":round(high10*(1-base/100),12) if valid else None,"deep_target_price_estimate":round(high10*(1-deep/100),12) if valid else None,"fib_618_drop_from_high_pct":round(deep618,2)},"discovery_lane":"A2_MULTI_DAY" if multiday_lane else "EARLY" if early_lane else "RETEST" if retest_lane else "DISCOVERY","legacy_status":c.get("status"),"legacy_phase":c.get("phase"),"opportunity_score":c.get("opportunity_score"),"squeeze_risk":c.get("squeeze_risk"),"metrics":{"pump_10d_pct":pump,"distance_from_10d_high_pct":dist,"change_24h_pct":ch24,"change_72h_pct":ch72,"rsi_1h":r1,"rsi_15m":r15}}

def main():
    src=json.loads(SRC.read_text()); radar=[x for c in src.get("candidates",[]) if (x:=classify(c))]; radar.sort(key=lambda x:(x["alert_eligible"],x["radar_rank"],x["setup_quality"]),reverse=True); alerts=sorted([x for x in radar if x["alert_eligible"]],key=lambda x:x["radar_rank"],reverse=True); out={"scanner_overlay_version":"6.0-discovery-timing-split","source_scanner_version":src.get("scanner_version"),"source_fetched_at_ms":src.get("fetched_at_ms"),"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"pre_setups":radar[:30],"alert_candidates":alerts[:2],"count":len(radar),"alert_count":len(alerts)}; OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n"); print(json.dumps({"pre_setups":len(radar),"alerts":len(alerts),"top_alerts":[x["symbol"] for x in alerts[:2]]}))
if __name__=="__main__":main()
