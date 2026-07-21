"""R3 compat-r3 contract: final representation-only live compatibility repair."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as r2

CONTRACT_VERSION = "presignal_event_path_contract_v1_historical_verification_r3_compat_r3"
PARENT_CONTRACT_VERSION = r2.CONTRACT_VERSION
ANTHROPIC_ATTENTION_MAX_TOKENS = r2.ANTHROPIC_ATTENTION_MAX_TOKENS

PIP_REPRESENTATION_RULE = (
    "Direction carries the sign. For both UP and DOWN, expected_pips_min and "
    "expected_pips_max are nonnegative absolute pip magnitudes and must satisfy "
    "0 <= expected_pips_min <= expected_pips_max. Do not use negative pip values "
    "for DOWN. For FLAT, both values are 0. Valid DOWN example: "
    '{"direction":"DOWN","expected_pips_min":5,"expected_pips_max":15}.'
)

REQUEST_CATEGORY_RULE = (
    "information_category must be exactly one of "
    "(treasury_yields|fed_expectations|dxy|usdjpy_trend|risk_sentiment|equity_tone|"
    "inflation_narrative|labor_market_trend|growth_context|market_positioning|"
    "upcoming_larger_events|jpy_intervention_risk|volatility|historical_surprise_sensitivity|"
    "event_consensus_detail|other). Use information_category=other when no listed "
    "category applies. Do not use information_category=unknown."
)

PROMPT_RULES = {
    **r2.PROMPT_RULES,
    "pip_representation": PIP_REPRESENTATION_RULE,
    "gemini_pips": PIP_REPRESENTATION_RULE,
    "request_unknown_category": REQUEST_CATEGORY_RULE,
}

NORMALIZATION = {
    "affected_channel": r2.NORMALIZATION,
    "information_category": {
        "field": "information_category",
        "input": "unknown",
        "output": "other",
        "case_sensitive": True,
        "reason": "The existing canonical category enum identifies other as its generic fallback; exact lowercase unknown adds no distinct Request category.",
    },
    "anthropic_attention_identity": {
        "raw_provider": "presignal_v2",
        "raw_model": None,
        "canonical_provider": "Anthropic",
        "canonical_model": "claude-haiku-4-5",
        "reason": "The R6 raw fenced JSON used this exact internal task label while bridge metadata proved the manifest-bound Anthropic route and model.",
    },
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def spec() -> dict[str, Any]:
    inherited = r2.spec()
    base = {
        "contract_version": CONTRACT_VERSION,
        "parent_contract_version": PARENT_CONTRACT_VERSION,
        "scope": "HISTORICAL_VERIFICATION_ONLY",
        "prompt_rules": PROMPT_RULES,
        "schema_fingerprint": inherited["schema_fingerprint"],
        "parser_fingerprint": fingerprint({"parent": inherited["parser_fingerprint"], "anthropic_identity": NORMALIZATION["anthropic_attention_identity"]}),
        "validator_fingerprint": inherited["validator_fingerprint"],
        "prompt_template_fingerprint": fingerprint(PROMPT_RULES),
        "generation_settings_fingerprint": inherited["generation_settings_fingerprint"],
        "normalization_fingerprint": fingerprint(NORMALIZATION),
    }
    base["contract_fingerprint"] = fingerprint(base)
    return base


def extract_json_object(raw: Any) -> dict[str, Any]:
    return r2.extract_json_object(raw)
