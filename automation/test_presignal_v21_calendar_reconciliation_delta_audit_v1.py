import unittest

from automation import run_presignal_v21_calendar_reconciliation_delta_audit_v1 as audit


class CalendarReconciliationDeltaAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = audit.audit()

    def test_preserved_instant_filter_excluded_exactly_seven_july_31_events(self):
        delta = self.values["calendar_event_identity_delta.json"]
        self.assertEqual(delta["preserved_91_versus_86_difference"], 5)
        self.assertEqual(delta["boundary_excluded_count_under_prior_instant_parser"], 7)

    def test_calendar_date_semantics_produces_unique_93_row_readback(self):
        readback = self.values["calendar_preserved_readback_event_set.json"]
        self.assertEqual(readback["calendar_date_inclusive_window_count"], 93)
        self.assertEqual(readback["duplicate_identities"], 0)

    def test_absent_adapter_rows_fail_closed_without_a_second_readback(self):
        classification = self.values["calendar_readback_defect_classification.json"]
        self.assertEqual(classification["overall_classification"], "RECONCILIATION_UNRESOLVED")
        self.assertFalse(classification["corrected_google_readback_authorized"])
        self.assertEqual(self.values["external_access_audit.json"]["new_google_event_readbacks"], 0)

    def test_no_candidate_package_is_created_from_unreconciled_events(self):
        self.assertEqual(self.values["new_r6_episode_candidate_package.json"]["status"], "NOT_CREATED_RECONCILIATION_UNRESOLVED")
