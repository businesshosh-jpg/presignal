import unittest
from automation import bind_presignal_v21_step8_r3_runtime_v1 as b
class BindingTests(unittest.TestCase):
 def test_manifest_and_gate(self):
  self.assertEqual(b.gate()['status'],'R3_RUNTIME_BINDING_VALIDATED')
 def test_anthropic_forms(self):
  self.assertEqual(b.attention_parser('Anthropic','```json\n{"x":1}\n```'),{'x':1})
  with self.assertRaises(ValueError):b.attention_parser('Anthropic','prose {"x":1}')
 def test_prompt_rules_and_missingness_scope(self):
  row={'information_arm':'PACK_A','episode_id':'E','source_session_id':'S','country':'US','release_ts':'2024-01-01T01:00:00Z','forecast_cutoff_ts':'2024-01-01T00:00:00Z','episode_members':[],'structural_component_roles':[],'provider_attention_map':[],'information_requests':[],'shared_market_state_pack':{},'pack_fingerprint':'x'}
  self.assertIn('expected_pips_min',b.forecast_prompt(row,'Gemini'))
  self.assertIn('reversal',b.forecast_prompt(row,'OpenAI'))
if __name__=='__main__':unittest.main()
