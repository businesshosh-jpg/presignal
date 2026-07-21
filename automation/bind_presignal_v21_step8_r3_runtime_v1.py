"""Manifest-bound, call-free runtime adapter for R3 historical verification."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Mapping
from automation import presignal_v21_historical_verification_r3_contract_v1 as contract
from automation import presignal_v21_prospective_flat_contract_v1 as parent

ROOT=Path(__file__).resolve().parents[1]
PREP=ROOT/'outputs/presignal_v21_step8_r3_repair/STEP8-R3-REPAIR-df9c25e/fresh_verification_manifest.json'
EXPECTED='sha256:ca2e8053e0302dbd08d640c858877b4bd93b4177fcbe6cbc99d6db125a46f9fa'
class BindingError(RuntimeError):pass
def fingerprint(x:Any)->str:return 'sha256:'+hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load_manifest(path:Path=PREP)->dict[str,Any]:
 m=json.loads(path.read_text()); spec=m.get('contract',{})
 if spec.get('contract_version')!=contract.CONTRACT_VERSION:raise BindingError('R3_CONTRACT_REQUIRED')
 if spec.get('contract_fingerprint')!=EXPECTED or spec!=contract.spec():raise BindingError('R3_CONTRACT_FINGERPRINT_DRIFT')
 return m
def attention_parser(provider:str, raw:Any)->dict[str,Any]:
 if provider=='Anthropic':return contract.extract_json_object(raw)
 # R3 requires unambiguous strict JSON for every other provider too.
 return contract.extract_json_object(raw)
def forecast_prompt(input_row:Mapping[str,Any], provider:str)->str:
 if provider not in ('Gemini','OpenAI','Anthropic'):raise BindingError('EXACT_PROVIDER_REQUIRED')
 base=parent.prospective_prompt_text(parent.prospective_context(input_row,parent.PROSPECTIVE_CONTRACT_VERSION),parent.PROSPECTIVE_CONTRACT_VERSION)
 rule=contract.PROMPT_RULES['gemini_pips'] if provider=='Gemini' else contract.PROMPT_RULES['openai_reversal'] if provider=='OpenAI' else contract.PROMPT_RULES['anthropic_json']
 return base+'\n\nR3 historical-verification compatibility rule: '+rule
def missingness(records:list[Mapping[str,Any]])->dict[str,Any]:
 forecast=[r for r in records if r.get('selection')=='FORECAST']; complete=[r for r in forecast if r.get('completion')=='COMPLETE_PAIRED']
 diff=sum(int(r['pack_a_evaluation']['direction_15m_ok'] is True)-int(r['pack_e_evaluation']['direction_15m_ok'] is True) for r in complete)
 a_missing=sum(r.get('completion')=='INCOMPLETE_PACK_A' for r in forecast);e_missing=sum(r.get('completion')=='INCOMPLETE_PACK_E' for r in forecast)
 den=len(forecast)
 return {'estimand':'FORECAST_SELECTED_PAIRS','denominator':den,'complete_case_difference':diff/len(complete) if complete else None,'worst_pack_a':(diff-a_missing-e_missing)/den if den else None,'worst_pack_e':(diff+a_missing+e_missing)/den if den else None,'incomplete_both':'excluded_symmetrically'}
def gate()->dict[str,Any]:
 m=load_manifest();return {'status':'R3_RUNTIME_BINDING_VALIDATED','manifest_fingerprint':fingerprint(m),'contract':contract.spec(),'provider_routes':m['providers'],'provider_calls':0,'execution_enabled':False}
