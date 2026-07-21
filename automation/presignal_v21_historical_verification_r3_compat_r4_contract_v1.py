"""R3 compat-r4 contract: final bounded provider-coverage repair."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from automation import presignal_v21_historical_verification_r3_compat_r3_contract_v1 as r3

CONTRACT_VERSION = "presignal_event_path_contract_v1_historical_verification_r3_compat_r4"
PARENT_CONTRACT_VERSION = r3.CONTRACT_VERSION
ANTHROPIC_ATTENTION_MAX_TOKENS = r3.ANTHROPIC_ATTENTION_MAX_TOKENS

REQUEST_HOUSING_RULE = (
    "Use exactly one listed information_category and do not invent more specific category names. "
    "For housing-market information use information_category=other, because other is the existing "
    "canonical generic fallback. If no listed category applies, use other. Valid example: "
    '{"information_category":"other","priority":"useful","affected_channel":"growth_outlook"}.'
)

PROMPT_RULES = {
    **r3.PROMPT_RULES,
    "request_housing_category": REQUEST_HOUSING_RULE,
}

NORMALIZATION = {
    **r3.NORMALIZATION,
    "information_category_housing": {
        "field": "information_category",
        "input": "housing_market_trend",
        "output": "other",
        "case_sensitive": True,
        "reason": "The frozen canonical Request category enum has no housing-specific value, and preserved historical housing Requests use other as the generic category fallback.",
    },
    "anthropic_runtime_identity": {
        "runtime_provider": "Anthropic",
        "runtime_model": "claude-haiku-4-5",
        "accepted_emitted_provider_identities": [None, "Anthropic", "presignal_v2", "presignal_v2_shadow_research"],
        "accepted_emitted_model_identities": [None, "claude-haiku-4-5"],
        "reason": "Provider/model identity is owned by the manifest-bound route and bridge metadata; accepted emitted labels are exact application/workflow audit values observed in frozen smoke evidence.",
    },
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def spec() -> dict[str, Any]:
    inherited = r3.spec()
    base = {
        "contract_version": CONTRACT_VERSION,
        "parent_contract_version": PARENT_CONTRACT_VERSION,
        "scope": "HISTORICAL_VERIFICATION_ONLY",
        "prompt_rules": PROMPT_RULES,
        "schema_fingerprint": inherited["schema_fingerprint"],
        "parser_fingerprint": fingerprint({"parent": inherited["parser_fingerprint"], "anthropic_runtime_identity": NORMALIZATION["anthropic_runtime_identity"]}),
        "validator_fingerprint": inherited["validator_fingerprint"],
        "prompt_template_fingerprint": fingerprint(PROMPT_RULES),
        "generation_settings_fingerprint": inherited["generation_settings_fingerprint"],
        "normalization_fingerprint": fingerprint(NORMALIZATION),
    }
    base["contract_fingerprint"] = fingerprint(base)
    return base


def extract_json_object(raw: Any) -> dict[str, Any]:
    return r3.extract_json_object(raw)
