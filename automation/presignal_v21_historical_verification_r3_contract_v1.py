"""Compatibility-only R3 contract overlay for a fresh historical cohort."""
from __future__ import annotations
import hashlib, json
from typing import Any
from automation import presignal_v21_prospective_flat_contract_v1 as parent

CONTRACT_VERSION='presignal_event_path_contract_v1_historical_verification_r3'
PARENT_CONTRACT_VERSION=parent.PROSPECTIVE_CONTRACT_VERSION
PROMPT_RULES={
 'anthropic_json':'Return one JSON object only. JSON inside one markdown fence is accepted, but no prose may make the object ambiguous.',
 'gemini_pips':'For UP use 0 <= expected_pips_min <= expected_pips_max; for DOWN use expected_pips_min <= expected_pips_max <= 0; for FLAT both values are 0.',
 'openai_reversal':'expected_reversal_flag is true only when a later stated horizon reverses the stated path direction; include that reversal horizon and do not contradict the stage directions.'}
def canonical(x:Any)->str:return json.dumps(x,sort_keys=True,separators=(',',':'))
def fingerprint(x:Any)->str:return 'sha256:'+hashlib.sha256(canonical(x).encode()).hexdigest()
def extract_json_object(raw:Any)->dict[str,Any]:
 if isinstance(raw,dict):return dict(raw)
 if not isinstance(raw,str):raise ValueError('PROVIDER_RAW_OBJECT_REQUIRED')
 text=raw.strip()
 if text.startswith('```') and text.endswith('```'):
  text='\n'.join(text.splitlines()[1:-1]).strip()
 try:value=json.loads(text)
 except json.JSONDecodeError as exc:raise ValueError('PROVIDER_RAW_JSON_INVALID') from exc
 if not isinstance(value,dict):raise ValueError('PROVIDER_RAW_OBJECT_REQUIRED')
 return value
def spec()->dict[str,Any]:
 inherited=parent.fingerprints(); base={'contract_version':CONTRACT_VERSION,'parent_contract_version':PARENT_CONTRACT_VERSION,'scope':'HISTORICAL_VERIFICATION_ONLY','prompt_rules':PROMPT_RULES,**inherited}
 base['contract_fingerprint']=fingerprint(base);return base
