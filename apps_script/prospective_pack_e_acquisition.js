/*
 * Caller-controlled prospective Pack E acquisition adapters.
 *
 * These adapters deliberately reuse only the v2B fetch and row-normalization
 * functions.  They do not invoke _v2bBuildSeriesCache_, _buildMarketContextPack_,
 * or any spreadsheet writer.  A caller supplies the approved source binding,
 * bounded query, lineage, and cutoff; the adapter makes one fetch attempt and
 * returns one NATIVE_ACQUISITION_RECORD (including a frozen failure record).
 */

var PROSPECTIVE_PACK_E_ADAPTER_VERSION_V1 = 'presignal.prospective_pack_e_acquisition.v1';

var PROSPECTIVE_PACK_E_SOURCE_SPECS_V1 = {
  KSRC_FMP: {
    adapter_identity: 'apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord',
    configuration_reference: 'Apps Script FMP_API_KEY resolver (CFG.FMP_API_KEY or Script Property FMP_API_KEY)',
    credential_reference_type: 'APPS_SCRIPT_SCRIPT_PROPERTY_API_KEY',
    fetch: function(symbol, startDate, endDate) { return _v2bFetchFmpHistory_(symbol, startDate, endDate); }
  },
  KSRC_FRED: {
    adapter_identity: 'apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord',
    configuration_reference: 'Apps Script Script Property FRED_API_KEY',
    credential_reference_type: 'APPS_SCRIPT_SCRIPT_PROPERTY_API_KEY',
    fetch: function(symbol, startDate, endDate) { return _v2bFetchFredHistory_(symbol, startDate, endDate); }
  },
  KSRC_EODHD: {
    adapter_identity: 'apps_script/prospective_pack_e_acquisition.js:apiBuildProspectivePackENativeAcquisitionRecord',
    configuration_reference: 'Apps Script EODHD API-key resolver',
    credential_reference_type: 'APPS_SCRIPT_SCRIPT_PROPERTY_API_KEY',
    fetch: function(symbol, startDate, endDate) { return _v2bFetchEodhdHistory_(symbol, startDate, endDate); }
  }
};

function _prospectivePackEText_(value) {
  return value === null || value === undefined ? '' : String(value).trim();
}

function _prospectivePackESort_(value) {
  if (Array.isArray(value)) return value.map(_prospectivePackESort_);
  if (value && typeof value === 'object') {
    var out = {};
    Object.keys(value).sort().forEach(function(key) { out[key] = _prospectivePackESort_(value[key]); });
    return out;
  }
  return value;
}

function _prospectivePackECanonicalJson_(value) {
  return JSON.stringify(_prospectivePackESort_(value));
}

function _prospectivePackESha256_(value) {
  var bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, _prospectivePackECanonicalJson_(value), Utilities.Charset.UTF_8);
  return 'sha256:' + bytes.map(function(byte) {
    var normalized = byte < 0 ? byte + 256 : byte;
    return ('0' + normalized.toString(16)).slice(-2);
  }).join('');
}

function _prospectivePackERequire_(value, code) {
  if (!_prospectivePackEText_(value)) throw new Error(code);
  return _prospectivePackEText_(value);
}

function _prospectivePackEUtc_(value, code) {
  var date = new Date(_prospectivePackEText_(value));
  if (!isFinite(date.getTime())) throw new Error(code);
  return date.toISOString();
}

function _prospectivePackEDateOnly_(value, code) {
  var text = _prospectivePackEText_(value);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) throw new Error(code);
  return text;
}

function _prospectivePackEFailure_(request, classification, reason) {
  var sourceId = _prospectivePackEText_(request.source_id);
  var identity = {
    adapter_identity: _prospectivePackEText_(request.adapter_identity),
    episode_id: _prospectivePackEText_(request.episode_id),
    request_identity: _prospectivePackEText_(request.request_identity),
    source_id: sourceId,
    source_url_or_key: _prospectivePackEText_(request.source_url_or_key),
    status: 'UNAVAILABLE'
  };
  return {
    object: 'NATIVE_ACQUISITION_RECORD',
    schema_version: PROSPECTIVE_PACK_E_ADAPTER_VERSION_V1,
    acquisition_record_id: 'NACQ_' + _prospectivePackESha256_(identity).slice(7, 27),
    episode_id: _prospectivePackEText_(request.episode_id),
    pack_a_identity: _prospectivePackEText_(request.pack_a_identity),
    request_identity: _prospectivePackEText_(request.request_identity),
    forecast_cutoff_ts: _prospectivePackEText_(request.forecast_cutoff_ts),
    source_id: sourceId,
    adapter_identity: _prospectivePackEText_(request.adapter_identity),
    configuration_reference: _prospectivePackEText_(request.configuration_reference),
    credential_reference_type: _prospectivePackEText_(request.credential_reference_type),
    source_identity: _prospectivePackEText_(request.source_identity),
    source_url_or_key: _prospectivePackEText_(request.source_url_or_key),
    source_type: _prospectivePackEText_(request.source_type),
    query_identity: _prospectivePackEText_(request.query_identity),
    retrieval_timestamp: _prospectivePackEText_(request.retrieval_timestamp),
    acquisition_timestamp: _prospectivePackEText_(request.retrieval_timestamp),
    acquisition_method: 'caller_controlled_existing_v2_fetch',
    status: 'UNAVAILABLE',
    error_classification: classification,
    reason: reason,
    raw_acquired_content: '',
    normalized_acquired_content: '',
    raw_checksum: 'sha256:',
    normalized_checksum: 'sha256:',
    source_items: []
  };
}

function _prospectivePackENormalizeRows_(rows) {
  return (rows || []).map(function(row) {
    var date = _prospectivePackEText_(row && row.date).slice(0, 10);
    var value = Number(row && row.value);
    return { date: date, value: isFinite(value) ? value : null };
  }).filter(function(row) { return /^\d{4}-\d{2}-\d{2}$/.test(row.date) && isFinite(row.value); })
    .sort(function(left, right) { return left.date < right.date ? -1 : (left.date > right.date ? 1 : 0); });
}

function _prospectivePackEValidationOnly_(request) {
  request = request || {};
  return {
    object: 'PROSPECTIVE_PACK_E_CAPABILITY_METADATA',
    schema_version: PROSPECTIVE_PACK_E_ADAPTER_VERSION_V1,
    function_identity: 'apiBuildProspectivePackENativeAcquisitionRecord',
    adapter_identity: _prospectivePackEText_(request.adapter_identity),
    source_id: _prospectivePackEText_(request.source_id),
    validation_only: true,
    external_source_dispatch_count: 0,
    writer_count: 0,
    retry_budget: 0,
    writer_behavior: 'none',
    scientific_behavior_changed: false,
    supported_sources: Object.keys(PROSPECTIVE_PACK_E_SOURCE_SPECS_V1).sort()
  };
}

function _prospectivePackEBuildRecordWithFetcher_(request, fetcher) {
  request = request || {};
  var sourceId = _prospectivePackERequire_(request.source_id, 'SOURCE_ID_REQUIRED');
  var spec = PROSPECTIVE_PACK_E_SOURCE_SPECS_V1[sourceId];
  if (!spec) throw new Error('SOURCE_NOT_APPROVED:' + sourceId);
  var adapterIdentity = _prospectivePackERequire_(request.adapter_identity, 'ADAPTER_ID_REQUIRED');
  if (adapterIdentity !== spec.adapter_identity) throw new Error('ADAPTER_IDENTITY_MISMATCH');
  if (_prospectivePackERequire_(request.configuration_reference, 'CONFIGURATION_REFERENCE_REQUIRED') !== spec.configuration_reference) throw new Error('CONFIGURATION_REFERENCE_MISMATCH');
  if (_prospectivePackERequire_(request.credential_reference_type, 'CREDENTIAL_REFERENCE_TYPE_REQUIRED') !== spec.credential_reference_type) throw new Error('CREDENTIAL_REFERENCE_TYPE_MISMATCH');
  var episodeId = _prospectivePackERequire_(request.episode_id, 'EPISODE_ID_REQUIRED');
  var packA = _prospectivePackERequire_(request.pack_a_identity, 'PACK_A_IDENTITY_REQUIRED');
  var requestId = _prospectivePackERequire_(request.request_identity, 'REQUEST_ID_REQUIRED');
  var field = _prospectivePackERequire_(request.canonical_field, 'CANONICAL_FIELD_REQUIRED');
  var queryIdentity = _prospectivePackERequire_(request.query_identity, 'QUERY_IDENTITY_REQUIRED');
  var symbol = _prospectivePackERequire_(request.query_symbol, 'QUERY_SYMBOL_REQUIRED');
  var startDate = _prospectivePackEDateOnly_(request.bounded_start_date, 'BOUNDED_START_DATE_REQUIRED');
  var endDate = _prospectivePackEDateOnly_(request.bounded_end_date, 'BOUNDED_END_DATE_REQUIRED');
  if (startDate > endDate) throw new Error('BOUNDED_DATE_RANGE_INVALID');
  var cutoff = _prospectivePackEUtc_(request.forecast_cutoff_ts, 'FORECAST_CUTOFF_REQUIRED');
  var retrieval = _prospectivePackEUtc_(request.retrieval_timestamp, 'RETRIEVAL_TIMESTAMP_REQUIRED');
  var asOf = _prospectivePackEUtc_(request.as_of_timestamp, 'AS_OF_TIMESTAMP_REQUIRED');
  if (retrieval > cutoff || asOf > cutoff) throw new Error('SOURCE_TEMPORAL_CONTRACT_UNSUPPORTED');
  var sourceIdentity = _prospectivePackERequire_(request.source_identity, 'SOURCE_IDENTITY_REQUIRED');
  var sourceKey = _prospectivePackERequire_(request.source_url_or_key, 'SOURCE_URL_OR_KEY_REQUIRED');
  var sourceType = _prospectivePackERequire_(request.source_type, 'SOURCE_TYPE_REQUIRED');
  var rows;
  try {
    rows = _prospectivePackENormalizeRows_((fetcher || spec.fetch)(symbol, startDate, endDate));
  } catch (error) {
    return _prospectivePackEFailure_(request, 'SOURCE_ACCESS_NOT_AUTHORIZED', 'FETCH_FAILED:' + String(error && error.message || error));
  }
  var selected = null;
  var asOfDate = asOf.slice(0, 10);
  rows.forEach(function(row) { if (row.date <= asOfDate) selected = row; });
  if (!selected) return _prospectivePackEFailure_(request, 'SOURCE_CONTENT_NOT_FOUND', 'NO_OBSERVATION_AT_OR_BEFORE_AS_OF');
  var sourceTimestamp = _prospectivePackEUtc_(selected.date + 'T00:00:00Z', 'SOURCE_TIMESTAMP_INVALID');
  if (sourceTimestamp > cutoff) throw new Error('SOURCE_TEMPORAL_CONTRACT_UNSUPPORTED');
  var rawEvidence = { source_id: sourceId, query_identity: queryIdentity, query_symbol: symbol, bounded_start_date: startDate, bounded_end_date: endDate, rows: rows };
  var normalizedEvidence = { canonical_field: field, selected_observation: selected, source_identity: sourceIdentity, source_timestamp: sourceTimestamp, as_of_timestamp: asOf };
  var identity = { episode_id: episodeId, pack_a_identity: packA, request_identity: requestId, source_id: sourceId, canonical_field: field, source_identity: sourceIdentity, source_timestamp: sourceTimestamp };
  return {
    object: 'NATIVE_ACQUISITION_RECORD',
    schema_version: PROSPECTIVE_PACK_E_ADAPTER_VERSION_V1,
    acquisition_record_id: 'NACQ_' + _prospectivePackESha256_(identity).slice(7, 27),
    episode_id: episodeId,
    pack_a_identity: packA,
    request_identity: requestId,
    forecast_cutoff_ts: cutoff,
    source_id: sourceId,
    adapter_identity: adapterIdentity,
    configuration_reference: spec.configuration_reference,
    credential_reference_type: spec.credential_reference_type,
    source_identity: sourceIdentity,
    source_url_or_key: sourceKey,
    source_type: sourceType,
    query_identity: queryIdentity,
    retrieval_timestamp: retrieval,
    acquisition_timestamp: retrieval,
    source_timestamp: sourceTimestamp,
    as_of_timestamp: asOf,
    acquisition_method: 'caller_controlled_existing_v2_fetch',
    status: 'SUPPLIED',
    error_classification: '',
    reason: '',
    raw_acquired_content: _prospectivePackECanonicalJson_(rawEvidence),
    normalized_acquired_content: _prospectivePackECanonicalJson_(normalizedEvidence),
    raw_checksum: _prospectivePackESha256_(rawEvidence),
    normalized_checksum: _prospectivePackESha256_(normalizedEvidence),
    source_items: [{
      canonical_field: field,
      value: selected.value,
      value_type: _prospectivePackEText_(request.value_type) || 'scalar',
      source_id: sourceId,
      source_name: _prospectivePackEText_(request.source_name) || sourceId,
      source_identity: sourceIdentity,
      source_timestamp: sourceTimestamp,
      as_of_timestamp: asOf,
      acquisition_timestamp: retrieval,
      acquisition_method: 'caller_controlled_existing_v2_fetch'
    }]
  };
}

function apiBuildProspectivePackENativeAcquisitionRecord(request) {
  request = request || {};
  if (request.validation_only === true) return _prospectivePackEValidationOnly_(request);
  return _prospectivePackEBuildRecordWithFetcher_(request, null);
}
