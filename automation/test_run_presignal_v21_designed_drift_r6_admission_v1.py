import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from automation import run_presignal_v21_designed_drift_r6_admission_v1 as admission
from automation.presignal_v21_canonical_states_v1 import SelectionState


NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
EPISODE = {"episode_id": "EP", "member_event_ids": ["E"], "release_ts": "2030-01-01T01:00:00Z", "forecast_cutoff_ts": "2030-01-01T00:30:00Z"}
COMMON = {"episode_id": "EP", "provider": "OpenAI", "model": "m", "forecast_cutoff": "2030-01-01T00:30:00Z", "forecast_target": "EP"}


class AdmissionTests(unittest.TestCase):
    def test_conditional_batch_semantics(self):
        admission.validate_event_batch_semantics({'event_id':'E','type':'single','batch_id':''})
        admission.validate_event_batch_semantics({'event_id':'E','type':'member','batch_id':'B'})
        for row, reason in (({'event_id':'E','type':'single','batch_id':'B'},'SINGLE'),({'event_id':'E','type':'member','batch_id':''},'MEMBER'),({'event_id':'','type':'single','batch_id':''},'EVENT_ID'),({'event_id':'E','type':'batch','batch_id':''},'TYPE')):
            with self.assertRaisesRegex(admission.AdmissionError,reason): admission.validate_event_batch_semantics(row)
    def inputs(self):
        return {"attention": {"identity": "A"}, "requests": {"identity": "R"}, "pack_a": {**COMMON, "identity": "PA"}, "pack_e": {**COMMON, "identity": "PE"}}

    def test_selected_pre_cutoff_is_ready_and_non_entries_are_not(self):
        ready = admission.admission_snapshot(episode=EPISODE, selection_state=SelectionState.SELECTED, provider="OpenAI", model="m", admitted_at=NOW, **self.inputs())
        self.assertTrue(ready["smoke_ready"])
        for state in (SelectionState.WATCH, SelectionState.IGNORED, SelectionState.NOT_SELECTED, SelectionState.REJECTED):
            value = admission.admission_snapshot(episode=EPISODE, selection_state=state, provider="OpenAI", model="m", admitted_at=NOW, **self.inputs())
            self.assertFalse(value["smoke_ready"])

    def test_late_lineage_mismatch_and_leakage_fail_closed(self):
        with self.assertRaisesRegex(admission.AdmissionError, "NO_PRE_CUTOFF"):
            admission.admission_snapshot(episode=EPISODE, selection_state=SelectionState.SELECTED, provider="OpenAI", model="m", admitted_at=datetime(2030, 1, 1, 1, tzinfo=timezone.utc), **self.inputs())
        bad = self.inputs(); bad["pack_e"]["model"] = "other"
        with self.assertRaisesRegex(admission.AdmissionError, "PACK_LINEAGE"):
            admission.admission_snapshot(episode=EPISODE, selection_state=SelectionState.SELECTED, provider="OpenAI", model="m", admitted_at=NOW, **bad)
        bad = self.inputs(); bad["pack_a"]["outcome"] = {}
        with self.assertRaisesRegex(admission.AdmissionError, "PACK_LEAKAGE"):
            admission.admission_snapshot(episode=EPISODE, selection_state=SelectionState.SELECTED, provider="OpenAI", model="m", admitted_at=NOW, **bad)

    def test_isolated_atomic_persistence_and_duplicate_protection(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "isolated"
            identity = {"smoke_ready": True, "episode_id": "EP"}
            run = admission.persist_admission(run_id="RUN", identity=identity, snapshots={"episode_snapshot.json": EPISODE}, root=root)
            self.assertTrue((run / "smoke_identity.json").exists())
            with self.assertRaisesRegex(admission.AdmissionError, "DUPLICATE"):
                admission.persist_admission(run_id="RUN", identity=identity, snapshots={}, root=root)
            with self.assertRaisesRegex(admission.AdmissionError, "WRITE_ISOLATION"):
                admission.safe_run_path("Predictions", root=root)


if __name__ == "__main__":
    unittest.main()
