from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import presignal_v21_prospective_flat_contract_v1 as prospective
from automation import run_presignal_v21_prospective_shadow_v1 as shadow


class ProspectiveShadowPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authorization = shadow.verify_authorization(prospective.PROSPECTIVE_CONTRACT_VERSION)
        self.study = shadow.study_manifest(self.authorization)

    def test_step9_policy_and_prospective_contract_are_required(self) -> None:
        self.assertEqual(self.authorization["step9_decision"], "V2_1_STEP9_PROMOTION_DEFERRED_PROSPECTIVE_SHADOW_AUTHORIZED")
        self.assertEqual(self.study["direct_session_forecast_status"], "RETAIN_ACTIVE_REFERENCE_BASELINE")
        with self.assertRaisesRegex(shadow.ProspectiveShadowError, "PROSPECTIVE_CONTRACT_REQUIRED"):
            shadow.verify_authorization("presignal_event_path_contract_v1")

    def test_stages_are_episode_bounded_not_provider_row_bounded(self) -> None:
        self.assertEqual(shadow.STAGES["P12"], {"episodes": 12, "pairs": 36, "arms": 72})
        self.assertEqual(shadow.STAGES["P40"]["episodes"], 40)
        self.assertEqual(shadow.STAGES["P60"]["arms"], 360)
        self.assertEqual(shadow.STAGES["P80"]["pairs"], 240)
        self.assertIn("width > 0.20", self.study["p60_to_p80_extension_rule"])

    def test_forecast_selection_and_non_forecast_records_are_distinct(self) -> None:
        a, e = shadow.fixture_pair(); self.assertEqual(shadow.validate_pair(a, e, study=self.study)["status"], "FORECAST_READY")
        for selection in ("WATCH", "IGNORE", "NO_SIGNAL"):
            a, e = shadow.fixture_pair(selection=selection)
            self.assertEqual(shadow.validate_pair(a, e, study=self.study)["status"], "NOT_FORECAST_SELECTED")

    def test_timing_attention_pack_leakage_and_duplicate_controls_fail_closed(self) -> None:
        a, e = shadow.fixture_pair(); a["provider_attention_map"] = []
        with self.assertRaisesRegex(shadow.ProspectiveShadowError, "ATTENTION_INCOMPLETE"): shadow.validate_pair(a, e, study=self.study)
        a, e = shadow.fixture_pair(); a["information_requests"] = []
        with self.assertRaisesRegex(shadow.ProspectiveShadowError, "PACK_A_EMPTY"): shadow.validate_pair(a, e, study=self.study)
        a, e = shadow.fixture_pair(); a["forecast_cutoff_ts"] = e["forecast_cutoff_ts"] = a["release_ts"]
        with self.assertRaisesRegex(shadow.ProspectiveShadowError, "CUTOFF_NOT_BEFORE_RELEASE"): shadow.validate_pair(a, e, study=self.study)
        a, e = shadow.fixture_pair(); a["released_value"] = 1
        with self.assertRaisesRegex(Exception, "FORBIDDEN_LEAKAGE_FIELD"): shadow.validate_pair(a, e, study=self.study)
        a, e = shadow.fixture_pair()
        with self.assertRaisesRegex(shadow.ProspectiveShadowError, "DUPLICATE_PROSPECTIVE_EPISODE"): shadow.validate_pair(a, e, study=self.study, seen_episodes={a["episode_id"]})

    def test_prompt_symmetry_restart_and_outcome_isolation_are_frozen(self) -> None:
        a, e = shadow.fixture_pair()
        ready = shadow.validate_pair(a, e, study=self.study, resume_state={"arms": {"PACK_A": "FORECAST_ACCEPTED"}})
        self.assertTrue(ready["prompt_diff"]["passed"])
        self.assertEqual(ready["resume_action"], "SKIP_ACCEPTED_PACK_A")
        self.assertIn("OUTCOME_CONTENTS_UNAVAILABLE", ready["outcome_isolation"])
        self.assertEqual(ready["provider_calls"], 0)

    def test_dry_run_and_execute_hard_stop(self) -> None:
        results = shadow.dry_run(self.study)
        self.assertEqual(len(results), 20)
        self.assertTrue(all(result["passed"] for result in results))
        with self.assertRaisesRegex(shadow.ProspectiveShadowError, "EXECUTION_DISABLED"):
            shadow.run(mode="execute", contract_version=prospective.PROSPECTIVE_CONTRACT_VERSION)

    def test_preparation_is_deterministic_and_does_not_call_external_systems(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first, left = shadow.run(mode="prepare", contract_version=prospective.PROSPECTIVE_CONTRACT_VERSION, output_dir=Path(directory) / "left")
            second, right = shadow.run(mode="dry-run", contract_version=prospective.PROSPECTIVE_CONTRACT_VERSION, output_dir=Path(directory) / "right")
            self.assertEqual(left["preparation_fingerprint"], right["preparation_fingerprint"])
            self.assertEqual(left["external_calls"]["provider"], 0)
            self.assertTrue((first / "prospective_study_manifest.json").exists())
            self.assertTrue((second / "dry_run_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
