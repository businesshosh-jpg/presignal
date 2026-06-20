/*******************************************************
 * provider_character_outcome_layer_audit.js
 * - Diagnostic-only Provider Character Outcome-Layer Audit v1
 * - Classifies character / signal experiments by outcome layer
 * - Rebuilds audit, rebuild-plan, translation, and methodology sheets
 *   without changing live prediction behavior
 *******************************************************/

function menuBuildProviderCharacterOutcomeLayerAudit_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterOutcomeLayerAudit_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character outcome-layer audit -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Audit=' + (res.audit_rows_written || 0) +
      ' | Rebuild=' + (res.rebuild_rows_written || 0) +
      ' | Translation=' + (res.translation_rows_written || 0),
      'Provider Character Outcome-Layer Audit',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character outcome-layer audit -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterOutcomeLayerAudit_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var specs = _providerCharacterOutcomeLayerAuditSpecs_(warnings);
  var auditRows = [];
  for (var i = 0; i < specs.length; i++) {
    auditRows.push(_providerCharacterOutcomeLayerAuditRow_(generatedTs, specs[i], warnings));
  }

  var rebuildRows = _providerCharacterEconomicRebuildPlanRows_(generatedTs, auditRows, warnings);
  var translationRows = _providerCharacterTranslationReinterpretationRows_(generatedTs, auditRows, warnings);
  var summaryRows = _providerCharacterMethodologySummaryRows_(generatedTs, auditRows, rebuildRows, translationRows);

  var auditSheet = getDiagnosticsSheet_('Provider_Character_Outcome_Layer_Audit', _providerCharacterOutcomeLayerAuditHeaders_(), warnings);
  var rebuildSheet = getDiagnosticsSheet_('Provider_Character_Economic_Rebuild_Plan', _providerCharacterEconomicRebuildPlanHeaders_(), warnings);
  var translationSheet = getDiagnosticsSheet_('Provider_Character_Translation_Reinterpretation', _providerCharacterTranslationReinterpretationHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Provider_Character_Methodology_Summary', _providerCharacterMethodologySummaryHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(auditSheet.sheet, auditSheet.headers, _providerCharacterObjectsToRows_(auditRows, auditSheet.headers));
  _rewriteSheetRowsPreservingHeaders_(rebuildSheet.sheet, rebuildSheet.headers, _providerCharacterObjectsToRows_(rebuildRows, rebuildSheet.headers));
  _rewriteSheetRowsPreservingHeaders_(translationSheet.sheet, translationSheet.headers, _providerCharacterObjectsToRows_(translationRows, translationSheet.headers));
  _rewriteSheetRowsPreservingHeaders_(summarySheet.sheet, summarySheet.headers, _providerCharacterObjectsToRows_(summaryRows, summarySheet.headers));

  return {
    status: 'ok',
    generated_ts: generatedTs,
    audit_sheet: auditSheet.sheet.getName(),
    rebuild_sheet: rebuildSheet.sheet.getName(),
    translation_sheet: translationSheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    audit_rows_written: auditRows.length,
    rebuild_rows_written: rebuildRows.length,
    translation_rows_written: translationRows.length,
    summary_rows_written: summaryRows.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function buildProviderCharacterOutcomeLayerAudit() {
  return buildProviderCharacterOutcomeLayerAudit_();
}

function buildProviderCharacterEconomicRebuildPlan_() {
  return buildProviderCharacterOutcomeLayerAudit_();
}

function buildProviderCharacterTranslationReinterpretation_() {
  return buildProviderCharacterOutcomeLayerAudit_();
}

function buildProviderCharacterMethodologySummary_() {
  return buildProviderCharacterOutcomeLayerAudit_();
}

function _providerCharacterOutcomeLayerAuditHeaders_() {
  return [
    'generated_ts',
    'experiment_name',
    'sheet_name',
    'builder_function_name',
    'source_sheets_used',
    'outcome_fields_used',
    'economic_value_fields_used',
    'market_reaction_fields_used',
    'classification',
    'methodological_risk',
    'prior_conclusion_status',
    'required_action',
    'notes'
  ];
}

function _providerCharacterEconomicRebuildPlanHeaders_() {
  return [
    'generated_ts',
    'original_experiment_name',
    'original_sheet_name',
    'current_outcome_layer',
    'target_outcome_layer',
    'required_source_sheets',
    'required_economic_fields',
    'missing_required_fields',
    'rebuild_priority',
    'recommended_new_sheet_name',
    'recommended_builder_name',
    'expected_question_answered',
    'notes'
  ];
}

function _providerCharacterTranslationReinterpretationHeaders_() {
  return [
    'generated_ts',
    'original_experiment_name',
    'provider',
    'trait',
    'original_result',
    'original_outcome_metric',
    'corrected_interpretation',
    'valid_as_economic_character_signal',
    'valid_as_market_translation_signal',
    'notes'
  ];
}

function _providerCharacterMethodologySummaryHeaders_() {
  return [
    'generated_ts',
    'total_character_experiments_reviewed',
    'economic_value_layer_count',
    'market_reaction_layer_count',
    'mixed_layer_count',
    'unclear_layer_count',
    'experiments_needing_rebuild_count',
    'experiments_valid_as_translation_count',
    'experiments_remaining_valid_count',
    'highest_priority_rebuilds',
    'main_methodology_warning',
    'recommended_next_step'
  ];
}

function _providerCharacterOutcomeLayerAuditSpecs_(warnings) {
  var econResidualFields = [
    'ai_forecast_value',
    'consensus_value',
    'prev_revision',
    'released_value',
    'forecast_error_abs',
    'forecast_error_pct',
    'forecast_dir_ok',
    'economic_direction_ok',
    'economic_surprise_direction_ok',
    'baseline_value',
    'actual_value',
    'value_delta_from_baseline',
    'abs_value_delta_from_baseline',
    'direction_delta_from_baseline'
  ];
  var marketOutcomeFields = [
    'mr_pred_dir',
    'mr_pred_net_pips',
    'mr_pred_strength',
    'mr_pred_sustain_min',
    'mr_real_dir',
    'mr_real_strength',
    'mr_real_sustain_min',
    'realized_pips',
    'mr_dir_ok',
    'mr_strength_ok',
    'mr_sustain_ok',
    'overall_ok',
    'outcome_score'
  ];
  var marketSummaryFields = [
    'overall_ok_rate',
    'dir_ok_rate',
    'strength_ok_rate',
    'sustain_ok_rate',
    'avg_outcome_score',
    'score_delta'
  ];
  var marketRecurrenceFields = [
    'discovery_overall_ok_rate',
    'discovery_dir_ok_rate',
    'discovery_strength_ok_rate',
    'discovery_sustain_ok_rate',
    'discovery_avg_outcome_score',
    'validation_overall_ok_rate',
    'validation_dir_ok_rate',
    'validation_strength_ok_rate',
    'validation_sustain_ok_rate',
    'validation_avg_outcome_score',
    'recurrence_score',
    'recurrence_classification',
    'profile_similarity_score',
    'sign_stability',
    'effect_size_stability',
    'drift_classification'
  ];
  var marketSignalFields = [
    'recurrence_score',
    'outcome_link_status',
    'falsification_status',
    'drift_status',
    'profile_similarity_score',
    'discovery_score_delta',
    'validation_score_delta',
    'effect_direction',
    'effect_size_stability',
    'candidate_status',
    'readiness_classification'
  ];
  var shadowEconFields = [
    'economic_value_accuracy_present_rate',
    'economic_value_accuracy_absent_rate',
    'economic_value_accuracy_delta'
  ];
  var shadowMarketFields = [
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
    'sustain_ok_delta'
  ];

  var commonResidualSources = ['Predictions', 'Event', 'Feature_Pack_Audit', 'Feature_Pack_v2B_Core_Audit'];
  var commonOutcomeSources = ['Outcome_Ledger', 'Provider_Character_Residuals', 'Character_Recurrence_Validation'];
  var commonFalsificationSources = ['Character_Outcome_Link', 'Character_Recurrence_Validation', 'Outcome_Ledger', 'Provider_Character_Residuals'];
  var commonRecurrenceDriftSources = ['Character_Outcome_Falsification_Report', 'Character_Outcome_Link', 'Outcome_Ledger', 'Provider_Character_Residuals'];
  var commonCandidateSources = [
    'Character_Outcome_Falsification_Report',
    'Character_Outcome_Recurrence_Validation',
    'Character_Outcome_Recurrence_Interpretation',
    'Character_Outcome_Link',
    'Character_Outcome_Family_Link',
    'Character_Recurrence_Family_Validation',
    'Character_Drift_Assessment',
    'Provider_Character_Summary',
    'Provider_Character_Family_Summary',
    'Character_Outcome_Robust_Traits'
  ];
  var commonShadowSources = [
    'Character_Signal_Candidates',
    'Character_Signal_Readiness_Report',
    'Provider_Character_Residuals',
    'Outcome_Ledger',
    'Economic_Value_Accuracy',
    'Provider_Family_Economic_Accuracy',
    'Evaluation_Rows',
    'Character_Outcome_Recurrence_Validation',
    'Character_Outcome_Recurrence_Interpretation',
    'Character_Drift_Assessment',
    'Character_Outcome_Falsification_Report',
    'Character_Signal_Candidate_Summary'
  ];

  var specs = [];
  _providerCharacterOutcomeLayerAuditExpandGroup_(
    specs,
    [
      { sheet_name: 'Character_Baseline_E', experiment_name: 'Character baseline economic layer' },
      { sheet_name: 'Provider_Character_Residuals', experiment_name: 'Provider character residuals' },
      { sheet_name: 'Provider_Character_Summary', experiment_name: 'Provider character summary' },
      { sheet_name: 'Provider_Character_Family_Summary', experiment_name: 'Provider character family summary' },
      { sheet_name: 'Character_Disagreement_Report', experiment_name: 'Character disagreement report' }
    ],
    {
      builder_function_name: 'buildCharacterResidualArchitecture_',
      source_sheets_used: commonResidualSources,
      economic_value_fields_used: econResidualFields,
      market_reaction_fields_used: [],
      classification: 'economic_value_layer',
      methodological_risk: 'clean',
      prior_conclusion_status: 'remains_valid',
      required_action: 'no_action',
      rebuild_priority: 'not_needed',
      expected_question_answered: 'Does provider character explain pre-market economic-value accuracy rather than downstream market reaction?',
      notes: 'Economic-value residual architecture; clean basis for character-vs-actual economic claims.'
    },
    warnings
  );
  _providerCharacterOutcomeLayerAuditExpandGroup_(
    specs,
    [
      { sheet_name: 'Character_Recurrence_Validation', experiment_name: 'Character recurrence validation' },
      { sheet_name: 'Character_Recurrence_Family_Validation', experiment_name: 'Character recurrence family validation' }
    ],
    {
      builder_function_name: 'buildCharacterRecurrenceValidation_',
      source_sheets_used: ['Provider_Character_Residuals', 'Predictions', 'Event', 'Feature_Pack_Audit', 'Feature_Pack_v2B_Core_Audit'],
      economic_value_fields_used: [],
      market_reaction_fields_used: [],
      classification: 'unclear_layer',
      methodological_risk: 'unknown',
      prior_conclusion_status: 'inconclusive_until_rebuilt',
      required_action: 'investigate_manually',
      rebuild_priority: 'not_needed',
      expected_question_answered: 'Does the character signature recur across independent blocks, regardless of outcome layer?',
      notes: 'Recurrence / reliability diagnostic; useful for stability, but no explicit outcome target is tested.'
    },
    warnings
  );
  _providerCharacterOutcomeLayerAuditExpandGroup_(
    specs,
    [
      { sheet_name: 'Provider_Character_Diagnostics', experiment_name: 'Provider character diagnostics' }
    ],
    {
      builder_function_name: 'buildProviderCharacterDiagnostics_',
      source_sheets_used: ['Outcome_Ledger'],
      economic_value_fields_used: [],
      market_reaction_fields_used: ['rows_scored', 'overall_ok', 'mr_dir_ok', 'outcome_score', 'mr_pred_dir', 'mr_pred_strength'],
      classification: 'market_reaction_layer',
      methodological_risk: 'acceptable_if_translation_experiment',
      prior_conclusion_status: 'valid_only_as_market_translation_result',
      required_action: 'relabel_as_market_translation',
      rebuild_priority: 'medium',
      expected_question_answered: 'Does provider character explain downstream market-reaction differences?',
      notes: 'Attention-era provider diagnostics built from Outcome_Ledger scored rows.'
    },
    warnings
  );
  _providerCharacterOutcomeLayerAuditExpandGroup_(
    specs,
    [
      { sheet_name: 'Character_Outcome_Link', experiment_name: 'Character outcome link' },
      { sheet_name: 'Character_Outcome_Summary', experiment_name: 'Character outcome summary' },
      { sheet_name: 'Character_Outcome_Family_Link', experiment_name: 'Character outcome family link' }
    ],
    {
      builder_function_name: 'buildCharacterOutcomeLink_',
      source_sheets_used: ['Outcome_Ledger', 'Provider_Character_Residuals', 'Character_Recurrence_Validation', 'Economic_Value_Accuracy'],
      economic_value_fields_used: [],
      market_reaction_fields_used: marketSummaryFields,
      classification: 'market_reaction_layer',
      methodological_risk: 'acceptable_if_translation_experiment',
      prior_conclusion_status: 'valid_only_as_market_translation_result',
      required_action: 'relabel_as_market_translation',
      rebuild_priority: 'high',
      expected_question_answered: 'Does the trait predict USDJPY market reaction after release?',
      notes: 'Core character-to-outcome linkage, but the outcome target is downstream reaction, not economic value.'
    },
    warnings
  );
  _providerCharacterOutcomeLayerAuditExpandGroup_(
    specs,
    [
      { sheet_name: 'Character_Outcome_Provider_Controlled', experiment_name: 'Character outcome provider controlled' },
      { sheet_name: 'Character_Outcome_Family_Controlled', experiment_name: 'Character outcome family controlled' },
      { sheet_name: 'Character_Outcome_Permutation_Test', experiment_name: 'Character outcome permutation test' },
      { sheet_name: 'Character_Outcome_Robust_Traits', experiment_name: 'Character outcome robust traits' },
      { sheet_name: 'Character_Good_Reasoning_Proxy_Test', experiment_name: 'Character good reasoning proxy test' },
      { sheet_name: 'Character_Outcome_Falsification_Report', experiment_name: 'Character outcome falsification report' }
    ],
    {
      builder_function_name: 'buildCharacterOutcomeFalsification_',
      source_sheets_used: commonFalsificationSources,
      economic_value_fields_used: [],
      market_reaction_fields_used: [
        'present_overall_ok_rate',
        'absent_overall_ok_rate',
        'present_dir_ok_rate',
        'absent_dir_ok_rate',
        'present_strength_ok_rate',
        'absent_strength_ok_rate',
        'present_sustain_ok_rate',
        'absent_sustain_ok_rate',
        'present_avg_outcome_score',
        'absent_avg_outcome_score',
        'overall_delta',
        'dir_delta',
        'strength_delta',
        'sustain_delta',
        'score_delta',
        'permutation_result',
        'proxy_test_result',
        'falsification_status'
      ],
      classification: 'market_reaction_layer',
      methodological_risk: 'acceptable_if_translation_experiment',
      prior_conclusion_status: 'valid_only_as_market_translation_result',
      required_action: 'relabel_as_market_translation',
      rebuild_priority: 'high',
      expected_question_answered: 'Does provider character survive falsification when the target is downstream market reaction?',
      notes: 'Validation and falsification remain useful, but they speak to translation behavior unless rebuilt on economic value.'
    },
    warnings
  );
  _providerCharacterOutcomeLayerAuditExpandGroup_(
    specs,
    [
      { sheet_name: 'Character_Outcome_Recurrence_Validation', experiment_name: 'Character outcome recurrence validation' },
      { sheet_name: 'Character_Drift_Assessment', experiment_name: 'Character drift assessment' },
      { sheet_name: 'Character_Outcome_Recurrence_Block_Detail', experiment_name: 'Character outcome recurrence block detail' },
      { sheet_name: 'Character_Outcome_Recurrence_Interpretation', experiment_name: 'Character outcome recurrence interpretation' }
    ],
    {
      builder_function_name: 'buildCharacterOutcomeRecurrenceDriftValidation_',
      source_sheets_used: commonRecurrenceDriftSources,
      economic_value_fields_used: [],
      market_reaction_fields_used: marketRecurrenceFields,
      classification: 'market_reaction_layer',
      methodological_risk: 'acceptable_if_translation_experiment',
      prior_conclusion_status: 'valid_only_as_market_translation_result',
      required_action: 'relabel_as_market_translation',
      rebuild_priority: 'medium',
      expected_question_answered: 'Does character recurrence and drift track downstream market-reaction scoring?',
      notes: 'Recurrence and drift are useful stability diagnostics, but the outcomes are still market-reaction based.'
    },
    warnings
  );
  _providerCharacterOutcomeLayerAuditExpandGroup_(
    specs,
    [
      { sheet_name: 'Character_Signal_Candidates', experiment_name: 'Character signal candidates' },
      { sheet_name: 'Character_Signal_Candidate_Summary', experiment_name: 'Character signal candidate summary' },
      { sheet_name: 'Character_Signal_Candidate_Family_Map', experiment_name: 'Character signal candidate family map' },
      { sheet_name: 'Character_Signal_Readiness_Report', experiment_name: 'Character signal readiness report' }
    ],
    {
      builder_function_name: 'buildCharacterSignalCandidateLayer_',
      source_sheets_used: commonCandidateSources,
      economic_value_fields_used: [],
      market_reaction_fields_used: marketSignalFields,
      classification: 'market_reaction_layer',
      methodological_risk: 'acceptable_if_translation_experiment',
      prior_conclusion_status: 'valid_only_as_market_translation_result',
      required_action: 'relabel_as_market_translation',
      rebuild_priority: 'medium',
      expected_question_answered: 'Does provider character separate better and worse market-reaction translation candidates?',
      notes: 'Candidate and readiness layers are bridge diagnostics; they do not establish economic-value character on their own.'
    },
    warnings
  );
  _providerCharacterOutcomeLayerAuditExpandGroup_(
    specs,
    [
      { sheet_name: 'Character_Signal_Shadow_Test', experiment_name: 'Character signal shadow test' },
      { sheet_name: 'Character_Signal_Shadow_Family_Test', experiment_name: 'Character signal shadow family test' },
      { sheet_name: 'Character_Signal_Shadow_Summary', experiment_name: 'Character signal shadow summary' },
      { sheet_name: 'Character_Signal_Shadow_Readiness', experiment_name: 'Character signal shadow readiness' }
    ],
    {
      builder_function_name: 'buildCharacterSignalShadowTest_',
      source_sheets_used: commonShadowSources,
      economic_value_fields_used: shadowEconFields,
      market_reaction_fields_used: shadowMarketFields,
      classification: 'mixed_layer',
      methodological_risk: 'risky_for_character_economic_claims',
      prior_conclusion_status: 'needs_rebuild_against_economic_value',
      required_action: 'split_economic_vs_market_versions',
      rebuild_priority: 'high',
      expected_question_answered: 'Does the signal candidate remain predictive when the target is individual event value before market reaction, and how much of the signal is only translation behavior?',
      notes: 'This is the clearest mixed layer: economic-value and market-reaction metrics are both present and must be separated for causal interpretation.'
    },
    warnings
  );

  return specs;
}

function _providerCharacterOutcomeLayerAuditExpandGroup_(specs, sheetEntries, common, warnings) {
  for (var i = 0; i < (sheetEntries || []).length; i++) {
    var entry = sheetEntries[i] || {};
    var spec = {};
    Object.keys(common || {}).forEach(function(key) {
      spec[key] = Array.isArray(common[key]) ? common[key].slice() : common[key];
    });
    Object.keys(entry || {}).forEach(function(key) {
      spec[key] = entry[key];
    });
    specs.push(spec);
  }
  return specs;
}

function _providerCharacterOutcomeLayerAuditRow_(generatedTs, spec, warnings) {
  var sheetName = String(spec.sheet_name || '').trim();
  var classification = String(spec.classification || 'unclear_layer').trim();
  var economicFields = spec.economic_value_fields_used || [];
  var marketFields = spec.market_reaction_fields_used || [];
  var sourceSheets = spec.source_sheets_used || [];
  var actualSources = [];
  var missingSources = [];

  for (var i = 0; i < sourceSheets.length; i++) {
    var source = String(sourceSheets[i] || '').trim();
    if (!source) continue;
    actualSources.push(source);
    var ref = typeof findSheetAcrossKnownWorkbooks_ === 'function' ? findSheetAcrossKnownWorkbooks_(source) : null;
    if (!ref || !ref.found) missingSources.push(source);
  }

  var notes = [
    String(spec.notes || '').trim(),
    missingSources.length ? 'missing_source_sheets=' + missingSources.join('|') : '',
    sheetName ? 'sheet_present=' + (_providerCharacterOutcomeLayerAuditSheetPresent_(sheetName) ? 'TRUE' : 'FALSE') : ''
  ].filter(Boolean).join('; ');

  return {
    generated_ts: generatedTs,
    experiment_name: String(spec.experiment_name || _providerCharacterOutcomeLayerAuditPrettyName_(sheetName)).trim(),
    sheet_name: sheetName,
    builder_function_name: String(spec.builder_function_name || '').trim(),
    source_sheets_used: actualSources.join('|'),
    outcome_fields_used: _uniqueStrings_((economicFields || []).concat(marketFields || [])).join('|'),
    economic_value_fields_used: (economicFields || []).join('|'),
    market_reaction_fields_used: (marketFields || []).join('|'),
    classification: classification,
    methodological_risk: String(spec.methodological_risk || 'unknown').trim(),
    prior_conclusion_status: String(spec.prior_conclusion_status || 'inconclusive_until_rebuilt').trim(),
    required_action: String(spec.required_action || 'investigate_manually').trim(),
    notes: notes
  };
}

function _providerCharacterOutcomeLayerAuditSheetPresent_(sheetName) {
  if (typeof findSheetAcrossKnownWorkbooks_ !== 'function') return false;
  var ref = findSheetAcrossKnownWorkbooks_(sheetName);
  return !!(ref && ref.found);
}

function _providerCharacterOutcomeLayerAuditPrettyName_(sheetName) {
  var s = String(sheetName || '').trim();
  if (!s) return '';
  return s.replace(/_/g, ' ').replace(/\b\w/g, function(ch) { return ch.toUpperCase(); });
}

function _providerCharacterEconomicRebuildPlanRows_(generatedTs, auditRows, warnings) {
  var rows = [];
  var requiredEconomicFields = [
    'ai_forecast_value',
    'consensus_value',
    'prev_revision',
    'released_value',
    'forecast_error_abs',
    'forecast_error_pct',
    'forecast_dir_ok',
    'economic_value_direction_ok',
    'economic_surprise_direction',
    'economic_value_accuracy_rate'
  ];

  for (var i = 0; i < (auditRows || []).length; i++) {
    var row = auditRows[i] || {};
    var layer = String(row.classification || '').trim();
    if (layer !== 'market_reaction_layer' && layer !== 'mixed_layer') continue;

    var sheetName = String(row.sheet_name || '').trim();
    var missingRequiredFields = _providerCharacterOutcomeLayerAuditMissingEconomicFields_(
      sheetName,
      requiredEconomicFields,
      row,
      warnings
    );

    rows.push({
      generated_ts: generatedTs,
      original_experiment_name: row.experiment_name || '',
      original_sheet_name: sheetName,
      current_outcome_layer: layer,
      target_outcome_layer: 'economic_value_layer',
      required_source_sheets: _providerCharacterEconomicRebuildRequiredSources_(sheetName).join('|'),
      required_economic_fields: requiredEconomicFields.join('|'),
      missing_required_fields: missingRequiredFields.join('|'),
      rebuild_priority: _providerCharacterEconomicRebuildPriority_(sheetName, layer),
      recommended_new_sheet_name: sheetName ? (sheetName + '_Economic') : '',
      recommended_builder_name: sheetName ? ('build' + _providerCharacterOutcomeLayerAuditBuilderStem_(sheetName) + 'Economic_') : '',
      expected_question_answered: _providerCharacterEconomicRebuildQuestion_(sheetName, layer),
      notes: _providerCharacterEconomicRebuildNotes_(layer, missingRequiredFields)
    });
  }

  return rows;
}

function _providerCharacterOutcomeLayerAuditMissingEconomicFields_(sheetName, requiredFields, row, warnings) {
  var required = (requiredFields || []).slice();
  var available = _providerCharacterOutcomeLayerAuditHeaderSetFromSheet_(sheetName, warnings);
  if (!available) {
    available = _providerCharacterOutcomeLayerAuditFieldSet_(String(row.economic_value_fields_used || '').split('|'));
  }

  return required.filter(function(field) {
    return !available[field];
  });
}

function _providerCharacterOutcomeLayerAuditHeaderSetFromSheet_(sheetName, warnings) {
  var name = String(sheetName || '').trim();
  if (!name) return null;
  if (typeof findSheetAcrossKnownWorkbooks_ !== 'function') return null;

  var ref = findSheetAcrossKnownWorkbooks_(name);
  if (!ref || !ref.found || !ref.sheet) {
    if (warnings) warnings.push('missing_audit_sheet:' + name);
    return null;
  }

  var headers = [];
  try {
    headers = getHeaderNames(ref.sheet) || [];
  } catch (e) {
    if (warnings) warnings.push('header_read_failed:' + name);
    return null;
  }
  return _providerCharacterOutcomeLayerAuditFieldSet_(headers);
}

function _providerCharacterOutcomeLayerAuditFieldSet_(values) {
  var set = {};
  for (var i = 0; i < (values || []).length; i++) {
    var value = String(values[i] || '').trim();
    if (value) set[value] = true;
  }
  return set;
}

function _providerCharacterEconomicRebuildRequiredSources_(sheetName) {
  var name = String(sheetName || '').trim();
  var common = ['Predictions', 'Event', 'Provider_Character_Residuals', 'Economic_Value_Accuracy'];
  if (name === 'Provider_Character_Diagnostics') {
    return ['Outcome_Ledger', 'Economic_Value_Accuracy', 'Predictions', 'Event'];
  }
  if (name.indexOf('Character_Signal_Shadow_') === 0) {
    return common.concat(['Provider_Family_Economic_Accuracy', 'Economic_To_Market_Translation_Errors', 'Evaluation_Rows']);
  }
  if (name.indexOf('Character_Signal_') === 0) {
    return common.concat(['Character_Outcome_Falsification_Report', 'Character_Outcome_Recurrence_Validation', 'Character_Outcome_Recurrence_Interpretation', 'Character_Drift_Assessment']);
  }
  if (name.indexOf('Character_Outcome_') === 0) {
    return common.concat(['Character_Outcome_Link', 'Character_Outcome_Falsification_Report']);
  }
  return common;
}

function _providerCharacterEconomicRebuildPriority_(sheetName, layer) {
  var high = {
    'Provider_Character_Diagnostics': true,
    'Character_Outcome_Link': true,
    'Character_Outcome_Falsification_Report': true,
    'Character_Signal_Shadow_Test': true
  };
  var medium = {
    'Character_Outcome_Family_Link': true,
    'Character_Outcome_Provider_Controlled': true,
    'Character_Outcome_Family_Controlled': true,
    'Character_Outcome_Permutation_Test': true,
    'Character_Outcome_Robust_Traits': true,
    'Character_Good_Reasoning_Proxy_Test': true,
    'Character_Outcome_Recurrence_Validation': true,
    'Character_Drift_Assessment': true,
    'Character_Outcome_Recurrence_Block_Detail': true,
    'Character_Outcome_Recurrence_Interpretation': true,
    'Character_Signal_Candidates': true,
    'Character_Signal_Readiness_Report': true,
    'Character_Signal_Shadow_Family_Test': true,
    'Character_Signal_Shadow_Readiness': true
  };
  var low = {
    'Character_Outcome_Summary': true,
    'Character_Signal_Candidate_Summary': true,
    'Character_Signal_Candidate_Family_Map': true,
    'Character_Signal_Shadow_Summary': true
  };

  if (high[sheetName]) return 'high';
  if (medium[sheetName]) return 'medium';
  if (low[sheetName]) return 'low';
  if (layer === 'mixed_layer') return 'high';
  return 'medium';
}

function _providerCharacterEconomicRebuildQuestion_(sheetName, layer) {
  var label = _providerCharacterOutcomeLayerAuditPrettyName_(sheetName);
  if (layer === 'mixed_layer') {
    return 'Can ' + label + ' be split so the economic-value slice is tested before market reaction?';
  }
  return 'Does ' + label + ' hold when the target is released-value accuracy instead of downstream market reaction?';
}

function _providerCharacterEconomicRebuildNotes_(layer, missingRequiredFields) {
  var parts = [
    'rebuild against economic_value_layer only',
    'current_layer=' + layer,
    'do_not_use_market_reaction_fields_for_economic_claims'
  ];
  if (layer === 'mixed_layer') parts.push('split_economic_and_market_versions');
  if ((missingRequiredFields || []).length) {
    parts.push('missing_required_fields=' + missingRequiredFields.join('|'));
  } else {
    parts.push('all_required_economic_fields_present');
  }
  return parts.join('; ');
}

function _providerCharacterTranslationReinterpretationRows_(generatedTs, auditRows, warnings) {
  var rows = [];
  for (var i = 0; i < (auditRows || []).length; i++) {
    var row = auditRows[i] || {};
    var layer = String(row.classification || '').trim();
    if (layer !== 'market_reaction_layer' && layer !== 'mixed_layer') continue;
    rows.push({
      generated_ts: generatedTs,
      original_experiment_name: row.experiment_name || '',
      provider: 'all_providers',
      trait: 'all_traits',
      original_result: row.classification || '',
      original_outcome_metric: (row.market_reaction_fields_used || row.outcome_fields_used || ''),
      corrected_interpretation: _providerCharacterTranslationCorrectedInterpretation_(row),
      valid_as_economic_character_signal: 'FALSE',
      valid_as_market_translation_signal: 'TRUE',
      notes: _providerCharacterTranslationNotes_(row, warnings)
    });
  }
  return rows;
}

function _providerCharacterTranslationCorrectedInterpretation_(row) {
  var layer = String(row.classification || '').trim();
  if (layer === 'mixed_layer') {
    return 'Mixed evidence: preserve the market-translation read, but split economic-value and market-reaction versions before claiming economic character.';
  }
  return 'Provider Character -> Economic-to-Market Translation Behavior';
}

function _providerCharacterTranslationNotes_(row, warnings) {
  var parts = [];
  if (row.sheet_name) parts.push('sheet=' + row.sheet_name);
  if (String(row.methodological_risk || '').trim()) parts.push('risk=' + row.methodological_risk);
  if (String(row.prior_conclusion_status || '').trim()) parts.push('prior_status=' + row.prior_conclusion_status);
  parts.push('sheet_level_summary=true');
  if (warnings && warnings.length) parts.push('warnings=' + warnings.length);
  return parts.join('; ');
}

function _providerCharacterMethodologySummaryRows_(generatedTs, auditRows, rebuildRows, translationRows) {
  var counts = {
    economic_value_layer: 0,
    market_reaction_layer: 0,
    mixed_layer: 0,
    unclear_layer: 0
  };

  for (var i = 0; i < (auditRows || []).length; i++) {
    var layer = String((auditRows[i] || {}).classification || '').trim();
    if (counts.hasOwnProperty(layer)) counts[layer] += 1;
  }

  var highestPriorityRebuilds = _providerCharacterHighestPriorityRebuilds_(rebuildRows || []);
  var mainWarning = [
    'Most character experiments were judged on downstream market-reaction layers, not the economic value layer.',
    'The residual/disagreement stack remains the cleanest economic-character evidence.',
    'Mixed shadow sheets need split economic and market versions before economic claims.'
  ].join(' ');

  return [{
    generated_ts: generatedTs,
    total_character_experiments_reviewed: (auditRows || []).length,
    economic_value_layer_count: counts.economic_value_layer,
    market_reaction_layer_count: counts.market_reaction_layer,
    mixed_layer_count: counts.mixed_layer,
    unclear_layer_count: counts.unclear_layer,
    experiments_needing_rebuild_count: (rebuildRows || []).length,
    experiments_valid_as_translation_count: counts.market_reaction_layer + counts.mixed_layer,
    experiments_remaining_valid_count: counts.economic_value_layer,
    highest_priority_rebuilds: highestPriorityRebuilds,
    main_methodology_warning: mainWarning,
    recommended_next_step: 'Rebuild the highest-priority outcome-link and shadow sheets against Economic_Value_Accuracy before making Provider Character economic claims.'
  }];
}

function _providerCharacterHighestPriorityRebuilds_(rebuildRows) {
  var priorityWeight = { high: 0, medium: 1, low: 2, not_needed: 3 };
  var sorted = (rebuildRows || []).slice().sort(function(a, b) {
    var aw = priorityWeight[String(a.rebuild_priority || 'low').trim()] || 2;
    var bw = priorityWeight[String(b.rebuild_priority || 'low').trim()] || 2;
    if (aw !== bw) return aw - bw;
    return String(a.original_sheet_name || '').localeCompare(String(b.original_sheet_name || ''));
  });
  return sorted.slice(0, 3).map(function(row) {
    return String(row.original_sheet_name || '');
  }).join('|');
}

function _providerCharacterOutcomeLayerAuditObjectsToRows_(rows, headers) {
  return (rows || []).map(function(row) {
    return (headers || []).map(function(header) {
      return row && row.hasOwnProperty(header) ? row[header] : '';
    });
  });
}

function _providerCharacterOutcomeLayerAuditBuilderStem_(sheetName) {
  return _providerCharacterOutcomeLayerAuditPrettyName_(sheetName).replace(/[^A-Za-z0-9]+/g, '');
}
