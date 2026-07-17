"""Offline fixture executor; never dispatches a provider without an injected dispatcher."""
from __future__ import annotations
import json, uuid
from pathlib import Path
from typing import Mapping, Any
from automation.simplified_authoritative_replay_contract_v1 import validate_and_resolve
def execute(package:Path, identity:Mapping[str,Any], members, response:Mapping[str,Any], run_id='FUTURE-TEST-RUN'):
    logs=package/'canary_ledgers'; logs.mkdir(exist_ok=True); fid=identity['forecast_identity']; raw=logs/(fid+'.raw.json'); raw.write_text(json.dumps(response))
    inv={'identity_id':fid,'run_id':run_id,'provider':identity['provider'],'requested_model':identity['model'],'raw_response_reference':str(raw)}
    (logs/(fid+'.invocation.json')).write_text(json.dumps(inv))
    accepted=logs/(fid+'.prediction.json')
    if accepted.exists(): raise ValueError('DUPLICATE_ACCEPTED_IDENTITY')
    if response.get('actual_provider')!=identity['provider'] or response.get('actual_model')!=identity['model']: raise ValueError('PROVIDER_MODEL_MISMATCH')
    payload=json.loads(response['raw_output']); resolved=validate_and_resolve(payload,members)
    transaction='TX_'+uuid.uuid4().hex; prediction={**inv,**resolved,'package_id':json.loads((package/'package_manifest.json').read_text())['package_id'],'actual_model':response['actual_model'],'transaction_reference':transaction}
    accepted.write_text(json.dumps(prediction)); return prediction
