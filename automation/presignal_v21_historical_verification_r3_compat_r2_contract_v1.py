"""R3 compat-r2 contract: bounded transport compatibility only."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from automation import presignal_v21_historical_verification_r3_compat_r1_contract_v1 as r1

CONTRACT_VERSION = "presignal_event_path_contract_v1_historical_verification_r3_compat_r2"
PARENT_CONTRACT_VERSION = r1.CONTRACT_VERSION
ANTHROPIC_ATTENTION_MAX_TOKENS = 8192
REQUEST_ENUM_RULE = r1.REQUEST_ENUM_RULE

REQUEST_PRIORITY_RULE = (
    "Request priority is separate from Attention classification. priority must be exactly one of "
    "(must_have|useful|optional|low_value). Never use Attention labels in priority, including "
    "PRIMARY_DRIVER, SECONDARY_DRIVER, WATCHLIST, CONTEXT_ONLY, IGNORE, NO_SIGNAL, "
    "primary_driver, or secondary_driver. Use affected_channel=unknown when no listed market "
    "channel applies. Valid example: {\"information_category\":\"fed_expectations\","
    "\"priority\":\"must_have\",\"affected_channel\":\"fed_path\"}."
)

OTHER_CHANNEL_RULE = (
    "affected_channel=other is not a valid output token. Use affected_channel=unknown for an "
    "otherwise unspecified market channel."
)

PROMPT_RULES = {
    **r1.PROMPT_RULES,
    "request_priority_separation": REQUEST_PRIORITY_RULE,
    "request_unknown_channel": OTHER_CHANNEL_RULE,
}

NORMALIZATION = {
    "field": "affected_channel",
    "input": "other",
    "output": "unknown",
    "case_sensitive": True,
    "reason": "The existing schema identifies unknown as the sole generic channel fallback; exact lowercase other carries no additional channel meaning.",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def spec() -> dict[str, Any]:
    inherited = r1.spec()
    base = {
        "contract_version": CONTRACT_VERSION,
        "parent_contract_version": PARENT_CONTRACT_VERSION,
        "scope": "HISTORICAL_VERIFICATION_ONLY",
        "prompt_rules": PROMPT_RULES,
        "schema_fingerprint": inherited["schema_fingerprint"],
        "parser_fingerprint": inherited["parser_fingerprint"],
        "validator_fingerprint": inherited["validator_fingerprint"],
        "prompt_template_fingerprint": fingerprint(PROMPT_RULES),
        "generation_settings_fingerprint": fingerprint({
            "anthropic_attention_max_tokens": ANTHROPIC_ATTENTION_MAX_TOKENS,
            "anthropic_attention_raw_before_parse": True,
            "other_stages": "existing_bridge_default",
        }),
        "normalization_fingerprint": fingerprint(NORMALIZATION),
    }
    base["contract_fingerprint"] = fingerprint(base)
    return base


def extract_json_object(raw: Any) -> dict[str, Any]:
    return r1.extract_json_object(raw)
