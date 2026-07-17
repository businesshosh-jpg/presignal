"""Minimal provider contract for the restarted authoritative replay canary.

This module deliberately owns no provider-specific scientific schema.  It
validates one reduced cross-provider object and deterministically resolves
provider-selected driver tokens to frozen session members.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence


DIRECTIONS = {"UP", "DOWN", "FLAT", "NO_CLEAR_DIRECTION"}
STRENGTHS = {"WEAK", "MODERATE", "STRONG"}
REDUCED_FIELD_ORDER = (
    "primary_driver_token", "secondary_driver_token", "final_usdjpy_direction",
    "reaction_strength", "confidence", "primary_thesis", "secondary_thesis",
    "reasoning_steps",
)
REQUIRED = set(REDUCED_FIELD_ORDER)


class ReducedForecastError(ValueError):
    pass


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def parse_reduced_output_json(raw_output: Any) -> tuple[Any, dict[str, Any]]:
    """Parse strict JSON, allowing one complete outer Markdown code fence only."""
    if not isinstance(raw_output, str):
        raise json.JSONDecodeError("REDUCED_OUTPUT_NOT_TEXT", str(raw_output), 0)
    text = raw_output.strip()
    if text.startswith("```"):
        match = re.fullmatch(r"```(?P<language>json)?[ \t]*\r?\n(?P<body>.*)\r?\n```", text, re.DOTALL)
        if not match or "```" in match.group("body"):
            raise json.JSONDecodeError("OUTER_MARKDOWN_FENCE_INVALID", raw_output, 0)
        return json.loads(match.group("body")), {
            "output_normalization": "single_outer_markdown_fence_removed",
            "fence_language": match.group("language") or "",
        }
    return json.loads(text), {"output_normalization": "none"}


def driver_options(members: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Create stable, collision-resistant provider tokens from frozen IDs."""
    options = []
    for row in sorted(members, key=lambda item: str(item["event_id"])):
        event_id = str(row["event_id"])
        token = "DRV_" + hashlib.sha256(event_id.encode()).hexdigest()[:20]
        options.append({"token": token, "event_id": event_id, "label": str(row.get("indicator_name") or "")})
    if len({row["token"] for row in options}) != len(options):
        raise ReducedForecastError("DRIVER_TOKEN_COLLISION")
    return options


def reduced_output_response_schema(members: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build a provider schema from the same frozen contract used by validation."""
    tokens = [option["token"] for option in driver_options(members)]
    if not tokens:
        raise ReducedForecastError("DRIVER_TOKEN_ENUM_EMPTY")
    return {
        "type": "object",
        "properties": {
            "primary_driver_token": {"type": "string", "enum": tokens},
            "secondary_driver_token": {
                "anyOf": [
                    {"type": "string", "enum": tokens},
                    {"type": "null"},
                ],
            },
            "final_usdjpy_direction": {"type": "string", "enum": sorted(DIRECTIONS)},
            "reaction_strength": {"type": "string", "enum": sorted(STRENGTHS)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "primary_thesis": {"type": "string"},
            "secondary_thesis": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
            },
            "reasoning_steps": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 4,
            },
        },
        "required": list(REDUCED_FIELD_ORDER),
        "additionalProperties": False,
        "propertyOrdering": list(REDUCED_FIELD_ORDER),
    }


def canonical_event_identity(member: Mapping[str, Any]) -> str:
    """Deterministic upstream ID from immutable source-member content."""
    keys = ("session_id", "batch_id", "country", "indicator_name", "genre", "importance",
            "consensus_value", "prev_revision", "release_ts", "same_minute_group_key",
            "member_order", "source_sheet", "type")
    return "EID_" + hashlib.sha256(_canon({key: member.get(key) for key in keys}).encode()).hexdigest()[:24]


def require_unique_event_identities(members: Sequence[Mapping[str, Any]]) -> None:
    ids = [str(row.get("event_id") or "") for row in members]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ReducedForecastError("DUPLICATE_OR_MISSING_EVENT_IDENTITY")


def validate_and_resolve(payload: Mapping[str, Any], members: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReducedForecastError("FORECAST_NOT_OBJECT")
    extra = set(payload) - REQUIRED
    missing = REQUIRED - set(payload)
    if extra:
        raise ReducedForecastError("UNKNOWN_FIELD:" + sorted(extra)[0])
    if missing:
        raise ReducedForecastError("MISSING_FIELD:" + sorted(missing)[0])
    options = {row["token"]: row["event_id"] for row in driver_options(members)}
    primary = payload["primary_driver_token"]
    secondary = payload["secondary_driver_token"]
    if not isinstance(primary, str) or primary not in options:
        raise ReducedForecastError("PRIMARY_DRIVER_TOKEN_INVALID")
    if secondary is not None and (not isinstance(secondary, str) or secondary not in options or secondary == primary):
        raise ReducedForecastError("SECONDARY_DRIVER_TOKEN_INVALID")
    if payload["final_usdjpy_direction"] not in DIRECTIONS:
        raise ReducedForecastError("FINAL_DIRECTION_INVALID")
    if payload["reaction_strength"] not in STRENGTHS:
        raise ReducedForecastError("REACTION_STRENGTH_INVALID")
    if isinstance(payload["confidence"], bool) or not isinstance(payload["confidence"], (int, float)) or not 0 <= payload["confidence"] <= 1:
        raise ReducedForecastError("CONFIDENCE_INVALID")
    if not isinstance(payload["primary_thesis"], str) or not payload["primary_thesis"].strip():
        raise ReducedForecastError("PRIMARY_THESIS_INVALID")
    if secondary is None and payload["secondary_thesis"] not in (None, ""):
        raise ReducedForecastError("SECONDARY_THESIS_WITHOUT_DRIVER")
    if secondary is not None and (not isinstance(payload["secondary_thesis"], str) or not payload["secondary_thesis"].strip()):
        raise ReducedForecastError("SECONDARY_THESIS_INVALID")
    steps = payload["reasoning_steps"]
    if not isinstance(steps, list) or not 2 <= len(steps) <= 4 or any(not isinstance(step, str) or not step.strip() for step in steps):
        raise ReducedForecastError("REASONING_STEPS_INVALID")
    return {
        "primary_driver_event_id": options[primary],
        "secondary_driver_event_id": options.get(secondary, "") if secondary is not None else "",
        "final_usdjpy_direction": payload["final_usdjpy_direction"],
        "reaction_strength": payload["reaction_strength"],
        "confidence": float(payload["confidence"]),
        "primary_thesis": payload["primary_thesis"],
        "secondary_thesis": payload["secondary_thesis"] or "",
        "reasoning_steps": list(steps),
    }
