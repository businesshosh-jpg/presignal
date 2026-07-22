from __future__ import annotations

import unittest

from automation import presignal_shared_runtime_reliability_v1 as runtime
from automation import verify_presignal_v21_shared_runtime_reliability_r1 as verification


class SharedRuntimeR1VerificationTests(unittest.TestCase):
    def test_health_payload_rejects_missing_required_fields(self) -> None:
        row = {"execution": {"ok": True, "result": {"status": "READY"}}}
        result = verification.health_payload([row])
        self.assertEqual(result["status"], "INVALID_HEALTH_RESPONSE")

    def test_health_payload_accepts_complete_health_response(self) -> None:
        row = {"response_fingerprint": "sha256:test", "execution": {"ok": True, "result": {"status": "READY", "timestamp": "2026-07-22T00:00:00Z", "script_version": "HEAD", "dev_mode": True}}}
        result = verification.health_payload([row])
        self.assertEqual(result["status"], "READY")

    def test_guard_fails_closed_for_invalid_credential(self) -> None:
        self.assertFalse(runtime.prospective_runtime_guard("CREDENTIAL_INVALID", "READY", True, True)["admission_allowed"])


if __name__ == "__main__":
    unittest.main()
