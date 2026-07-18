from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps_script" / "historical_market_data_endpoint.js"


NODE_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const writes = [];
const sandbox = {
  Date,
  JSON,
  Math,
  Number,
  String,
  Array,
  Object,
  isFinite,
  encodeURIComponent,
  PropertiesService: {getScriptProperties: () => ({getProperty: name => input.properties[name] || ''})},
  Session: {getActiveUser: () => ({getEmail: () => input.active_email || ''})},
  UrlFetchApp: {fetch: (url, options) => {
    sandbox.captured = {url, options};
    if (input.transport_error) throw new Error('transport');
    return {getResponseCode: () => input.http_status || 200, getContentText: () => input.body || '[]'};
  }},
  SpreadsheetApp: {openById: () => { writes.push('openById'); throw new Error('forbidden'); }},
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('apps_script/historical_market_data_endpoint.js', 'utf8'), sandbox);
let output;
try {
  output = {ok: true, result: sandbox.apiFetchGovernedHistoricalUsdJpyObservation(input.params)};
} catch (error) {
  output = {ok: false, error: String(error && error.message || error)};
}
output.captured = sandbox.captured || null;
output.writes = writes;
process.stdout.write(JSON.stringify(output));
"""


def endpoint_result(payload: dict) -> dict:
    result = subprocess.run(
        ["node", "-e", NODE_HARNESS],
        cwd=ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def valid_payload(**overrides: object) -> dict:
    payload = {
    "properties": {"TIINGO_API_KEY": "secret"},
        "params": {
            "request_identity": "session|member|start",
            "instrument": "USD/JPY",
            "requested_timestamp": "2024-05-06T07:00:00Z",
            "timezone": "UTC",
        },
        "body": json.dumps([{
            "date": "2024-05-06T07:00:00Z",
            "open": 155.1,
            "high": 155.2,
            "low": 155.0,
            "close": 155.15,
        }]),
    }
    payload.update(overrides)
    return payload


class HistoricalMarketDataEndpointTest(unittest.TestCase):
    def test_exact_timestamp_request_and_raw_timestamp_are_preserved(self):
        result = endpoint_result(valid_payload())
        self.assertTrue(result["ok"])
        response = result["result"]
        self.assertEqual(response["status"], "SUCCESS")
        self.assertEqual(response["request_identity"], "session|member|start")
        self.assertEqual(response["requested_timestamp"], "2024-05-06T07:00:00Z")
        observation = response["observations"][0]
        self.assertEqual(observation["provider_returned_timestamp_raw"], "2024-05-06T07:00:00Z")
        self.assertEqual(observation["returned_observation_timestamp"], "2024-05-06T07:00:00.000Z")
        self.assertEqual(observation["accepted_raw_price_field"], "close")
        self.assertNotIn("secret", json.dumps(response))

    def test_execution_api_owner_gate_and_request_validation_fail_closed(self):
        manifest = json.loads((ROOT / "apps_script" / "appsscript.json").read_text())
        self.assertEqual(manifest["executionApi"]["access"], "MYSELF")
        unsupported = endpoint_result(valid_payload(params={"instrument": "EUR/USD", "requested_timestamp": "2024-05-06T07:00:00Z"}))
        self.assertFalse(unsupported["ok"])
        self.assertEqual(unsupported["error"], "HISTORICAL_USDJPY_ENDPOINT_UNSUPPORTED_INSTRUMENT")
        missing = endpoint_result(valid_payload(params={"instrument": "USD/JPY"}))
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["error"], "HISTORICAL_USDJPY_ENDPOINT_MISSING_TIMESTAMP")

    def test_provider_priority_missing_and_transport_results_are_deterministic(self):
        fallback = endpoint_result(valid_payload(properties={"EODHD_API_KEY": "secret"}, body=json.dumps([{
            "timestamp": 1714978800, "open": 155.1, "high": 155.2, "low": 155.0, "close": 155.15,
        }])))
        self.assertTrue(fallback["ok"])
        response = fallback["result"]
        self.assertEqual(response["provider_hierarchy_attempted"], ["tiingo", "eodhd"])
        self.assertEqual(response["provider_attempts"][0]["status"], "CREDENTIAL_UNAVAILABLE")
        self.assertEqual(response["selected_provider"], "eodhd")

        missing = endpoint_result(valid_payload(body="[]"))
        self.assertTrue(missing["ok"])
        self.assertEqual(missing["result"]["provider_attempts"][0]["status"], "OBSERVATION_UNAVAILABLE")

        transport = endpoint_result(valid_payload(transport_error=True))
        self.assertTrue(transport["ok"])
        self.assertEqual(transport["result"]["provider_attempts"][0]["status"], "TRANSPORT_FAILURE")

    def test_endpoint_source_cannot_use_spreadsheets_or_operational_helpers(self):
        source = SOURCE.read_text()
        prohibited = [
            "SpreadsheetApp", "getActiveSpreadsheet", "appendRow", "setValue", "setValues",
            "getFxCandlesForWindow_", "fetchTiingoFx_", "fetchEodhdFx_", "log_(", "Session.",
        ]
        for token in prohibited:
            self.assertNotIn(token, source)
        result = endpoint_result(valid_payload())
        self.assertEqual(result["writes"], [])
        self.assertEqual(result["captured"]["options"]["muteHttpExceptions"], True)

    def test_schema_shape_is_stable(self):
        result = endpoint_result(valid_payload())
        self.assertTrue(result["ok"])
        response = result["result"]
        self.assertEqual(response["schema_version"], "presignal.historical_usdjpy_raw_observation.v1")
        self.assertEqual(list(response.keys()), [
            "schema_version", "request_identity", "instrument", "requested_timestamp",
            "requested_window_start", "requested_window_end", "timezone", "provider_hierarchy_attempted",
            "provider_attempts", "selected_provider", "status", "missing_data_reason",
            "returned_observation_count", "observations", "response_generated_at",
        ])


if __name__ == "__main__":
    unittest.main()
