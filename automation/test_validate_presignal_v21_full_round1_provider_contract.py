import tempfile
import unittest
from pathlib import Path

from automation import validate_presignal_v21_full_round1_provider_contract as validation


class ProviderContractValidationTests(unittest.TestCase):
    def test_governing_matrix_contains_exactly_96_provider_contract_blocked_arms(self) -> None:
        rows = validation.load_matrix_rows()
        blocked = validation.blocked_arms(rows)
        self.assertEqual(len(blocked), 96)
        self.assertEqual({row["provider"] for row in blocked}, {"Anthropic"})
        self.assertEqual({row["model"] for row in blocked}, {"claude-haiku-4-5"})
        self.assertEqual({row["pack_arm"] for row in blocked}, {"PACK_A", "PACK_E"})

    def test_validation_cases_reproduce_wrapper_root_cause_and_repair(self) -> None:
        reproduction_rows, validation_rows = validation.build_validation_case_ledger()
        self.assertEqual({row["provider"] for row in reproduction_rows}, {"Anthropic", "Gemini", "OpenAI"})
        self.assertTrue(
            all(row["exact_validation_error"] == "RAW_OUTPUT_NOT_FOUND_AT_TRANSPORT_TOP_LEVEL" for row in reproduction_rows)
        )
        self.assertTrue(all(row["repaired_parse_status"] == "PARSED" for row in reproduction_rows))
        self.assertTrue(all(row["repaired_validation_status"] == "VALID" for row in reproduction_rows))
        self.assertTrue(all(row["validation_status"] == "VALID" for row in validation_rows))

    def test_arm_recommendations_make_all_96_ready_without_touching_other_statuses(self) -> None:
        rows = validation.load_matrix_rows()
        blocked = validation.blocked_arms(rows)
        recommendations = validation.build_arm_recommendations(blocked)
        self.assertEqual(len(recommendations), 96)
        self.assertEqual({row["recommended_status"] for row in recommendations}, {"READY_FOR_EXECUTION"})
        self.assertEqual({row["recommendation_reason"] for row in recommendations}, {"PROVIDER_CONTRACT_VALIDATED"})

    def test_build_validation_is_deterministic_under_fixed_timestamp(self) -> None:
        fixed_timestamp = "2026-07-28T18:00:00.000000Z"
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            first = validation.build_validation(output_root=output_root, fixed_timestamp=fixed_timestamp)
            second = validation.build_validation(output_root=output_root, fixed_timestamp=fixed_timestamp)
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual(first["preview"], second["preview"])
        self.assertEqual(first["recommendations"], second["recommendations"])


if __name__ == "__main__":
    unittest.main()
