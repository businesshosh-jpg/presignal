from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from automation import audit_presignal_v21_remaining_65_event_date_rescue as audit


class Remaining65EventDateRescueTest(unittest.TestCase):
    def test_rescue_population_stays_73(self) -> None:
        rows = audit.load_blocked_population()
        self.assertEqual(len(rows), 73)
        self.assertEqual(len({row["episode_id"] for row in rows}), 73)

    def test_prior_partial_population_is_64(self) -> None:
        rows = audit.load_blocked_population()
        self.assertEqual(sum(row["prior_classification"] == "PARTIAL_LINEAGE_ONLY" for row in rows), 64)

    def test_event_source_uses_exact_row_locator_mapping(self) -> None:
        event_source = audit.build_event_source()
        self.assertIn("ER_", next(iter(event_source["normalized_by_locator"])))
        sample_episode = event_source["episode_members_by_episode"]["EP_BATCH_801c20917321a78fded4"]
        locator = sample_episode[0]["event_row_locator"]
        self.assertEqual(event_source["normalized_by_locator"][locator]["event_id"], sample_episode[0]["event_id"])

    def test_event_names_alone_are_not_mapping_contract(self) -> None:
        text = Path(audit.__file__).read_text()
        self.assertIn("EXACT_EVENT_ROW_LOCATOR_WITH_EVENT_ID_CROSSCHECK", text)
        self.assertNotIn("fuzzy", text.lower())

    def test_timezone_conversion_uses_america_new_york(self) -> None:
        utc_ts, local_ts, session_date = audit.to_us_eastern_date("2024-05-09T00:00:00Z")
        self.assertEqual(utc_ts, "2024-05-09T00:00:00Z")
        self.assertEqual(session_date, "2024-05-08")
        self.assertTrue(local_ts.endswith("-04:00"))

    def test_no_fixed_offset_is_used(self) -> None:
        text = Path(audit.__file__).read_text()
        self.assertIn("ZoneInfo(TIMEZONE_NAME)", text)
        self.assertNotIn("UTC-4", text)
        self.assertNotIn("UTC-5", text)

    def test_no_invented_session_for_no_route_case(self) -> None:
        result = audit.audit_population()
        row = next(item for item in result["classification_rows"] if item["episode_id"] == "EP_EVENT_67dc98eaf62822136db2")
        self.assertEqual(row["final_classification"], "NO_RECOVERY_ROUTE")
        self.assertEqual(row["selected_session_id"], "")

    def test_all_partial_cases_are_reaudited_and_batches_stay_on_one_us_date(self) -> None:
        result = audit.audit_population()
        partial_rows = [row for row in result["classification_rows"] if row["prior_classification"] == "PARTIAL_LINEAGE_ONLY"]
        self.assertEqual(len(partial_rows), 64)
        self.assertTrue(all(row["member_us_session_dates"] for row in partial_rows))
        self.assertTrue(all(len(row["member_us_session_dates"]) == 1 for row in partial_rows))

    def test_previous_eight_are_preserved(self) -> None:
        result = audit.audit_population()
        preserved = [row for row in result["classification_rows"] if row["prior_classification"] == "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR"]
        self.assertEqual(len(preserved), 8)
        self.assertTrue(all(row["final_classification"] == "RECOVERABLE_BY_DETERMINISTIC_LINK_REPAIR" for row in preserved))

    def test_remaining_partial_population_is_rescued(self) -> None:
        summary = audit.summarize(audit.audit_population())
        self.assertEqual(summary["RECOVERABLE_BY_DETERMINISTIC_EVENT_DATE_LINK"], 64)
        self.assertEqual(summary["PARTIAL_LINEAGE_ONLY"], 0)
        self.assertEqual(summary["NO_RECOVERY_ROUTE"], 1)
        self.assertEqual(summary["total_promotion_candidate_count"], 72)

    def test_downstream_route_is_evaluated_separately_from_event_membership(self) -> None:
        result = audit.audit_population()
        route_row = next(item for item in result["downstream_rows"] if item["episode_id"] == "EP_BATCH_801c20917321a78fded4")
        self.assertEqual(route_row["Attention_route"], "RECONSTRUCTABLE_UNDER_EXISTING_341_ROUTE")
        self.assertEqual(route_row["Information_Request_route"], "EXACT_REUSABLE")
        self.assertEqual(route_row["Pack_A_route"], "RECONSTRUCTABLE_UNDER_EXISTING_341_ROUTE")
        self.assertEqual(route_row["Pack_E_route"], "RECONSTRUCTABLE_UNDER_EXISTING_341_ROUTE")

    def test_deterministic_scientific_outputs(self) -> None:
        first = audit.audit_population()
        second = audit.audit_population()
        self.assertEqual(first["scientific_fingerprint"], second["scientific_fingerprint"])
        self.assertEqual(first["classification_rows"], second["classification_rows"])

    def test_cli_reruns_match_scientific_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            subprocess.run(
                ["python3", str(Path(audit.__file__)), "--output-root", str(root / "first")],
                cwd=audit.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["python3", str(Path(audit.__file__)), "--output-root", str(root / "second")],
                cwd=audit.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            first_dir = next((root / "first").iterdir())
            second_dir = next((root / "second").iterdir())
            first_summary = json.loads((first_dir / "audit_summary.json").read_text())
            second_summary = json.loads((second_dir / "audit_summary.json").read_text())
            self.assertEqual(first_summary["scientific_fingerprint"], second_summary["scientific_fingerprint"])
            self.assertEqual(
                (first_dir / "final_recovery_classification.jsonl").read_text(),
                (second_dir / "final_recovery_classification.jsonl").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
