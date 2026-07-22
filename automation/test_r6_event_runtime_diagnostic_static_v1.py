import unittest
from pathlib import Path
class DiagnosticStaticTests(unittest.TestCase):
 def test_diagnostic_is_single_and_bounded(self):
  s=Path('apps_script/automation_api.js').read_text(); self.assertEqual(s.count('function apiDiagnoseProspectiveEventIdentityRuntime('),1)
  start=s.index('function apiDiagnoseProspectiveEventIdentityRuntime('); end=s.index('\nfunction apiRunPipelineWindow_', start); body=s[start:end]
  for forbidden in ('apiUpsertEventWindow(', 'runPredictions', 'apiRunPrediction', 'runFetchActuals', 'apiRunPipelineWindow'):
   self.assertNotIn(forbidden,body)
  for required in ('applyBatchingForKeys_(sh, undefined)','normalized_header_map','missing_event_id_before','postpass_return_type'):
   self.assertIn(required,body)
if __name__=='__main__': unittest.main()
