from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import execute_presignal_v21_auth_recovery_and_attention_batches_015_016 as wrapper


class AuthRecoveryAttentionBatches015016Test(unittest.TestCase):
    def test_authentication_must_succeed_before_provider_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(wrapper, "verify_authentication", return_value={
                "authentication_decision": "GOOGLE_AUTHENTICATION_STILL_BLOCKED",
                "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
                "token_path_external": True,
                "scope_names": list(wrapper.google_clients.SCOPES),
                "scope_verification_result": "FAILED",
                "read_only_preflight_result": "FAILED",
                "resource_identity_result": "NOT_REACHED",
            }):
                result = wrapper.execute_move(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:00:00Z", enforce_head=False)
            self.assertIsNone(result["coordinator_result"])

    def test_credential_contents_never_enter_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            auth = {
                "authentication_decision": "GOOGLE_AUTHENTICATION_STILL_BLOCKED",
                "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
                "token_path_external": True,
                "scope_names": list(wrapper.google_clients.SCOPES),
                "scope_verification_result": "FAILED",
                "read_only_preflight_result": "FAILED",
                "resource_identity_result": "NOT_REACHED",
                "error": "x",
            }
            with patch.object(wrapper, "verify_authentication", return_value=auth):
                result = wrapper.execute_move(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:00:00Z", enforce_head=False)
            for path in result["run_dir"].iterdir():
                text = path.read_text()
                self.assertNotIn("refresh_token", text)
                self.assertNotIn("client_secret", text)
                self.assertNotIn("\"token\":", text)

    def test_token_path_remains_outside_repository(self) -> None:
        result = wrapper.verify_authentication()
        self.assertFalse(str(wrapper.TOKEN_PATH).startswith(str(wrapper.ROOT)))
        self.assertTrue(result["token_path_external"])

    def test_blocked_run_contained_zero_provider_calls(self) -> None:
        blocked = wrapper.coordinator.batch015.batch004.read_json(
            wrapper.OUTPUT_ROOT / "PPHB-R1-ATTENTION-EXECUTION-BATCH-015-20260729T090319Z-a624a4386240" / "batch_reconciliation.json"
        )
        self.assertEqual(blocked["attempted_calls"], 0)


if __name__ == "__main__":
    unittest.main()
