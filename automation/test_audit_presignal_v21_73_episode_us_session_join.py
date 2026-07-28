from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from automation import audit_presignal_v21_73_episode_us_session_join as audit


class AuditBlocked73UsSessionJoinTest(unittest.TestCase):
    def test_blocked_population_is_exactly_73_unique_episodes(self) -> None:
        rows = audit.load_blocked_population()
        self.assertEqual(len(rows), 73)
        self.assertEqual(len({row["episode_id"] for row in rows}), 73)

    def test_utc_conversion_uses_america_new_york_timezone(self) -> None:
        converted = audit.derive_us_session_date("2024-05-09T00:00:00Z")
        self.assertEqual(converted["derived_us_session_date"], "2024-05-08")
        self.assertEqual(converted["timezone_name"], "America/New_York")
        self.assertEqual(converted["utc_offset_applied"], "-04:00")
        self.assertTrue(converted["release_ts_us_eastern"].endswith("-04:00"))

    def test_session_id_pattern_is_date_based_not_fixed_offset_guess(self) -> None:
        self.assertEqual(
            audit.expected_session_id_for_date("2024-05-15"),
            "US|2024-05-15|CUSTOM_CONFIG_WINDOW",
        )

    def test_join_requires_exactly_one_preserved_session(self) -> None:
        universe = audit.build_session_universe()
        counts = [len(value) for value in universe["session_ids_by_date"].values()]
        self.assertTrue(all(count == 1 for count in counts))
        self.assertIn("2024-05-15", universe["session_ids_by_date"])

    def test_event_name_matching_is_not_part_of_membership_evidence(self) -> None:
        evidence = audit.build_member_evidence()
        for session_id, event_ids in evidence["member_ids_by_session"].items():
            self.assertTrue(all(isinstance(event_id, str) and "-" in event_id for event_id in event_ids), session_id)

    def test_full_audit_classifies_all_73_and_preserves_population(self) -> None:
        result = audit.audit_blocked_population()
        rows = result["classification_rows"]
        self.assertEqual(len(rows), 73)
        self.assertEqual(len(result["timezone_rows"]), 73)
        self.assertEqual(len(result["join_rows"]), 73)
        self.assertEqual(len(result["membership_rows"]), 73)
        self.assertEqual(len(result["downstream_rows"]), 73)
        self.assertTrue(all(row["recovery_classification"] in audit.CLASSIFICATIONS for row in rows))

    def test_promotion_candidates_are_subset_of_blocked_population(self) -> None:
        result = audit.audit_blocked_population()
        blocked_ids = {row["episode_id"] for row in result["blocked_rows"]}
        promoted_ids = {row["episode_id"] for row in result["promotion_rows"]}
        remaining_ids = {row["episode_id"] for row in result["remaining_rows"]}
        self.assertTrue(promoted_ids.issubset(blocked_ids))
        self.assertTrue(remaining_ids.issubset(blocked_ids))
        self.assertEqual(promoted_ids | remaining_ids, blocked_ids)
        self.assertEqual(promoted_ids & remaining_ids, set())

    def test_no_fixed_offset_or_web_or_provider_calls_in_script(self) -> None:
        text = Path(audit.__file__).read_text()
        self.assertIn("ZoneInfo(TIMEZONE_NAME)", text)
        self.assertNotIn("UTC-4", text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)

    def test_deterministic_scientific_fingerprint_across_reruns(self) -> None:
        first = audit.audit_blocked_population()
        second = audit.audit_blocked_population()
        self.assertEqual(first["scientific_fingerprint"], second["scientific_fingerprint"])
        self.assertEqual(first["classification_rows"], second["classification_rows"])

    def test_cli_reruns_produce_identical_scientific_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            cmd = ["python3", str(Path(audit.__file__)), "--output-root", str(root / "first")]
            subprocess.run(cmd, cwd=audit.ROOT, check=True, capture_output=True, text=True)
            subprocess.run(["python3", str(Path(audit.__file__)), "--output-root", str(root / "second")], cwd=audit.ROOT, check=True, capture_output=True, text=True)
            first_dirs = sorted(path for path in (root / "first").iterdir() if path.is_dir())
            second_dirs = sorted(path for path in (root / "second").iterdir() if path.is_dir())
            self.assertEqual(len(first_dirs), 1)
            self.assertEqual(len(second_dirs), 1)
            first_summary = json.loads((first_dirs[0] / "audit_summary.json").read_text())
            second_summary = json.loads((second_dirs[0] / "audit_summary.json").read_text())
            first_class = (first_dirs[0] / "recovery_classification.jsonl").read_text()
            second_class = (second_dirs[0] / "recovery_classification.jsonl").read_text()
            self.assertEqual(first_summary["scientific_fingerprint"], second_summary["scientific_fingerprint"])
            self.assertEqual(first_class, second_class)


if __name__ == "__main__":
    unittest.main()
