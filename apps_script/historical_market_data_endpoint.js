/*
 * Read-only historical USD/JPY observation endpoint.
 *
 * This deliberately does not reuse the operational candle helpers: those
 * helpers populate caches and write workbook logs.  This endpoint only reads
 * Script Properties and performs provider HTTP requests.
 */

var HISTORICAL_USDJPY_ENDPOINT_SCHEMA_VERSION = 'presignal.historical_usdjpy_raw_observation.v1';
var HISTORICAL_USDJPY_ENDPOINT_PROVIDERS = ['tiingo', 'eodhd', 'massive', 'twelvedata'];

function apiFetchGovernedHistoricalUsdJpyObservation(params) {
  var request = _historicalUsdJpyValidateRequest_(params || {});
  var properties = PropertiesService.getScriptProperties();
  var attempts = [];
  var providers = _historicalUsdJpyRequestedProviders_(request);
  var firstSuccess = null;

  for (var i = 0; i < providers.length; i++) {
    var provider = providers[i];
    var attempt = _historicalUsdJpyFetchProvider_(provider, request, properties);
    attempts.push(attempt);
    if (!firstSuccess && attempt.status === 'SUCCESS') {
      firstSuccess = attempt;
    }
    if (request.mode === 'first_success' && attempt.status === 'SUCCESS') {
      return _historicalUsdJpyFirstSuccessResponse_(request, attempts, attempt, 'SUCCESS', '');
    }
  }

  if (request.mode === 'provider') {
    return _historicalUsdJpyProviderModeResponse_(request, attempts[0] || null);
  }
  if (request.mode === 'all_available') {
    return _historicalUsdJpyAllAvailableResponse_(request, attempts, firstSuccess);
  }
  return _historicalUsdJpyFirstSuccessResponse_(request, attempts, null, 'MISSING_OR_UNUSABLE', _historicalUsdJpyFinalReason_(attempts));
}

function _historicalUsdJpyValidateRequest_(params) {
  if (String(params.instrument || '').trim().toUpperCase() !== 'USD/JPY') {
    throw new Error('HISTORICAL_USDJPY_ENDPOINT_UNSUPPORTED_INSTRUMENT');
  }
  var timezone = String(params.timezone || 'UTC').trim().toUpperCase();
  if (timezone !== 'UTC') throw new Error('HISTORICAL_USDJPY_ENDPOINT_UNSUPPORTED_TIMEZONE');

  var requestedTimestamp = params.requested_timestamp == null ? '' : String(params.requested_timestamp);
  var windowStart = params.requested_window_start == null ? '' : String(params.requested_window_start);
  var windowEnd = params.requested_window_end == null ? '' : String(params.requested_window_end);
  if (requestedTimestamp) {
    var requestedMs = _historicalUsdJpyParseStrictUtc_(requestedTimestamp);
    if (windowStart || windowEnd) {
      if (!windowStart || !windowEnd) throw new Error('HISTORICAL_USDJPY_ENDPOINT_INVALID_WINDOW');
      if (_historicalUsdJpyParseStrictUtc_(windowStart) !== requestedMs || _historicalUsdJpyParseStrictUtc_(windowEnd) !== requestedMs) {
        throw new Error('HISTORICAL_USDJPY_ENDPOINT_TIMESTAMP_WINDOW_CONFLICT');
      }
    }
    windowStart = requestedTimestamp;
    windowEnd = requestedTimestamp;
  } else {
    if (!windowStart || !windowEnd) throw new Error('HISTORICAL_USDJPY_ENDPOINT_MISSING_TIMESTAMP');
  }

  var startMs = _historicalUsdJpyParseStrictUtc_(windowStart);
  var endMs = _historicalUsdJpyParseStrictUtc_(windowEnd);
  if (startMs > endMs) throw new Error('HISTORICAL_USDJPY_ENDPOINT_INVALID_WINDOW');
  var mode = _historicalUsdJpyValidateMode_(params.mode);
  var provider = _historicalUsdJpyValidateProvider_(params.provider, mode);
  return {
    request_identity: params.request_identity == null ? '' : String(params.request_identity),
    instrument: 'USD/JPY',
    requested_timestamp: requestedTimestamp,
    requested_window_start: windowStart,
    requested_window_end: windowEnd,
    timezone: timezone,
    start_ms: startMs,
    end_ms: endMs,
    mode: mode,
    provider: provider
  };
}

function _historicalUsdJpyValidateMode_(rawMode) {
  var mode = String(rawMode == null ? 'first_success' : rawMode).trim().toLowerCase();
  if (!mode) mode = 'first_success';
  if (['first_success', 'provider', 'all_available'].indexOf(mode) < 0) {
    throw new Error('HISTORICAL_USDJPY_ENDPOINT_UNSUPPORTED_MODE');
  }
  return mode;
}

function _historicalUsdJpyValidateProvider_(rawProvider, mode) {
  var provider = String(rawProvider == null ? '' : rawProvider).trim().toLowerCase();
  if (mode === 'provider') {
    if (!provider) throw new Error('HISTORICAL_USDJPY_ENDPOINT_PROVIDER_REQUIRED');
    if (HISTORICAL_USDJPY_ENDPOINT_PROVIDERS.indexOf(provider) < 0) {
      throw new Error('HISTORICAL_USDJPY_ENDPOINT_UNKNOWN_PROVIDER');
    }
    return provider;
  }
  if (provider && HISTORICAL_USDJPY_ENDPOINT_PROVIDERS.indexOf(provider) < 0) {
    throw new Error('HISTORICAL_USDJPY_ENDPOINT_UNKNOWN_PROVIDER');
  }
  return provider;
}

function _historicalUsdJpyRequestedProviders_(request) {
  if (request.mode === 'provider') return [request.provider];
  return HISTORICAL_USDJPY_ENDPOINT_PROVIDERS.slice();
}

function _historicalUsdJpyParseStrictUtc_(value) {
  var raw = String(value || '');
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(raw)) {
    throw new Error('HISTORICAL_USDJPY_ENDPOINT_INVALID_TIMESTAMP');
  }
  var millis = Date.parse(raw);
  if (!isFinite(millis)) throw new Error('HISTORICAL_USDJPY_ENDPOINT_INVALID_TIMESTAMP');
  return millis;
}

function _historicalUsdJpyFetchProvider_(provider, request, properties) {
  var propertyName = _historicalUsdJpyCredentialProperty_(provider);
  var key = properties.getProperty(propertyName);
  var base = {
    provider: provider,
    credential_property_name: propertyName,
    credential_available: !!key,
    requested_window_start: request.requested_window_start,
    requested_window_end: request.requested_window_end,
    http_status: null,
    status: '',
    missing_data_reason: '',
    source_resolution: 'ONE_MINUTE',
    observation_type: 'OHLC',
    observations: []
  };
  if (!key) {
    base.status = 'CREDENTIAL_UNAVAILABLE';
    base.missing_data_reason = 'CREDENTIAL_UNAVAILABLE';
    return base;
  }

  try {
    var response = _historicalUsdJpyProviderResponse_(provider, request, key);
    base.http_status = response.http_status;
    if (response.http_status !== 200) {
      base.status = 'TRANSPORT_FAILURE';
      base.missing_data_reason = 'HTTP_' + String(response.http_status);
      return base;
    }
    var observations = _historicalUsdJpyParseProviderRows_(provider, response.body, request);
    base.observations = observations;
    if (!observations.length) {
      base.status = 'OBSERVATION_UNAVAILABLE';
      base.missing_data_reason = 'NO_EXACT_TIMESTAMP_OBSERVATION';
      return base;
    }
    base.status = 'SUCCESS';
    return base;
  } catch (error) {
    base.status = 'TRANSPORT_FAILURE';
    base.missing_data_reason = 'PROVIDER_REQUEST_OR_PARSE_FAILURE';
    return base;
  }
}

function _historicalUsdJpyCredentialProperty_(provider) {
  return {
    tiingo: 'TIINGO_API_KEY',
    eodhd: 'EODHD_API_KEY',
    massive: 'MASSIVE_API_KEY',
    twelvedata: 'TWELVEDATA_API_KEY'
  }[provider];
}

function _historicalUsdJpyProviderResponse_(provider, request, key) {
  var startIso = _historicalUsdJpyIso_(request.start_ms);
  var endIso = _historicalUsdJpyIso_(request.end_ms);
  var url = '';
  if (provider === 'tiingo') {
    url = 'https://api.tiingo.com/tiingo/fx/USDJPY/prices?startDate=' + encodeURIComponent(startIso)
      + '&endDate=' + encodeURIComponent(endIso) + '&resampleFreq=1min&token=' + encodeURIComponent(key);
  } else if (provider === 'eodhd') {
    url = 'https://eodhd.com/api/intraday/USDJPY.FOREX?api_token=' + encodeURIComponent(key)
      + '&fmt=json&interval=1m&from=' + encodeURIComponent(String(Math.floor(request.start_ms / 1000)))
      + '&to=' + encodeURIComponent(String(Math.floor(request.end_ms / 1000)));
  } else if (provider === 'massive') {
    url = 'https://api.massive.com/v2/aggs/ticker/C:USDJPY/range/1/minute/'
      + encodeURIComponent(_historicalUsdJpyDate_(request.start_ms)) + '/' + encodeURIComponent(_historicalUsdJpyDate_(request.end_ms))
      + '?sort=asc&limit=50000&apiKey=' + encodeURIComponent(key);
  } else if (provider === 'twelvedata') {
    url = 'https://api.twelvedata.com/time_series?symbol=USD%2FJPY&interval=1min&start_date='
      + encodeURIComponent(startIso.replace('Z', '')) + '&end_date=' + encodeURIComponent(endIso.replace('Z', ''))
      + '&timezone=UTC&order=asc&apikey=' + encodeURIComponent(key);
  } else {
    throw new Error('HISTORICAL_USDJPY_ENDPOINT_UNKNOWN_PROVIDER');
  }
  var response = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
    validateHttpsCertificates: true
  });
  return { http_status: response.getResponseCode(), body: response.getContentText() };
}

function _historicalUsdJpyParseProviderRows_(provider, body, request) {
  var payload = JSON.parse(body);
  var rows = [];
  if (provider === 'tiingo') rows = Array.isArray(payload) ? payload : [];
  else if (provider === 'eodhd') rows = Array.isArray(payload) ? payload : [];
  else if (provider === 'massive') rows = payload && Array.isArray(payload.results) ? payload.results : [];
  else if (provider === 'twelvedata') rows = payload && Array.isArray(payload.values) ? payload.values : [];

  return rows.map(function(row) {
    var rawTimestamp = provider === 'tiingo' ? (row.date || row.datetime || row.timestamp)
      : provider === 'eodhd' ? (row.timestamp != null ? row.timestamp : row.datetime)
      : provider === 'massive' ? row.t
      : row.datetime;
    var timestampMs = _historicalUsdJpyProviderTimestampMs_(provider, rawTimestamp);
    var observation = {
      timestamp: timestampMs == null ? null : _historicalUsdJpyIso_(timestampMs),
      timestamp_raw: rawTimestamp == null ? null : String(rawTimestamp),
      provider_returned_timestamp_raw: rawTimestamp == null ? null : String(rawTimestamp),
      returned_observation_timestamp: timestampMs == null ? null : _historicalUsdJpyIso_(timestampMs),
      open: _historicalUsdJpyFiniteNumber_(row.open != null ? row.open : row.o),
      high: _historicalUsdJpyFiniteNumber_(row.high != null ? row.high : row.h),
      low: _historicalUsdJpyFiniteNumber_(row.low != null ? row.low : row.l),
      close: _historicalUsdJpyFiniteNumber_(row.close != null ? row.close : row.c),
      accepted_raw_price_field: 'close',
      accepted_raw_price: _historicalUsdJpyFiniteNumber_(row.close != null ? row.close : row.c),
      bid: null,
      ask: null,
      midpoint: null,
      source_observation_id: null
    };
    return { timestamp_ms: timestampMs, observation: observation };
  }).filter(function(item) {
    return item.timestamp_ms != null && item.timestamp_ms >= request.start_ms && item.timestamp_ms <= request.end_ms
      && item.observation.open != null && item.observation.high != null && item.observation.low != null
      && item.observation.close != null;
  }).map(function(item) {
    return item.observation;
  }).sort(function(a, b) {
    return a.returned_observation_timestamp < b.returned_observation_timestamp ? -1 : a.returned_observation_timestamp > b.returned_observation_timestamp ? 1 : 0;
  });
}

function _historicalUsdJpyProviderTimestampMs_(provider, raw) {
  if (raw == null || raw === '') return null;
  if (provider === 'eodhd' || provider === 'massive') {
    var epoch = Number(raw);
    if (isFinite(epoch)) return epoch < 1000000000000 ? epoch * 1000 : epoch;
  }
  var text = String(raw);
  if (!/Z$/.test(text) && !/[+-]\d{2}:?\d{2}$/.test(text)) text = text.replace(' ', 'T') + 'Z';
  var millis = Date.parse(text);
  return isFinite(millis) ? millis : null;
}

function _historicalUsdJpyFiniteNumber_(value) {
  if (value == null || value === '') return null;
  var number = Number(String(value).replace(/,/g, ''));
  return isFinite(number) ? number : null;
}

function _historicalUsdJpyFirstSuccessResponse_(request, attempts, selected, status, reason) {
  var observations = selected ? selected.observations : [];
  return {
    schema_version: HISTORICAL_USDJPY_ENDPOINT_SCHEMA_VERSION,
    request_identity: request.request_identity,
    instrument: request.instrument,
    mode: request.mode,
    requested_provider: request.provider || '',
    requested_timestamp: request.requested_timestamp,
    requested_window_start: request.requested_window_start,
    requested_window_end: request.requested_window_end,
    timezone: request.timezone,
    provider_hierarchy_attempted: attempts.map(function(attempt) { return attempt.provider; }),
    provider_attempts: attempts,
    selected_provider: selected ? selected.provider : '',
    status: status,
    missing_data_reason: reason,
    returned_observation_count: observations.length,
    observations: observations,
    response_generated_at: _historicalUsdJpyIso_(new Date().getTime())
  };
}

function _historicalUsdJpyProviderModeResponse_(request, attempt) {
  var providerResult = _historicalUsdJpyProviderResult_(request, attempt);
  return {
    schema_version: HISTORICAL_USDJPY_ENDPOINT_SCHEMA_VERSION,
    request_identity: request.request_identity,
    instrument: request.instrument,
    mode: request.mode,
    requested_provider: request.provider,
    requested_timestamp: request.requested_timestamp,
    requested_window_start: request.requested_window_start,
    requested_window_end: request.requested_window_end,
    timezone: request.timezone,
    provider_hierarchy_attempted: [request.provider],
    provider_attempts: attempt ? [attempt] : [],
    selected_provider: providerResult.status === 'SUCCESS' ? providerResult.provider : '',
    status: providerResult.status === 'SUCCESS' ? 'SUCCESS' : 'MISSING_OR_UNUSABLE',
    missing_data_reason: providerResult.status === 'SUCCESS' ? '' : providerResult.error_code,
    returned_observation_count: providerResult.observation_count,
    observations: providerResult.observations,
    provider_result: providerResult,
    response_generated_at: _historicalUsdJpyIso_(new Date().getTime())
  };
}

function _historicalUsdJpyAllAvailableResponse_(request, attempts, firstSuccess) {
  var providerResults = attempts.map(function(attempt) {
    return _historicalUsdJpyProviderResult_(request, attempt);
  });
  return {
    schema_version: HISTORICAL_USDJPY_ENDPOINT_SCHEMA_VERSION,
    request_identity: request.request_identity,
    instrument: request.instrument,
    mode: request.mode,
    requested_provider: '',
    requested_timestamp: request.requested_timestamp,
    requested_window_start: request.requested_window_start,
    requested_window_end: request.requested_window_end,
    timezone: request.timezone,
    provider_hierarchy_attempted: attempts.map(function(attempt) { return attempt.provider; }),
    provider_attempts: attempts,
    selected_provider: '',
    status: firstSuccess ? 'SUCCESS' : 'MISSING_OR_UNUSABLE',
    missing_data_reason: firstSuccess ? '' : _historicalUsdJpyFinalReason_(attempts),
    returned_observation_count: firstSuccess ? firstSuccess.observations.length : 0,
    observations: firstSuccess ? firstSuccess.observations : [],
    provider_results: providerResults,
    comparable_provider_count: providerResults.filter(function(item) { return item.status === 'SUCCESS'; }).length,
    response_generated_at: _historicalUsdJpyIso_(new Date().getTime())
  };
}

function _historicalUsdJpyProviderResult_(request, attempt) {
  var status = attempt ? attempt.status : 'UNAVAILABLE';
  var observations = attempt && attempt.observations ? attempt.observations : [];
  var errorCode = '';
  if (status !== 'SUCCESS') {
    errorCode = attempt && attempt.missing_data_reason ? attempt.missing_data_reason : 'UNAVAILABLE';
  }
  return {
    provider: attempt ? attempt.provider : '',
    status: status,
    instrument: request.instrument,
    request_start: request.requested_window_start,
    request_end: request.requested_window_end,
    source_resolution: attempt && attempt.source_resolution ? attempt.source_resolution : 'UNKNOWN',
    observation_type: attempt && attempt.observation_type ? attempt.observation_type : 'UNKNOWN',
    observation_count: observations.length,
    observations: observations,
    error_code: errorCode,
    error_summary: _historicalUsdJpyErrorSummary_(status, errorCode),
    credential_route_present: !!(attempt && attempt.credential_available)
  };
}

function _historicalUsdJpyErrorSummary_(status, code) {
  if (status === 'SUCCESS') return '';
  if (code === 'CREDENTIAL_UNAVAILABLE') return 'Credential route unavailable.';
  if (code === 'NO_EXACT_TIMESTAMP_OBSERVATION') return 'No exact timestamp observations inside requested window.';
  if (String(code || '').indexOf('HTTP_') === 0) return 'Provider HTTP failure.';
  if (code === 'PROVIDER_REQUEST_OR_PARSE_FAILURE') return 'Provider request or parse failure.';
  return 'Provider unavailable.';
}

function _historicalUsdJpyFinalReason_(attempts) {
  var reasons = attempts.map(function(attempt) { return attempt.missing_data_reason; });
  return reasons.indexOf('NO_EXACT_TIMESTAMP_OBSERVATION') >= 0 ? 'NO_EXACT_TIMESTAMP_OBSERVATION' : 'NO_USABLE_PROVIDER_RESPONSE';
}

function _historicalUsdJpyIso_(millis) {
  return new Date(millis).toISOString();
}

function _historicalUsdJpyDate_(millis) {
  return _historicalUsdJpyIso_(millis).slice(0, 10);
}
