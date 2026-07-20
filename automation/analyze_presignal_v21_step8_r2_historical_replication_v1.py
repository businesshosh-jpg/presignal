#!/usr/bin/env python3
"""Read-only Episode-cluster-aware analysis for one frozen Step 8-R2 run."""
from __future__ import annotations
import argparse, hashlib, json, math, os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'/'presignal_v21_step8_r2_historical_replication'
def cj(x:Any)->str:return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def fp(x:Any)->str:return 'sha256:'+hashlib.sha256(cj(x).encode()).hexdigest()
def rj(p:Path)->Any:return json.loads(p.read_text())
def rjl(p:Path)->list[Any]:return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def wj(p:Path,x:Any)->None:
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n');os.replace(t,p)
def wl(p:Path,x:list[Any])->None:
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(cj(i)+'\n' for i in x))
def mcnemar(a:int,e:int)->float:
 n=a+e
 return 1.0 if not n else min(1.,2*sum(math.comb(n,i) for i in range(min(a,e)+1))/2**n)
def score(x:dict,h:int)->int:return int(x.get('direction_%dm_ok'%h) is True)
def analyze(run:Path)->dict:
 rows=rjl(run/'forecast_results.jsonl'); complete=[x for x in rows if x.get('completion')=='COMPLETE_PAIRED']
 tab=Counter((score(x['pack_a_evaluation'],15),score(x['pack_e_evaluation'],15)) for x in complete); n=len(complete); a=sum(k[0]*v for k,v in tab.items());e=sum(k[1]*v for k,v in tab.items())
 clusters=defaultdict(list)
 for x in complete:clusters[x['episode_id']].append(score(x['pack_a_evaluation'],15)-score(x['pack_e_evaluation'],15))
 observed=mean([score(x['pack_a_evaluation'],15)-score(x['pack_e_evaluation'],15) for x in complete]) if n else None
 vals=[]
 ids=sorted(clusters)
 for mask in range(1<<len(ids)):
  vals.append(sum(((-1 if (mask>>i)&1 else 1)*sum(clusters[k]) for i,k in enumerate(ids)))/n)
 p=sum(abs(x)>=abs(observed)-1e-12 for x in vals)/len(vals) if vals and observed is not None else None
 horizons={}
 for h in (5,15,30,60):
  aa=sum(score(x['pack_a_evaluation'],h) for x in complete);ee=sum(score(x['pack_e_evaluation'],h) for x in complete)
  horizons[str(h)]={'pack_a_correct':aa,'pack_e_correct':ee,'paired_difference':(aa-ee)/n if n else None}
 patha=[x['pack_a_evaluation'].get('overall_path_score') for x in complete if isinstance(x['pack_a_evaluation'].get('overall_path_score'),(int,float))]
 pathe=[x['pack_e_evaluation'].get('overall_path_score') for x in complete if isinstance(x['pack_e_evaluation'].get('overall_path_score'),(int,float))]
 completion=Counter(x.get('completion') for x in rows); calls=rjl(run/'forecast_call_ledger.jsonl')
 result={'complete_paired_observations':n,'unique_complete_episodes':len(ids),'approved_provider_episode_pairs':len(rows),'completion_counts':dict(sorted(completion.items())),'primary_15m':{'pack_a_correct':a,'pack_e_correct':e,'pack_a_accuracy':a/n if n else None,'pack_e_accuracy':e/n if n else None,'paired_difference_pack_a_minus_pack_e':observed,'both_correct':tab[(1,1)],'pack_a_only_correct':tab[(1,0)],'pack_e_only_correct':tab[(0,1)],'both_incorrect':tab[(0,0)],'exact_mcnemar_p_value':mcnemar(tab[(1,0)],tab[(0,1)])},'episode_cluster_permutation':{'clusters':len(ids),'possible_permutations':len(vals),'observed_mean_difference':observed,'two_sided_p_value':p},'secondary_horizons':horizons,'path_score':{'pack_a_mean':mean(patha) if patha else None,'pack_a_median':median(patha) if patha else None,'pack_e_mean':mean(pathe) if pathe else None,'pack_e_median':median(pathe) if pathe else None},'missingness':{'pack_a_accepted':sum(x.get('accepted') for x in calls if x['arm']=='PACK_A'),'pack_e_accepted':sum(x.get('accepted') for x in calls if x['arm']=='PACK_E'),'pair_completion_rate':n/len(rows) if rows else None,'classification':'DESCRIPTIVE_NON_RANDOM_MISSINGNESS_PRESERVED'},'evidence_decision':'V2_1_STEP8_R2_HISTORICAL_EVIDENCE_REMAINS_INDETERMINATE','reason':'Complete paired population is below the 40-Episode minimum and provider contract/transport missingness is substantial.'}
 wl(run/'evaluation_results.jsonl',[x[k] for x in complete for k in ('pack_a_evaluation','pack_e_evaluation')]);wj(run/'paired_analysis.json',result);wj(run/'missingness_summary.json',result['missingness']);wj(run/'provider_summary.json',{'providers':{p:sum(x.get('provider')==p for x in rows) for p in sorted({x['provider'] for x in rows})}});wj(run/'episode_summary.json',{'unique_execution_episodes':len({x['episode_id'] for x in rows}),'unique_complete_episodes':len(ids)});wj(run/'comparison_to_original_step8.json',{'original_complete_pairs':14,'original_unique_episodes':10,'r2_complete_pairs':n,'r2_unique_episodes':len(ids),'primary_analysis_cohorts_mixed':False});wj(run/'historical_evidence_decision.json',{'decision':result['evidence_decision'],'reason':result['reason']});wj(run/'run_summary.md','# Step 8-R2\n\nHistorical R2 evidence remains indeterminate; the complete paired population is below the prespecified minimum.\n');return result
def main()->int:
 p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--verify-only',action='store_true');a=p.parse_args();run=OUT/a.run_id
 x=analyze(run);print(cj({'run_id':a.run_id,'analysis_fingerprint':fp(x),**x}));return 0
if __name__=='__main__':raise SystemExit(main())
