#!/usr/bin/env python3
"""v11.6 opportunity-first radar: preserve exceptional post-pumps through first correction/retest."""
import importlib.util,json,os,time
from pathlib import Path
BASE=Path('scripts/scanner_v2_early_warning.py'); OUT=Path('snapshots/scanner_v2_radar.json'); MARKET=Path('snapshots/market_scan.json'); STATE=Path(os.environ.get('SCANNER_STATE_PATH','/data/history/scanner_v2_state.json'))
def n(v,d=0.0):
    try:return float(v)
    except:return d
def loadmod(name,path):
    s=importlib.util.spec_from_file_location(name,str(path)); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def run_base():
    m=loadmod('scanner_v2_base',BASE); m.main(); return m
def load_state():
    try:return json.loads(STATE.read_text())
    except:return {'symbols':{}}
def save_state(s):
    try:STATE.parent.mkdir(parents=True,exist_ok=True); STATE.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n')
    except:pass
def signals(x):return list(dict.fromkeys((x.get('pre_drop_signals') or [])+(x.get('confirmation_signals') or [])))
def forward_reward(x):
    c=x.get('correction_model') or {}; p=n(x.get('price')); b=n(c.get('base_target_price_estimate'))
    return round(max(0,((p-b)/p*100) if p>0 and 0<b<p else n(c.get('remaining_move_base_pct'))),2)
def dump_gate(x,lane,failed,has_lh,has_ll,exhaust):
    m=x.get('metrics') or {}; mom30=n(m.get('momentum_30m_pct')); mom45=n(m.get('momentum_45m_pct')); r15=n(m.get('rsi_15m'),50); r1=n(m.get('rsi_1h'),50); red=int(n(m.get('recent_red_15m'))); lh15=bool(m.get('lower_high_15m')); ll15=bool(m.get('lower_low_15m')); div15=bool(m.get('bearish_rsi_divergence_15m')); div1=bool(m.get('bearish_rsi_divergence_1h')); fade=bool(m.get('momentum_fade_15m')); comp=bool(m.get('near_high_compression_15m')); fail15=bool(m.get('failed_high_15m'))
    structure=failed or fail15 or lh15 or has_lh; momentum=(fade or div15 or div1 or exhaust) and (mom30<=0.35 or mom45<=0.60 or r15<68); seller_shift=(mom30<0 or mom45<0 or red>=2 or ll15); continuation_hot=(mom30>1.25 and mom45>1.75 and r15>=68 and red==0); groups=sum((bool(structure),bool(momentum),bool(seller_shift)))
    passed=(groups>=3 and (lane!='RETEST' or failed or fail15) and not continuation_hot); score=(35 if structure else 0)+(30 if momentum else 0)+(35 if seller_shift else 0)-(35 if continuation_hot else 0)
    return passed,max(0,min(100,score)),{'structure':structure,'momentum':momentum,'seller_shift':seller_shift,'continuation_hot':continuation_hot,'mom30':mom30,'mom45':mom45,'rsi15':r15,'rsi1h':r1,'red15':red,'lh15':lh15,'ll15':ll15,'failed15':fail15,'div15':div15,'div1h':div1,'fade15':fade,'compression15':comp}
def extreme_gate(x,pump,dist,reward,setup,timing,tech,squeeze,failed,has_lh,has_ll,exhaust,dump_evidence):
    """Earlier READY only near the high; after first drop the same name stays WATCH for a retest."""
    extreme=(pump>=100 or (pump>=70 and reward>=10)) and reward>=8 and dist<=12 and setup>=55 and squeeze<=86
    structure=bool(failed or has_lh or dump_evidence.get('failed15') or dump_evidence.get('lh15')); momentum=bool(exhaust or dump_evidence.get('momentum')); hot=bool(dump_evidence.get('continuation_hot'))
    passed=extreme and structure and momentum and timing>=40 and tech>=42 and not has_ll and not hot
    return passed,{'extreme':extreme,'structure':structure,'momentum':momentum,'continuation_hot':hot}
def main():
    early=run_base(); data=json.loads(OUT.read_text()); market=json.loads(MARKET.read_text()); rows=[]; classify_errors={}; source=market.get('analyzed_all') or market.get('candidates') or []
    for c in source:
        try:
            x=early.classify(c)
            if x:rows.append(x)
        except Exception as e:classify_errors[str(c.get('symbol') or '?')]=f'{type(e).__name__}: {e}'
    old=(load_state().get('symbols') or {}); now=int(time.time()*1000); new={}; ready=[]; pump_watch=[]; retest_watch=[]; diag=[]
    for x in rows:
        m=x.get('metrics') or {}; sym=str(x.get('symbol') or ''); prev=old.get(sym) or {}; sig=signals(x); sl=[str(s).lower() for s in sig]; phase=str(x.get('legacy_phase') or '').upper(); pump=max(0,n(m.get('pump_10d_pct'))); dist=max(0,abs(n(m.get('distance_from_10d_high_pct'),999))); setup=n(x.get('setup_quality')); timing=n(x.get('timing_readiness'),n(x.get('pre_drop_score'))); tech=n(x.get('technical_confirmation')); squeeze=n(x.get('squeeze_risk'),50); reward=forward_reward(x); room=max(0,min(100,n(x.get('remaining_correction_room_pct'),0)))
        has_lh=any('_lh' in s or s.endswith('lh') or 'failed_high' in s or 'failed_reclaim' in s for s in sl); has_ll=any('_ll' in s or s.endswith('ll') for s in sl); exhaust=any(k in s for s in sl for k in ('div','fading','fade','compression','exhaust','momentum_fade')); failed=any(k in s for s in sl for k in ('failed_high','failed_reclaim')); retest=('RETEST' in phase or str(x.get('discovery_lane') or '').upper()=='RETEST' or any('retest' in s for s in sl))
        extreme_cycle=(pump>=70 and reward>=4.0 and setup>=50 and dist<=22 and squeeze<=92); normal_spent=(dist>=15 or (room<25 and reward<2.5) or (has_ll and dist>=10)); correction_spent=normal_spent and not extreme_cycle
        active_normal=(pump>=20 and dist<=10 and room>=45 and setup>=45 and squeeze<=82 and not retest and not correction_spent); extreme_watch=(extreme_cycle and room>=15 and not retest); active_pump=active_normal or extreme_watch
        fresh_retest=(retest and reward>=2.5 and dist<=18 and squeeze<=88 and not correction_spent and (extreme_cycle or not (has_ll and dist>=14))); lane='PUMP' if active_pump else ('RETEST' if fresh_retest else 'NONE')
        dg,dump_score,dump_evidence=dump_gate(x,lane,failed,has_lh,has_ll,exhaust) if lane!='NONE' else (False,0,{})
        extreme_ready,extreme_evidence=extreme_gate(x,pump,dist,reward,setup,timing,tech,squeeze,failed,has_lh,has_ll,exhaust,dump_evidence) if lane=='PUMP' else (False,{})
        normal_turn=(active_pump and dist<=10 and (failed or has_lh) and exhaust and timing>=50 and tech>=50 and not has_ll and dg); turn_trigger=normal_turn or (active_pump and extreme_ready); retest_trigger=(fresh_retest and has_lh and failed and exhaust and timing>=55 and tech>=52 and not has_ll and dg)
        is_ready=(reward>=2.5 and (turn_trigger or retest_trigger)); trigger_mode='EXTREME_PUMP_EARLY' if active_pump and extreme_ready else ('NORMAL_DUMP_GATE' if normal_turn or retest_trigger else None); state='READY_FOR_CHAT' if is_ready else ('WATCH_PUMP' if active_pump else ('WATCH_RETEST' if fresh_retest else ('CORRECTION_SPENT' if correction_spent else 'TRACK')))
        watch_rank=round(min(100,pump*.40+room*.25+setup*.15+(100-squeeze)*.10+max(0,10-dist)),1); ready_rank=round(min(100,timing*.30+tech*.25+dump_score*.25+min(100,reward*12)*.10+setup*.10),1)
        x['cycle_state']=state; x['radar_lane']=lane; x['expected_drop_pct']=reward; x['canonical_timing']=round(timing,1); x['canonical_technical']=round(tech,1); x['canonical_opportunity']=ready_rank if is_ready else watch_rank; x['v11_rank']=x['canonical_opportunity']; x['deep_is_qualification_input']=False; x['dump_likelihood_score']=dump_score; x['dump_evidence']=dump_evidence; x['trigger_mode']=trigger_mode; x['scanner_context']={'state':state,'lane':lane,'pump_pct':round(pump,2),'distance_from_high_pct':round(dist,2),'remaining_room_pct':round(room,1),'forward_reward_pct':reward,'setup_quality':round(setup,1),'timing':round(timing,1),'technical':round(tech,1),'squeeze':round(squeeze,1),'signals':sig,'turn_trigger':turn_trigger,'retest_trigger':retest_trigger,'dump_gate':dg,'dump_score':dump_score,'dump_evidence':dump_evidence,'extreme_gate':extreme_evidence,'extreme_cycle':extreme_cycle,'trigger_mode':trigger_mode,'correction_spent':correction_spent}
        diag.append({'s':sym,'phase':phase,'pump':round(pump,1),'dist':round(dist,1),'room':round(room,1),'reward':reward,'setup':round(setup,1),'timing':round(timing,1),'tech':round(tech,1),'dump':dump_score,'dg':dg,'ext':extreme_ready,'cycle':extreme_cycle,'mode':trigger_mode,'sq':round(squeeze,1),'lh':has_lh,'ll':has_ll,'retest':retest,'spent':correction_spent,'state':state})
        if is_ready:x['bucket']='SHORT_SETUP'; x['status']='READY'; x['alert_eligible']=True; ready.append(x)
        elif active_pump:x['bucket']='PUMP_WATCH'; x['status']='WATCH'; x['alert_eligible']=True; pump_watch.append(x)
        elif fresh_retest:x['bucket']='RETEST_WATCH'; x['status']='WATCH'; x['alert_eligible']=True; retest_watch.append(x)
        else:x['bucket']='TRACK'; x['status']=state; x['alert_eligible']=False
        prevst=str(prev.get('cycle_state') or ''); x['progression']={'previous_cycle_state':prevst or None,'current_cycle_state':state,'material_change':prevst!=state,'first_alert':not bool(prev)}; new[sym]={'cycle_state':state,'lane':lane,'timing':timing,'confidence':tech,'dump_score':dump_score,'price':x.get('price'),'last_seen_ms':now}
    ready.sort(key=lambda z:n(z.get('v11_rank')),reverse=True); pump_watch.sort(key=lambda z:n(z.get('v11_rank')),reverse=True); retest_watch.sort(key=lambda z:n(z.get('v11_rank')),reverse=True); watches=pump_watch+retest_watch
    data['short_setup_candidates']=ready[:3]; data['short_setup_overflow']=ready[3:]; data['pump_watch_candidates']=watches[:3]; data['pump_watch_overflow']=watches[3:]; data['pump_watch_all']=pump_watch; data['retest_watch_all']=retest_watch; data['alert_candidates']=ready[:3]+watches[:3]; data['alert_count']=len(ready)+len(watches); data['pre_setups']=rows[:120]; data['scanner_overlay_version']='11.6-extreme-cycle-persistence'; data['v11_diagnostics']=diag; data['full_universe_input_count']=len(source); data['full_universe_classified_count']=len(rows); data['full_universe_classify_errors']=classify_errors
    save_state({'updated_at_ms':now,'symbols':new}); OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n'); print('V11_DIAG='+json.dumps(diag,ensure_ascii=False,separators=(',',':')),flush=True); print(json.dumps({'v11':True,'universe':len(source),'classified':len(rows),'ready':[x.get('symbol') for x in ready],'pump_watch':[x.get('symbol') for x in pump_watch],'retest_watch':[x.get('symbol') for x in retest_watch],'classify_errors':len(classify_errors)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
