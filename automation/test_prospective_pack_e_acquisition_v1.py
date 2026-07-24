"""Offline contract tests for caller-controlled prospective Pack E adapters."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps_script" / "prospective_pack_e_acquisition.js"


NODE_HARNESS = r"""
const crypto = require('crypto');
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = { FMP: 0, FRED: 0, EODHD: 0, writers: 0 };
const sandbox = {
  Date, JSON, Math, Number, String, Array, Object, isFinite,
  Utilities: {
    DigestAlgorithm: { SHA_256: 'sha256' }, Charset: { UTF_8: 'utf8' },
    computeDigest: (algorithm, text) => Array.from(crypto.createHash(algorithm).update(text, 'utf8').digest()).map(x => x > 127 ? x - 256 : x)
  },
  _v2bFetchFmpHistory_: (symbol, start, end) => { calls.FMP++; if (input.throw_source === 'FMP') throw new Error('source'); return input.rows.FMP || []; },
  _v2bFetchFredHistory_: (symbol, start, end) => { calls.FRED++; if (input.throw_source === 'FRED') throw new Error('source'); return input.rows.FRED || []; },
  _v2bFetchEodhdHistory_: (symbol, start, end) => { calls.EODHD++; if (input.throw_source === 'EODHD') throw new Error('source'); return input.rows.EODHD || []; },
  _v2bBuildSeriesCache_: () => { calls.writers++; throw new Error('writer forbidden'); },
  _buildMarketContextPack_: () => { calls.writers++; throw new Error('writer forbidden'); },
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('apps_script/prospective_pack_e_acquisition.js', 'utf8'), sandbox);
let output;
try { output = { ok: true, result: sandbox.apiBuildProspectivePackENativeAcquisitionRecord(input.request) }; }
catch (error) { output = { ok: false, error: String(error && error.message || error) }; }
output.calls = calls;
process.stdout.write(JSON.stringify(output));
"""


ADAPTER = "apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord"


def payload(source: str = "KSRC_FRED", **overrides: object) -> dict:
    config = {
        "KSRC_FMP": "Apps Script FMP_API_KEY resolver (CFG.FMP_API_KEY or Script Property FMP_API_KEY)",
        "KSRC_FRED": "Apps Script Script Property FRED_API_KEY",
        "KSRC_EODHD": "Apps Script EODHD API-key resolver",
    }[source]
    request = {
        "source_id": source,
        "adapter_identity": ADAPTER,
        "configuration_reference": config,
        "credential_reference_type": "APPS_SCRIPT_SCRIPT_PROPERTY_API_KEY",
        "episode_id": "EP_FIXTURE",
        "pack_a_identity": "PACK_A_FIXTURE",
        "request_identity": "NREQ_FIXTURE",
        "canonical_field": "US2Y_YIELD_LEVEL",
        "query_identity": "DGS2@2026-07-28",
        "query_symbol": "DGS2",
        "bounded_start_date": "2026-07-20",
        "bounded_end_date": "2026-07-28",
        "forecast_cutoff_ts": "2026-07-29T18:00:00Z",
        "retrieval_timestamp": "2026-07-29T17:00:00Z",
        "as_of_timestamp": "2026-07-29T16:00:00Z",
        "source_identity": "fred:DGS2",
        "source_url_or_key": "fred:series:DGS2",
        "source_type": "historical_series_observation",
    }
    request.update(overrides)
    return {"request": request, "rows": {source.split("_")[1]: [
        {"date": "2026-07-25", "value": 4.1}, {"date": "2026-07-28", "value": 4.2}
    ]}}


def invoke(data: dict) -> dict:
    result = subprocess.run(["node", "-e", NODE_HARNESS], cwd=ROOT, input=json.dumps(data), text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


class ProspectivePackEAcquisitionTests(unittest.TestCase):
    def test_valid_fred_fixture_emits_one_native_record_and_never_writes(self) -> None:
        result = invoke(payload())
        self.assertTrue(result["ok"])
        record = result["result"]
        self.assertEqual(record["object"], "NATIVE_ACQUISITION_RECORD")
        self.assertEqual(record["status"], "SUPPLIED")
        self.assertEqual(record["source_items"][0]["value"], 4.2)
        self.assertEqual(result["calls"], {"FMP": 0, "FRED": 1, "EODHD": 0, "writers": 0})
        self.assertNotIn("secret", json.dumps(record))

    def test_same_fixture_is_deterministic_and_one_fetch_has_no_retry(self) -> None:
        first, second, third = invoke(payload()), invoke(payload()), invoke(payload())
        self.assertEqual(first["result"], second["result"])
        self.assertEqual(second["result"], third["result"])
        self.assertEqual(first["calls"]["FRED"], 1)

    def test_fmp_and_eodhd_reuse_their_existing_fetch_paths(self) -> None:
        fmp = invoke(payload("KSRC_FMP", canonical_field="DXY_LEVEL", query_symbol="DX-Y.NYB", query_identity="DX-Y.NYB@2026-07-28", source_identity="fmp:DX-Y.NYB", source_url_or_key="fmp:DX-Y.NYB"))
        eodhd = invoke(payload("KSRC_EODHD", canonical_field="USDJPY_RETURN_24H_PRESESSION", query_symbol="USDJPY.FOREX", query_identity="USDJPY@2026-07-28", source_identity="eodhd:USDJPY.FOREX", source_url_or_key="eodhd:USDJPY.FOREX"))
        self.assertTrue(fmp["ok"]); self.assertTrue(eodhd["ok"])
        self.assertEqual(fmp["calls"]["FMP"], 1)
        self.assertEqual(eodhd["calls"]["EODHD"], 1)
        self.assertEqual(fmp["calls"]["writers"], 0)
        self.assertEqual(eodhd["calls"]["writers"], 0)

    def test_invalid_payloads_fail_closed_and_empty_source_is_a_frozen_failure_record(self) -> None:
        post_cutoff = invoke(payload(retrieval_timestamp="2026-07-29T18:00:01Z"))
        self.assertFalse(post_cutoff["ok"])
        self.assertEqual(post_cutoff["error"], "SOURCE_TEMPORAL_CONTRACT_UNSUPPORTED")
        missing = payload(); missing["rows"]["FRED"] = []
        unavailable = invoke(missing)
        self.assertTrue(unavailable["ok"])
        self.assertEqual(unavailable["result"]["status"], "UNAVAILABLE")
        self.assertEqual(unavailable["result"]["error_classification"], "SOURCE_CONTENT_NOT_FOUND")
        self.assertEqual(unavailable["result"]["raw_acquired_content"], "")
        unapproved = invoke(payload(source_id="KSRC_UNAPPROVED"))
        self.assertFalse(unapproved["ok"])
        self.assertEqual(unapproved["error"], "SOURCE_NOT_APPROVED:KSRC_UNAPPROVED")

    def test_record_contract_includes_required_lineage_and_checksums(self) -> None:
        record = invoke(payload())["result"]
        for field in (
            "acquisition_record_id", "source_id", "adapter_identity", "request_identity", "episode_id",
            "forecast_cutoff_ts", "raw_checksum", "normalized_checksum", "source_items", "status",
        ):
            self.assertTrue(record[field])
        self.assertTrue(record["raw_checksum"].startswith("sha256:"))
        self.assertTrue(record["normalized_checksum"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
