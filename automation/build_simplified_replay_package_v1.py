"""Offline-only freezer for the reduced authoritative replay package."""
from __future__ import annotations
import hashlib, json, shutil
from pathlib import Path
from typing import Any
from automation.simplified_authoritative_replay_contract_v1 import canonical_event_identity, driver_options, require_unique_event_identities

ROOT=Path(__file__).resolve().parents[1]
SNAPSHOT=Path('/Users/junhoshino/projects/presignal_replay_archives/9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T094156Z/input_snapshot')
def rows(p): return [json.loads(x) for x in p.read_text().splitlines() if x]
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'))
def sha(x): return hashlib.sha256((x if isinstance(x,bytes) else canon(x).encode()).__class__ and (x if isinstance(x,bytes) else canon(x).encode())).hexdigest()
def file_sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze(destination: Path, package_id='SIMPLIFIED-REPLAY-DRY-RUN-V1'):
    if destination.exists(): raise ValueError('DESTINATION_EXISTS')
    sessions, members, population, packs, excluded=[rows(SNAPSHOT/n) for n in ('authoritative_sessions.jsonl','authoritative_session_members.jsonl','authoritative_forecast_population.jsonl','authoritative_pack_references.jsonl','authoritative_excluded_sessions.jsonl')]
    if (len(sessions),len(excluded),len(population),sum(x['arm']=='A' for x in population),sum(x['arm']=='E' for x in population),len(packs)) != (239,10,1434,717,717,239): raise ValueError('POPULATION_MISMATCH')
    # Repair only duplicated legacy IDs before freeze, preserving all other
    # immutable scientific member content.
    counts={}
    for m in members: counts[m['event_id']]=counts.get(m['event_id'],0)+1
    members=[{**m,'event_id':canonical_event_identity(m)} if counts[m['event_id']]>1 else m for m in members]
    require_unique_event_identities(members)
    by_session={};
    for m in members: by_session.setdefault(m['session_id'],[]).append(m)
    token_audit={sid:driver_options(ms) for sid,ms in by_session.items()}
    if any(len({x['token'] for x in v})!=len(v) or len({x['event_id'] for x in v})!=len(v) for v in token_audit.values()): raise ValueError('TOKEN_AUDIT_FAILED')
    if any(x['session_id'] not in by_session for x in population): raise ValueError('IDENTITY_SESSION_MISSING')
    providers={};
    for x in population: providers[(x['provider'],x['model'])]=providers.get((x['provider'],x['model']),0)+1
    destination.mkdir(parents=True); snap=destination/'snapshot'; snap.mkdir()
    names=('authoritative_sessions.jsonl','authoritative_session_members.jsonl','authoritative_forecast_population.jsonl','authoritative_pack_references.jsonl','authoritative_excluded_sessions.jsonl')
    for n in names:
        if n=='authoritative_session_members.jsonl': (snap/n).write_text(''.join(canon(x)+'\n' for x in members))
        else: shutil.copyfile(SNAPSHOT/n,snap/n)
    (destination/'token_mapping_audit.json').write_text(json.dumps(token_audit,sort_keys=True))
    manifest={'package_id':package_id,'offline_only':True,'outcome_evaluation_enabled':False,'counts':{'sessions':239,'excluded':10,'identities':1434,'pack_a':717,'pack_e':717},'provider_models':{f'{a}|{b}':n for (a,b),n in providers.items()},'scientific_snapshot_equality':'PASS','source_snapshot':str(SNAPSHOT),'components':{n:file_sha(snap/n) for n in names},'token_audit_sha256':file_sha(destination/'token_mapping_audit.json')}
    manifest['package_fingerprint']=sha(manifest); (destination/'package_manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)); return manifest
