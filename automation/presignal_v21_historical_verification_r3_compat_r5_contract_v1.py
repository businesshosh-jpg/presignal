"""R3 compat-r5 contract: strict Attention-rank and raw Request boundaries."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from automation import presignal_v21_historical_verification_r3_compat_r4_contract_v1 as r4

CONTRACT_VERSION = "presignal_event_path_contract_v1_historical_verification_r3_compat_r5"
PARENT_CONTRACT_VERSION = r4.CONTRACT_VERSION
PROMPT_RULES = r4.PROMPT_RULES

ATTENTION_RANK_RULE = {
    "field": "attention_rank",
    "type": "integer",
    "minimum": 0,
    "required": True,
    "error": "INVALID_ATTENTION_RANK",
    "reason": "Attention rank is deterministic ordering metadata and must be validated before any Request or forecast construction.",
}

ANTHROPIC_REQUEST_RAW_BOUNDARY = {
    "provider": "Anthropic",
    "stage": "REQUEST",
    "raw_response_before_parse": True,
    "strict_parse_failure": True,
    "reason": "Preserve the provider HTTP body and parse metadata before rejecting an undecodable bridge envelope.",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def spec() -> dict[str, Any]:
    inherited = r4.spec()
    base = {
        "contract_version": CONTRACT_VERSION,
        "parent_contract_version": PARENT_CONTRACT_VERSION,
        "scope": "HISTORICAL_VERIFICATION_ONLY",
        "prompt_rules": inherited["prompt_rules"],
        "schema_fingerprint": inherited["schema_fingerprint"],
        "parser_fingerprint": fingerprint({"parent": inherited["parser_fingerprint"], "anthropic_request_raw_boundary": ANTHROPIC_REQUEST_RAW_BOUNDARY}),
        "validator_fingerprint": fingerprint({"parent": inherited["validator_fingerprint"], "attention_rank": ATTENTION_RANK_RULE}),
        "prompt_template_fingerprint": inherited["prompt_template_fingerprint"],
        "generation_settings_fingerprint": inherited["generation_settings_fingerprint"],
        "normalization_fingerprint": inherited["normalization_fingerprint"],
    }
    base["contract_fingerprint"] = fingerprint(base)
    return base


def extract_json_object(raw: Any) -> dict[str, Any]:
    return r4.extract_json_object(raw)
