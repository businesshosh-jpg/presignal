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
  if (!providerName || !requestedModel || !authoritativeRunId || !forecastIdentity || !sessionId || !arm) {
    throw new Error('apiCallAuthoritativeProviderJsonObject requires frozen execution identity metadata.');
  }
  if (requestSchemaVersion !== 'authoritative_historical_replay_bridge_v1') {
    throw new Error('apiCallAuthoritativeProviderJsonObject received unsupported request_schema_version.');
  }
  if (!isFinite(hardTimeoutSeconds) || hardTimeoutSeconds <= 0) {
    throw new Error('apiCallAuthoritativeProviderJsonObject requires positive hard_timeout_seconds.');
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
  var prov = resolved[0];
  if (String(prov.model || '').trim() !== requestedModel) {
    return _authoritativeBridgeResult_(metadata, {
      status: 'model_not_enforceable',
      request_status: 'rejected_before_provider_execution',
      response_status: 'model_not_enforceable',
      terminal_status: 'model_not_enforceable',
      error: 'configured_model_does_not_match_frozen_model'
    });
  }
  var prompt = params.prompt || {};
  var startedMs = new Date().getTime();
  try {
    var response = _apiCallProviderRawJsonObject_(prov, {
      system: String(prompt.system || ''),
      user: String(prompt.user || ''),
      instruction: String(prompt.instruction || ''),
      cache_scaffold: String(prompt.cache_scaffold || '')
    });
    var elapsedMs = new Date().getTime() - startedMs;
    var actualProvider = String(response.ai_name || '').trim();
    var actualModel = String(response.ai_model || '').trim();
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
      cache_read_input_tokens: response.cache_read_input_tokens || null
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
    cache_read_input_tokens: result.cache_read_input_tokens || null
  };
}

function apiCallAuthoritativeProviderJsonObject(params) {
  return apiCallAuthoritativeProviderJsonObject_(params);
}
