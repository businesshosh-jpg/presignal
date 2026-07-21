import shutil,unittest
from automation import run_presignal_v21_step8_r3_fresh_historical_verification_v1 as r
class LoopTests(unittest.TestCase):
 def setUp(self):self.loop=r.ExecutionLoop('TEST-R3-LOOP');shutil.rmtree(self.loop.run,ignore_errors=True)
 def tearDown(self):shutil.rmtree(self.loop.run,ignore_errors=True)
 def test_state_and_duplicate_guard(self):
  i={'episode_id':'E','provider':'Gemini','stage':'ATTENTION','attempt_number':1}
  self.loop.transition(i,'ATTENTION_REQUEST_FROZEN');self.assertEqual(self.loop.status()['current'][__import__('json').dumps(i,sort_keys=True)],'ATTENTION_REQUEST_FROZEN')
  self.loop.transition(i,'COMPLETE')
  with self.assertRaisesRegex(RuntimeError,'DUPLICATE'):self.loop.transition(i,'PACK_A_SENT')
 def test_mock_dispatch_and_resume(self):
  state=self.loop.dispatch_mock_episode()
  self.assertEqual(state['processed_episodes'],1);self.assertEqual(state['unique_complete_episodes'],1)
  self.assertEqual(self.loop.status()['processed_episodes'],1)
