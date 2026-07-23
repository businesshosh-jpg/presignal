"""Focused offline tests for R6 native Attention and Pack A materialization."""
from __future__ import annotations

from copy import deepcopy
import unittest

from automation import presignal_v21_native_input_materialization_v1 as native
from automation import run_presignal_v21_native_input_materialization_v1 as reports


class _Values:
    def __init__(self, rows=None): self.rows = rows or []; self.appended = []
    def get(self, **kwargs): self.kwargs = kwargs; return self
    def append(self, **kwargs): self.append_kwargs = kwargs; return self
    def execute(self):
        if hasattr(self, 'append_kwargs'): self.appended.append(self.append_kwargs); return {'updates': {'updatedRange': 'x'}}
        return {'values': [list(native.ATTENTION_HEADERS if 'Native_Attention' in self.kwargs['range'] else native.PACK_A_HEADERS)] if self.kwargs['range'].endswith('1:1') else self.rows}
class _Sheets:
    def __init__(self, values): self.values_obj = values
    def values(self): return self.values_obj
class _Service:
    def __init__(self, values): self.sheets_obj = _Sheets(values)
    def spreadsheets(self): return self.sheets_obj


class NativeInputMaterializationTests(unittest.TestCase):
    def setUp(self): self.episode, self.attention, self.requests = reports.fixture()
    def test_attention_is_deterministic_and_watch_is_rejected(self):
        second = native.materialize_selected_native_attention(episode=self.episode, provider='Gemini', model='gemini-2.5-flash-lite', prompt_version='NATIVE_ATTENTION_PROMPT_V1', selection_state='SELECTED_FOR_INFORMATION_REQUESTS', acceptance_state='ACCEPTED', selection_reason='frozen native contract fixture', effective_timestamp='2030-01-01T11:55:00Z', provenance={'source':'existing_v2_attention_prompt_schema','fixture':True})
        self.assertEqual(self.attention['attention_identity'], second['attention_identity'])
        with self.assertRaisesRegex(native.NativeInputMaterializationError, 'NOT_SELECTED'):
            native.materialize_selected_native_attention(episode=self.episode, provider='Gemini', model='gemini-2.5-flash-lite', prompt_version='p', selection_state='WATCH', acceptance_state='ACCEPTED', selection_reason='historical', effective_timestamp='2030-01-01T11:55:00Z', provenance={})
    def test_pack_a_is_deterministic_and_has_no_pack_e_content(self):
        pack = native.build_canonical_pack_a(episode=self.episode, attention=self.attention, canonical_requests=self.requests, provenance={'source':'existing_v2_pack_a_provider_requests','fixture':True})
        self.assertEqual(pack['content_checksum'], native.build_canonical_pack_a(episode=self.episode, attention=self.attention, canonical_requests=self.requests, provenance={'source':'existing_v2_pack_a_provider_requests','fixture':True})['content_checksum'])
        self.assertTrue(all('pack_e' not in native.canonical(item).lower() for item in pack['pack_a_items']))
        contaminated = deepcopy(self.requests); contaminated[0]['pack_e_source_lineage'] = 'bad'
        with self.assertRaisesRegex(native.NativeInputMaterializationError, 'CONTAMINATION'): native.build_canonical_pack_a(episode=self.episode, attention=self.attention, canonical_requests=contaminated, provenance={})
    def test_pack_a_ordering_and_lineage_fail_closed(self):
        with self.assertRaisesRegex(native.NativeInputMaterializationError, 'ORDER_NOT_CANONICAL'):
            native.build_canonical_pack_a(episode=self.episode, attention=self.attention, canonical_requests=list(reversed(self.requests)), provenance={})
        wrong = deepcopy(self.requests); wrong[0]['episode_identity'] = 'wrong'
        with self.assertRaisesRegex(native.NativeInputMaterializationError, 'LINEAGE_MISMATCH'): native.build_canonical_pack_a(episode=self.episode, attention=self.attention, canonical_requests=wrong, provenance={})
    def test_writers_fail_closed_on_wrong_target_and_duplicate_conflict(self):
        record = {key: 'x' for key in native.ATTENTION_HEADERS}; record.update({'attention_identity':'A','authorization_identity':native.R6_AUTHORIZATION,'authorization_fingerprint':'AUTH','route_b_freeze_fingerprint':native.ROUTE_B_FREEZE})
        with self.assertRaisesRegex(native.NativeInputMaterializationError, 'TARGET_MISMATCH'): native.persist_native_attention(sheets_service=_Service(_Values()), record=record, authorization_fingerprint='AUTH', spreadsheet_id='wrong', sheet_name=native.ATTENTION_SHEET)
        row = [record[key] for key in native.ATTENTION_HEADERS]; changed = list(row); changed[1] = 'different'
        with self.assertRaisesRegex(native.NativeInputMaterializationError, 'DUPLICATE_CONFLICT'): native.persist_native_attention(sheets_service=_Service(_Values(rows=[changed])), record=record, authorization_fingerprint='AUTH', spreadsheet_id=native.MAIN_SPREADSHEET_ID, sheet_name=native.ATTENTION_SHEET)
    def test_reports_are_three_run_deterministic_and_block_live_materialization(self):
        value = reports.build_reports(); self.assertEqual(value['native_input_determinism_report.json']['proof_runs'], 3)
        self.assertEqual(value['final_native_input_materialization_decision.json']['decision'], reports.DECISION)
        self.assertEqual(sum(value['native_input_isolation_audit.json'].values()), 0)


if __name__ == '__main__': unittest.main()
