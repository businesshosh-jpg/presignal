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
function providerName(url) {
  if (url.indexOf('tiingo.com') >= 0) return 'tiingo';
  if (url.indexOf('eodhd.com') >= 0) return 'eodhd';
  if (url.indexOf('api.massive.com') >= 0) return 'massive';
  if (url.indexOf('api.twelvedata.com') >= 0) return 'twelvedata';
  return 'unknown';
}
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
    const provider = providerName(url);
    if (!sandbox.captured) sandbox.captured = [];
    sandbox.captured.push({provider, url, options});
    if (input.transport_error || (input.transport_errors && input.transport_errors[provider])) throw new Error('transport');
    const httpStatus = (input.http_statuses && input.http_statuses[provider]) || input.http_status || 200;
    const body = (input.bodies && Object.prototype.hasOwnProperty.call(input.bodies, provider)) ? input.bodies[provider] : (input.body || '[]');
    return {getResponseCode: () => httpStatus, getContentText: () => body};
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
        "bodies": {
            "tiingo": json.dumps([{
                "date": "2024-05-06T07:00:00Z",
                "open": 155.1,
                "high": 155.2,
                "low": 155.0,
                "close": 155.15,
            }]),
        },
    }
    payload.update(overrides)
    return payload


class HistoricalMarketDataEndpointTest(unittest.TestCase):
    def test_exact_timestamp_request_and_raw_timestamp_are_preserved(self):
        result = endpoint_result(valid_payload())
        self.assertTrue(result["ok"])
        response = result["result"]
        self.assertEqual(response["status"], "SUCCESS")
        self.assertEqual(response["mode"], "first_success")
        self.assertEqual(response["request_identity"], "session|member|start")
        self.assertEqual(response["requested_timestamp"], "2024-05-06T07:00:00Z")
        observation = response["observations"][0]
        self.assertEqual(observation["timestamp"], "2024-05-06T07:00:00.000Z")
        self.assertEqual(observation["timestamp_raw"], "2024-05-06T07:00:00Z")
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
        bad_mode = endpoint_result(valid_payload(params={"instrument": "USD/JPY", "requested_timestamp": "2024-05-06T07:00:00Z", "mode": "weird"}))
        self.assertFalse(bad_mode["ok"])
        self.assertEqual(bad_mode["error"], "HISTORICAL_USDJPY_ENDPOINT_UNSUPPORTED_MODE")
        unknown_provider = endpoint_result(valid_payload(params={"instrument": "USD/JPY", "requested_timestamp": "2024-05-06T07:00:00Z", "mode": "provider", "provider": "fcsapi"}))
        self.assertFalse(unknown_provider["ok"])
        self.assertEqual(unknown_provider["error"], "HISTORICAL_USDJPY_ENDPOINT_UNKNOWN_PROVIDER")

    def test_provider_priority_missing_and_transport_results_are_deterministic(self):
        fallback = endpoint_result(valid_payload(properties={"EODHD_API_KEY": "secret"}, bodies={"eodhd": json.dumps([{
            "timestamp": 1714978800, "open": 155.1, "high": 155.2, "low": 155.0, "close": 155.15,
        }])}))
        self.assertTrue(fallback["ok"])
        response = fallback["result"]
        self.assertEqual(response["provider_hierarchy_attempted"], ["tiingo", "eodhd"])
        self.assertEqual(response["provider_attempts"][0]["status"], "CREDENTIAL_UNAVAILABLE")
        self.assertEqual(response["selected_provider"], "eodhd")

        missing = endpoint_result(valid_payload(bodies={"tiingo": "[]"}))
        self.assertTrue(missing["ok"])
        self.assertEqual(missing["result"]["provider_attempts"][0]["status"], "OBSERVATION_UNAVAILABLE")

        transport = endpoint_result(valid_payload(transport_error=True))
        self.assertTrue(transport["ok"])
        self.assertEqual(transport["result"]["provider_attempts"][0]["status"], "TRANSPORT_FAILURE")

    def test_explicit_provider_mode_uses_requested_provider_only(self):
        result = endpoint_result(valid_payload(
            properties={"EODHD_API_KEY": "secret"},
            params={
                "request_identity": "session|member|start",
                "instrument": "USD/JPY",
                "requested_timestamp": "2024-05-06T07:00:00Z",
                "timezone": "UTC",
                "mode": "provider",
                "provider": "eodhd",
            },
            bodies={"eodhd": json.dumps([{
                "timestamp": 1714978800, "open": 155.1, "high": 155.2, "low": 155.0, "close": 155.15,
            }])},
        ))
        self.assertTrue(result["ok"])
        response = result["result"]
        self.assertEqual(response["mode"], "provider")
        self.assertEqual(response["provider_hierarchy_attempted"], ["eodhd"])
        self.assertEqual(response["selected_provider"], "eodhd")
        self.assertEqual(len(result["captured"]), 1)
        self.assertEqual(result["captured"][0]["provider"], "eodhd")
        provider_result = response["provider_result"]
        self.assertEqual(provider_result["source_resolution"], "ONE_MINUTE")
        self.assertEqual(provider_result["observation_type"], "OHLC")
        self.assertTrue(provider_result["credential_route_present"])

    def test_all_available_mode_does_not_short_circuit_and_preserves_independent_failures(self):
        result = endpoint_result(valid_payload(
            properties={
                "TIINGO_API_KEY": "secret",
                "EODHD_API_KEY": "secret",
                "MASSIVE_API_KEY": "secret",
                "TWELVEDATA_API_KEY": "secret",
            },
            params={
                "request_identity": "session|member|start",
                "instrument": "USD/JPY",
                "requested_window_start": "2024-05-06T07:00:00Z",
                "requested_window_end": "2024-05-06T07:02:00Z",
                "timezone": "UTC",
                "mode": "all_available",
            },
            bodies={
                "tiingo": json.dumps([{"date": "2024-05-06T07:00:00Z", "open": 155.1, "high": 155.2, "low": 155.0, "close": 155.15}]),
                "eodhd": json.dumps([{"timestamp": 1714978860, "open": 155.11, "high": 155.21, "low": 155.01, "close": 155.16}]),
                "massive": json.dumps({"results": [{"t": 1714978920000, "o": 155.12, "h": 155.22, "l": 155.02, "c": 155.17}]}),
                "twelvedata": json.dumps({"status": "error", "message": "bad plan"}),
            },
            http_statuses={"twelvedata": 429},
        ))
        self.assertTrue(result["ok"])
        response = result["result"]
        self.assertEqual(response["mode"], "all_available")
        self.assertEqual(response["provider_hierarchy_attempted"], ["tiingo", "eodhd", "massive", "twelvedata"])
        self.assertEqual(len(result["captured"]), 4)
        self.assertEqual([item["provider"] for item in result["captured"]], ["tiingo", "eodhd", "massive", "twelvedata"])
        provider_results = response["provider_results"]
        self.assertEqual([item["provider"] for item in provider_results], ["tiingo", "eodhd", "massive", "twelvedata"])
        self.assertEqual([item["status"] for item in provider_results[:3]], ["SUCCESS", "SUCCESS", "SUCCESS"])
        self.assertEqual(provider_results[3]["status"], "TRANSPORT_FAILURE")
        self.assertEqual(response["comparable_provider_count"], 3)
        self.assertNotIn("secret", json.dumps(response))

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
        self.assertEqual(result["captured"][0]["options"]["muteHttpExceptions"], True)

    def test_schema_shape_is_stable(self):
        result = endpoint_result(valid_payload())
        self.assertTrue(result["ok"])
        response = result["result"]
        self.assertEqual(response["schema_version"], "presignal.historical_usdjpy_raw_observation.v1")
        self.assertEqual(list(response.keys()), [
            "schema_version", "request_identity", "instrument", "mode", "requested_provider", "requested_timestamp",
            "requested_window_start", "requested_window_end", "timezone", "provider_hierarchy_attempted",
            "provider_attempts", "selected_provider", "status", "missing_data_reason",
            "returned_observation_count", "observations", "response_generated_at",
        ])


if __name__ == "__main__":
    unittest.main()
