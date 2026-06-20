/*******************************************************
 * character_residual_architecture.js
 * - Diagnostic-only Character Residual Architecture v1
 * - Derives deterministic baseline E and provider residual vectors
 * - Reads existing sheets only; does not call providers or change prediction behavior
 *******************************************************/

function menuBuildCharacterResidualArchitecture_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildCharacterResidualArchitecture_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Character residual architecture -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Baseline=' + (res.baseline_rows_written || 0) +
      ' | Residuals=' + (res.residual_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0),
      'Character Residual Architecture',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Character residual architecture -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildCharacterResidualArchitecture_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];
  var sources = _characterResidualLoadSources_(warnings);
  var baselineMap = _characterResidualBuildBaselineMap_(sources, generatedTs, warnings);
  var baselineRows = _characterResidualBaselineRows_(baselineMap, generatedTs);
  var residualRows = _characterResidualResidualRows_(sources, baselineMap, generatedTs, warnings);
  var summaryRows = _characterResidualSummaryRows_(residualRows, generatedTs);
  var familyRows = _characterResidualFamilySummaryRows_(residualRows, generatedTs);
  var disagreementRows = _characterResidualDisagreementRows_(residualRows, baselineMap, generatedTs);

  _sortCharacterResidualBaselineRows_(baselineRows);
  _sortCharacterResidualResidualRows_(residualRows);
  _sortCharacterResidualSummaryRows_(summaryRows);
  _sortCharacterResidualFamilySummaryRows_(familyRows);
  _sortCharacterResidualDisagreementRows_(disagreementRows);

  var baselineSheet = getDiagnosticsSheet_('Character_Baseline_E', _characterResidualBaselineHeaders_(), warnings);
  var residualSheet = getDiagnosticsSheet_('Provider_Character_Residuals', _characterResidualResidualHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Provider_Character_Summary', _characterResidualSummaryHeaders_(), warnings);
  var familySheet = getDiagnosticsSheet_('Provider_Character_Family_Summary', _characterResidualFamilySummaryHeaders_(), warnings);
  var disagreementSheet = getDiagnosticsSheet_('Character_Disagreement_Report', _characterResidualDisagreementHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    baselineSheet.sheet,
    baselineSheet.headers,
    _characterResidualObjectsToRows_(baselineRows, baselineSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    residualSheet.sheet,
    residualSheet.headers,
    _characterResidualObjectsToRows_(residualRows, residualSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    summarySheet.sheet,
    summarySheet.headers,
    _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    familySheet.sheet,
    familySheet.headers,
    _characterResidualObjectsToRows_(familyRows, familySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    disagreementSheet.sheet,
    disagreementSheet.headers,
    _characterResidualObjectsToRows_(disagreementRows, disagreementSheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    baseline_sheet: baselineSheet.sheet.getName(),
    residual_sheet: residualSheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    family_summary_sheet: familySheet.sheet.getName(),
    disagreement_sheet: disagreementSheet.sheet.getName(),
    baseline_rows_written: baselineRows.length,
    residual_rows_written: residualRows.length,
    summary_rows_written: summaryRows.length,
    family_summary_rows_written: familyRows.length,
    disagreement_rows_written: disagreementRows.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function getOrCreateCharacterBaselineSheet_() {
  return _getOrCreateSheet_('Character_Baseline_E');
}

function getOrCreateProviderCharacterResidualsSheet_() {
  return _getOrCreateSheet_('Provider_Character_Residuals');
}

function getOrCreateProviderCharacterSummarySheet_() {
  return _getOrCreateSheet_('Provider_Character_Summary');
}

function getOrCreateProviderCharacterFamilySummarySheet_() {
  return _getOrCreateSheet_('Provider_Character_Family_Summary');
}

function getOrCreateCharacterDisagreementReportSheet_() {
  return _getOrCreateSheet_('Character_Disagreement_Report');
}

function ensureCharacterBaselineHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _characterResidualBaselineHeaders_());
}

function ensureProviderCharacterResidualHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _characterResidualResidualHeaders_());
}

function ensureProviderCharacterSummaryHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _characterResidualSummaryHeaders_());
}

function ensureProviderCharacterFamilySummaryHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _characterResidualFamilySummaryHeaders_());
}

function ensureCharacterDisagreementReportHeaders_(sheet) {
  return _ensureOutcomeLedgerHeadersAppendOnly_(sheet, _characterResidualDisagreementHeaders_());
}

function _characterResidualBaselineHeaders_() {
  return [
    'generated_ts',
    'event_id',
    'batch_id',
    'type',
    'indicator_name',
    'country',
    'release_ts',
    'outcome_family',
    'consensus_value',
    'prev_revision',
    'actual_value',
    'baseline_version',
    'baseline_value',
    'baseline_direction_vs_consensus',
    'baseline_confidence',
    'baseline_reason_codes',
    'baseline_available_fields',
    'baseline_missing_fields',
    'raw_baseline_json'
  ];
}

function _characterResidualResidualHeaders_() {
  return [
    'generated_ts',
    'event_id',
    'batch_id',
    'type',
    'indicator_name',
    'country',
    'release_ts',
    'outcome_family',
    'provider',
    'ai_forecast_value',
    'qualitative_result',
    'actual_value',
    'baseline_version',
    'baseline_value',
    'baseline_direction_vs_consensus',
    'baseline_confidence',
    'value_delta_from_baseline',
    'abs_value_delta_from_baseline',
    'direction_delta_from_baseline',
    'emphasized_factors',
    'ignored_factors',
    'risk_language',
    'uncertainty_pattern',
    'confidence_delta_from_baseline',
    'inferred_confidence_flag',
    'rationale_style_tags',
    'rationale_short',
    'rationale_preview',
    'raw_character_vector_json'
  ];
}

function _characterResidualSummaryHeaders_() {
  return [
    'generated_ts',
    'provider',
    'row_count',
    'avg_value_delta_from_baseline',
    'avg_abs_value_delta_from_baseline',
    'provider_more_positive_count',
    'provider_more_negative_count',
    'same_direction_count',
    'provider_flat_vs_directional_count',
    'provider_directional_vs_flat_count',
    'top_emphasized_factors',
    'top_ignored_available_factors',
    'dominant_risk_language',
    'dominant_uncertainty_pattern',
    'character_stability_note'
  ];
}

function _characterResidualFamilySummaryHeaders_() {
  return [
    'generated_ts',
    'provider',
    'outcome_family',
    'row_count',
    'avg_value_delta_from_baseline',
    'avg_abs_value_delta_from_baseline',
    'direction_delta_distribution',
    'top_emphasized_factors',
    'top_ignored_available_factors',
    'risk_language_distribution',
    'uncertainty_pattern_distribution',
    'sample_depth_warning'
  ];
}

function _characterResidualDisagreementHeaders_() {
  return [
    'generated_ts',
    'event_id',
    'indicator_name',
    'release_ts',
    'outcome_family',
    'baseline_value',
    'baseline_direction_vs_consensus',
    'provider_count',
    'value_delta_range',
    'direction_disagreement_level',
    'factor_disagreement_level',
    'providers_positive',
    'providers_negative',
    'providers_flat',
    'disagreement_summary',
    'actual_value',
    'which_provider_closest_to_actual',
    'notes'
  ];
}

function _characterResidualLoadSources_(warnings) {
  var out = {
    eventsBundle: null,
    predictionsBundle: null,
    featurePackAuditBundle: null,
    v2bCoreAuditBundle: null
  };

  var eventRef = _characterResidualReadSheetBundle_('Event', warnings, true);
  if (eventRef) out.eventsBundle = eventRef;

  var predRef = _characterResidualReadSheetBundle_('Predictions', warnings, false);
  if (predRef) {
    predRef.rows = _characterResidualDedupePredictionRows_(predRef.rows, predRef.idx);
    out.predictionsBundle = predRef;
  }

  var featurePackRef = _characterResidualReadSheetBundle_('Feature_Pack_Audit', warnings, false);
  if (featurePackRef) out.featurePackAuditBundle = featurePackRef;

  var v2bCoreRef = _characterResidualReadSheetBundle_('Feature_Pack_v2B_Core_Audit', warnings, false);
  if (v2bCoreRef) out.v2bCoreAuditBundle = v2bCoreRef;

  return out;
}

function _characterResidualReadSheetBundle_(sheetName, warnings, canonicalEventSheet) {
  try {
    var ref = getSheetForRead_(sheetName);
    if (!ref || !ref.sheet) return null;
    var headers = getHeaderNames(ref.sheet);
    if (!headers || !headers.length) {
      warnings.push('missing_headers:' + sheetName);
      return null;
    }
    var rows = _readDataRows_(ref.sheet);
    var idx = _headerIndexMap_(headers);
    return {
      sheet: ref.sheet,
      headers: headers,
      idx: idx,
      rows: rows,
      workbook_type: ref.workbook_type || '',
      sheet_name: sheetName,
      canonical_event_sheet: !!canonicalEventSheet
    };
  } catch (e) {
    warnings.push('missing_sheet:' + sheetName);
    return null;
  }
}

function _characterResidualDedupePredictionRows_(rows, predIdx) {
  var latestByKey = {};
  var order = [];
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i];
    if (!_characterResidualIsUsablePredictionRow_(row, predIdx)) continue;
    var eventId = String(_predValue_(row, predIdx, 'event_id') || '').trim();
    var aiName = String(_predValue_(row, predIdx, 'ai_name') || '').trim();
    if (!eventId || !aiName) continue;
    var key = eventId + '|' + aiName;
    if (!latestByKey.hasOwnProperty(key)) {
      latestByKey[key] = row;
      order.push(key);
      continue;
    }
    if (_characterResidualPredictionRowIsNewer_(row, latestByKey[key], predIdx)) {
      latestByKey[key] = row;
    }
  }
  var out = [];
  for (var j = 0; j < order.length; j++) out.push(latestByKey[order[j]]);
  return out;
}

function _characterResidualIsUsablePredictionRow_(row, idx) {
  return !!row && (!!String(_predValue_(row, idx, 'event_id') || '').trim() || !!String(_predValue_(row, idx, 'ai_name') || '').trim());
}

function _characterResidualPredictionRowIsNewer_(candidate, existing, predIdx) {
  var candidateCreatedMs = _characterResidualDateMs_(_predValue_(candidate, predIdx, 'created_ts'));
  var existingCreatedMs = _characterResidualDateMs_(_predValue_(existing, predIdx, 'created_ts'));
  if (candidateCreatedMs !== existingCreatedMs) return candidateCreatedMs > existingCreatedMs;
  var candidateEvalMs = _characterResidualDateMs_(_predValue_(candidate, predIdx, 'eval_ts'));
  var existingEvalMs = _characterResidualDateMs_(_predValue_(existing, predIdx, 'eval_ts'));
  if (candidateEvalMs !== existingEvalMs) return candidateEvalMs > existingEvalMs;
  return true;
}

function _characterResidualDateMs_(value) {
  var s = String(value || '').trim();
  if (!s) return 0;
  var d = new Date(s);
  var ms = d.getTime();
  return isFinite(ms) ? ms : 0;
}

function _characterResidualBuildBaselineMap_(sources, generatedTs, warnings) {
  var eventBundle = sources.eventsBundle || null;
  var predBundle = sources.predictionsBundle || null;
  var eventMap = _characterResidualBuildEventMap_(eventBundle, warnings);
  var contextMap = _characterResidualBuildContextMap_(sources.featurePackAuditBundle, sources.v2bCoreAuditBundle, warnings);
  var eventIds = {};
  var predIdx = predBundle ? predBundle.idx : {};

  Object.keys(eventMap).forEach(function(key) { eventIds[key] = true; });
  for (var i = 0; i < ((predBundle && predBundle.rows) || []).length; i++) {
    var pred = predBundle.rows[i];
    var eventId = String(_predValue_(pred, predIdx, 'event_id') || '').trim();
    if (eventId) eventIds[eventId] = true;
  }

  var baselineMap = {};
  Object.keys(eventIds).sort().forEach(function(eventId) {
    var eventMeta = eventMap[eventId] || {};
    var predictionRow = _characterResidualFirstPredictionForEvent_(predBundle, eventId);
    var contextMeta = contextMap[eventId] || {};
    baselineMap[eventId] = _characterResidualBuildBaselineRecord_(generatedTs, eventId, eventMeta, predictionRow, predIdx, contextMeta);
  });
  return baselineMap;
}

function _characterResidualBuildEventMap_(eventBundle, warnings) {
  var out = {};
  var rows = (eventBundle && eventBundle.rows) || [];
  var idx = (eventBundle && eventBundle.idx) || {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var eventId = String(_predValue_(row, idx, 'event_id') || '').trim();
    if (!eventId) continue;
    if (!_characterResidualEventRowIsCanonical_(row, idx)) continue;
    out[eventId] = {
      event_id: eventId,
      batch_id: String(_predValue_(row, idx, 'batch_id') || '').trim(),
      type: String(_predValue_(row, idx, 'type') || '').trim(),
      indicator_name: String(_predValue_(row, idx, 'indicator_name') || '').trim(),
      country: String(_predValue_(row, idx, 'country') || '').trim(),
      release_ts: String(_predValue_(row, idx, 'release_ts') || '').trim(),
      genre: String(_predValue_(row, idx, 'genre') || '').trim(),
      consensus_value: _characterResidualNum_(_predValue_(row, idx, 'consensus_value')),
      prev_revision: _characterResidualNum_(_predValue_(row, idx, 'prev_revision')),
      actual_value: _characterResidualNum_(_predValue_(row, idx, 'released_value')),
      actual_ts: String(_predValue_(row, idx, 'released_ts') || '').trim(),
      importance: String(_predValue_(row, idx, 'importance') || '').trim(),
      source_sheet: 'Event'
    };
  }
  return out;
}

function _characterResidualEventRowIsCanonical_(row, idx) {
  var obj = String(_predValue_(row, idx, 'object') || '').trim().toLowerCase();
  return !obj || obj === 'econ_event';
}

function _characterResidualBuildContextMap_(featurePackRows, v2bCoreRows, warnings) {
  var out = {};
  _characterResidualMergeContextRows_(out, featurePackRows || [], 'Feature_Pack_Audit');
  _characterResidualMergeContextRows_(out, v2bCoreRows || [], 'Feature_Pack_v2B_Core_Audit');
  return out;
}

function _characterResidualMergeContextRows_(out, bundle, sourceName) {
  var rows = (bundle && bundle.rows) || [];
  var idx = (bundle && bundle.idx) || {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var eventId = String(_predValue_(row, idx, 'event_id') || '').trim();
    if (!eventId) continue;
    if (!out[eventId]) out[eventId] = {};
    var target = out[eventId];
    target.event_id = eventId;
    target.source_sheet = target.source_sheet || sourceName;
    target.feature_pack_version = String(_predValue_(row, idx, 'feature_pack_version') || target.feature_pack_version || '').trim();
    target.signal_quality = String(_predValue_(row, idx, 'signal_quality') || target.signal_quality || '').trim();
    target.signal_quality_reason_codes = _characterResidualConcatUnique_(
      target.signal_quality_reason_codes,
      _characterResidualPipeSplit_(_predValue_(row, idx, 'signal_quality_reason_codes'))
    );
    target.has_market_context_pack = _characterResidualTruth_(target.has_market_context_pack) || _characterResidualTruth_(_predValue_(row, idx, 'has_market_context_pack'));
    target.market_context_available = _characterResidualTruth_(target.market_context_available) || _characterResidualTruth_(_predValue_(row, idx, 'market_context_available'));
    target.market_context_quality = String(_predValue_(row, idx, 'market_context_quality') || target.market_context_quality || '').trim();
    target.missing_market_context_fields = _characterResidualConcatUnique_(
      target.missing_market_context_fields,
      _characterResidualPipeSplit_(_predValue_(row, idx, 'missing_market_context_fields'))
    );
    target.market_context_char_count = target.market_context_char_count || _characterResidualNum_(_predValue_(row, idx, 'market_context_char_count'));
    target.snapshot_ts = String(_predValue_(row, idx, 'snapshot_ts') || target.snapshot_ts || '').trim();
    _characterResidualCopyNumField_(target, row, idx, 'fedfunds_level');
    _characterResidualCopyNumField_(target, row, idx, 'dff_level');
    _characterResidualCopyNumField_(target, row, idx, 'us2y_yield');
    _characterResidualCopyNumField_(target, row, idx, 'us10y_yield');
    _characterResidualCopyNumField_(target, row, idx, 'us_2s10s_curve');
    _characterResidualCopyNumField_(target, row, idx, 'jp10y_yield');
    _characterResidualCopyNumField_(target, row, idx, 'us_jp_10y_spread');
    _characterResidualCopyNumField_(target, row, idx, 'usdjpy_24h_change_pips');
    _characterResidualCopyNumField_(target, row, idx, 'usdjpy_5d_change_pips');
    _characterResidualCopyNumField_(target, row, idx, 'dxy_5d_change_pct');
    _characterResidualCopyNumField_(target, row, idx, 'spx_5d_change_pct');
    _characterResidualCopyNumField_(target, row, idx, 'gold_5d_change_pct');
    _characterResidualCopyNumField_(target, row, idx, 'wti_5d_change_pct');
    target.historical_context_quality = String(_predValue_(row, idx, 'history_quality') || target.historical_context_quality || '').trim();
    target.same_indicator_surprise_events_seen = _characterResidualMaxNum_(target.same_indicator_surprise_events_seen, _characterResidualNum_(_predValue_(row, idx, 'surprise_events_seen')));
    target.last_3_surprises = target.last_3_surprises || String(_predValue_(row, idx, 'last_3_surprises') || '').trim();
    target.surprise_bias = String(_predValue_(row, idx, 'surprise_bias') || target.surprise_bias || '').trim();
    target.surprise_pattern = String(_predValue_(row, idx, 'surprise_pattern') || target.surprise_pattern || '').trim();
    target.surprise_volatility = String(_predValue_(row, idx, 'surprise_volatility') || target.surprise_volatility || '').trim();
    target.consensus_accuracy_trend = String(_predValue_(row, idx, 'consensus_accuracy_trend') || target.consensus_accuracy_trend || '').trim();
    target.family_events_seen = _characterResidualMaxNum_(target.family_events_seen, _characterResidualNum_(_predValue_(row, idx, 'family_events_seen')));
    target.family_surprise_bias = String(_predValue_(row, idx, 'family_surprise_bias') || target.family_surprise_bias || '').trim();
    target.family_surprise_volatility = String(_predValue_(row, idx, 'family_surprise_volatility') || target.family_surprise_volatility || '').trim();
    target.family_forecastability_proxy = String(_predValue_(row, idx, 'family_forecastability_proxy') || target.family_forecastability_proxy || '').trim();
    target.family_market_translation_noise = String(_predValue_(row, idx, 'family_market_translation_noise') || target.family_market_translation_noise || '').trim();
    target.family_notes = String(_predValue_(row, idx, 'family_notes') || target.family_notes || '').trim();
  }
}

function _characterResidualCopyNumField_(target, row, idx, field) {
  var value = _predValue_(row, idx, field);
  if (value === '' || value === null || value === undefined) return;
  target[field] = value;
}

function _characterResidualMaxNum_(existing, next) {
  var a = _characterResidualNum_(existing);
  var b = _characterResidualNum_(next);
  if (a == null) return b;
  if (b == null) return a;
  return Math.max(a, b);
}

function _characterResidualFirstPredictionForEvent_(predBundle, eventId) {
  var rows = (predBundle && predBundle.rows) || [];
  var idx = (predBundle && predBundle.idx) || {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    if (String(_predValue_(row, idx, 'event_id') || '').trim() === eventId) return row;
  }
  return null;
}

function _characterResidualBuildBaselineRecord_(generatedTs, eventId, eventMeta, predictionRow, predictionIdx, contextMeta) {
  eventMeta = eventMeta || {};
  predictionRow = predictionRow || null;
  predictionIdx = predictionIdx || {};
  contextMeta = contextMeta || {};
  var baseline = {
    generated_ts: generatedTs,
    event_id: eventId,
    batch_id: _characterResidualText_(eventMeta.batch_id || (predictionRow ? _predValue_(predictionRow, predictionIdx, 'batch_id') : '')),
    type: _characterResidualText_(eventMeta.type || (predictionRow ? _predValue_(predictionRow, predictionIdx, 'type') : '')),
    indicator_name: _characterResidualText_(eventMeta.indicator_name || (predictionRow ? _predValue_(predictionRow, predictionIdx, 'indicator_name') : '')),
    country: _characterResidualText_(eventMeta.country || (predictionRow ? _predValue_(predictionRow, predictionIdx, 'country') : '')),
    release_ts: _characterResidualText_(eventMeta.release_ts || (predictionRow ? _predValue_(predictionRow, predictionIdx, 'release_ts') : '')),
    outcome_family: deriveOutcomeFamily_(
      String(eventMeta.indicator_name || (predictionRow ? _predValue_(predictionRow, predictionIdx, 'indicator_name') : '') || ''),
      String(eventMeta.genre || (predictionRow ? _predValue_(predictionRow, predictionIdx, 'genre') : '') || '')
    ) || 'other',
    consensus_value: _characterResidualNum_(eventMeta.consensus_value),
    prev_revision: _characterResidualNum_(eventMeta.prev_revision),
    actual_value: _characterResidualNum_(eventMeta.actual_value),
    baseline_version: 'character_residual_v1',
    baseline_value: null,
    baseline_direction_vs_consensus: 'unknown',
    baseline_confidence: 'low',
    baseline_reason_codes: [],
    baseline_available_fields: [],
    baseline_missing_fields: [],
    raw_baseline_json: ''
  };

  var reasonCodes = [];
  var available = [];
  var missing = [];
  var consensus = baseline.consensus_value;
  var prevRevision = baseline.prev_revision;
  var actualValue = baseline.actual_value;
  var featurePack = contextMeta || {};
  var signalQuality = String(featurePack.signal_quality || '').trim();
  var sameIndicatorSeen = _characterResidualNum_(featurePack.same_indicator_surprise_events_seen);
  var familySeen = _characterResidualNum_(featurePack.family_events_seen);
  var hasMarketContext = _characterResidualHasMarketContext_(featurePack);
  var marketFactors = _characterResidualMarketContextFactors_(featurePack);
  var historyQuality = String(featurePack.historical_context_quality || '').trim();
  var familyName = String(baseline.outcome_family || '').trim();
  var indicatorName = String(baseline.indicator_name || '').trim();

  if (_characterResidualHasNumeric_(consensus)) {
    baseline.baseline_value = consensus;
    reasonCodes.push('consensus_anchor');
    available.push('consensus_value');
  } else if (_characterResidualHasNumeric_(prevRevision)) {
    baseline.baseline_value = prevRevision;
    reasonCodes.push('prev_revision_anchor');
    available.push('prev_revision');
  } else {
    missing.push('consensus_value');
  }

  if (_characterResidualHasNumeric_(prevRevision)) {
    available.push('previous_value');
    reasonCodes.push('revision_context');
  } else {
    missing.push('prev_revision');
  }

  if (_characterResidualHasNumeric_(sameIndicatorSeen) && sameIndicatorSeen > 0) {
    available.push('surprise_history');
    reasonCodes.push('same_indicator_surprise_history');
  } else {
    missing.push('surprise_history');
  }

  if (_characterResidualHasNumeric_(familySeen) && familySeen > 0) {
    available.push('family_context');
    reasonCodes.push('family_context');
  } else {
    missing.push('family_context');
  }

  if (signalQuality) {
    available.push('signal_quality');
    reasonCodes.push('signal_quality=' + signalQuality);
  } else {
    missing.push('signal_quality');
  }

  if (historyQuality) {
    available.push('historical_context');
    reasonCodes.push('historical_context=' + historyQuality);
    if (historyQuality === 'cold_start' || historyQuality === 'partial') {
      reasonCodes.push('hidden_detail_risk');
    }
  } else {
    missing.push('historical_context');
  }

  if (hasMarketContext) {
    available.push('market_context');
    reasonCodes.push('market_context_available');
    Array.prototype.push.apply(available, marketFactors);
  } else {
    missing.push('market_context');
  }

  if (String(featurePack.feature_pack_version || '').toLowerCase()) {
    available.push('v2a_context');
    reasonCodes.push('v2a_context_available');
  } else {
    missing.push('v2a_context');
  }

  if (hasMarketContext || /v2b/i.test(String(featurePack.feature_pack_version || ''))) {
    available.push('v2b_context');
    reasonCodes.push('v2b_context_available');
  } else {
    missing.push('v2b_context');
  }

  if (String(featurePack.surprise_bias || '').trim()) {
    reasonCodes.push('surprise_bias=' + String(featurePack.surprise_bias).trim());
  }
  if (String(featurePack.surprise_pattern || '').trim()) {
    reasonCodes.push('surprise_pattern=' + String(featurePack.surprise_pattern).trim());
  }
  if (String(featurePack.consensus_accuracy_trend || '').trim()) {
    reasonCodes.push('consensus_accuracy_trend=' + String(featurePack.consensus_accuracy_trend).trim());
  }
  if (String(featurePack.family_surprise_bias || '').trim()) {
    reasonCodes.push('family_surprise_bias=' + String(featurePack.family_surprise_bias).trim());
  }
  if (String(featurePack.family_surprise_volatility || '').trim()) {
    reasonCodes.push('family_surprise_volatility=' + String(featurePack.family_surprise_volatility).trim());
  }
  if (String(featurePack.family_forecastability_proxy || '').trim()) {
    reasonCodes.push('family_forecastability_proxy=' + String(featurePack.family_forecastability_proxy).trim());
  }
  if (String(featurePack.family_market_translation_noise || '').trim()) {
    reasonCodes.push('family_market_translation_noise=' + String(featurePack.family_market_translation_noise).trim());
  }

  if (String(baseline.outcome_family || '').toLowerCase() === 'positioning') {
    available.push('positioning_or_crowding');
    reasonCodes.push('positioning_or_crowding');
  }
  if (String(baseline.outcome_family || '').toLowerCase() === 'central_bank' || /fed|fomc|policy/i.test(indicatorName)) {
    available.push('direct_fx_transmission');
    reasonCodes.push('direct_fx_transmission');
  }
  if (String(baseline.outcome_family || '').toLowerCase() === 'labor') {
    available.push('labor_strength');
  }
  if (String(baseline.outcome_family || '').toLowerCase() === 'inflation') {
    available.push('inflation_persistence');
  }
  if (String(baseline.outcome_family || '').toLowerCase() === 'growth') {
    available.push('consumer_demand');
    available.push('manufacturing_cycle');
  }
  if (String(baseline.outcome_family || '').toLowerCase() === 'housing') {
    available.push('housing_weakness');
  }
  if (String(baseline.outcome_family || '').toLowerCase() === 'energy') {
    available.push('energy_inventory');
  }

  if (!_characterResidualHasNumeric_(consensus)) {
    reasonCodes.push('missing_consensus');
  }
  if (_characterResidualIsLowSignalFamily_(baseline.outcome_family, indicatorName, featurePack)) {
    reasonCodes.push('low_signal_event');
  }

  if (featurePack.family_market_translation_noise === 'high') {
    reasonCodes.push('market_whipsaw_risk');
  }

  baseline.baseline_confidence = _characterResidualBaselineConfidence_(baseline, featurePack, reasonCodes);
  baseline.baseline_reason_codes = _characterResidualUniqueStrings_(reasonCodes);
  baseline.baseline_available_fields = _characterResidualUniqueStrings_(available);
  baseline.baseline_missing_fields = _characterResidualUniqueStrings_(missing);
  baseline.baseline_direction_vs_consensus = _characterResidualBaselineDirection_(baseline.baseline_value, baseline.consensus_value);

  baseline.raw_baseline_json = JSON.stringify({
    event_id: baseline.event_id,
    baseline_version: baseline.baseline_version,
    baseline_value: baseline.baseline_value,
    baseline_direction_vs_consensus: baseline.baseline_direction_vs_consensus,
    baseline_confidence: baseline.baseline_confidence,
    baseline_confidence_score: _characterResidualBuildBaselineConfidenceScore_(baseline, featurePack),
    baseline_reason_codes: baseline.baseline_reason_codes,
    baseline_available_fields: baseline.baseline_available_fields,
    baseline_missing_fields: baseline.baseline_missing_fields,
    source_snapshot: {
      consensus_value: baseline.consensus_value,
      prev_revision: baseline.prev_revision,
      actual_value: baseline.actual_value,
      historical_context_quality: historyQuality,
      same_indicator_surprise_events_seen: sameIndicatorSeen == null ? '' : sameIndicatorSeen,
      family_events_seen: familySeen == null ? '' : familySeen,
      signal_quality: signalQuality,
      market_context_fields: marketFactors,
      feature_pack_version: String(featurePack.feature_pack_version || '').trim(),
      source_sheet: String(featurePack.source_sheet || '').trim()
    }
  });

  return baseline;
}

function _characterResidualHasMarketContext_(featurePack) {
  return !!(featurePack && (
    featurePack.has_market_context_pack ||
    featurePack.market_context_available ||
    _characterResidualMarketContextFactors_(featurePack).length
  ));
}

function _characterResidualMarketContextFactors_(featurePack) {
  var out = [];
  if (!featurePack) return out;
  var mapping = [
    ['rates', ['fedfunds_level', 'dff_level', 'us2y_yield', 'us10y_yield', 'jp10y_yield']],
    ['yield_curve', ['us_2s10s_curve', 'us_jp_10y_spread']],
    ['usdjpy', ['usdjpy_24h_change_pips', 'usdjpy_5d_change_pips']],
    ['dxy', ['dxy_5d_change_pct']],
    ['spx', ['spx_5d_change_pct']],
    ['gold', ['gold_5d_change_pct']],
    ['wti', ['wti_5d_change_pct']],
    ['jp10y', ['jp10y_yield']],
    ['us_jp_spread', ['us_jp_10y_spread']]
  ];
  for (var i = 0; i < mapping.length; i++) {
    var label = mapping[i][0];
    var keys = mapping[i][1];
    for (var j = 0; j < keys.length; j++) {
      if (featurePack.hasOwnProperty(keys[j]) && featurePack[keys[j]] !== '' && featurePack[keys[j]] !== null && featurePack[keys[j]] !== undefined) {
        out.push(label);
        break;
      }
    }
  }
  return _characterResidualUniqueStrings_(out);
}

function _characterResidualBuildBaselineConfidenceScore_(baseline, featurePack) {
  var score = 10;
  if (_characterResidualHasNumeric_(baseline.consensus_value)) score += 40;
  if (_characterResidualHasNumeric_(baseline.prev_revision)) score += 10;
  if (_characterResidualHasNumeric_(featurePack.same_indicator_surprise_events_seen) && Number(featurePack.same_indicator_surprise_events_seen) > 0) score += 15;
  if (_characterResidualHasNumeric_(featurePack.family_events_seen) && Number(featurePack.family_events_seen) > 0) score += 10;
  if (_characterResidualHasMarketContext_(featurePack)) score += 10;
  if (String(featurePack.signal_quality || '').toLowerCase() === 'high') score += 10;
  if (String(featurePack.signal_quality || '').toLowerCase() === 'medium') score += 5;
  if (String(featurePack.signal_quality || '').toLowerCase() === 'low') score -= 10;
  if (String(featurePack.historical_context_quality || '').toLowerCase() === 'cold_start') score -= 15;
  if (String(featurePack.historical_context_quality || '').toLowerCase() === 'partial') score -= 10;
  if (!_characterResidualHasNumeric_(baseline.consensus_value)) score -= 10;
  if (String(baseline.outcome_family || '').toLowerCase() === 'other') score -= 5;
  score = Math.max(0, Math.min(100, score));
  return score;
}

function _characterResidualBaselineConfidenceScore_(baseline, featurePack) {
  return _characterResidualBuildBaselineConfidenceScore_(baseline, featurePack);
}

function _characterResidualBaselineConfidence_(baseline, featurePack, reasonCodes) {
  var score = _characterResidualBuildBaselineConfidenceScore_(baseline, featurePack);
  if (score >= 70) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
}

function _characterResidualBaselineDirection_(baselineValue, consensusValue) {
  if (!_characterResidualHasNumeric_(consensusValue) || !_characterResidualHasNumeric_(baselineValue)) return 'unknown';
  var delta = Number(baselineValue) - Number(consensusValue);
  if (Math.abs(delta) <= 1e-9) return 'inline';
  return delta > 0 ? 'above' : 'below';
}

function _characterResidualResidualRows_(sources, baselineMap, generatedTs, warnings) {
  var out = [];
  var predBundle = sources.predictionsBundle || null;
  var predRows = (predBundle && predBundle.rows) || [];
  var predIdx = (predBundle && predBundle.idx) || {};
  for (var i = 0; i < predRows.length; i++) {
    var row = predRows[i];
    var eventId = String(_predValue_(row, predIdx, 'event_id') || '').trim();
    var aiName = String(_predValue_(row, predIdx, 'ai_name') || '').trim();
    if (!eventId || !aiName) continue;
    var baseline = baselineMap[eventId];
    if (!baseline) {
      baseline = _characterResidualBuildFallbackBaseline_(generatedTs, row, predIdx);
      baselineMap[eventId] = baseline;
    }
    var eventMeta = _characterResidualPredictionEventMeta_(row, predIdx, baseline);
    var providerConfidence = _characterResidualProviderConfidence_(row, predIdx, baseline);
    var emphasizedFactors = _characterResidualProviderFactors_(row, predIdx);
    var ignoredFactors = _characterResidualIgnoredFactors_(baseline, emphasizedFactors);
    var riskLanguage = _characterResidualRiskLanguage_(row, predIdx);
    var uncertaintyPattern = _characterResidualUncertaintyPattern_(row, predIdx, providerConfidence);
    var rationaleStyleTags = _characterResidualRationaleStyleTags_(row, predIdx);
    var confidenceDelta = _characterResidualConfidenceDelta_(baseline.baseline_confidence, providerConfidence.level);
    var valueDelta = _characterResidualValueDelta_(row, predIdx, baseline.baseline_value);
    var absValueDelta = valueDelta === '' ? '' : Math.abs(Number(valueDelta));
    var directionDelta = _characterResidualDirectionDelta_(row, predIdx, baseline);
    var rationaleShort = _characterResidualText_(_predValue_(row, predIdx, 'rationale_short'));
    var rationalePreview = _characterResidualRationalePreview_(row, predIdx);
    out.push({
      generated_ts: generatedTs,
      event_id: eventId,
      batch_id: eventMeta.batch_id,
      type: eventMeta.type,
      indicator_name: eventMeta.indicator_name,
      country: eventMeta.country,
      release_ts: eventMeta.release_ts,
      outcome_family: baseline.outcome_family,
      provider: aiName,
      ai_forecast_value: _characterResidualNum_(_predValue_(row, predIdx, 'ai_forecast_value')),
      qualitative_result: _characterResidualText_(_predValue_(row, predIdx, 'qualitative_result')),
      actual_value: _characterResidualActualValue_(row, predIdx, baseline),
      baseline_version: baseline.baseline_version,
      baseline_value: baseline.baseline_value == null ? '' : baseline.baseline_value,
      baseline_direction_vs_consensus: baseline.baseline_direction_vs_consensus,
      baseline_confidence: baseline.baseline_confidence,
      value_delta_from_baseline: valueDelta === '' ? '' : _round4_(valueDelta),
      abs_value_delta_from_baseline: absValueDelta === '' ? '' : _round4_(absValueDelta),
      direction_delta_from_baseline: directionDelta,
      emphasized_factors: emphasizedFactors.join('|'),
      ignored_factors: ignoredFactors.join('|'),
      risk_language: riskLanguage,
      uncertainty_pattern: uncertaintyPattern,
      confidence_delta_from_baseline: confidenceDelta,
      inferred_confidence_flag: providerConfidence.inferred ? 'TRUE' : 'FALSE',
      rationale_style_tags: rationaleStyleTags.join('|'),
      rationale_short: rationaleShort,
      rationale_preview: rationalePreview,
      raw_character_vector_json: JSON.stringify({
        event_id: eventId,
        provider: aiName,
        baseline: baseline,
        provider_confidence: providerConfidence,
        emphasized_factors: emphasizedFactors,
        ignored_factors: ignoredFactors,
        risk_language: riskLanguage,
        uncertainty_pattern: uncertaintyPattern,
        rationale_style_tags: rationaleStyleTags,
        value_delta_from_baseline: valueDelta,
        direction_delta_from_baseline: directionDelta,
        confidence_delta_from_baseline: confidenceDelta,
        rationale_short: rationaleShort,
        rationale_preview: rationalePreview
      })
    });
  }
  return out;
}

function _characterResidualPredictionEventMeta_(row, predIdx, baseline) {
  return {
    batch_id: _characterResidualText_(_predValue_(row, predIdx, 'batch_id') || baseline.batch_id),
    type: _characterResidualText_(_predValue_(row, predIdx, 'type') || baseline.type),
    indicator_name: _characterResidualText_(_predValue_(row, predIdx, 'indicator_name') || baseline.indicator_name),
    country: _characterResidualText_(_predValue_(row, predIdx, 'country') || baseline.country),
    release_ts: _characterResidualText_(_predValue_(row, predIdx, 'release_ts') || baseline.release_ts)
  };
}

function _characterResidualBuildFallbackBaseline_(generatedTs, row, predIdx) {
  var indicatorName = String(_predValue_(row, predIdx, 'indicator_name') || '').trim();
  var genre = String(_predValue_(row, predIdx, 'genre') || '').trim();
  var consensus = _characterResidualNum_(_predValue_(row, predIdx, 'consensus_value'));
  var prevRevision = _characterResidualNum_(_predValue_(row, predIdx, 'prev_revision'));
  var baselineValue = _characterResidualHasNumeric_(consensus) ? consensus : ( _characterResidualHasNumeric_(prevRevision) ? prevRevision : null );
  return {
    generated_ts: generatedTs,
    event_id: String(_predValue_(row, predIdx, 'event_id') || '').trim(),
    batch_id: String(_predValue_(row, predIdx, 'batch_id') || '').trim(),
    type: String(_predValue_(row, predIdx, 'type') || '').trim(),
    indicator_name: indicatorName,
    country: String(_predValue_(row, predIdx, 'country') || '').trim(),
    release_ts: String(_predValue_(row, predIdx, 'release_ts') || '').trim(),
    outcome_family: deriveOutcomeFamily_(indicatorName, genre) || 'other',
    consensus_value: consensus,
    prev_revision: prevRevision,
    actual_value: _characterResidualNum_(_predValue_(row, predIdx, 'released_value')),
    baseline_version: 'character_residual_v1',
    baseline_value: baselineValue,
    baseline_direction_vs_consensus: _characterResidualBaselineDirection_(baselineValue, consensus),
    baseline_confidence: _characterResidualHasNumeric_(consensus) ? 'medium' : 'low',
    baseline_reason_codes: _characterResidualHasNumeric_(consensus) ? ['consensus_anchor'] : ['missing_consensus'],
    baseline_available_fields: _characterResidualHasNumeric_(consensus) ? ['consensus_value'] : [],
    baseline_missing_fields: _characterResidualHasNumeric_(consensus) ? [] : ['consensus_value'],
    raw_baseline_json: JSON.stringify({ fallback: true, event_id: String(_predValue_(row, predIdx, 'event_id') || '').trim() })
  };
}

function _characterResidualActualValue_(row, predIdx, baseline) {
  var actual = _characterResidualNum_(_predValue_(row, predIdx, 'released_value'));
  if (actual != null) return actual;
  return baseline.actual_value == null ? '' : baseline.actual_value;
}

function _characterResidualProviderConfidence_(row, predIdx, baseline) {
  var explicit = _characterResidualFirstNonBlank_([
    _predValue_(row, predIdx, 'provider_confidence'),
    _predValue_(row, predIdx, 'confidence'),
    _predValue_(row, predIdx, 'ai_confidence'),
    _predValue_(row, predIdx, 'prediction_confidence')
  ]);
  if (explicit) {
    return {
      level: _characterResidualConfidenceLevel_(explicit),
      inferred: false,
      source: 'explicit'
    };
  }

  var rationale = _characterResidualText_(_predValue_(row, predIdx, 'rationale_short') || _predValue_(row, predIdx, 'rationale'));
  var level = 'medium';
  if (/low confidence|uncertain|cautious|hedged|weak|flat|limited|maybe|not enough|missing consensus|thin signal|low signal/i.test(rationale)) {
    level = 'low';
  } else if (/high confidence|clear|confident|strong|decisive|conviction/i.test(rationale)) {
    level = 'high';
  }
  if (baseline && baseline.baseline_confidence === 'low' && level === 'high') level = 'medium';
  return {
    level: level,
    inferred: true,
    source: 'inferred_from_rationale'
  };
}

function _characterResidualConfidenceLevel_(value) {
  var s = String(value || '').trim().toLowerCase();
  if (!s) return 'medium';
  if (/high|strong|confident|certain/.test(s)) return 'high';
  if (/low|weak|uncertain|cautious|hedged|limited|thin/.test(s)) return 'low';
  return 'medium';
}

function _characterResidualValueDelta_(row, predIdx, baselineValue) {
  var forecast = _characterResidualNum_(_predValue_(row, predIdx, 'ai_forecast_value'));
  if (forecast == null || !_characterResidualHasNumeric_(baselineValue)) return '';
  return _round4_(Number(forecast) - Number(baselineValue));
}

function _characterResidualDirectionDelta_(row, predIdx, baseline) {
  var providerDir = _characterResidualProviderDirection_(row, predIdx, baseline.baseline_value);
  var baselineDir = String(baseline.baseline_direction_vs_consensus || 'unknown').trim();
  if (!providerDir || providerDir === 'unknown' || !baselineDir || baselineDir === 'unknown') return 'unknown';
  if (providerDir === 'inline' && baselineDir !== 'inline') return 'provider_flat_vs_directional';
  if (baselineDir === 'inline') {
    if (providerDir === 'inline') return 'same_direction';
    return 'provider_directional_vs_flat';
  }
  if (providerDir === 'inline') return 'provider_flat_vs_directional';
  if (providerDir === baselineDir) return 'same_direction';
  if (baselineDir === 'above' && providerDir === 'below') return 'provider_more_negative';
  if (baselineDir === 'below' && providerDir === 'above') return 'provider_more_positive';
  return 'unknown';
}

function _characterResidualProviderDirection_(row, predIdx, baselineValue) {
  var qualitative = String(_predValue_(row, predIdx, 'qualitative_result') || '').trim().toLowerCase();
  if (qualitative === 'stronger') return 'above';
  if (qualitative === 'weaker') return 'below';
  if (qualitative === 'inline') return 'inline';
  var forecast = _characterResidualNum_(_predValue_(row, predIdx, 'ai_forecast_value'));
  if (forecast == null || !_characterResidualHasNumeric_(baselineValue)) return 'unknown';
  var delta = Number(forecast) - Number(baselineValue);
  if (Math.abs(delta) <= 1e-9) return 'inline';
  return delta > 0 ? 'above' : 'below';
}

function _characterResidualProviderFactors_(row, predIdx) {
  var raw = [];
  raw.push(_predValue_(row, predIdx, 'attention_primary_factor'));
  raw.push(_predValue_(row, predIdx, 'attention_factors'));
  raw.push(_predValue_(row, predIdx, 'attention_factor_1'));
  raw.push(_predValue_(row, predIdx, 'attention_factor_2'));
  raw.push(_predValue_(row, predIdx, 'attention_factor_3'));
  raw.push(_predValue_(row, predIdx, 'attention_summary'));
  raw.push(_predValue_(row, predIdx, 'rationale_short'));
  raw.push(_predValue_(row, predIdx, 'rationale'));
  var tokens = [];
  for (var i = 0; i < raw.length; i++) {
    Array.prototype.push.apply(tokens, _characterResidualExtractFactorsFromText_(raw[i]));
  }
  return _characterResidualUniqueStrings_(tokens);
}

function _characterResidualIgnoredFactors_(baseline, emphasizedFactors) {
  var available = baseline && baseline.baseline_available_fields ? baseline.baseline_available_fields : [];
  var ignored = [];
  var emphasized = {};
  for (var i = 0; i < (emphasizedFactors || []).length; i++) emphasized[String(emphasizedFactors[i] || '').trim().toLowerCase()] = true;
  for (var j = 0; j < available.length; j++) {
    var factor = _characterResidualNormalizeFactorToken_(available[j]);
    if (!factor || factor === 'other' || emphasized[factor]) continue;
    ignored.push(factor);
  }
  return _characterResidualUniqueStrings_(ignored);
}

function _characterResidualNormalizeFactorToken_(value) {
  var s = String(value || '').trim().toLowerCase();
  if (!s) return '';
  if (s === 'consensus_value' || s === 'consensus') return 'consensus';
  if (s === 'prev_revision' || s === 'previous_value' || s === 'prior_value') return 'previous_value';
  if (s === 'revision_history') return 'revision_history';
  if (s === 'surprise_history' || s === 'historical_context' || s === 'last_3_surprises') return 'surprise_history';
  if (s === 'family_context' || s === 'family') return 'family_context';
  if (s === 'signal_quality') return 'signal_quality';
  if (s === 'v2a_context' || s === 'historical_context_quality') return 'v2a_context';
  if (s === 'v2b_context' || s === 'market_context_quality' || s === 'market_context_available') return 'v2b_context';
  if (s === 'market_context') return 'market_context';
  if (s === 'rates' || s === 'yield_curve' || s === 'usdjpy' || s === 'dxy' || s === 'spx' || s === 'gold' || s === 'wti' || s === 'jp10y' || s === 'us_jp_spread') return s;
  if (s === 'hidden_detail_risk' || s === 'missing_consensus' || s === 'low_signal_event' || s === 'direct_fx_transmission' || s === 'market_whipsaw_risk' || s === 'positioning_or_crowding' || s === 'uncertainty') return s;
  if (s === 'inflation_persistence' || s === 'labor_strength' || s === 'consumer_demand' || s === 'housing_weakness' || s === 'manufacturing_cycle' || s === 'energy_inventory') return s;
  return s;
}

function _characterResidualRiskLanguage_(row, predIdx) {
  var text = _characterResidualText_(_predValue_(row, predIdx, 'rationale_short') + ' ' + _predValue_(row, predIdx, 'rationale'));
  var t = text.toLowerCase();
  if (/tail risk|black swan|extreme|catastrophic/.test(t)) return 'tail_risk_language';
  if (/hidden detail|subcomponent|post-release internals|internal detail|deciding details/.test(t)) return 'hidden_detail_risk_language';
  if (/crowd|crowded|positioning|whipsaw|squeeze/.test(t)) return 'crowded_trade_language';
  if (/uncertain|uncertainty|cautious|hedged|limited|weak signal|low confidence|thin signal|missing consensus|low signal/.test(t)) return 'uncertainty_language';
  if (/strong|decisive|high confidence|clear edge|conviction/.test(t)) return 'high_risk_language';
  if (/flat|weak|conservative|small pips|low risk|avoid overstate|limited confidence/.test(t)) return 'low_risk_language';
  return 'normal_risk_language';
}

function _characterResidualUncertaintyPattern_(row, predIdx, providerConfidence) {
  var text = _characterResidualText_(_predValue_(row, predIdx, 'rationale_short') + ' ' + _predValue_(row, predIdx, 'rationale'));
  var t = text.toLowerCase();
  if (/scenario|if\/then|case|base case|bull case|bear case/.test(t)) return 'scenario_based';
  if (/low signal|thin signal|missing consensus|cold start|partial history|no consensus/.test(t)) return 'low_signal';
  if (/hedged|mixed|offset|both|but|however/.test(t)) return 'mixed_signal';
  if (/cautious|uncertain|limited|maybe|weak|flat|conservative|not enough/.test(t)) return 'cautious';
  if (/confident|clear|strong|decisive|high confidence/.test(t) || (providerConfidence && providerConfidence.level === 'high')) return 'confident';
  return 'unknown';
}

function _characterResidualRationaleStyleTags_(row, predIdx) {
  var text = _characterResidualText_(_predValue_(row, predIdx, 'rationale_short') + ' ' + _predValue_(row, predIdx, 'rationale'));
  var t = text.toLowerCase();
  var out = [];
  if (!t) return out;
  if (/scenario|if\/then|case|base case|bull case|bear case/.test(t)) out.push('scenario_based');
  if (/because|due to|since|as/.test(t)) out.push('causal_explanation');
  if (/however|but|although|yet|still|while/.test(t)) out.push('hedged');
  if (/clear|decisive|confident|strong|conviction/.test(t)) out.push('decisive');
  if (/low signal|thin signal|missing consensus|cold start|partial history/.test(t)) out.push('low_signal');
  if (/hidden detail|subcomponent|internal detail|post-release internals/.test(t)) out.push('hidden_detail_sensitive');
  if (/rates|yield|usd\/?jpy|dxy|spx|gold|wti/.test(t)) out.push('market_context');
  if (/consensus|prev revision|previous value|surprise/.test(t)) out.push('reference_anchor');
  return _characterResidualUniqueStrings_(out);
}

function _characterResidualConfidenceDelta_(baselineConfidence, providerConfidence) {
  var map = { low: 1, medium: 2, high: 3 };
  var b = map[String(baselineConfidence || '').trim().toLowerCase()] || 0;
  var p = map[String(providerConfidence || '').trim().toLowerCase()] || 0;
  if (!b || !p) return 'unknown';
  if (p === b) return 'same';
  return p > b ? 'higher' : 'lower';
}

function _characterResidualRationalePreview_(row, predIdx) {
  var shortText = _characterResidualText_(_predValue_(row, predIdx, 'rationale_short'));
  if (shortText) return _characterResidualTruncate_(shortText, 180);
  return _characterResidualTruncate_(_characterResidualText_(_predValue_(row, predIdx, 'rationale')), 180);
}

function _characterResidualExtractFactorsFromText_(text) {
  var out = [];
  var s = String(text || '').toLowerCase();
  if (!s) return out;
  if (/consensus/.test(s)) out.push('consensus');
  if (/prev revision|previous value|prior value|revision/.test(s)) out.push('previous_value', 'revision_history');
  if (/surprise history|historical surprise|surprise bias|surprise pattern/.test(s)) out.push('surprise_history');
  if (/family|same family|family context/.test(s)) out.push('family_context');
  if (/signal quality|signal/.test(s)) out.push('signal_quality');
  if (/rate|yield|fed|treasury|policy/.test(s)) out.push('rates', 'yield_curve');
  if (/usd\/?jpy|usdjpy|yen/.test(s)) out.push('usdjpy', 'direct_fx_transmission');
  if (/dxy|dollar index/.test(s)) out.push('dxy');
  if (/spx|s&p|sp500|equity/.test(s)) out.push('spx');
  if (/gold/.test(s)) out.push('gold');
  if (/wti|oil|crude|petroleum|gasoline|inventory/.test(s)) out.push('wti', 'energy_inventory');
  if (/jp10y|japan 10y/.test(s)) out.push('jp10y');
  if (/spread/.test(s)) out.push('us_jp_spread');
  if (/inflation|cpi|pce/.test(s)) out.push('inflation_persistence');
  if (/labor|payroll|jobless|claims|wage|employment/.test(s)) out.push('labor_strength');
  if (/consumer|retail sales|demand/.test(s)) out.push('consumer_demand');
  if (/housing|home sales|permits|starts/.test(s)) out.push('housing_weakness');
  if (/manufacturing|ism|pmi|factory/.test(s)) out.push('manufacturing_cycle');
  if (/hidden detail|subcomponent|internal|deciding details/.test(s)) out.push('hidden_detail_risk');
  if (/missing consensus|no consensus/.test(s)) out.push('missing_consensus');
  if (/low signal|thin signal|limited signal/.test(s)) out.push('low_signal_event');
  if (/whipsaw|crowd|crowded|positioning|squeeze/.test(s)) out.push('market_whipsaw_risk', 'positioning_or_crowding');
  if (/uncertain|uncertainty|hedged|mixed|maybe|cautious/.test(s)) out.push('uncertainty');
  if (out.length === 0 && s) out.push('other');
  return out;
}

function _characterResidualBaselineRows_(baselineMap, generatedTs) {
  var out = [];
  Object.keys(baselineMap || {}).forEach(function(eventId) {
    out.push(_characterResidualBaselineRecordToRow_(baselineMap[eventId], generatedTs));
  });
  return out;
}

function _characterResidualBaselineRecordToRow_(baseline, generatedTs) {
  if (!baseline) return {};
  return {
    generated_ts: generatedTs || baseline.generated_ts || '',
    event_id: baseline.event_id || '',
    batch_id: baseline.batch_id || '',
    type: baseline.type || '',
    indicator_name: baseline.indicator_name || '',
    country: baseline.country || '',
    release_ts: baseline.release_ts || '',
    outcome_family: baseline.outcome_family || '',
    consensus_value: baseline.consensus_value == null ? '' : baseline.consensus_value,
    prev_revision: baseline.prev_revision == null ? '' : baseline.prev_revision,
    actual_value: baseline.actual_value == null ? '' : baseline.actual_value,
    baseline_version: baseline.baseline_version || 'character_residual_v1',
    baseline_value: baseline.baseline_value == null ? '' : baseline.baseline_value,
    baseline_direction_vs_consensus: baseline.baseline_direction_vs_consensus || 'unknown',
    baseline_confidence: baseline.baseline_confidence || 'low',
    baseline_reason_codes: _characterResidualJoinPipe_(baseline.baseline_reason_codes || []),
    baseline_available_fields: _characterResidualJoinPipe_(baseline.baseline_available_fields || []),
    baseline_missing_fields: _characterResidualJoinPipe_(baseline.baseline_missing_fields || []),
    raw_baseline_json: baseline.raw_baseline_json || ''
  };
}

function _characterResidualSummaryRows_(residualRows, generatedTs) {
  var byProvider = {};
  for (var i = 0; i < (residualRows || []).length; i++) {
    var row = residualRows[i];
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!byProvider[provider]) {
      byProvider[provider] = {
        provider: provider,
        row_count: 0,
        value_delta_sum: 0,
        value_delta_count: 0,
        abs_delta_sum: 0,
        abs_delta_count: 0,
        more_positive: 0,
        more_negative: 0,
        same_direction: 0,
        flat_vs_directional: 0,
        directional_vs_flat: 0,
        factors: {},
        ignored: {},
        risk: {},
        uncertainty: {}
      };
    }
    var g = byProvider[provider];
    g.row_count += 1;
    var delta = _characterResidualNum_(row.value_delta_from_baseline);
    if (delta != null) {
      g.value_delta_sum += delta;
      g.value_delta_count += 1;
    }
    var absDelta = _characterResidualNum_(row.abs_value_delta_from_baseline);
    if (absDelta != null) {
      g.abs_delta_sum += absDelta;
      g.abs_delta_count += 1;
    }
    if (delta != null) {
      if (Math.abs(delta) <= 1e-9) g.same_direction += 1;
      else if (delta > 0) g.more_positive += 1;
      else g.more_negative += 1;
    } else if (String(row.direction_delta_from_baseline || '').trim() === 'same_direction') {
      g.same_direction += 1;
    }
    var dir = String(row.direction_delta_from_baseline || '').trim();
    if (dir === 'provider_flat_vs_directional') g.flat_vs_directional += 1;
    else if (dir === 'provider_directional_vs_flat') g.directional_vs_flat += 1;
    _characterResidualIncTokens_(g.factors, _characterResidualPipeSplit_(row.emphasized_factors));
    _characterResidualIncTokens_(g.ignored, _characterResidualPipeSplit_(row.ignored_factors));
    _characterResidualIncSingle_(g.risk, row.risk_language);
    _characterResidualIncSingle_(g.uncertainty, row.uncertainty_pattern);
  }

  var rowsOut = [];
  Object.keys(byProvider).sort().forEach(function(provider) {
    var g = byProvider[provider];
    rowsOut.push({
      generated_ts: generatedTs,
      provider: provider,
      row_count: g.row_count,
      avg_value_delta_from_baseline: g.value_delta_count ? _round4_(g.value_delta_sum / g.value_delta_count) : '',
      avg_abs_value_delta_from_baseline: g.abs_delta_count ? _round4_(g.abs_delta_sum / g.abs_delta_count) : '',
      provider_more_positive_count: g.more_positive,
      provider_more_negative_count: g.more_negative,
      same_direction_count: g.same_direction,
      provider_flat_vs_directional_count: g.flat_vs_directional,
      provider_directional_vs_flat_count: g.directional_vs_flat,
      top_emphasized_factors: _characterResidualCountMapText_(g.factors, 5),
      top_ignored_available_factors: _characterResidualCountMapText_(g.ignored, 5),
      dominant_risk_language: _characterResidualDominantKey_(g.risk),
      dominant_uncertainty_pattern: _characterResidualDominantKey_(g.uncertainty),
      character_stability_note: _characterResidualCharacterStabilityNote_(g)
    });
  });
  return rowsOut;
}

function _characterResidualFamilySummaryRows_(residualRows, generatedTs) {
  var byGroup = {};
  for (var i = 0; i < (residualRows || []).length; i++) {
    var row = residualRows[i];
    var key = [String(row.provider || '').trim(), String(row.outcome_family || '').trim()].join('|');
    if (!byGroup[key]) {
      byGroup[key] = {
        provider: String(row.provider || '').trim(),
        outcome_family: String(row.outcome_family || '').trim() || 'other',
        row_count: 0,
        value_delta_sum: 0,
        value_delta_count: 0,
        abs_delta_sum: 0,
        abs_delta_count: 0,
        directions: {},
        factors: {},
        ignored: {},
        risk: {},
        uncertainty: {}
      };
    }
    var g = byGroup[key];
    g.row_count += 1;
    var delta = _characterResidualNum_(row.value_delta_from_baseline);
    if (delta != null) {
      g.value_delta_sum += delta;
      g.value_delta_count += 1;
    }
    var absDelta = _characterResidualNum_(row.abs_value_delta_from_baseline);
    if (absDelta != null) {
      g.abs_delta_sum += absDelta;
      g.abs_delta_count += 1;
    }
    _characterResidualIncSingle_(g.directions, row.direction_delta_from_baseline);
    _characterResidualIncTokens_(g.factors, _characterResidualPipeSplit_(row.emphasized_factors));
    _characterResidualIncTokens_(g.ignored, _characterResidualPipeSplit_(row.ignored_factors));
    _characterResidualIncSingle_(g.risk, row.risk_language);
    _characterResidualIncSingle_(g.uncertainty, row.uncertainty_pattern);
  }

  var rowsOut = [];
  Object.keys(byGroup).sort().forEach(function(key) {
    var g = byGroup[key];
    rowsOut.push({
      generated_ts: generatedTs,
      provider: g.provider,
      outcome_family: g.outcome_family,
      row_count: g.row_count,
      avg_value_delta_from_baseline: g.value_delta_count ? _round4_(g.value_delta_sum / g.value_delta_count) : '',
      avg_abs_value_delta_from_baseline: g.abs_delta_count ? _round4_(g.abs_delta_sum / g.abs_delta_count) : '',
      direction_delta_distribution: _characterResidualCountMapText_(g.directions, 6),
      top_emphasized_factors: _characterResidualCountMapText_(g.factors, 5),
      top_ignored_available_factors: _characterResidualCountMapText_(g.ignored, 5),
      risk_language_distribution: _characterResidualCountMapText_(g.risk, 4),
      uncertainty_pattern_distribution: _characterResidualCountMapText_(g.uncertainty, 4),
      sample_depth_warning: g.row_count < 5 ? 'thin_sample' : ''
    });
  });
  return rowsOut;
}

function _characterResidualDisagreementRows_(residualRows, baselineMap, generatedTs) {
  var byEvent = {};
  for (var i = 0; i < (residualRows || []).length; i++) {
    var row = residualRows[i];
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    if (!byEvent[eventId]) byEvent[eventId] = [];
    byEvent[eventId].push(row);
  }

  var out = [];
  Object.keys(byEvent).sort().forEach(function(eventId) {
    var rows = byEvent[eventId];
    if (rows.length < 2) return;
    var baseline = baselineMap[eventId] || {};
    var providerPositive = [];
    var providerNegative = [];
    var providerFlat = [];
    var valueDeltas = [];
    var factorSets = {};
    var actualValue = null;
    var closestProvider = '';
    var closestDiff = null;
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var delta = _characterResidualNum_(row.value_delta_from_baseline);
      if (delta != null) {
        valueDeltas.push(delta);
        if (Math.abs(delta) <= 1e-9) providerFlat.push(row.provider);
        else if (delta > 0) providerPositive.push(row.provider);
        else providerNegative.push(row.provider);
      } else {
        var dir = String(row.direction_delta_from_baseline || '').trim();
        if (dir === 'provider_more_positive') providerPositive.push(row.provider);
        else if (dir === 'provider_more_negative') providerNegative.push(row.provider);
        else providerFlat.push(row.provider);
      }
      factorSets[String(row.provider || '').trim()] = _characterResidualPipeSplit_(row.emphasized_factors).join('|');
      var actual = _characterResidualNum_(row.actual_value);
      if (actual != null) actualValue = actual;
      if (actual != null && _characterResidualNum_(row.ai_forecast_value) != null) {
        var diff = Math.abs(Number(row.ai_forecast_value) - actual);
        if (closestDiff == null || diff < closestDiff || (Math.abs(diff - closestDiff) <= 1e-9 && String(row.provider).localeCompare(String(closestProvider)) < 0)) {
          closestDiff = diff;
          closestProvider = String(row.provider || '').trim();
        }
      }
    }

    var minDelta = null;
    var maxDelta = null;
    for (var j = 0; j < valueDeltas.length; j++) {
      if (minDelta == null || valueDeltas[j] < minDelta) minDelta = valueDeltas[j];
      if (maxDelta == null || valueDeltas[j] > maxDelta) maxDelta = valueDeltas[j];
    }
    var uniqueFactorSets = {};
    Object.keys(factorSets).forEach(function(provider) {
      uniqueFactorSets[factorSets[provider]] = true;
    });
    var directionDisagreementLevel = _characterResidualDisagreementLevel_(providerPositive, providerNegative, providerFlat);
    var factorDisagreementLevel = Object.keys(uniqueFactorSets).length > 2 ? 'high' : (Object.keys(uniqueFactorSets).length > 1 ? 'moderate' : 'low');
    var materialDisagreement = directionDisagreementLevel !== 'low' || factorDisagreementLevel !== 'low' || (minDelta != null && maxDelta != null && Math.abs(maxDelta - minDelta) > 0.1);
    if (!materialDisagreement) return;
    out.push({
      generated_ts: generatedTs,
      event_id: eventId,
      indicator_name: String((baseline && baseline.indicator_name) || '').trim(),
      release_ts: String((baseline && baseline.release_ts) || '').trim(),
      outcome_family: String((baseline && baseline.outcome_family) || 'other').trim(),
      baseline_value: baseline.baseline_value == null ? '' : baseline.baseline_value,
      baseline_direction_vs_consensus: String((baseline && baseline.baseline_direction_vs_consensus) || 'unknown'),
      provider_count: rows.length,
      value_delta_range: (minDelta == null || maxDelta == null) ? '' : _round4_(maxDelta - minDelta),
      direction_disagreement_level: directionDisagreementLevel,
      factor_disagreement_level: factorDisagreementLevel,
      providers_positive: _characterResidualUniqueStrings_(providerPositive).join('|'),
      providers_negative: _characterResidualUniqueStrings_(providerNegative).join('|'),
      providers_flat: _characterResidualUniqueStrings_(providerFlat).join('|'),
      disagreement_summary: _characterResidualDisagreementSummary_(rows.length, directionDisagreementLevel, factorDisagreementLevel, baseline),
      actual_value: actualValue == null ? '' : actualValue,
      which_provider_closest_to_actual: closestProvider,
      notes: 'Provider-character diagnostic only; not trading advice.'
    });
  });
  return out;
}

function _characterResidualDisagreementLevel_(positive, negative, flat) {
  var kinds = 0;
  if ((positive || []).length) kinds += 1;
  if ((negative || []).length) kinds += 1;
  if ((flat || []).length) kinds += 1;
  if (kinds <= 1) return 'low';
  if (kinds === 2) return 'moderate';
  return 'high';
}

function _characterResidualDisagreementSummary_(providerCount, directionLevel, factorLevel, baseline) {
  return [
    'providers=' + providerCount,
    'direction=' + directionLevel,
    'factors=' + factorLevel,
    'baseline=' + String((baseline && baseline.baseline_direction_vs_consensus) || 'unknown')
  ].join('; ');
}

function _characterResidualObjectsToRows_(rows, headers) {
  return (rows || []).map(function(row) {
    return (headers || []).map(function(header) {
      return row && row.hasOwnProperty(header) ? row[header] : '';
    });
  });
}

function _characterResidualSortKey_(a, b, cols) {
  return _cmpByColumns_(a, b, cols);
}

function _sortCharacterResidualBaselineRows_(rows) {
  rows.sort(function(a, b) {
    return _characterResidualSortKey_(a, b, ['release_ts', 'outcome_family', 'indicator_name', 'event_id']);
  });
}

function _sortCharacterResidualResidualRows_(rows) {
  rows.sort(function(a, b) {
    return _characterResidualSortKey_(a, b, ['provider', 'release_ts', 'event_id', 'indicator_name']);
  });
}

function _sortCharacterResidualSummaryRows_(rows) {
  rows.sort(function(a, b) {
    return _characterResidualSortKey_(a, b, ['provider']);
  });
}

function _sortCharacterResidualFamilySummaryRows_(rows) {
  rows.sort(function(a, b) {
    return _characterResidualSortKey_(a, b, ['provider', 'outcome_family']);
  });
}

function _sortCharacterResidualDisagreementRows_(rows) {
  rows.sort(function(a, b) {
    return _characterResidualSortKey_(a, b, ['release_ts', 'event_id', 'indicator_name']);
  });
}

function _characterResidualIncrementDirectionCounts_(group, dir) {
  var s = String(dir || '').trim();
  if (s === 'provider_more_positive') group.more_positive += 1;
  else if (s === 'provider_more_negative') group.more_negative += 1;
  else if (s === 'same_direction') group.same_direction += 1;
  else if (s === 'provider_flat_vs_directional') group.flat_vs_directional += 1;
  else if (s === 'provider_directional_vs_flat') group.directional_vs_flat += 1;
}

function _characterResidualCharacterStabilityNote_(group) {
  var dominantFactor = _characterResidualDominantKey_(group.factors);
  var factorShare = _characterResidualDominantShare_(group.factors);
  var directionShare = Math.max(group.more_positive, group.more_negative, group.same_direction, group.flat_vs_directional, group.directional_vs_flat) / Math.max(1, group.row_count);
  if (group.row_count < 5) return 'thin_sample';
  if (factorShare >= 0.6 && directionShare >= 0.6) return 'stable_residual_signature';
  if (group.row_count >= 10 && factorShare < 0.35) return 'mixed_character_signature';
  if (dominantFactor && factorShare >= 0.4) return 'emerging_signature';
  return 'needs_more_rows';
}

function _characterResidualDominantKey_(map) {
  var top = _characterResidualTopCountItems_(map, 1);
  return top.length ? top[0].key : '';
}

function _characterResidualDominantShare_(map) {
  var top = _characterResidualTopCountItems_(map, 1);
  if (!top.length) return 0;
  var total = 0;
  Object.keys(map || {}).forEach(function(key) { total += Number(map[key] || 0); });
  if (!(total > 0)) return 0;
  return top[0].count / total;
}

function _characterResidualCountMapText_(map, limit) {
  return _characterResidualTopCountItems_(map, limit || 5).map(function(item) {
    return item.key + '=' + item.count;
  }).join('|');
}

function _characterResidualTopCountItems_(map, limit) {
  var items = [];
  Object.keys(map || {}).forEach(function(key) {
    items.push({ key: key, count: Number(map[key] || 0) });
  });
  items.sort(function(a, b) {
    if (a.count !== b.count) return b.count - a.count;
    return String(a.key).localeCompare(String(b.key));
  });
  return items.slice(0, limit || items.length);
}

function _characterResidualIncTokens_(map, items) {
  for (var i = 0; i < (items || []).length; i++) {
    _characterResidualIncSingle_(map, items[i]);
  }
}

function _characterResidualIncSingle_(map, key) {
  var s = String(key || '').trim();
  if (!s) return;
  map[s] = Number(map[s] || 0) + 1;
}

function _characterResidualPipeSplit_(value) {
  if (Array.isArray(value)) {
    return value.map(function(item) { return String(item || '').trim(); }).filter(Boolean);
  }
  var s = String(value || '').trim();
  if (!s) return [];
  return s.split('|').map(function(item) { return String(item || '').trim(); }).filter(Boolean);
}

function _characterResidualJoinPipe_(items) {
  return _characterResidualUniqueStrings_(items || []).join('|');
}

function _characterResidualConcatUnique_(existing, next) {
  return _characterResidualUniqueStrings_(_characterResidualPipeSplit_(existing).concat(next || []));
}

function _characterResidualUniqueStrings_(items) {
  var seen = {};
  var out = [];
  for (var i = 0; i < (items || []).length; i++) {
    var item = String(items[i] || '').trim();
    if (!item || seen[item]) continue;
    seen[item] = true;
    out.push(item);
  }
  return out;
}

function _characterResidualText_(value) {
  return String(value == null ? '' : value).trim();
}

function _characterResidualTruncate_(value, limit) {
  var text = String(value == null ? '' : value);
  var max = Number(limit || 180);
  if (text.length <= max) return text;
  return text.slice(0, Math.max(0, max - 3)) + '...';
}

function _characterResidualNum_(value) {
  if (value === '' || value === null || value === undefined) return null;
  var n = Number(value);
  return isFinite(n) ? n : null;
}

function _characterResidualHasNumeric_(value) {
  return _characterResidualNum_(value) != null;
}

function _characterResidualFirstNonBlank_(values) {
  for (var i = 0; i < (values || []).length; i++) {
    var v = values[i];
    if (v !== '' && v !== null && v !== undefined && String(v).trim() !== '') return String(v).trim();
  }
  return '';
}

function _characterResidualTruth_(value) {
  return String(value || '').trim().toUpperCase() === 'TRUE';
}

function _characterResidualHasMarketContextField_(featurePack, field) {
  return !!(featurePack && featurePack.hasOwnProperty(field) && featurePack[field] !== '' && featurePack[field] !== null && featurePack[field] !== undefined);
}

function _characterResidualIsLowSignalFamily_(family, indicatorName, featurePack) {
  var familyName = String(family || '').toLowerCase();
  var indicator = String(indicatorName || '').toLowerCase();
  if (familyName === 'positioning') return true;
  if (/cftc|positioning/.test(indicator)) return true;
  if (familyName === 'other' && String(featurePack.signal_quality || '').toLowerCase() === 'low') return true;
  if (/fed speeches|statement_report_text|treasury auctions/.test(indicator)) return true;
  return false;
}
