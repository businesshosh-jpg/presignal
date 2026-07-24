"""Offline checks for the bounded OAuth rebind and V2 authorization."""
from __future__ import annotations

import unittest

from automation import run_presignal_v21_new_r6_information_request_oauth_redispatch_v1 as redispatch


class InformationRequestOauthRedispatchTest(unittest.TestCase):
    def test_existing_token_binding_resolves_accepted_source(self) -> None:
        trace, classification = redispatch.oauth_trace()
        self.assertEqual(classification, "TOKEN_PATH_RESOLVED_IN_WRONG_WORKTREE")
        self.assertTrue(trace["worktree_token_exists"])
        self.assertTrue(trace["worktree_token_is_symlink"])
        self.assertTrue(trace["source_matches_resolved_path"])

    def test_v2_authorization_binds_consumed_v1_failure(self) -> None:
        _, failure_checksum = redispatch.v1_failure_evidence()
        value = redispatch.v2_authorization(probe_checksum="sha256:probe", v1_failure_checksum=failure_checksum)
        self.assertEqual(value["consumed_v1_request_authorization_fingerprint"], redispatch.V1_AUTH)
        self.assertEqual(value["retry_count"], 0)
        self.assertEqual(value["authorization_fingerprint"], redispatch.sha({key: item for key, item in value.items() if key != "authorization_fingerprint"}))

    def test_probe_failure_blocks_v2_validation(self) -> None:
        _, failure_checksum = redispatch.v1_failure_evidence()
        value = redispatch.v2_authorization(probe_checksum="sha256:probe", v1_failure_checksum=failure_checksum)
        result = redispatch.v2_validation(value, {"status": "FAILED"})
        self.assertFalse(result["v2_authorization_valid"])
        self.assertFalse(result["checks"]["probe_passed"])


if __name__ == "__main__":
    unittest.main()
