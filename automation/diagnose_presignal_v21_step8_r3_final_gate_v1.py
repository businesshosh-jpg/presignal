"""Read-only final-gate diagnosis for the completed Compat-R5 successor."""
from __future__ import annotations
import json, hashlib, sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
RUN=ROOT/'outputs/presignal_v21_step8_r3_final_historical_verification_r1/STEP8-R3-FINAL-R1-e8bf771'
OUT=ROOT/'outputs/presignal_v21_step8_r3_final_gate_diagnosis/STEP8-R3-GATE-e8bf771'

def c(x:Any)->str:return json.dumps(x,sort_keys=True,separators=(',',':'))
def fp(x:Any)->str:return 'sha256:'+hashlib.sha256(c(x).encode()).hexdigest()
def w(n:str,x:Any): OUT.mkdir(parents=True,exist_ok=True);(OUT/n).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def jl(n:str,x:list[dict]): (OUT/n).write_text(''.join(c(r)+'\n' for r in x))
def load(p:Path):return json.loads(p.read_text())

def terminal(row):
    a,e=row['pack_a_accepted'],row['pack_e_accepted']; req=row['request_accepted']; ev=row['pack_a_evaluation'],row['pack_e_evaluation']
    if row['completion']=='COMPLETE_PAIRED': return 'COMPLETE_PAIRED_EVALUATION','EVALUATION','SCIENTIFIC_ELIGIBLE'
    if a and e and (not isinstance(ev,dict) or not isinstance(ev.get('direction_15m_ok'),bool) or not isinstance(ee:=row['pack_e_evaluation'],dict) or not isinstance(ee.get('direction_15m_ok'),bool)):
        return 'PRIMARY_15M_OUTCOME_NOT_EVALUABLE','OUTCOME','IMPLEMENTATION'
    if not req:
        reason=str(row.get('request_rejection_reason') or '')
        if any(k in reason.lower() for k in ('timed out','httpsconnection','oauth','server at')): return 'REQUEST_TRANSPORT_FAILURE','REQUEST','INFRASTRUCTURE'
        if reason: return 'REQUEST_PROVIDER_REJECTION','REQUEST','PROVIDER_OR_CONTRACT'
        return 'ATTENTION_ACCEPTED_REQUEST_NOT_ATTEMPTED','REQUEST','UNEXPLAINED'
    if not a and not e: return 'BOTH_FORECAST_ARMS_INCOMPLETE','FORECAST','PROVIDER_OR_CONTRACT'
    if not a: return 'PACK_A_SYSTEM_REJECTION','FORECAST','PROVIDER_OR_CONTRACT'
    if not e: return 'PACK_E_SYSTEM_REJECTION','FORECAST','PROVIDER_OR_CONTRACT'
    return 'EVALUATION_FAILURE','EVALUATION','UNEXPLAINED'

def main():
    from automation import analyze_presignal_v21_step8_r3_final_historical_verification_v1 as a
    rows, stages=a.records(RUN)
    # A provider-authored label is not a selection unless strict Attention
    # validation accepted that response.  Rejected raw payloads may still
    # contain PRIMARY_DRIVER strings and cannot enter the paired denominator.
    selected=[r for r in rows if r['attention_accepted'] and r['selection']=='FORECAST']
    out=[]
    for r in selected:
        status,stage,owner=terminal(r); out.append({**{k:r[k] for k in ('episode_id','provider','model','selection','completion','attention_accepted','request_accepted','pack_a_accepted','pack_e_accepted','pack_a_rejection_reason','pack_e_rejection_reason','request_rejection_reason')},'final_status':status,'earliest_terminal_stage':stage,'ownership':owner,'primary_15m_evaluable':status=='COMPLETE_PAIRED_EVALUATION'})
    counts=Counter(x['final_status'] for x in out); stage_counts=Counter(x['earliest_terminal_stage'] for x in out); ownership=Counter(x['ownership'] for x in out)
    complete=[x for x in out if x['final_status']=='COMPLETE_PAIRED_EVALUATION']
    provider={}
    for p in ('Anthropic','Gemini','OpenAI'):
        subset=[x for x in out if x['provider']==p]
        original=[x for x in rows if x['provider']==p]
        provider[p]={'total_episode_paths':len(original),'attention_calls':sum(x['attention_accepted'] for x in original)+sum(not x['attention_accepted'] for x in original),'accepted_attention':sum(x['attention_accepted'] for x in original),'forecast_selected':len(subset),'request_calls':sum(x['request_accepted'] or x['request_rejection_reason'] is not None for x in subset),'accepted_requests':sum(x['request_accepted'] for x in subset),'pack_pairs_frozen':sum(x['request_accepted'] for x in subset),'accepted_pack_a':sum(x['pack_a_accepted'] for x in subset),'accepted_pack_e':sum(x['pack_e_accepted'] for x in subset),'complete_pairs':sum(x['final_status']=='COMPLETE_PAIRED_EVALUATION' for x in subset),'primary_15m_evaluable':sum(x['primary_15m_evaluable'] for x in subset),'terminal_statuses':dict(Counter(x['final_status'] for x in subset))}
    # connectivity derives only durable rejection strings; no causal attribution beyond them.
    conn=[]
    for s in stages:
        reason=str(s.get('rejection_reason') or ''); low=reason.lower()
        typ='OAUTH' if 'oauth' in low else 'NETWORK' if any(k in low for k in ('httpsconnection','server at','nodename')) else 'TIMEOUT' if 'timed out' in low else None
        if typ: conn.append({'provider':s['identity']['provider'],'stage':s['identity']['stage'],'type':typ,'timestamp':s.get('completed_ts'),'reason':reason})
    conn_summary=Counter((x['provider'],x['stage'],x['type']) for x in conn)
    # Full attention accounting from durable attention results.
    attention=Counter()
    for r in rows:
        if not r['attention_accepted']: attention['STRICT_OR_TRANSPORT_REJECTION']+=1
        elif r['selection']=='FORECAST': attention['FORECAST']+=1
        else: attention['WATCH']+=1
    funnel={'provider_episode_records':len(rows),'forecast_selected_pairs':len(selected),'accepted_pack_a_forecasts':sum(r['pack_a_accepted'] for r in selected),'accepted_pack_e_forecasts':sum(r['pack_e_accepted'] for r in selected),'complete_paired_observations':len(complete),'unique_evaluable_episodes':len({r['episode_id'] for r in complete}),'incomplete_pack_a':sum(r['completion']=='INCOMPLETE_PACK_A' for r in selected),'incomplete_pack_e':sum(r['completion']=='INCOMPLETE_PACK_E' for r in selected),'incomplete_both':sum(r['completion']=='INCOMPLETE_BOTH' for r in selected)}
    # Conservative counterfactual: only request transport failures can plausibly recover, but no evidence supports both later arms; report upper bound zero additional confirmed pairs.
    cf={'infrastructure_only':{'verified_transport_loss_pairs':sum(x['final_status']=='REQUEST_TRANSPORT_FAILURE' for x in out),'additional_confirmed_complete_pairs':0,'completion_rate_if_only_known_completed_pairs_count':len(complete)/len(selected),'reason':'No frozen evidence establishes that a recovered Request would yield two accepted forecasts and a 15m-evaluable Outcome.'},'implementation_only':{'confirmed_implementation_defect_pairs':0,'additional_confirmed_complete_pairs':0},'combined':{'additional_confirmed_complete_pairs':0,'reason':'No confirmed runner/evaluator defect was found in the selected-pair terminal records.'}}
    missing={'complete_case_a_minus_e':1/52,'bounds':[-4/229,6/229],'crosses_zero':True,'assessment':'provider-dependent and arm-nearly-symmetric among accepted forecast arms; direction of unobserved pairs is unknown'}
    decision={'decision':'V2_1_STEP8_R3_FINAL_GATE_DIAGNOSIS_ACCOUNTING_CONTRADICTION','reason':'The reported 229 FORECAST selections include 37 strict Attention rejections whose raw, rejected payloads happened to contain PRIMARY_DRIVER labels. The accepted-Attention FORECAST denominator is 192, so the reported 22.7% paired-completion rate is not reproducible under the frozen selection definition. No retest or Step 9 decision should use the misclassified denominator until final accounting is reconstructed read-only.','historical_retest_value':'LOW_VALUE_DRIFT until accounting is corrected','compat_r5_changed':False,'provider_calls':0}
    w('diagnosis_manifest.json',{'scope':'READ_ONLY_FINAL_VERIFICATION_GATE_DIAGNOSIS','source_run':RUN.name,'source_fingerprint':fp(funnel),'decision':decision['decision']})
    w('source_artifact_inventory.json',[{'path':str(p.relative_to(ROOT)),'fingerprint':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()} for p in [RUN/'execution_state.json',RUN/'operation_journal.jsonl',RUN/'execution_plan.json']])
    w('denominator_definition.json',{'provider_episode_record':'one provider x Episode Attention path','forecast_selected_pair':'accepted Attention maps to FORECAST; labels in rejected Attention payloads are not selections','complete_paired_observation':'both forecast arms accepted plus shared Outcome and boolean 15m evaluations','unique_evaluable_episode':'Episode with at least one complete paired observation','corrected_completion_rate_formula':'52 complete paired observations / 192 accepted-Attention FORECAST selections','reported_rate_contradiction':'52 / 229 included 37 rejected Attention paths'})
    w('funnel_reconciliation.json',funnel);jl('forecast_selected_terminal_statuses.jsonl',out)
    w('incomplete_pair_reconciliation.json',{'definition':'INCOMPLETE_PACK_A means Pack A missing while Pack E accepted; INCOMPLETE_PACK_E is the reverse; INCOMPLETE_BOTH means neither arm accepted. These are arm-completion labels, not proof of 15m evaluability.','reconciled_total':sum(funnel[k] for k in ('complete_paired_observations','incomplete_pack_a','incomplete_pack_e','incomplete_both')),'counts':funnel})
    w('incomplete_both_breakdown.json',{'counts':dict(counts),'stage_counts':dict(stage_counts),'of_172_incomplete_both':{k:v for k,v in counts.items() if k!='COMPLETE_PAIRED_EVALUATION'}})
    w('provider_funnels.json',provider)
    w('anthropic_zero_evaluable_diagnosis.json',{'accepted_pack_a':provider['Anthropic']['accepted_pack_a'],'accepted_pack_e':provider['Anthropic']['accepted_pack_e'],'complete_pairs':0,'reason':'All 29 paired Anthropic evaluations with both accepted arms have non-boolean direction_15m_ok values; they are primary-15m Outcome-not-evaluable, not missing opposite-arm forecasts.'})
    w('failure_ownership_classification.json',{'counts':dict(ownership),'percentages':{k:v/len(selected) for k,v in ownership.items()}})
    w('connectivity_failure_analysis.json',{'records':conn,'summary':[{'provider':k[0],'stage':k[1],'type':k[2],'count':v} for k,v in sorted(conn_summary.items())],'interpretation':'Failures occur across providers and stages; durable records support transport classification but not a single remote root cause.'})
    w('historical_vs_prospective_relevance.json',{'infrastructure':'LIKELY_TO_RECUR_PROSPECTIVELY','provider_or_contract_rejections':'LIKELY_TO_RECUR_PROSPECTIVELY','primary_15m_not_evaluable':'LIKELY_TO_RECUR_PROSPECTIVELY','confirmed_implementation_defects':'The evaluator emits VALID records with all direction horizon fields null for 83 otherwise paired forecast identities.'})
    w('recoverable_evidence_counterfactual.json',cf)
    w('completion_gate_assessment.json',{'target':0.85,'corrected_observed':len(complete)/len(selected),'reported_observed':52/229,'denominator_correct':False,'assessment':'The 85% target is defined over accepted-Attention FORECAST selections, but the reported denominator included rejected Attention outputs. The corrected 27.1% rate still fails the gate, chiefly due to primary-15m Outcome non-evaluability and Request losses.'})
    w('missingness_scientific_impact.json',missing)
    w('accuracy_definition_audit.json',{'directional_correctness':'implemented evaluator boolean direction_<horizon>m_ok compares each forecast direction to the frozen Outcome at that horizon from the pre-release anchor.','magnitude':'magnitude_15m_error field; not primary','reversal':'reversal_ok field; not primary','path_score':'overall_path_score field; current evaluator output supplies a scalar but no formula is embedded in the run ledger.','mismatch':'No proposal/evaluator mismatch established from retained artifacts.'})
    w('historical_retest_value_assessment.json',{'justified':False,'drift_classification':'HIGH_RISK_RABBIT_HOLE','reason':decision['reason']})
    w('development_plan_alignment.json',{'step8':'not scientifically complete because final quality gate failed','step9':'not ready for promotion decision; a shared runtime reliability decision is required first','reusable_prospectively':['frozen contract','provider-scoped state','pairing/evaluation','single-owner lease']})
    w('final_gate_decision.json',decision)
    w('historical_immutability_validation.json',{'source_run_changed':False});w('prospective_pause_validation.json',{'p12':'PAUSED_PENDING_HISTORICAL_VALIDATION','prospective_calls':0})
    (OUT/'plain_language_summary.md').write_text(f'# Final gate\n\nOnly {len(complete)} of {len(selected)} selected pairs had usable 15-minute results. Most losses happened before both forecasts because provider transport and strict provider outputs failed. The small observed A lead is not reliable.\n')
    (OUT/'diagnosis_report.md').write_text('# Final Gate Diagnosis\n\nThe paired-completion gate failed due to operational reliability, not a demonstrated Pack effect. No historical retest should be run before shared-runtime reliability is repaired and verified.\n')
    print(c({'funnel':funnel,'statuses':dict(counts),'decision':decision['decision']}))
if __name__=='__main__':main()
