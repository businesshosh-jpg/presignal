"""Manifest-bound R3 execution loop; live dispatch is separately authorized."""
from __future__ import annotations
import argparse,json,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
OUT=ROOT/'outputs/presignal_v21_step8_r3_fresh_historical_verification'
STAGES=['PENDING','ATTENTION_REQUEST_FROZEN','ATTENTION_SENT','ATTENTION_RESPONSE_RECEIVED','ATTENTION_ACCEPTED','ATTENTION_REJECTED','NOT_FORECAST_SELECTED','REQUEST_FROZEN','REQUEST_SENT','REQUEST_ACCEPTED','REQUEST_REJECTED','PACKS_FROZEN','FORECAST_PROMPTS_FROZEN','PACK_A_SENT','PACK_A_ACCEPTED','PACK_A_REJECTED','PACK_E_SENT','PACK_E_ACCEPTED','PACK_E_REJECTED','OUTCOME_ATTACHED','EVALUATED','COMPLETE','TERMINAL_INCOMPLETE']
TERMINAL={'COMPLETE','TERMINAL_INCOMPLETE','NOT_FORECAST_SELECTED'}
def atomic(path:Path,value):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n');os.replace(tmp,path)
def append(path:Path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a') as f:f.write(json.dumps(value,sort_keys=True)+'\n')
class ExecutionLoop:
 def __init__(self,run_id:str):
  self.gate=binding.gate();self.run=OUT/run_id;self.state_path=self.run/'execution_state.json'
 def initialize(self):
  if self.state_path.exists():return json.loads(self.state_path.read_text())
  state={'run_id':self.run.name,'gate':self.gate,'processed_episodes':0,'unique_complete_episodes':0,'current':{},'terminal_identities':[],'last_durable_checkpoint':'INITIALIZED'};atomic(self.state_path,state);atomic(self.run/'run_manifest.json',self.gate);return state
 def transition(self,identity:dict,stage:str):
  if stage not in STAGES:raise RuntimeError('INVALID_STATE')
  state=self.initialize(); key=json.dumps(identity,sort_keys=True)
  if key in state['terminal_identities']:raise RuntimeError('V2_1_STEP8_R3_R2_DUPLICATE_ACCEPTED_CALL_BLOCKED')
  append(self.run/'error_ledger.jsonl' if stage.endswith('REJECTED') else self.run/'forecast_call_ledger.jsonl',{'identity':identity,'stage':stage})
  state['current'][key]=stage
  if stage in TERMINAL:state['terminal_identities'].append(key)
  state['last_durable_checkpoint']=stage;atomic(self.state_path,state);return state
 def status(self):return self.initialize()
def main():
 p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--status',action='store_true');p.add_argument('--run-id',default='STEP8-R3-VERIFY-8ca9100');a=p.parse_args()
 loop=ExecutionLoop(a.run_id)
 if a.status:print(json.dumps(loop.status(),sort_keys=True));return
 if a.execute or a.resume:
  # The loop is deliberately initialized only; a future execution task supplies the live dispatcher.
  print(json.dumps({'status':'EXECUTION_LOOP_INITIALIZED','run':a.run_id,**loop.initialize()},sort_keys=True));return
 if not a.preflight:raise SystemExit('PRELIGHT_REQUIRED')
 print(json.dumps(binding.gate(),sort_keys=True))
if __name__=='__main__':main()
