"""R3 compatibility-only child contract for live historical verification."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from automation import presignal_v21_historical_verification_r3_contract_v1 as r3
from automation import presignal_v21_prospective_flat_contract_v1 as flat

CONTRACT_VERSION = "presignal_event_path_contract_v1_historical_verification_r3_compat_r1"
PARENT_CONTRACT_VERSION = r3.CONTRACT_VERSION

ANTHROPIC_ATTENTION_RULE = (
    "Use compact JSON values so every supplied event fits in one response: "
    "attention_reason must contain at most six words; expected_market_channel and "
    "driver_role must be concise labels; session_attention_summary must be a compact count summary. "
    "Return only the required object and required fields."
)

REQUEST_ENUM_RULE = (
    "Use these exact enum tokens, with lowercase spelling and underscores: "
    "information_category=(treasury_yields|fed_expectations|dxy|usdjpy_trend|risk_sentiment|equity_tone|"
    "inflation_narrative|labor_market_trend|growth_context|market_positioning|upcoming_larger_events|"
    "jpy_intervention_risk|volatility|historical_surprise_sensitivity|event_consensus_detail|other); "
    "priority=(must_have|useful|optional|low_value); "
    "affected_channel=(fed_path|treasury_yields|usd_direction|jpy_direction|risk_sentiment|"
    "inflation_expectations|labor_market|growth_outlook|market_positioning|event_importance|"
    "low_direct_market_impact|unknown). "
    "For example: {\"information_category\":\"fed_expectations\",\"priority\":\"must_have\","
    "\"affected_channel\":\"fed_path\"}. Do not use semantic aliases."
)

PROMPT_RULES = {
    **r3.PROMPT_RULES,
    "anthropic_attention_concise": ANTHROPIC_ATTENTION_RULE,
    "request_canonical_enums": REQUEST_ENUM_RULE,
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def spec() -> dict[str, Any]:
    inherited = flat.fingerprints()
    prompt_fingerprint = fingerprint(PROMPT_RULES)
    base = {
        "contract_version": CONTRACT_VERSION,
        "parent_contract_version": PARENT_CONTRACT_VERSION,
        "scope": "HISTORICAL_VERIFICATION_ONLY",
        "prompt_rules": PROMPT_RULES,
        **inherited,
        "prompt_template_fingerprint": prompt_fingerprint,
        "generation_settings_fingerprint": fingerprint({"anthropic_max_tokens": 4096, "temperature": "existing_bridge_default"}),
    }
    base["contract_fingerprint"] = fingerprint(base)
    return base


def extract_json_object(raw: Any) -> dict[str, Any]:
    return r3.extract_json_object(raw)
