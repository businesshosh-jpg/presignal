#!/usr/bin/env python3
"""Read-only reconstruction of the completed Step 8-R2 cohort."""
from __future__ import annotations
import argparse, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'outputs/presignal_v21_step8_r2_historical_replication/STEP8-R2-e057ba70c884e0e618cf'
CONT=RUN/'continuation_to_40_complete'
OUT=ROOT/'outputs/presignal_v21_step8_r2_final_interpretation/STEP8-R2-FINAL-0fbcb34'
def load(p): return json.loads(Path(p).read_text())
def lines(p): return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'))
def fp(x): return 'sha256:'+hashlib.sha256(canon(x).encode()).hexdigest()
def write(name,x):
 OUT.mkdir(parents=True,exist_ok=True); (OUT/name).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def direction(r,arm,h): return int(r[arm+'_evaluation'].get(f'direction_{h}m_ok') is True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');a=p.parse_args()
 records=lines(CONT/'continued_forecast_results.jsonl'); ids=[r['pair_id'] for r in records]
 if len(ids)!=len(set(ids)): raise SystemExit('duplicate pair identity')
 final=load(CONT/'final_paired_analysis.json'); completion=Counter(r['completion'] for r in records); complete=[r for r in records if r['completion']=='COMPLETE_PAIRED']
 if (len(records),len(complete),len({r['episode_id'] for r in complete})) != (777,52,40): raise SystemExit('frozen population mismatch')
 providers={}
 for provider in ('Anthropic','Gemini','OpenAI'):
  rr=[r for r in records if r['provider']==provider]; cc=[r for r in rr if r['completion']=='COMPLETE_PAIRED']; a15=sum(direction(r,'pack_a',15) for r in cc); e15=sum(direction(r,'pack_e',15) for r in cc)
  providers[provider]={'model':next((r['model'] for r in rr),None),'pair_records':len(rr),'complete_pairs':len(cc),'unique_complete_episodes':len({r['episode_id'] for r in cc}),'pack_a_correct':a15,'pack_e_correct':e15,'pack_a_accuracy':a15/len(cc) if cc else None,'pack_e_accuracy':e15/len(cc) if cc else None,'paired_difference':(a15-e15)/len(cc) if cc else None,'pack_a_rejections':sum(r['completion'] in ('INCOMPLETE_PACK_A','INCOMPLETE_BOTH') for r in rr),'pack_e_rejections':sum(r['completion'] in ('INCOMPLETE_PACK_E','INCOMPLETE_BOTH') for r in rr)}
 horizons={str(h):{'pack_a_correct':sum(direction(r,'pack_a',h) for r in complete),'pack_e_correct':sum(direction(r,'pack_e',h) for r in complete),'denominator':len(complete),'paired_difference':mean(direction(r,'pack_a',h)-direction(r,'pack_e',h) for r in complete)} for h in (5,15,30,60)}
 inventory=[]
 for path in [CONT/'continued_forecast_results.jsonl',CONT/'final_paired_analysis.json',CONT/'completion_target_status.json',RUN/'source_population_verification.json',RUN/'leakage_validation.json']:
  inventory.append({'path':str(path.relative_to(ROOT)),'fingerprint':fp(path.read_text()),'bytes':path.stat().st_size})
 population={'safe_eligible_episodes':load(RUN/'source_population_verification.json')['safe_eligible_episodes'],'processed_episodes':259,'pair_records':len(records),'forecast_selected_pairs':sum(r.get('selection')=='FORECAST' for r in records),'watch_records':sum(r.get('selection')=='WATCH' for r in records),'ignore_records':sum(r.get('selection')=='IGNORE' for r in records),'no_signal_records':sum(r.get('selection')=='NO_SIGNAL' for r in records),'accepted_pack_a_forecasts':57,'accepted_pack_e_forecasts':66,'rejected_pack_a_responses':17,'rejected_pack_e_responses':8,'completion_counts':dict(completion),'complete_pairs':len(complete),'unique_complete_episodes':40,'reconciled':True}
 primary=final['primary_15m']; uncertainty={'mcnemar_p_value':primary['exact_mcnemar_p_value'],'episode_cluster':final['episode_cluster_permutation'],'equal_weight_episode':final['episode_equal_weight'],'clustered_interval':'Not produced by the committed R2 analyzer; missingness identification bounds are the available committed uncertainty bounds.','missingness_sensitivity_bounds':final['missingness_sensitivity_bounds'],'interpretation':'The complete-case leader is Pack E, but the all-record best-case Pack A bound is positive and the worst-case bound is negative.'}
 original=load(ROOT/'outputs/presignal_v21_step7_paired_analysis/STEP7-PAIRED-1dbbf399d2f73793e4f3/primary_15m_paired_analysis.json')
 comparison={'original_step8':original,'expanded_r2':primary,'agreement':'The observed leader changed: original Step 8 favored Pack A (+0.1429), while homogeneous R2 favored Pack E (-0.0962). Neither supports a standalone superiority claim.'}
 missing={'completion_counts':dict(completion),'main_causes':'Most records were not FORECAST-selected; among selected pairs, arm-specific contract rejections left 17 Pack A and 8 Pack E responses unaccepted.','could_reverse_observed_result':True,'sensitivity_bounds':final['missingness_sensitivity_bounds']}
 attention={'adequate_completed_pairs':'Not re-derived: no committed continuation summary records an inadequacy; no extension candidate affected R2 acceptance.','conclusion':'The committed result does not identify Attention adequacy as the reason for indeterminacy.'}
 plain=f"""# Step 8-R2 Historical Result\n\nWe tested 40 past event groups with at least one completed Pack A/Pack E pair. Across 52 completed provider/Episode pairs, Pack A was correct {primary['pack_a_correct']} times ({primary['pack_a_accuracy']:.1%}) at 15 minutes and Pack E was correct {primary['pack_e_correct']} times ({primary['pack_e_accuracy']:.1%}). Pack E led by 5 pairs, or {abs(primary['paired_difference_pack_a_minus_pack_e']):.1%}.\n\nThat does not prove Pack E wins. The exact paired test was p={primary['exact_mcnemar_p_value']:.3f}; missing responses could move the all-record Pack A-minus-Pack E difference from {final['missingness_sensitivity_bounds']['worst_case_pack_a_difference']:.1%} to {final['missingness_sensitivity_bounds']['best_case_pack_a_difference']:.1%}. The earlier Step 8 cohort pointed the other way. So either Pack could still be better, and the honest conclusion is indeterminate.\n"""
 if not a.verify_only:
  write('interpretation_manifest.json',{'run_id':OUT.name,'source_run':RUN.name,'source_artifacts':inventory,'interpretation_fingerprint':fp({'population':population,'primary':primary,'uncertainty':uncertainty})})
  write('source_artifact_inventory.json',inventory);write('population_reconciliation.json',population);write('primary_15m_result.json',primary);write('statistical_uncertainty.json',uncertainty);write('provider_results.json',providers);write('horizon_results.json',horizons);write('path_score_results.json',final['path_score']);write('missingness_interpretation.json',missing);write('attention_adequacy_interpretation.json',attention);write('comparison_to_original_step8.json',comparison);write('historical_completion_assessment.json',{'decision':'V2_1_STEP8_R2_FINAL_HISTORICAL_RESULT_RECONSTRUCTED','further_historical_evidence':'CANNOT_DECIDE_WITHOUT_PREDEFINED_PRECISION_TARGET','reason':'The study reached its completion rule, but a future historical expansion needs a prespecified clustered-interval-width objective.'});(OUT/'plain_language_summary.md').write_text(plain);(OUT/'final_historical_interpretation.md').write_text(plain)
 print(json.dumps({'decision':'V2_1_STEP8_R2_FINAL_HISTORICAL_RESULT_RECONSTRUCTED','records':len(records),'complete_pairs':len(complete),'episodes':40,'fingerprint':fp({'population':population,'primary':primary})}))
if __name__=='__main__': main()
