import json
import unittest

from automation import run_presignal_v21_candidate_selection_brief_v1 as subject


class CandidateSelectionBriefTests(unittest.TestCase):
    def test_brief_is_advisory_and_complete(self):
        decision = subject.run("2026-07-24T04:57:39Z")
        self.assertEqual("NEW_R6_CANDIDATE_SELECTION_BRIEF_READY_USER_DECISION_REQUIRED", decision)
        table = json.loads((subject.OUT / "all_eligible_episode_decision_table.json").read_text())["rows"]
        recommendation = json.loads((subject.OUT / "candidate_recommendation.json").read_text())
        shortlist = json.loads((subject.OUT / "candidate_shortlist.json").read_text())["shortlist"]
        self.assertEqual(29, len(table)); self.assertEqual(29, len({x["episode_identity"] for x in table}))
        self.assertLessEqual(len(shortlist), 5); self.assertIn(recommendation["recommended_candidate_identity"], [x["episode_identity"] for x in shortlist])
        self.assertTrue(recommendation["recommendation_advisory"]); self.assertFalse(recommendation["selection_authorization_created"])
        self.assertNotIn("EP_BATCH_0b3bf1cac3c02da74063", [x["episode_identity"] for x in table])

    def test_expired_candidates_are_not_shortlisted(self):
        subject.run("2026-08-01T00:00:00Z")
        shortlist = json.loads((subject.OUT / "candidate_shortlist.json").read_text())["shortlist"]
        self.assertEqual([], shortlist)


if __name__ == "__main__":
    unittest.main()
