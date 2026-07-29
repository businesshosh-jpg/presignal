from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import recover_presignal_v21_forecast_batch_002_governance as recovery
from automation.test_execute_presignal_v21_forecast_batch_001 import valid_raw_output


class GovernanceRecoveryBatch002Test(unittest.TestCase):
    def test_attempt_categories_cover_three_two_seven_split(self) -> None:
        bundle = recovery.batch_exec.verified_batch_bundle(
            user_batch_label=recovery.USER_BATCH_LABEL,
            frozen_batch_id=recovery.FROZEN_BATCH_ID,
        )
        categories = recovery.category_map(bundle)
        counts = {}
        for row in categories.values():
            counts[row["attempt_category"]] = counts.get(row["attempt_category"], 0) + 1
        self.assertEqual(counts["GOVERNANCE_AUTHORIZED_UNKNOWN_STATE_RECOVERY"], 3)
        self.assertEqual(counts["CONFIRMED_NOT_SENT_RETRY"], 2)
        self.assertEqual(counts["FIRST_ATTEMPT"], 7)
        self.assertEqual(len(categories), 12)

    def test_recovery_authoritative_selection_reasons_follow_attempt_category(self) -> None:
        call = {"forecast_call_id": "FCL_test"}
        unknown = recovery.authoritative_selection_row(
            call=call,
            attempt_meta={"attempt_category": "GOVERNANCE_AUTHORIZED_UNKNOWN_STATE_RECOVERY", "original_attempt_reference": {"x": 1}},
            terminal_state="SUCCEEDED_VALID",
            run_dir=Path("/tmp/RUN"),
        )
        retry = recovery.authoritative_selection_row(
            call=call,
            attempt_meta={"attempt_category": "CONFIRMED_NOT_SENT_RETRY", "original_attempt_reference": {"x": 1}},
            terminal_state="SUCCEEDED_VALID",
            run_dir=Path("/tmp/RUN"),
        )
        first = recovery.authoritative_selection_row(
            call=call,
            attempt_meta={"attempt_category": "FIRST_ATTEMPT", "original_attempt_reference": None},
            terminal_state="SUCCEEDED_VALID",
            run_dir=Path("/tmp/RUN"),
        )
        self.assertIn("EXPLICITLY_AUTHORIZED", unknown["authority_reason"])
        self.assertIn("CONFIRMED_NOT_SENT", retry["authority_reason"])
        self.assertEqual(first["authority_reason"], "FIRST_SUCCESSFUL_FROZEN_ATTEMPT")

    def test_existing_valid_result_blocks_dispatch(self) -> None:
        def fake_preflight() -> dict[str, object]:
            return {
                "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
                "token_path_external": True,
                "authentication_method": "test",
                "scope_names": [],
                "scope_verification_result": "PASSED",
                "read_only_preflight_result": "PASSED",
                "resource_identity_result": "PASSED",
                "google_writes": 0,
            }

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            fake_valid_dir = out / "PPHB-R1-FORECAST-EXECUTION-BATCH-999"
            fake_valid_dir.mkdir(parents=True)
            target_call = recovery.batch_exec.verified_batch_bundle(
                user_batch_label=recovery.USER_BATCH_LABEL,
                frozen_batch_id=recovery.FROZEN_BATCH_ID,
            )["bundles"][0]["call"]["forecast_call_id"]
            (fake_valid_dir / "normalized_forecast_results.jsonl").write_text(
                recovery.canonical_json({"forecast_call_id": target_call, "terminal_state": "SUCCEEDED_VALID", "prediction": {"run_id": "PREEXISTING"}})
                + "\n"
            )
            with mock.patch.object(recovery, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), mock.patch.object(
                recovery, "git_head", return_value=recovery.EXPECTED_START_HEAD
            ), mock.patch.object(recovery, "is_descendant_of", return_value=True):
                with self.assertRaises(recovery.GovernanceRecoveryError):
                    recovery.execute_recovery(
                        output_root=out,
                        fixed_timestamp="2026-07-29T15:50:00Z",
                        enforce_head=False,
                        auth_preflight=fake_preflight,
                        dispatch=lambda *_args, **_kwargs: {"ok": False},
                    )

    def test_execute_recovery_uses_fresh_dispatch_and_preserves_one_attempt_per_call(self) -> None:
        dispatch_calls: list[str] = []
        service_instances: list[object] = []

        def fake_preflight() -> dict[str, object]:
            return {
                "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
                "token_path_external": True,
                "authentication_method": "test",
                "scope_names": [],
                "scope_verification_result": "PASSED",
                "read_only_preflight_result": "PASSED",
                "resource_identity_result": "PASSED",
                "google_writes": 0,
            }

        def fake_factory() -> object:
            service = object()
            service_instances.append(service)
            return service

        def fake_dispatch(service: object, _script_id: str, payload: dict[str, object]) -> dict[str, object]:
            self.assertIs(service, service_instances[len(dispatch_calls)])
            dispatch_calls.append(str(payload["forecast_identity"]))
            return {
                "ok": True,
                "request": {"function": "apiCallAuthoritativeProviderJsonObject"},
                "classification": {"category": "READY"},
                "result": {
                    "status": "ok",
                    "actual_provider": payload["provider"],
                    "actual_model": payload["model"],
                    "raw_output": valid_raw_output(),
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "latency_ms": 30,
                    "completed_timestamp": "2026-07-29T15:55:00Z",
                },
            }

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(recovery, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), mock.patch.object(
                recovery, "git_head", return_value=recovery.EXPECTED_START_HEAD
            ), mock.patch.object(recovery, "is_descendant_of", return_value=True), mock.patch.object(
                recovery.batch_exec,
                "build_default_script_service_factory",
                return_value=(fake_factory, recovery.batch_exec.EXPECTED_SCRIPT_ID),
            ):
                result = recovery.execute_recovery(
                    output_root=Path(tmp),
                    fixed_timestamp="2026-07-29T15:51:00Z",
                    enforce_head=False,
                    auth_preflight=fake_preflight,
                    dispatch=fake_dispatch,
                )
        self.assertEqual(len(dispatch_calls), 12)
        self.assertEqual(len(service_instances), 12)
        self.assertEqual(result["reconciliation"]["attempted_provider_calls"], 12)
        self.assertEqual(result["reconciliation"]["successful_valid_calls"], 12)
        self.assertEqual(result["decision"]["recovery_status"], "BATCH_002_GOVERNANCE_RECOVERY_COMPLETE")
        self.assertEqual(len(result["duplicate_lineage_rows"]), 12)

    def test_no_automatic_retry_and_no_batch_003_execution(self) -> None:
        self.assertNotIn("FORECAST_BATCH_003", recovery.__doc__ or "")
        self.assertEqual(recovery.UNKNOWN_STATE_CALL_IDS, tuple(recovery.final_verify.UNKNOWN_CALL_IDS))


if __name__ == "__main__":
    unittest.main()
