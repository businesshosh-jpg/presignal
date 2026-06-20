/*******************************************************
 * character_recurrence_validation.js
 * - Diagnostic-only Character Residual Recurrence Validation Phase 1B
 * - Compares original Character Residual sample A against a new out-of-sample sample B
 * - Reuses the existing baseline/residual extraction logic
 *******************************************************/

function menuBuildCharacterRecurrenceValidation_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildCharacterRecurrenceValidation_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Character recurrence validation -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Providers=' + (res.provider_rows_written || 0) +
      ' | Families=' + (res.family_rows_written || 0) +
      ' | BlockB=' + (res.sample_b_event_count || 0),
      'Character Recurrence Validation',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Character recurrence validation -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildCharacterRecurrenceValidation_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sampleA = _characterRecurrenceLoadSampleA_(warnings);
  if (!sampleA.rows.length) {
    throw new Error('Character recurrence validation requires an existing Provider_Character_Residuals sample A sheet.');
  }

  var sourceBundles = _characterResidualLoadSources_(warnings);
  var sampleB = _characterRecurrenceBuildSampleB_(sourceBundles, sampleA, generatedTs, warnings);
  if (sampleB.eventIds.length !== 100) {
    throw new Error('Character recurrence validation expected exactly 100 Block B events, got ' + sampleB.eventIds.length);
  }

  var sampleAAggregates = _characterRecurrenceAggregateResidualRows_(sampleA.rows);
  var sampleBAggregates = _characterRecurrenceAggregateResidualRows_(sampleB.rows);

  var providerRows = _characterRecurrenceBuildProviderRows_(generatedTs, sampleAAggregates.byProvider, sampleBAggregates.byProvider);
  var familyRows = _characterRecurrenceBuildFamilyRows_(generatedTs, sampleAAggregates.byProviderFamily, sampleBAggregates.byProviderFamily);

  var providerSheet = getDiagnosticsSheet_('Character_Recurrence_Validation', _characterRecurrenceValidationHeaders_(), warnings);
  var familySheet = getDiagnosticsSheet_('Character_Recurrence_Family_Validation', _characterRecurrenceFamilyHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    providerSheet.sheet,
    providerSheet.headers,
    _characterResidualObjectsToRows_(providerRows, providerSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    familySheet.sheet,
    familySheet.headers,
    _characterResidualObjectsToRows_(familyRows, familySheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    provider_sheet: providerSheet.sheet.getName(),
    family_sheet: familySheet.sheet.getName(),
    provider_rows_written: providerRows.length,
    family_rows_written: familyRows.length,
    sample_a_rows: sampleA.rows.length,
    sample_b_event_count: sampleB.eventIds.length,
    sample_b_rows: sampleB.rows.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function _characterRecurrenceValidationHeaders_() {
  return [
    'generated_ts',
    'provider',
    'sample_a_rows',
    'sample_b_rows',
    'sample_a_risk_distribution',
    'sample_b_risk_distribution',
    'sample_a_uncertainty_distribution',
    'sample_b_uncertainty_distribution',
    'sample_a_top_emphasized_factors',
    'sample_b_top_emphasized_factors',
    'sample_a_direction_distribution',
    'sample_b_direction_distribution',
    'risk_similarity_score',
    'uncertainty_similarity_score',
    'factor_similarity_score',
    'direction_similarity_score',
    'recurrence_score',
    'recurrence_classification',
    'validation_note'
  ];
}

function _characterRecurrenceFamilyHeaders_() {
  return [
    'generated_ts',
    'provider',
    'outcome_family',
    'sample_a_rows',
    'sample_b_rows',
    'recurrence_score',
    'recurrence_classification',
    'sample_depth_warning'
  ];
}

function _characterRecurrenceLoadSampleA_(warnings) {
  var bundle = _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false);
  if (!bundle) return { rows: [], eventIds: {}, maxReleaseMs: 0 };
  var rows = _characterRecurrenceBundleRowsToObjects_(bundle);
  var byEvent = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    if (!byEvent[eventId]) {
      byEvent[eventId] = {
        event_id: eventId,
        release_ms: _characterResidualDateMs_(row.release_ts),
        rows: []
      };
    }
    byEvent[eventId].rows.push(row);
    var ms = _characterResidualDateMs_(row.release_ts);
    if (!byEvent[eventId].release_ms || (ms && ms < byEvent[eventId].release_ms)) {
      byEvent[eventId].release_ms = ms;
    }
  }

  var orderedEvents = Object.keys(byEvent).sort(function(a, b) {
    var ea = byEvent[a] || {};
    var eb = byEvent[b] || {};
    if (ea.release_ms !== eb.release_ms) return (ea.release_ms || 0) - (eb.release_ms || 0);
    return String(a).localeCompare(String(b));
  });

  var selectedIds = orderedEvents.slice(0, 100);
  if (selectedIds.length < 100) {
    warnings.push('sample_a_shortfall:' + selectedIds.length);
  }

  var selectedSet = {};
  var maxReleaseMs = 0;
  var selectedRows = [];
  for (var j = 0; j < selectedIds.length; j++) {
    var selectedId = selectedIds[j];
    selectedSet[selectedId] = true;
    var entry = byEvent[selectedId] || {};
    if ((entry.release_ms || 0) > maxReleaseMs) maxReleaseMs = entry.release_ms || 0;
    selectedRows = selectedRows.concat(entry.rows || []);
  }

  return { rows: selectedRows, eventIds: selectedSet, maxReleaseMs: maxReleaseMs };
}

function _characterRecurrenceBuildSampleB_(sources, sampleA, generatedTs, warnings) {
  var eventBundle = sources.eventsBundle || null;
  var predBundle = sources.predictionsBundle || null;
  var contextMap = _characterResidualBuildContextMap_(sources.featurePackAuditBundle, sources.v2bCoreAuditBundle, warnings);
  var eventMap = _characterResidualBuildEventMap_(eventBundle, warnings);
  var predIdx = predBundle ? predBundle.idx : {};
  var candidateIds = [];

  Object.keys(eventMap).forEach(function(eventId) {
    if (sampleA.eventIds[eventId]) return;
    var eventMeta = eventMap[eventId] || {};
    if (!_characterResidualHasNumeric_(eventMeta.actual_value)) return;
    if (!_characterResidualFirstPredictionForEvent_(predBundle, eventId)) return;
    candidateIds.push(eventId);
  });

  candidateIds.sort(function(a, b) {
    var ea = eventMap[a] || {};
    var eb = eventMap[b] || {};
    var ta = _characterResidualDateMs_(ea.release_ts);
    var tb = _characterResidualDateMs_(eb.release_ts);
    if (ta !== tb) return ta - tb;
    return String(a).localeCompare(String(b));
  });

  var afterCutoff = [];
  for (var i = 0; i < candidateIds.length; i++) {
    var eventId = candidateIds[i];
    var releaseMs = _characterResidualDateMs_((eventMap[eventId] || {}).release_ts);
    if (releaseMs > sampleA.maxReleaseMs) afterCutoff.push(eventId);
  }
  var selectedIds = afterCutoff.length >= 100 ? afterCutoff.slice(0, 100) : candidateIds.slice(0, 100);
  if (selectedIds.length < 100) {
    warnings.push('sample_b_shortfall:' + selectedIds.length);
  }

  var selectedSet = {};
  for (var j = 0; j < selectedIds.length; j++) selectedSet[selectedIds[j]] = true;

  var filteredSources = {
    eventsBundle: _characterRecurrenceFilterBundle_(eventBundle, selectedSet, false),
    predictionsBundle: _characterRecurrenceFilterBundle_(predBundle, selectedSet, true),
    featurePackAuditBundle: _characterRecurrenceFilterBundle_(sources.featurePackAuditBundle, selectedSet, false),
    v2bCoreAuditBundle: _characterRecurrenceFilterBundle_(sources.v2bCoreAuditBundle, selectedSet, false)
  };

  var baselineMap = _characterResidualBuildBaselineMap_(filteredSources, generatedTs, warnings);
  var rows = _characterResidualResidualRows_(filteredSources, baselineMap, generatedTs, warnings);
  return {
    eventIds: selectedIds,
    rows: rows,
    baselineMap: baselineMap,
    contextMap: contextMap,
    predIdx: predIdx
  };
}

function _characterRecurrenceFilterBundle_(bundle, eventSet, dedupePredictions) {
  if (!bundle || !bundle.rows) return bundle;
  var idx = bundle.idx || {};
  var rows = [];
  for (var i = 0; i < bundle.rows.length; i++) {
    var row = bundle.rows[i];
    var eventId = String(_predValue_(row, idx, 'event_id') || '').trim();
    if (!eventId || !eventSet[eventId]) continue;
    rows.push(row);
  }
  if (dedupePredictions) rows = _characterResidualDedupePredictionRows_(rows, idx);
  return {
    sheet: bundle.sheet,
    headers: bundle.headers,
    idx: idx,
    rows: rows,
    workbook_type: bundle.workbook_type || '',
    sheet_name: bundle.sheet_name || ''
  };
}

function _characterRecurrenceBundleRowsToObjects_(bundle) {
  var rows = (bundle && bundle.rows) || [];
  var headers = (bundle && bundle.headers) || [];
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = row[j];
    }
    out.push(obj);
  }
  return out;
}

function _characterRecurrenceAggregateResidualRows_(rows) {
  var byProvider = {};
  var byProviderFamily = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var family = String(row.outcome_family || '').trim() || 'other';
    if (!provider) continue;

    if (!byProvider[provider]) {
      byProvider[provider] = _characterRecurrenceBlankGroup_();
    }
    _characterRecurrenceAccumulateGroup_(byProvider[provider], row);

    var key = provider + '|' + family;
    if (!byProviderFamily[key]) {
      byProviderFamily[key] = _characterRecurrenceBlankGroup_();
      byProviderFamily[key].provider = provider;
      byProviderFamily[key].outcome_family = family;
    }
    _characterRecurrenceAccumulateGroup_(byProviderFamily[key], row);
  }

  return { byProvider: byProvider, byProviderFamily: byProviderFamily };
}

function _characterRecurrenceBlankGroup_() {
  return {
    provider: '',
    outcome_family: '',
    row_count: 0,
    risk: {},
    uncertainty: {},
    direction: {},
    factors: {}
  };
}

function _characterRecurrenceAccumulateGroup_(group, row) {
  group.row_count += 1;
  _characterRecurrenceIncSingle_(group.risk, row.risk_language);
  _characterRecurrenceIncSingle_(group.uncertainty, row.uncertainty_pattern);
  _characterRecurrenceIncSingle_(group.direction, row.direction_delta_from_baseline);
  _characterRecurrenceIncTokens_(group.factors, _characterResidualPipeSplit_(row.emphasized_factors));
}

function _characterRecurrenceBuildProviderRows_(generatedTs, aGroups, bGroups) {
  var providers = {};
  Object.keys(aGroups || {}).forEach(function(provider) { providers[provider] = true; });
  Object.keys(bGroups || {}).forEach(function(provider) { providers[provider] = true; });

  var rows = [];
  Object.keys(providers).sort().forEach(function(provider) {
    var a = aGroups[provider] || _characterRecurrenceBlankGroup_();
    var b = bGroups[provider] || _characterRecurrenceBlankGroup_();
    var riskSim = _characterRecurrenceSimilarity_(a.risk, b.risk);
    var uncertaintySim = _characterRecurrenceSimilarity_(a.uncertainty, b.uncertainty);
    var factorSim = _characterRecurrenceSimilarity_(a.factors, b.factors);
    var directionSim = _characterRecurrenceSimilarity_(a.direction, b.direction);
    var recurrenceScore = _characterRecurrenceWeightedScore_(riskSim, uncertaintySim, factorSim, directionSim);
    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      sample_a_rows: a.row_count,
      sample_b_rows: b.row_count,
      sample_a_risk_distribution: _characterResidualCountMapText_(a.risk, 6),
      sample_b_risk_distribution: _characterResidualCountMapText_(b.risk, 6),
      sample_a_uncertainty_distribution: _characterResidualCountMapText_(a.uncertainty, 6),
      sample_b_uncertainty_distribution: _characterResidualCountMapText_(b.uncertainty, 6),
      sample_a_top_emphasized_factors: _characterResidualCountMapText_(a.factors, 5),
      sample_b_top_emphasized_factors: _characterResidualCountMapText_(b.factors, 5),
      sample_a_direction_distribution: _characterResidualCountMapText_(a.direction, 6),
      sample_b_direction_distribution: _characterResidualCountMapText_(b.direction, 6),
      risk_similarity_score: _round4_(riskSim),
      uncertainty_similarity_score: _round4_(uncertaintySim),
      factor_similarity_score: _round4_(factorSim),
      direction_similarity_score: _round4_(directionSim),
      recurrence_score: _round4_(recurrenceScore),
      recurrence_classification: _characterRecurrenceClassify_(recurrenceScore),
      validation_note: 'Block A is the original Character Residual sample; Block B is a later independent 100-event slice using identical residual logic.'
    });
  });
  return rows;
}

function _characterRecurrenceBuildFamilyRows_(generatedTs, aGroups, bGroups) {
  var groups = {};
  Object.keys(aGroups || {}).forEach(function(key) { groups[key] = true; });
  Object.keys(bGroups || {}).forEach(function(key) { groups[key] = true; });

  var rows = [];
  Object.keys(groups).sort().forEach(function(key) {
    var a = aGroups[key] || _characterRecurrenceBlankGroup_();
    var b = bGroups[key] || _characterRecurrenceBlankGroup_();
    var provider = a.provider || b.provider || '';
    var family = a.outcome_family || b.outcome_family || 'other';
    var riskSim = _characterRecurrenceSimilarity_(a.risk, b.risk);
    var uncertaintySim = _characterRecurrenceSimilarity_(a.uncertainty, b.uncertainty);
    var factorSim = _characterRecurrenceSimilarity_(a.factors, b.factors);
    var directionSim = _characterRecurrenceSimilarity_(a.direction, b.direction);
    var recurrenceScore = _characterRecurrenceWeightedScore_(riskSim, uncertaintySim, factorSim, directionSim);
    var sampleDepthWarning = (a.row_count < 5 || b.row_count < 5) ? 'thin_sample' : '';
    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      outcome_family: family,
      sample_a_rows: a.row_count,
      sample_b_rows: b.row_count,
      recurrence_score: _round4_(recurrenceScore),
      recurrence_classification: _characterRecurrenceClassify_(recurrenceScore),
      sample_depth_warning: sampleDepthWarning
    });
  });
  return rows;
}

function _characterRecurrenceSimilarity_(mapA, mapB) {
  var normA = _characterRecurrenceNormalizeMap_(mapA);
  var normB = _characterRecurrenceNormalizeMap_(mapB);
  var keys = {};
  Object.keys(normA).forEach(function(k) { keys[k] = true; });
  Object.keys(normB).forEach(function(k) { keys[k] = true; });
  var totalDiff = 0;
  var count = 0;
  Object.keys(keys).forEach(function(key) {
    totalDiff += Math.abs((normA[key] || 0) - (normB[key] || 0));
    count += 1;
  });
  if (!count) return 1;
  return Math.max(0, 1 - (totalDiff / 2));
}

function _characterRecurrenceNormalizeMap_(map) {
  var total = 0;
  Object.keys(map || {}).forEach(function(key) {
    total += Number(map[key] || 0);
  });
  var out = {};
  if (!(total > 0)) return out;
  Object.keys(map || {}).forEach(function(key) {
    out[key] = Number(map[key] || 0) / total;
  });
  return out;
}

function _characterRecurrenceWeightedScore_(riskSim, uncertaintySim, factorSim, directionSim) {
  return (
    (Number(riskSim) * 0.25) +
    (Number(uncertaintySim) * 0.25) +
    (Number(factorSim) * 0.35) +
    (Number(directionSim) * 0.15)
  );
}

function _characterRecurrenceClassify_(score) {
  var s = Number(score || 0);
  if (s >= 0.8) return 'strong_recurrence';
  if (s >= 0.65) return 'moderate_recurrence';
  if (s >= 0.5) return 'weak_recurrence';
  return 'no_recurrence';
}

function _characterRecurrenceIncSingle_(map, key) {
  var s = String(key || '').trim();
  if (!s) return;
  map[s] = Number(map[s] || 0) + 1;
}

function _characterRecurrenceIncTokens_(map, tokens) {
  for (var i = 0; i < (tokens || []).length; i++) {
    _characterRecurrenceIncSingle_(map, tokens[i]);
  }
}
