#!/usr/bin/env python3
"""Local-only tests for the one-read schedule refresh reconciliation."""
from __future__ import annotations

import unittest

from automation import reconcile_presignal_v21_round_2_schedule_refresh as reconciliation


class ReconciliationTests(unittest.TestCase):
    def test_authorization_has_no_refresh_or_write_authority(self):
        prior = {"authorization_fingerprint": reconciliation.PRIOR_FP, "remote_state": "UNKNOWN_POST_DISPATCH"}
        auth = reconciliation.authorization(prior)
        self.assertEqual(auth["ceilings"]["fmp_requests"], 0)
        self.assertEqual(auth["ceilings"]["apps_script_refresh_invocations"], 0)
        self.assertEqual(auth["ceilings"]["event_sheet_writes"], 0)
        self.assertEqual(auth["ceilings"]["event_sheet_diagnostic_reads"], 1)

    def test_missing_invocation_lineage_requires_unresolved_classification(self):
        auth = reconciliation.authorization({"authorization_fingerprint": reconciliation.PRIOR_FP, "remote_state": "UNKNOWN_POST_DISPATCH"})
        self.assertIn("Existing matching rows alone are insufficient", auth["classification_rule"])


if __name__ == "__main__":
    unittest.main()
