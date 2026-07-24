import json
import unittest

from automation import run_presignal_v21_native_attention_bridge_repair_v1 as subject


class AttentionBridgeRepairTests(unittest.TestCase):
    def test_role_is_not_provider_alias_and_preserved_raw_is_unchanged(self):
        self.assertEqual("NEW_R6_ATTENTION_BRIDGE_REPAIR_BLOCKED_PAYLOAD_ROLE", subject.run())
        role = json.loads((subject.OUT / "new_r6_attention_payload_role_decision.json").read_text())
        replay = json.loads((subject.OUT / "new_r6_attention_preserved_response_revalidation.json").read_text())
        self.assertFalse(role["provider_identity_changed"]); self.assertFalse(role["role_enum_broadened"])
        self.assertTrue(replay["raw_response_unchanged"]); self.assertTrue(replay["member_lineage_valid_after"])


if __name__ == "__main__":
    unittest.main()
