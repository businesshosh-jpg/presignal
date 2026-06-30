/*******************************************************
 * provider_character_raw_output_micro_expression_replay.js
 * - Diagnostic-only Provider Character v2 — Raw Output Micro-Expression Replay v1
 * - Replay-only comparison of micro-expressions extracted from
 *   rationale_short, structured compressed fields, and raw_output
 * - No provider calls, no prediction runs, no production changes
 *******************************************************/

function menuBuildProviderCharacterRawOutputMicroExpressionReplay_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterRawOutputMicroExpressionReplay_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character raw output micro-expression replay -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Replay=' + (res.replay_rows_written || 0) +
      ' | Clusters=' + (res.cluster_rows_written || 0) +
      ' | Comparison=' + (res.comparison_rows_written || 0),
      'Provider Character Raw Output Replay',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character raw output micro-expression replay -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterRawOutputMicroExpressionReplay_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _providerCharacterRawOutputReplayLoadSources_(warnings);
  var sampleGuideRows = _providerCharacterRawOutputReplayBuildSampleGuideRows_(sources, warnings);
  var economicCases = _providerCharacterMicroExpressionBuildEconomicCases_(sources.economicBundle, warnings);
  if (!economicCases.length && sources.sampleFallbackBundle) {
    warnings.push('economic_value_accuracy_missing_or_empty');
  }

  var econLookup = _providerCharacterRawOutputReplayBuildCaseLookup_(economicCases);
  var predLookup = _providerCharacterRawOutputReplayBuildPredictionLookup_(sources.predictionsBundle, warnings);
  var residualLookup = _providerCharacterRawOutputReplayBuildResidualLookup_(sources.residualBundle);

  var replayRows = _providerCharacterRawOutputReplayBuildReplayRows_(
    generatedTs,
    sampleGuideRows,
    econLookup,
    predLookup,
    residualLookup,
    warnings
  );
  var clusterRows = _providerCharacterRawOutputReplayBuildClusterRows_(generatedTs, replayRows, warnings);
  var comparisonRows = _providerCharacterRawOutputReplayBuildComparisonRows_(generatedTs, replayRows, clusterRows, warnings);
  var methodologyRows = _providerCharacterRawOutputReplayBuildMethodologyRows_(generatedTs, sources, sampleGuideRows.length, replayRows.length, warnings);

  var replaySheet = getDiagnosticsSheet_('Provider_Character_RawOutput_MicroExpression_Replay', _providerCharacterRawOutputReplayHeaders_(), warnings);
  var comparisonSheet = getDiagnosticsSheet_('Provider_Character_RawOutput_Tier_Comparison', _providerCharacterRawOutputTierComparisonHeaders_(), warnings);
  var clusterSheet = getDiagnosticsSheet_('Provider_Character_RawOutput_Clusters', _providerCharacterRawOutputClusterHeaders_(), warnings);
  var methodologySheet = getDiagnosticsSheet_('Provider_Character_RawOutput_Methodology', _providerCharacterRawOutputMethodologyHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    replaySheet.sheet,
    replaySheet.headers,
    _characterResidualObjectsToRows_(replayRows, replaySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    comparisonSheet.sheet,
    comparisonSheet.headers,
    _characterResidualObjectsToRows_(comparisonRows, comparisonSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    clusterSheet.sheet,
    clusterSheet.headers,
    _characterResidualObjectsToRows_(clusterRows, clusterSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    methodologySheet.sheet,
    methodologySheet.headers,
    _characterResidualObjectsToRows_(methodologyRows, methodologySheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    replay_sheet: replaySheet.sheet.getName(),
    comparison_sheet: comparisonSheet.sheet.getName(),
    cluster_sheet: clusterSheet.sheet.getName(),
    methodology_sheet: methodologySheet.sheet.getName(),
    sampled_events: _providerCharacterRawOutputReplayUniqueEventCount_(replayRows),
    provider_event_rows: replayRows.length,
    replay_rows_written: replayRows.length,
    comparison_rows_written: comparisonRows.length,
    cluster_rows_written: clusterRows.length,
    methodology_rows_written: methodologyRows.length,
    source_tiers_compared: 'rationale_short|structured_compressed_fields|raw_output',
    warnings: _uniqueStrings_(warnings)
  };
}

function buildProviderCharacterRawOutputMicroExpressionReplay() {
  return buildProviderCharacterRawOutputMicroExpressionReplay_();
}

function _providerCharacterRawOutputReplayHeaders_() {
  return [
    'generated_ts',
    'event_id',
    'provider',
    'source_tier',
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
    'source_text_available',
    'source_text_length_chars',
    'primary_focus_phrase',
    'secondary_focus_phrase',
    'ignored_or_discounted_factor_phrase',
    'causal_path_phrase',
    'failure_condition_phrase',
    'confidence_basis_phrase',
    'uncertainty_phrase',
    'expression_summary_phrase',
    'attention_terms',
    'extraction_quality',
    'token_cost_estimate',
    'notes'
  ];
}

function _providerCharacterRawOutputTierComparisonHeaders_() {
  return [
    'generated_ts',
    'provider',
    'source_tier',
    'rows_attempted',
    'rows_extracted',
    'extraction_success_rate',
    'avg_source_text_length_chars',
    'avg_token_cost_estimate',
    'unique_micro_expression_count',
    'cluster_count',
    'provider_specificity_score',
    'avg_economic_dir_ok',
    'avg_forecast_error_abs',
    'better_than_consensus_rate',
    'strongest_expression_clusters',
    'early_positive_economic_hints',
    'early_negative_economic_hints',
    'tier_interpretation',
    'recommended_next_step',
    'notes'
  ];
}

function _providerCharacterRawOutputClusterHeaders_() {
  return [
    'generated_ts',
    'provider',
    'source_tier',
    'cluster_id',
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

function _providerCharacterRawOutputMethodologyHeaders_() {
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
    'source_tiers_compared',
    'token_minimization_rule',
    'interpretation_rule',
    'notes'
  ];
}

function _providerCharacterRawOutputReplayLoadSources_(warnings) {
  return {
    pilotBundle: _characterResidualReadSheetBundle_('Provider_Character_MicroExpression_Pilot', warnings, false),
    residualBundle: _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false),
    economicBundle: _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false),
    predictionsBundle: _characterResidualReadSheetBundle_('Predictions', warnings, false),
    sampleFallbackBundle: null
  };
}

function _providerCharacterRawOutputReplayBuildSampleGuideRows_(sources, warnings) {
  var bundle = sources.pilotBundle || sources.residualBundle || sources.economicBundle;
  var sourceName = bundle === sources.pilotBundle
    ? 'Provider_Character_MicroExpression_Pilot'
    : (bundle === sources.residualBundle ? 'Provider_Character_Residuals' : 'Economic_Value_Accuracy');

  if (!bundle) {
    if (warnings) warnings.push('missing_sample_source');
    return [];
  }

  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var keyed = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (String(row.type || '').trim().toLowerCase() === 'batch') continue;
    if (bundle === sources.economicBundle) {
      if (String(row.row_type || '').trim() !== 'case') continue;
      if (String(row.value_scored_flag || '').trim().toUpperCase() !== 'TRUE') continue;
    }
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || row.ai_name || '').trim();
    if (!eventId || !provider) continue;
    var key = eventId + '|' + provider;
    if (!keyed[key] || _providerCharacterMicroExpressionRowIsNewer_(row, keyed[key])) {
      keyed[key] = row;
    }
  }

  var out = [];
  Object.keys(keyed).sort(function(a, b) {
    var aa = keyed[a] || {};
    var bb = keyed[b] || {};
    if (String(aa.release_ts || '') !== String(bb.release_ts || '')) {
      return String(aa.release_ts || '').localeCompare(String(bb.release_ts || ''));
    }
    return String(a).localeCompare(String(b));
  }).forEach(function(key) {
    var row = keyed[key] || {};
    out.push({
      generated_ts: String(row.generated_ts || row.created_ts || '').trim(),
      event_id: String(row.event_id || '').trim(),
      batch_id: String(row.batch_id || '').trim(),
      type: String(row.type || '').trim(),
      provider: String(row.provider || row.ai_name || '').trim(),
      indicator_name: String(row.indicator_name || '').trim(),
      release_ts: String(row.release_ts || '').trim(),
      outcome_family: String(row.outcome_family || row.family || '').trim() || 'other',
      importance: String(row.importance || '').trim(),
      ai_forecast_value: _providerCharacterRawOutputReplayNumber_(row.ai_forecast_value),
      consensus_value: _providerCharacterRawOutputReplayNumber_(row.consensus_value),
      released_value: _providerCharacterRawOutputReplayNumber_(row.released_value),
      economic_dir_ok: String(row.economic_dir_ok || row.value_dir_ok || '').trim(),
      forecast_error_abs: _providerCharacterRawOutputReplayNumber_(row.forecast_error_abs || row.value_error_abs),
      better_than_consensus: String(row.better_than_consensus || '').trim(),
      sample_source: sourceName,
      residual_match: ''
    });
  });

  if (!out.length && warnings) warnings.push('sample_guide_empty:' + sourceName);
  return out;
}

function _providerCharacterRawOutputReplayBuildCaseLookup_(rows) {
  var map = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (!eventId || !provider) continue;
    var key = eventId + '|' + provider;
    if (!map[key] || _providerCharacterMicroExpressionRowIsNewer_(row, map[key])) {
      map[key] = row;
    }
  }
  return map;
}

function _providerCharacterRawOutputReplayBuildPredictionLookup_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var keyed = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.ai_name || row.provider || '').trim();
    if (!eventId || !provider) continue;
    var key = eventId + '|' + provider;
    if (!keyed[key] || _providerCharacterMicroExpressionRowIsNewer_(row, keyed[key])) {
      keyed[key] = row;
    }
  }

  var map = {};
  Object.keys(keyed).forEach(function(key) {
    map[key] = keyed[key];
  });
  if (!Object.keys(map).length && warnings) warnings.push('prediction_lookup_empty');
  return map;
}

function _providerCharacterRawOutputReplayBuildResidualLookup_(bundle) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var map = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (!eventId || !provider) continue;
    map[eventId + '|' + provider] = row;
  }
  return map;
}

function _providerCharacterRawOutputReplayBuildReplayRows_(generatedTs, sampleGuideRows, econLookup, predLookup, residualLookup, warnings) {
  var rows = [];
  var tierOrder = ['tier_a_short_compressed', 'tier_b_structured_compressed', 'tier_c_raw_output'];
  var providerOrder = { Anthropic: 1, Gemini: 2, OpenAI: 3 };

  var usable = [];
  for (var i = 0; i < (sampleGuideRows || []).length; i++) {
    var guide = sampleGuideRows[i] || {};
    var key = String(guide.event_id || '').trim() + '|' + String(guide.provider || '').trim();
    var econ = econLookup[key] || guide;
    var pred = predLookup[key];
    usable.push({
      guide: guide,
      econ: econ,
      pred: pred || null,
      residual: residualLookup[key] || null,
      key: key
    });
  }

  usable.sort(function(a, b) {
    var ra = a.econ || {};
    var rb = b.econ || {};
    if (String(ra.release_ts || '') !== String(rb.release_ts || '')) {
      return String(ra.release_ts || '').localeCompare(String(rb.release_ts || ''));
    }
    var pa = providerOrder[String(a.guide.provider || '')] || 99;
    var pb = providerOrder[String(b.guide.provider || '')] || 99;
    if (pa !== pb) return pa - pb;
    return String(a.guide.event_id || '').localeCompare(String(b.guide.event_id || ''));
  });

  for (var u = 0; u < usable.length; u++) {
    var item = usable[u];
    for (var t = 0; t < tierOrder.length; t++) {
      rows.push(_providerCharacterRawOutputReplayBuildOneRow_(generatedTs, tierOrder[t], item.guide, item.econ, item.pred, item.residual));
    }
  }

  if (!rows.length && warnings) warnings.push('raw_output_replay_rows_empty');
  return rows;
}

function _providerCharacterRawOutputReplayBuildOneRow_(generatedTs, sourceTier, guideRow, econRow, predRow, residualRow) {
  var extraction = _providerCharacterRawOutputReplayExtract_(sourceTier, predRow || {}, residualRow || {}, econRow || {});
  var sourceText = String(extraction.source_text || '');
  var sourceTextAvailable = sourceText ? 'TRUE' : 'FALSE';
  var sourceTextLengthChars = sourceText ? sourceText.length : 0;
  var tokenCostEstimate = extraction.token_cost_estimate == null ? '' : extraction.token_cost_estimate;
  var sourceMissing = !sourceText;
  var extractionQuality = _providerCharacterRawOutputReplayExtractionQuality_(sourceText, extraction);
  var notesParts = [
    'replay_only',
    'source_tier=' + sourceTier,
    'sample_source=' + String(guideRow.sample_source || ''),
    'residual_match=' + (residualRow ? 'TRUE' : 'FALSE')
  ];
  if (extraction.source_note) notesParts.push(extraction.source_note);

  return {
    generated_ts: generatedTs,
    event_id: String(guideRow.event_id || '').trim(),
    provider: String(guideRow.provider || '').trim(),
    source_tier: sourceTier,
    indicator_name: String((predRow && predRow.indicator_name) || guideRow.indicator_name || '').trim(),
    release_ts: String((predRow && predRow.release_ts) || guideRow.release_ts || '').trim(),
    outcome_family: String((econRow && econRow.outcome_family) || guideRow.outcome_family || 'other').trim() || 'other',
    importance: String((econRow && econRow.importance) || guideRow.importance || '').trim(),
    ai_forecast_value: _providerCharacterRawOutputReplayNumber_(econRow && econRow.ai_forecast_value),
    consensus_value: _providerCharacterRawOutputReplayNumber_(econRow && econRow.consensus_value),
    released_value: _providerCharacterRawOutputReplayNumber_(econRow && econRow.released_value),
    economic_dir_ok: String((econRow && econRow.value_dir_ok) || '').trim(),
    forecast_error_abs: _providerCharacterRawOutputReplayNumber_(econRow && econRow.forecast_error_abs),
    better_than_consensus: _providerCharacterMicroExpressionBetterThanConsensus_(econRow || {}),
    source_text_available: sourceTextAvailable,
    source_text_length_chars: sourceTextLengthChars,
    primary_focus_phrase: extraction.primary_focus_phrase,
    secondary_focus_phrase: extraction.secondary_focus_phrase,
    ignored_or_discounted_factor_phrase: extraction.ignored_or_discounted_factor_phrase,
    causal_path_phrase: extraction.causal_path_phrase,
    failure_condition_phrase: extraction.failure_condition_phrase,
    confidence_basis_phrase: extraction.confidence_basis_phrase,
    uncertainty_phrase: extraction.uncertainty_phrase,
    expression_summary_phrase: extraction.expression_summary_phrase,
    attention_terms: extraction.attention_terms,
    extraction_quality: extractionQuality,
    token_cost_estimate: tokenCostEstimate,
    notes: notesParts.join('; ')
  };
}

function _providerCharacterRawOutputReplayExtract_(sourceTier, predRow, residualRow, econRow) {
  var bundle = _providerCharacterRawOutputReplayBuildTierBundle_(sourceTier, predRow || {}, residualRow || {}, econRow || {});
  if (!bundle.source_text) {
    return {
      source_text: '',
      source_note: 'source_missing',
      primary_focus_phrase: '',
      secondary_focus_phrase: '',
      ignored_or_discounted_factor_phrase: '',
      causal_path_phrase: '',
      failure_condition_phrase: '',
      confidence_basis_phrase: '',
      uncertainty_phrase: '',
      expression_summary_phrase: '',
      attention_terms: '',
      token_cost_estimate: 0
    };
  }

  var primary = _providerCharacterRawOutputReplayPrimaryPhrase_(bundle);
  var secondary = _providerCharacterRawOutputReplaySecondaryPhrase_(bundle, primary);
  var ignored = _providerCharacterRawOutputReplayIgnoredPhrase_(bundle, primary, secondary);
  var causalPath = _providerCharacterRawOutputReplayCausalPath_(bundle, primary, secondary);
  var failureCondition = _providerCharacterRawOutputReplayFailureCondition_(bundle);
  var confidenceBasis = _providerCharacterRawOutputReplayConfidenceBasis_(bundle, econRow);
  var uncertainty = _providerCharacterRawOutputReplayUncertaintyPhrase_(bundle, econRow);
  var summary = _providerCharacterRawOutputReplaySummaryPhrase_(primary, causalPath, uncertainty);
  var attentionTerms = _providerCharacterRawOutputReplayAttentionTerms_(bundle, primary, secondary, causalPath, failureCondition, confidenceBasis, uncertainty);
  var tokenEstimate = _providerCharacterRawOutputReplayTokenEstimate_(bundle, primary, secondary, causalPath, failureCondition, confidenceBasis, uncertainty, summary);

  return {
    source_text: bundle.source_text,
    source_note: bundle.source_note || '',
    primary_focus_phrase: primary,
    secondary_focus_phrase: secondary,
    ignored_or_discounted_factor_phrase: ignored,
    causal_path_phrase: causalPath,
    failure_condition_phrase: failureCondition,
    confidence_basis_phrase: confidenceBasis,
    uncertainty_phrase: uncertainty,
    expression_summary_phrase: summary,
    attention_terms: attentionTerms,
    token_cost_estimate: tokenEstimate
  };
}

function _providerCharacterRawOutputReplayBuildTierBundle_(sourceTier, predRow, residualRow, econRow) {
  var tier = String(sourceTier || '').trim();
  var raw = String((predRow && predRow.raw_output) || '').trim();
  var sourceNote = '';

  if (tier === 'tier_a_short_compressed') {
    var shortText = String((predRow && predRow.rationale_short) || '').trim();
    return {
      source_text: shortText,
      source_note: shortText ? '' : 'rationale_short_missing',
      primary_source: shortText,
      secondary_source: shortText,
      support_text: shortText,
      qualitative_result: String((predRow && predRow.qualitative_result) || '').trim().toLowerCase(),
      parsed: null
    };
  }

  if (tier === 'tier_b_structured_compressed') {
    var partsB = [
      String((predRow && predRow.qualitative_result) || '').trim(),
      String((predRow && predRow.rationale) || '').trim(),
      String((predRow && predRow.attention_primary_factor) || '').trim(),
      String((predRow && predRow.attention_factors) || '').trim(),
      String((predRow && predRow.attention_factor_1) || '').trim(),
      String((predRow && predRow.attention_factor_2) || '').trim(),
      String((predRow && predRow.attention_factor_3) || '').trim(),
      String((predRow && predRow.attention_summary) || '').trim()
    ].filter(function(item) { return !!item; });
    var sourceTextB = partsB.join(' | ');
    return {
      source_text: sourceTextB,
      source_note: sourceTextB ? '' : 'structured_compressed_fields_missing',
      primary_source: String((predRow && predRow.attention_primary_factor) || (predRow && predRow.attention_factor_1) || (predRow && predRow.rationale) || '').trim(),
      secondary_source: String((predRow && predRow.attention_factors) || (predRow && predRow.attention_summary) || (predRow && predRow.rationale) || '').trim(),
      support_text: sourceTextB,
      qualitative_result: String((predRow && predRow.qualitative_result) || '').trim().toLowerCase(),
      parsed: null
    };
  }

  if (tier === 'tier_c_raw_output') {
    if (!raw) {
      return {
        source_text: '',
        source_note: 'raw_output_missing',
        primary_source: '',
        secondary_source: '',
        support_text: '',
        qualitative_result: '',
        parsed: null
      };
    }
    var parsed = _providerCharacterRawOutputReplayParseBlob_(raw);
    var supportParts = [];
    if (parsed) {
      supportParts.push(parsed.rationale_short || '');
      supportParts.push(parsed.rationale || '');
      supportParts.push(parsed.qualitative_result || '');
      supportParts.push(parsed.expected_move_dir || '');
      supportParts.push(parsed.expected_move_pips_min || '');
      supportParts.push(parsed.expected_move_pips_max || '');
      supportParts.push(parsed.expected_holding_minutes || '');
      supportParts.push(parsed.mr_pred_dir || '');
      supportParts.push(parsed.mr_pred_net_pips || '');
      supportParts.push(parsed.mr_pred_strength || '');
      supportParts.push(parsed.mr_pred_sustain_min || '');
      if (parsed.normalization_note) supportParts.push(parsed.normalization_note);
      sourceNote = parsed.normalization_note ? 'normalization_note_stripped=TRUE' : '';
    } else {
      supportParts.push(raw);
      sourceNote = 'raw_output_unparsed';
    }
    var sourceTextC = raw;
    return {
      source_text: sourceTextC,
      source_note: sourceNote,
      primary_source: parsed ? String(parsed.rationale_short || parsed.rationale || parsed.qualitative_result || '').trim() : raw,
      secondary_source: parsed ? String(parsed.rationale || parsed.qualitative_result || parsed.expected_move_dir || '').trim() : raw,
      support_text: supportParts.filter(function(item) { return !!String(item || '').trim(); }).join(' | '),
      qualitative_result: parsed ? String(parsed.qualitative_result || '').trim().toLowerCase() : String((predRow && predRow.qualitative_result) || '').trim().toLowerCase(),
      parsed: parsed
    };
  }

  return {
    source_text: '',
    source_note: 'unknown_source_tier',
    primary_source: '',
    secondary_source: '',
    support_text: '',
    qualitative_result: '',
    parsed: null
  };
}

function _providerCharacterRawOutputReplayPrimaryPhrase_(bundle) {
  var primarySource = String(bundle.primary_source || '').trim();
  var support = String(bundle.support_text || '').trim();
  var primary = _providerCharacterMicroExpressionPhraseFromText_(primarySource, 8);
  if (!primary && bundle.parsed) {
    primary = _providerCharacterMicroExpressionPhraseFromText_(bundle.parsed.rationale_short || bundle.parsed.rationale || bundle.parsed.qualitative_result || support, 8);
  }
  if (!primary) primary = _providerCharacterMicroExpressionPhraseFromText_(support || bundle.source_text || '', 8);
  if (!primary && /consensus|prev revision|surprise|family|signal|rates|yield|usd|fx/.test(String(support || bundle.source_text || '').toLowerCase())) {
    primary = _providerCharacterRawOutputReplayFallbackPhrase_(support || bundle.source_text || '');
  }
  return primary || '';
}

function _providerCharacterRawOutputReplaySecondaryPhrase_(bundle, primaryPhrase) {
  var secondarySource = String(bundle.secondary_source || '').trim();
  var support = String(bundle.support_text || '').trim();
  var secondary = _providerCharacterMicroExpressionPhraseFromText_(secondarySource, 8);
  if (!secondary || secondary === primaryPhrase) {
    secondary = _providerCharacterMicroExpressionPhraseFromText_(support, 8);
  }
  if (!secondary || secondary === primaryPhrase) {
    secondary = _providerCharacterRawOutputReplayFallbackPhrase_(support || bundle.source_text || '');
  }
  return secondary || '';
}

function _providerCharacterRawOutputReplayIgnoredPhrase_(bundle, primaryPhrase, secondaryPhrase) {
  var text = String(bundle.support_text || bundle.source_text || '').toLowerCase();
  var hints = [];
  if (/consensus/.test(text)) hints.push('consensus');
  if (/prev revision|previous value|prior value|revision/.test(text)) hints.push('previous_value');
  if (/surprise history|surprise bias|surprise pattern/.test(text)) hints.push('surprise_history');
  if (/family/.test(text)) hints.push('family_context');
  if (/signal quality|signal/.test(text)) hints.push('signal_quality');
  if (/rate|yield|fed|treasury|policy/.test(text)) hints.push('rates');
  if (/usd\/?jpy|usdjpy|yen/.test(text)) hints.push('usdjpy');
  if (/dxy|dollar index/.test(text)) hints.push('dxy');
  if (/spx|equity/.test(text)) hints.push('spx');
  if (/gold/.test(text)) hints.push('gold');
  if (/wti|oil|crude/.test(text)) hints.push('wti');
  if (/hidden detail|low signal|whipsaw|crowd|crowded|positioning/.test(text)) hints.push('hidden_detail_risk');
  if (!hints.length) return _providerCharacterRawOutputReplayFallbackIgnored_(primaryPhrase, secondaryPhrase);
  var unique = [];
  for (var i = 0; i < hints.length && unique.length < 2; i++) {
    if (unique.indexOf(hints[i]) === -1) unique.push(hints[i]);
  }
  return unique.join(' and ');
}

function _providerCharacterRawOutputReplayFallbackIgnored_(primaryText, secondaryText) {
  var text = String(primaryText || '') + ' ' + String(secondaryText || '');
  var lower = text.toLowerCase();
  if (lower.indexOf('consensus') >= 0) return 'consensus not explicit';
  if (lower.indexOf('rate') >= 0 || lower.indexOf('yield') >= 0) return 'rate path not explicit';
  if (lower.indexOf('usd') >= 0 || lower.indexOf('fx') >= 0) return 'fx channel not explicit';
  if (lower.indexOf('detail') >= 0) return 'minor details not explicit';
  return 'not explicitly referenced';
}

function _providerCharacterRawOutputReplayCausalPath_(bundle, primaryPhrase, secondaryPhrase) {
  var text = String(bundle.support_text || bundle.source_text || '').toLowerCase();
  var path = '';
  if (/\b(inflation|cpi|ppi|prices?|core pce)\b/.test(text)) path = 'surprise moves inflation then yields';
  else if (/\b(labor|employment|payroll|jobs|unemployment|claims|wage)\b/.test(text)) path = 'jobs move wages then rates';
  else if (/\b(housing|mortgage|home|building permits|housing starts)\b/.test(text)) path = 'housing flows into growth then rates';
  else if (/\b(central bank|fomc|fed|rate|rates|yield|treasury|policy)\b/.test(text)) path = 'policy surprise moves yields then USD';
  else if (/\b(consumer|retail|spending|demand|confidence|sentiment)\b/.test(text)) path = 'demand surprise flows into pricing';
  else if (/\b(energy|oil|wti|inventory|crude|gas)\b/.test(text)) path = 'inventory shock moves oil then inflation';
  else if (/\b(usd|usdjpy|dxy|fx|yen)\b/.test(text)) path = 'release moves FX then rates';
  else if (/\b(whipsaw|noise|flat|mixed|uncertain)\b/.test(text)) path = 'signal noise keeps reaction flat';
  if (!path) {
    if (String(primaryPhrase || secondaryPhrase || '').toLowerCase().indexOf('uncertain') >= 0) path = 'uncertainty keeps follow-through limited';
  }
  if (!path) path = 'release moves repricing then follow-through';
  return _providerCharacterMicroExpressionTrimWords_(path, 3, 8);
}

function _providerCharacterRawOutputReplayFailureCondition_(bundle) {
  var text = String(bundle.support_text || bundle.source_text || '').toLowerCase();
  var phrase = '';
  if (text.indexOf('missing consensus') >= 0 || text.indexOf('no consensus') >= 0) phrase = 'missing consensus leaves the read flat';
  else if (text.indexOf('low signal') >= 0 || text.indexOf('weak signal') >= 0) phrase = 'weak signal or noisy release';
  else if (text.indexOf('indirect') >= 0 && text.indexOf('policy') >= 0) phrase = 'policy transmission stays too indirect';
  else if (text.indexOf('ambiguous') >= 0 || text.indexOf('uncertain') >= 0) phrase = 'ambiguity keeps conviction low';
  else if (text.indexOf('flat') >= 0) phrase = 'market treats the print as noise';
  if (!phrase) phrase = 'market treats the print as noise';
  return _providerCharacterMicroExpressionTrimWords_(phrase, 3, 8);
}

function _providerCharacterRawOutputReplayConfidenceBasis_(bundle, econRow) {
  var parts = [];
  var q = String(bundle.qualitative_result || '').trim().toLowerCase();
  if (q === 'stronger') parts.push('directional conviction');
  else if (q === 'weaker') parts.push('cautious conviction');
  else if (q === 'inline') parts.push('flat read');
  if (String(bundle.support_text || '').toLowerCase().indexOf('high confidence') >= 0) parts.push('high confidence');
  if (String(bundle.support_text || '').toLowerCase().indexOf('low confidence') >= 0) parts.push('low confidence');
  if (bundle.parsed && bundle.parsed.mr_pred_strength) parts.push(String(bundle.parsed.mr_pred_strength || '').trim() + ' strength');
  if (!parts.length) parts.push('baseline confidence only');
  return _providerCharacterMicroExpressionTrimWords_(parts.join(', '), 3, 8);
}

function _providerCharacterRawOutputReplayUncertaintyPhrase_(bundle, econRow) {
  var text = String(bundle.support_text || bundle.source_text || '').toLowerCase();
  var q = String(bundle.qualitative_result || '').trim().toLowerCase();
  var phrase = '';
  if (/scenario|if\/then|case|base case|bull case|bear case/.test(text)) phrase = 'scenario framed uncertainty';
  else if (/low signal|thin signal|missing consensus|cold start|partial history|no consensus/.test(text)) phrase = 'low signal and flat';
  else if (/hedged|mixed|offset|both|but|however/.test(text)) phrase = 'mixed signal, split read';
  else if (/cautious|uncertain|limited|maybe|weak|flat|conservative|not enough/.test(text)) phrase = 'cautious, limited conviction';
  else if (/confident|clear|strong|decisive|high confidence/.test(text) || q === 'stronger') phrase = 'clear conviction';
  if (!phrase) phrase = 'uncertainty remains unresolved';
  return _providerCharacterMicroExpressionTrimWords_(phrase, 3, 8);
}

function _providerCharacterRawOutputReplaySummaryPhrase_(primaryPhrase, causalPath, uncertaintyPhrase) {
  var parts = [];
  if (primaryPhrase) parts.push(primaryPhrase);
  if (causalPath) parts.push(causalPath);
  if (uncertaintyPhrase) parts.push(uncertaintyPhrase);
  return _providerCharacterMicroExpressionTrimWords_(parts.join(', '), 3, 8);
}

function _providerCharacterRawOutputReplayAttentionTerms_(bundle, primaryPhrase, secondaryPhrase, causalPath, failureCondition, confidenceBasis, uncertaintyPhrase) {
  var text = [
    primaryPhrase,
    secondaryPhrase,
    causalPath,
    failureCondition,
    confidenceBasis,
    uncertaintyPhrase,
    bundle.support_text || bundle.source_text || ''
  ].join(' ');
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

function _providerCharacterRawOutputReplayTokenEstimate_(bundle, primaryPhrase, secondaryPhrase, causalPath, failureCondition, confidenceBasis, uncertaintyPhrase, summaryPhrase) {
  var text = [
    bundle.source_text || '',
    primaryPhrase,
    secondaryPhrase,
    causalPath,
    failureCondition,
    confidenceBasis,
    uncertaintyPhrase,
    summaryPhrase
  ].join(' ');
  return Math.max(4, _providerCharacterMicroExpressionTokenize_(text).length);
}

function _providerCharacterRawOutputReplayExtractionQuality_(sourceText, extraction) {
  var text = String(sourceText || '').trim();
  if (!text) return 'source_missing';
  var filled = 0;
  [
    extraction.primary_focus_phrase,
    extraction.secondary_focus_phrase,
    extraction.ignored_or_discounted_factor_phrase,
    extraction.causal_path_phrase,
    extraction.failure_condition_phrase,
    extraction.confidence_basis_phrase,
    extraction.uncertainty_phrase,
    extraction.expression_summary_phrase,
    extraction.attention_terms
  ].forEach(function(item) {
    if (String(item || '').trim()) filled += 1;
  });
  if (filled === 0) return 'failed';
  if (filled >= 6 && text.length >= 80) return 'strong';
  if (filled >= 4 || text.length >= 40) return 'usable';
  return 'weak';
}

function _providerCharacterRawOutputReplayBuildClusterRows_(generatedTs, replayRows, warnings) {
  var groups = {};
  for (var i = 0; i < (replayRows || []).length; i++) {
    var row = replayRows[i] || {};
    var provider = String(row.provider || '').trim();
    var sourceTier = String(row.source_tier || '').trim();
    if (!provider || !sourceTier) continue;
    var key = provider + '|' + sourceTier;
    if (!groups[key]) groups[key] = [];
    groups[key].push(row);
  }

  var out = [];
  Object.keys(groups).sort().forEach(function(key) {
    var parts = key.split('|');
    var provider = parts[0] || '';
    var sourceTier = parts[1] || '';
    var groupRows = groups[key] || [];
    var clusterInputRows = groupRows.filter(function(row) {
      var quality = String(row.extraction_quality || '').trim();
      return quality && quality !== 'source_missing' && quality !== 'failed';
    });
    if (!clusterInputRows.length) return;
    var baseClusters = _providerCharacterMicroExpressionBuildClusterRows_(generatedTs, clusterInputRows, warnings);

    for (var i = 0; i < baseClusters.length; i++) {
      var cluster = baseClusters[i] || {};
      out.push({
        generated_ts: generatedTs,
        provider: provider,
        source_tier: sourceTier,
        cluster_id: _providerCharacterRawOutputReplayClusterId_(cluster.cluster_id, sourceTier),
        cluster_phrase: String(cluster.cluster_phrase || '').trim(),
        representative_terms: String(cluster.representative_terms || '').trim(),
        representative_examples: String(cluster.representative_examples || '').trim(),
        row_count: cluster.row_count == null ? '' : cluster.row_count,
        event_count: cluster.event_count == null ? '' : cluster.event_count,
        family_distribution: String(cluster.family_distribution || '').trim(),
        avg_economic_dir_ok: cluster.avg_economic_dir_ok == null ? '' : cluster.avg_economic_dir_ok,
        avg_forecast_error_abs: cluster.avg_forecast_error_abs == null ? '' : cluster.avg_forecast_error_abs,
        better_than_consensus_rate: cluster.better_than_consensus_rate == null ? '' : cluster.better_than_consensus_rate,
        provider_specificity_score: cluster.provider_specificity_score == null ? '' : cluster.provider_specificity_score,
        economic_separation_hint: String(cluster.economic_separation_hint || '').trim(),
        notes: 'source_tier=' + sourceTier + '; ' + String(cluster.notes || '').trim()
      });
    }
  });

  out.sort(function(a, b) {
    if (a.provider !== b.provider) return String(a.provider || '').localeCompare(String(b.provider || ''));
    if (a.source_tier !== b.source_tier) return String(a.source_tier || '').localeCompare(String(b.source_tier || ''));
    var ar = _providerCharacterRawOutputReplayNum_(a.row_count);
    var br = _providerCharacterRawOutputReplayNum_(b.row_count);
    if (br !== ar) return br - ar;
    return String(a.cluster_id || '').localeCompare(String(b.cluster_id || ''));
  });

  if (!out.length && warnings) warnings.push('raw_output_clusters_empty');
  return out;
}

function _providerCharacterRawOutputReplayClusterId_(clusterId, sourceTier) {
  var suffix = 'X';
  if (sourceTier === 'tier_a_short_compressed') suffix = 'A';
  else if (sourceTier === 'tier_b_structured_compressed') suffix = 'B';
  else if (sourceTier === 'tier_c_raw_output') suffix = 'C';
  return String(clusterId || 'cluster') + '_' + suffix;
}

function _providerCharacterRawOutputReplayBuildComparisonRows_(generatedTs, replayRows, clusterRows, warnings) {
  var groups = {};
  for (var i = 0; i < (replayRows || []).length; i++) {
    var row = replayRows[i] || {};
    var provider = String(row.provider || '').trim();
    var sourceTier = String(row.source_tier || '').trim();
    if (!provider || !sourceTier) continue;
    var key = provider + '|' + sourceTier;
    if (!groups[key]) groups[key] = { rows: [], clusters: [] };
    groups[key].rows.push(row);
  }
  for (var j = 0; j < (clusterRows || []).length; j++) {
    var c = clusterRows[j] || {};
    var keyC = String(c.provider || '').trim() + '|' + String(c.source_tier || '').trim();
    if (!groups[keyC]) groups[keyC] = { rows: [], clusters: [] };
    groups[keyC].clusters.push(c);
  }

  var providerTierSummary = {};
  Object.keys(groups).forEach(function(key) {
    var parts = key.split('|');
    var provider = parts[0] || '';
    var tier = parts[1] || '';
    var rows = groups[key].rows || [];
    var clusters = groups[key].clusters || [];
    var summary = _providerCharacterRawOutputReplaySummarizeGroup_(generatedTs, provider, tier, rows, clusters);
    providerTierSummary[key] = summary;
  });

  var out = [];
  Object.keys(providerTierSummary).sort().forEach(function(key) {
    var summary = providerTierSummary[key];
    var provider = summary.provider;
    var tier = summary.source_tier;
    var baselineKey = provider + '|tier_b_structured_compressed';
    var baseline = providerTierSummary[baselineKey] || null;
    var interpretation = _providerCharacterRawOutputReplayTierInterpretation_(summary, baseline, warnings);
    out.push({
      generated_ts: generatedTs,
      provider: provider,
      source_tier: tier,
      rows_attempted: summary.rows_attempted,
      rows_extracted: summary.rows_extracted,
      extraction_success_rate: summary.extraction_success_rate,
      avg_source_text_length_chars: summary.avg_source_text_length_chars,
      avg_token_cost_estimate: summary.avg_token_cost_estimate,
      unique_micro_expression_count: summary.unique_micro_expression_count,
      cluster_count: summary.cluster_count,
      provider_specificity_score: summary.provider_specificity_score,
      avg_economic_dir_ok: summary.avg_economic_dir_ok,
      avg_forecast_error_abs: summary.avg_forecast_error_abs,
      better_than_consensus_rate: summary.better_than_consensus_rate,
      strongest_expression_clusters: summary.strongest_expression_clusters,
      early_positive_economic_hints: summary.early_positive_economic_hints,
      early_negative_economic_hints: summary.early_negative_economic_hints,
      tier_interpretation: interpretation.interpretation,
      recommended_next_step: interpretation.next_step,
      notes: interpretation.note
    });
  });

  if (!out.length && warnings) warnings.push('raw_output_comparison_empty');
  return out;
}

function _providerCharacterRawOutputReplaySummarizeGroup_(generatedTs, provider, sourceTier, rows, clusters) {
  var extracted = [];
  var sourceLengthSum = 0;
  var sourceLengthCount = 0;
  var tokenCostSum = 0;
  var tokenCostCount = 0;
  var econDirSum = 0;
  var econDirCount = 0;
  var errorSum = 0;
  var errorCount = 0;
  var btcSum = 0;
  var btcCount = 0;
  var uniqueExpr = {};
  var extractedCount = 0;

  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (String(row.extraction_quality || '').trim() !== 'source_missing' && String(row.extraction_quality || '').trim() !== 'failed') {
      extractedCount += 1;
    }
    if (String(row.expression_summary_phrase || '').trim()) uniqueExpr[String(row.expression_summary_phrase)] = true;
    if (row.source_text_length_chars !== '' && row.source_text_length_chars != null) {
      sourceLengthSum += Number(row.source_text_length_chars || 0);
      sourceLengthCount += 1;
    }
    if (row.token_cost_estimate !== '' && row.token_cost_estimate != null) {
      tokenCostSum += Number(row.token_cost_estimate || 0);
      tokenCostCount += 1;
    }
    var dir = _providerCharacterRawOutputReplayBoolScore_(row.economic_dir_ok);
    if (dir != null) {
      econDirSum += dir;
      econDirCount += 1;
    }
    var err = _providerCharacterRawOutputReplayNum_(row.forecast_error_abs);
    if (err != null) {
      errorSum += err;
      errorCount += 1;
    }
    var btc = _providerCharacterRawOutputReplayBoolScore_(row.better_than_consensus);
    if (btc != null) {
      btcSum += btc;
      btcCount += 1;
    }
  }

  var rowsAttempted = (rows || []).length;
  var rowsExtracted = extractedCount;
  var extractionSuccessRate = rowsAttempted ? _round4_(rowsExtracted / rowsAttempted) : '';
  var avgSourceLength = sourceLengthCount ? _round4_(sourceLengthSum / sourceLengthCount) : '';
  var avgTokenCost = tokenCostCount ? _round4_(tokenCostSum / tokenCostCount) : '';
  var avgDir = econDirCount ? _round4_(econDirSum / econDirCount) : '';
  var avgErr = errorCount ? _round4_(errorSum / errorCount) : '';
  var avgBtc = btcCount ? _round4_(btcSum / btcCount) : '';
  var clusterCount = (clusters || []).length;
  var specificity = _providerCharacterRawOutputReplayWeightedSpecificity_(clusters);
  var strongestClusters = _providerCharacterMicroExpressionTopClusterText_(clusters, 3);
  var positiveHints = _providerCharacterRawOutputReplayClusterHintText_(clusters, true);
  var negativeHints = _providerCharacterRawOutputReplayClusterHintText_(clusters, false);

  return {
    generated_ts: generatedTs,
    provider: provider,
    source_tier: sourceTier,
    rows_attempted: rowsAttempted,
    rows_extracted: rowsExtracted,
    extraction_success_rate: extractionSuccessRate,
    avg_source_text_length_chars: avgSourceLength,
    avg_token_cost_estimate: avgTokenCost,
    unique_micro_expression_count: Object.keys(uniqueExpr).length,
    cluster_count: clusterCount,
    provider_specificity_score: specificity == null ? '' : _round4_(specificity),
    avg_economic_dir_ok: avgDir,
    avg_forecast_error_abs: avgErr,
    better_than_consensus_rate: avgBtc,
    strongest_expression_clusters: strongestClusters,
    early_positive_economic_hints: positiveHints,
    early_negative_economic_hints: negativeHints
  };
}

function _providerCharacterRawOutputReplayTierInterpretation_(summary, baseline, warnings) {
  var tier = String(summary.source_tier || '').trim();
  if (tier === 'tier_a_short_compressed') {
    return {
      interpretation: 'short_compressed_baseline',
      next_step: 'monitor_only',
      note: 'tier_a_short_compressed used as minimal baseline'
    };
  }
  if (tier === 'tier_b_structured_compressed') {
    return {
      interpretation: 'structured_compressed_reference',
      next_step: 'use_as_compressed_baseline',
      note: 'tier_b_structured_compressed used as structured baseline'
    };
  }

  if (!baseline) {
    return {
      interpretation: 'inconclusive',
      next_step: 'monitor_more_data',
      note: 'structured baseline missing for raw_output comparison'
    };
  }

  var raw = summary || {};
  var base = baseline || {};
  var positive = 0;
  var negative = 0;

  var successDelta = _providerCharacterRawOutputReplaySignedDelta_(raw.extraction_success_rate, base.extraction_success_rate);
  if (successDelta > 0.05) positive += 1;
  else if (successDelta < -0.05) negative += 1;

  var uniqueDelta = _providerCharacterRawOutputReplaySignedDelta_(raw.unique_micro_expression_count, base.unique_micro_expression_count);
  if (uniqueDelta > 5) positive += 1;
  else if (uniqueDelta < -5) negative += 1;

  var clusterDelta = _providerCharacterRawOutputReplaySignedDelta_(raw.cluster_count, base.cluster_count);
  if (clusterDelta > 1) positive += 1;
  else if (clusterDelta < -1) negative += 1;

  var specDelta = _providerCharacterRawOutputReplaySignedDelta_(raw.provider_specificity_score, base.provider_specificity_score);
  if (specDelta > 0.05) positive += 1;
  else if (specDelta < -0.05) negative += 1;

  var btcDelta = _providerCharacterRawOutputReplaySignedDelta_(raw.better_than_consensus_rate, base.better_than_consensus_rate);
  if (btcDelta > 0.02) positive += 1;
  else if (btcDelta < -0.02) negative += 1;

  var errDelta = _providerCharacterRawOutputReplaySignedDelta_(base.avg_forecast_error_abs, raw.avg_forecast_error_abs);
  if (errDelta > 0.05) positive += 1;
  else if (errDelta < -0.05) negative += 1;

  if (positive >= 3 && negative <= 1) {
    return {
      interpretation: 'raw_output_richer',
      next_step: 'extend_raw_output_replay',
      note: 'raw_output shows stronger extraction or separation than compressed baseline'
    };
  }
  if (negative >= 3) {
    return {
      interpretation: 'raw_output_noisier',
      next_step: 'compressed_fields_sufficient',
      note: 'raw_output underperforms structured compressed baseline'
    };
  }
  if (Math.abs(successDelta) <= 0.05 && Math.abs(uniqueDelta) <= 5 && Math.abs(clusterDelta) <= 1 && Math.abs(specDelta) <= 0.05) {
    return {
      interpretation: 'raw_output_similar',
      next_step: 'use_both_tiers',
      note: 'raw_output and structured compressed fields look broadly similar'
    };
  }
  return {
    interpretation: 'inconclusive',
    next_step: 'monitor_more_data',
    note: 'raw_output differences are not decisive'
  };
}

function _providerCharacterRawOutputReplayWeightedSpecificity_(clusters) {
  var sum = 0;
  var weight = 0;
  for (var i = 0; i < (clusters || []).length; i++) {
    var row = clusters[i] || {};
    var spec = _providerCharacterRawOutputReplayNum_(row.provider_specificity_score);
    var rows = _providerCharacterRawOutputReplayNum_(row.row_count);
    if (spec == null || rows == null) continue;
    sum += spec * rows;
    weight += rows;
  }
  return weight ? (sum / weight) : null;
}

function _providerCharacterRawOutputReplayClusterHintText_(clusters, positive) {
  var hints = [];
  for (var i = 0; i < (clusters || []).length; i++) {
    var row = clusters[i] || {};
    var hint = String(row.economic_separation_hint || '').toLowerCase();
    if (!hint) continue;
    var isPositive = hint.indexOf('higher dir ok') >= 0 || hint.indexOf('lower error') >= 0 || hint.indexOf('higher better-than-consensus') >= 0;
    var isNegative = hint.indexOf('lower dir ok') >= 0 || hint.indexOf('higher error') >= 0 || hint.indexOf('lower better-than-consensus') >= 0;
    if (positive && isPositive) hints.push(row.cluster_phrase + ' (' + row.economic_separation_hint + ')');
    if (!positive && isNegative) hints.push(row.cluster_phrase + ' (' + row.economic_separation_hint + ')');
  }
  return hints.slice(0, 3).join(' | ');
}

function _providerCharacterRawOutputReplayParseBlob_(rawText) {
  var text = String(rawText || '').trim();
  if (!text) return null;

  var note = '';
  var csvText = text;
  var noteMarker = ' normalization_note=';
  var noteIdx = text.indexOf(noteMarker);
  if (noteIdx >= 0) {
    csvText = text.slice(0, noteIdx);
    note = text.slice(noteIdx + 1);
  }

  var values = null;
  if (csvText.indexOf(',') >= 0) {
    values = _providerCharacterRawOutputReplayCsvSplit_(csvText);
  }

  if (values && values.length) {
    var keys = [
      'object',
      'event_id',
      'type',
      'ai_forecast_value',
      'qualitative_result',
      'mr_window_min',
      'mr_pred_dir',
      'mr_pred_net_pips',
      'mr_pred_strength',
      'mr_pred_sustain_min',
      'expected_move_dir',
      'expected_move_pips_min',
      'expected_move_pips_max',
      'expected_holding_minutes',
      'rationale_short',
      'rationale'
    ];
    var out = {};
    for (var i = 0; i < keys.length; i++) {
      out[keys[i]] = i < values.length ? String(values[i] || '').trim() : '';
    }
    if (note) out.normalization_note = note;
    return out;
  }

  return {
    raw_text: text,
    normalization_note: note
  };
}

function _providerCharacterRawOutputReplayCsvSplit_(text) {
  var out = [];
  var cell = '';
  var inQuotes = false;
  var s = String(text || '');
  for (var i = 0; i < s.length; i++) {
    var ch = s.charAt(i);
    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < s.length && s.charAt(i + 1) === '"') {
          cell += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        cell += ch;
      }
    } else {
      if (ch === ',') {
        out.push(cell);
        cell = '';
      } else if (ch === '"') {
        inQuotes = true;
      } else {
        cell += ch;
      }
    }
  }
  out.push(cell);
  return out;
}

function _providerCharacterRawOutputReplayFallbackPhrase_(text) {
  return _providerCharacterMicroExpressionTrimWords_(String(text || ''), 3, 8);
}

function _providerCharacterRawOutputReplayBoolScore_(value) {
  var s = String(value == null ? '' : value).trim().toLowerCase();
  if (!s) return null;
  if (s === 'true' || s === '1' || s === 'yes' || s === 'ok' || s === 'y') return 1;
  if (s === 'false' || s === '0' || s === 'no' || s === 'bad' || s === 'fail') return 0;
  return null;
}

function _providerCharacterRawOutputReplayNum_(value) {
  if (value === null || value === undefined || value === '') return null;
  var n = Number(value);
  return isFinite(n) ? n : null;
}

function _providerCharacterRawOutputReplayNumber_(value) {
  var n = _providerCharacterRawOutputReplayNum_(value);
  return n == null ? '' : n;
}

function _providerCharacterRawOutputReplaySignedDelta_(a, b) {
  var aa = _providerCharacterRawOutputReplayNum_(a);
  var bb = _providerCharacterRawOutputReplayNum_(b);
  if (aa == null || bb == null) return 0;
  return aa - bb;
}

function _providerCharacterRawOutputReplayUniqueEventCount_(rows) {
  var seen = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (!String(row.event_id || '').trim()) continue;
    seen[String(row.event_id || '').trim()] = true;
  }
  return Object.keys(seen).length;
}

function _providerCharacterRawOutputReplayBuildMethodologyRows_(generatedTs, sources, sampledEventCount, rowCount, warnings) {
  var used = [
    sources.pilotBundle ? 'Provider_Character_MicroExpression_Pilot' : '',
    sources.residualBundle ? 'Provider_Character_Residuals' : '',
    sources.economicBundle ? 'Economic_Value_Accuracy' : '',
    sources.predictionsBundle ? 'Predictions' : ''
  ].filter(function(item) { return !!item; }).join('|');

  return [{
    generated_ts: generatedTs,
    experiment_name: 'Provider Character v2 — Raw Output Micro-Expression Replay v1',
    branch_name: 'Provider Character v2 / Raw Expression Candidate Branch',
    purpose: 'Replay-only comparison of raw_output against compressed prediction fields.',
    sample_strategy: 'Reuse the existing micro-expression pilot sample rows and join to Predictions plus Economic_Value_Accuracy.',
    provider_calls_made: 'FALSE',
    prediction_runs_made: 'FALSE',
    production_changes: 'FALSE',
    source_sheets_used: used,
    source_tiers_compared: 'rationale_short|structured_compressed_fields|raw_output',
    token_minimization_rule: '3–8 words per micro-expression field; no long rationale; no predefined labels',
    interpretation_rule: 'Raw output is a replay-only diagnostic source. Do not claim causation, production improvement, or calibration approval.',
    notes: 'sampled_events=' + sampledEventCount + '; provider_event_rows=' + rowCount + '; warnings=' + String((warnings || []).length)
  }];
}
