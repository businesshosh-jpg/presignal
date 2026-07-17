from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SimplifiedAuthoritativeReplayBridgeTest(unittest.TestCase):
    def test_frozen_openai_model_is_dispatched_exactly(self):
        bridge = (ROOT / "apps_script" / "authoritative_provider_bridge.js").read_text()
        self.assertIn("prov.model = requestedModel", bridge)
        self.assertIn("actualModel !== requestedModel", bridge)

    def test_anthropic_reduced_json_route_has_capacity_cache_and_telemetry(self):
        source = (ROOT / "apps_script" / "prediction_runner.js").read_text()
        start = source.index("function _callClaudeJsonObject_")
        body = source[start:source.index("function _strictParseJsonObject_", start)]
        self.assertIn("max_tokens: 4096", body)
        self.assertIn("cache_control", body)
        self.assertIn("stop_reason", body)


if __name__ == "__main__":
    unittest.main()
