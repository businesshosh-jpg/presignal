from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from automation.build_simplified_replay_package_v1 import freeze
from automation.run_simplified_replay_canary_v1 import execute
class T(unittest.TestCase):
 def test_freeze_and_canary(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'p'; m=freeze(p); self.assertEqual(m['counts']['identities'],1434); pop=[json.loads(x) for x in (p/'snapshot/authoritative_forecast_population.jsonl').read_text().splitlines()]; e=pop[0]; ms=[json.loads(x) for x in (p/'snapshot/authoritative_session_members.jsonl').read_text().splitlines() if json.loads(x)['session_id']==e['session_id']]; audit=json.loads((p/'token_mapping_audit.json').read_text())[e['session_id']]; raw={'primary_driver_token':audit[0]['token'],'secondary_driver_token':None,'final_usdjpy_direction':'UP','reaction_strength':'MODERATE','confidence':.5,'primary_thesis':'x','secondary_thesis':'','reasoning_steps':['a','b']}; r={'actual_provider':e['provider'],'actual_model':e['model'],'raw_output':json.dumps(raw)}; self.assertTrue(execute(p,e,ms,r));
   with self.assertRaises(ValueError): execute(p,e,ms,r)
   raw.pop('final_usdjpy_direction'); r['raw_output']=json.dumps(raw)
   with self.assertRaises(Exception): execute(p,pop[1],ms,r)
if __name__=='__main__': unittest.main()
