#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import google_clients
from automation import presignal_shared_runtime_reliability_v1 as runtime


class RuntimeReliabilityTests(unittest.TestCase):
    def test_classifies_credential_and_connection_failures(self) -> None:
        self.assertEqual(google_clients.classify_google_exception(google_clients.GoogleCredentialError("GOOGLE_OAUTH_TOKEN_MISSING", "missing"))["category"], "GOOGLE_OAUTH_TOKEN_MISSING")
        self.assertEqual(google_clients.classify_google_exception(OSError("nodename nor servname provided"))["category"], "GOOGLE_API_CONNECTION_ERROR")

    def test_atomic_token_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "token.json"
            google_clients.atomic_write_json(token, "{\"token\":\"redacted\"}")
            self.assertEqual(token.read_text(), "{\"token\":\"redacted\"}")
            self.assertFalse(token.with_suffix(".json.tmp").exists())

    def test_preflight_invalid_grant_is_explicit(self) -> None:
        def invalid(_interactive):
            raise google_clients.GoogleCredentialError("GOOGLE_OAUTH_INVALID_GRANT", "revoked")
        result = runtime.classify_credential_preflight(invalid)
        self.assertEqual(result["status"], "CREDENTIAL_INVALID")

    def test_prospective_guard_fails_closed(self) -> None:
        self.assertTrue(runtime.prospective_runtime_guard("READY", "READY", True, True)["admission_allowed"])
        self.assertFalse(runtime.prospective_runtime_guard("CREDENTIAL_INVALID", "READY", True, True)["admission_allowed"])
        self.assertFalse(runtime.prospective_runtime_guard("READY", "READY", True, False)["admission_allowed"])


if __name__ == "__main__":
    unittest.main()
