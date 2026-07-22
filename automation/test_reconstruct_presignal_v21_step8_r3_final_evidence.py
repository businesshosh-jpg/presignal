#!/usr/bin/env python3
"""Focused invariants for the read-only final-evidence reconstruction."""
from __future__ import annotations

import unittest

from automation import reconstruct_presignal_v21_step8_r3_final_evidence_v1 as recon


class ReconstructionTests(unittest.TestCase):
    def test_rejected_attention_is_not_selected(self) -> None:
        rejected = {"accepted": False, "output": {"rows": [{"attention_label": "PRIMARY_DRIVER", "status": "parsed"}]}}
        self.assertIsNone(recon.attention_selection(rejected))

    def test_accepted_primary_driver_is_selected(self) -> None:
        accepted = {"accepted": True, "output": {"rows": [{"attention_label": "PRIMARY_DRIVER", "status": "parsed"}]}}
        self.assertEqual(recon.attention_selection(accepted), "FORECAST")

    def test_null_pattern_requires_every_horizon(self) -> None:
        self.assertTrue(recon.directions_null({f"direction_{h}m_ok": None for h in recon.HORIZONS}))
        self.assertFalse(recon.directions_null({"direction_5m_ok": True, "direction_15m_ok": None, "direction_30m_ok": None, "direction_60m_ok": None}))

    def test_mcnemar_and_sampled_signflip_are_deterministic(self) -> None:
        self.assertEqual(recon.mcnemar(1, 1), 1.0)
        clusters = {str(index): [1 if index % 2 else -1] for index in range(17)}
        self.assertEqual(recon.signflip(clusters), recon.signflip(clusters))

    def test_authoritative_population_counts(self) -> None:
        grouped, _ = recon.stage_index(recon.SOURCE_RUN)
        selected = []
        affected = 0
        for stages in grouped.values():
            if recon.attention_selection(stages.get("ATTENTION:")) != "FORECAST":
                continue
            selected.append(stages)
            a, e, evaluation = stages.get("FORECAST:PACK_A"), stages.get("FORECAST:PACK_E"), stages.get("EVALUATE:")
            if a and e and a.get("accepted") and e.get("accepted") and (recon.directions_null(recon.evaluation(evaluation, "PACK_A")) or recon.directions_null(recon.evaluation(evaluation, "PACK_E"))):
                affected += 1
        self.assertEqual(len(selected), 192)
        self.assertEqual(affected, 83)


if __name__ == "__main__":
    unittest.main()
