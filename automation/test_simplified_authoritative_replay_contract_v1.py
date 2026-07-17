from __future__ import annotations

import unittest

from automation.simplified_authoritative_replay_contract_v1 import (
    ReducedForecastError, canonical_event_identity, driver_options,
    require_unique_event_identities, validate_and_resolve,
)


MEMBERS = [
    {"event_id": "event-a", "indicator_name": "A"},
    {"event_id": "event-b", "indicator_name": "B"},
]


def valid_payload():
    options = driver_options(MEMBERS)
    return {"primary_driver_token": options[0]["token"], "secondary_driver_token": options[1]["token"],
            "final_usdjpy_direction": "UP", "reaction_strength": "MODERATE", "confidence": 0.6,
            "primary_thesis": "Primary forecast.", "secondary_thesis": "Secondary context.",
            "reasoning_steps": ["Step one.", "Step two."]}


class SimplifiedAuthoritativeReplayContractTest(unittest.TestCase):
    def test_tokens_are_deterministic_and_resolve(self):
        self.assertEqual(driver_options(MEMBERS), driver_options(list(reversed(MEMBERS))))
        result = validate_and_resolve(valid_payload(), MEMBERS)
        self.assertEqual(result["primary_driver_event_id"], "event-a")
        self.assertNotIn("primary_driver_token", result)

    def test_core_fields_and_steps_fail_closed(self):
        payload = valid_payload(); payload.pop("primary_thesis")
        with self.assertRaisesRegex(ReducedForecastError, "MISSING_FIELD"):
            validate_and_resolve(payload, MEMBERS)
        payload = valid_payload(); payload["reasoning_steps"] = ["only one"]
        with self.assertRaisesRegex(ReducedForecastError, "REASONING_STEPS_INVALID"):
            validate_and_resolve(payload, MEMBERS)

    def test_unknown_driver_and_duplicate_acceptance_inputs_fail(self):
        payload = valid_payload(); payload["primary_driver_token"] = "DRV_unknown"
        with self.assertRaisesRegex(ReducedForecastError, "PRIMARY_DRIVER_TOKEN_INVALID"):
            validate_and_resolve(payload, MEMBERS)

    def test_duplicate_event_ids_fail_before_freeze_and_canonical_ids_are_stable(self):
        with self.assertRaisesRegex(ReducedForecastError, "DUPLICATE"):
            require_unique_event_identities([{**MEMBERS[0]}, {**MEMBERS[0]}])
        member = {**MEMBERS[0], "session_id": "s", "member_order": 1}
        self.assertEqual(canonical_event_identity(member), canonical_event_identity(dict(member)))
        payload = valid_payload(); payload["secondary_driver_token"] = payload["primary_driver_token"]
        with self.assertRaisesRegex(ReducedForecastError, "SECONDARY_DRIVER_TOKEN_INVALID"):
            validate_and_resolve(payload, MEMBERS)


if __name__ == "__main__":
    unittest.main()
