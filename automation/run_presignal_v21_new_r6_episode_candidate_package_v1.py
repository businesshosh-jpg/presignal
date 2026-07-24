"""Fail-closed evidence package for a bounded prospective R6 Event refresh."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/presignal_v21_designed_drift_r6_new_episode_refresh'/'R6-NEW-EPISODE-REFRESH-20260724-v1'
FREEZE='sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4'
TEMPORAL='sha256:d557c0733cc59982c46f71efaa89dad03a27e0d0c6023ba54eb2ef807c84c570'
CLOSURE='sha256:4c56f37ceb8507c0ea98d004c75f7d2ddd5433fe08e294da89d357b22f289656'

def canon(v:Any)->str:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def sha(v:Any)->str:return 'sha256:'+hashlib.sha256(canon(v).encode()).hexdigest()
def write(p:Path,v:Any)->None:p.parent.mkdir(parents=True,exist_ok=True);p.write_text(canon(v)+'\n')
def audit():return {'calendar_refresh_calls':0,'google_event_reads':0,'google_event_writes':0,'gemini_calls':0,'other_ai_provider_calls':0,'attention_calls':0,'information_request_calls':0,'forecast_calls':0,'pack_a_constructions':0,'pack_e_acquisitions':0,'pack_e_computations':0,'r6_paired_evidence_writes':0,'outcome_operations':0,'evaluation_operations':0}
def reports(reference_utc:str)->dict[str,Any]:
 start=datetime.fromisoformat(reference_utc.replace('Z','+00:00')).astimezone(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0); end=start+timedelta(days=7)
 window={'start_utc':start.isoformat().replace('+00:00','Z'),'end_utc':end.isoformat().replace('+00:00','Z'),'rule':'current UTC date through +7 calendar days'}
 package={'package_name':'PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_EPISODE_CANDIDATE_PACKAGE_V1','route_b_freeze_fingerprint':FREEZE,'temporal_scope_alignment_fingerprint':TEMPORAL,'pmi_attempt_closure_fingerprint':CLOSURE,'calendar_source_identity':'FMP_ECONOMIC_CALENDAR','refresh_window':window,'frozen_reference_timestamp':reference_utc,'canonical_event_set_checksum':sha([]),'canonical_episode_set_checksum':sha([]),'eligible_candidate_identities':[],'excluded_candidate_identities':[],'selection_rule_status':'NOT_EVALUATED_REFRESH_BLOCKED','recommended_candidate':None,'request_prompt_version':'presignal_v21_information_request_prompt_v2','request_prompt_checksum':'sha256:219b3d33989d06b5f1968f6024c0135454320cf6c8f545116c6595d630011cb5','category_enum_checksum':'sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52','old_pmi_attention_reused':False,'old_pmi_request_response_reused':False}
 blocker={'attempted_operation':'apiUpsertEventWindow','transport':'existing Google Apps Script -> FMP economic calendar route','window':window,'status':'BLOCKED_BEFORE_DISPATCH','error_category':'GOOGLE_OAUTH_TOKEN_MISSING','dispatch_certainty':'CONFIRMED_NOT_SENT','error':'Missing or insufficient Google API token. Run `python3 auth_sheets.py` once to bootstrap persistent auth.','calendar_refresh_calls':0,'google_event_reads':0,'google_event_writes':0}
 return {'prospective_event_refresh_manifest.json':{'reference_utc_timestamp':reference_utc,'refresh_window':window,'bounded_extension_attempted':False,'status':'BLOCKED_BEFORE_EVENT_RETRIEVAL'},'prospective_event_source_binding.json':{'source_identity':'FMP_ECONOMIC_CALENDAR','configuration_path':'apps_script/fmp_calendar.js:runFmpRangeToEvent_','adapter':'apps_script/automation_api.js:apiUpsertEventWindow','binding_status':'AUTHORIZED_EXISTING_V2_1_PATH'},'prospective_event_refresh_report.json':blocker,'canonical_future_events.json':{'status':'NOT_CREATED_REFRESH_BLOCKED','events':[],'checksum':sha([])},'canonical_future_episodes.json':{'status':'NOT_CREATED_REFRESH_BLOCKED','episodes':[],'checksum':sha([])},'episode_eligibility_report.json':{'eligible_episode_count':0,'status':'NOT_EVALUATED_REFRESH_BLOCKED'},'episode_exclusion_report.json':{'closed_pmi_episode_excluded':'EP_BATCH_0b3bf1cac3c02da74063','excluded_episodes':[],'status':'NO_NEW_EVENT_POPULATION'},'execution_buffer_report.json':{'authoritative_minimum_execution_buffer_rule':'NOT_FOUND','operational_classification':'NOT_EVALUATED_REFRESH_BLOCKED','scientific_cutoff_changed':False},'episode_selection_rule_trace.json':{'existing_authoritative_rule_found':False,'rule_path':'automation/presignal_v21_prospective_episode_refresh_v1.py:candidate_decision','rule_result':'NOT_EVALUATED_REFRESH_BLOCKED','invented_tie_breaker':False},'new_r6_episode_candidate_package.json':package,'new_r6_episode_candidate_package_fingerprint.json':{'package_name':package['package_name'],'package_fingerprint':sha(package),'reproducible':True},'external_access_audit.json':audit(),'final_new_r6_episode_refresh_decision.json':{'decision':'NEW_R6_EPISODE_REFRESH_BLOCKED','reason':'GOOGLE_OAUTH_TOKEN_MISSING','attention_authorization_created':False}}
def run(output:Path=OUT,reference_utc:str|None=None):
 ref=reference_utc or datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
 for n,v in reports(ref).items():write(output/n,v)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=OUT);p.add_argument('--reference-utc');a=p.parse_args();run(a.output,a.reference_utc)
