#!/usr/bin/env python3
"""Append-only continuation of the frozen Step 8-R2 historical cohort."""
from __future__ import annotations
import argparse, json, math, os, random, sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from automation import run_presignal_v21_step8_r2_historical_replication_v1 as parent
PARENT_RUN="STEP8-R2-e057ba70c884e0e618cf"
CEILING=400; TARGET=40; CHECKPOINT=20
def read(path:Path)->Any:return json.loads(path.read_text())
def rows(path:Path)->list[Any]:return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def write(path:Path,x:Any)->None: parent.write_json(path,x)
def writel(path:Path,x:list[Any])->None: parent.write_jsonl(path,x)
def complete_episode_ids(run:Path)->set[str]:
 return {x['episode_id'] for x in rows(run/'forecast_results.jsonl') if x.get('completion')=='COMPLETE_PAIRED'}
def existing_episode_ids(run:Path)->set[str]:
 return {x['episode_id'] for x in read(run/'frozen_execution_population.json')['episodes']}
def continuation_dir(run:Path)->Path:return run/'continuation_to_40_complete'
def selected_ids(path:Path)->set[str]:
 return {x['episode_id'] for x in rows(path) if isinstance(x,dict) and x.get('episode_id')} if path.exists() else set()
def accepted_counts(records:list[dict[str,Any]])->tuple[int,int]:
 return (
  sum(x.get('completion') in {'COMPLETE_PAIRED','INCOMPLETE_PACK_E'} for x in records),
  sum(x.get('completion') in {'COMPLETE_PAIRED','INCOMPLETE_PACK_A'} for x in records),
 )
def unique_records(records:list[dict[str,Any]])->list[dict[str,Any]]:
 """Preserve the first immutable pair record if a resumed invocation replays it."""
 seen=set(); result=[]
 for record in records:
  identity=record.get('pair_id')
  if not identity or identity not in seen:
   result.append(record); seen.add(identity)
 return result
def complete_episode_count(records:list[dict[str,Any]])->int:
 return len({x['episode_id'] for x in records if x.get('completion')=='COMPLETE_PAIRED'})
def mcnemar(a:int,e:int)->float:
 n=a+e
 return 1.0 if not n else min(1.0,2*sum(math.comb(n,i) for i in range(min(a,e)+1))/2**n)
def analyze(records:list[dict[str,Any]])->dict[str,Any]:
 complete=[x for x in records if x.get('completion')=='COMPLETE_PAIRED']
 def ok(x:dict[str,Any],arm:str,h:int)->int:
  return int(x[arm+'_evaluation'].get('direction_%dm_ok'%h) is True)
 n=len(complete); table=Counter((ok(x,'pack_a',15),ok(x,'pack_e',15)) for x in complete)
 diffs=[ok(x,'pack_a',15)-ok(x,'pack_e',15) for x in complete]
 clusters=defaultdict(list)
 for x,d in zip(complete,diffs):clusters[x['episode_id']].append(d)
 episode_ids=sorted(clusters); observed=mean(diffs) if diffs else None
 possible=1<<len(episode_ids)
 # Exact enumeration remains practical for small cohorts; larger cohorts use
 # preregistered fixed-seed sign flips and never treat provider rows as independent.
 masks=range(possible) if possible<=65536 else (random.Random(20260721).getrandbits(len(episode_ids)) for _ in range(100000))
 permutations=[sum((-1 if (mask>>index)&1 else 1)*sum(clusters[eid]) for index,eid in enumerate(episode_ids))/n for mask in masks]
 extreme=sum(abs(x)>=abs(observed)-1e-12 for x in permutations)
 p=((extreme/len(permutations)) if possible<=65536 else ((extreme+1)/(len(permutations)+1))) if permutations and observed is not None else None
 horizons={}
 for horizon in (5,15,30,60):
  a=sum(ok(x,'pack_a',horizon) for x in complete); e=sum(ok(x,'pack_e',horizon) for x in complete)
  horizons[str(horizon)]={'pack_a_correct':a,'pack_e_correct':e,'paired_difference':(a-e)/n if n else None}
 path_a=[x['pack_a_evaluation'].get('overall_path_score') for x in complete if isinstance(x['pack_a_evaluation'].get('overall_path_score'),(int,float))]
 path_e=[x['pack_e_evaluation'].get('overall_path_score') for x in complete if isinstance(x['pack_e_evaluation'].get('overall_path_score'),(int,float))]
 episode_means=[mean(clusters[eid]) for eid in episode_ids]
 complete_by_episode={x['episode_id'] for x in complete}
 # Identification bounds hold accepted arms fixed and let each missing arm vary in {0,1}.
 total_pairs=len(records); observed_total=sum(diffs)
 incomplete_a=sum(x.get('completion')=='INCOMPLETE_PACK_A' for x in records)
 incomplete_e=sum(x.get('completion')=='INCOMPLETE_PACK_E' for x in records)
 incomplete_both=sum(x.get('completion')=='INCOMPLETE_BOTH' for x in records)
 return {
  'approved_provider_episode_pairs':total_pairs,
  'complete_paired_observations':n,
  'unique_complete_episodes':len(complete_by_episode),
  'primary_15m':{
   'pack_a_correct':sum(ok(x,'pack_a',15) for x in complete),'pack_e_correct':sum(ok(x,'pack_e',15) for x in complete),
   'pack_a_accuracy':sum(ok(x,'pack_a',15) for x in complete)/n if n else None,'pack_e_accuracy':sum(ok(x,'pack_e',15) for x in complete)/n if n else None,
   'paired_difference_pack_a_minus_pack_e':observed,'both_correct':table[(1,1)],'pack_a_only_correct':table[(1,0)],'pack_e_only_correct':table[(0,1)],'both_incorrect':table[(0,0)],
   'exact_mcnemar_p_value':mcnemar(table[(1,0)],table[(0,1)])},
  'episode_cluster_permutation':{'clusters':len(episode_ids),'possible_permutations':possible,'enumerated_permutations':len(permutations),'method':'EXACT_ENUMERATION' if possible<=65536 else 'FIXED_SEED_MONTE_CARLO','seed':None if possible<=65536 else 20260721,'observed_mean_difference':observed,'two_sided_p_value':p},
  'episode_equal_weight':{'episodes':len(episode_means),'mean_paired_difference':mean(episode_means) if episode_means else None},
  'secondary_horizons':horizons,
  'path_score':{'pack_a_mean':mean(path_a) if path_a else None,'pack_a_median':median(path_a) if path_a else None,'pack_e_mean':mean(path_e) if path_e else None,'pack_e_median':median(path_e) if path_e else None,'paired_mean_difference':mean([a-b for a,b in zip(path_a,path_e)]) if path_a and path_e else None},
  'missingness_sensitivity_bounds':{'worst_case_pack_a_difference':(observed_total-incomplete_a-incomplete_e)/total_pairs if total_pairs else None,'best_case_pack_a_difference':(observed_total+incomplete_a+incomplete_e)/total_pairs if total_pairs else None,'incomplete_both_pairs':incomplete_both},
  'provider_summary':{provider:{'approved_pairs':sum(x.get('provider')==provider for x in records),'complete_pairs':sum(x.get('provider')==provider and x.get('completion')=='COMPLETE_PAIRED' for x in records)} for provider in sorted({x.get('provider') for x in records})},
 }
def execute(*, parent_run:Path, max_new:int=CEILING-80, dry_run:bool=False)->dict[str,Any]:
 _summary,eligible,_excluded,_source=parent.recover_population(); prior=existing_episode_ids(parent_run)
 if len(prior)!=80:raise parent.Step8R2Error('PARENT_R2_POPULATION_NOT_80')
 out=continuation_dir(parent_run); out.mkdir(parents=True,exist_ok=True)
 continued_path=out/'continued_population.jsonl'
 already=prior|selected_ids(continued_path)
 ordered=[x for x in eligible if x['episode_id'] not in already][:max(0,min(max_new,CEILING-len(already)))]
 if dry_run:
  return {'out':str(out),'status':'DRY_RUN','existing_additional_episodes':len(already-prior),'planned_additional_episodes':len(ordered),'next_episode_id':ordered[0]['episode_id'] if ordered else None,'cumulative_processed_episodes':len(already)}
 write(out/'parent_r2_run_reference.json',{'parent_run_id':parent_run.name,'parent_execution_population_fingerprint':read(parent_run/'frozen_execution_population.json')['execution_population_fingerprint'],'parent_episodes':80,'contract_fingerprint':read(parent_run/'run_manifest.json')['contract_fingerprint']})
 existing_continued=rows(continued_path) if continued_path.exists() else []
 existing_results_path=out/'continued_forecast_results.jsonl'
 original_records=rows(parent_run/'forecast_results.jsonl')
 all_records=unique_records(rows(existing_results_path) if existing_results_path.exists() else list(original_records))
 existing_checkpoints=rows(out/'progress_checkpoints.jsonl') if (out/'progress_checkpoints.jsonl').exists() else []
 write(out/'continuation_manifest.json',{'parent_run_id':parent_run.name,'target_unique_complete_episodes':TARGET,'cumulative_ceiling':CEILING,'canonical_order':['scheduled_release_ts','session_id','episode_id'],'base_execution_population_fingerprint':read(parent_run/'frozen_execution_population.json')['execution_population_fingerprint'],'existing_additional_episodes':len(existing_continued),'invocation_population_fingerprint':parent.sha256(ordered),'planned_additional_episodes_this_invocation':len(ordered),'dry_run':dry_run})
 processed=len(existing_continued); checkpoints=list(existing_checkpoints); newly=[]
 for episode in ordered:
  if dry_run: result={'records':[]}
  else: result=parent.execute(parent_run,[episode])
  all_records=unique_records(all_records+result['records']); newly.append(episode); processed+=1
  if complete_episode_count(all_records)>=TARGET:break
  if processed%CHECKPOINT==0:
   a,e=accepted_counts(all_records)
   checkpoints.append({'additional_processed_episodes':processed,'cumulative_processed_episodes':80+processed,'unique_complete_episodes':complete_episode_count(all_records),'complete_paired_observations':sum(x.get('completion')=='COMPLETE_PAIRED' for x in all_records),'forecast_selected_pairs':sum(x.get('selection')=='FORECAST' for x in all_records),'accepted_pack_a_forecasts':a,'accepted_pack_e_forecasts':e,'rejected_responses':sum(x.get('completion','').startswith('INCOMPLETE') for x in all_records),'remaining_episode_budget':CEILING-(80+processed)})
 combined_population=existing_continued+newly
 a,e=accepted_counts(all_records)
 final={'additional_processed_episodes':len(combined_population),'cumulative_processed_episodes':80+len(combined_population),'unique_complete_episodes':complete_episode_count(all_records),'complete_paired_observations':sum(x.get('completion')=='COMPLETE_PAIRED' for x in all_records),'forecast_selected_pairs':sum(x.get('selection')=='FORECAST' for x in all_records),'accepted_pack_a_forecasts':a,'accepted_pack_e_forecasts':e,'rejected_responses':sum(x.get('completion','').startswith('INCOMPLETE') for x in all_records),'remaining_episode_budget':CEILING-(80+len(combined_population))}
 if not checkpoints or checkpoints[-1].get('additional_processed_episodes')!=final['additional_processed_episodes']:checkpoints.append(final)
 writel(continued_path,combined_population);writel(out/'progress_checkpoints.jsonl',checkpoints);writel(out/'continued_call_ledger.jsonl',[r for r in all_records if 'pair_id' in r]);writel(out/'continued_forecast_results.jsonl',[r for r in all_records if 'pair_id' in r]);writel(out/'continued_evaluations.jsonl',[r for r in all_records if r.get('completion')=='COMPLETE_PAIRED'])
 status='TARGET_REACHED' if final['unique_complete_episodes']>=TARGET else 'CEILING_REACHED' if final['cumulative_processed_episodes']>=CEILING else 'NO_EXECUTION'
 write(out/'completion_target_status.json',{'status':status,**final})
 if status in {'TARGET_REACHED','CEILING_REACHED'}:
  analysis=analyze(all_records)
  decision='V2_1_STEP8_R2_40_COMPLETE_HISTORICAL_EPISODES_ACCRUED' if status=='TARGET_REACHED' else 'V2_1_STEP8_R2_400_EPISODE_CEILING_REACHED_BELOW_COMPLETION_TARGET'
  evidence='HISTORICAL_EVIDENCE_REMAINS_INDETERMINATE'
  write(out/'final_paired_analysis.json',analysis);write(out/'historical_evidence_decision.json',{'decision':decision,'evidence_classification':evidence,'analysis_fingerprint':parent.sha256(analysis),'reason':'The pre-specified completion boundary, not outcome performance, ended historical accrual.'})
 return {'out':str(out),'status':status,**final}
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--parent-run',type=Path,default=ROOT/'outputs'/'presignal_v21_step8_r2_historical_replication'/PARENT_RUN);p.add_argument('--max-new',type=int,default=CEILING-80);p.add_argument('--dry-run',action='store_true');a=p.parse_args();print(json.dumps(execute(parent_run=a.parent_run,max_new=a.max_new,dry_run=a.dry_run),sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
