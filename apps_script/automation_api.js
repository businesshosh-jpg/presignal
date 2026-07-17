/**
 * automation_api.js
 * API-safe entrypoints for local automation via Apps Script Execution API.
 * These wrappers avoid menu/UI flows and operate on plain parameter objects.
 */

function apiRunPredictionsWindow_(params) {
  params = params || {};
  var applied = _apiApplyWindowConfig_(params);
  var providers = _apiNormalizeProviderList_(params.providers);
  var passes = _apiRunPredictionsPasses_({
    providers: providers,
    clearCheckpoint: params.clear_checkpoint !== false,
    continueUntilDone: params.continue_until_done !== false,
    maxPasses: Number(params.max_passes || 12)
  });
  return {
    status: passes.final && passes.final.status || 'ok',
    config_applied: applied,
    prediction_passes: passes.passes,
    prediction_final: passes.final
  };
}

function apiRunPredictionsWindow(params) {
  return apiRunPredictionsWindow_(params);
}

function apiRunPredictionForEvent_(params) {
  params = params || {};
  var eventId = String(params.event_id || '').trim();
  if (!eventId) throw new Error('apiRunPredictionForEvent requires event_id.');
  var providers = _apiNormalizeProviderList_(params.providers);
  return {
    status: 'ok',
    prediction: runPredictionForEventId_(eventId, providers)
  };
}

function apiRunPredictionForEvent(params) {
  return apiRunPredictionForEvent_(params);
}

function apiCallProviderJsonObject_(params) {
  params = params || {};
  var providerName = _normalizeProviderName_(params.provider);
  if (!providerName) throw new Error('apiCallProviderJsonObject requires provider.');
  var requestedModel = String(params.model || '').trim();
  var requestSchemaVersion = String(params.request_schema_version || '').trim();
  var hardTimeoutSeconds = Number(params.hard_timeout_seconds || 0);
  var authoritativeRunId = String(params.authoritative_run_id || '').trim();
  var forecastIdentity = String(params.forecast_identity || '').trim();
  var sessionId = String(params.session_id || '').trim();
  var arm = String(params.arm || '').trim();
  if (!requestedModel || !authoritativeRunId || !forecastIdentity || !sessionId || !arm) {
    throw new Error('apiCallProviderJsonObject requires authoritative execution identity metadata.');
  }
  if (requestSchemaVersion !== 'authoritative_historical_replay_bridge_v1') {
    throw new Error('apiCallProviderJsonObject received unsupported request_schema_version.');
  }
  if (!isFinite(hardTimeoutSeconds) || hardTimeoutSeconds <= 0) {
    throw new Error('apiCallProviderJsonObject requires positive hard_timeout_seconds.');
  }

  var prompt = params.prompt || {};
  var resolved = _resolveProviders_([providerName]);
  var startedAt = new Date().toISOString();
  var baseMetadata = {
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
  if (!resolved || !resolved.length) {
    return {
      status: 'provider_unavailable',
      provider: providerName,
      model: requestedModel,
      request_status: 'provider_unavailable',
      response_status: 'provider_unavailable',
      terminal_status: 'provider_unavailable',
      completed_timestamp: new Date().toISOString(),
      error: 'provider_not_configured',
      metadata: baseMetadata
    };
  }

  var prov = resolved[0];
  if (String(prov.model || '').trim() !== requestedModel) {
    return {
      status: 'model_not_enforceable',
      provider: providerName,
      model: String(prov.model || '').trim(),
      request_status: 'rejected_before_provider_execution',
      response_status: 'model_not_enforceable',
      terminal_status: 'model_not_enforceable',
      actual_provider: '',
      actual_model: '',
      completed_timestamp: new Date().toISOString(),
      error: 'configured_model_does_not_match_frozen_model',
      metadata: baseMetadata
    };
  }
  try {
    var resp = _apiCallProviderRawJsonObject_(
      prov,
      {
        system: String(prompt.system || ''),
        user: String(prompt.user || ''),
        instruction: String(prompt.instruction || ''),
        cache_scaffold: String(prompt.cache_scaffold || '')
      }
    );

    var completedAt = new Date().toISOString();
    var actualProvider = String(resp.ai_name || prov.name || '').trim();
    var actualModel = String(resp.ai_model || prov.model || '').trim();
    if (actualProvider !== providerName || actualModel !== requestedModel) {
      return {
        status: 'execution_integrity_error',
        provider: providerName,
        model: requestedModel,
        request_status: 'attempted',
        response_status: 'execution_identity_mismatch',
        terminal_status: 'execution_integrity_error',
        actual_provider: actualProvider,
        actual_model: actualModel,
        completed_timestamp: completedAt,
        error: 'actual_provider_or_model_mismatch',
        metadata: baseMetadata
      };
    }
    return {
      status: 'ok',
      provider: prov.name,
      model: actualModel,
      request_status: 'attempted',
      response_status: 'ok',
      terminal_status: 'completed',
      actual_provider: actualProvider,
      actual_model: actualModel,
      completed_timestamp: completedAt,
      raw_output: resp.raw_output || '',
      prompt_tokens: resp.prompt_tokens || null,
      completion_tokens: resp.completion_tokens || null,
      cache_creation_input_tokens: resp.cache_creation_input_tokens || null,
      cache_read_input_tokens: resp.cache_read_input_tokens || null,
      metadata: baseMetadata
    };
  } catch (e) {
    return {
      status: 'error',
      provider: prov.name,
      model: prov.model,
      request_status: 'attempted',
      response_status: 'error',
      terminal_status: 'error',
      actual_provider: '',
      actual_model: '',
      completed_timestamp: new Date().toISOString(),
      raw_output: (e && e.raw_output) ? String(e.raw_output) : '',
      error: String(e || 'provider_call_failed'),
      metadata: baseMetadata
    };
  }
}

function apiCallProviderJsonObject(params) {
  return apiCallProviderJsonObject_(params);
}

function apiRunAcquisitionAiSourceGrounded_(params) {
  params = params || {};
  var request = params.request || {};
  var sourceBundles = params.source_bundles || [];
  var mode = String(params.mode || 'HISTORICAL_ASOF_REPLAY').trim();
  var fixtureResponse = params.fixture_response || null;

  if (!sourceBundles || !sourceBundles.length) {
    throw new Error('apiRunAcquisitionAiSourceGrounded requires at least one source bundle.');
  }

  var normalizedBundles = _apiAcquisitionValidateSourceBundles_(sourceBundles, mode);
  var acquisition = _apiResolveAcquisitionOpenAi_();
  var prompt = _apiAcquisitionPrompt_(request, normalizedBundles);
  var parsed;
  var rawOutput = '';
  var promptTokens = null;
  var completionTokens = null;

  if (fixtureResponse) {
    parsed = _apiAcquisitionValidateModelPayload_(fixtureResponse);
    rawOutput = JSON.stringify(fixtureResponse);
  } else {
    if (!acquisition.key) {
      throw new Error('missing_acquisition_openai_api_key');
    }
    var resp = _apiCallOpenAiRawJsonObject_({
      name: 'OpenAI',
      key: acquisition.key,
      model: acquisition.model,
      reasoning_effort: acquisition.reasoning_effort,
      temperature_mode: acquisition.temperature_mode,
      temperature_parameter_sent: acquisition.temperature_parameter_sent,
      response_schema_name: 'presignal_source_grounded_acquisition',
      response_schema: _apiAcquisitionResponseSchema_()
    }, prompt);
    rawOutput = resp.raw_output || '';
    parsed = _apiAcquisitionValidateModelPayload_(JSON.parse(rawOutput));
    promptTokens = resp.prompt_tokens || null;
    completionTokens = resp.completion_tokens || null;
  }

  return {
    status: 'ok',
    acquisition_provider: 'OpenAI',
    acquisition_model: acquisition.model,
    acquisition_reasoning: acquisition.reasoning_effort,
    acquisition_temperature_mode: acquisition.temperature_mode,
    acquisition_temperature_parameter_sent: acquisition.temperature_parameter_sent,
    api_key_property_present: acquisition.key ? 'TRUE' : 'FALSE',
    transport: 'apps_script_execution_api',
    source_bundle_count: normalizedBundles.length,
    parsed_result: parsed,
    raw_output: rawOutput,
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens
  };
}

function apiRunAcquisitionAiSourceGrounded(params) {
  return apiRunAcquisitionAiSourceGrounded_(params);
}

function _apiResolveAcquisitionOpenAi_() {
  var key = '';
  try {
    key = String(PropertiesService.getScriptProperties().getProperty('ACQUISITION_OPENAI_API_KEY') || '').trim();
  } catch (e) {
    key = '';
  }
  return {
    key: key,
    model: 'gpt-5.6-luna',
    reasoning_effort: 'low',
    temperature_mode: 'MODEL_DEFAULT',
    temperature_parameter_sent: false
  };
}

function _apiAcquisitionNorm_(value) {
  return (value === null || value === undefined) ? '' : String(value).trim();
}

function _apiAcquisitionParseTimestamp_(value, fieldName) {
  var text = _apiAcquisitionNorm_(value);
  if (!text) throw new Error('missing_timestamp:' + fieldName);
  var d = new Date(text);
  if (isNaN(d.getTime())) throw new Error('invalid_timestamp:' + fieldName + ':' + text);
  return d;
}

function _apiAcquisitionTruth_(value) {
  return ['TRUE', 'T', 'YES', 'Y', '1'].indexOf(_apiAcquisitionNorm_(value).toUpperCase()) >= 0;
}

function _apiAcquisitionValidateSourceBundles_(sourceBundles, mode) {
  var allowedTypes = {
    official_central_bank: true,
    official_government_statistics: true,
    official_economic_calendar: true,
    approved_market_data: true,
    timestamped_institutional_research: true,
    authoritative_financial_news: true,
    exchange_source: true
  };
  var required = [
    'source_bundle_id', 'session_id', 'information_key', 'source_name',
    'source_type', 'source_reference', 'publication_timestamp',
    'retrieval_timestamp', 'as_of_timestamp', 'forecast_timestamp',
    'content_or_structured_extract', 'source_language', 'source_reliability',
    'historical_availability_proven', 'backtest_safe'
  ];
  var seen = {};
  return sourceBundles.map(function(raw, idx) {
    var row = raw || {};
    for (var i = 0; i < required.length; i++) {
      if (!_apiAcquisitionNorm_(row[required[i]])) {
        throw new Error('source_bundle_missing_field:' + idx + ':' + required[i]);
      }
    }
    var sourceType = _apiAcquisitionNorm_(row.source_type).toLowerCase();
    if (!allowedTypes[sourceType]) {
      throw new Error('source_policy_required:' + sourceType);
    }
    var sourceId = _apiAcquisitionNorm_(row.source_bundle_id);
    if (seen[sourceId]) throw new Error('duplicate_source_bundle_id:' + sourceId);
    seen[sourceId] = true;

    var publication = _apiAcquisitionParseTimestamp_(row.publication_timestamp, 'publication_timestamp');
    var retrieval = _apiAcquisitionParseTimestamp_(row.retrieval_timestamp, 'retrieval_timestamp');
    var asOf = _apiAcquisitionParseTimestamp_(row.as_of_timestamp, 'as_of_timestamp');
    var forecast = _apiAcquisitionParseTimestamp_(row.forecast_timestamp, 'forecast_timestamp');
    if (asOf.getTime() !== forecast.getTime()) {
      throw new Error('asof_forecast_timestamp_mismatch:' + sourceId);
    }
    if (mode === 'HISTORICAL_ASOF_REPLAY') {
      if (!_apiAcquisitionTruth_(row.historical_availability_proven)) {
        throw new Error('historical_availability_not_proven:' + sourceId);
      }
      if (!_apiAcquisitionTruth_(row.backtest_safe)) {
        throw new Error('backtest_safe_not_true:' + sourceId);
      }
      // A historical evidence-retrieval job can run after the historical
      // cutoff. The source's original publication time proves availability.
      if (publication.getTime() > forecast.getTime()) {
        throw new Error('post_forecast_source:' + sourceId);
      }
      if (retrieval.getTime() < publication.getTime()) {
        throw new Error('retrieval_before_publication:' + sourceId);
      }
      var historicalAvailability = _apiAcquisitionParseTimestamp_(
        _apiAcquisitionNorm_(row.historical_availability_timestamp) || _apiAcquisitionNorm_(row.publication_timestamp),
        'historical_availability_timestamp'
      );
      if (historicalAvailability.getTime() > forecast.getTime()) {
        throw new Error('historical_availability_after_forecast:' + sourceId);
      }
    } else if (mode === 'PROSPECTIVE_SHADOW') {
      if (retrieval.getTime() >= forecast.getTime() || publication.getTime() > forecast.getTime()) {
        throw new Error('prospective_source_after_deadline:' + sourceId);
      }
    } else {
      throw new Error('invalid_acquisition_mode:' + mode);
    }
    return {
      source_bundle_id: sourceId,
      session_id: _apiAcquisitionNorm_(row.session_id),
      information_key: _apiAcquisitionNorm_(row.information_key),
      source_name: _apiAcquisitionNorm_(row.source_name),
      source_type: sourceType,
      source_reference: _apiAcquisitionNorm_(row.source_reference),
      publication_timestamp: _apiAcquisitionNorm_(row.publication_timestamp),
      retrieval_timestamp: _apiAcquisitionNorm_(row.retrieval_timestamp),
      as_of_timestamp: _apiAcquisitionNorm_(row.as_of_timestamp),
      forecast_timestamp: _apiAcquisitionNorm_(row.forecast_timestamp),
      content_or_structured_extract: _apiAcquisitionNorm_(row.content_or_structured_extract),
      source_language: _apiAcquisitionNorm_(row.source_language),
      source_reliability: _apiAcquisitionNorm_(row.source_reliability).toLowerCase(),
      historical_availability_proven: _apiAcquisitionTruth_(row.historical_availability_proven) ? 'TRUE' : 'FALSE',
      historical_availability_timestamp: _apiAcquisitionNorm_(row.historical_availability_timestamp) || _apiAcquisitionNorm_(row.publication_timestamp),
      backtest_safe: _apiAcquisitionTruth_(row.backtest_safe) ? 'TRUE' : 'FALSE'
    };
  });
}

function _apiAcquisitionPrompt_(request, bundles) {
  var sourcePayload = bundles.map(function(bundle) {
    return {
      source_bundle_id: bundle.source_bundle_id,
      source_name: bundle.source_name,
      source_type: bundle.source_type,
      source_reference: bundle.source_reference,
      publication_timestamp: bundle.publication_timestamp,
      extract: bundle.content_or_structured_extract
    };
  });
  return {
    system: [
      "You are PreSignal's separate source-grounded acquisition role.",
      "Use only the supplied sources.",
      "Do not forecast USDJPY, predict direction, discuss forecast success, assign mechanism arms, or add unsupported interpretation.",
      "Return strict JSON only."
    ].join(' '),
    user: JSON.stringify({
      request_id: _apiAcquisitionNorm_(request.request_id),
      information_key: _apiAcquisitionNorm_(request.information_key),
      requested_information: _apiAcquisitionNorm_(request.requested_information),
      forecast_timestamp: bundles[0].forecast_timestamp,
      sources: sourcePayload,
      required_json: {
        object: 'source_grounded_acquisition',
        retrieved_value: 'short factual value or state',
        structured_summary: 'source-grounded factual summary',
        allowed_state_or_stance: 'factual state only, otherwise empty',
        confidence: 'high|medium|low|unknown',
        reliability_label: 'high|medium|low|unknown'
      }
    }),
    instruction: 'Return one JSON object matching required_json. Do not include markdown.',
    cache_scaffold: ''
  };
}

function _apiAcquisitionResponseSchema_() {
  return {
    type: 'object',
    additionalProperties: false,
    required: [
      'object',
      'retrieved_value',
      'structured_summary',
      'allowed_state_or_stance',
      'confidence',
      'reliability_label'
    ],
    properties: {
      object: { type: 'string', enum: ['source_grounded_acquisition'] },
      retrieved_value: { type: 'string' },
      structured_summary: { type: 'string' },
      allowed_state_or_stance: { type: 'string' },
      confidence: { type: 'string', enum: ['high', 'medium', 'low', 'unknown'] },
      reliability_label: { type: 'string', enum: ['high', 'medium', 'low', 'unknown'] }
    }
  };
}

function _apiAcquisitionValidateModelPayload_(payload) {
  var obj = payload || {};
  var allowed = { high: true, medium: true, low: true, unknown: true };
  var forbidden = [
    'forecast', 'predict', 'expected direction', 'likely direction',
    'will rise', 'will fall', 'success', 'positive arm', 'negative arm'
  ];
  if (_apiAcquisitionNorm_(obj.object) !== 'source_grounded_acquisition') {
    throw new Error('invalid_acquisition_object');
  }
  var retrievedValue = _apiAcquisitionNorm_(obj.retrieved_value);
  var structuredSummary = _apiAcquisitionNorm_(obj.structured_summary);
  var allowedState = _apiAcquisitionNorm_(obj.allowed_state_or_stance);
  var confidence = _apiAcquisitionNorm_(obj.confidence).toLowerCase();
  var reliability = _apiAcquisitionNorm_(obj.reliability_label).toLowerCase();
  if (!retrievedValue && !structuredSummary) throw new Error('empty_acquisition_result');
  if (!allowed[confidence]) throw new Error('invalid_confidence');
  if (!allowed[reliability]) throw new Error('invalid_reliability_label');
  var text = (retrievedValue + ' ' + structuredSummary + ' ' + allowedState).toLowerCase();
  for (var i = 0; i < forbidden.length; i++) {
    if (text.indexOf(forbidden[i]) >= 0) {
      throw new Error('forbidden_forecasting_content:' + forbidden[i]);
    }
  }
  return {
    object: 'source_grounded_acquisition',
    retrieved_value: retrievedValue,
    structured_summary: structuredSummary,
    allowed_state_or_stance: allowedState,
    confidence: confidence,
    reliability_label: reliability
  };
}

function _apiProviderResponseError_(message, rawOutput) {
  var err = new Error(message);
  err.raw_output = rawOutput || '';
  return err;
}

function _apiCallProviderRawJsonObject_(prov, prompt) {
  if (!prov || !prov.name) throw new Error('Provider metadata missing');
  if (prov.name === 'OpenAI') return _apiCallOpenAiRawJsonObject_(prov, prompt);
  if (prov.name === 'Gemini') return _apiCallGeminiRawJsonObject_(prov, prompt);
  if (prov.name === 'Anthropic') return _apiCallClaudeRawJsonObject_(prov, prompt);
  throw new Error('Unsupported provider for raw JSON object call: ' + prov.name);
}

function _apiCallOpenAiRawJsonObject_(prov, prompt) {
  var url = 'https://api.openai.com/v1/chat/completions';
  var body = {
    model: prov.model,
    seed: CFG.PREDICTION_SEED,
    messages: [
      { role: 'system', content: prompt.system },
      { role: 'user', content: prompt.user + '\n\n' + prompt.instruction }
    ]
  };
  if (prov.response_schema) {
    body.response_format = {
      type: 'json_schema',
      json_schema: {
        name: prov.response_schema_name || 'presignal_json_object',
        strict: true,
        schema: prov.response_schema
      }
    };
  } else {
    body.response_format = { type: 'json_object' };
  }
  if (prov.temperature_parameter_sent === false || prov.temperature_mode === 'MODEL_DEFAULT') {
    // Some acquisition models require their default temperature and reject an
    // explicit value. Forecasting calls keep the existing configured default.
  } else {
    body.temperature = (typeof prov.temperature === 'number') ? prov.temperature : CFG.PREDICTION_TEMPERATURE;
  }
  if (prov.reasoning_effort) body.reasoning_effort = prov.reasoning_effort;
  return _withRetries_(function() {
    var resp = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'Authorization': 'Bearer ' + prov.key },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = resp.getResponseCode();
    if (code === 429) throw _quotaErr_('OpenAI 429');
    if (code >= 500) throw _providerErr_('OpenAI ' + code);
    if (code < 200 || code > 299) throw _providerErr_('OpenAI ' + code + ': ' + resp.getContentText());
    var j = JSON.parse(resp.getContentText());
    var c = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
    if (!c) throw _apiProviderResponseError_('OpenAI: empty content', '');
    var usage = j.usage || {};
    return {
      ai_name: 'OpenAI',
      ai_model: j.model || prov.model,
      raw_output: c,
      prompt_tokens: usage.prompt_tokens || null,
      completion_tokens: usage.completion_tokens || null,
      cache_creation_input_tokens: null,
      cache_read_input_tokens: usage.prompt_tokens_details && usage.prompt_tokens_details.cached_tokens || null,
      finish_reason: j.choices && j.choices[0] && j.choices[0].finish_reason || null,
      refusal: j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.refusal || null,
      structured_output_mode: prov.response_schema ? 'openai_json_schema_strict' : ''
    };
  }, { provider: 'OpenAI' });
}

function _apiCallGeminiRawJsonObject_(prov, prompt) {
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/' + encodeURIComponent(prov.model) + ':generateContent?key=' + encodeURIComponent(prov.key);
  var body = {
    contents: [{ role: 'user', parts: [{ text: prompt.system + '\n\n' + prompt.user + '\n\n' + prompt.instruction }] }],
    generationConfig: {
      responseMimeType: 'application/json',
      temperature: CFG.PREDICTION_TEMPERATURE,
      seed: CFG.PREDICTION_SEED
    }
  };
  if (prov.response_schema) body.generationConfig.responseSchema = prov.response_schema;
  return _withRetries_(function() {
    var resp = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = resp.getResponseCode();
    var txt = resp.getContentText();
    if (code === 429) throw _quotaErr_('Gemini 429: ' + txt);
    if (code >= 500) throw _providerErr_('Gemini ' + code);
    if (code < 200 || code > 299) throw _providerErr_('Gemini ' + code + ': ' + txt);
    var j = JSON.parse(txt);
    var c = (j.candidates && j.candidates[0] && j.candidates[0].content && j.candidates[0].content.parts && j.candidates[0].content.parts[0] && j.candidates[0].content.parts[0].text) || '';
    if (!c) throw _apiProviderResponseError_('Gemini: empty content', txt);
    var usage = j.usageMetadata || {};
    return {
      ai_name: 'Gemini',
      ai_model: prov.model,
      raw_output: c,
      prompt_tokens: usage.promptTokenCount || null,
      completion_tokens: usage.candidatesTokenCount || null,
      cache_creation_input_tokens: null,
      cache_read_input_tokens: usage.cachedContentTokenCount || null,
      finish_reason: j.candidates && j.candidates[0] && j.candidates[0].finishReason || null,
      structured_output_mode: prov.response_schema ? 'gemini_response_schema' : ''
    };
  }, { provider: 'Gemini' });
}

function _apiCallClaudeRawJsonObject_(prov, prompt) {
  var url = 'https://api.anthropic.com/v1/messages';
  var staticPromptText = [
    prompt.system,
    prompt.instruction,
    prompt.cache_scaffold || ''
  ].filter(function(part){ return !!part; }).join('\n\n');
  var staticPromptBlock = {
    type: 'text',
    text: staticPromptText
  };
  if (_anthropicPromptCacheEnabled_()) {
    staticPromptBlock.cache_control = _anthropicPromptCacheControl_();
  }
  var body = {
    model: prov.model,
    // A complete native-v2 Prediction contains 36 required top-level fields
    // plus a bounded two-to-four-stage path.  The previous 2,048 cap truncated
    // valid structured responses.  4,096 leaves a twofold safety margin while
    // the strict JSON-only prompt continues to prohibit unbounded prose.
    max_tokens: 4096,
    temperature: CFG.PREDICTION_TEMPERATURE,
    system: [ staticPromptBlock ],
    messages: [ { role: 'user', content: [ { type: 'text', text: prompt.user } ] } ]
  };
  if (prov.response_schema) {
    body.tools = [{
      name: 'emit_native_v2_prediction',
      description: 'Emit exactly one native-v2 Prediction object using the supplied typed input schema.',
      input_schema: prov.response_schema
    }];
    body.tool_choice = { type: 'tool', name: 'emit_native_v2_prediction' };
  }
  return _withRetries_(function() {
    var resp = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'x-api-key': prov.key, 'anthropic-version': '2023-06-01' },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = resp.getResponseCode();
    var txt = resp.getContentText();
    if (code === 429) throw _quotaErr_('Anthropic 429: ' + txt);
    if (code >= 500) throw _providerErr_('Anthropic ' + code);
    if (code < 200 || code > 299) throw _providerErr_('Anthropic ' + code + ': ' + txt);
    var j = JSON.parse(txt);
    var toolUse = null;
    var content = j.content || [];
    for (var i = 0; i < content.length; i++) {
      if (content[i] && content[i].type === 'tool_use' && content[i].name === 'emit_native_v2_prediction') {
        toolUse = content[i];
        break;
      }
    }
    var c = prov.response_schema ? (toolUse && toolUse.input ? JSON.stringify(toolUse.input) : '') : ((content[0] && content[0].text) || '');
    if (!c) throw _apiProviderResponseError_('Anthropic: empty content', txt);
    var usage = j.usage || {};
    return {
      ai_name: 'Anthropic',
      ai_model: prov.model,
      raw_output: c,
      prompt_tokens: usage.input_tokens || null,
      completion_tokens: usage.output_tokens || null,
      cache_creation_input_tokens: usage.cache_creation_input_tokens || null,
      cache_read_input_tokens: usage.cache_read_input_tokens || null,
      stop_reason: j.stop_reason || null,
      structured_output_mode: prov.response_schema ? 'anthropic_forced_tool_input_schema' : ''
    };
  }, { provider: 'Anthropic' });
}

function apiRunMinimalDataAvailabilityAudit_() {
  return {
    status: 'ok',
    data_availability_audit: runMinimalDataAvailabilityAudit_()
  };
}

function apiRunMinimalDataAvailabilityAudit() {
  return apiRunMinimalDataAvailabilityAudit_();
}

function apiBuildMarketContextProviderRepairReport_() {
  return {
    status: 'ok',
    market_context_provider_repair_report: buildMarketContextProviderRepairReport_()
  };
}

function apiBuildMarketContextProviderRepairReport() {
  return apiBuildMarketContextProviderRepairReport_();
}

function apiBuildFeaturePackV2BCoreAudit_(params) {
  params = params || {};
  return {
    status: 'ok',
    feature_pack_v2b_core_audit: buildFeaturePackV2BCoreAudit_(params.event_ids || params.eventIds || null)
  };
}

function apiBuildFeaturePackV2BCoreAudit(params) {
  return apiBuildFeaturePackV2BCoreAudit_(params);
}

function apiBuildMarketContextDataSanityReport_() {
  return {
    status: 'ok',
    market_context_data_sanity_report: buildMarketContextDataSanityReport_()
  };
}

function apiBuildMarketContextDataSanityReport() {
  return apiBuildMarketContextDataSanityReport_();
}

function apiBuildMarketContextSourceValidationReport_() {
  return {
    status: 'ok',
    market_context_source_validation_report: buildMarketContextSourceValidationReport_()
  };
}

function apiBuildMarketContextSourceValidationReport() {
  return apiBuildMarketContextSourceValidationReport_();
}

function apiDebugFeaturePackForEvent_(params) {
  params = params || {};
  var eventId = String(params.event_id || params.eventId || '').trim();
  if (!eventId) throw new Error('apiDebugFeaturePackForEvent requires event_id.');
  return {
    status: 'ok',
    feature_pack: debugFeaturePackForEvent(eventId)
  };
}

function apiDebugFeaturePackForEvent(params) {
  return apiDebugFeaturePackForEvent_(params);
}

function apiFetchActualsWindow_(params) {
  params = params || {};
  var applied = _apiApplyWindowConfig_(params);
  var win = resolveWindow_('actuals_api');
  if (!win || !win.windowEnabled) {
    throw new Error('Automation actuals run requires WINDOW_ENABLED with valid FROM/TO.');
  }
  return {
    status: 'ok',
    config_applied: applied,
    actuals: runFetchActualsWindowBounds_(
      win.fromUtcIso,
      win.toUtcIso,
      Number(params.actuals_row_cap || params.row_cap || 2000)
    )
  };
}

function apiFetchActualsWindow(params) {
  return apiFetchActualsWindow_(params);
}

function apiScoreMarketReactionWindow_(params) {
  params = params || {};
  var applied = _apiApplyWindowConfig_(params);
  return {
    status: 'ok',
    config_applied: applied,
    market_reaction: scoreMarketReactionByConfigWindow_()
  };
}

function apiScoreMarketReactionWindow(params) {
  return apiScoreMarketReactionWindow_(params);
}

function apiGetUsdJpyWindowMove_(params) {
  params = params || {};
  var startIso = String(params.start_ts || params.startTs || '').trim();
  var endIso = String(params.end_ts || params.endTs || '').trim();
  var provider = String(params.provider || '').trim();
  if (!startIso || !endIso) throw new Error('apiGetUsdJpyWindowMove requires start_ts and end_ts.');

  var startTs = new Date(startIso);
  var endTs = new Date(endIso);
  if (!_validDate_(startTs) || !_validDate_(endTs)) {
    throw new Error('apiGetUsdJpyWindowMove received invalid timestamp(s).');
  }
  if (endTs.getTime() < startTs.getTime()) {
    throw new Error('apiGetUsdJpyWindowMove requires end_ts >= start_ts.');
  }

  var midMs = Math.floor((startTs.getTime() + endTs.getTime()) / 2);
  var midTs = new Date(midMs);
  var preMinutes = Math.max(1, Math.ceil((midMs - startTs.getTime()) / 60000) + 5);
  var postMinutes = Math.max(1, Math.ceil((endTs.getTime() - midMs) / 60000) + 5);
  var out = getFxCandlesForWindowByProvider_(provider || null, 'USD/JPY', midTs, preMinutes, postMinutes);
  if (!out || !out.candles || !out.candles.length) {
    return {
      status: _isLikelyFxMarketClosedAt_(startTs) ? 'market_closed' : 'no_candles',
      provider: out && out.provider ? out.provider : '',
      candle_count: out && out.candles ? out.candles.length : 0,
      start_ts: startIso,
      end_ts: endIso
    };
  }

  var startCandle = _nearestAtOrBefore_(out.candles, startTs.getTime());
  var endCandle = _nearestAtOrBefore_(out.candles, endTs.getTime());
  if (!startCandle || !isFinite(startCandle.close)) {
    return {
      status: 'no_start_candle',
      provider: out.provider || '',
      candle_count: out.candles.length,
      start_ts: startIso,
      end_ts: endIso
    };
  }
  if (!endCandle || !isFinite(endCandle.close)) {
    return {
      status: 'no_end_candle',
      provider: out.provider || '',
      candle_count: out.candles.length,
      start_ts: startIso,
      end_ts: endIso,
      start_candle_ts: _validDate_(startCandle.ts) ? startCandle.ts.toISOString() : ''
    };
  }

  var startPrice = startCandle.close;
  var endPrice = endCandle.close;
  var realizedPips = _roundUsdJpyPips_(endPrice - startPrice);
  var cfg = _readConfigMap_('Config');
  var flatThresholdPips = _getMarketReactionFlatMaxAbsPips_(cfg || {});
  var dir = _dirSignForPips_(realizedPips, flatThresholdPips);
  var dirLabel = dir > 0 ? 'up' : dir < 0 ? 'down' : 'flat';

  return {
    status: 'ok',
    provider: out.provider || '',
    provider_meta_json: out && out.meta ? JSON.stringify(out.meta) : '',
    candle_count: out.candles.length,
    start_ts: startIso,
    end_ts: endIso,
    start_candle_ts: _validDate_(startCandle.ts) ? startCandle.ts.toISOString() : '',
    end_candle_ts: _validDate_(endCandle.ts) ? endCandle.ts.toISOString() : '',
    start_price: startPrice,
    end_price: endPrice,
    realized_pips: realizedPips,
    realized_direction: dirLabel,
    flat_threshold_pips: flatThresholdPips
  };
}

function apiGetUsdJpyWindowMove(params) {
  return apiGetUsdJpyWindowMove_(params);
}

function _apiShadowDateIso_(dt) {
  if (!(dt instanceof Date) || !isFinite(dt.getTime())) return '';
  return Utilities.formatDate(dt, 'UTC', 'yyyy-MM-dd');
}

function _apiShadowConservativeDailySnapshotFromRows_(rows, targetDateIso) {
  var sorted = _v2bSortRowsAsc_(rows || []).filter(function(row) {
    return !!_v2bRowDate_(row);
  });
  if (!sorted.length) {
    return {
      status: 'missing',
      chosen: null,
      prior: null,
      same_day_candidate_found: false,
      same_day_value_used: false,
      same_day_timestamp_confirmed: 'UNKNOWN',
      publication_timestamp_policy: 'conservative'
    };
  }

  var idx = -1;
  for (var i = 0; i < sorted.length; i++) {
    if (_v2bRowDate_(sorted[i]) <= targetDateIso) idx = i;
    else break;
  }
  if (idx < 0) {
    return {
      status: 'missing',
      chosen: null,
      prior: null,
      same_day_candidate_found: false,
      same_day_value_used: false,
      same_day_timestamp_confirmed: 'UNKNOWN',
      publication_timestamp_policy: 'conservative'
    };
  }

  var sameDayCandidateFound = (_v2bRowDate_(sorted[idx]) === targetDateIso);
  var chosenIdx = idx;
  if (sameDayCandidateFound) chosenIdx = idx - 1;
  if (chosenIdx < 0) {
    return {
      status: 'missing_prior_only',
      chosen: null,
      prior: null,
      same_day_candidate_found: sameDayCandidateFound,
      same_day_value_used: false,
      same_day_timestamp_confirmed: 'UNKNOWN',
      publication_timestamp_policy: 'conservative'
    };
  }

  var chosen = sorted[chosenIdx];
  var prior = chosenIdx > 0 ? sorted[chosenIdx - 1] : null;
  return {
    status: 'ok',
    chosen: chosen,
    prior: prior,
    same_day_candidate_found: sameDayCandidateFound,
    same_day_value_used: false,
    same_day_timestamp_confirmed: 'UNKNOWN',
    publication_timestamp_policy: 'conservative'
  };
}

function _apiShadowRealizedVolatility1h_(candles, startMs, endMs) {
  var filtered = (candles || []).filter(function(c) {
    return c && c.ts instanceof Date && isFinite(c.ts.getTime()) &&
      c.ts.getTime() >= startMs && c.ts.getTime() <= endMs && isFinite(c.close);
  }).sort(function(a, b) {
    return a.ts.getTime() - b.ts.getTime();
  });
  if (filtered.length < 2) {
    return { status: 'insufficient_candles', bar_count: filtered.length, volatility: null };
  }
  var returns = [];
  for (var i = 1; i < filtered.length; i++) {
    var prev = filtered[i - 1].close;
    var curr = filtered[i].close;
    if (!isFinite(prev) || !isFinite(curr) || prev <= 0 || curr <= 0) continue;
    returns.push(Math.log(curr / prev));
  }
  if (!returns.length) {
    return { status: 'insufficient_returns', bar_count: filtered.length, volatility: null };
  }
  var mean = returns.reduce(function(sum, value) { return sum + value; }, 0) / returns.length;
  var variance = returns.reduce(function(sum, value) {
    var diff = value - mean;
    return sum + diff * diff;
  }, 0) / returns.length;
  return {
    status: 'ok',
    bar_count: filtered.length,
    volatility: Number(Math.sqrt(variance).toFixed(8))
  };
}

function _apiShadowGapReason_(targetStartTs, startCandleTs) {
  if (!_validDate_(targetStartTs)) return '';
  if (_isLikelyFxMarketClosedAt_(targetStartTs)) return 'weekend_or_market_closed_boundary';
  if (_validDate_(startCandleTs) && _isLikelyFxMarketClosedAt_(startCandleTs)) return 'weekend_or_market_closed_boundary';
  return 'nearest_available_candle';
}

function _apiShadowUsdJpyWindowStats_(cutoffTs, preMinutes, toleranceMinutes) {
  var endMs = cutoffTs.getTime();
  var requestedPreMinutes = Number(preMinutes || 0);
  var allowedToleranceMinutes = Math.max(0, Number(toleranceMinutes || 0));
  var startMs = endMs - (requestedPreMinutes * 60 * 1000);
  var targetStartTs = new Date(startMs);
  var out = getFxCandlesForWindowByProvider_('eodhd', 'USD/JPY', cutoffTs, requestedPreMinutes + allowedToleranceMinutes + 10, 0);
  if (!out || !out.candles || !out.candles.length) {
    return {
      status: _isLikelyFxMarketClosedAt_(cutoffTs) ? 'market_closed_missing' : 'source_unavailable',
      provider: out && out.provider ? out.provider : 'eodhd',
      start_ts: targetStartTs.toISOString(),
      end_ts: cutoffTs.toISOString(),
      candle_count: out && out.candles ? out.candles.length : 0,
      post_forecast_data_used: false,
      start_candle_exact: false,
      start_candle_gap_minutes: '',
      start_candle_gap_reason: '',
      weekend_gap_flag: _isLikelyFxMarketClosedAt_(targetStartTs)
    };
  }
  var startCandle = _nearestAtOrBefore_(out.candles, startMs);
  var endCandle = _nearestAtOrBefore_(out.candles, endMs);
  var weekendGapFlag = _isLikelyFxMarketClosedAt_(targetStartTs);
  if (!startCandle || !isFinite(startCandle.close) || !(startCandle.ts instanceof Date) || !isFinite(startCandle.ts.getTime())) {
    return {
      status: weekendGapFlag ? 'weekend_gap_outside_tolerance' : 'insufficient_history',
      provider: out.provider || 'eodhd',
      start_ts: targetStartTs.toISOString(),
      end_ts: cutoffTs.toISOString(),
      candle_count: out.candles.length,
      post_forecast_data_used: false,
      start_candle_exact: false,
      start_candle_gap_minutes: '',
      start_candle_gap_reason: weekendGapFlag ? 'weekend_gap_outside_tolerance' : 'insufficient_history',
      weekend_gap_flag: weekendGapFlag
    };
  }
  if (!endCandle || !isFinite(endCandle.close)) {
    return {
      status: 'no_end_candle',
      provider: out.provider || 'eodhd',
      start_ts: targetStartTs.toISOString(),
      end_ts: cutoffTs.toISOString(),
      candle_count: out.candles.length,
      start_candle_ts: startCandle.ts.toISOString(),
      post_forecast_data_used: false,
      start_candle_exact: false,
      start_candle_gap_minutes: '',
      start_candle_gap_reason: '',
      weekend_gap_flag: weekendGapFlag
    };
  }
  var startGapMinutes = Math.max(0, Math.round((startMs - startCandle.ts.getTime()) / 60000));
  if (startGapMinutes > allowedToleranceMinutes) {
    return {
      status: weekendGapFlag ? 'weekend_gap_outside_tolerance' : 'insufficient_history',
      provider: out.provider || 'eodhd',
      start_ts: targetStartTs.toISOString(),
      end_ts: cutoffTs.toISOString(),
      candle_count: out.candles.length,
      start_candle_ts: startCandle.ts.toISOString(),
      end_candle_ts: endCandle.ts.toISOString(),
      post_forecast_data_used: false,
      start_candle_exact: false,
      start_candle_gap_minutes: startGapMinutes,
      start_candle_gap_reason: weekendGapFlag ? 'weekend_gap_outside_tolerance' : 'insufficient_history',
      weekend_gap_flag: weekendGapFlag
    };
  }

  var exactStart = startGapMinutes === 0;
  var status = exactStart ? 'exact_window' : 'leakage_safe_nearest_start';
  var gapReason = exactStart ? 'exact_window' : _apiShadowGapReason_(targetStartTs, startCandle.ts);
  var returnPct = startCandle.close > 0 ? Number((((endCandle.close - startCandle.close) / startCandle.close) * 100).toFixed(6)) : null;
  var vol = _apiShadowRealizedVolatility1h_(out.candles, startMs, endMs);
  return {
    status: status,
    provider: out.provider || 'eodhd',
    start_ts: targetStartTs.toISOString(),
    end_ts: cutoffTs.toISOString(),
    start_candle_ts: startCandle.ts.toISOString(),
    end_candle_ts: endCandle.ts.toISOString(),
    start_price: startCandle.close,
    end_price: endCandle.close,
    candle_count: out.candles.length,
    return_pct: returnPct,
    realized_pips: _roundUsdJpyPips_(endCandle.close - startCandle.close),
    realized_volatility: vol.volatility,
    realized_volatility_status: vol.status,
    realized_volatility_bar_count: vol.bar_count,
    post_forecast_data_used: false,
    start_candle_exact: exactStart,
    start_candle_gap_minutes: startGapMinutes,
    start_candle_gap_reason: gapReason,
    weekend_gap_flag: weekendGapFlag
  };
}

function apiBuildMarketStateShadowSnapshot_(params) {
  params = params || {};
  var cutoffIso = String(params.cutoff_ts || params.cutoffTs || '').trim();
  if (!cutoffIso) throw new Error('apiBuildMarketStateShadowSnapshot requires cutoff_ts.');
  var cutoffTs = new Date(cutoffIso);
  if (!_validDate_(cutoffTs)) throw new Error('apiBuildMarketStateShadowSnapshot received invalid cutoff_ts.');

  var targetDateIso = _apiShadowDateIso_(cutoffTs);
  var startIso = _v2bOffsetDateIso_(targetDateIso, -180);

  var dgs2Rows = _v2bFetchFredHistory_('DGS2', startIso, targetDateIso);
  var dgs5Rows = _v2bFetchFredHistory_('DGS5', startIso, targetDateIso);
  var dgs10Rows = _v2bFetchFredHistory_('DGS10', startIso, targetDateIso);
  var dgs30Rows = _v2bFetchFredHistory_('DGS30', startIso, targetDateIso);
  var sp500Rows = _v2bFetchFredHistory_('SP500', startIso, targetDateIso);
  var usdProxyRows = _v2bFetchFredHistory_('DTWEXBGS', startIso, targetDateIso);
  var dxyRows = _v2bFetchFmpHistory_('DX-Y.NYB', startIso, targetDateIso);
  var usdjpyDailyRows = _v2bFetchEodhdHistory_('USDJPY.FOREX', startIso, targetDateIso);

  var dgs2Snap = _apiShadowConservativeDailySnapshotFromRows_(dgs2Rows, targetDateIso);
  var dgs5Snap = _apiShadowConservativeDailySnapshotFromRows_(dgs5Rows, targetDateIso);
  var dgs10Snap = _apiShadowConservativeDailySnapshotFromRows_(dgs10Rows, targetDateIso);
  var dgs30Snap = _apiShadowConservativeDailySnapshotFromRows_(dgs30Rows, targetDateIso);
  var sp500Snap = _apiShadowConservativeDailySnapshotFromRows_(sp500Rows, targetDateIso);
  var usdProxySnap = _apiShadowConservativeDailySnapshotFromRows_(usdProxyRows, targetDateIso);
  var dxySnap = _apiShadowConservativeDailySnapshotFromRows_(dxyRows, targetDateIso);
  var usdjpyDailySnap = _apiShadowConservativeDailySnapshotFromRows_(usdjpyDailyRows, targetDateIso);

  return {
    status: 'ok',
    cutoff_ts: cutoffTs.toISOString(),
    release_date: targetDateIso,
    daily_snapshots: {
      us2y: dgs2Snap,
      us5y: dgs5Snap,
      us10y: dgs10Snap,
      us30y: dgs30Snap,
      sp500: sp500Snap,
      usd_index_proxy: usdProxySnap,
      dxy: dxySnap,
      usdjpy_daily: usdjpyDailySnap
    },
    usdjpy_windows: {
      return_1h: _apiShadowUsdJpyWindowStats_(cutoffTs, 60, 0),
      return_4h: _apiShadowUsdJpyWindowStats_(cutoffTs, 240, 0),
      return_24h: _apiShadowUsdJpyWindowStats_(cutoffTs, 1440, 4320),
      realized_vol_1h: _apiShadowUsdJpyWindowStats_(cutoffTs, 60, 0)
    }
  };
}

function apiBuildMarketStateShadowSnapshot(params) {
  return apiBuildMarketStateShadowSnapshot_(params);
}

function apiBuildEvaluationSheets_() {
  return {
    status: 'ok',
    evaluation: buildEvaluationSheets_()
  };
}

function apiBuildEvaluationSheets() {
  return apiBuildEvaluationSheets_();
}

function apiBuildOutcomeLedgerSheet_() {
  return {
    status: 'ok',
    outcome_ledger: buildOutcomeLedger_()
  };
}

function apiBuildOutcomeLedgerSheet() {
  return apiBuildOutcomeLedgerSheet_();
}

function apiBuildOutcomeLedger_() {
  return apiBuildOutcomeLedgerSheet_();
}

function apiBuildOutcomeSummaries_() {
  return {
    status: 'ok',
    outcome_summaries: buildOutcomeSummaries_()
  };
}

function apiBuildOutcomeSummaries() {
  return apiBuildOutcomeSummaries_();
}

function apiBuildOutcomeDiagnostics_() {
  return {
    status: 'ok',
    outcome_diagnostics: buildOutcomeDiagnostics_()
  };
}

function apiBuildOutcomeDiagnostics() {
  return apiBuildOutcomeDiagnostics_();
}

function apiBuildActiveDecisionReports_() {
  return {
    status: 'ok',
    active_decision_reports: buildActiveDecisionReports_()
  };
}

function apiBuildActiveDecisionReports() {
  return apiBuildActiveDecisionReports_();
}

function apiBuildProjectStatus_() {
  return {
    status: 'ok',
    project_status: buildProjectStatus_()
  };
}

function apiBuildProjectStatus() {
  return apiBuildProjectStatus_();
}

function apiBuildDecisionLog_() {
  return {
    status: 'ok',
    decision_log: buildDecisionLog_()
  };
}

function apiBuildDecisionLog() {
  return apiBuildDecisionLog_();
}

function apiReadWorkbookRoutingConfig_() {
  return {
    status: 'ok',
    workbook_routing_config: readWorkbookRoutingConfig_()
  };
}

function apiReadWorkbookRoutingConfig() {
  return apiReadWorkbookRoutingConfig_();
}

function apiRunControlledV2BReplayComparison_(params) {
  return {
    status: 'ok',
    controlled_v2b_replay_comparison: runControlledV2BReplayComparison_(params || {})
  };
}

function apiRunControlledV2BReplayComparison(params) {
  return apiRunControlledV2BReplayComparison_(params);
}

function apiBuildControlledV2BReplaySummary_() {
  return {
    status: 'ok',
    controlled_v2b_replay_summary: buildControlledV2BReplaySummary_()
  };
}

function apiBuildControlledV2BReplaySummary() {
  return apiBuildControlledV2BReplaySummary_();
}

function apiProbeMarketContextCrudeSymbols_() {
  var warnings = [];
  var out = {};
  var eodKey = null;
  try { eodKey = _getEodhdApiKey_(); } catch (e) {}
  var fmpKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
  var fmpBase = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
  if (eodKey && typeof _mcprSafeEodhdSearch_ === 'function') {
    out.eodhd = _mcprSafeEodhdSearch_('crude oil', eodKey, warnings).symbols || [];
  }
  if (fmpKey && typeof _mcprSafeFmpSearch_ === 'function') {
    out.fmp = _mcprSafeFmpSearch_('crude oil', fmpKey, fmpBase, warnings).symbols || [];
  }
  return { status: 'ok', crude_symbol_search: out, warnings: warnings };
}

function apiProbeMarketContextCrudeSymbols() {
  return apiProbeMarketContextCrudeSymbols_();
}

function apiProbeHistoricalPrices_(params) {
  params = params || {};
  var symbols = Array.isArray(params.symbols) ? params.symbols : [];
  var provider = String(params.provider || 'fmp').toLowerCase();
  var fromDate = String(params.from_date || '2024-05-01');
  var toDate = String(params.to_date || '2024-07-10');
  var out = [];
  for (var i = 0; i < symbols.length; i++) {
    var symbol = String(symbols[i] || '').trim();
    if (!symbol) continue;
    try {
      if (provider === 'fmp') {
        var apiKey = (typeof CFG !== 'undefined' && CFG.FMP_API_KEY) ? CFG.FMP_API_KEY : _getScriptProp_('FMP_API_KEY');
        var base = (typeof CFG !== 'undefined' && CFG.FMP_BASE) ? CFG.FMP_BASE : 'https://financialmodelingprep.com/api/v3';
        var rows = _fmpFetchHistoricalWindow_(base, apiKey, symbol, fromDate, toDate) || [];
        out.push({
          symbol: symbol,
          provider: 'fmp',
          row_count: rows.length,
          first_date: rows.length ? rows[rows.length - 1].date : '',
          last_date: rows.length ? rows[0].date : '',
          sample_first: rows.length ? rows[rows.length - 1] : null,
          sample_last: rows.length ? rows[0] : null
        });
      } else {
        var eodKey = _getEodhdApiKey_();
        var rowsEod = _eodhdFetchEodWindow_(symbol, eodKey, fromDate, toDate, 'a') || [];
        out.push({
          symbol: symbol,
          provider: 'eodhd',
          row_count: rowsEod.length,
          first_date: rowsEod.length ? rowsEod[0].date : '',
          last_date: rowsEod.length ? rowsEod[rowsEod.length - 1].date : '',
          sample_first: rowsEod.length ? rowsEod[0] : null,
          sample_last: rowsEod.length ? rowsEod[rowsEod.length - 1] : null
        });
      }
    } catch (e) {
      out.push({ symbol: symbol, provider: provider, error: String(e) });
    }
  }
  return { status: 'ok', provider: provider, from_date: fromDate, to_date: toDate, results: out };
}

function apiProbeHistoricalPrices(params) {
  return apiProbeHistoricalPrices_(params);
}

function _apiEodhdNewsFetchJson_(url) {
  var response = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
    validateHttpsCertificates: true
  });
  var code = response.getResponseCode();
  var body = response.getContentText();
  var parsed = null;
  try { parsed = JSON.parse(body); } catch (e) {}
  return { response_code: code, parsed: parsed, body_preview: body.slice(0, 300) };
}

function _apiEodhdNewsSafeAccount_(apiKey) {
  var result = _apiEodhdNewsFetchJson_(
    'https://eodhd.com/api/user?api_token=' + encodeURIComponent(apiKey) + '&fmt=json'
  );
  var row = result.parsed && !Array.isArray(result.parsed) ? result.parsed : {};
  return {
    response_code: result.response_code,
    subscription_type: String(row.subscriptionType || row.subscription_type || row.plan || ''),
    account_status: String(row.status || row.accountStatus || ''),
    daily_rate_limit: row.dailyRateLimit == null ? null : Number(row.dailyRateLimit),
    api_requests: row.apiRequests == null ? null : Number(row.apiRequests),
    api_requests_date: String(row.apiRequestsDate || ''),
    error: result.response_code === 200 ? '' : result.body_preview
  };
}

function apiProbeEodhdHistoricalNews_(params) {
  params = params || {};
  var apiKey = _getEodhdApiKey_();
  if (!apiKey) {
    return { status: 'credential_missing', credential_present: false, results: [] };
  }
  var queries = Array.isArray(params.queries) ? params.queries.slice(0, 12) : [];
  var results = [];
  for (var i = 0; i < queries.length; i++) {
    var query = queries[i] || {};
    var queryType = String(query.query_type || '').toLowerCase() === 'ticker' ? 's' : 't';
    var queryValue = String(query.query_value || '').trim();
    var fromDate = String(query.from_date || '').trim();
    var toDate = String(query.to_date || '').trim();
    var limit = Math.max(1, Math.min(20, Number(query.limit || 5)));
    if (!queryValue || !/^202[45]-\d{2}-\d{2}$/.test(fromDate) || !/^202[45]-\d{2}-\d{2}$/.test(toDate)) {
      results.push({ query_id: String(query.query_id || ''), status: 'invalid_query', articles: [] });
      continue;
    }
    var url = 'https://eodhd.com/api/news?'
      + queryType + '=' + encodeURIComponent(queryValue)
      + '&from=' + encodeURIComponent(fromDate)
      + '&to=' + encodeURIComponent(toDate)
      + '&limit=' + encodeURIComponent(String(limit))
      + '&offset=0&fmt=json&api_token=' + encodeURIComponent(apiKey);
    var fetched = _apiEodhdNewsFetchJson_(url);
    var rows = Array.isArray(fetched.parsed) ? fetched.parsed : [];
    var articles = rows.map(function(row) {
      var content = String(row.content || row.description || '');
      return {
        article_identity: String(row.id || row.uuid || row.link || ''),
        publication_timestamp: String(row.date || row.datetime || row.published_at || ''),
        title: String(row.title || ''),
        original_publisher: String(row.source || row.publisher || ''),
        article_url: String(row.link || row.url || ''),
        content_excerpt: content.slice(0, 5000),
        content_length: content.length,
        description: String(row.description || '').slice(0, 1000),
        topic_tags: Array.isArray(row.tags) ? row.tags : [],
        ticker_tags: Array.isArray(row.symbols) ? row.symbols : [],
        sentiment: row.sentiment == null ? null : row.sentiment
      };
    });
    results.push({
      query_id: String(query.query_id || ''),
      query_type: queryType === 's' ? 'ticker' : 'topic',
      query_value: queryValue,
      from_date: fromDate,
      to_date: toDate,
      response_code: fetched.response_code,
      status: fetched.response_code === 200 && Array.isArray(fetched.parsed) ? 'ok' : 'api_error',
      error: fetched.response_code === 200 ? '' : fetched.body_preview,
      articles: articles
    });
  }
  return {
    status: 'ok',
    credential_present: true,
    endpoint: 'https://eodhd.com/api/news',
    account: _apiEodhdNewsSafeAccount_(apiKey),
    results: results
  };
}

function apiProbeEodhdHistoricalNews(params) {
  return apiProbeEodhdHistoricalNews_(params);
}

function apiBuildAttentionFactorSummary_() {
  return {
    status: 'ok',
    attention_factor_summary: buildAttentionFactorSummary_()
  };
}

function apiBuildAttentionFactorSummary() {
  return apiBuildAttentionFactorSummary_();
}

function apiBuildProviderCharacterDiagnostics_() {
  return {
    status: 'ok',
    provider_character_diagnostics: buildProviderCharacterDiagnostics_()
  };
}

function apiBuildProviderCharacterDiagnostics() {
  return apiBuildProviderCharacterDiagnostics_();
}

function apiBuildCharacterResidualArchitecture_() {
  return {
    status: 'ok',
    character_residual_architecture: buildCharacterResidualArchitecture_()
  };
}

function apiBuildCharacterResidualArchitecture() {
  return apiBuildCharacterResidualArchitecture_();
}

function apiBuildCharacterRecurrenceValidation_() {
  return {
    status: 'ok',
    character_recurrence_validation: buildCharacterRecurrenceValidation_()
  };
}

function apiBuildCharacterRecurrenceValidation() {
  return apiBuildCharacterRecurrenceValidation_();
}

function apiBuildProviderCharacterEconomicOutcomeLink_() {
  return {
    status: 'ok',
    provider_character_economic_outcome_link: buildProviderCharacterEconomicOutcomeLink_()
  };
}

function apiBuildProviderCharacterEconomicOutcomeLink(params) {
  return apiBuildProviderCharacterEconomicOutcomeLink_();
}

function apiBuildProviderCharacterEconomicFalsification_() {
  return {
    status: 'ok',
    provider_character_economic_falsification: buildProviderCharacterEconomicFalsification_()
  };
}

function apiBuildProviderCharacterEconomicFalsification(params) {
  return apiBuildProviderCharacterEconomicFalsification_();
}

function apiBuildProviderCharacterMicroExpressionPilot_() {
  return {
    status: 'ok',
    provider_character_micro_expression_pilot: buildProviderCharacterMicroExpressionPilot_()
  };
}

function apiBuildProviderCharacterMicroExpressionPilot(params) {
  return apiBuildProviderCharacterMicroExpressionPilot_();
}

function apiBuildProviderCharacterRawOutputMicroExpressionReplay_() {
  return {
    status: 'ok',
    provider_character_raw_output_micro_expression_replay: buildProviderCharacterRawOutputMicroExpressionReplay_()
  };
}

function apiBuildProviderCharacterRawOutputMicroExpressionReplay(params) {
  return apiBuildProviderCharacterRawOutputMicroExpressionReplay_();
}

function apiBuildProviderCharacterFreshVsOriginalReplay_() {
  return {
    status: 'ok',
    provider_character_fresh_vs_original_micro_expression_replay: buildProviderCharacterFreshVsOriginalReplay_()
  };
}

function apiBuildProviderCharacterFreshVsOriginalReplay(params) {
  return apiBuildProviderCharacterFreshVsOriginalReplay_();
}

function apiBuildProviderCharacterDirectExpressionCapture_() {
  return {
    status: 'ok',
    provider_character_direct_expression_capture: buildProviderCharacterDirectExpressionCapture_({})
  };
}

function apiBuildProviderCharacterDirectExpressionCapture(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_capture: buildProviderCharacterDirectExpressionCapture_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionRandomCohort_() {
  return {
    status: 'ok',
    provider_character_direct_expression_random_cohort: buildProviderCharacterDirectExpressionRandomCohort_({})
  };
}

function apiBuildProviderCharacterDirectExpressionRandomCohort(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_random_cohort: buildProviderCharacterDirectExpressionRandomCohort_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionRecurrence_() {
  return {
    status: 'ok',
    provider_character_direct_expression_recurrence: buildProviderCharacterDirectExpressionRecurrence_()
  };
}

function apiBuildProviderCharacterDirectExpressionRecurrence(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_recurrence: buildProviderCharacterDirectExpressionRecurrence_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionEconomicLink_() {
  return {
    status: 'ok',
    provider_character_direct_expression_economic_link: buildProviderCharacterDirectExpressionEconomicLink_({})
  };
}

function apiBuildProviderCharacterDirectExpressionEconomicLink(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_economic_link: buildProviderCharacterDirectExpressionEconomicLink_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionValidation_() {
  return {
    status: 'ok',
    provider_character_direct_expression_validation: buildProviderCharacterDirectExpressionValidation_()
  };
}

function apiBuildProviderCharacterDirectExpressionValidation(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_validation: buildProviderCharacterDirectExpressionValidation_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionMicrocohortRerun_() {
  return {
    status: 'ok',
    provider_character_direct_expression_microcohort_rerun: buildProviderCharacterDirectExpressionMicrocohortRerun_()
  };
}

function apiBuildProviderCharacterDirectExpressionMicrocohortRerun(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_microcohort_rerun: buildProviderCharacterDirectExpressionMicrocohortRerun_(params || {})
  };
}

function apiListProviderCharacterDirectExpressionMicrocohortEligibleRows_(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_microcohort_eligible_rows: listProviderCharacterDirectExpressionMicrocohortEligibleRows_(params || {})
  };
}

function apiListProviderCharacterDirectExpressionMicrocohortEligibleRows(params) {
  return apiListProviderCharacterDirectExpressionMicrocohortEligibleRows_(params);
}

function apiBuildProviderCharacterDirectExpressionEligibilityAudit_() {
  return {
    status: 'ok',
    provider_character_direct_expression_eligibility_audit: buildProviderCharacterDirectExpressionEligibilityAudit_({})
  };
}

function apiBuildProviderCharacterDirectExpressionEligibilityAudit(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_eligibility_audit: buildProviderCharacterDirectExpressionEligibilityAudit_(params || {})
  };
}

function apiBuildProviderCharacterDirectExpressionOutcomeCheck_() {
  return {
    status: 'ok',
    provider_character_direct_expression_outcome_check: buildProviderCharacterDirectExpressionOutcomeCheck_()
  };
}

function apiBuildProviderCharacterDirectExpressionOutcomeCheck(params) {
  return {
    status: 'ok',
    provider_character_direct_expression_outcome_check: buildProviderCharacterDirectExpressionOutcomeCheck_(params || {})
  };
}

function apiBuildSignalSynchronyCohortCharacterization_() {
  return {
    status: 'ok',
    signal_synchrony_cohort_characterization: buildSignalSynchronyCohortCharacterization_()
  };
}

function apiBuildSignalSynchronyCohortCharacterization(params) {
  return {
    status: 'ok',
    signal_synchrony_cohort_characterization: buildSignalSynchronyCohortCharacterization_(params || {})
  };
}

function apiBuildAttentionProviderIndividuality_() {
  return {
    status: 'ok',
    attention_provider_individuality: buildAttentionProviderIndividuality_()
  };
}

function apiBuildAttentionProviderIndividuality() {
  return apiBuildAttentionProviderIndividuality_();
}

function apiBuildAttentionEvidenceReport_() {
  return {
    status: 'ok',
    attention_evidence_report: buildAttentionEvidenceReport_()
  };
}

function apiBuildAttentionEvidenceReport() {
  return apiBuildAttentionEvidenceReport_();
}

function apiBuildAttentionBlockStability_() {
  return {
    status: 'ok',
    attention_block_stability: buildAttentionBlockStability_()
  };
}

function apiBuildAttentionBlockStability() {
  return apiBuildAttentionBlockStability_();
}

function apiBuildAttentionDisagreementReview_() {
  return {
    status: 'ok',
    attention_disagreement_review: buildAttentionDisagreementReview_()
  };
}

function apiBuildAttentionDisagreementReview() {
  return apiBuildAttentionDisagreementReview_();
}

function apiBuildAttentionDisagreementSummary_() {
  return {
    status: 'ok',
    attention_disagreement_summary: buildAttentionDisagreementSummary_()
  };
}

function apiBuildAttentionDisagreementSummary() {
  return apiBuildAttentionDisagreementSummary_();
}

function apiBuildAttentionPhase3Candidates_() {
  return {
    status: 'ok',
    attention_phase3_candidates: buildAttentionPhase3Candidates_()
  };
}

function apiBuildAttentionPhase3Candidates() {
  return apiBuildAttentionPhase3Candidates_();
}

function apiBuildAttentionShadowExperiments_() {
  return {
    status: 'ok',
    attention_shadow_experiments: buildAttentionShadowExperiments_()
  };
}

function apiBuildAttentionShadowExperiments() {
  return apiBuildAttentionShadowExperiments_();
}

function apiBuildFamilyStructureReport_() {
  return {
    status: 'ok',
    family_structure_report: buildFamilyStructureReport_()
  };
}

function apiBuildFamilyStructureReport() {
  return apiBuildFamilyStructureReport_();
}

function apiBuildBatchSplittingCandidates_() {
  return {
    status: 'ok',
    batch_splitting_candidates: buildBatchSplittingCandidates_()
  };
}

function apiBuildBatchSplittingCandidates() {
  return apiBuildBatchSplittingCandidates_();
}

function apiBuildBatchSplitCounterfactuals_() {
  return {
    status: 'ok',
    batch_split_counterfactuals: buildBatchSplitCounterfactuals_()
  };
}

function apiBuildBatchSplitCounterfactuals() {
  return apiBuildBatchSplitCounterfactuals_();
}

function apiBuildBatchBaselineCoverageAudit_() {
  return {
    status: 'ok',
    batch_baseline_coverage_audit: buildBatchBaselineCoverageAudit_()
  };
}

function apiBuildBatchBaselineCoverageAudit() {
  return apiBuildBatchBaselineCoverageAudit_();
}

function apiBuildBatchSplitGroupCounterfactuals_() {
  return {
    status: 'ok',
    batch_split_group_counterfactuals: buildBatchSplitGroupCounterfactuals_()
  };
}

function apiBuildBatchSplitGroupCounterfactuals() {
  return apiBuildBatchSplitGroupCounterfactuals_();
}

function apiBuildEconomicValueAccuracy_() {
  return {
    status: 'ok',
    economic_value_accuracy: buildEconomicValueAccuracy_()
  };
}

function apiBuildEconomicValueAccuracy() {
  return apiBuildEconomicValueAccuracy_();
}

function apiBuildAttentionEconomicValueReport_() {
  return {
    status: 'ok',
    attention_economic_value_report: buildAttentionEconomicValueReport_()
  };
}

function apiBuildAttentionEconomicValueReport() {
  return apiBuildAttentionEconomicValueReport_();
}

function apiRunAttentionV3ReplayExperiment_(params) {
  return {
    status: 'ok',
    attention_v3_replay_experiment: runAttentionV3ReplayExperiment_(params || {})
  };
}

function apiRunAttentionV3ReplayExperiment(params) {
  return apiRunAttentionV3ReplayExperiment_(params);
}

function apiRunAttentionC0ReliabilityReplay_(params) {
  return {
    status: 'ok',
    attention_c0_reliability_replay: runAttentionC0ReliabilityReplay_(params || {})
  };
}

function apiRunAttentionC0ReliabilityReplay(params) {
  return apiRunAttentionC0ReliabilityReplay_(params);
}

function apiBuildProviderFamilyEconomicAccuracy_() {
  return {
    status: 'ok',
    provider_family_economic_accuracy: buildProviderFamilyEconomicAccuracy_()
  };
}

function apiBuildProviderFamilyEconomicAccuracy() {
  return apiBuildProviderFamilyEconomicAccuracy_();
}

function apiBuildEconomicToMarketTranslationErrors_() {
  return {
    status: 'ok',
    economic_to_market_translation_errors: buildEconomicToMarketTranslationErrors_()
  };
}

function apiBuildEconomicToMarketTranslationErrors() {
  return apiBuildEconomicToMarketTranslationErrors_();
}

function apiBuildMarketSensitivityFilterCandidates_() {
  return {
    status: 'ok',
    market_sensitivity_filter_candidates: buildMarketSensitivityFilterCandidates_()
  };
}

function apiBuildMarketSensitivityFilterCandidates() {
  return apiBuildMarketSensitivityFilterCandidates_();
}

function apiBuildMarketSensitivityFilterSummary_() {
  return {
    status: 'ok',
    market_sensitivity_filter_summary: buildMarketSensitivityFilterSummary_()
  };
}

function apiBuildMarketSensitivityFilterSummary() {
  return apiBuildMarketSensitivityFilterSummary_();
}

function apiBuildMarketSensitivityNoSignalCounterfactuals_() {
  return {
    status: 'ok',
    market_sensitivity_no_signal_counterfactuals: buildMarketSensitivityNoSignalCounterfactuals_()
  };
}

function apiBuildMarketSensitivityNoSignalCounterfactuals() {
  return apiBuildMarketSensitivityNoSignalCounterfactuals_();
}

function apiBuildInflationNoSignalReview_() {
  return {
    status: 'ok',
    inflation_no_signal_review: buildInflationNoSignalReview_()
  };
}

function apiBuildInflationNoSignalReview() {
  return apiBuildInflationNoSignalReview_();
}

function apiUpsertEventWindow_(params) {
  params = params || {};

  var fromUtcIso = String(
    params.from_utc_iso ||
    params.window_from_utc ||
    params.from_utc ||
    params.fromUtcIso ||
    ''
  ).trim();
  var toUtcIso = String(
    params.to_utc_iso ||
    params.window_to_utc ||
    params.to_utc ||
    params.toUtcIso ||
    ''
  ).trim();

  if (!fromUtcIso || !toUtcIso) {
    throw new Error('apiUpsertEventWindow requires from_utc_iso and to_utc_iso.');
  }

  var upsert = runFmpRangeToEvent_(fromUtcIso, toUtcIso);
  var batching = (typeof applyBatchingForKeys_ === 'function')
    ? applyBatchingForKeys_()
    : null;

  return {
    status: 'ok',
    window_from_utc: fromUtcIso,
    window_to_utc: toUtcIso,
    upsert: upsert,
    batching: batching
  };
}

function apiUpsertEventWindow(params) {
  return apiUpsertEventWindow_(params);
}

function apiRunPipelineWindow_(params) {
  params = params || {};
  var applied = _apiApplyWindowConfig_(params);
  var out = {
    status: 'ok',
    config_applied: applied,
    steps: {}
  };

  if (params.run_predictions !== false) {
    var providers = _apiNormalizeProviderList_(params.providers);
    var predictionRun = _apiRunPredictionsPasses_({
      providers: providers,
      clearCheckpoint: params.clear_checkpoint !== false,
      continueUntilDone: params.continue_until_done !== false,
      maxPasses: Number(params.max_passes || 12)
    });
    out.steps.predictions = {
      passes: predictionRun.passes,
      final: predictionRun.final
    };
    if (predictionRun.final && predictionRun.final.status === 'partial') {
      out.status = 'partial';
    }
  }

  if (params.run_actuals) {
    var win = resolveWindow_('actuals_api');
    if (!win || !win.windowEnabled) {
      throw new Error('Automation actuals run requires WINDOW_ENABLED with valid FROM/TO.');
    }
    out.steps.actuals = runFetchActualsWindowBounds_(
      win.fromUtcIso,
      win.toUtcIso,
      Number(params.actuals_row_cap || params.row_cap || 2000)
    );
  }

  if (params.run_market_reaction) {
    out.steps.market_reaction = scoreMarketReactionByConfigWindow_();
  }

  if (params.build_evaluation !== false) {
    out.steps.evaluation = buildEvaluationSheets_();
  }

  return out;
}

function apiRunPipelineWindow(params) {
  return apiRunPipelineWindow_(params);
}

function _apiRunPredictionsPasses_(opts) {
  opts = opts || {};
  var passes = [];
  var providers = opts.providers || null;
  var maxPasses = Math.max(1, Number(opts.maxPasses || 12));

  if (opts.clearCheckpoint && typeof menuClearPredictionCheckpoint_ === 'function') {
    menuClearPredictionCheckpoint_();
  }

  var finalSummary = null;
  for (var i = 0; i < maxPasses; i++) {
    finalSummary = runPredictionsCore_({
      windowMinBeforeMin: CFG.WINDOW_MIN_BEFORE_MIN,
      windowMaxAfterMin: CFG.WINDOW_MAX_AFTER_MIN,
      providers: providers,
      autoContinueEnabledOverride: false
    });
    passes.push(finalSummary);
    if (!opts.continueUntilDone) break;
    if (!finalSummary || finalSummary.status !== 'partial' || !Number(finalSummary.remaining_work_units || 0)) {
      break;
    }
  }

  return {
    passes: passes,
    final: finalSummary
  };
}

function _apiApplyWindowConfig_(params) {
  params = params || {};
  var tz = String(
    params.window_tz ||
    params.tz ||
    params.pred_window_tz ||
    params.mr_window_tz ||
    'Asia/Tokyo'
  ).trim();
  var fromLocal = _apiFirstNonEmpty_([
    params.window_from_local,
    params.from_local,
    params.from
  ]);
  var toLocal = _apiFirstNonEmpty_([
    params.window_to_local,
    params.to_local,
    params.to
  ]);
  if (!fromLocal || !toLocal) {
    throw new Error('Automation window params require window_from_local and window_to_local.');
  }

  var predEnabled = params.pred_window_enabled;
  if (predEnabled == null) predEnabled = true;
  var mrEnabled = params.mr_window_enabled;
  if (mrEnabled == null) mrEnabled = true;

  var entries = {
    WINDOW_ENABLED: 'TRUE',
    WINDOW_FROM_LOCAL: String(fromLocal),
    WINDOW_TO_LOCAL: String(toLocal),
    WINDOW_TZ: tz,
    PRED_WINDOW_ENABLED: predEnabled ? 'TRUE' : 'FALSE',
    PRED_WINDOW_FROM_LOCAL: String(_apiFirstNonEmpty_([params.pred_window_from_local, fromLocal])),
    PRED_WINDOW_TO_LOCAL: String(_apiFirstNonEmpty_([params.pred_window_to_local, toLocal])),
    PRED_WINDOW_TZ: String(_apiFirstNonEmpty_([params.pred_window_tz, tz])),
    MR_WINDOW_ENABLED: mrEnabled ? 'TRUE' : 'FALSE',
    MR_WINDOW_FROM_LOCAL: String(_apiFirstNonEmpty_([params.mr_window_from_local, fromLocal])),
    MR_WINDOW_TO_LOCAL: String(_apiFirstNonEmpty_([params.mr_window_to_local, toLocal])),
    MR_WINDOW_TZ: String(_apiFirstNonEmpty_([params.mr_window_tz, tz]))
  };
  _apiUpsertConfigEntries_(entries);
  return entries;
}

function _apiUpsertConfigEntries_(entries) {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(CONFIG_SHEET_NAME || 'Config');
  if (!sh) throw new Error('Config sheet not found');

  var lastRow = Math.max(1, sh.getLastRow());
  var values = sh.getRange(1, 1, lastRow, 2).getValues();
  if (!values.length) values = [['key', 'value']];

  var rowByKey = {};
  for (var i = 1; i < values.length; i++) {
    var key = String(values[i][0] || '').trim();
    if (key) rowByKey[key] = i + 1;
  }

  var updates = [];
  var appends = [];
  Object.keys(entries || {}).forEach(function(key) {
    var value = entries[key];
    if (rowByKey[key]) {
      updates.push({ row: rowByKey[key], value: value });
    } else {
      appends.push([key, value]);
    }
  });

  for (var u = 0; u < updates.length; u++) {
    sh.getRange(updates[u].row, 2).setValue(updates[u].value);
  }
  if (appends.length) {
    sh.getRange(sh.getLastRow() + 1, 1, appends.length, 2).setValues(appends);
  }
}

function _apiNormalizeProviderList_(providers) {
  if (!providers || !providers.length) return null;
  return providers.map(function(p){ return _normalizeProviderName_(p); }).filter(Boolean);
}

function _apiFirstNonEmpty_(values) {
  values = values || [];
  for (var i = 0; i < values.length; i++) {
    var v = values[i];
    if (v != null && String(v).trim() !== '') return v;
  }
  return '';
}
