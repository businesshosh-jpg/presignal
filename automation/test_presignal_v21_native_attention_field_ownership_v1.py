import json
import unittest

from automation import run_presignal_v21_native_attention_field_ownership_v1 as subject


class FieldOwnershipTests(unittest.TestCase):
    def test_system_owned_fields_override_raw_and_preserved_response_canonicalizes(self):
        self.assertEqual("NEW_R6_NATIVE_ATTENTION_FIELD_OWNERSHIP_REPAIRED_ACCEPTED", subject.run())
        attention = json.loads((subject.OUT / "new_r6_native_attention.json").read_text())
        replay = json.loads((subject.OUT / "native_attention_preserved_response_revalidation.json").read_text())
        req = json.loads((subject.OUT / "new_r6_information_request_authorization_preparation.json").read_text())
        self.assertEqual("Gemini", attention["provider_identity"]); self.assertEqual("macro-research-model", attention["payload_provider_role"])
        self.assertTrue(replay["raw_checksum_unchanged"]); self.assertTrue(replay["duplicate_attention_items_normalized"])
        self.assertFalse(req["authorization_activated"]); self.assertFalse(req["request_call_executed"])


if __name__ == "__main__":
    unittest.main()
