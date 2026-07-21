import json
import unittest
from pathlib import Path

from automation import diagnose_presignal_v21_step8_r3_v1 as d


class Step8R3DiagnosticsTests(unittest.TestCase):
    def test_frozen_population_and_cluster_reconstruction(self):
        records = d.rows(d.CONT / 'continued_forecast_results.jsonl')
        self.assertEqual(len(records), 777)
        self.assertEqual(len({x['pair_id'] for x in records}), 777)
        complete = [x for x in records if x['completion'] == 'COMPLETE_PAIRED']
        self.assertEqual(len(complete), 52)
        self.assertEqual(len({x['episode_id'] for x in complete}), 40)
        committed = json.loads((d.CONT / 'final_paired_analysis.json').read_text())
        self.assertEqual(committed['episode_cluster_permutation']['two_sided_p_value'], 9.99990000099999e-06)


if __name__ == '__main__':
    unittest.main()
