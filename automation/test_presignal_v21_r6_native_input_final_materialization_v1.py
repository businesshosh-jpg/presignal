"""Offline guards for the bounded final native-input materialization runner."""
from __future__ import annotations

import unittest

from automation import presignal_v21_native_input_materialization_v1 as native
from automation import run_presignal_v21_r6_native_input_final_materialization_v1 as runner


class _Values:
    def __init__(self): self.header = []; self.rows = []; self.last = {}
    def get(self, **kwargs): self.last = kwargs; return self
    def update(self, **kwargs): self.update_kwargs = kwargs; return self
    def append(self, **kwargs): self.append_kwargs = kwargs; return self
    def execute(self):
        if hasattr(self, "update_kwargs"):
            self.header = list(self.update_kwargs["body"]["values"][0]); del self.update_kwargs; return {}
        if hasattr(self, "append_kwargs"):
            self.rows.extend(self.append_kwargs["body"]["values"]); del self.append_kwargs; return {"updates": {"updatedRange": "Native_Attention!A2:S2"}}
        if self.last["range"].endswith("1:1"): return {"values": [self.header]}
        return {"values": self.rows}


class _Sheets:
    def __init__(self, values): self.values_object = values; self.titles = []
    def get(self, **kwargs): return self
    def batchUpdate(self, **kwargs):
        self.titles.append(kwargs["body"]["requests"][0]["addSheet"]["properties"]["title"]); return self
    def values(self): return self.values_object
    def execute(self): return {"sheets": [{"properties": {"title": title}} for title in self.titles]}


class _Service:
    def __init__(self): self.values_object = _Values(); self.sheets_object = _Sheets(self.values_object)
    def spreadsheets(self): return self.sheets_object


class FinalNativeInputMaterializationTests(unittest.TestCase):
    def test_preserved_attention_map_cannot_be_reinterpreted_as_requests(self):
        value = runner.reports(attempt_google=False)
        request = value["canonical_request_set.json"]
        self.assertEqual(request["source_object"], "session_attention_map")
        self.assertFalse(request["usable_information_request_response"])
        self.assertEqual(request["failure"], "CANONICAL_REQUEST_RESPONSE_UNAVAILABLE")
        self.assertEqual(value["final_native_input_materialization_decision.json"]["decision"], "R6_NATIVE_INPUTS_FINAL_MATERIALIZATION_BLOCKED")

    def test_attention_record_preserves_exact_bridge_role_and_checksums(self):
        attention, _raw, _provenance = runner.load_validated_attention()
        record = runner._attention_record(attention)
        self.assertEqual(record["provider_identity"], "Gemini")
        self.assertEqual(record["payload_provider_role"], "macro-research-model")
        self.assertEqual(record["raw_response_checksum"], runner.EXPECTED_RAW)
        self.assertEqual(set(record), set(native.ATTENTION_HEADERS) | {"authorization_identity", "authorization_fingerprint", "route_b_freeze_fingerprint"})

    def test_schema_is_append_only_and_writer_is_idempotent(self):
        service = _Service()
        schema = native.ensure_bounded_object_schema(sheets_service=service, spreadsheet_id=native.MAIN_SPREADSHEET_ID, sheet_name=native.ATTENTION_SHEET, required_headers=native.ATTENTION_HEADERS)
        self.assertTrue(schema["created"])
        attention, _raw, _provenance = runner.load_validated_attention(); record = runner._attention_record(attention)
        first = native.persist_native_attention(sheets_service=service, record=record, authorization_fingerprint=runner.V3_FINGERPRINT, spreadsheet_id=native.MAIN_SPREADSHEET_ID, sheet_name=native.ATTENTION_SHEET)
        second = native.persist_native_attention(sheets_service=service, record=record, authorization_fingerprint=runner.V3_FINGERPRINT, spreadsheet_id=native.MAIN_SPREADSHEET_ID, sheet_name=native.ATTENTION_SHEET)
        self.assertEqual(first["status"], "MATERIALIZED")
        self.assertEqual(second["status"], "ALREADY_MATERIALIZED_IDENTICAL")


if __name__ == "__main__":
    unittest.main()
