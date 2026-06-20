/*******************************************************
 * character_signal_shadow_test.js
 * - Diagnostic-only Character Signal Shadow Test v1
 * - Tests whether validated Character Signal Candidates separate
 *   better forecasts from worse forecasts in shadow mode
 * - Read-only over existing diagnostics / outcome sheets
 *******************************************************/

function menuBuildCharacterSignalShadowTest_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildCharacterSignalShadowTest_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Character signal shadow test -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Shadow=' + (res.shadow_rows_written || 0) +
      ' | Family=' + (res.family_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0),
      'Character Signal Shadow Test',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Character signal shadow test -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildCharacterSignalShadowTest_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _characterSignalShadowLoadSources_(warnings);
  var candidateDefs = _characterSignalShadowBuildUniverse_(sources, warnings);
  if (!candidateDefs.length) warnings.push('shadow_candidate_universe_empty');

  var residualLookup = _characterOutcomeBuildResidualLookup_(sources.residualBundle, warnings);
  var outcomeLookup = _characterSignalShadowBuildOutcomeLookup_(sources.outcomeBundle, sources.economicBundle, warnings);
  var econLookup = _characterSignalShadowBuildEconomicLookup_(sources.economicBundle, warnings);
  var providerCaseMap = _characterSignalShadowBuildProviderCaseMap_(outcomeLookup, econLookup, residualLookup, warnings);
  var providerFamilyCaseMap = _characterSignalShadowBuildProviderFamilyCaseMap_(providerCaseMap, warnings);

  var rows = _characterSignalShadowBuildRows_(generatedTs, candidateDefs, providerCaseMap, warnings);
  var familyRows = _characterSignalShadowBuildFamilyRows_(generatedTs, candidateDefs, providerFamilyCaseMap, warnings);
  var summaryRows = _characterSignalShadowBuildSummaryRows_(generatedTs, rows, candidateDefs, warnings);
  var readinessRows = _characterSignalShadowBuildReadinessRows_(generatedTs, rows, warnings);

  var shadowSheet = getDiagnosticsSheet_('Character_Signal_Shadow_Test', _characterSignalShadowHeaders_(), warnings);
  var familySheet = getDiagnosticsSheet_('Character_Signal_Shadow_Family_Test', _characterSignalShadowFamilyHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Character_Signal_Shadow_Summary', _characterSignalShadowSummaryHeaders_(), warnings);
  var readinessSheet = getDiagnosticsSheet_('Character_Signal_Shadow_Readiness', _characterSignalShadowReadinessHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    shadowSheet.sheet,
    shadowSheet.headers,
    _characterResidualObjectsToRows_(rows, shadowSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    familySheet.sheet,
    familySheet.headers,
    _characterResidualObjectsToRows_(familyRows, familySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    summarySheet.sheet,
    summarySheet.headers,
    _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    readinessSheet.sheet,
    readinessSheet.headers,
    _characterResidualObjectsToRows_(readinessRows, readinessSheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    shadow_sheet: shadowSheet.sheet.getName(),
    family_sheet: familySheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    readiness_sheet: readinessSheet.sheet.getName(),
    shadow_rows_written: rows.length,
    family_rows_written: familyRows.length,
    summary_rows_written: summaryRows.length,
    readiness_rows_written: readinessRows.length,
    candidate_count: candidateDefs.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function _characterSignalShadowHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'signal_candidate_id',
    'signal_family',
    'trait_domain',
    'recurrence_score',
    'outcome_link_status',
    'falsification_status',
    'drift_status',
    'profile_similarity_score',
    'row_count_present',
    'row_count_absent',
    'outcome_score_present_avg',
    'outcome_score_absent_avg',
    'outcome_score_delta',
    'overall_ok_present_rate',
    'overall_ok_absent_rate',
    'overall_ok_delta',
    'dir_ok_present_rate',
    'dir_ok_absent_rate',
    'dir_ok_delta',
    'strength_ok_present_rate',
    'strength_ok_absent_rate',
    'strength_ok_delta',
    'sustain_ok_present_rate',
    'sustain_ok_absent_rate',
    'sustain_ok_delta',
    'economic_value_accuracy_present_rate',
    'economic_value_accuracy_absent_rate',
    'economic_value_accuracy_delta',
    'sample_depth_warning',
    'shadow_result',
    'shadow_confidence',
    'shadow_interpretation_note',
    'candidate_status',
    'recommended_future_use'
  ];
}

function _characterSignalShadowFamilyHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'outcome_family',
    'signal_candidate_id',
    'signal_family',
    'trait_domain',
    'row_count_present',
    'row_count_absent',
    'outcome_score_present_avg',
    'outcome_score_absent_avg',
    'outcome_score_delta',
    'overall_ok_present_rate',
    'overall_ok_absent_rate',
    'overall_ok_delta',
    'dir_ok_present_rate',
    'dir_ok_absent_rate',
    'dir_ok_delta',
    'economic_value_accuracy_present_rate',
    'economic_value_accuracy_absent_rate',
    'economic_value_accuracy_delta',
    'sample_depth_warning',
    'family_shadow_result',
    'family_interpretation_note',
    'candidate_status',
    'recommended_future_use'
  ];
}

function _characterSignalShadowSummaryHeaders_() {
  return [
    'generated_ts',
    'provider',
    'candidate_status',
    'candidates_tested',
    'shadow_positive_count',
    'shadow_negative_count',
    'shadow_neutral_count',
    'shadow_mixed_count',
    'shadow_inconclusive_count',
    'best_shadow_positive_candidates',
    'worst_shadow_negative_candidates',
    'strongest_reliability_candidates',
    'strongest_calibration_candidates',
    'provider_shadow_summary_note'
  ];
}

function _characterSignalShadowReadinessHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'candidate_status',
    'recurrence_evidence',
    'falsification_evidence',
    'drift_evidence',
    'shadow_test_result',
    'shadow_effect_size',
    'sample_depth_evidence',
    'reliability_signal_readiness',
    'calibration_shadow_readiness',
    'next_action',
    'final_note'
  ];
}

function _characterSignalShadowLoadSources_(warnings) {
  return {
    candidateBundle: _characterResidualReadSheetBundle_('Character_Signal_Candidates', warnings, false),
    readinessBundle: _characterResidualReadSheetBundle_('Character_Signal_Readiness_Report', warnings, false),
    residualBundle: _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false),
    outcomeBundle: _characterResidualReadSheetBundle_('Outcome_Ledger', warnings, true),
    economicBundle: _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false),
    familyEconomicBundle: _characterResidualReadSheetBundle_('Provider_Family_Economic_Accuracy', warnings, false),
    evaluationRowsBundle: _characterResidualReadSheetBundle_('Evaluation_Rows', warnings, false),
    recurrenceValidationBundle: _characterResidualReadSheetBundle_('Character_Outcome_Recurrence_Validation', warnings, false),
    recurrenceInterpretationBundle: _characterResidualReadSheetBundle_('Character_Outcome_Recurrence_Interpretation', warnings, false),
    driftBundle: _characterResidualReadSheetBundle_('Character_Drift_Assessment', warnings, false),
    falsificationBundle: _characterResidualReadSheetBundle_('Character_Outcome_Falsification_Report', warnings, false),
    candidateSummaryBundle: _characterResidualReadSheetBundle_('Character_Signal_Candidate_Summary', warnings, false)
  };
}

function _characterSignalShadowBuildUniverse_(sources, warnings) {
  var rows = [];
  var seen = {};
  var fallbackRows = [];
  if (sources.candidateBundle) fallbackRows = _characterSignalCandidateBundleRowsToObjects_(sources.candidateBundle);
  if (!fallbackRows.length && sources.readinessBundle) fallbackRows = _characterSignalCandidateBundleRowsToObjects_(sources.readinessBundle);

  for (var i = 0; i < (fallbackRows || []).length; i++) {
    var row = fallbackRows[i] || {};
    var provider = String(row.provider || '').trim();
    var trait = String(row.trait || '').trim();
    if (!provider || !trait) continue;
    var candidateStatus = String(row.candidate_status || '').trim();
    var recommendedFutureUse = String(row.recommended_future_use || '').trim();
    if (candidateStatus === 'strong_candidate') {
      if (recommendedFutureUse && recommendedFutureUse !== 'shadow_calibration_test') continue;
      if (!recommendedFutureUse) recommendedFutureUse = 'shadow_calibration_test';
    } else if (candidateStatus === 'medium_candidate') {
      if (recommendedFutureUse && recommendedFutureUse !== 'reliability_signal_test') continue;
      if (!recommendedFutureUse) recommendedFutureUse = 'reliability_signal_test';
    } else {
      continue;
    }

    var key = provider + '|' + trait;
    if (seen[key]) continue;
    seen[key] = true;

    rows.push({
      provider: provider,
      trait: trait,
      signal_candidate_id: String(row.signal_candidate_id || (provider + '__' + trait)).trim(),
      signal_family: String(row.signal_family || '').trim() || _characterSignalCandidateSignalFamily_(String(row.trait_domain || '')),
      trait_domain: String(row.trait_domain || '').trim() || _characterSignalShadowTraitDomain_(trait),
      recurrence_score: _characterSignalCandidateNum_(row.recurrence_score, ''),
      outcome_link_status: String(row.outcome_link_status || '').trim(),
      falsification_status: String(row.falsification_status || '').trim(),
      drift_status: String(row.drift_status || '').trim(),
      profile_similarity_score: _characterSignalCandidateNum_(row.profile_similarity_score, ''),
      discovery_score_delta: _characterSignalCandidateNum_(row.discovery_score_delta, ''),
      validation_score_delta: _characterSignalCandidateNum_(row.validation_score_delta, ''),
      effect_direction: String(row.effect_direction || '').trim(),
      effect_size_stability: _characterSignalCandidateNum_(row.effect_size_stability, ''),
      sample_size_total: Number(row.sample_size_total || 0),
      sample_size_discovery: Number(row.sample_size_discovery || 0),
      sample_size_validation: Number(row.sample_size_validation || 0),
      sample_depth_warning: String(row.sample_depth_warning || '').trim(),
      confidence_level: String(row.confidence_level || '').trim(),
      candidate_status: candidateStatus,
      recommended_future_use: recommendedFutureUse,
      recurrence_classification: String(row.recurrence_classification || '').trim()
    });
  }

  rows.sort(function(a, b) {
    var ap = String(a.provider || '');
    var bp = String(b.provider || '');
    if (ap !== bp) return ap.localeCompare(bp);
    var ar = _characterSignalShadowCandidateRankBucket_(a.candidate_status);
    var br = _characterSignalShadowCandidateRankBucket_(b.candidate_status);
    if (ar !== br) return ar - br;
    var as = _characterSignalCandidateNum_(a.recurrence_score, '');
    var bs = _characterSignalCandidateNum_(b.recurrence_score, '');
    if (as !== bs) return (bs || 0) - (as || 0);
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  });

  if (!rows.length) warnings.push('shadow_candidate_universe_shortfall:0');
  return rows;
}

function _characterSignalShadowBuildOutcomeLookup_(outcomeBundle, economicBundle, warnings) {
  var lookup = {};
  var outcomeRows = _characterOutcomeBundleRowsToObjects_(outcomeBundle);
  for (var i = 0; i < (outcomeRows || []).length; i++) {
    var row = outcomeRows[i] || {};
    if (!_characterOutcomeIsScoredRow_(row)) continue;
    var provider = String(row.ai_name || row.provider || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var key = eventId + '|' + provider;
    if (!lookup[key]) {
      lookup[key] = _characterSignalShadowOutcomeFromOutcomeLedgerRow_(row);
    }
  }

  if (!Object.keys(lookup).length && economicBundle) {
    var econRows = _characterSignalShadowEconomicRows_(economicBundle);
    for (var j = 0; j < econRows.length; j++) {
      var econ = econRows[j];
      if (!econ || econ.value_scored_flag !== 'TRUE') continue;
      var eKey = econ.event_id + '|' + econ.provider;
      if (lookup[eKey]) continue;
      lookup[eKey] = _characterSignalShadowOutcomeFromEconomicRow_(econ);
    }
    warnings.push('outcome_lookup_fallback:Economic_Value_Accuracy');
  }

  return {
    by_key: lookup,
    by_provider: _characterSignalShadowGroupBy_(lookup, function(row) { return row.provider || 'unknown'; }),
    by_provider_family: _characterSignalShadowGroupBy_(lookup, function(row) { return (row.provider || 'unknown') + '|' + (row.outcome_family || 'other'); })
  };
}

function _characterSignalShadowBuildEconomicLookup_(economicBundle, warnings) {
  var rows = _characterSignalShadowEconomicRows_(economicBundle);
  var out = {
    by_key: {},
    by_provider: {},
    by_provider_family: {}
  };
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var key = eventId + '|' + provider;
    if (!out.by_key[key]) out.by_key[key] = row;
    if (!out.by_provider[provider]) out.by_provider[provider] = [];
    out.by_provider[provider].push(row);
    var familyKey = provider + '|' + String(row.outcome_family || 'other').trim();
    if (!out.by_provider_family[familyKey]) out.by_provider_family[familyKey] = [];
    out.by_provider_family[familyKey].push(row);
  }
  return out;
}

function _characterSignalShadowEconomicRows_(economicBundle) {
  if (!economicBundle) return [];
  var rawRows = _characterOutcomeBundleRowsToObjects_(economicBundle);
  var out = [];
  for (var i = 0; i < rawRows.length; i++) {
    var row = rawRows[i] || {};
    if (String(row.row_type || '').trim() !== 'case') continue;
    var provider = String(row.ai_name || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var scored = String(row.value_scored_flag || '').trim().toUpperCase() === 'TRUE';
    var hasValueDir = row.hasOwnProperty('value_dir_ok') && String(row.value_dir_ok).trim() !== '';
    if (!scored && !hasValueDir) continue;
    out.push({
      generated_ts: String(row.generated_ts || '').trim(),
      event_id: eventId,
      provider: provider,
      outcome_family: String(row.family || row.outcome_family || '').trim() || 'other',
      value_dir_ok: String(row.value_dir_ok || '').trim().toUpperCase() === 'TRUE',
      overall_ok: String(row.overall_ok || '').trim().toUpperCase() === 'TRUE',
      dir_ok: String(row.mr_dir_ok || '').trim().toUpperCase() === 'TRUE',
      strength_ok: String(row.mr_strength_ok || '').trim().toUpperCase() === 'TRUE',
      sustain_ok: String(row.mr_sustain_ok || '').trim().toUpperCase() === 'TRUE',
      value_scored_flag: scored ? 'TRUE' : 'FALSE'
    });
  }
  return out;
}

function _characterSignalShadowOutcomeFromOutcomeLedgerRow_(row) {
  var overallOk = String(row.overall_ok || '').trim().toUpperCase() === 'TRUE';
  var dirOk = String(row.dir_ok || '').trim().toUpperCase() === 'TRUE';
  var strengthOk = String(row.strength_ok || '').trim().toUpperCase() === 'TRUE';
  var sustainOk = String(row.sustain_ok || '').trim().toUpperCase() === 'TRUE';
  var score = _characterOutcomeNum_(row.outcome_score);
  if (score == null) score = _characterOutcomeNum_(computeOutcomeScore_({
    scored_flag: 'TRUE',
    mr_dir_ok: dirOk ? 'TRUE' : 'FALSE',
    mr_strength_ok: strengthOk ? 'TRUE' : 'FALSE',
    mr_sustain_ok: sustainOk ? 'TRUE' : 'FALSE',
    overall_ok: overallOk ? 'TRUE' : 'FALSE'
  }));
  if (score != null) score = _round4_(Number(score));
  return {
    event_id: String(row.event_id || '').trim(),
    provider: String(row.provider || '').trim(),
    outcome_family: String(row.outcome_family || '').trim() || 'other',
    overall_ok: overallOk,
    dir_ok: dirOk,
    strength_ok: strengthOk,
    sustain_ok: sustainOk,
    outcome_score: score == null ? null : score,
    value_dir_ok: null,
    source: 'Outcome_Ledger'
  };
}

function _characterSignalShadowOutcomeFromEconomicRow_(row) {
  var overallOk = !!row.overall_ok;
  var dirOk = !!row.dir_ok;
  var strengthOk = !!row.strength_ok;
  var sustainOk = !!row.sustain_ok;
  var score = computeOutcomeScore_({
    scored_flag: 'TRUE',
    mr_dir_ok: dirOk ? 'TRUE' : 'FALSE',
    mr_strength_ok: strengthOk ? 'TRUE' : 'FALSE',
    mr_sustain_ok: sustainOk ? 'TRUE' : 'FALSE',
    overall_ok: overallOk ? 'TRUE' : 'FALSE'
  });
  score = score == null || score === '' ? null : _round4_(Number(score) / 6);
  return {
    event_id: String(row.event_id || '').trim(),
    provider: String(row.provider || '').trim(),
    outcome_family: String(row.outcome_family || '').trim() || 'other',
    overall_ok: overallOk,
    dir_ok: dirOk,
    strength_ok: strengthOk,
    sustain_ok: sustainOk,
    outcome_score: score,
    value_dir_ok: !!row.value_dir_ok,
    source: 'Economic_Value_Accuracy'
  };
}

function _characterSignalShadowBuildProviderCaseMap_(outcomeLookup, econLookup, residualLookup, warnings) {
  var byProvider = {};
  var keys = {};
  Object.keys(outcomeLookup.by_key || {}).forEach(function(key) { keys[key] = true; });
  Object.keys(econLookup.by_key || {}).forEach(function(key) { keys[key] = true; });

  Object.keys(keys).forEach(function(key) {
    var outcome = outcomeLookup.by_key[key] || null;
    var econ = econLookup.by_key[key] || null;
    var residual = residualLookup[key] || null;
    if (!residual && !outcome && !econ) return;
    var provider = String((residual && residual.provider) || (outcome && outcome.provider) || (econ && econ.provider) || '').trim();
    if (!provider) return;
    var family = String((outcome && outcome.outcome_family) || (econ && econ.outcome_family) || (residual && residual.outcome_family) || 'other').trim() || 'other';
    if (!byProvider[provider]) byProvider[provider] = [];
    byProvider[provider].push({
      key: key,
      provider: provider,
      outcome_family: family,
      residual: residual,
      outcome: outcome || (econ ? _characterSignalShadowOutcomeFromEconomicRow_(econ) : null),
      econ: econ
    });
  });

  return byProvider;
}

function _characterSignalShadowBuildProviderFamilyCaseMap_(providerCaseMap, warnings) {
  var byProviderFamily = {};
  Object.keys(providerCaseMap || {}).forEach(function(provider) {
    var rows = providerCaseMap[provider] || [];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i] || {};
      var family = String(row.outcome_family || 'other').trim() || 'other';
      var key = provider + '|' + family;
      if (!byProviderFamily[key]) byProviderFamily[key] = [];
      byProviderFamily[key].push(row);
    }
  });
  return byProviderFamily;
}

function _characterSignalShadowBuildRows_(generatedTs, candidateDefs, providerCaseMap, warnings) {
  var rows = [];
  for (var i = 0; i < (candidateDefs || []).length; i++) {
    var candidate = candidateDefs[i] || {};
    var provider = String(candidate.provider || '').trim();
    var trait = String(candidate.trait || '').trim();
    var cases = providerCaseMap[provider] || [];
    var stats = _characterSignalShadowBlankStats_();
    var present = _characterSignalShadowBlankStats_();
    var absent = _characterSignalShadowBlankStats_();

    for (var j = 0; j < cases.length; j++) {
      var c = cases[j] || {};
      var residual = c.residual || null;
      var outcome = c.outcome || null;
      if (!residual || !outcome) continue;
      var matches = _characterOutcomeTraitMatchesResidual_(
        { trait: trait, domains: _characterOutcomeRecurrenceInferTraitDomains_(trait) },
        residual
      );
      _characterSignalShadowAccumulate_(stats, outcome, c.econ);
      if (matches) _characterSignalShadowAccumulate_(present, outcome, c.econ);
      else _characterSignalShadowAccumulate_(absent, outcome, c.econ);
    }

    rows.push(_characterSignalShadowFinalizeRow_(generatedTs, candidate, stats, present, absent, warnings));
  }
  return rows;
}

function _characterSignalShadowBuildFamilyRows_(generatedTs, candidateDefs, providerFamilyCaseMap, warnings) {
  var out = [];
  for (var i = 0; i < (candidateDefs || []).length; i++) {
    var candidate = candidateDefs[i] || {};
    var provider = String(candidate.provider || '').trim();
    var trait = String(candidate.trait || '').trim();
    var keys = Object.keys(providerFamilyCaseMap || {}).filter(function(key) {
      return String(key || '').indexOf(provider + '|') === 0;
    });
    for (var k = 0; k < keys.length; k++) {
      var familyKey = keys[k];
      var family = String(familyKey.split('|')[1] || '').trim() || 'other';
      var cases = providerFamilyCaseMap[familyKey] || [];
      var stats = _characterSignalShadowBlankStats_();
      var present = _characterSignalShadowBlankStats_();
      var absent = _characterSignalShadowBlankStats_();
      for (var j = 0; j < cases.length; j++) {
        var c = cases[j] || {};
        var residual = c.residual || null;
        var outcome = c.outcome || null;
        if (!residual || !outcome) continue;
        var matches = _characterOutcomeTraitMatchesResidual_(
          { trait: trait, domains: _characterOutcomeRecurrenceInferTraitDomains_(trait) },
          residual
        );
        _characterSignalShadowAccumulate_(stats, outcome, c.econ);
        if (matches) _characterSignalShadowAccumulate_(present, outcome, c.econ);
        else _characterSignalShadowAccumulate_(absent, outcome, c.econ);
      }
      out.push(_characterSignalShadowFinalizeFamilyRow_(generatedTs, candidate, family, stats, present, absent, warnings));
    }
  }
  return out;
}

function _characterSignalShadowBuildSummaryRows_(generatedTs, rows, candidateDefs, warnings) {
  var byProvider = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var status = String(row.candidate_status || '').trim();
    if (!provider || !status) continue;
    var key = provider + '|' + status;
    if (!byProvider[key]) {
      byProvider[key] = {
        provider: provider,
        candidate_status: status,
        candidates_tested: 0,
        positive: [],
        negative: [],
        neutral: [],
        mixed: [],
        inconclusive: [],
        reliability: [],
        calibration: []
      };
    }
    var g = byProvider[key];
    g.candidates_tested += 1;
    var result = String(row.shadow_result || '').trim();
    if (result === 'shadow_positive') g.positive.push({ trait: row.trait, score: _characterSignalShadowSummaryScore_(row) });
    else if (result === 'shadow_negative') g.negative.push({ trait: row.trait, score: _characterSignalShadowSummaryScore_(row) });
    else if (result === 'shadow_neutral') g.neutral.push({ trait: row.trait, score: _characterSignalShadowSummaryScore_(row) });
    else if (result === 'shadow_mixed') g.mixed.push({ trait: row.trait, score: _characterSignalShadowSummaryScore_(row) });
    else g.inconclusive.push({ trait: row.trait, score: _characterSignalShadowSummaryScore_(row) });
  }

  var readinessRows = _characterSignalShadowBuildReadinessRows_(generatedTs, rows, warnings);
  var readinessByKey = {};
  for (var r = 0; r < readinessRows.length; r++) {
    var rr = readinessRows[r] || {};
    readinessByKey[String(rr.provider || '').trim() + '|' + String(rr.trait || '').trim()] = rr;
  }

  var out = [];
  Object.keys(byProvider).sort().forEach(function(key) {
    var g = byProvider[key];
    var strongCalibration = [];
    var strongReliability = [];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (String(row.provider || '').trim() + '|' + String(row.candidate_status || '').trim() !== key) continue;
      var readiness = readinessByKey[String(row.provider || '').trim() + '|' + String(row.trait || '').trim()] || {};
      if (String(readiness.calibration_shadow_readiness || '').trim() === 'ready_for_extended_shadow_calibration') {
        strongCalibration.push({ trait: row.trait, score: _characterSignalShadowSummaryScore_(row) });
      }
      if (String(readiness.reliability_signal_readiness || '').trim() === 'ready_for_reliability_monitoring' ||
          String(readiness.calibration_shadow_readiness || '').trim() === 'ready_for_extended_shadow_calibration') {
        strongReliability.push({ trait: row.trait, score: _characterSignalShadowSummaryScore_(row) });
      }
    }
    out.push({
      generated_ts: generatedTs,
      provider: g.provider,
      candidate_status: g.candidate_status,
      candidates_tested: g.candidates_tested,
      shadow_positive_count: g.positive.length,
      shadow_negative_count: g.negative.length,
      shadow_neutral_count: g.neutral.length,
      shadow_mixed_count: g.mixed.length,
      shadow_inconclusive_count: g.inconclusive.length,
      best_shadow_positive_candidates: _characterSignalCandidateTopTraitText_(g.positive, 5, true),
      worst_shadow_negative_candidates: _characterSignalCandidateTopTraitText_(g.negative, 5, false),
      strongest_reliability_candidates: _characterSignalCandidateTopTraitText_(strongReliability, 5, true),
      strongest_calibration_candidates: _characterSignalCandidateTopTraitText_(strongCalibration, 5, true),
      provider_shadow_summary_note: _characterSignalShadowSummaryNote_(g, rows)
    });
  });
  return out;
}

function _characterSignalShadowBuildReadinessRows_(generatedTs, rows, warnings) {
  var out = [];
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (String(row.candidate_status || '').trim() !== 'strong_candidate') continue;
    var readiness = _characterSignalShadowReadiness_(row);
    out.push({
      generated_ts: generatedTs,
      provider: row.provider,
      trait: row.trait,
      candidate_status: row.candidate_status,
      recurrence_evidence: _characterSignalShadowEvidenceText_('recurrence', row.recurrence_score, row.outcome_link_status, row.falsification_status),
      falsification_evidence: _characterSignalShadowEvidenceText_('falsification', row.falsification_status, row.outcome_link_status, ''),
      drift_evidence: _characterSignalShadowEvidenceText_('drift', row.drift_status, row.profile_similarity_score, ''),
      shadow_test_result: row.shadow_result,
      shadow_effect_size: row.shadow_effect_size,
      sample_depth_evidence: row.sample_depth_warning || '',
      reliability_signal_readiness: readiness.reliability_signal_readiness,
      calibration_shadow_readiness: readiness.calibration_shadow_readiness,
      next_action: readiness.next_action,
      final_note: readiness.final_note
    });
  }
  return out;
}

function _characterSignalShadowBlankStats_() {
  return {
    row_count: 0,
    outcome_score_sum: 0,
    outcome_score_count: 0,
    overall_ok_count: 0,
    dir_ok_count: 0,
    strength_ok_count: 0,
    sustain_ok_count: 0,
    econ_value_ok_count: 0,
    econ_value_ok_total: 0
  };
}

function _characterSignalShadowAccumulate_(stats, outcome, econ) {
  if (!stats || !outcome) return;
  stats.row_count += 1;
  var score = _characterOutcomeNum_(outcome.outcome_score);
  if (score != null) {
    stats.outcome_score_sum += score;
    stats.outcome_score_count += 1;
  }
  if (outcome.overall_ok) stats.overall_ok_count += 1;
  if (outcome.dir_ok) stats.dir_ok_count += 1;
  if (outcome.strength_ok) stats.strength_ok_count += 1;
  if (outcome.sustain_ok) stats.sustain_ok_count += 1;
  if (econ && econ.value_scored_flag === 'TRUE') {
    stats.econ_value_ok_total += 1;
    if (econ.value_dir_ok) stats.econ_value_ok_count += 1;
  }
}

function _characterSignalShadowFinalizeRow_(generatedTs, candidate, stats, present, absent, warnings) {
  var sampleTotal = Number(stats.row_count || 0);
  var presentCount = Number(present.row_count || 0);
  var absentCount = Number(absent.row_count || 0);
  var sampleDepthWarning = _characterSignalShadowSampleDepthWarning_(presentCount, absentCount, sampleTotal, present, absent);
  var outcomePresent = _characterSignalShadowStatsToMetrics_(present);
  var outcomeAbsent = _characterSignalShadowStatsToMetrics_(absent);
  var econPresent = _characterSignalShadowEconomicRate_(present);
  var econAbsent = _characterSignalShadowEconomicRate_(absent);

  var outcomeScoreDelta = _characterSignalShadowDelta_(outcomePresent.outcome_score_avg, outcomeAbsent.outcome_score_avg);
  var overallDelta = _characterSignalShadowDelta_(outcomePresent.overall_ok_rate, outcomeAbsent.overall_ok_rate);
  var dirDelta = _characterSignalShadowDelta_(outcomePresent.dir_ok_rate, outcomeAbsent.dir_ok_rate);
  var strengthDelta = _characterSignalShadowDelta_(outcomePresent.strength_ok_rate, outcomeAbsent.strength_ok_rate);
  var sustainDelta = _characterSignalShadowDelta_(outcomePresent.sustain_ok_rate, outcomeAbsent.sustain_ok_rate);
  var econDelta = _characterSignalShadowDelta_(econPresent, econAbsent);
  var effectSize = _characterSignalShadowWeightedEffect_({
    outcome_score_delta: outcomeScoreDelta,
    overall_ok_delta: overallDelta,
    dir_ok_delta: dirDelta,
    strength_ok_delta: strengthDelta,
    sustain_ok_delta: sustainDelta,
    economic_value_accuracy_delta: econDelta
  });
  var result = _characterSignalShadowClassify_(effectSize, {
    outcome_score_delta: outcomeScoreDelta,
    overall_ok_delta: overallDelta,
    dir_ok_delta: dirDelta,
    strength_ok_delta: strengthDelta,
    sustain_ok_delta: sustainDelta,
    economic_value_accuracy_delta: econDelta
  }, sampleDepthWarning);
  var confidence = _characterSignalShadowConfidence_(presentCount, absentCount, sampleTotal, result, candidate);
  var note = _characterSignalShadowInterpretationNote_(candidate, outcomePresent, outcomeAbsent, econPresent, econAbsent, result, effectSize, sampleDepthWarning);

  return {
    generated_ts: generatedTs,
    provider: candidate.provider,
    trait: candidate.trait,
    signal_candidate_id: candidate.signal_candidate_id,
    signal_family: candidate.signal_family,
    trait_domain: candidate.trait_domain,
    recurrence_score: _characterSignalCandidateNum_(candidate.recurrence_score, ''),
    outcome_link_status: candidate.outcome_link_status,
    falsification_status: candidate.falsification_status,
    drift_status: candidate.drift_status,
    profile_similarity_score: _characterSignalCandidateNum_(candidate.profile_similarity_score, ''),
    row_count_present: presentCount,
    row_count_absent: absentCount,
    outcome_score_present_avg: outcomePresent.outcome_score_avg == null ? '' : outcomePresent.outcome_score_avg,
    outcome_score_absent_avg: outcomeAbsent.outcome_score_avg == null ? '' : outcomeAbsent.outcome_score_avg,
    outcome_score_delta: outcomeScoreDelta == null ? '' : outcomeScoreDelta,
    overall_ok_present_rate: outcomePresent.overall_ok_rate == null ? '' : outcomePresent.overall_ok_rate,
    overall_ok_absent_rate: outcomeAbsent.overall_ok_rate == null ? '' : outcomeAbsent.overall_ok_rate,
    overall_ok_delta: overallDelta == null ? '' : overallDelta,
    dir_ok_present_rate: outcomePresent.dir_ok_rate == null ? '' : outcomePresent.dir_ok_rate,
    dir_ok_absent_rate: outcomeAbsent.dir_ok_rate == null ? '' : outcomeAbsent.dir_ok_rate,
    dir_ok_delta: dirDelta == null ? '' : dirDelta,
    strength_ok_present_rate: outcomePresent.strength_ok_rate == null ? '' : outcomePresent.strength_ok_rate,
    strength_ok_absent_rate: outcomeAbsent.strength_ok_rate == null ? '' : outcomeAbsent.strength_ok_rate,
    strength_ok_delta: strengthDelta == null ? '' : strengthDelta,
    sustain_ok_present_rate: outcomePresent.sustain_ok_rate == null ? '' : outcomePresent.sustain_ok_rate,
    sustain_ok_absent_rate: outcomeAbsent.sustain_ok_rate == null ? '' : outcomeAbsent.sustain_ok_rate,
    sustain_ok_delta: sustainDelta == null ? '' : sustainDelta,
    economic_value_accuracy_present_rate: econPresent == null ? '' : econPresent,
    economic_value_accuracy_absent_rate: econAbsent == null ? '' : econAbsent,
    economic_value_accuracy_delta: econDelta == null ? '' : econDelta,
    sample_depth_warning: sampleDepthWarning,
    shadow_result: result,
    shadow_confidence: confidence,
    shadow_interpretation_note: note,
    candidate_status: candidate.candidate_status,
    recommended_future_use: candidate.recommended_future_use,
    shadow_effect_size: effectSize
  };
}

function _characterSignalShadowFinalizeFamilyRow_(generatedTs, candidate, family, stats, present, absent, warnings) {
  var sampleTotal = Number(stats.row_count || 0);
  var presentCount = Number(present.row_count || 0);
  var absentCount = Number(absent.row_count || 0);
  var sampleDepthWarning = _characterSignalShadowSampleDepthWarning_(presentCount, absentCount, sampleTotal, present, absent);
  var outcomePresent = _characterSignalShadowStatsToMetrics_(present);
  var outcomeAbsent = _characterSignalShadowStatsToMetrics_(absent);
  var econPresent = _characterSignalShadowEconomicRate_(present);
  var econAbsent = _characterSignalShadowEconomicRate_(absent);
  var outcomeScoreDelta = _characterSignalShadowDelta_(outcomePresent.outcome_score_avg, outcomeAbsent.outcome_score_avg);
  var overallDelta = _characterSignalShadowDelta_(outcomePresent.overall_ok_rate, outcomeAbsent.overall_ok_rate);
  var dirDelta = _characterSignalShadowDelta_(outcomePresent.dir_ok_rate, outcomeAbsent.dir_ok_rate);
  var econDelta = _characterSignalShadowDelta_(econPresent, econAbsent);
  var effectSize = _characterSignalShadowWeightedEffect_({
    outcome_score_delta: outcomeScoreDelta,
    overall_ok_delta: overallDelta,
    dir_ok_delta: dirDelta,
    economic_value_accuracy_delta: econDelta
  });
  var result = _characterSignalShadowClassify_(effectSize, {
    outcome_score_delta: outcomeScoreDelta,
    overall_ok_delta: overallDelta,
    dir_ok_delta: dirDelta,
    economic_value_accuracy_delta: econDelta
  }, sampleDepthWarning);
  var note = _characterSignalShadowFamilyInterpretationNote_(candidate, family, result, sampleDepthWarning, outcomePresent, outcomeAbsent, econPresent, econAbsent);
  return {
    generated_ts: generatedTs,
    provider: candidate.provider,
    trait: candidate.trait,
    outcome_family: family,
    signal_candidate_id: candidate.signal_candidate_id,
    signal_family: candidate.signal_family,
    trait_domain: candidate.trait_domain,
    row_count_present: presentCount,
    row_count_absent: absentCount,
    outcome_score_present_avg: outcomePresent.outcome_score_avg == null ? '' : outcomePresent.outcome_score_avg,
    outcome_score_absent_avg: outcomeAbsent.outcome_score_avg == null ? '' : outcomeAbsent.outcome_score_avg,
    outcome_score_delta: outcomeScoreDelta == null ? '' : outcomeScoreDelta,
    overall_ok_present_rate: outcomePresent.overall_ok_rate == null ? '' : outcomePresent.overall_ok_rate,
    overall_ok_absent_rate: outcomeAbsent.overall_ok_rate == null ? '' : outcomeAbsent.overall_ok_rate,
    overall_ok_delta: overallDelta == null ? '' : overallDelta,
    dir_ok_present_rate: outcomePresent.dir_ok_rate == null ? '' : outcomePresent.dir_ok_rate,
    dir_ok_absent_rate: outcomeAbsent.dir_ok_rate == null ? '' : outcomeAbsent.dir_ok_rate,
    dir_ok_delta: dirDelta == null ? '' : dirDelta,
    economic_value_accuracy_present_rate: econPresent == null ? '' : econPresent,
    economic_value_accuracy_absent_rate: econAbsent == null ? '' : econAbsent,
    economic_value_accuracy_delta: econDelta == null ? '' : econDelta,
    sample_depth_warning: sampleDepthWarning,
    family_shadow_result: result,
    family_interpretation_note: note,
    candidate_status: candidate.candidate_status,
    recommended_future_use: candidate.recommended_future_use,
    shadow_effect_size: effectSize
  };
}

function _characterSignalShadowStatsToMetrics_(stats) {
  stats = stats || _characterSignalShadowBlankStats_();
  var n = Number(stats.row_count || 0);
  return {
    row_count: n,
    outcome_score_avg: stats.outcome_score_count ? _round4_(stats.outcome_score_sum / stats.outcome_score_count) : null,
    overall_ok_rate: n ? _round4_(stats.overall_ok_count / n) : null,
    dir_ok_rate: n ? _round4_(stats.dir_ok_count / n) : null,
    strength_ok_rate: n ? _round4_(stats.strength_ok_count / n) : null,
    sustain_ok_rate: n ? _round4_(stats.sustain_ok_count / n) : null
  };
}

function _characterSignalShadowEconomicRate_(stats) {
  stats = stats || _characterSignalShadowBlankStats_();
  var total = Number(stats.econ_value_ok_total || 0);
  var ok = Number(stats.econ_value_ok_count || 0);
  if (!(total > 0)) return null;
  return _round4_(ok / total);
}

function _characterSignalShadowWeightedEffect_(deltas) {
  var weights = {
    outcome_score_delta: 3,
    overall_ok_delta: 2,
    dir_ok_delta: 1.5,
    strength_ok_delta: 1,
    sustain_ok_delta: 1,
    economic_value_accuracy_delta: 2
  };
  var sum = 0;
  var weightSum = 0;
  Object.keys(weights).forEach(function(key) {
    var delta = _characterSignalShadowDeltaNumber_(deltas[key]);
    if (delta == null) return;
    sum += delta * weights[key];
    weightSum += weights[key];
  });
  if (!(weightSum > 0)) return null;
  return _round4_(sum / weightSum);
}

function _characterSignalShadowClassify_(effectSize, deltas, sampleDepthWarning) {
  var names = Object.keys(deltas || {});
  var positive = 0;
  var negative = 0;
  var available = 0;
  for (var i = 0; i < names.length; i++) {
    var delta = _characterSignalShadowDeltaNumber_(deltas[names[i]]);
    if (delta == null) continue;
    available += 1;
    if (delta >= 0.05) positive += 1;
    else if (delta <= -0.05) negative += 1;
  }
  if (!available) return 'shadow_inconclusive';
  if (sampleDepthWarning && String(sampleDepthWarning).indexOf('thin_total_sample') >= 0) return 'shadow_inconclusive';
  if (positive > 0 && negative > 0) return 'shadow_mixed';
  var e = _characterSignalShadowDeltaNumber_(effectSize);
  if (e == null || Math.abs(e) < 0.05) {
    if (!positive && !negative) return 'shadow_neutral';
    if (positive && !negative) return 'shadow_positive';
    if (negative && !positive) return 'shadow_negative';
    return 'shadow_mixed';
  }
  if (e >= 0.05) return 'shadow_positive';
  if (e <= -0.05) return 'shadow_negative';
  return 'shadow_neutral';
}

function _characterSignalShadowConfidence_(presentCount, absentCount, totalCount, result, candidate) {
  var status = String(candidate.candidate_status || '').trim();
  var thin = String(_characterSignalShadowSampleDepthWarning_(presentCount, absentCount, totalCount, null, null) || '');
  if (result === 'shadow_inconclusive') return 'low';
  if (thin.indexOf('thin_total_sample') >= 0 || thin.indexOf('thin_present_sample') >= 0 || thin.indexOf('thin_absent_sample') >= 0) return 'low';
  if (presentCount >= 40 && absentCount >= 40 && (result === 'shadow_positive' || result === 'shadow_negative' || result === 'shadow_neutral')) return 'high';
  if (status === 'strong_candidate' && presentCount >= 20 && absentCount >= 20) return 'medium';
  return 'low';
}

function _characterSignalShadowInterpretationNote_(candidate, presentMetrics, absentMetrics, econPresent, econAbsent, result, effectSize, sampleDepthWarning) {
  var parts = [
    'functional_layer=Character Signal Shadow Test',
    'provider=' + String(candidate.provider || ''),
    'trait=' + String(candidate.trait || ''),
    'recurrence=' + String(candidate.recurrence_score == null ? '' : candidate.recurrence_score),
    'falsification=' + String(candidate.falsification_status || ''),
    'drift=' + String(candidate.drift_status || ''),
    'result=' + String(result || ''),
    'effect=' + String(effectSize == null ? '' : effectSize)
  ];
  if (sampleDepthWarning) parts.push('sample_depth_warning=' + sampleDepthWarning);
  if (presentMetrics.row_count !== undefined && absentMetrics.row_count !== undefined) {
    parts.push(
      'present_rows=' + presentMetrics.row_count +
      '|absent_rows=' + absentMetrics.row_count +
      '|present_outcome=' + (presentMetrics.outcome_score_avg == null ? 'n/a' : presentMetrics.outcome_score_avg) +
      '|absent_outcome=' + (absentMetrics.outcome_score_avg == null ? 'n/a' : absentMetrics.outcome_score_avg)
    );
  }
  if (econPresent != null || econAbsent != null) {
    parts.push('econ_present=' + (econPresent == null ? 'n/a' : econPresent) + '|econ_absent=' + (econAbsent == null ? 'n/a' : econAbsent));
  }
  return parts.join('; ');
}

function _characterSignalShadowFamilyInterpretationNote_(candidate, family, result, sampleDepthWarning, presentMetrics, absentMetrics, econPresent, econAbsent) {
  var parts = [
    'functional_layer=Character Signal Shadow Test',
    'provider=' + String(candidate.provider || ''),
    'trait=' + String(candidate.trait || ''),
    'family=' + String(family || ''),
    'result=' + String(result || '')
  ];
  if (sampleDepthWarning) parts.push('sample_depth_warning=' + sampleDepthWarning);
  if (presentMetrics.row_count !== undefined && absentMetrics.row_count !== undefined) {
    parts.push('present_rows=' + presentMetrics.row_count + '|absent_rows=' + absentMetrics.row_count);
  }
  if (econPresent != null || econAbsent != null) {
    parts.push('econ_present=' + (econPresent == null ? 'n/a' : econPresent) + '|econ_absent=' + (econAbsent == null ? 'n/a' : econAbsent));
  }
  return parts.join('; ');
}

function _characterSignalShadowReadiness_(row) {
  var shadowResult = String(row.shadow_result || '').trim();
  var effect = _characterSignalShadowDeltaNumber_(row.shadow_effect_size);
  var recurrence = String(row.recurrence_score || '').trim();
  var recurrenceScore = _characterSignalShadowDeltaNumber_(row.recurrence_score);
  var drift = String(row.drift_status || '').trim().toLowerCase();
  var falsification = String(row.falsification_status || '').trim().toLowerCase();
  var sampleDepthWarning = String(row.sample_depth_warning || '').trim();
  var candidateStatus = String(row.candidate_status || '').trim();
  var thin = sampleDepthWarning.indexOf('thin') >= 0;
  var driftOk = drift === 'stable' || drift === 'mild_drift' || drift === '';
  var recurrenceOk = recurrenceScore != null ? recurrenceScore >= 0.75 : /strong|moderate/.test(String(row.recurrence_evidence || recurrence || '').toLowerCase());
  var falsificationOk = falsification && falsification.indexOf('fail') < 0;

  var reliability = 'monitor_more_data';
  var calibration = 'monitor_more_data';
  var nextAction = 'monitor_more_data';

  if (candidateStatus !== 'strong_candidate') {
    reliability = 'reject_for_now';
    calibration = 'reject_for_now';
    nextAction = 'reject_for_now';
  } else if (shadowResult === 'shadow_positive' && !thin && driftOk && recurrenceOk && falsificationOk) {
    reliability = 'ready_for_reliability_monitoring';
    if (effect != null && effect >= 0.1 && recurrenceScore != null && recurrenceScore >= 0.9) {
      calibration = 'ready_for_extended_shadow_calibration';
      nextAction = 'consider_extended_shadow_calibration';
    } else {
      calibration = 'monitor_more_data';
      nextAction = 'continue_shadow_monitoring';
    }
  } else if ((shadowResult === 'shadow_positive' || shadowResult === 'shadow_neutral') && driftOk && recurrenceOk) {
    reliability = 'ready_for_reliability_monitoring';
    calibration = 'monitor_more_data';
    nextAction = 'continue_shadow_monitoring';
  } else if (shadowResult === 'shadow_mixed') {
    reliability = driftOk ? 'monitor_more_data' : 'reject_for_now';
    calibration = 'monitor_more_data';
    nextAction = driftOk ? 'monitor_more_data' : 'reject_for_now';
  } else if (shadowResult === 'shadow_negative') {
    reliability = 'reject_for_now';
    calibration = 'reject_for_now';
    nextAction = 'reject_for_now';
  } else {
    reliability = 'inconclusive';
    calibration = 'inconclusive';
    nextAction = 'monitor_more_data';
  }

  return {
    reliability_signal_readiness: reliability,
    calibration_shadow_readiness: calibration,
    next_action: nextAction,
    final_note: [
      'shadow=' + shadowResult,
      'effect=' + (effect == null ? '' : effect),
      'recurrence=' + recurrence,
      'drift=' + drift,
      'falsification=' + falsification,
      'sample_depth_warning=' + sampleDepthWarning
    ].join('; ')
  };
}

function _characterSignalShadowEvidenceText_(label, a, b, c) {
  return [
    String(label || ''),
    String(a == null ? '' : a),
    String(b == null ? '' : b),
    String(c == null ? '' : c)
  ].filter(function(v) { return String(v || '').trim(); }).join('|');
}

function _characterSignalShadowSampleDepthWarning_(presentCount, absentCount, totalCount) {
  var notes = [];
  if (Number(presentCount || 0) < 20) notes.push('thin_present_sample');
  if (Number(absentCount || 0) < 20) notes.push('thin_absent_sample');
  if (Number(totalCount || 0) < 50) notes.push('thin_total_sample');
  return _uniqueStrings_(notes).join('|');
}

function _characterSignalShadowDelta_(presentValue, absentValue) {
  var a = _characterSignalShadowDeltaNumber_(presentValue);
  var b = _characterSignalShadowDeltaNumber_(absentValue);
  if (a == null || b == null) return null;
  return _round4_(a - b);
}

function _characterSignalShadowDeltaNumber_(value) {
  var n = _characterResidualNum_(value);
  return n == null ? null : n;
}

function _characterSignalShadowSummaryScore_(row) {
  var effect = _characterSignalShadowDeltaNumber_(row.shadow_effect_size);
  if (effect != null) return effect;
  var score = _characterSignalShadowDeltaNumber_(row.outcome_score_delta);
  return score == null ? 0 : score;
}

function _characterSignalShadowSummaryNote_(group, rows) {
  var parts = [];
  parts.push('dominant_result=' + _characterSignalShadowDominantResult_(group));
  parts.push('candidates=' + group.candidates_tested);
  parts.push('positive=' + group.positive.length);
  parts.push('negative=' + group.negative.length);
  parts.push('neutral=' + group.neutral.length);
  parts.push('mixed=' + group.mixed.length);
  parts.push('inconclusive=' + group.inconclusive.length);
  if (group.candidate_status === 'strong_candidate') {
    parts.push('shadow_calibration_candidates=' + group.positive.length);
  }
  return parts.join('; ');
}

function _characterSignalShadowDominantResult_(group) {
  if (!group) return 'shadow_inconclusive';
  var buckets = [
    ['shadow_positive', group.positive.length],
    ['shadow_negative', group.negative.length],
    ['shadow_neutral', group.neutral.length],
    ['shadow_mixed', group.mixed.length],
    ['shadow_inconclusive', group.inconclusive.length]
  ];
  buckets.sort(function(a, b) {
    if (a[1] !== b[1]) return b[1] - a[1];
    return a[0].localeCompare(b[0]);
  });
  return buckets[0][0];
}

function _characterSignalShadowTraitDomain_(trait) {
  var domains = _characterSignalCandidateTraitDomains_(trait);
  return _characterSignalCandidatePrimaryTraitDomain_(domains);
}

function _characterSignalShadowCandidateRankBucket_(candidateStatus) {
  var s = String(candidateStatus || '').trim().toLowerCase();
  if (s === 'strong_candidate') return 0;
  if (s === 'medium_candidate') return 1;
  return 2;
}

function _characterSignalShadowGroupBy_(lookup, keyFn) {
  var grouped = {};
  Object.keys(lookup || {}).forEach(function(key) {
    var row = lookup[key];
    var gKey = keyFn(row || {}) || 'unknown';
    if (!grouped[gKey]) grouped[gKey] = [];
    grouped[gKey].push(row);
  });
  return grouped;
}
