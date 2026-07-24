import json,tempfile,unittest
from pathlib import Path
from automation import run_presignal_v21_new_r6_episode_candidate_package_v1 as runner
class CandidatePackageTests(unittest.TestCase):
 def test_blocker_is_fail_closed_and_deterministic(self):
  with tempfile.TemporaryDirectory() as d:
   o=Path(d);runner.run(o,'2026-07-24T00:00:00Z');final=json.loads((o/'final_new_r6_episode_refresh_decision.json').read_text());package=json.loads((o/'new_r6_episode_candidate_package.json').read_text());audit=json.loads((o/'external_access_audit.json').read_text())
  self.assertEqual(final['decision'],'NEW_R6_EPISODE_REFRESH_BLOCKED');self.assertFalse(package['old_pmi_attention_reused']);self.assertTrue(all(v==0 for v in audit.values()))
if __name__=='__main__':unittest.main()
