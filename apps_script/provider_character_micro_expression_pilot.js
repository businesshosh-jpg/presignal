/*******************************************************
 * provider_character_micro_expression_pilot.js
 * - Diagnostic-only Provider Character v2 — Micro-Expression Pilot v1
 * - Replay/extraction only: no provider calls, no prediction runs
 * - Uses existing stored provider text to build compact free-form
 *   micro-expressions and lightweight similarity clusters
 *******************************************************/

function menuBuildProviderCharacterMicroExpressionPilot_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterMicroExpressionPilot_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character micro-expression pilot -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Pilot=' + (res.pilot_rows_written || 0) +
      ' | Clusters=' + (res.cluster_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0),
      'Provider Character Micro-Expression Pilot',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character micro-expression pilot -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterMicroExpressionPilot_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _providerCharacterMicroExpressionLoadSources_(warnings);
  var economicCases = _providerCharacterMicroExpressionBuildEconomicCases_(sources.economicBundle, warnings);
  var residualRows = _providerCharacterMicroExpressionBuildResidualRows_(sources.residualBundle, warnings);
  var residualLookup = _providerCharacterMicroExpressionBuildResidualLookup_(residualRows);
  var caseLookup = _providerCharacterMicroExpressionBuildCaseLookup_(economicCases);
  var eventUniverse = _providerCharacterMicroExpressionBuildEventUniverse_(economicCases, warnings);
  var overlapTraits = _providerCharacterMicroExpressionLoadOverlapTraits_(sources.falsificationBundle, warnings);
  var sampledEvents = _providerCharacterMicroExpressionSelectSampleEvents_(eventUniverse, residualLookup, overlapTraits, warnings);

  var pilotRows = _providerCharacterMicroExpressionBuildPilotRows_(generatedTs, sampledEvents, caseLookup, residualLookup, warnings);
  var clusterRows = _providerCharacterMicroExpressionBuildClusterRows_(generatedTs, pilotRows, warnings);
  var summaryRows = _providerCharacterMicroExpressionBuildSummaryRows_(generatedTs, pilotRows, clusterRows, warnings);
  var methodologyRows = _providerCharacterMicroExpressionBuildMethodologyRows_(generatedTs, sources, sampledEvents.length, pilotRows.length, warnings);

  var pilotSheet = getDiagnosticsSheet_('Provider_Character_MicroExpression_Pilot', _providerCharacterMicroExpressionPilotHeaders_(), warnings);
  var clusterSheet = getDiagnosticsSheet_('Provider_Character_MicroExpression_Clusters', _providerCharacterMicroExpressionClusterHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Provider_Character_MicroExpression_Summary', _providerCharacterMicroExpressionSummaryHeaders_(), warnings);
  var methodologySheet = getDiagnosticsSheet_('Provider_Character_MicroExpression_Methodology', _providerCharacterMicroExpressionMethodologyHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    pilotSheet.sheet,
    pilotSheet.headers,
    _characterResidualObjectsToRows_(pilotRows, pilotSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    clusterSheet.sheet,
    clusterSheet.headers,
    _characterResidualObjectsToRows_(clusterRows, clusterSheet.headers)
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
    pilot_sheet: pilotSheet.sheet.getName(),
    cluster_sheet: clusterSheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    methodology_sheet: methodologySheet.sheet.getName(),
    pilot_rows_written: pilotRows.length,
    cluster_rows_written: clusterRows.length,
    summary_rows_written: summaryRows.length,
    methodology_rows_written: methodologyRows.length,
    sampled_events: sampledEvents.length,
    provider_event_rows: pilotRows.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function buildProviderCharacterMicroExpressionPilot() {
  return buildProviderCharacterMicroExpressionPilot_();
}

function _providerCharacterMicroExpressionPilotHeaders_() {
  return [
    'generated_ts',
    'event_id',
    'provider',
    'indicator_name',
    'release_ts',
    'outcome_family',
    'importance',
    'ai_forecast_value',
    'consensus_value',
    'released_value',
    'economic_dir_ok',
    'forecast_error_abs',
    'better_than_consensus',
    'primary_focus_phrase',
    'secondary_focus_phrase',
    'ignored_or_discounted_factor_phrase',
    'causal_path_phrase',
    'failure_condition_phrase',
    'confidence_basis_phrase',
    'uncertainty_phrase',
    'expression_summary_phrase',
    'attention_terms',
    'source_text_basis',
    'extraction_method',
    'token_cost_estimate',
    'notes'
  ];
}

function _providerCharacterMicroExpressionClusterHeaders_() {
  return [
    'generated_ts',
    'cluster_id',
    'provider',
    'cluster_phrase',
    'representative_terms',
    'representative_examples',
    'row_count',
    'event_count',
    'family_distribution',
    'avg_economic_dir_ok',
    'avg_forecast_error_abs',
    'better_than_consensus_rate',
    'provider_specificity_score',
    'economic_separation_hint',
    'notes'
  ];
}

function _providerCharacterMicroExpressionSummaryHeaders_() {
  return [
    'generated_ts',
    'provider',
    'sampled_events',
    'expression_rows',
    'unique_micro_expression_count',
    'cluster_count',
    'strongest_expression_clusters',
    'most_provider_specific_patterns',
    'early_positive_economic_hints',
    'early_negative_economic_hints',
    'avg_token_cost_estimate',
    'pilot_result',
    'recommended_next_step',
    'notes'
  ];
}

function _providerCharacterMicroExpressionMethodologyHeaders_() {
  return [
    'generated_ts',
    'experiment_name',
    'branch_name',
    'purpose',
    'sample_strategy',
    'provider_calls_made',
    'prediction_runs_made',
    'production_changes',
    'source_sheets_used',
    'extraction_method',
    'token_minimization_rule',
    'forbidden_behavior',
    'interpretation_rule',
    'notes'
  ];
}

function _providerCharacterMicroExpressionLoadSources_(warnings) {
  return {
    economicBundle: _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false),
    residualBundle: _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false),
    falsificationBundle: _characterResidualReadSheetBundle_('Character_Economic_Falsification', warnings, false),
    providerSummaryBundle: _characterResidualReadSheetBundle_('Provider_Character_Summary', warnings, false),
    providerFamilySummaryBundle: _characterResidualReadSheetBundle_('Provider_Character_Family_Summary', warnings, false)
  };
}

function _providerCharacterMicroExpressionBuildEconomicCases_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var keyed = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (String(row.row_type || '').trim() !== 'case') continue;
    if (String(row.value_scored_flag || '').trim().toUpperCase() !== 'TRUE') continue;
    if (String(row.type || '').trim().toLowerCase() === 'batch') continue;
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.ai_name || row.provider || '').trim();
    if (!eventId || !provider) continue;
    var key = eventId + '|' + provider;
    if (!keyed[key] || _providerCharacterMicroExpressionRowIsNewer_(row, keyed[key])) {
      keyed[key] = row;
    }
  }
  var out = [];
  Object.keys(keyed).sort().forEach(function(key) {
    var row = keyed[key] || {};
    out.push({
      generated_ts: String(row.generated_ts || '').trim(),
      row_type: 'case',
      event_id: String(row.event_id || '').trim(),
      batch_id: String(row.batch_id || '').trim(),
      type: String(row.type || '').trim(),
      provider: String(row.ai_name || row.provider || '').trim(),
      ai_model: String(row.ai_model || '').trim(),
      indicator_name: String(row.indicator_name || '').trim(),
      country: String(row.country || '').trim(),
      release_ts: String(row.release_ts || '').trim(),
      outcome_family: String(row.family || row.outcome_family || '').trim() || 'other',
      importance: String(row.importance || '').trim(),
      consensus_value: _numOrNull_(row.consensus_value),
      prev_revision: _numOrNull_(row.prev_revision),
      ai_forecast_value: _numOrNull_(row.ai_forecast_value),
      released_value: _numOrNull_(row.released_value),
      actual_surprise_dir: String(row.actual_surprise_dir || '').trim(),
      ai_value_dir: String(row.ai_value_dir || '').trim(),
      value_dir_ok: String(row.value_dir_ok || '').trim(),
      forecast_error_abs: _numOrNull_(row.value_error_abs),
      value_error_pct: _numOrNull_(row.value_error_pct),
      value_score_note: String(row.value_score_note || '').trim(),
      qualitative_only: String(row.qualitative_only || '').trim(),
      qualitative_result: String(row.qualitative_result || '').trim(),
      attention_primary_factor: String(row.attention_primary_factor || '').trim(),
      attention_factors: String(row.attention_factors || '').trim()
    });
  });
  if (!out.length && warnings) warnings.push('missing_source_rows:Economic_Value_Accuracy');
  return out;
}

function _providerCharacterMicroExpressionBuildResidualRows_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var keyed = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (!eventId || !provider) continue;
    if (String(row.type || '').trim().toLowerCase() === 'batch') continue;
    var key = eventId + '|' + provider;
    if (!keyed[key] || _providerCharacterMicroExpressionRowIsNewer_(row, keyed[key])) {
      keyed[key] = row;
    }
  }
  var out = [];
  Object.keys(keyed).sort().forEach(function(key) {
    var row = keyed[key] || {};
    out.push({
      generated_ts: String(row.generated_ts || '').trim(),
      event_id: String(row.event_id || '').trim(),
      batch_id: String(row.batch_id || '').trim(),
      type: String(row.type || '').trim(),
      indicator_name: String(row.indicator_name || '').trim(),
      country: String(row.country || '').trim(),
      release_ts: String(row.release_ts || '').trim(),
      outcome_family: String(row.outcome_family || '').trim(),
      provider: String(row.provider || '').trim(),
      ai_forecast_value: _numOrNull_(row.ai_forecast_value),
      qualitative_result: String(row.qualitative_result || '').trim(),
      actual_value: _numOrNull_(row.actual_value),
      baseline_version: String(row.baseline_version || '').trim(),
      baseline_value: _numOrNull_(row.baseline_value),
      baseline_direction_vs_consensus: String(row.baseline_direction_vs_consensus || '').trim(),
      baseline_confidence: String(row.baseline_confidence || '').trim(),
      value_delta_from_baseline: _numOrNull_(row.value_delta_from_baseline),
      abs_value_delta_from_baseline: _numOrNull_(row.abs_value_delta_from_baseline),
      direction_delta_from_baseline: String(row.direction_delta_from_baseline || '').trim(),
      emphasized_factors: String(row.emphasized_factors || '').trim(),
      ignored_factors: String(row.ignored_factors || '').trim(),
      risk_language: String(row.risk_language || '').trim(),
      uncertainty_pattern: String(row.uncertainty_pattern || '').trim(),
      confidence_delta_from_baseline: String(row.confidence_delta_from_baseline || '').trim(),
      inferred_confidence_flag: String(row.inferred_confidence_flag || '').trim(),
      rationale_style_tags: String(row.rationale_style_tags || '').trim(),
      rationale_short: String(row.rationale_short || '').trim(),
      rationale_preview: String(row.rationale_preview || '').trim(),
      raw_character_vector_json: String(row.raw_character_vector_json || '').trim()
    });
  });
  if (!out.length && warnings) warnings.push('missing_source_rows:Provider_Character_Residuals');
  return out;
}

function _providerCharacterMicroExpressionBuildResidualLookup_(rows) {
  var map = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = String(row.event_id || '').trim() + '|' + String(row.provider || '').trim();
    if (!String(row.event_id || '').trim() || !String(row.provider || '').trim()) continue;
    map[key] = row;
  }
  return map;
}

function _providerCharacterMicroExpressionBuildCaseLookup_(rows) {
  var map = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = String(row.event_id || '').trim() + '|' + String(row.provider || '').trim();
    if (!String(row.event_id || '').trim() || !String(row.provider || '').trim()) continue;
    map[key] = row;
  }
  return map;
}

function _providerCharacterMicroExpressionBuildEventUniverse_(economicCases, warnings) {
  var byEvent = {};
  for (var i = 0; i < (economicCases || []).length; i++) {
    var row = economicCases[i] || {};
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    if (!byEvent[eventId]) {
      byEvent[eventId] = {
        event_id: eventId,
        release_ts: String(row.release_ts || '').trim(),
        indicator_name: String(row.indicator_name || '').trim(),
        family: String(row.outcome_family || '').trim() || 'other',
        family_key: _providerCharacterMicroExpressionFamilyKey_(String(row.outcome_family || '').trim(), String(row.indicator_name || '').trim()),
        importance: String(row.importance || '').trim(),
        consensus_value: row.consensus_value,
        prev_revision: row.prev_revision,
        released_value: row.released_value,
        providers: {},
        provider_count: 0
      };
    }
    byEvent[eventId].providers[row.provider] = row;
  }

  var out = [];
  Object.keys(byEvent).sort(function(a, b) {
    var aa = byEvent[a] || {};
    var bb = byEvent[b] || {};
    if (String(aa.release_ts || '') !== String(bb.release_ts || '')) return String(aa.release_ts || '').localeCompare(String(bb.release_ts || ''));
    return String(a).localeCompare(String(b));
  }).forEach(function(eventId) {
    var item = byEvent[eventId];
    item.provider_count = Object.keys(item.providers || {}).length;
    out.push(item);
  });

  if (!out.length && warnings) warnings.push('economic_event_universe_empty');
  return out;
}

function _providerCharacterMicroExpressionLoadOverlapTraits_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var traits = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var finalResult = String(row.final_result || '').trim();
    var overlapClass = String(row.overlap_classification || '').trim();
    var trait = String(row.trait || '').trim();
    var overlapTrait = String(row.strongest_overlap_trait || '').trim();
    if (!trait && !overlapTrait) continue;
    if (finalResult === 'overlap_artifact' || finalResult === 'fails_falsification' || overlapClass === 'likely_duplicate_cluster' || overlapClass === 'strong_overlap') {
      if (trait) traits[trait] = true;
      if (overlapTrait) traits[overlapTrait] = true;
    }
  }
  var out = Object.keys(traits).sort();
  if (!out.length && warnings) warnings.push('overlap_traits_unavailable');
  return out;
}

function _providerCharacterMicroExpressionSelectSampleEvents_(eventUniverse, residualLookup, overlapTraits, warnings) {
  var selected = [];
  var seen = {};
  var sampleInfo = {};
  var targets = _providerCharacterMicroExpressionTargetFamilyKeys_();

  function addEvent(event, band) {
    if (!event || seen[event.event_id]) return false;
    seen[event.event_id] = true;
    selected.push({
      event_id: event.event_id,
      sample_band: band,
      family: event.family,
      family_key: event.family_key,
      release_ts: event.release_ts,
      indicator_name: event.indicator_name,
      importance: event.importance,
      provider_count: event.provider_count,
      providers: event.providers
    });
    sampleInfo[event.event_id] = band;
    return true;
  }

  var familyBuckets = _providerCharacterMicroExpressionBucketEventsByFamily_(eventUniverse, targets);
  _providerCharacterMicroExpressionSelectRoundRobin_(familyBuckets, 20, addEvent, 'high_value_family');

  var overlapPool = eventUniverse.filter(function(event) {
    return !seen[event.event_id];
  });
  overlapPool.sort(function(a, b) {
    var scoreDiff = _providerCharacterMicroExpressionOverlapScore_(b, overlapTraits, residualLookup) - _providerCharacterMicroExpressionOverlapScore_(a, overlapTraits, residualLookup);
    if (scoreDiff !== 0) return scoreDiff;
    return _providerCharacterMicroExpressionHash_(a.event_id) - _providerCharacterMicroExpressionHash_(b.event_id);
  });
  for (var i = 0; i < overlapPool.length && selected.length < 40; i++) {
    addEvent(overlapPool[i], 'overlap_cluster');
  }

  var remaining = eventUniverse.filter(function(event) {
    return !seen[event.event_id];
  });
  var broadBuckets = _providerCharacterMicroExpressionBucketEventsByFamily_(remaining, []);
  _providerCharacterMicroExpressionSelectRoundRobin_(broadBuckets, 60, addEvent, 'broad_random');

  var leftover = eventUniverse.filter(function(event) {
    return !seen[event.event_id];
  });
  leftover.sort(function(a, b) {
    var ha = _providerCharacterMicroExpressionHash_(a.event_id);
    var hb = _providerCharacterMicroExpressionHash_(b.event_id);
    if (ha !== hb) return ha - hb;
    return String(a.event_id).localeCompare(String(b.event_id));
  });
  for (var j = 0; j < leftover.length && selected.length < 100; j++) {
    addEvent(leftover[j], sampleInfo[leftover[j].event_id] || 'broad_random');
  }

  if (selected.length > 100) selected = selected.slice(0, 100);
  if (selected.length < 100 && warnings) warnings.push('sample_size_below_target:' + selected.length);
  return selected;
}

function _providerCharacterMicroExpressionBuildPilotRows_(generatedTs, sampledEvents, caseLookup, residualLookup, warnings) {
  var rows = [];
  var providerOrder = { Anthropic: 1, Gemini: 2, OpenAI: 3 };

  for (var i = 0; i < (sampledEvents || []).length; i++) {
    var event = sampledEvents[i] || {};
    var providerNames = Object.keys((event && event.providers) ? event.providers : {});
    providerNames.sort(function(a, b) {
      var pa = providerOrder[a] || 99;
      var pb = providerOrder[b] || 99;
      if (pa !== pb) return pa - pb;
      return String(a).localeCompare(String(b));
    });

    for (var p = 0; p < providerNames.length; p++) {
      var provider = providerNames[p];
      var caseRow = caseLookup[String(event.event_id || '').trim() + '|' + provider];
      var residualRow = residualLookup[String(event.event_id || '').trim() + '|' + provider];
      if (!caseRow || !residualRow) continue;

      var extraction = _providerCharacterMicroExpressionExtractRow_(caseRow, residualRow);
      rows.push({
        generated_ts: generatedTs,
        event_id: String(event.event_id || '').trim(),
        provider: provider,
        indicator_name: String(caseRow.indicator_name || event.indicator_name || '').trim(),
        release_ts: String(caseRow.release_ts || event.release_ts || '').trim(),
        outcome_family: String(caseRow.outcome_family || event.family || 'other').trim() || 'other',
        importance: String(caseRow.importance || event.importance || '').trim(),
        ai_forecast_value: caseRow.ai_forecast_value == null ? '' : caseRow.ai_forecast_value,
        consensus_value: caseRow.consensus_value == null ? '' : caseRow.consensus_value,
        released_value: caseRow.released_value == null ? '' : caseRow.released_value,
        economic_dir_ok: String(caseRow.value_dir_ok || '').trim(),
        forecast_error_abs: caseRow.forecast_error_abs == null ? '' : caseRow.forecast_error_abs,
        better_than_consensus: extraction.better_than_consensus,
        primary_focus_phrase: extraction.primary_focus_phrase,
        secondary_focus_phrase: extraction.secondary_focus_phrase,
        ignored_or_discounted_factor_phrase: extraction.ignored_or_discounted_factor_phrase,
        causal_path_phrase: extraction.causal_path_phrase,
        failure_condition_phrase: extraction.failure_condition_phrase,
        confidence_basis_phrase: extraction.confidence_basis_phrase,
        uncertainty_phrase: extraction.uncertainty_phrase,
        expression_summary_phrase: extraction.expression_summary_phrase,
        attention_terms: extraction.attention_terms,
        source_text_basis: extraction.source_text_basis,
        extraction_method: extraction.extraction_method,
        token_cost_estimate: extraction.token_cost_estimate,
        notes: extraction.notes
      });
    }
  }

  if (!rows.length && warnings) warnings.push('micro_expression_rows_empty');
  return rows;
}

function _providerCharacterMicroExpressionExtractRow_(caseRow, residualRow) {
  var primarySource = _providerCharacterMicroExpressionBestSourceText_(residualRow.rationale_short, residualRow.rationale_preview, caseRow.attention_primary_factor, caseRow.attention_factors);
  var secondarySource = _providerCharacterMicroExpressionBestSourceText_(residualRow.rationale_preview, residualRow.rationale_short, caseRow.attention_factors, residualRow.emphasized_factors);
  var sourceBits = [];
  if (residualRow.rationale_short) sourceBits.push('rationale_short');
  if (residualRow.rationale_preview) sourceBits.push('rationale_preview');
  if (caseRow.attention_primary_factor) sourceBits.push('attention_primary_factor');
  if (caseRow.attention_factors) sourceBits.push('attention_factors');
  if (residualRow.emphasized_factors) sourceBits.push('emphasized_factors');
  if (residualRow.ignored_factors) sourceBits.push('ignored_factors');
  if (residualRow.rationale_style_tags) sourceBits.push('rationale_style_tags');
  if (residualRow.raw_character_vector_json) sourceBits.push('raw_character_vector_json');

  var primary = _providerCharacterMicroExpressionPhraseFromText_(primarySource, 8);
  if (!primary) primary = _providerCharacterMicroExpressionPhraseFromFactors_(residualRow.emphasized_factors, 8);

  var secondary = _providerCharacterMicroExpressionPhraseFromText_(secondarySource, 8);
  if (!secondary || secondary === primary) secondary = _providerCharacterMicroExpressionPhraseFromFactors_(residualRow.ignored_factors, 8);

  var ignored = _providerCharacterMicroExpressionIgnoredPhrase_(residualRow.ignored_factors, residualRow.rationale_short, residualRow.rationale_preview);
  var causalPath = _providerCharacterMicroExpressionCausalPath_(primary, secondary, residualRow);
  var failureCondition = _providerCharacterMicroExpressionFailureCondition_(residualRow, caseRow);
  var confidenceBasis = _providerCharacterMicroExpressionConfidenceBasis_(residualRow, caseRow);
  var uncertainty = _providerCharacterMicroExpressionUncertaintyPhrase_(residualRow, caseRow);
  var summary = _providerCharacterMicroExpressionSummaryPhrase_(primary, causalPath, uncertainty);
  var attentionTerms = _providerCharacterMicroExpressionAttentionTerms_(primary, secondary, causalPath, failureCondition, confidenceBasis, uncertainty, residualRow);
  var betterThanConsensus = _providerCharacterMicroExpressionBetterThanConsensus_(caseRow);
  var tokenEstimate = _providerCharacterMicroExpressionTokenEstimate_(sourceBits, residualRow, caseRow, primary, secondary, causalPath, failureCondition, confidenceBasis, uncertainty, summary);

  return {
    primary_focus_phrase: primary,
    secondary_focus_phrase: secondary,
    ignored_or_discounted_factor_phrase: ignored,
    causal_path_phrase: causalPath,
    failure_condition_phrase: failureCondition,
    confidence_basis_phrase: confidenceBasis,
    uncertainty_phrase: uncertainty,
    expression_summary_phrase: summary,
    attention_terms: attentionTerms,
    source_text_basis: sourceBits.join('|'),
    extraction_method: 'stored_text_replay_heuristic_v1',
    token_cost_estimate: tokenEstimate,
    better_than_consensus: betterThanConsensus,
    notes: 'stored_replay_only; no_provider_calls; no_prediction_runs'
  };
}

function _providerCharacterMicroExpressionBestSourceText_() {
  for (var i = 0; i < arguments.length; i++) {
    var text = String(arguments[i] || '').trim();
    if (text) return text;
  }
  return '';
}

function _providerCharacterMicroExpressionPhraseFromText_(text, maxWords) {
  var phrases = _providerCharacterMicroExpressionSplitPhrases_(String(text || ''));
  for (var i = 0; i < phrases.length; i++) {
    var phrase = _providerCharacterMicroExpressionTrimWords_(phrases[i], 3, maxWords || 8);
    if (phrase) return phrase;
  }
  return '';
}

function _providerCharacterMicroExpressionPhraseFromFactors_(factorText, maxWords) {
  var factors = _providerCharacterMicroExpressionFactorList_(factorText);
  if (!factors.length) return '';
  return _providerCharacterMicroExpressionFactorPhrase_(factors[0], maxWords || 8);
}

function _providerCharacterMicroExpressionIgnoredPhrase_(ignoredFactors, primaryText, secondaryText) {
  var factors = _providerCharacterMicroExpressionFactorList_(ignoredFactors);
  if (factors.length) {
    var phrases = [];
    for (var i = 0; i < Math.min(2, factors.length); i++) {
      phrases.push(_providerCharacterMicroExpressionFactorPhrase_(factors[i], 4));
    }
    var joined = phrases.join(' and ');
    return _providerCharacterMicroExpressionTrimWords_(joined, 3, 8) || 'not explicitly referenced';
  }
  var hint = _providerCharacterMicroExpressionInferIgnoredHint_(primaryText, secondaryText);
  return _providerCharacterMicroExpressionTrimWords_(hint, 3, 8) || 'not explicitly referenced';
}

function _providerCharacterMicroExpressionCausalPath_(primaryPhrase, secondaryPhrase, residualRow) {
  var text = _providerCharacterMicroExpressionBestSourceText_(primaryPhrase, secondaryPhrase, residualRow.rationale_short, residualRow.rationale_preview);
  var lower = String(text || '').toLowerCase();
  var path = '';
  if (/\b(inflation|cpi|ppi|prices?)\b/.test(lower)) path = 'surprise moves inflation then yields';
  else if (/\b(labor|employment|payroll|jobs|unemployment)\b/.test(lower)) path = 'jobs move wages then rates';
  else if (/\b(housing|mortgage|home|building permits|housing starts)\b/.test(lower)) path = 'housing flows into growth then rates';
  else if (/\b(central bank|fomc|fed|rates?|yield|yield curve|treasury)\b/.test(lower)) path = 'policy surprise moves yields then USD';
  else if (/\b(consumer|retail|spending|demand|confidence|sentiment)\b/.test(lower)) path = 'demand surprise flows into pricing';
  else if (/\b(energy|oil|wti|inventory|crude)\b/.test(lower)) path = 'inventory shock moves oil then inflation';
  else if (/\b(usd|usdjpy|dxy|fx)\b/.test(lower)) path = 'release moves FX then rates';
  else if (/\b(whipsaw|noise|flat|mixed|uncertain)\b/.test(lower)) path = 'signal noise keeps reaction flat';
  if (!path) path = 'release moves repricing then follow-through';
  return _providerCharacterMicroExpressionTrimWords_(path, 3, 8);
}

function _providerCharacterMicroExpressionFailureCondition_(residualRow, caseRow) {
  var text = _providerCharacterMicroExpressionBestSourceText_(residualRow.rationale_short, residualRow.rationale_preview);
  var lower = String(text || '').toLowerCase();
  var phrase = '';
  if (lower.indexOf('missing consensus') >= 0 || lower.indexOf('no consensus') >= 0) phrase = 'missing consensus leaves the read flat';
  else if (lower.indexOf('low signal') >= 0 || lower.indexOf('weak signal') >= 0) phrase = 'weak signal or noisy release';
  else if (lower.indexOf('indirect') >= 0 && lower.indexOf('policy') >= 0) phrase = 'policy transmission stays too indirect';
  else if (lower.indexOf('ambiguous') >= 0 || lower.indexOf('uncertain') >= 0) phrase = 'ambiguity keeps conviction low';
  else if (lower.indexOf('flat') >= 0) phrase = 'market treats the print as noise';
  if (!phrase) phrase = 'market treats the print as noise';
  return _providerCharacterMicroExpressionTrimWords_(phrase, 3, 8);
}

function _providerCharacterMicroExpressionConfidenceBasis_(residualRow, caseRow) {
  var parts = [];
  var providerConf = '';
  try {
    var raw = residualRow.raw_character_vector_json ? JSON.parse(residualRow.raw_character_vector_json) : null;
    if (raw && raw.provider_confidence && raw.provider_confidence.level) {
      providerConf = String(raw.provider_confidence.level || '').trim().toLowerCase();
    }
  } catch (e) {}
  if (providerConf) parts.push(providerConf + ' confidence');
  if (String(residualRow.baseline_confidence || '').trim()) parts.push(String(residualRow.baseline_confidence || '').trim() + ' baseline');
  if (String(residualRow.direction_delta_from_baseline || '').trim()) parts.push(String(residualRow.direction_delta_from_baseline || '').trim());
  if (!parts.length) parts.push('low baseline confidence');
  return _providerCharacterMicroExpressionTrimWords_(parts.join(', '), 3, 8);
}

function _providerCharacterMicroExpressionUncertaintyPhrase_(residualRow, caseRow) {
  var risk = String(residualRow.risk_language || '').trim().toLowerCase();
  var unc = String(residualRow.uncertainty_pattern || '').trim().toLowerCase();
  var phrase = '';
  if (unc === 'scenario_based') phrase = 'scenario framed uncertainty';
  else if (unc === 'low_signal') phrase = 'low signal and flat';
  else if (unc === 'mixed_signal') phrase = 'mixed signal, split read';
  else if (unc === 'hedged') phrase = 'hedged conviction and caution';
  else if (unc === 'cautious') phrase = 'cautious, limited conviction';
  else if (unc === 'confident') phrase = 'clear conviction';
  else if (unc === 'unknown') phrase = 'uncertainty stays unresolved';
  if (!phrase) {
    if (risk === 'hidden_detail_risk_language') phrase = 'hidden detail risk';
    else if (risk === 'tail_risk_language') phrase = 'tail risk framing';
    else if (risk === 'crowded_trade_language') phrase = 'crowded trade concern';
    else if (risk === 'low_risk_language') phrase = 'low risk framing';
    else if (risk === 'high_risk_language') phrase = 'high risk framing';
    else if (risk === 'uncertainty_language') phrase = 'uncertainty remains';
  }
  if (!phrase) phrase = 'uncertainty remains';
  return _providerCharacterMicroExpressionTrimWords_(phrase, 3, 8);
}

function _providerCharacterMicroExpressionSummaryPhrase_(primaryPhrase, causalPath, uncertaintyPhrase) {
  var parts = [];
  if (primaryPhrase) parts.push(primaryPhrase);
  if (causalPath) parts.push(causalPath);
  if (uncertaintyPhrase) parts.push(uncertaintyPhrase);
  return _providerCharacterMicroExpressionTrimWords_(parts.join(', '), 3, 8);
}

function _providerCharacterMicroExpressionAttentionTerms_(primaryPhrase, secondaryPhrase, causalPath, failureCondition, confidenceBasis, uncertaintyPhrase, residualRow) {
  var text = [primaryPhrase, secondaryPhrase, causalPath, failureCondition, confidenceBasis, uncertaintyPhrase, residualRow.indicator_name, residualRow.outcome_family].join(' ');
  var tokens = _providerCharacterMicroExpressionTokenize_(text);
  var filtered = [];
  var seen = {};
  for (var i = 0; i < tokens.length; i++) {
    var t = tokens[i];
    if (!t) continue;
    if (_providerCharacterMicroExpressionIsStopToken_(t)) continue;
    if (seen[t]) continue;
    seen[t] = true;
    filtered.push(t);
    if (filtered.length >= 8) break;
  }
  return filtered.join('|');
}

function _providerCharacterMicroExpressionBetterThanConsensus_(caseRow) {
  var ai = _numOrNull_(caseRow.ai_forecast_value);
  var released = _numOrNull_(caseRow.released_value);
  var consensus = _numOrNull_(caseRow.consensus_value);
  if (ai == null || released == null || consensus == null) return '';
  return Math.abs(ai - released) < Math.abs(consensus - released) ? 'TRUE' : 'FALSE';
}

function _providerCharacterMicroExpressionTokenEstimate_(sourceBits, residualRow, caseRow, primary, secondary, causalPath, failureCondition, confidenceBasis, uncertainty, summary) {
  var text = [
    residualRow.rationale_short,
    residualRow.rationale_preview,
    caseRow.attention_primary_factor,
    caseRow.attention_factors,
    residualRow.emphasized_factors,
    residualRow.ignored_factors,
    residualRow.rationale_style_tags,
    primary,
    secondary,
    causalPath,
    failureCondition,
    confidenceBasis,
    uncertainty,
    summary
  ].join(' ');
  var words = _providerCharacterMicroExpressionTokenize_(text).length;
  return Math.max(4, Math.round(words || 0));
}

function _providerCharacterMicroExpressionFactorList_(text) {
  var raw = String(text || '').trim();
  if (!raw) return [];
  return raw.split('|').map(function(item) {
    return String(item || '').trim();
  }).filter(function(item) {
    return !!item;
  });
}

function _providerCharacterMicroExpressionFactorPhrase_(factor, maxWords) {
  var map = {
    consensus: 'consensus anchor',
    previous_value: 'prior print',
    surprise_history: 'surprise history',
    revision_history: 'revision path',
    family_context: 'family backdrop',
    signal_quality: 'signal quality',
    rates: 'rate path',
    yield_curve: 'yield curve',
    usdjpy: 'USDJPY move',
    dxy: 'dollar index',
    spx: 'equity risk tone',
    gold: 'safe haven bid',
    wti: 'oil move',
    jp10y: 'Japan ten-year yields',
    us_jp_spread: 'US Japan spread',
    inflation_persistence: 'sticky inflation',
    labor_strength: 'strong labor',
    consumer_demand: 'consumer demand',
    housing_weakness: 'housing softness',
    manufacturing_cycle: 'manufacturing cycle',
    energy_inventory: 'inventory shock',
    hidden_detail_risk: 'hidden detail risk',
    missing_consensus: 'missing consensus',
    low_signal_event: 'low signal',
    direct_fx_transmission: 'direct FX transmission',
    market_whipsaw_risk: 'whipsaw risk',
    positioning_or_crowding: 'crowded positioning',
    uncertainty: 'uncertainty',
    other: 'other'
  };
  var key = String(factor || '').trim().toLowerCase();
  var phrase = map[key] || key.replace(/_/g, ' ');
  return _providerCharacterMicroExpressionTrimWords_(phrase, 3, maxWords || 8);
}

function _providerCharacterMicroExpressionInferIgnoredHint_(primaryText, secondaryText) {
  var text = String(primaryText || '') + ' ' + String(secondaryText || '');
  var lower = text.toLowerCase();
  if (lower.indexOf('consensus') >= 0) return 'prior print not explicit';
  if (lower.indexOf('rates') >= 0 || lower.indexOf('yield') >= 0) return 'yield path not explicit';
  if (lower.indexOf('usd') >= 0 || lower.indexOf('fx') >= 0) return 'FX channel not explicit';
  if (lower.indexOf('detail') >= 0) return 'minor details not explicit';
  return 'not explicitly referenced';
}

function _providerCharacterMicroExpressionSplitPhrases_(text) {
  var raw = String(text || '').trim();
  if (!raw) return [];
  var out = [];
  raw.split(/[.!?;]+|\s+-\s+|,| but | however | though | while | because | since /i).forEach(function(part) {
    var cleaned = String(part || '').replace(/\s+/g, ' ').trim();
    if (cleaned) out.push(cleaned);
  });
  if (!out.length && raw) out.push(raw);
  return out;
}

function _providerCharacterMicroExpressionTrimWords_(text, minWords, maxWords) {
  var tokens = _providerCharacterMicroExpressionTokenize_(text);
  if (!tokens.length) return '';
  var start = 0;
  var end = Math.min(tokens.length, maxWords || 8);
  if (end < (minWords || 3)) return '';
  return tokens.slice(start, end).join(' ');
}

function _providerCharacterMicroExpressionTokenize_(text) {
  var stop = _providerCharacterMicroExpressionStopTokens_();
  return String(text || '')
    .toLowerCase()
    .replace(/[_/|]+/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .split(/\s+/)
    .map(function(token) { return String(token || '').trim(); })
    .filter(function(token) { return !!token && !stop[token]; });
}

function _providerCharacterMicroExpressionStopTokens_() {
  return {
    a: true, an: true, and: true, as: true, at: true, be: true, by: true, for: true, from: true,
    if: true, in: true, into: true, is: true, it: true, its: true, no: true, not: true, of: true,
    on: true, or: true, out: true, the: true, to: true, too: true, too: true, with: true, without: true,
    this: true, that: true, these: true, those: true, are: true, was: true, were: true, can: true,
    will: true, would: true, should: true, could: true, may: true, might: true, maybe: true,
    provider: true, forecast: true, signal: true, signals: true, print: true, release: true, data: true,
    model: true, models: true, path: true, paths: true, factor: true, factors: true, event: true,
    reaction: true, move: true, moves: true, moveing: true, market: true, usd: false, fx: false, jpy: false
  };
}

function _providerCharacterMicroExpressionIsStopToken_(token) {
  return !!_providerCharacterMicroExpressionStopTokens_()[String(token || '').trim().toLowerCase()];
}

function _providerCharacterMicroExpressionRowIsNewer_(candidate, existing) {
  var a = String(candidate.generated_ts || candidate.created_ts || '').trim();
  var b = String(existing.generated_ts || existing.created_ts || '').trim();
  if (a !== b) return a > b;
  return true;
}

function _providerCharacterMicroExpressionFamilyKey_(family, indicatorName) {
  var text = (String(family || '') + ' ' + String(indicatorName || '')).toLowerCase();
  if (/inflation|cpi|ppi|prices|core pce/.test(text)) return 'inflation';
  if (/labor|employment|payroll|jobs|unemployment|claims|wage/.test(text)) return 'labor';
  if (/growth|gdp|activity|production|orders|sales/.test(text)) return 'growth';
  if (/central bank|fomc|fed|rate|rates|yield|treasury|policy/.test(text)) return 'central_bank';
  if (/consumer|retail|spending|confidence|sentiment/.test(text)) return 'consumer';
  if (/housing|mortgage|home|building permits|starts/.test(text)) return 'housing';
  if (/manufactur|pmi|ism|factory|durable/.test(text)) return 'manufacturing';
  if (/energy|oil|wti|crude|inventory|gas/.test(text)) return 'energy';
  return String(family || 'other').trim().toLowerCase() || 'other';
}

function _providerCharacterMicroExpressionTargetFamilyKeys_() {
  return {
    inflation: true,
    labor: true,
    growth: true,
    central_bank: true,
    consumer: true,
    rates: true,
    sentiment: true
  };
}

function _providerCharacterMicroExpressionBucketEventsByFamily_(eventUniverse, familyFilter) {
  var out = {};
  var filter = familyFilter && familyFilter.length ? familyFilter : null;
  for (var i = 0; i < (eventUniverse || []).length; i++) {
    var event = eventUniverse[i] || {};
    var key = String(event.family_key || event.family || 'other').trim().toLowerCase() || 'other';
    if (filter && !filter[key]) continue;
    if (!out[key]) out[key] = [];
    out[key].push(event);
  }
  Object.keys(out).forEach(function(key) {
    out[key].sort(function(a, b) {
      var ha = _providerCharacterMicroExpressionHash_(a.event_id);
      var hb = _providerCharacterMicroExpressionHash_(b.event_id);
      if (ha !== hb) return ha - hb;
      return String(a.event_id).localeCompare(String(b.event_id));
    });
  });
  return out;
}

function _providerCharacterMicroExpressionSelectRoundRobin_(buckets, targetCount, addFn, band) {
  var keys = Object.keys(buckets || {}).sort();
  var positions = {};
  for (var i = 0; i < keys.length; i++) positions[keys[i]] = 0;
  var added = 0;
  while (added < targetCount) {
    var progressed = false;
    for (var k = 0; k < keys.length && added < targetCount; k++) {
      var key = keys[k];
      var list = buckets[key] || [];
      var pos = positions[key] || 0;
      if (pos >= list.length) continue;
      positions[key] = pos + 1;
      if (addFn(list[pos], band)) added += 1;
      progressed = true;
    }
    if (!progressed) break;
  }
}

function _providerCharacterMicroExpressionOverlapScore_(event, overlapTraits, residualLookup) {
  var score = 0;
  var providers = Object.keys(event.providers || {});
  for (var i = 0; i < providers.length; i++) {
    var provider = providers[i];
    var residual = residualLookup[String(event.event_id || '').trim() + '|' + provider];
    if (!residual) continue;
    for (var j = 0; j < (overlapTraits || []).length; j++) {
      if (_providerCharacterMicroExpressionTraitMatchesResidual_(overlapTraits[j], residual)) {
        score += 1;
        break;
      }
    }
  }
  return score;
}

function _providerCharacterMicroExpressionTraitMatchesResidual_(trait, residual) {
  return _providerCharacterEconomicTraitMatchesResidual_(trait, residual);
}

function _providerCharacterMicroExpressionHash_(text) {
  var s = String(text || '');
  var hash = 0;
  for (var i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash) + s.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function _providerCharacterMicroExpressionBundleRowsToObjects_(bundle) {
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

function _providerCharacterMicroExpressionBuildClusterRows_(generatedTs, pilotRows, warnings) {
  var byProvider = {};
  for (var i = 0; i < (pilotRows || []).length; i++) {
    var row = pilotRows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!byProvider[provider]) byProvider[provider] = [];
    byProvider[provider].push(row);
  }

  var clusters = [];
  Object.keys(byProvider).sort().forEach(function(provider) {
    var providerRows = byProvider[provider].slice().sort(function(a, b) {
      if (String(a.release_ts || '') !== String(b.release_ts || '')) return String(a.release_ts || '').localeCompare(String(b.release_ts || ''));
      return String(a.event_id || '').localeCompare(String(b.event_id || ''));
    });
    var providerClusters = [];

    for (var i = 0; i < providerRows.length; i++) {
      var row = providerRows[i];
      var tokens = _providerCharacterMicroExpressionClusterTokens_(row);
      var bestIdx = -1;
      var bestScore = 0;

      for (var c = 0; c < providerClusters.length; c++) {
        var cluster = providerClusters[c];
        var score = _providerCharacterMicroExpressionClusterSimilarity_(tokens, cluster.token_set, row, cluster.representative_row);
        if (score > bestScore) {
          bestScore = score;
          bestIdx = c;
        }
      }

      if (bestIdx >= 0 && bestScore >= 0.38) {
        var clusterMatch = providerClusters[bestIdx];
        clusterMatch.rows.push(row);
        clusterMatch.event_ids[row.event_id] = true;
        clusterMatch.token_counts = _providerCharacterMicroExpressionMergeTokenCounts_(clusterMatch.token_counts, tokens);
        clusterMatch.token_set = _providerCharacterMicroExpressionUnionTokens_(clusterMatch.token_set, tokens);
        clusterMatch.family_counts[row.outcome_family] = (clusterMatch.family_counts[row.outcome_family] || 0) + 1;
        clusterMatch.primary_texts[row.expression_summary_phrase] = (clusterMatch.primary_texts[row.expression_summary_phrase] || 0) + 1;
        clusterMatch.representative_row = _providerCharacterMicroExpressionPickRepresentativeRow_(clusterMatch.representative_row, row, clusterMatch);
      } else {
        providerClusters.push({
          provider: provider,
          rows: [row],
          event_ids: (function() { var m = {}; m[row.event_id] = true; return m; })(),
          token_set: tokens,
          token_counts: _providerCharacterMicroExpressionInitTokenCounts_(tokens),
          family_counts: (function() { var m = {}; m[row.outcome_family] = 1; return m; })(),
          primary_texts: (function() { var m = {}; m[row.expression_summary_phrase] = 1; return m; })(),
          representative_row: row
        });
      }
    }

    providerClusters.sort(function(a, b) {
      if (b.rows.length !== a.rows.length) return b.rows.length - a.rows.length;
      return String(_providerCharacterMicroExpressionClusterRepresentativePhrase_(b)).localeCompare(String(_providerCharacterMicroExpressionClusterRepresentativePhrase_(a)));
    });

    for (var j = 0; j < providerClusters.length; j++) {
      var cluster = providerClusters[j];
      var rep = _providerCharacterMicroExpressionClusterRepresentativePhrase_(cluster);
      var terms = _providerCharacterMicroExpressionClusterRepresentativeTerms_(cluster, 5);
      var examples = _providerCharacterMicroExpressionClusterRepresentativeExamples_(cluster, 2);
      var providerBaseline = _providerCharacterMicroExpressionProviderBaseline_(providerRows);
      var clusterMetrics = _providerCharacterMicroExpressionClusterMetrics_(cluster.rows);
      var specificity = _providerCharacterMicroExpressionProviderSpecificity_(cluster, pilotRows);
      var sepHint = _providerCharacterMicroExpressionSeparationHint_(clusterMetrics, providerBaseline);
      clusters.push({
        generated_ts: generatedTs,
        cluster_id: _providerCharacterMicroExpressionClusterId_(provider, j + 1),
        provider: provider,
        cluster_phrase: rep,
        representative_terms: terms,
        representative_examples: examples,
        row_count: cluster.rows.length,
        event_count: Object.keys(cluster.event_ids || {}).length,
        family_distribution: _providerCharacterMicroExpressionCountMapText_(cluster.family_counts, 5),
        avg_economic_dir_ok: clusterMetrics.avg_economic_dir_ok == null ? '' : clusterMetrics.avg_economic_dir_ok,
        avg_forecast_error_abs: clusterMetrics.avg_forecast_error_abs == null ? '' : clusterMetrics.avg_forecast_error_abs,
        better_than_consensus_rate: clusterMetrics.better_than_consensus_rate == null ? '' : clusterMetrics.better_than_consensus_rate,
        provider_specificity_score: specificity == null ? '' : _round4_(specificity),
        economic_separation_hint: sepHint,
        notes: 'cluster_tokens=' + terms + '; provider_baseline_dir_ok=' + (providerBaseline.avg_economic_dir_ok == null ? 'n/a' : providerBaseline.avg_economic_dir_ok) + '; provider_baseline_error=' + (providerBaseline.avg_forecast_error_abs == null ? 'n/a' : providerBaseline.avg_forecast_error_abs)
      });
    }
  });

  clusters.sort(function(a, b) {
    if (a.provider !== b.provider) return a.provider.localeCompare(b.provider);
    if (b.row_count !== a.row_count) return b.row_count - a.row_count;
    return String(a.cluster_id).localeCompare(String(b.cluster_id));
  });

  if (!clusters.length && warnings) warnings.push('micro_expression_clusters_empty');
  return clusters;
}

function _providerCharacterMicroExpressionBuildSummaryRows_(generatedTs, pilotRows, clusterRows, warnings) {
  var groups = {};
  var allRows = (pilotRows || []).slice();
  allRows.push({ provider: 'ALL', event_id: '__all__', expression_summary_phrase: '', token_cost_estimate: 0 });

  for (var i = 0; i < (pilotRows || []).length; i++) {
    var row = pilotRows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!groups[provider]) groups[provider] = [];
    groups[provider].push(row);
  }
  groups.ALL = pilotRows || [];

  var rows = [];
  var providers = Object.keys(groups).sort(function(a, b) {
    if (a === 'ALL') return 1;
    if (b === 'ALL') return -1;
    return a.localeCompare(b);
  });

  for (var p = 0; p < providers.length; p++) {
    var provider = providers[p];
    var providerRows = groups[provider] || [];
    var providerClusters = (clusterRows || []).filter(function(row) {
      return String(row.provider || '') === String(provider || '') || (provider === 'ALL' && !!String(row.provider || '').trim());
    });
    var sampledEvents = {};
    var uniqueExpr = {};
    var positiveHints = [];
    var negativeHints = [];
    var specificityHints = [];

    for (var r = 0; r < providerRows.length; r++) {
      var row = providerRows[r];
      if (row.event_id) sampledEvents[row.event_id] = true;
      if (row.expression_summary_phrase) uniqueExpr[row.expression_summary_phrase] = true;
    }

    providerClusters.forEach(function(cluster) {
      if (String(cluster.economic_separation_hint || '').indexOf('above provider average') >= 0 || String(cluster.economic_separation_hint || '').indexOf('higher dir ok') >= 0 || String(cluster.economic_separation_hint || '').indexOf('higher better-than-consensus') >= 0) {
        positiveHints.push(cluster.cluster_phrase + ' (' + cluster.economic_separation_hint + ')');
      } else if (String(cluster.economic_separation_hint || '').indexOf('below provider average') >= 0 || String(cluster.economic_separation_hint || '').indexOf('higher error') >= 0 || String(cluster.economic_separation_hint || '').indexOf('lower dir ok') >= 0) {
        negativeHints.push(cluster.cluster_phrase + ' (' + cluster.economic_separation_hint + ')');
      }
      if (_numOrNull_(cluster.provider_specificity_score) != null && _numOrNull_(cluster.provider_specificity_score) >= 0.5) {
        specificityHints.push(cluster.cluster_phrase + ' (' + cluster.provider_specificity_score + ')');
      }
    });

    var avgTokenCost = _providerCharacterMicroExpressionAverage_(providerRows, 'token_cost_estimate');
    var strongestClusters = _providerCharacterMicroExpressionTopClusterText_(providerClusters, 3);
    var specificPatterns = _providerCharacterMicroExpressionTopSpecificClusterText_(providerClusters, 3);
    var positiveHintText = positiveHints.slice(0, 3).join(' | ');
    var negativeHintText = negativeHints.slice(0, 3).join(' | ');
    var resultClass = _providerCharacterMicroExpressionPilotResult_(providerRows, providerClusters, avgTokenCost, positiveHints.length, negativeHints.length);

    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      sampled_events: Object.keys(sampledEvents).length,
      expression_rows: providerRows.length,
      unique_micro_expression_count: Object.keys(uniqueExpr).length,
      cluster_count: providerClusters.length,
      strongest_expression_clusters: strongestClusters,
      most_provider_specific_patterns: specificPatterns,
      early_positive_economic_hints: positiveHintText,
      early_negative_economic_hints: negativeHintText,
      avg_token_cost_estimate: avgTokenCost == null ? '' : _round4_(avgTokenCost),
      pilot_result: resultClass.result,
      recommended_next_step: resultClass.next_step,
      notes: resultClass.note
    });
  }

  if (!rows.length && warnings) warnings.push('micro_expression_summary_empty');
  return rows;
}

function _providerCharacterMicroExpressionBuildMethodologyRows_(generatedTs, sources, sampledEventCount, rowCount, warnings) {
  var sourceSheets = [];
  if (sources.economicBundle) sourceSheets.push('Economic_Value_Accuracy');
  if (sources.residualBundle) sourceSheets.push('Provider_Character_Residuals');
  if (sources.falsificationBundle) sourceSheets.push('Character_Economic_Falsification');
  if (sources.providerSummaryBundle) sourceSheets.push('Provider_Character_Summary');
  if (sources.providerFamilySummaryBundle) sourceSheets.push('Provider_Character_Family_Summary');

  return [{
    generated_ts: generatedTs,
    experiment_name: 'Provider Character v2 - Micro-Expression Pilot v1',
    branch_name: 'Provider Character v2 / Raw Expression Candidate Branch',
    purpose: 'Test whether compact free-form attention expressions preserve more useful provider-character signal than predefined labels, while staying replay-only and low cost.',
    sample_strategy: 'Deterministic stratified sample of 100 completed economic events: 60 broad completed events, 20 events from prior overlap/failure clusters, and 20 events from high-value families such as inflation, labor, growth, rates / central bank, and consumer demand.',
    provider_calls_made: 'FALSE',
    prediction_runs_made: 'FALSE',
    production_changes: 'FALSE',
    source_sheets_used: _uniqueStrings_(sourceSheets).join('|'),
    extraction_method: 'stored_text_replay_heuristic_v1 from Provider_Character_Residuals and Economic_Value_Accuracy',
    token_minimization_rule: '3-8 words per micro-expression field; no long rationale; no predefined labels',
    forbidden_behavior: 'no provider calls|no prediction runs|no routing|no weighting|no calibration|no market-reaction scoring|no subscriber-facing changes',
    interpretation_rule: 'Treat the output as a diagnostic pilot only. Richer expressions and early separation hints are hypotheses, not validated predictive value.',
    notes: 'sampled_events=' + sampledEventCount + '; expression_rows=' + rowCount + '; no_provider_calls=' + 'TRUE' + '; no_prediction_runs=' + 'TRUE'
  }];
}

function _providerCharacterMicroExpressionClusterTokens_(row) {
  var text = [
    row.primary_focus_phrase,
    row.secondary_focus_phrase,
    row.ignored_or_discounted_factor_phrase,
    row.causal_path_phrase,
    row.failure_condition_phrase,
    row.confidence_basis_phrase,
    row.uncertainty_phrase,
    row.expression_summary_phrase,
    row.attention_terms
  ].join(' ');
  return _providerCharacterMicroExpressionTokenize_(text);
}

function _providerCharacterMicroExpressionClusterSimilarity_(tokensA, tokensB, rowA, rowB) {
  var j = _providerCharacterMicroExpressionJaccard_(tokensA, tokensB);
  var causalA = _providerCharacterMicroExpressionCausalSignature_(rowA);
  var causalB = _providerCharacterMicroExpressionCausalSignature_(rowB);
  var causal = causalA && causalB && causalA === causalB ? 1 : 0;
  return (j * 0.8) + (causal * 0.2);
}

function _providerCharacterMicroExpressionJaccard_(a, b) {
  var A = {};
  var B = {};
  for (var i = 0; i < (a || []).length; i++) A[a[i]] = true;
  for (var j = 0; j < (b || []).length; j++) B[b[j]] = true;
  var inter = 0;
  var uni = 0;
  Object.keys(A).forEach(function(key) { uni += 1; });
  Object.keys(B).forEach(function(key) {
    if (A[key]) inter += 1;
    else uni += 1;
  });
  return uni ? (inter / uni) : 0;
}

function _providerCharacterMicroExpressionCausalSignature_(row) {
  var text = String(row && row.causal_path_phrase || '').toLowerCase();
  if (!text) return '';
  if (text.indexOf('inflation') >= 0) return 'inflation';
  if (text.indexOf('jobs') >= 0 || text.indexOf('labor') >= 0) return 'labor';
  if (text.indexOf('housing') >= 0) return 'housing';
  if (text.indexOf('policy') >= 0 || text.indexOf('yields') >= 0 || text.indexOf('usd') >= 0) return 'policy_fx';
  if (text.indexOf('demand') >= 0) return 'demand';
  if (text.indexOf('inventory') >= 0 || text.indexOf('oil') >= 0) return 'energy';
  if (text.indexOf('flat') >= 0 || text.indexOf('noise') >= 0) return 'flat';
  return 'other';
}

function _providerCharacterMicroExpressionInitTokenCounts_(tokens) {
  var map = {};
  for (var i = 0; i < (tokens || []).length; i++) {
    var token = tokens[i];
    if (!token) continue;
    map[token] = (map[token] || 0) + 1;
  }
  return map;
}

function _providerCharacterMicroExpressionMergeTokenCounts_(base, tokens) {
  var out = {};
  Object.keys(base || {}).forEach(function(key) { out[key] = Number(base[key] || 0); });
  for (var i = 0; i < (tokens || []).length; i++) {
    var token = tokens[i];
    if (!token) continue;
    out[token] = (out[token] || 0) + 1;
  }
  return out;
}

function _providerCharacterMicroExpressionPickRepresentativeRow_(existing, candidate, cluster) {
  if (!existing) return candidate;
  if (String(candidate.expression_summary_phrase || '').length > String(existing.expression_summary_phrase || '').length) return candidate;
  if ((candidate.token_cost_estimate || 0) < (existing.token_cost_estimate || 0)) return candidate;
  return existing;
}

function _providerCharacterMicroExpressionClusterRepresentativePhrase_(cluster) {
  var row = cluster.representative_row || (cluster.rows && cluster.rows[0]) || {};
  var phrase = String(row.expression_summary_phrase || row.primary_focus_phrase || row.causal_path_phrase || '').trim();
  if (!phrase) phrase = _providerCharacterMicroExpressionTopTermPhrase_(cluster.token_counts);
  return _providerCharacterMicroExpressionTrimWords_(phrase, 3, 8);
}

function _providerCharacterMicroExpressionClusterRepresentativeTerms_(cluster, limit) {
  var counts = cluster.token_counts || {};
  var arr = [];
  Object.keys(counts).forEach(function(key) {
    arr.push({ token: key, count: Number(counts[key] || 0) });
  });
  arr.sort(function(a, b) {
    if (b.count !== a.count) return b.count - a.count;
    return String(a.token).localeCompare(String(b.token));
  });
  return arr.slice(0, limit || 5).map(function(item) { return item.token; }).join('|');
}

function _providerCharacterMicroExpressionClusterRepresentativeExamples_(cluster, limit) {
  var seen = {};
  var out = [];
  for (var i = 0; i < (cluster.rows || []).length; i++) {
    var text = String(cluster.rows[i].expression_summary_phrase || '').trim();
    if (!text || seen[text]) continue;
    seen[text] = true;
    out.push(text);
    if (out.length >= (limit || 2)) break;
  }
  return out.join(' | ');
}

function _providerCharacterMicroExpressionClusterMetrics_(rows) {
  var dirOk = 0;
  var dirCount = 0;
  var errorAbs = 0;
  var errorCount = 0;
  var better = 0;
  var betterCount = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var d = String(row.economic_dir_ok || '').trim().toUpperCase();
    if (d === 'TRUE' || d === 'FALSE') {
      dirCount += 1;
      if (d === 'TRUE') dirOk += 1;
    }
    var err = _numOrNull_(row.forecast_error_abs);
    if (err != null) {
      errorAbs += Number(err || 0);
      errorCount += 1;
    }
    var btc = String(row.better_than_consensus || '').trim().toUpperCase();
    if (btc === 'TRUE' || btc === 'FALSE') {
      betterCount += 1;
      if (btc === 'TRUE') better += 1;
    }
  }
  return {
    avg_economic_dir_ok: dirCount ? _round4_(dirOk / dirCount) : null,
    avg_forecast_error_abs: errorCount ? _round4_(errorAbs / errorCount) : null,
    better_than_consensus_rate: betterCount ? _round4_(better / betterCount) : null
  };
}

function _providerCharacterMicroExpressionProviderBaseline_(rows) {
  var m = _providerCharacterMicroExpressionClusterMetrics_(rows);
  return {
    avg_economic_dir_ok: m.avg_economic_dir_ok,
    avg_forecast_error_abs: m.avg_forecast_error_abs,
    better_than_consensus_rate: m.better_than_consensus_rate
  };
}

function _providerCharacterMicroExpressionProviderSpecificity_(cluster, allRows) {
  var provider = String(cluster.provider || '').trim();
  var sig = _providerCharacterMicroExpressionClusterSignature_(cluster);
  var providers = {};
  for (var i = 0; i < (allRows || []).length; i++) {
    var row = allRows[i] || {};
    var rowSig = _providerCharacterMicroExpressionClusterSignatureFromRow_(row);
    if (sig && rowSig && _providerCharacterMicroExpressionJaccard_(_providerCharacterMicroExpressionTokenize_(sig), _providerCharacterMicroExpressionTokenize_(rowSig)) >= 0.45) {
      providers[String(row.provider || '').trim()] = true;
    }
  }
  var count = Object.keys(providers).length;
  if (!count) return 1;
  return 1 / count;
}

function _providerCharacterMicroExpressionClusterSignature_(cluster) {
  return _providerCharacterMicroExpressionClusterRepresentativeTerms_(cluster, 4);
}

function _providerCharacterMicroExpressionClusterSignatureFromRow_(row) {
  return [
    row.primary_focus_phrase,
    row.causal_path_phrase,
    row.uncertainty_phrase
  ].join(' ');
}

function _providerCharacterMicroExpressionSeparationHint_(clusterMetrics, providerBaseline) {
  var dir = _numOrNull_(clusterMetrics.avg_economic_dir_ok);
  var baseDir = _numOrNull_(providerBaseline.avg_economic_dir_ok);
  var err = _numOrNull_(clusterMetrics.avg_forecast_error_abs);
  var baseErr = _numOrNull_(providerBaseline.avg_forecast_error_abs);
  var btc = _numOrNull_(clusterMetrics.better_than_consensus_rate);
  var baseBtc = _numOrNull_(providerBaseline.better_than_consensus_rate);
  var parts = [];
  if (dir != null && baseDir != null) {
    if (dir > baseDir + 0.05) parts.push('higher dir ok');
    else if (dir < baseDir - 0.05) parts.push('lower dir ok');
  }
  if (err != null && baseErr != null) {
    if (err < baseErr - 0.05) parts.push('lower error');
    else if (err > baseErr + 0.05) parts.push('higher error');
  }
  if (btc != null && baseBtc != null) {
    if (btc > baseBtc + 0.05) parts.push('higher better-than-consensus');
    else if (btc < baseBtc - 0.05) parts.push('lower better-than-consensus');
  }
  if (!parts.length) return 'mixed separation';
  return parts.join('; ');
}

function _providerCharacterMicroExpressionClusterId_(provider, index) {
  var prefix = String(provider || 'provider').toUpperCase().replace(/[^A-Z0-9]+/g, '');
  return 'MEP_' + prefix + '_' + ('000' + Number(index || 0)).slice(-3);
}

function _providerCharacterMicroExpressionTopTermPhrase_(tokenCounts) {
  var arr = [];
  Object.keys(tokenCounts || {}).forEach(function(key) {
    arr.push({ token: key, count: Number(tokenCounts[key] || 0) });
  });
  arr.sort(function(a, b) {
    if (b.count !== a.count) return b.count - a.count;
    return String(a.token).localeCompare(String(b.token));
  });
  return arr.slice(0, 4).map(function(item) { return item.token; }).join(' ');
}

function _providerCharacterMicroExpressionUnionTokens_(baseTokens, extraTokens) {
  var map = {};
  for (var i = 0; i < (baseTokens || []).length; i++) map[baseTokens[i]] = true;
  for (var j = 0; j < (extraTokens || []).length; j++) map[extraTokens[j]] = true;
  return Object.keys(map);
}

function _providerCharacterMicroExpressionCountMapText_(map, limit) {
  var arr = [];
  Object.keys(map || {}).forEach(function(key) {
    arr.push({ key: key, count: Number(map[key] || 0) });
  });
  arr.sort(function(a, b) {
    if (b.count !== a.count) return b.count - a.count;
    return String(a.key).localeCompare(String(b.key));
  });
  return arr.slice(0, limit || 5).map(function(item) {
    return item.key + '(' + item.count + ')';
  }).join(' | ');
}

function _providerCharacterMicroExpressionTopClusterText_(clusters, limit) {
  var list = (clusters || []).slice().sort(function(a, b) {
    if ((b.row_count || 0) !== (a.row_count || 0)) return (b.row_count || 0) - (a.row_count || 0);
    if (_numOrNull_(b.avg_economic_dir_ok) != null && _numOrNull_(a.avg_economic_dir_ok) != null && _numOrNull_(b.avg_economic_dir_ok) !== _numOrNull_(a.avg_economic_dir_ok)) {
      return _numOrNull_(b.avg_economic_dir_ok) - _numOrNull_(a.avg_economic_dir_ok);
    }
    return String(a.cluster_id || '').localeCompare(String(b.cluster_id || ''));
  }).slice(0, limit || 3);
  return list.map(function(item) {
    return item.cluster_phrase + ' (' + item.row_count + ')';
  }).join(' | ');
}

function _providerCharacterMicroExpressionTopSpecificClusterText_(clusters, limit) {
  var list = (clusters || []).slice().sort(function(a, b) {
    var as = _numOrNull_(a.provider_specificity_score) || 0;
    var bs = _numOrNull_(b.provider_specificity_score) || 0;
    if (bs !== as) return bs - as;
    if ((b.row_count || 0) !== (a.row_count || 0)) return (b.row_count || 0) - (a.row_count || 0);
    return String(a.cluster_id || '').localeCompare(String(b.cluster_id || ''));
  }).slice(0, limit || 3);
  return list.map(function(item) {
    return item.cluster_phrase + ' (' + item.provider_specificity_score + ')';
  }).join(' | ');
}

function _providerCharacterMicroExpressionAverage_(rows, field) {
  var sum = 0;
  var count = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    var val = _numOrNull_(rows[i] && rows[i][field]);
    if (val != null) {
      sum += Number(val || 0);
      count += 1;
    }
  }
  return count ? (sum / count) : null;
}

function _providerCharacterMicroExpressionPilotResult_(rows, clusters, avgTokenCost, positiveHintCount, negativeHintCount) {
  var rowCount = (rows || []).length;
  var clusterCount = (clusters || []).length;
  if (!rowCount || rowCount < 20 || !clusterCount) {
    return { result: 'extraction_failed', next_step: 'tighten_extraction_rules', note: 'insufficient_rows_or_clusters' };
  }
  if ((avgTokenCost || 0) > 90 || clusterCount < 4 || positiveHintCount + negativeHintCount < 2) {
    return { result: 'weak_do_not_scale', next_step: 'hold_for_review', note: 'generic_or_sparse_patterns' };
  }
  if (positiveHintCount > 0 && negativeHintCount > 0) {
    return { result: 'promising_continue', next_step: 'run_larger_replay_test', note: 'provider-specific recurrence and some separation hints' };
  }
  return { result: 'mixed_continue_cautiously', next_step: 'expand_family_coverage', note: 'patterns exist but economic separation is still tentative' };
}
