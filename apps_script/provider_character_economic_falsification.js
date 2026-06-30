/*******************************************************
 * provider_character_economic_falsification.js
 * - Diagnostic-only Provider Character Economic Falsification v1
 * - Gatekeeper test for Character -> Economic Outcome candidates
 * - Uses Economic Value Prediction Layer only; no market reaction logic
 *******************************************************/

function menuBuildProviderCharacterEconomicFalsification_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterEconomicFalsification_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character economic falsification -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Falsification=' + (res.falsification_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0) +
      ' | Methodology=' + (res.methodology_rows_written || 0),
      'Provider Character Economic Falsification',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character economic falsification -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterEconomicFalsification_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _providerCharacterEconomicFalsificationLoadSources_(warnings);
  var candidateUniverse = _providerCharacterEconomicFalsificationBuildCandidateUniverse_(sources.linkBundle, warnings);
  if (!candidateUniverse.length) warnings.push('missing_candidate_universe');

  var cases = _providerCharacterEconomicFalsificationBuildEconomicCases_(sources.economicBundle, warnings);
  var residualLookup = _providerCharacterEconomicBuildResidualLookup_(sources.residualBundle, warnings);
  var providerCaseMap = _providerCharacterEconomicFalsificationBuildProviderCaseMap_(cases, residualLookup, warnings);

  var selectedCandidates = _providerCharacterEconomicFalsificationSelectCandidates_(candidateUniverse, providerCaseMap, residualLookup, warnings);
  var presenceMap = _providerCharacterEconomicFalsificationBuildPresenceMap_(selectedCandidates, providerCaseMap, residualLookup);

  var evaluatedRows = [];
  for (var i = 0; i < selectedCandidates.length; i++) {
    evaluatedRows.push(
      _providerCharacterEconomicFalsificationEvaluateCandidate_(
        generatedTs,
        selectedCandidates[i],
        providerCaseMap,
        presenceMap,
        residualLookup,
        warnings
      )
    );
  }

  var summaryRows = _providerCharacterEconomicFalsificationBuildSummaryRows_(generatedTs, evaluatedRows);
  var methodologyRows = _providerCharacterEconomicFalsificationBuildMethodologyRows_(generatedTs, sources, warnings);

  var falsificationSheet = getDiagnosticsSheet_('Character_Economic_Falsification', _providerCharacterEconomicFalsificationHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Character_Economic_Falsification_Summary', _providerCharacterEconomicFalsificationSummaryHeaders_(), warnings);
  var methodologySheet = getDiagnosticsSheet_('Character_Economic_Falsification_Methodology', _providerCharacterEconomicFalsificationMethodologyHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    falsificationSheet.sheet,
    falsificationSheet.headers,
    _characterResidualObjectsToRows_(evaluatedRows, falsificationSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    summarySheet.sheet,
    summarySheet.headers,
    _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    methodologySheet.sheet,
    methodologySheet.headers,
    _characterResidualObjectsToRows_(methodologyRows, methodologySheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    falsification_sheet: falsificationSheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    methodology_sheet: methodologySheet.sheet.getName(),
    falsification_rows_written: evaluatedRows.length,
    summary_rows_written: summaryRows.length,
    methodology_rows_written: methodologyRows.length,
    candidates_tested: selectedCandidates.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function buildProviderCharacterEconomicFalsification() {
  return buildProviderCharacterEconomicFalsification_();
}

function _providerCharacterEconomicFalsificationHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'candidate_type',
    'original_effect',
    'original_sample_size',
    'provider_control_result',
    'family_control_result',
    'strongest_overlap_trait',
    'overlap_rate',
    'overlap_classification',
    'leave_one_out_result',
    'final_result',
    'credibility',
    'recommended_next_step',
    'interpretation',
    'notes'
  ];
}

function _providerCharacterEconomicFalsificationSummaryHeaders_() {
  return [
    'generated_ts',
    'provider',
    'candidates_tested',
    'survivors',
    'partial_survivors',
    'overlap_artifacts',
    'family_specific',
    'failed',
    'strongest_survivors',
    'strongest_negative_survivors',
    'strongest_overlap_clusters',
    'provider_interpretation',
    'recommended_next_step',
    'notes'
  ];
}

function _providerCharacterEconomicFalsificationMethodologyHeaders_() {
  return [
    'generated_ts',
    'experiment',
    'branch',
    'purpose',
    'allowed_outcome_layer',
    'forbidden_outcome_layer',
    'provider_calls',
    'prediction_runs',
    'production_changes',
    'candidate_selection_rule',
    'provider_control_rule',
    'family_control_rule',
    'overlap_rule',
    'leave_one_out_rule',
    'source_sheets_used',
    'notes'
  ];
}

function _providerCharacterEconomicFalsificationLoadSources_(warnings) {
  return {
    linkBundle: _characterResidualReadSheetBundle_('Character_Economic_Outcome_Link', warnings, false),
    summaryBundle: _characterResidualReadSheetBundle_('Character_Economic_Outcome_Summary', warnings, false),
    familyBundle: _characterResidualReadSheetBundle_('Character_Economic_Outcome_Family_Link', warnings, false),
    economicBundle: _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false),
    providerFamilyEconomicBundle: _characterResidualReadSheetBundle_('Provider_Family_Economic_Accuracy', warnings, false),
    residualBundle: _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false)
  };
}

function _providerCharacterEconomicFalsificationBuildCandidateUniverse_(linkBundle, warnings) {
  var rows = _providerCharacterEconomicFalsificationBundleRowsToObjects_(linkBundle);
  var candidates = [];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var trait = String(row.trait || '').trim();
    if (!provider || !trait) continue;
    var result = String(row.economic_link_result || '').trim();
    if (!result || result === 'insufficient_sample') continue;

    var dirDelta = _numOrNull_(row.economic_dir_ok_delta);
    var absErrorDelta = _numOrNull_(row.avg_abs_error_delta);
    var score = _providerCharacterEconomicFalsificationSelectionScore_(dirDelta, absErrorDelta, row.row_count_trait_present, row.row_count_trait_absent, result);
    var candidateType = _providerCharacterEconomicFalsificationCandidateType_(dirDelta, absErrorDelta, result);
    var originalSampleSize = Number(row.row_count_trait_present || 0) + Number(row.row_count_trait_absent || 0);

    candidates.push({
      provider: provider,
      trait: trait,
      candidate_type: candidateType,
      original_dir_delta: dirDelta,
      original_abs_error_delta: absErrorDelta,
      original_sample_size: originalSampleSize,
      original_result: result,
      original_effect_score: score,
      link_row: row
    });
  }

  candidates = _providerCharacterEconomicFalsificationSelectByProvider_(candidates, 10);

  if (!candidates.length) warnings.push('candidate_universe_empty');
  return candidates;
}

function _providerCharacterEconomicFalsificationSelectCandidates_(candidateUniverse, providerCaseMap, residualLookup, warnings) {
  if (!candidateUniverse || !candidateUniverse.length) return [];
  return candidateUniverse.slice();
}

function _providerCharacterEconomicFalsificationCandidateType_(dirDelta, absErrorDelta, result) {
  var dir = _numOrNull_(dirDelta);
  var err = _numOrNull_(absErrorDelta);
  var positiveSupport = 0;
  var negativeSupport = 0;

  if (dir != null) {
    if (dir > 0) positiveSupport += 1;
    else if (dir < 0) negativeSupport += 1;
  }
  if (err != null) {
    if (err < 0) positiveSupport += 1;
    else if (err > 0) negativeSupport += 1;
  }

  var lower = String(result || '').toLowerCase();
  if (lower.indexOf('positive') >= 0 && positiveSupport >= negativeSupport) return 'positive_candidate';
  if (lower.indexOf('negative') >= 0 && negativeSupport >= positiveSupport) return 'negative_candidate';
  if (positiveSupport >= 2 && positiveSupport > negativeSupport) return 'positive_candidate';
  if (negativeSupport >= 2 && negativeSupport > positiveSupport) return 'negative_candidate';
  return 'mixed_candidate';
}

function _providerCharacterEconomicFalsificationSelectionScore_(dirDelta, absErrorDelta, presentRows, absentRows, result) {
  var dir = Math.abs(_numOrNull_(dirDelta) || 0);
  var err = Math.abs(_numOrNull_(absErrorDelta) || 0);
  var depth = Math.max(0, Number(presentRows || 0) + Number(absentRows || 0));
  var resultBonus = String(result || '').toLowerCase().indexOf('positive') >= 0 || String(result || '').toLowerCase().indexOf('negative') >= 0 ? 1 : 0;
  return (dir * 1000) + (err * 100) + Math.min(depth, 10000) + resultBonus;
}

function _providerCharacterEconomicFalsificationSelectByProvider_(candidates, perProviderCap) {
  var grouped = {};
  for (var i = 0; i < (candidates || []).length; i++) {
    var c = candidates[i];
    if (!grouped[c.provider]) grouped[c.provider] = [];
    grouped[c.provider].push(c);
  }

  var selected = [];
  Object.keys(grouped).sort().forEach(function(provider) {
    var list = grouped[provider].slice();
    var positives = list.filter(function(c) { return c.candidate_type === 'positive_candidate'; });
    var negatives = list.filter(function(c) { return c.candidate_type === 'negative_candidate'; });
    var mixed = list.filter(function(c) { return c.candidate_type === 'mixed_candidate'; });

    positives.sort(function(a, b) {
      if ((a.original_dir_delta || 0) !== (b.original_dir_delta || 0)) return (b.original_dir_delta || 0) - (a.original_dir_delta || 0);
      if (a.original_sample_size !== b.original_sample_size) return b.original_sample_size - a.original_sample_size;
      if ((a.original_abs_error_delta || 0) !== (b.original_abs_error_delta || 0)) return (a.original_abs_error_delta || 0) - (b.original_abs_error_delta || 0);
      return a.trait.localeCompare(b.trait);
    });
    negatives.sort(function(a, b) {
      if ((a.original_dir_delta || 0) !== (b.original_dir_delta || 0)) return (a.original_dir_delta || 0) - (b.original_dir_delta || 0);
      if (a.original_sample_size !== b.original_sample_size) return b.original_sample_size - a.original_sample_size;
      if ((a.original_abs_error_delta || 0) !== (b.original_abs_error_delta || 0)) return (b.original_abs_error_delta || 0) - (a.original_abs_error_delta || 0);
      return a.trait.localeCompare(b.trait);
    });
    mixed.sort(function(a, b) {
      if (a.original_sample_size !== b.original_sample_size) return b.original_sample_size - a.original_sample_size;
      if ((a.original_effect_score || 0) !== (b.original_effect_score || 0)) return (b.original_effect_score || 0) - (a.original_effect_score || 0);
      return a.trait.localeCompare(b.trait);
    });

    var chosen = [];
    function addFrom(list, limit) {
      for (var i = 0; i < list.length && chosen.length < perProviderCap && i < limit; i++) {
        chosen.push(list[i]);
      }
    }

    addFrom(positives, 4);
    addFrom(negatives, 4);
    addFrom(mixed, 2);

    if (chosen.length < 5) {
      var rest = positives.concat(negatives).concat(mixed).filter(function(item) {
        return chosen.indexOf(item) < 0;
      });
      rest.sort(function(a, b) {
        if (a.original_sample_size !== b.original_sample_size) return b.original_sample_size - a.original_sample_size;
        if ((a.original_effect_score || 0) !== (b.original_effect_score || 0)) return (b.original_effect_score || 0) - (a.original_effect_score || 0);
        return a.trait.localeCompare(b.trait);
      });
      for (var j = 0; j < rest.length && chosen.length < perProviderCap; j++) {
        chosen.push(rest[j]);
      }
    }

    if (chosen.length > perProviderCap) chosen = chosen.slice(0, perProviderCap);
    selected = selected.concat(chosen);
  });

  selected.sort(function(a, b) {
    if (a.provider !== b.provider) return a.provider.localeCompare(b.provider);
    if (a.candidate_type !== b.candidate_type) return a.candidate_type.localeCompare(b.candidate_type);
    if ((a.original_effect_score || 0) !== (b.original_effect_score || 0)) return (b.original_effect_score || 0) - (a.original_effect_score || 0);
    return a.trait.localeCompare(b.trait);
  });

  return selected;
}

function _providerCharacterEconomicFalsificationBuildEconomicCases_(economicBundle, warnings) {
  var rows = _providerCharacterEconomicFalsificationBundleRowsToObjects_(economicBundle);
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (String(row.row_type || '').trim() !== 'case') continue;
    if (String(row.value_scored_flag || '').trim().toUpperCase() !== 'TRUE') continue;
    if (!String(row.ai_name || '').trim()) continue;
    if (!String(row.event_id || '').trim()) continue;
    out.push({
      generated_ts: String(row.generated_ts || '').trim(),
      provider: String(row.ai_name || '').trim(),
      event_id: String(row.event_id || '').trim(),
      batch_id: String(row.batch_id || '').trim(),
      type: String(row.type || '').trim(),
      family: String(row.family || '').trim() || 'other',
      release_ts: String(row.release_ts || '').trim(),
      indicator_name: String(row.indicator_name || '').trim(),
      country: String(row.country || '').trim(),
      consensus_value: _numOrNull_(row.consensus_value),
      prev_revision: _numOrNull_(row.prev_revision),
      ai_forecast_value: _numOrNull_(row.ai_forecast_value),
      released_value: _numOrNull_(row.released_value),
      value_dir_ok: String(row.value_dir_ok || '').trim(),
      value_error_abs: _numOrNull_(row.value_error_abs),
      value_error_pct: _numOrNull_(row.value_error_pct),
      value_scored_flag: String(row.value_scored_flag || '').trim(),
      qualitative_only: String(row.qualitative_only || '').trim(),
      comparison_label: String(row.comparison_label || '').trim(),
      decision_support_note: String(row.decision_support_note || '').trim(),
      residual_key: String(row.event_id || '').trim() + '|' + String(row.ai_name || '').trim()
    });
  }
  if (!out.length && warnings) warnings.push('missing_source_rows:Economic_Value_Accuracy');
  return out;
}

function _providerCharacterEconomicFalsificationBuildProviderCaseMap_(cases, residualLookup, warnings) {
  var map = {};
  for (var i = 0; i < (cases || []).length; i++) {
    var row = cases[i];
    var residual = residualLookup[row.residual_key];
    if (!residual) continue;
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!map[provider]) map[provider] = [];
    map[provider].push({
      case_row: row,
      residual: residual
    });
  }
  return map;
}

function _providerCharacterEconomicFalsificationBuildPresenceMap_(selectedCandidates, providerCaseMap, residualLookup) {
  var presence = {};
  for (var i = 0; i < (selectedCandidates || []).length; i++) {
    var c = selectedCandidates[i];
    var providerCases = providerCaseMap[c.provider] || [];
    var key = c.provider + '|' + c.trait;
    presence[key] = {
      event_ids: {},
      rows: [],
      provider: c.provider,
      trait: c.trait,
      candidate_type: c.candidate_type
    };
    for (var j = 0; j < providerCases.length; j++) {
      var pair = providerCases[j];
      if (_providerCharacterEconomicTraitMatchesResidual_(c.trait, pair.residual)) {
        var eventId = String(pair.case_row.event_id || '').trim();
        if (!eventId) continue;
        presence[key].event_ids[eventId] = true;
        presence[key].rows.push(pair.case_row);
      }
    }
  }
  return presence;
}

function _providerCharacterEconomicFalsificationEvaluateCandidate_(generatedTs, candidate, providerCaseMap, presenceMap, residualLookup, warnings) {
  var provider = candidate.provider;
  var trait = candidate.trait;
  var expectedSign = _providerCharacterEconomicFalsificationExpectedSign_(candidate);
  var providerCases = providerCaseMap[provider] || [];
  var key = provider + '|' + trait;
  var presence = presenceMap[key] || { event_ids: {}, rows: [] };
  var presentRows = presence.rows.slice();
  var absentRows = [];
  for (var i = 0; i < providerCases.length; i++) {
    var row = providerCases[i].case_row;
    var residual = providerCases[i].residual;
    if (!residual) continue;
    if (_providerCharacterEconomicTraitMatchesResidual_(trait, residual)) continue;
    absentRows.push(row);
  }

  var originalMetrics = _providerCharacterEconomicFalsificationMetrics_(presentRows, absentRows);
  var providerControlResult = _providerCharacterEconomicFalsificationProviderControl_(presentRows, absentRows, originalMetrics, expectedSign);

  var familyControl = _providerCharacterEconomicFalsificationFamilyControl_(providerCases, trait, expectedSign);
  var overlapInfo = _providerCharacterEconomicFalsificationOverlap_(candidate, presenceMap, providerCaseMap);
  var looInfo = _providerCharacterEconomicFalsificationLeaveOneOut_(candidate, providerCases, overlapInfo, expectedSign);

  var finalResult = _providerCharacterEconomicFalsificationFinalResult_(providerControlResult, familyControl.result, overlapInfo.classification, looInfo.result, originalMetrics);
  var credibility = _providerCharacterEconomicFalsificationCredibility_(finalResult, originalMetrics, overlapInfo.classification);
  var nextStep = _providerCharacterEconomicFalsificationNextStep_(finalResult, credibility);

  return {
    generated_ts: generatedTs,
    provider: provider,
    trait: trait,
    candidate_type: candidate.candidate_type,
    original_effect: _providerCharacterEconomicFalsificationEffectText_(candidate, originalMetrics),
    original_sample_size: candidate.original_sample_size,
    provider_control_result: providerControlResult,
    family_control_result: familyControl.result,
    strongest_overlap_trait: overlapInfo.trait,
    overlap_rate: overlapInfo.overlap_rate == null ? '' : _round4_(overlapInfo.overlap_rate),
    overlap_classification: overlapInfo.classification,
    leave_one_out_result: looInfo.result,
    final_result: finalResult,
    credibility: credibility,
    recommended_next_step: nextStep,
    interpretation: _providerCharacterEconomicFalsificationInterpretation_(finalResult, providerControlResult, familyControl.result, overlapInfo.classification, looInfo.result),
    notes: _providerCharacterEconomicFalsificationNotes_(candidate, originalMetrics, providerControlResult, familyControl, overlapInfo, looInfo)
  };
}

function _providerCharacterEconomicFalsificationExpectedSign_(candidate) {
  if (candidate.candidate_type === 'positive_candidate') return 1;
  if (candidate.candidate_type === 'negative_candidate') return -1;
  var dir = _numOrNull_(candidate.original_dir_delta);
  if (dir == null || dir === 0) return 0;
  return dir > 0 ? 1 : -1;
}

function _providerCharacterEconomicFalsificationMetrics_(presentRows, absentRows) {
  function measure(rows) {
    var total = 0;
    var scored = 0;
    var dirOk = 0;
    var absSum = 0;
    var absCount = 0;
    var pctSum = 0;
    var pctCount = 0;
    for (var i = 0; i < (rows || []).length; i++) {
      var row = rows[i] || {};
      total += 1;
      var dir = String(row.value_dir_ok || '').trim().toUpperCase();
      if (dir === 'TRUE' || dir === 'FALSE') {
        scored += 1;
        if (dir === 'TRUE') dirOk += 1;
      }
      var absErr = _numOrNull_(row.value_error_abs);
      if (absErr != null) {
        absSum += absErr;
        absCount += 1;
      }
      var pctErr = _numOrNull_(row.value_error_pct);
      if (pctErr != null) {
        pctSum += pctErr;
        pctCount += 1;
      }
    }
    return {
      row_count: total,
      value_dir_ok_rate: scored ? _round4_(dirOk / scored) : null,
      avg_value_error_abs: absCount ? _round4_(absSum / absCount) : null,
      avg_value_error_pct: pctCount ? _round4_(pctSum / pctCount) : null
    };
  }
  return {
    present: measure(presentRows),
    absent: measure(absentRows)
  };
}

function _providerCharacterEconomicFalsificationProviderControl_(presentRows, absentRows, metrics, expectedSign) {
  if ((presentRows || []).length < 10 || (absentRows || []).length < 20) {
    return 'insufficient_provider_control_sample';
  }
  if (!expectedSign) return 'insufficient_provider_control_sample';

  var support = _providerCharacterEconomicFalsificationSupportCount_(
    metrics.present.value_dir_ok_rate,
    metrics.absent.value_dir_ok_rate,
    metrics.present.avg_value_error_abs,
    metrics.absent.avg_value_error_abs,
    metrics.present.avg_value_error_pct,
    metrics.absent.avg_value_error_pct,
    expectedSign
  );
  var effect = _providerCharacterEconomicFalsificationSignedEffect_(metrics.present, metrics.absent, expectedSign);
  if (support >= 3 && Math.abs(effect) >= 0.05) return 'survives_provider_control';
  if (support >= 2) return 'weakens_provider_control';
  return 'fails_provider_control';
}

function _providerCharacterEconomicFalsificationFamilyControl_(providerCases, trait, expectedSign) {
  var byFamily = {};
  var totalPresent = 0;
  for (var i = 0; i < (providerCases || []).length; i++) {
    var pair = providerCases[i];
    var row = pair.case_row;
    var residual = pair.residual;
    if (!residual) continue;
    var family = String(row.family || 'other').trim() || 'other';
    if (!byFamily[family]) {
      byFamily[family] = { present: [], absent: [] };
    }
    if (_providerCharacterEconomicTraitMatchesResidual_(trait, residual)) {
      byFamily[family].present.push(row);
      totalPresent += 1;
    } else {
      byFamily[family].absent.push(row);
    }
  }

  var families = Object.keys(byFamily);
  if (totalPresent < 20 || families.length < 2) {
    return {
      result: 'insufficient_family_control_sample',
      top_family_share: families.length ? _providerCharacterEconomicFalsificationTopFamilyShare_(byFamily, totalPresent) : 0,
      usable_family_count: 0,
      notes: _providerCharacterEconomicFalsificationFamilyNotes_(byFamily, expectedSign)
    };
  }

  var usable = [];
  var alignedFamilies = 0;
  var signSupport = 0;
  var weighted = 0;
  var weightedCount = 0;
  for (var f = 0; f < families.length; f++) {
    var familyName = families[f];
    var group = byFamily[familyName];
    if (group.present.length < 3 || group.absent.length < 3) continue;
    usable.push(familyName);
    var m = _providerCharacterEconomicFalsificationMetrics_(group.present, group.absent);
    var signed = _providerCharacterEconomicFalsificationSignedEffect_(m.present, m.absent, expectedSign);
    weighted += signed * (group.present.length + group.absent.length);
    weightedCount += (group.present.length + group.absent.length);
    if (signed > 0) alignedFamilies += 1;
    if (signed > 0.01) signSupport += 1;
  }

  var topShare = _providerCharacterEconomicFalsificationTopFamilyShare_(byFamily, totalPresent);
  if (!usable.length) {
    return {
      result: 'insufficient_family_control_sample',
      top_family_share: topShare,
      usable_family_count: 0,
      notes: _providerCharacterEconomicFalsificationFamilyNotes_(byFamily, expectedSign)
    };
  }

  if (topShare >= 0.7 && usable.length <= 1) {
    return {
      result: 'family_specific_only',
      top_family_share: topShare,
      usable_family_count: usable.length,
      notes: _providerCharacterEconomicFalsificationFamilyNotes_(byFamily, expectedSign)
    };
  }

  var weightedEffect = weightedCount ? (weighted / weightedCount) : 0;
  if (signSupport >= 2 && weightedEffect > 0.02) {
    return {
      result: 'survives_family_control',
      top_family_share: topShare,
      usable_family_count: usable.length,
      notes: _providerCharacterEconomicFalsificationFamilyNotes_(byFamily, expectedSign)
    };
  }
  if (signSupport >= 1 || alignedFamilies >= 1 || weightedEffect > 0) {
    return {
      result: 'weakens_family_control',
      top_family_share: topShare,
      usable_family_count: usable.length,
      notes: _providerCharacterEconomicFalsificationFamilyNotes_(byFamily, expectedSign)
    };
  }
  return {
    result: 'fails_family_control',
    top_family_share: topShare,
    usable_family_count: usable.length,
    notes: _providerCharacterEconomicFalsificationFamilyNotes_(byFamily, expectedSign)
  };
}

function _providerCharacterEconomicFalsificationTopFamilyShare_(byFamily, totalPresent) {
  var top = 0;
  Object.keys(byFamily || {}).forEach(function(key) {
    top = Math.max(top, Number((byFamily[key] && byFamily[key].present || []).length || 0));
  });
  return totalPresent ? (top / totalPresent) : 0;
}

function _providerCharacterEconomicFalsificationFamilyNotes_(byFamily, expectedSign) {
  var parts = [];
  Object.keys(byFamily || {}).sort().slice(0, 4).forEach(function(name) {
    parts.push(name + '=' + (byFamily[name].present.length || 0) + '/' + (byFamily[name].absent.length || 0));
  });
  if (expectedSign > 0) parts.push('expected_positive');
  else if (expectedSign < 0) parts.push('expected_negative');
  else parts.push('expected_mixed');
  return parts.join('; ');
}

function _providerCharacterEconomicFalsificationOverlap_(candidate, presenceMap, providerCaseMap) {
  var provider = candidate.provider;
  var candidateKey = provider + '|' + candidate.trait;
  var candidatePresence = presenceMap[candidateKey] || { event_ids: {}, rows: [] };
  var candidateCount = Object.keys(candidatePresence.event_ids || {}).length;
  var best = {
    trait: '',
    overlap_rate: 0,
    shared_count: 0,
    classification: 'independent_candidate',
    effect_similarity: 0
  };

  var providerCases = providerCaseMap[provider] || [];
  var selectedTraits = Object.keys(presenceMap).filter(function(key) {
    return key.indexOf(provider + '|') === 0 && key !== candidateKey;
  });

  for (var i = 0; i < selectedTraits.length; i++) {
    var otherKey = selectedTraits[i];
    var otherPresence = presenceMap[otherKey];
    var otherCount = Object.keys(otherPresence.event_ids || {}).length;
    if (!candidateCount || !otherCount) continue;
    var shared = _providerCharacterEconomicFalsificationSharedCount_(candidatePresence.event_ids, otherPresence.event_ids);
    if (!shared) continue;
    var overlapRate = shared / candidateCount;
    var candidateEffect = _providerCharacterEconomicFalsificationEffectMagnitude_(candidate);
    var otherCandidate = _providerCharacterEconomicFalsificationCandidateFromKey_(otherKey, providerCases, presenceMap);
    var otherEffect = otherCandidate ? _providerCharacterEconomicFalsificationEffectMagnitude_(otherCandidate) : 0;
    var effectSimilarity = _providerCharacterEconomicFalsificationEffectSimilarity_(candidateEffect, otherEffect);
    var classification = _providerCharacterEconomicFalsificationOverlapClass_(overlapRate, effectSimilarity);
    if (overlapRate > best.overlap_rate || (overlapRate === best.overlap_rate && shared > best.shared_count)) {
      best = {
        trait: otherKey.split('|')[1] || '',
        overlap_rate: overlapRate,
        shared_count: shared,
        classification: classification,
        effect_similarity: effectSimilarity
      };
    }
  }

  return best;
}

function _providerCharacterEconomicFalsificationSharedCount_(a, b) {
  var shared = 0;
  Object.keys(a || {}).forEach(function(key) {
    if (b && b[key]) shared += 1;
  });
  return shared;
}

function _providerCharacterEconomicFalsificationOverlapClass_(overlapRate, effectSimilarity) {
  if (overlapRate >= 0.65 && effectSimilarity >= 0.5) return 'likely_duplicate_cluster';
  if (overlapRate >= 0.35) return 'strong_overlap';
  if (overlapRate >= 0.15) return 'moderate_overlap';
  return 'independent_candidate';
}

function _providerCharacterEconomicFalsificationCandidateFromKey_(key, providerCases, presenceMap) {
  var trait = String(key || '').split('|')[1] || '';
  if (!trait) return null;
  var candidate = {
    provider: String(key || '').split('|')[0] || '',
    trait: trait,
    candidate_type: 'mixed_candidate',
    original_dir_delta: 0,
    original_abs_error_delta: 0,
    original_sample_size: 0,
    original_result: '',
    original_effect_score: 0
  };
  var found = false;
  for (var i = 0; i < (providerCases || []).length; i++) {
    var row = providerCases[i].case_row;
    var residual = providerCases[i].residual;
    if (!residual) continue;
    if (_providerCharacterEconomicTraitMatchesResidual_(trait, residual)) {
      found = true;
      break;
    }
  }
  return found ? candidate : null;
}

function _providerCharacterEconomicFalsificationEffectMagnitude_(candidate) {
  var dir = Math.abs(_numOrNull_(candidate.original_dir_delta) || 0);
  var err = Math.abs(_numOrNull_(candidate.original_abs_error_delta) || 0);
  return dir + err;
}

function _providerCharacterEconomicFalsificationEffectSimilarity_(a, b) {
  var denom = Math.max(0.0001, a + b);
  var diff = Math.abs(a - b);
  var similarity = 1 - Math.min(1, diff / denom);
  return _round4_(similarity);
}

function _providerCharacterEconomicFalsificationLeaveOneOut_(candidate, providerCases, overlapInfo, expectedSign) {
  if (!overlapInfo || !overlapInfo.trait) {
    return { result: 'survives_leave_one_out', shared_count: 0, remaining_present: 0 };
  }

  var trait = candidate.trait;
  var overlapTrait = overlapInfo.trait;
  var shared = [];
  var candidateOnly = [];
  var absentOnly = [];
  for (var i = 0; i < (providerCases || []).length; i++) {
    var pair = providerCases[i];
    var row = pair.case_row;
    var residual = pair.residual;
    if (!residual) continue;
    var hasCandidate = _providerCharacterEconomicTraitMatchesResidual_(trait, residual);
    var hasOverlap = _providerCharacterEconomicTraitMatchesResidual_(overlapTrait, residual);
    if (hasCandidate && hasOverlap) {
      shared.push(row);
      continue;
    }
    if (hasCandidate) candidateOnly.push(row);
    else absentOnly.push(row);
  }

  if (shared.length === 0) {
    return { result: 'survives_leave_one_out', shared_count: 0, remaining_present: candidateOnly.length };
  }

  var metrics = _providerCharacterEconomicFalsificationMetrics_(candidateOnly, absentOnly);
  if ((candidateOnly.length < 10 || absentOnly.length < 20)) {
    return { result: 'insufficient_leave_one_out_sample', shared_count: shared.length, remaining_present: candidateOnly.length };
  }

  var signed = _providerCharacterEconomicFalsificationSignedEffect_(metrics.present, metrics.absent, expectedSign);
  var original = _providerCharacterEconomicFalsificationSignedEffect_(
    _providerCharacterEconomicFalsificationMetrics_(
      (providerCases || []).filter(function(pair) { return _providerCharacterEconomicTraitMatchesResidual_(trait, pair.residual); }).map(function(pair) { return pair.case_row; }),
      (providerCases || []).filter(function(pair) { return !_providerCharacterEconomicTraitMatchesResidual_(trait, pair.residual); }).map(function(pair) { return pair.case_row; })
    ).present,
    _providerCharacterEconomicFalsificationMetrics_(
      (providerCases || []).filter(function(pair) { return _providerCharacterEconomicTraitMatchesResidual_(trait, pair.residual); }).map(function(pair) { return pair.case_row; }),
      (providerCases || []).filter(function(pair) { return !_providerCharacterEconomicTraitMatchesResidual_(trait, pair.residual); }).map(function(pair) { return pair.case_row; })
    ).absent,
    expectedSign
  );

  if (signed <= 0) return { result: 'likely_overlap_artifact', shared_count: shared.length, remaining_present: candidateOnly.length };
  if (original > 0 && signed < original * 0.5) return { result: 'partial_overlap_dependency', shared_count: shared.length, remaining_present: candidateOnly.length };
  return { result: 'survives_leave_one_out', shared_count: shared.length, remaining_present: candidateOnly.length };
}

function _providerCharacterEconomicFalsificationSignedEffect_(presentMetrics, absentMetrics, expectedSign) {
  var dirDelta = _providerCharacterEconomicFalsificationDelta_(presentMetrics.value_dir_ok_rate, absentMetrics.value_dir_ok_rate);
  var errDelta = _providerCharacterEconomicFalsificationDelta_(presentMetrics.avg_value_error_abs, absentMetrics.avg_value_error_abs);
  var pctDelta = _providerCharacterEconomicFalsificationDelta_(presentMetrics.avg_value_error_pct, absentMetrics.avg_value_error_pct);
  if (!expectedSign) return 0;
  return (expectedSign * (dirDelta || 0)) + (expectedSign * (pctDelta || 0)) - (expectedSign * (errDelta || 0));
}

function _providerCharacterEconomicFalsificationSupportCount_(presentDir, absentDir, presentErr, absentErr, presentPct, absentPct, expectedSign) {
  var support = 0;
  var dirDelta = _providerCharacterEconomicFalsificationDelta_(presentDir, absentDir);
  var errDelta = _providerCharacterEconomicFalsificationDelta_(presentErr, absentErr);
  var pctDelta = _providerCharacterEconomicFalsificationDelta_(presentPct, absentPct);
  if (!expectedSign) return 0;
  if (expectedSign > 0) {
    if (dirDelta != null && dirDelta > 0) support += 1;
    if (errDelta != null && errDelta < 0) support += 1;
    if (pctDelta != null && pctDelta < 0) support += 1;
  } else {
    if (dirDelta != null && dirDelta < 0) support += 1;
    if (errDelta != null && errDelta > 0) support += 1;
    if (pctDelta != null && pctDelta > 0) support += 1;
  }
  return support;
}

function _providerCharacterEconomicFalsificationDelta_(a, b) {
  var av = _numOrNull_(a);
  var bv = _numOrNull_(b);
  if (av == null || bv == null) return null;
  return _round4_(av - bv);
}

function _providerCharacterEconomicFalsificationFinalResult_(providerControlResult, familyControlResult, overlapClassification, leaveOneOutResult, metrics) {
  var thin = (metrics.present.row_count < 10) || (metrics.absent.row_count < 20);
  if (thin && (providerControlResult.indexOf('insufficient') >= 0 || familyControlResult.indexOf('insufficient') >= 0)) {
    return 'thin_sample_artifact';
  }
  if (providerControlResult === 'insufficient_provider_control_sample' || familyControlResult === 'insufficient_family_control_sample' || leaveOneOutResult === 'insufficient_leave_one_out_sample') {
    return 'insufficient_evidence';
  }
  if (overlapClassification === 'likely_duplicate_cluster' || leaveOneOutResult === 'likely_overlap_artifact') {
    return 'overlap_artifact';
  }
  if (familyControlResult === 'family_specific_only') {
    return 'family_specific_only';
  }
  if (providerControlResult === 'fails_provider_control' || familyControlResult === 'fails_family_control') {
    return 'fails_falsification';
  }
  if (providerControlResult === 'survives_provider_control' && familyControlResult === 'survives_family_control' && leaveOneOutResult === 'survives_leave_one_out' && overlapClassification === 'independent_candidate') {
    return 'survives_falsification';
  }
  return 'partially_survives';
}

function _providerCharacterEconomicFalsificationCredibility_(finalResult, metrics, overlapClassification) {
  if (finalResult === 'survives_falsification' && metrics.present.row_count >= 20 && metrics.absent.row_count >= 20 && overlapClassification === 'independent_candidate') {
    return 'high';
  }
  if (finalResult === 'partially_survives' || finalResult === 'family_specific_only') return 'medium';
  if (finalResult === 'insufficient_evidence' || finalResult === 'thin_sample_artifact') return 'insufficient';
  return 'low';
}

function _providerCharacterEconomicFalsificationNextStep_(finalResult, credibility) {
  if (finalResult === 'survives_falsification') return 'proceed_to_economic_recurrence';
  if (finalResult === 'partially_survives' || finalResult === 'family_specific_only') return 'hold_for_review';
  if (finalResult === 'overlap_artifact') return 'merge_into_overlap_cluster';
  if (finalResult === 'thin_sample_artifact') return 'archive_as_artifact';
  if (finalResult === 'fails_falsification') return 'reject_candidate';
  return 'hold_for_review';
}

function _providerCharacterEconomicFalsificationInterpretation_(finalResult, providerControlResult, familyControlResult, overlapClassification, leaveOneOutResult) {
  return [
    'final=' + finalResult,
    'provider_control=' + providerControlResult,
    'family_control=' + familyControlResult,
    'overlap=' + overlapClassification,
    'leave_one_out=' + leaveOneOutResult
  ].join('; ');
}

function _providerCharacterEconomicFalsificationEffectText_(candidate, metrics) {
  var dir = _providerCharacterEconomicFalsificationDelta_(metrics.present.value_dir_ok_rate, metrics.absent.value_dir_ok_rate);
  var err = _providerCharacterEconomicFalsificationDelta_(metrics.present.avg_value_error_abs, metrics.absent.avg_value_error_abs);
  var pct = _providerCharacterEconomicFalsificationDelta_(metrics.present.avg_value_error_pct, metrics.absent.avg_value_error_pct);
  return [
    'dir_delta=' + (dir == null ? 'n/a' : _round4_(dir)),
    'abs_error_delta=' + (err == null ? 'n/a' : _round4_(err)),
    'pct_error_delta=' + (pct == null ? 'n/a' : _round4_(pct)),
    'link_result=' + String(candidate.original_result || ''),
    'score=' + _round4_(Number(candidate.original_effect_score || 0))
  ].join('; ');
}

function _providerCharacterEconomicFalsificationNotes_(candidate, metrics, providerControlResult, familyControl, overlapInfo, looInfo) {
  var parts = [
    'candidate=' + candidate.provider + '|' + candidate.trait,
    'candidate_type=' + candidate.candidate_type,
    'orig_dir_delta=' + (candidate.original_dir_delta == null ? 'n/a' : _round4_(candidate.original_dir_delta)),
    'orig_abs_error_delta=' + (candidate.original_abs_error_delta == null ? 'n/a' : _round4_(candidate.original_abs_error_delta)),
    'original_sample_size=' + candidate.original_sample_size,
    'provider_control=' + providerControlResult,
    'family_control=' + familyControl.result,
    'family_top_share=' + _round4_(familyControl.top_family_share || 0),
    'family_usable_count=' + familyControl.usable_family_count,
    'overlap_trait=' + (overlapInfo.trait || ''),
    'overlap_rate=' + (overlapInfo.overlap_rate == null ? 'n/a' : _round4_(overlapInfo.overlap_rate)),
    'overlap_shared_count=' + (overlapInfo.shared_count == null ? 0 : overlapInfo.shared_count),
    'leave_one_out=' + looInfo.result,
    'loo_shared_count=' + (looInfo.shared_count == null ? 0 : looInfo.shared_count),
    'present_n=' + metrics.present.row_count,
    'absent_n=' + metrics.absent.row_count
  ];
  return parts.join('; ');
}

function _providerCharacterEconomicFalsificationBuildSummaryRows_(generatedTs, evaluatedRows) {
  var byProvider = {};
  for (var i = 0; i < (evaluatedRows || []).length; i++) {
    var row = evaluatedRows[i];
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!byProvider[provider]) {
      byProvider[provider] = {
        provider: provider,
        rows: [],
        survivors: [],
        partial: [],
        overlapArtifacts: [],
        familySpecific: [],
        failed: [],
        negativeSurvivors: [],
        overlapClusters: {}
      };
    }
    var g = byProvider[provider];
    g.rows.push(row);
    var finalResult = String(row.final_result || '').trim();
    if (finalResult === 'survives_falsification') g.survivors.push(row);
    else if (finalResult === 'partially_survives') g.partial.push(row);
    else if (finalResult === 'overlap_artifact') g.overlapArtifacts.push(row);
    else if (finalResult === 'family_specific_only') g.familySpecific.push(row);
    else if (finalResult === 'fails_falsification') g.failed.push(row);
    if (String(row.candidate_type || '').trim() === 'negative_candidate' && (finalResult === 'survives_falsification' || finalResult === 'partially_survives')) {
      g.negativeSurvivors.push(row);
    }
    if (row.strongest_overlap_trait) {
      g.overlapClusters[row.strongest_overlap_trait] = (g.overlapClusters[row.strongest_overlap_trait] || 0) + 1;
    }
  }

  var rowsOut = [];
  Object.keys(byProvider).sort().forEach(function(provider) {
    var g = byProvider[provider];
    var interpretation;
    if (g.survivors.length >= 1 && g.failed.length === 0 && g.overlapArtifacts.length === 0) interpretation = 'credible_candidates_remain';
    else if (g.survivors.length === 0 && g.failed.length >= 1) interpretation = 'gatekeeper_rejected_most_candidates';
    else if (g.familySpecific.length >= 1 && g.survivors.length === 0) interpretation = 'family_specific_only';
    else interpretation = 'mixed_gatekeeper_result';

    rowsOut.push({
      generated_ts: generatedTs,
      provider: provider,
      candidates_tested: g.rows.length,
      survivors: g.survivors.length,
      partial_survivors: g.partial.length,
      overlap_artifacts: g.overlapArtifacts.length,
      family_specific: g.familySpecific.length,
      failed: g.failed.length,
      strongest_survivors: _providerCharacterEconomicFalsificationTopTraits_(g.survivors, 5),
      strongest_negative_survivors: _providerCharacterEconomicFalsificationTopTraits_(g.negativeSurvivors, 5),
      strongest_overlap_clusters: _providerCharacterEconomicFalsificationTopCounts_(g.overlapClusters, 5),
      provider_interpretation: interpretation,
      recommended_next_step: _providerCharacterEconomicFalsificationProviderNextStep_(g),
      notes: _providerCharacterEconomicFalsificationProviderNotes_(g)
    });
  });

  return rowsOut;
}

function _providerCharacterEconomicFalsificationTopTraits_(rows, limit) {
  var list = (rows || []).slice().sort(function(a, b) {
    var as = _numOrNull_(String(a.original_effect || '').match(/score=([\-0-9.]+)/) ? RegExp.$1 : '');
    var bs = _numOrNull_(String(b.original_effect || '').match(/score=([\-0-9.]+)/) ? RegExp.$1 : '');
    if ((bs || 0) !== (as || 0)) return (bs || 0) - (as || 0);
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  }).slice(0, limit || 5);
  return list.map(function(row) { return row.provider + '|' + row.trait; }).join(' | ');
}

function _providerCharacterEconomicFalsificationTopCounts_(map, limit) {
  var list = [];
  Object.keys(map || {}).forEach(function(key) {
    list.push({ key: key, count: Number(map[key] || 0) });
  });
  list.sort(function(a, b) {
    if (b.count !== a.count) return b.count - a.count;
    return a.key.localeCompare(b.key);
  });
  return list.slice(0, limit || 5).map(function(item) {
    return item.key + '(' + item.count + ')';
  }).join(' | ');
}

function _providerCharacterEconomicFalsificationProviderNextStep_(group) {
  if ((group.survivors || []).length >= 1) return 'proceed_to_economic_recurrence';
  if ((group.overlapArtifacts || []).length >= 1) return 'merge_into_overlap_cluster';
  if ((group.familySpecific || []).length >= 1) return 'hold_for_review';
  if ((group.failed || []).length >= 1) return 'reject_candidate';
  return 'hold_for_review';
}

function _providerCharacterEconomicFalsificationProviderNotes_(group) {
  return [
    'tested=' + group.rows.length,
    'survivors=' + group.survivors.length,
    'partial=' + group.partial.length,
    'overlap=' + group.overlapArtifacts.length,
    'family_specific=' + group.familySpecific.length,
    'failed=' + group.failed.length
  ].join('; ');
}

function _providerCharacterEconomicFalsificationBuildMethodologyRows_(generatedTs, sources, warnings) {
  var sourceSheets = [];
  if (sources.linkBundle) sourceSheets.push('Character_Economic_Outcome_Link');
  if (sources.summaryBundle) sourceSheets.push('Character_Economic_Outcome_Summary');
  if (sources.familyBundle) sourceSheets.push('Character_Economic_Outcome_Family_Link');
  if (sources.economicBundle) sourceSheets.push('Economic_Value_Accuracy');
  if (sources.providerFamilyEconomicBundle) sourceSheets.push('Provider_Family_Economic_Accuracy');
  if (sources.residualBundle) sourceSheets.push('Provider_Character_Residuals');

  return [{
    generated_ts: generatedTs,
    experiment: 'Provider Character Economic Falsification v1',
    branch: 'Provider Character Economic Validation Branch',
    purpose: 'Gatekeeper test before Economic Recurrence',
    allowed_outcome_layer: 'Economic Value Prediction Layer',
    forbidden_outcome_layer: 'Market Reaction Prediction Layer',
    provider_calls: 'FALSE',
    prediction_runs: 'FALSE',
    production_changes: 'FALSE',
    candidate_selection_rule: 'Select up to 10 candidates per provider from Character_Economic_Outcome_Link using strongest positive, strongest negative, and highest sample depth rows; positive and negative candidates are both required where available.',
    provider_control_rule: 'Compare trait-present versus trait-absent rows within the same provider using Economic Value Prediction Layer only.',
    family_control_rule: 'Compare trait-present versus trait-absent rows across economic families and flag family concentration or family-specific behavior.',
    overlap_rule: 'Inspect only the strongest overlapping trait among selected candidates for the same provider; no full trait matrix.',
    leave_one_out_rule: 'Remove rows where candidate and strongest overlap trait both appear, then recompute the economic effect.',
    source_sheets_used: _uniqueStrings_(sourceSheets).join('|'),
    notes: _uniqueStrings_((warnings || []).concat([
      'economic_value_only',
      'no_market_reaction',
      'no_provider_calls',
      'no_prediction_runs'
    ])).join('|')
  }];
}

function _providerCharacterEconomicFalsificationBundleRowsToObjects_(bundle) {
  var rows = (bundle && bundle.rows) || [];
  var headers = (bundle && bundle.headers) || [];
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var raw = rows[i] || [];
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = j < raw.length ? raw[j] : '';
    }
    out.push(obj);
  }
  return out;
}
