/**
 * Isolated bridge for the package-bound authoritative historical replay.
 * It deliberately reuses the project's established provider resolver and raw
 * JSON callers, while refusing any model that does not equal the frozen model.
 */
function apiCallAuthoritativeProviderJsonObject_(params) {
  params = params || {};
  var providerName = _normalizeProviderName_(params.provider);
  var requestedModel = String(params.model || '').trim();
  var requestSchemaVersion = String(params.request_schema_version || '').trim();
  var hardTimeoutSeconds = Number(params.hard_timeout_seconds || 0);
  var authoritativeRunId = String(params.authoritative_run_id || '').trim();
  var forecastIdentity = String(params.forecast_identity || '').trim();
  var sessionId = String(params.session_id || '').trim();
  var arm = String(params.arm || '').trim();
  var prompt = params.prompt || {};
  var responseSchema = null;
  if (!providerName || !requestedModel || !authoritativeRunId || !forecastIdentity || !sessionId || !arm) {
    throw new Error('apiCallAuthoritativeProviderJsonObject requires frozen execution identity metadata.');
  }
  if (requestSchemaVersion !== 'authoritative_historical_replay_bridge_v1') {
    throw new Error('apiCallAuthoritativeProviderJsonObject received unsupported request_schema_version.');
  }
  if (!isFinite(hardTimeoutSeconds) || hardTimeoutSeconds <= 0) {
    throw new Error('apiCallAuthoritativeProviderJsonObject requires positive hard_timeout_seconds.');
  }
  if (params.response_schema !== undefined && params.response_schema !== null) {
    responseSchema = _validateAuthoritativeReducedResponseSchema_(params.response_schema, prompt.user);
  }
  var startedAt = new Date().toISOString();
  var metadata = {
    requested_provider: providerName,
    requested_model: requestedModel,
    authoritative_run_id: authoritativeRunId,
    forecast_identity: forecastIdentity,
    session_id: sessionId,
    arm: arm,
    hard_timeout_seconds: hardTimeoutSeconds,
    request_schema_version: requestSchemaVersion,
    started_timestamp: startedAt
  };
  var resolved = _resolveProviders_([providerName]);
  if (!resolved || !resolved.length) {
    return _authoritativeBridgeResult_(metadata, {
      status: 'provider_unavailable',
      request_status: 'rejected_before_provider_execution',
      response_status: 'provider_unavailable',
      terminal_status: 'provider_unavailable',
      error: 'provider_not_configured'
    });
  }
  var resolvedProvider = resolved[0];
  if (!String(resolvedProvider.model || '').trim()) {
    return _authoritativeBridgeResult_(metadata, {
      status: 'model_not_enforceable',
      request_status: 'rejected_before_provider_execution',
      response_status: 'model_not_enforceable',
      terminal_status: 'model_not_enforceable',
      error: 'configured_provider_route_has_no_model_metadata'
    });
  }
  // The scientific package, rather than a resolver alias, owns the exact
  // model identifier. Keep the authenticated provider route and dispatch the
  // frozen model verbatim; returned metadata is checked before acceptance.
  var prov = {};
  Object.keys(resolvedProvider).forEach(function(key) { prov[key] = resolvedProvider[key]; });
  prov.model = requestedModel;
  var startedMs = new Date().getTime();
  try {
    var response = _callProviderJsonObject_(prov, {
      system: String(prompt.system || ''),
      user: String(prompt.user || ''),
      instruction: String(prompt.instruction || ''),
      cache_scaffold: String(prompt.cache_scaffold || '')
    }, null, responseSchema);
    var elapsedMs = new Date().getTime() - startedMs;
    var actualProvider = String(response.ai_name || prov.name || '').trim();
    var actualModel = String(response.ai_model || prov.model || '').trim();
    if (elapsedMs > hardTimeoutSeconds * 1000) {
      return _authoritativeBridgeResult_(metadata, {
        status: 'timeout',
        request_status: 'attempted',
        response_status: 'timeout',
        terminal_status: 'timeout',
        actual_provider: actualProvider,
        actual_model: actualModel,
        error: 'bridge_response_arrived_after_frozen_timeout'
      });
    }
    if (actualProvider !== providerName || actualModel !== requestedModel) {
      return _authoritativeBridgeResult_(metadata, {
        status: 'execution_integrity_error',
        request_status: 'attempted',
        response_status: 'execution_identity_mismatch',
        terminal_status: 'execution_integrity_error',
        actual_provider: actualProvider,
        actual_model: actualModel,
        error: 'actual_provider_or_model_mismatch'
      });
    }
    return _authoritativeBridgeResult_(metadata, {
      status: 'ok',
      request_status: 'attempted',
      response_status: 'ok',
      terminal_status: 'completed',
      actual_provider: actualProvider,
      actual_model: actualModel,
      request_id: response.request_id || null,
      raw_output: response.raw_output || '',
      prompt_tokens: response.prompt_tokens || null,
      completion_tokens: response.completion_tokens || null,
      cache_creation_input_tokens: response.cache_creation_input_tokens || null,
      cache_read_input_tokens: response.cache_read_input_tokens || null,
      stop_reason: response.stop_reason || null
    });
  } catch (error) {
    return _authoritativeBridgeResult_(metadata, {
      status: 'error',
      request_status: 'attempted',
      response_status: 'error',
      terminal_status: 'error',
      error: String(error || 'provider_call_failed')
    });
  }
}

function _authoritativeReplaySchemaError_(code) {
  throw new Error('AUTHORITATIVE_RESPONSE_SCHEMA_INVALID:' + code);
}

function _authoritativeReplayPlainObject_(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function _authoritativeReplayExactKeys_(value, expected, code) {
  if (!_authoritativeReplayPlainObject_(value)) _authoritativeReplaySchemaError_(code + '_not_object');
  var actual = Object.keys(value).sort();
  var wanted = expected.slice().sort();
  if (JSON.stringify(actual) !== JSON.stringify(wanted)) _authoritativeReplaySchemaError_(code + '_keys');
}

function _authoritativeReplayExactArray_(actual, expected, code) {
  if (!Array.isArray(actual) || JSON.stringify(actual) !== JSON.stringify(expected)) {
    _authoritativeReplaySchemaError_(code);
  }
}

function _authoritativeReplayTokenEnum_(value, expected, code) {
  if (!Array.isArray(value) || !value.length) _authoritativeReplaySchemaError_(code + '_empty');
  var seen = {};
  value.forEach(function(token) {
    if (typeof token !== 'string' || !/^DRV_[0-9a-f]{20}$/.test(token) || seen[token]) {
      _authoritativeReplaySchemaError_(code + '_malformed');
    }
    seen[token] = true;
  });
  _authoritativeReplayExactArray_(value, expected, code + '_context_mismatch');
}

function _validateAuthoritativeReducedResponseSchema_(schema, promptUser) {
  var fields = [
    'primary_driver_token', 'secondary_driver_token', 'final_usdjpy_direction',
    'reaction_strength', 'confidence', 'primary_thesis', 'secondary_thesis',
    'reasoning_steps'
  ];
  var context;
  try {
    context = JSON.parse(String(promptUser || ''));
  } catch (error) {
    _authoritativeReplaySchemaError_('prompt_context_json');
  }
  _authoritativeReplayExactKeys_(schema, ['type', 'properties', 'required', 'additionalProperties', 'propertyOrdering'], 'top_level');
  if (schema.type !== 'object' || schema.additionalProperties !== false) {
    _authoritativeReplaySchemaError_('top_level_contract');
  }
  _authoritativeReplayExactArray_(schema.required, fields, 'required_fields');
  _authoritativeReplayExactArray_(schema.propertyOrdering, fields, 'property_ordering');
  _authoritativeReplayExactKeys_(schema.properties, fields, 'properties');

  var props = schema.properties;
  _authoritativeReplayExactKeys_(props.primary_driver_token, ['type', 'enum'], 'primary_driver_token');
  if (props.primary_driver_token.type !== 'string') _authoritativeReplaySchemaError_('primary_driver_token_type');
  _authoritativeReplayTokenEnum_(
    props.primary_driver_token.enum,
    context.allowed_primary_driver_tokens,
    'primary_driver_token_enum'
  );

  _authoritativeReplayExactKeys_(props.secondary_driver_token, ['anyOf'], 'secondary_driver_token');
  if (!Array.isArray(props.secondary_driver_token.anyOf) || props.secondary_driver_token.anyOf.length !== 2) {
    _authoritativeReplaySchemaError_('secondary_driver_token_any_of');
  }
  var secondaryString = props.secondary_driver_token.anyOf[0];
  var secondaryNull = props.secondary_driver_token.anyOf[1];
  _authoritativeReplayExactKeys_(secondaryString, ['type', 'enum'], 'secondary_driver_token_string');
  _authoritativeReplayExactKeys_(secondaryNull, ['type'], 'secondary_driver_token_null');
  if (secondaryString.type !== 'string' || secondaryNull.type !== 'null') {
    _authoritativeReplaySchemaError_('secondary_driver_token_types');
  }
  _authoritativeReplayTokenEnum_(
    secondaryString.enum,
    context.allowed_secondary_driver_tokens,
    'secondary_driver_token_enum'
  );

  _authoritativeReplayExactKeys_(props.final_usdjpy_direction, ['type', 'enum'], 'final_direction');
  if (props.final_usdjpy_direction.type !== 'string') _authoritativeReplaySchemaError_('final_direction_type');
  _authoritativeReplayExactArray_(props.final_usdjpy_direction.enum, ['DOWN', 'FLAT', 'NO_CLEAR_DIRECTION', 'UP'], 'final_direction_enum');

  _authoritativeReplayExactKeys_(props.reaction_strength, ['type', 'enum'], 'reaction_strength');
  if (props.reaction_strength.type !== 'string') _authoritativeReplaySchemaError_('reaction_strength_type');
  _authoritativeReplayExactArray_(props.reaction_strength.enum, ['MODERATE', 'STRONG', 'WEAK'], 'reaction_strength_enum');

  _authoritativeReplayExactKeys_(props.confidence, ['type', 'minimum', 'maximum'], 'confidence');
  if (props.confidence.type !== 'number' || props.confidence.minimum !== 0 || props.confidence.maximum !== 1) {
    _authoritativeReplaySchemaError_('confidence_constraints');
  }
  _authoritativeReplayExactKeys_(props.primary_thesis, ['type'], 'primary_thesis');
  if (props.primary_thesis.type !== 'string') _authoritativeReplaySchemaError_('primary_thesis_type');

  _authoritativeReplayExactKeys_(props.secondary_thesis, ['anyOf'], 'secondary_thesis');
  if (!Array.isArray(props.secondary_thesis.anyOf) || props.secondary_thesis.anyOf.length !== 2) {
    _authoritativeReplaySchemaError_('secondary_thesis_any_of');
  }
  _authoritativeReplayExactKeys_(props.secondary_thesis.anyOf[0], ['type'], 'secondary_thesis_string');
  _authoritativeReplayExactKeys_(props.secondary_thesis.anyOf[1], ['type'], 'secondary_thesis_null');
  if (props.secondary_thesis.anyOf[0].type !== 'string' || props.secondary_thesis.anyOf[1].type !== 'null') {
    _authoritativeReplaySchemaError_('secondary_thesis_types');
  }

  _authoritativeReplayExactKeys_(props.reasoning_steps, ['type', 'items', 'minItems', 'maxItems'], 'reasoning_steps');
  _authoritativeReplayExactKeys_(props.reasoning_steps.items, ['type'], 'reasoning_step_items');
  if (props.reasoning_steps.type !== 'array' || props.reasoning_steps.items.type !== 'string' ||
      props.reasoning_steps.minItems !== 2 || props.reasoning_steps.maxItems !== 4) {
    _authoritativeReplaySchemaError_('reasoning_steps_constraints');
  }
  return JSON.parse(JSON.stringify(schema));
}

function _authoritativeBridgeResult_(metadata, result) {
  result = result || {};
  var actualProvider = String(result.actual_provider || '').trim();
  var actualModel = String(result.actual_model || '').trim();
  return {
    status: String(result.status || 'error'),
    provider: metadata.requested_provider,
    model: metadata.requested_model,
    requested_provider: metadata.requested_provider,
    requested_model: metadata.requested_model,
    actual_provider: actualProvider,
    actual_model: actualModel,
    authoritative_run_id: metadata.authoritative_run_id,
    forecast_identity: metadata.forecast_identity,
    session_id: metadata.session_id,
    arm: metadata.arm,
    hard_timeout_seconds: metadata.hard_timeout_seconds,
    request_schema_version: metadata.request_schema_version,
    started_timestamp: metadata.started_timestamp,
    completed_timestamp: new Date().toISOString(),
    request_status: String(result.request_status || 'error'),
    response_status: String(result.response_status || 'error'),
    terminal_status: String(result.terminal_status || 'error'),
    request_id: result.request_id || null,
    raw_output: result.raw_output || '',
    error: String(result.error || ''),
    prompt_tokens: result.prompt_tokens || null,
    completion_tokens: result.completion_tokens || null,
    cache_creation_input_tokens: result.cache_creation_input_tokens || null,
    cache_read_input_tokens: result.cache_read_input_tokens || null,
    stop_reason: result.stop_reason || null
  };
}

function apiCallAuthoritativeProviderJsonObject(params) {
  return apiCallAuthoritativeProviderJsonObject_(params);
}
