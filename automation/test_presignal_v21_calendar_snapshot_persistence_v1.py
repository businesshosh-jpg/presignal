"""Focused offline guards for snapshot/persistent Event-store reconciliation."""
import unittest

from automation import run_presignal_v21_calendar_snapshot_persistence_v1 as subject


class CalendarSnapshotPersistenceTests(unittest.TestCase):
    def test_preserved_sets_and_kansas_provenance_are_deterministic(self):
        state = subject.build()
        self.assertEqual(91, len(state["source"]))
        self.assertEqual(93, len(state["persistent"]))
        self.assertEqual(2, len(state["kansas"]))
        self.assertTrue(all(x["classification"] == "VALID_PERSISTED_SOURCE_EVENT_NOT_IN_LATEST_SNAPSHOT" for x in state["kansas"]))
        self.assertTrue(all(x["prior_source_snapshot_membership"] for x in state["kansas"]))
        self.assertEqual(subject.sha(subject.build()["package"]), subject.sha(state["package"]))

    def test_candidate_set_preserves_persistent_contract_and_old_pmi_boundary(self):
        state = subject.build()
        self.assertEqual("PERSISTENT_CANONICAL_EVENT_STORE", state["relationship"]["contract_classification"])
        self.assertEqual(2, state["relationship"]["persistent_only_count"])
        self.assertEqual(93, len(state["events"]))
        self.assertTrue(all(x["episode_id"] != subject.PMI_EPISODE for x in state["eligible"]))
        self.assertFalse(state["package"]["old_pmi_attention_reused"])
        self.assertFalse(state["package"]["old_pmi_request_responses_reused"])


if __name__ == "__main__":
    unittest.main()
