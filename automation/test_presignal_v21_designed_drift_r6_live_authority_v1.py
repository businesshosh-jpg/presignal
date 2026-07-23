"""Focused tests for the R6 explicit authority setup and isolated writer."""
from __future__ import annotations

from copy import deepcopy
import unittest

from automation import presignal_v21_r6_paired_evidence_writer_v1 as writer
from automation import run_presignal_v21_designed_drift_r6_live_authority_v1 as authority


class _Values:
    def __init__(self, existing=None): self.existing = existing or []; self.appended = []
    def get(self, **kwargs): self.kwargs = kwargs; return self
    def append(self, **kwargs): self.append_kwargs = kwargs; return self
    def execute(self):
        if getattr(self, 'append_kwargs', None): self.appended.append(self.append_kwargs); return {'updates': {'updatedRange': 'R6_Paired_Evidence!A2:AF2'}}
        if self.kwargs['range'].endswith('1:1'): return {'values': [list(writer.EVIDENCE_HEADERS)]}
        return {'values': self.existing}
class _Sheets:
    def __init__(self, values): self._values = values
    def values(self): return self._values
class _Service:
    def __init__(self, values): self._sheets = _Sheets(values)
    def spreadsheets(self): return self._sheets


def evidence() -> dict[str, str]:
    row = {key: 'x' for key in writer.EVIDENCE_HEADERS}
    row.update({'authorization_identity': writer.AUTHORIZATION_NAME, 'authorization_fingerprint': 'AUTH', 'route_b_freeze_name': writer.ROUTE_B_FREEZE_NAME, 'route_b_freeze_fingerprint': writer.ROUTE_B_FREEZE_FINGERPRINT, 'provider': 'Gemini', 'model': 'gemini-2.5-flash-lite', 'call_order': 'PACK_A_THEN_PACK_E', 'run_status': 'SUCCESS'})
    return row


class R6LiveAuthorityTests(unittest.TestCase):
    def setUp(self): self.value = authority.build_authority(); self.reports = self.value['reports']
    def test_source_registry_is_stable_and_one_run_only(self):
        manifest = self.reports['prospective_source_environment_manifest.json']; binding = self.reports['prospective_source_environment_binding.json']
        self.assertEqual(manifest['approved_source_count'], 16); self.assertTrue(manifest['native_acquisition_record_compatible'])
        self.assertEqual(manifest['registry_checksum'], authority.build_authority()['reports']['prospective_source_environment_manifest.json']['registry_checksum'])
        self.assertEqual(binding['binding_status'], 'BOUND_FOR_ONE_R6_RUN_ONLY'); self.assertFalse(manifest['general_prospective_authority']); self.assertFalse(manifest['permanent_promotion']); self.assertFalse(binding['registry_expansion_permitted'])
    def test_google_input_is_bounded_and_historical_attention_is_rejected(self):
        self.assertEqual(self.reports['google_input_workbook_binding.json']['spreadsheet_id'], authority.MAIN_SPREADSHEET_ID)
        self.assertEqual(self.reports['google_episode_input_binding.json']['object'], 'Event')
        self.assertEqual(self.reports['google_attention_input_binding.json']['binding_status'], 'BLOCKED')
        self.assertEqual(self.reports['google_pack_a_input_binding.json']['binding_status'], 'BLOCKED')
    def test_destination_and_schema_are_isolated(self):
        destination = self.reports['r6_evidence_destination_binding.json']; schema = self.reports['r6_evidence_schema.json']
        self.assertEqual(destination['maximum_successful_writes'], 1); self.assertFalse(destination['outcome_reachability']); self.assertFalse(destination['evaluation_reachability'])
        self.assertFalse(schema['outcome_fields_present']); self.assertFalse(schema['evaluation_fields_present'])
    def test_writer_fails_closed_on_target_authorization_freeze_and_write_limit(self):
        service = _Service(_Values())
        row = evidence(); result = writer.persist_one_paired_evidence(sheets_service=service, evidence=row, authorization_fingerprint='AUTH', spreadsheet_id=writer.TARGET_SPREADSHEET_ID, sheet_name=writer.TARGET_SHEET)
        self.assertEqual(result['successful_write_count'], 1)
        with self.assertRaisesRegex(writer.R6EvidenceWriterError, 'TARGET_MISMATCH'): writer.persist_one_paired_evidence(sheets_service=service, evidence=row, authorization_fingerprint='AUTH', spreadsheet_id='wrong', sheet_name=writer.TARGET_SHEET)
        wrong_auth = deepcopy(row); wrong_auth['authorization_fingerprint'] = 'wrong'
        with self.assertRaisesRegex(writer.R6EvidenceWriterError, 'AUTHORIZATION_MISMATCH'): writer.validate_evidence(wrong_auth, authorization_fingerprint='AUTH')
        wrong_freeze = deepcopy(row); wrong_freeze['route_b_freeze_fingerprint'] = 'wrong'
        with self.assertRaisesRegex(writer.R6EvidenceWriterError, 'FREEZE_MISMATCH'): writer.validate_evidence(wrong_freeze, authorization_fingerprint='AUTH')
        with self.assertRaisesRegex(writer.R6EvidenceWriterError, 'WRITE_LIMIT_EXCEEDED'): writer.persist_one_paired_evidence(sheets_service=_Service(_Values(existing=[['already']])), evidence=row, authorization_fingerprint='AUTH', spreadsheet_id=writer.TARGET_SPREADSHEET_ID, sheet_name=writer.TARGET_SHEET)
        forbidden = deepcopy(row); forbidden['outcome'] = 'forbidden'
        with self.assertRaises(writer.R6EvidenceWriterError): writer.validate_evidence(forbidden, authorization_fingerprint='AUTH')
    def test_v1_v2_preserved_and_v3_fingerprint_reproducible(self):
        self.assertEqual(self.value['fingerprint'], authority.build_authority()['fingerprint'])
        self.assertFalse(self.value['identity']['execution_authorized']); self.assertEqual(self.value['identity']['provider_call_budget'], 2); self.assertEqual(self.value['identity']['retry_count'], 0)
        self.assertTrue(self.value['identity']['outcome_prohibited']); self.assertTrue(self.value['identity']['evaluation_prohibited'])


if __name__ == '__main__': unittest.main()
