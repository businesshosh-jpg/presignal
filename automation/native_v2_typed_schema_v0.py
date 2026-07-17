"""Single machine-readable native-v2 provider-output schema and adapters."""
from __future__ import annotations

import hashlib
import json
import base64
from typing import Any, Dict, Mapping, Sequence

from automation.v2_layered_prediction_evaluation_v0 import (
    DIRECTIONS, FINAL_DIRECTIONS, INTERACTIONS, INTERACTION_STATUSES,
    PATH_BEHAVIORS, PATH_STAGE_TYPES, SECONDARY_REACTION_STATUSES, SECONDARY_STATUSES,
)


SCHEMA_ID = "presignal_native_v2_prediction_typed_output_v1"
PRIMARY_REACTION_BINDING_FIELD = "primary_reaction_binding"
PRIMARY_REACTION_TRANSPORT_SCHEMA_ID = "presignal_native_v2_primary_reaction_binding_transport_v1"
SECONDARY_REACTION_TRANSPORT_FIELD = "secondary_reaction"


def _enum(values: set[str]) -> Dict[str, Any]:
    return {"type": "string", "enum": sorted(values)}


def _number(*, minimum: float = 0) -> Dict[str, Any]:
    return {"type": "number", "minimum": minimum}


def _blank_or_number(*, minimum: float = 0) -> Dict[str, Any]:
    return {"anyOf": [_number(minimum=minimum), {"type": "string", "enum": [""]}]}


def _confidence(*, blank: bool = False) -> Dict[str, Any]:
    value: Dict[str, Any] = {"type": "number", "minimum": 0, "maximum": 1}
    return {"anyOf": [value, {"type": "string", "enum": [""]}]} if blank else value


def canonical_schema() -> Dict[str, Any]:
    """Return the immutable scientific payload shape; no provider owns a variant."""
    path_properties = {
        "path_stage_index": {"type": "integer", "minimum": 1},
        "path_stage_type": _enum(PATH_STAGE_TYPES),
        "path_target_type": _enum({"EVENT", "RELEASE_CLUSTER", "MARKET_SESSION"}),
        "path_target_id": {"type": "string", "minLength": 1},
        "path_target_name": {"type": "string", "minLength": 1},
        "expected_start_ts": {"type": "string", "minLength": 1},
        "expected_end_ts": {"type": "string", "minLength": 1},
        "expected_direction": _enum(DIRECTIONS),
        "expected_pips_min": _number(),
        "expected_pips_max": _number(),
        "expected_behavior": _enum(PATH_BEHAVIORS),
        "relationship_to_previous_stage": {"type": "string", "minLength": 1},
        "stage_confidence": _confidence(),
        "stage_explanation": {"type": "string", "minLength": 1},
    }
    properties = {
        "primary_driver_event_id": {"type": "string", "minLength": 1},
        "primary_driver_choice_confidence": _confidence(),
        "primary_driver_reason": {"type": "string", "minLength": 1},
        "secondary_driver_status": _enum(SECONDARY_STATUSES),
        "secondary_driver_event_id": {"type": "string"},
        "secondary_driver_choice_confidence": _confidence(blank=True),
        "secondary_driver_reason": {"type": "string"},
        "primary_reaction_target_type": _enum({"EVENT", "RELEASE_CLUSTER"}),
        "primary_reaction_target_id": {"type": "string", "minLength": 1},
        "primary_reaction_direction": _enum(DIRECTIONS),
        "primary_expected_pips_min": _number(), "primary_expected_pips_max": _number(),
        "primary_reaction_horizon_min": _number(minimum=0.01),
        "primary_reaction_confidence": _confidence(), "primary_reaction_thesis": {"type": "string", "minLength": 1},
        "secondary_reaction_status": _enum(SECONDARY_REACTION_STATUSES),
        "secondary_reaction_target_type": {"anyOf": [_enum({"EVENT", "RELEASE_CLUSTER"}), {"type": "string", "enum": [""]}]}, "secondary_reaction_target_id": {"type": "string"},
        "secondary_reaction_direction": _enum(DIRECTIONS),
        "secondary_expected_pips_min": _blank_or_number(), "secondary_expected_pips_max": _blank_or_number(),
        "secondary_reaction_horizon_min": _blank_or_number(minimum=0.01),
        "secondary_reaction_confidence": _confidence(blank=True), "secondary_reaction_thesis": {"type": "string"},
        "interaction_status": _enum(INTERACTION_STATUSES), "primary_secondary_interaction": _enum(INTERACTIONS),
        "interaction_confidence": _confidence(blank=True), "interaction_explanation": {"type": "string", "minLength": 1},
        "session_forecast_direction": _enum(FINAL_DIRECTIONS),
        "session_expected_pips_min": _number(), "session_expected_pips_max": _number(),
        "session_confidence": _confidence(), "session_expected_holding_min": _number(minimum=0.01),
        "session_path_summary": {"type": "string", "minLength": 1}, "session_thesis": {"type": "string", "minLength": 1},
        "causal_chain": {"type": "string", "minLength": 1}, "invalidation_condition": {"type": "string", "minLength": 1},
        "no_signal_flag": {"type": "boolean"}, "no_signal_reason": {"type": "string"},
        "information_used": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "missing_information": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "prediction_path": {"type": "array", "minItems": 2, "maxItems": 4, "items": {"type": "object", "additionalProperties": False, "required": list(path_properties), "properties": path_properties}},
    }
    # Cross-field constraints are deliberately enforced by the frozen native
    # v2 validator after typed schema validation.  OpenAI strict response
    # schemas prohibit root-level composition keywords, so keeping those
    # checks in that deterministic validation layer is the portable route.
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": SCHEMA_ID, "type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


def canonical_schema_fingerprint() -> str:
    return hashlib.sha256(json.dumps(canonical_schema(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def _binding_encode(record: Mapping[str, str]) -> str:
    """Use canonical stable IDs, not display text, in a reversible scalar enum."""
    payload = json.dumps(dict(record), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "pb1:" + base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _binding_decode(value: Any) -> Dict[str, str]:
    if not isinstance(value, str) or not value.startswith("pb1:"):
        raise ValueError("PRIMARY_REACTION_BINDING_MALFORMED")
    encoded = value[4:]
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        decoded = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("PRIMARY_REACTION_BINDING_MALFORMED") from exc
    expected = {"driver_event_id", "reaction_target_id", "reaction_target_type"}
    if not isinstance(decoded, dict) or set(decoded) != expected or not all(isinstance(decoded[key], str) for key in expected):
        raise ValueError("PRIMARY_REACTION_BINDING_MALFORMED")
    return {key: decoded[key] for key in sorted(expected)}


def validator_approved_primary_reaction_combinations(session_id: str, members: Sequence[Mapping[str, Any]]) -> list[Dict[str, str]]:
    """Enumerate exactly the primary pairs accepted by the frozen v2 rules."""
    from automation.v2_layered_prediction_evaluation_v0 import normalize_session_members

    normalized = normalize_session_members(session_id, members)
    cluster_sizes: Dict[str, int] = {}
    for member in normalized:
        cluster_id = str(member["release_cluster_id"])
        cluster_sizes[cluster_id] = cluster_sizes.get(cluster_id, 0) + 1
    combinations: list[Dict[str, str]] = []
    for member in normalized:
        event_id, cluster_id = str(member["event_id"]), str(member["release_cluster_id"])
        # This mirrors v2_layered_prediction_evaluation_v0: a clustered event
        # requires its release cluster; a singleton allows either frozen type.
        target_types = ("RELEASE_CLUSTER",) if cluster_sizes[cluster_id] > 1 else ("EVENT", "RELEASE_CLUSTER")
        for target_type in target_types:
            combinations.append({
                "driver_event_id": event_id,
                "reaction_target_type": target_type,
                "reaction_target_id": event_id if target_type == "EVENT" else cluster_id,
            })
    return sorted(combinations, key=lambda row: (row["driver_event_id"], row["reaction_target_type"], row["reaction_target_id"]))


def primary_reaction_binding_set(session_id: str, members: Sequence[Mapping[str, Any]]) -> list[Dict[str, str]]:
    """Return the complete, collision-free transport representation of that set."""
    return [
        {**record, "binding": _binding_encode(record)}
        for record in validator_approved_primary_reaction_combinations(session_id, members)
    ]


def primary_reaction_binding_fingerprint(session_id: str, members: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(primary_reaction_binding_set(session_id, members), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _primary_reaction_transport_schema(session_id: str, members: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Make a non-scientific provider transport envelope from canonical schema."""
    schema = _copy(canonical_schema())
    properties = schema["properties"]
    for field in ("primary_driver_event_id", "primary_reaction_target_type", "primary_reaction_target_id"):
        properties.pop(field)
        schema["required"].remove(field)
    options = primary_reaction_binding_set(session_id, members)
    properties[PRIMARY_REACTION_BINDING_FIELD] = {
        "type": "string",
        "enum": [row["binding"] for row in options],
    }
    schema["required"].append(PRIMARY_REACTION_BINDING_FIELD)
    schema["$id"] = PRIMARY_REACTION_TRANSPORT_SCHEMA_ID
    return schema


def _secondary_reaction_transport_schema(session_id: str, members: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Encode the frozen secondary conditional fields as two typed branches.

    The provider chooses either a complete predicted reaction or one of the
    existing no-separate-reaction statuses.  This is strictly a transport
    representation: the canonical persisted fields and their validator do
    not change.
    """
    schema = _primary_reaction_transport_schema(session_id, members)
    properties = schema["properties"]
    canonical_fields = (
        "secondary_reaction_status", "secondary_reaction_target_type",
        "secondary_reaction_target_id", "secondary_reaction_direction",
        "secondary_expected_pips_min", "secondary_expected_pips_max",
        "secondary_reaction_horizon_min", "secondary_reaction_confidence",
        "secondary_reaction_thesis",
    )
    for field in canonical_fields:
        properties.pop(field)
        schema["required"].remove(field)
    no_reaction_statuses = sorted(SECONDARY_REACTION_STATUSES - {"PREDICTED"})
    no_reaction = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status"],
        "properties": {"status": _enum(set(no_reaction_statuses))},
    }
    predicted = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status", "target_type", "target_id", "direction",
            "expected_pips_min", "expected_pips_max", "horizon_min",
            "confidence", "thesis",
        ],
        "properties": {
            "status": {"type": "string", "enum": ["PREDICTED"]},
            "target_type": _enum({"EVENT", "RELEASE_CLUSTER"}),
            "target_id": {"type": "string", "minLength": 1},
            "direction": _enum(DIRECTIONS),
            "expected_pips_min": _number(),
            "expected_pips_max": _number(),
            "horizon_min": _number(minimum=0.01),
            "confidence": _confidence(),
            "thesis": {"type": "string"},
        },
    }
    properties[SECONDARY_REACTION_TRANSPORT_FIELD] = {
        "anyOf": [no_reaction, predicted],
    }
    schema["required"].append(SECONDARY_REACTION_TRANSPORT_FIELD)
    return schema


def transport_adapter_schema(provider: str, session_id: str, members: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Provider schema derived from one canonical schema plus frozen session pairs."""
    if provider not in {"OpenAI", "Gemini", "Anthropic"}:
        raise ValueError("UNKNOWN_TYPED_SCHEMA_PROVIDER:" + provider)
    return _provider_schema(_secondary_reaction_transport_schema(session_id, members), provider=provider)


def transport_adapter_schema_fingerprint(provider: str, session_id: str, members: Sequence[Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(transport_adapter_schema(provider, session_id, members), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def decode_primary_reaction_transport(payload: Mapping[str, Any], session_id: str, members: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Decode exact provider-selected transport branches without repair."""
    if not isinstance(payload, Mapping):
        raise ValueError("PRIMARY_REACTION_TRANSPORT_NOT_OBJECT")
    _validate(payload, _secondary_reaction_transport_schema(session_id, members), "transport")
    selected = _binding_decode(payload.get(PRIMARY_REACTION_BINDING_FIELD))
    allowed = {row["binding"]: row for row in primary_reaction_binding_set(session_id, members)}
    binding = str(payload[PRIMARY_REACTION_BINDING_FIELD])
    if binding not in allowed or selected != {key: allowed[binding][key] for key in selected}:
        raise ValueError("PRIMARY_REACTION_BINDING_NOT_ALLOWED")
    decoded = dict(payload)
    decoded.pop(PRIMARY_REACTION_BINDING_FIELD)
    decoded.update({
        "primary_driver_event_id": selected["driver_event_id"],
        "primary_reaction_target_type": selected["reaction_target_type"],
        "primary_reaction_target_id": selected["reaction_target_id"],
    })
    secondary = payload.get(SECONDARY_REACTION_TRANSPORT_FIELD)
    if not isinstance(secondary, Mapping):
        raise ValueError("SECONDARY_REACTION_TRANSPORT_NOT_OBJECT")
    status = str(secondary.get("status") or "")
    if status == "PREDICTED":
        decoded.update({
            "secondary_reaction_status": status,
            "secondary_reaction_target_type": secondary["target_type"],
            "secondary_reaction_target_id": secondary["target_id"],
            "secondary_reaction_direction": secondary["direction"],
            "secondary_expected_pips_min": secondary["expected_pips_min"],
            "secondary_expected_pips_max": secondary["expected_pips_max"],
            "secondary_reaction_horizon_min": secondary["horizon_min"],
            "secondary_reaction_confidence": secondary["confidence"],
            "secondary_reaction_thesis": secondary["thesis"],
        })
    else:
        # These dependent canonical values are not provider choices in the
        # no-reaction branch; they are the frozen blank/not-applicable form.
        decoded.update({
            "secondary_reaction_status": status,
            "secondary_reaction_target_type": "",
            "secondary_reaction_target_id": "",
            "secondary_reaction_direction": "NOT_PREDICTED",
            "secondary_expected_pips_min": "",
            "secondary_expected_pips_max": "",
            "secondary_reaction_horizon_min": "",
            "secondary_reaction_confidence": "",
            "secondary_reaction_thesis": "",
        })
    decoded.pop(SECONDARY_REACTION_TRANSPORT_FIELD)
    validate_canonical_payload(decoded)
    return decoded


def _provider_schema(value: Any, *, provider: str) -> Any:
    """Derive a transport schema without creating a second scientific schema.

    The canonical schema remains the acceptance contract. Some provider
    structured-output dialects reject JSON-Schema meta/constraint keywords
    they cannot enforce; those keys are omitted only from their transport
    wrapper and remain enforced by ``validate_canonical_payload``.
    """
    if isinstance(value, list):
        return [_provider_schema(item, provider=provider) for item in value]
    if not isinstance(value, dict):
        return value
    unsupported = {"$schema", "$id"}
    if provider in {"OpenAI", "Gemini"}:
        # Keep types, scalar enums, required fields, exact object shape, and
        # path cardinality in the native wrapper. Scalar constraints remain
        # deterministic post-schema checks when the endpoint does not expose
        # them in its documented structured-output subset.
        unsupported.update({"minLength", "minimum", "maximum"})
    if provider == "Gemini":
        # Gemini's response-schema dialect does not accept this JSON-Schema
        # keyword. The canonical post-schema validator still rejects unknown
        # properties before persistence.
        unsupported.add("additionalProperties")
    out = {
        key: _provider_schema(item, provider=provider)
        for key, item in value.items() if key not in unsupported
    }
    if provider == "Gemini" and isinstance(out.get("type"), str):
        out["type"] = out["type"].upper()
    if "path_stage_index" in out and isinstance(out["path_stage_index"], dict):
        # The path itself is bounded to four rows. An explicit finite enum is
        # equivalent to integer >= 1 in that bounded domain and is supported
        # by all three native structured-output transports.
        out["path_stage_index"] = {"type": "INTEGER" if provider == "Gemini" else "integer"}
        if provider != "Gemini":
            out["path_stage_index"]["enum"] = [1, 2, 3, 4]
    return out


def _validate(value: Any, schema: Mapping[str, Any], path: str) -> None:
    for candidate in schema.get("allOf") or []:
        _validate(value, candidate, path)
    kind = schema.get("type")
    # JSON Schema condition branches may constrain ``properties`` without
    # repeating ``type: object``.  Treat those branches as object schemas so
    # the canonical cross-field constraints are actually enforced locally.
    if kind == "object" or "properties" in schema:
        if not isinstance(value, Mapping): raise ValueError("CANONICAL_SCHEMA_TYPE:" + path + ":object")
        required = set(schema.get("required") or [])
        missing = sorted(required - set(value))
        if missing: raise ValueError("CANONICAL_SCHEMA_REQUIRED:" + path + ":" + missing[0])
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set((schema.get("properties") or {})))
            if extra: raise ValueError("CANONICAL_SCHEMA_ADDITIONAL_PROPERTY:" + path + ":" + extra[0])
        for key, child in (schema.get("properties") or {}).items():
            # Conditional branches may constrain a subset of fields while the
            # enclosing schema owns required-field enforcement.
            if key in value:
                _validate(value[key], child, path + "." + key)
    elif kind == "array":
        if not isinstance(value, list): raise ValueError("CANONICAL_SCHEMA_TYPE:" + path + ":array")
        if len(value) < int(schema.get("minItems", 0)): raise ValueError("CANONICAL_SCHEMA_MIN_ITEMS:" + path)
        if "maxItems" in schema and len(value) > int(schema["maxItems"]): raise ValueError("CANONICAL_SCHEMA_MAX_ITEMS:" + path)
        for index, child in enumerate(value): _validate(child, schema["items"], path + "[" + str(index) + "]")
    elif kind == "string":
        if not isinstance(value, str): raise ValueError("CANONICAL_SCHEMA_TYPE:" + path + ":string")
        if len(value) < int(schema.get("minLength", 0)): raise ValueError("CANONICAL_SCHEMA_MIN_LENGTH:" + path)
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)): raise ValueError("CANONICAL_SCHEMA_TYPE:" + path + ":number")
        if value < schema.get("minimum", float("-inf")): raise ValueError("CANONICAL_SCHEMA_MINIMUM:" + path)
        if value > schema.get("maximum", float("inf")): raise ValueError("CANONICAL_SCHEMA_MAXIMUM:" + path)
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int): raise ValueError("CANONICAL_SCHEMA_TYPE:" + path + ":integer")
        if value < schema.get("minimum", float("-inf")): raise ValueError("CANONICAL_SCHEMA_MINIMUM:" + path)
    elif kind == "boolean" and not isinstance(value, bool): raise ValueError("CANONICAL_SCHEMA_TYPE:" + path + ":boolean")
    if "enum" in schema and value not in schema["enum"]: raise ValueError("CANONICAL_SCHEMA_ENUM:" + path)
    # Validate base constraints first.  Root-level conditional branches are
    # intentionally complete closed objects for provider compatibility, so
    # checking them first would mask a more precise base-schema error.
    if "anyOf" in schema:
        for candidate in schema["anyOf"]:
            try:
                _validate(value, candidate, path)
                break
            except ValueError:
                continue
        else:
            raise ValueError("CANONICAL_SCHEMA_ANY_OF_FAILED:" + path)


def validate_canonical_payload(payload: Mapping[str, Any]) -> None:
    _validate(payload, canonical_schema(), "prediction")


def adapter_schema(provider: str) -> Dict[str, Any]:
    """Return the deterministic provider transport view of the canonical schema."""
    if provider not in {"OpenAI", "Gemini", "Anthropic"}:
        raise ValueError("UNKNOWN_TYPED_SCHEMA_PROVIDER:" + provider)
    return _provider_schema(_copy(canonical_schema()), provider=provider)


def adapter_schema_fingerprint(provider: str) -> str:
    return hashlib.sha256(
        json.dumps(adapter_schema(provider), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
