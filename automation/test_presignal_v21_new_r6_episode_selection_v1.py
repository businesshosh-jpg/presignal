import json
import unittest

from automation import run_presignal_v21_new_r6_episode_selection_v1 as subject


class NewR6FomcSelectionTests(unittest.TestCase):
    def test_user_selected_episode_prepares_but_never_dispatches_attention(self):
        decision = subject.run("2026-07-24T05:09:34Z")
        self.assertEqual("NEW_R6_EPISODE_SELECTED_ATTENTION_AUTHORIZATION_PREPARED", decision)
        auth = json.loads((subject.OUT / "new_r6_attention_authorization_preparation.json").read_text())
        manifest = json.loads((subject.OUT / "new_r6_selected_episode_manifest.json").read_text())
        self.assertEqual(subject.SELECTED, manifest["episode_identity"])
        self.assertEqual([], manifest["secondary_event_identities"])
        self.assertEqual(1, auth["attention_call_budget"]); self.assertEqual(0, auth["retry_count"])
        self.assertFalse(auth["authorization_activated"]); self.assertFalse(auth["provider_call_executed"])

    def test_press_conference_is_separate_and_cutoff_closed_fails(self):
        subject.run("2026-07-24T05:09:34Z")
        separation = json.loads((subject.OUT / "new_r6_fomc_episode_separation_report.json").read_text())
        self.assertTrue(separation["separate_identities"]); self.assertTrue(separation["separate_membership"])
        self.assertEqual(30, separation["release_difference_minutes"])
        self.assertEqual("NEW_R6_EPISODE_SELECTION_BLOCKED_CUTOFF_CLOSED", subject.run("2026-07-29T18:00:00Z"))
        subject.run("2026-07-24T05:09:34Z")


if __name__ == "__main__":
    unittest.main()
