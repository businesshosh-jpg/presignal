/*******************************************************
 * provider_character_direct_expression_capture.js
 * - Diagnostic-only Provider Character v2 — Direct Expression Capture v1
 * - Reuses the existing 36 fresh replay rows as cohort A
 * - Adds a new provider-call cohort C on additional historical events
 * - No Generation-1 proxy data, no comparison sheets, no production changes
 *******************************************************/

function menuBuildProviderCharacterDirectExpressionCapture_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterDirectExpressionCapture_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character direct expression capture -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Total=' + (res.total_rows_written || 0) +
      ' | CohortA=' + (res.cohort_a_rows_written || 0) +
      ' | CohortB=' + (res.cohort_b_rows_written || 0) +
      ' | CohortC=' + (res.cohort_c_rows_written || 0),
      'Provider Character Direct Expression Capture',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character direct expression capture -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterDirectExpressionCapture_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var captureRunId = String(params.capture_run_id || '').trim() || _uuidFromString_('provider_character_direct_expression_capture:' + generatedTs);
  var warnings = [];
  try {
    var writeOutput = params.write_output !== false;
    var returnPayloadMode = String(params.return_payload || '').trim().toLowerCase();
    if (!returnPayloadMode) returnPayloadMode = writeOutput ? 'none' : 'cohort_c';
    var batchStart = _numOrNull_(params.batch_start);
    var batchSize = _numOrNull_(params.batch_size);
    var targetCount = _numOrNull_(params.target_event_count);
    if (targetCount == null || targetCount <= 0) targetCount = _providerCharacterDirectExpressionCaptureTargetCount_();
    if (batchStart == null || batchStart < 0) batchStart = 0;
    if (batchSize == null || batchSize <= 0) batchSize = targetCount;

    var sources = params.source_bundle || _providerCharacterDirectExpressionCaptureLoadSources_(warnings);
    var providers = _resolveProviders_(['Anthropic', 'Gemini', 'OpenAI']);
    if (!providers.length) {
      throw new Error('Direct expression capture requires at least one enabled provider.');
    }

    var providerMap = {};
    for (var p = 0; p < providers.length; p++) providerMap[providers[p].name] = providers[p];

    var freshReplayRows = Array.isArray(params.fresh_replay_rows)
      ? params.fresh_replay_rows
      : _providerCharacterDirectExpressionCaptureReadFreshReplayRows_(sources.freshReplayBundle, warnings);
    var cohortAEventIds = _providerCharacterDirectExpressionCaptureEventIdSet_(freshReplayRows);
    var econEventLookup = Array.isArray(params.economic_rows)
      ? _providerCharacterDirectExpressionCaptureBuildEconomicEventLookupFromRows_(params.economic_rows, warnings)
      : _providerCharacterDirectExpressionCaptureBuildEconomicEventLookup_(sources.economicBundle, warnings);
    var existingCaptureRows = Array.isArray(params.existing_capture_rows)
      ? params.existing_capture_rows
      : _providerCharacterMicroExpressionBundleRowsToObjects_(
          _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false)
        );
    var existingCaptureEventIds = _providerCharacterDirectExpressionCaptureEventIdSet_(existingCaptureRows);

    var cohortARows = _providerCharacterDirectExpressionCaptureBuildCohortARows_(
      generatedTs,
      captureRunId,
      freshReplayRows,
      econEventLookup,
      warnings
    );

    var eventPool = Array.isArray(params.event_rows)
      ? _providerCharacterDirectExpressionCaptureBuildEventPoolFromRows_(
          params.event_rows,
          econEventLookup,
          cohortAEventIds,
          existingCaptureEventIds,
          warnings
        )
      : _providerCharacterDirectExpressionCaptureBuildEventPool_(
          sources.eventBundle,
          econEventLookup,
          cohortAEventIds,
          existingCaptureEventIds,
          warnings
        );
    var sampledEvents = _providerCharacterDirectExpressionCaptureSelectEvents_(
      eventPool,
      targetCount,
      warnings
    );
    sampledEvents = sampledEvents.slice(batchStart, batchStart + batchSize);
    if (!sampledEvents.length && warnings) warnings.push('batch_window_empty:' + batchStart + ':' + batchSize);

    var cohortCRows = _providerCharacterDirectExpressionCaptureBuildCohortBRows_(
      generatedTs,
      captureRunId,
      sampledEvents,
      providers,
      providerMap,
      sources.eventBundle,
      econEventLookup,
      warnings,
      {
        cohort_id: String(params.cohort_id || '').trim() || 'cohort_c_direct_capture_expansion',
        source_experiment: String(params.source_experiment || '').trim() || 'Direct Expression Capture Expansion v1',
        notes_prefix: String(params.notes_prefix || '').trim(),
        random_seed: String(params.random_seed || '').trim()
      }
    );

    var allRows = existingCaptureRows.concat(cohortARows).concat(cohortCRows);
    allRows = _providerCharacterDirectExpressionCaptureDedupeRows_(allRows);
    var expressionRows = allRows.filter(function(row) {
      return String(row.provider_call_status || '').toLowerCase() !== 'failed';
    });

    var clusterRows = _providerCharacterDirectExpressionCaptureBuildClusterRows_(
      generatedTs,
      captureRunId,
      expressionRows,
      warnings
    );

    var summaryRows = _providerCharacterDirectExpressionCaptureBuildSummaryRows_(
      generatedTs,
      captureRunId,
      allRows,
      expressionRows,
      cohortARows.length,
      cohortCRows.length,
      clusterRows,
      warnings
    );

    var methodologyRows = _providerCharacterDirectExpressionCaptureBuildMethodologyRows_(
      generatedTs,
      captureRunId,
      freshReplayRows.length,
      cohortARows.length,
      cohortCRows.length,
      batchStart,
      batchSize,
      existingCaptureRows.length,
      warnings,
      {
        experiment_name: String(params.methodology_experiment_name || '').trim(),
        branch_name: String(params.methodology_branch_name || '').trim(),
        purpose: String(params.methodology_purpose || '').trim(),
        sample_strategy: String(params.methodology_sample_strategy || '').trim(),
        notes_suffix: String(params.methodology_notes_suffix || '').trim(),
        target_total_provider_event_rows: String(params.methodology_target_total_provider_event_rows || '').trim()
      }
    );

    var captureHeaders = _providerCharacterDirectExpressionCaptureHeaders_();
    var clusterHeaders = _providerCharacterDirectExpressionCaptureClusterHeaders_();
    var summaryHeaders = _providerCharacterDirectExpressionCaptureSummaryHeaders_();
    var methodologyHeaders = _providerCharacterDirectExpressionCaptureMethodologyHeaders_();

    var captureSheet = null;
    var clusterSheet = null;
    var summarySheet = null;
    var methodologySheet = null;
    if (writeOutput) {
      captureSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Capture', captureHeaders, warnings);
      clusterSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Clusters', clusterHeaders, warnings);
      summarySheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Summary', summaryHeaders, warnings);
      methodologySheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Methodology', methodologyHeaders, warnings);

      _rewriteSheetRowsPreservingHeaders_(captureSheet.sheet, captureSheet.headers, _characterResidualObjectsToRows_(allRows, captureHeaders));
      _rewriteSheetRowsPreservingHeaders_(clusterSheet.sheet, clusterSheet.headers, _characterResidualObjectsToRows_(clusterRows, clusterHeaders));
      _rewriteSheetRowsPreservingHeaders_(summarySheet.sheet, summarySheet.headers, _characterResidualObjectsToRows_(summaryRows, summaryHeaders));
      _rewriteSheetRowsPreservingHeaders_(methodologySheet.sheet, methodologySheet.headers, _characterResidualObjectsToRows_(methodologyRows, methodologyHeaders));
    }

    var response = {
      status: 'ok',
      generated_ts: generatedTs,
      capture_run_id: captureRunId,
      batch_start: batchStart,
      batch_size: batchSize,
      capture_sheet: captureSheet ? captureSheet.sheet.getName() : 'Provider_Character_Direct_Expression_Capture',
      cluster_sheet: clusterSheet ? clusterSheet.sheet.getName() : 'Provider_Character_Direct_Expression_Clusters',
      summary_sheet: summarySheet ? summarySheet.sheet.getName() : 'Provider_Character_Direct_Expression_Summary',
      methodology_sheet: methodologySheet ? methodologySheet.sheet.getName() : 'Provider_Character_Direct_Expression_Methodology',
      total_rows_written: allRows.length,
      cohort_a_rows_written: cohortARows.length,
      cohort_b_rows_written: existingCaptureRows.filter(function(row) {
        return String(row.cohort_id || '') === 'cohort_b_direct_capture_expansion';
      }).length,
      cohort_b_rows_preserved: existingCaptureRows.filter(function(row) {
        return String(row.cohort_id || '') === 'cohort_b_direct_capture_expansion';
      }).length,
      cohort_c_rows_written: cohortCRows.length,
      expression_rows_written: expressionRows.length,
      cluster_rows_written: clusterRows.length,
      summary_rows_written: summaryRows.length,
      methodology_rows_written: methodologyRows.length,
      sampled_events: _providerCharacterDirectExpressionCaptureUniqueEventCount_(allRows),
      warnings: _uniqueStrings_(warnings)
    };
    if (returnPayloadMode === 'cohort_c' || returnPayloadMode === 'all') {
      response.cohort_c_rows = cohortCRows;
      response.cohort_c_values = _characterResidualObjectsToRows_(cohortCRows, captureHeaders);
    }
    if (returnPayloadMode === 'reports' || returnPayloadMode === 'all') {
      response.cluster_rows = clusterRows;
      response.cluster_values = _characterResidualObjectsToRows_(clusterRows, clusterHeaders);
      response.summary_rows = summaryRows;
      response.summary_values = _characterResidualObjectsToRows_(summaryRows, summaryHeaders);
      response.methodology_rows = methodologyRows;
      response.methodology_values = _characterResidualObjectsToRows_(methodologyRows, methodologyHeaders);
    }
    if (returnPayloadMode === 'all') {
      response.capture_values = _characterResidualObjectsToRows_(allRows, captureHeaders);
    }
    return response;
  } catch (e) {
    return {
      status: 'error',
      generated_ts: generatedTs,
      capture_run_id: captureRunId,
      error_message: (e && e.stack) ? e.stack : String(e),
      warnings: _uniqueStrings_(warnings)
    };
  }
}

function buildProviderCharacterDirectExpressionCapture() {
  return buildProviderCharacterDirectExpressionCapture_();
}

function buildProviderCharacterDirectExpressionRandomCohort_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var captureRunId = String(params.capture_run_id || '').trim() || _uuidFromString_('provider_character_direct_expression_random_cohort:' + generatedTs);
  var randomSeed = String(params.random_seed || '').trim() || 'signal_synchrony_random_cohort_v1_seed_20260626';
  var warnings = [];

  try {
    var writeOutput = params.write_output !== false;
    var targetProviderEventPairs = _numOrNull_(params.target_provider_event_pairs);
    if (targetProviderEventPairs == null || targetProviderEventPairs <= 0) targetProviderEventPairs = 60;
    var providers = _resolveProviders_(['Anthropic', 'Gemini', 'OpenAI']);
    if (!providers.length) throw new Error('Random cohort capture requires at least one enabled provider.');
    var providerCount = providers.length;
    if (providerCount <= 0) throw new Error('Random cohort capture requires enabled providers.');
    var targetEventCount = Math.ceil(targetProviderEventPairs / providerCount);

    var sources = params.source_bundle || _providerCharacterDirectExpressionCaptureLoadSources_(warnings);
    var freshReplayRows = _providerCharacterDirectExpressionCaptureReadFreshReplayRows_(sources.freshReplayBundle, warnings);
    var cohortAEventIds = _providerCharacterDirectExpressionCaptureEventIdSet_(freshReplayRows);
    var econEventLookup = _providerCharacterDirectExpressionCaptureBuildEconomicEventLookup_(sources.economicBundle, warnings);
    var existingCaptureBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false);
    var existingCaptureRows = _providerCharacterMicroExpressionBundleRowsToObjects_(existingCaptureBundle);
    var existingCaptureEventIds = _providerCharacterDirectExpressionCaptureEventIdSet_(existingCaptureRows);
    var eventPool = _providerCharacterDirectExpressionCaptureBuildEventPool_(
      sources.eventBundle,
      econEventLookup,
      cohortAEventIds,
      existingCaptureEventIds,
      warnings
    );
    var sampledEvents = _providerCharacterDirectExpressionCaptureSelectRandomEvents_(
      eventPool,
      targetEventCount,
      randomSeed,
      warnings
    );
    if (!sampledEvents.length) throw new Error('Random cohort selection produced no events.');

    var providerMap = {};
    for (var p = 0; p < providers.length; p++) providerMap[providers[p].name] = providers[p];
    var randomCohortRows = _providerCharacterDirectExpressionCaptureBuildCohortBRows_(
      generatedTs,
      captureRunId,
      sampledEvents,
      providers,
      providerMap,
      sources.eventBundle,
      econEventLookup,
      warnings,
      {
        cohort_id: 'signal_synchrony_random_cohort_v1',
        source_experiment: 'Signal Synchrony v1 — Direct Expression Random Cohort',
        notes_prefix: 'randomized_validation_cohort=TRUE',
        random_seed: randomSeed
      }
    );

    var allRows = _providerCharacterDirectExpressionCaptureDedupeRows_((existingCaptureRows || []).concat(randomCohortRows));
    var expressionRows = allRows.filter(function(row) {
      return String(row.provider_call_status || '').toLowerCase() !== 'failed';
    });
    var clusterRows = _providerCharacterDirectExpressionCaptureBuildClusterRows_(generatedTs, captureRunId, expressionRows, warnings);
    var summaryRows = _providerCharacterDirectExpressionCaptureBuildSummaryRows_(
      generatedTs,
      captureRunId,
      allRows,
      expressionRows,
      0,
      randomCohortRows.length,
      clusterRows,
      warnings
    );
    var methodologyRows = _providerCharacterDirectExpressionCaptureBuildMethodologyRows_(
      generatedTs,
      captureRunId,
      0,
      0,
      randomCohortRows.length,
      0,
      sampledEvents.length,
      existingCaptureRows.length,
      warnings,
      {
        experiment_name: 'Signal Synchrony v1 — Direct Expression Random Cohort',
        branch_name: 'Signal Synchrony v1 / Direct Expression Randomized Replication',
        purpose: 'Build an independent randomized direct-expression replication cohort using the existing capture methodology',
        sample_strategy: 'Random without replacement from canonical eligible Event population using deterministic seed=' + randomSeed + '; excludes provider-event pairs already present in Direct Expression Capture; no manual ranking/filtering.',
        notes_suffix: 'random_seed=' + randomSeed + '; randomized_event_count=' + sampledEvents.length + '; randomized_provider_event_pairs=' + randomCohortRows.length,
        target_total_provider_event_rows: String(targetProviderEventPairs)
      }
    );

    if (writeOutput) {
      var captureSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Capture', _providerCharacterDirectExpressionCaptureHeaders_(), warnings);
      var clusterSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Clusters', _providerCharacterDirectExpressionCaptureClusterHeaders_(), warnings);
      var summarySheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Summary', _providerCharacterDirectExpressionCaptureSummaryHeaders_(), warnings);
      var methodologySheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Methodology', _providerCharacterDirectExpressionCaptureMethodologyHeaders_(), warnings);
      _rewriteSheetRowsPreservingHeaders_(captureSheet.sheet, captureSheet.headers, _characterResidualObjectsToRows_(allRows, captureSheet.headers));
      _rewriteSheetRowsPreservingHeaders_(clusterSheet.sheet, clusterSheet.headers, _characterResidualObjectsToRows_(clusterRows, clusterSheet.headers));
      _rewriteSheetRowsPreservingHeaders_(summarySheet.sheet, summarySheet.headers, _characterResidualObjectsToRows_(summaryRows, summarySheet.headers));
      _rewriteSheetRowsPreservingHeaders_(methodologySheet.sheet, methodologySheet.headers, _characterResidualObjectsToRows_(methodologyRows, methodologySheet.headers));
    }

    return {
      status: 'ok',
      generated_ts: generatedTs,
      capture_run_id: captureRunId,
      cohort_id: 'signal_synchrony_random_cohort_v1',
      random_seed: randomSeed,
      randomized_provider_event_pairs_requested: targetProviderEventPairs,
      randomized_events_requested: targetEventCount,
      randomized_events_selected: sampledEvents.length,
      randomized_rows_written: randomCohortRows.length,
      successful_captures: randomCohortRows.filter(function(row) { return String(row.provider_call_status || '').toLowerCase() === 'success'; }).length,
      failed_captures: randomCohortRows.filter(function(row) { return String(row.provider_call_status || '').toLowerCase() === 'failed'; }).length,
      sampled_events: sampledEvents,
      randomized_rows: randomCohortRows,
      warnings: _uniqueStrings_(warnings)
    };
  } catch (e) {
    return {
      status: 'error',
      generated_ts: generatedTs,
      capture_run_id: captureRunId,
      cohort_id: 'signal_synchrony_random_cohort_v1',
      random_seed: randomSeed,
      error_message: (e && e.stack) ? e.stack : String(e),
      warnings: _uniqueStrings_(warnings)
    };
  }
}

function buildProviderCharacterDirectExpressionRandomCohort(params) {
  return buildProviderCharacterDirectExpressionRandomCohort_(params || {});
}

function _providerCharacterDirectExpressionCaptureHeaders_() {
  return [
    'generated_ts',
    'capture_run_id',
    'cohort_id',
    'event_id',
    'provider',
    'indicator_name',
    'country',
    'release_ts',
    'outcome_family',
    'importance',
    'consensus_value',
    'prev_revision',
    'released_value',
    'ai_forecast_value',
    'qualitative_result',
    'economic_dir_ok',
    'forecast_error_abs',
    'better_than_consensus',
    'rationale_short',
    'primary_focus_phrase',
    'secondary_focus_phrase',
    'ignored_or_discounted_factor_phrase',
    'causal_path_phrase',
    'failure_condition_phrase',
    'confidence_basis_phrase',
    'uncertainty_phrase',
    'expression_summary_phrase',
    'attention_terms',
    'provider_call_status',
    'token_input_estimate',
    'token_output_estimate',
    'latency_ms',
    'source_experiment',
    'notes'
  ];
}

function _providerCharacterDirectExpressionCaptureClusterHeaders_() {
  return [
    'generated_ts',
    'capture_run_id',
    'cohort_id',
    'provider',
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

function _providerCharacterDirectExpressionCaptureSummaryHeaders_() {
  return [
    'generated_ts',
    'capture_run_id',
    'total_rows',
    'cohort_a_rows',
    'cohort_b_rows',
    'sampled_events',
    'provider',
    'successful_provider_calls',
    'failed_provider_calls',
    'economic_dir_ok_rate',
    'avg_forecast_error_abs',
    'better_than_consensus_rate',
    'unique_expression_count',
    'cluster_count',
    'avg_token_input_estimate',
    'avg_token_output_estimate',
    'avg_latency_ms',
    'strongest_expression_clusters',
    'early_positive_expression_hints',
    'early_negative_expression_hints',
    'dataset_readiness',
    'recommended_next_step',
    'notes'
  ];
}

function _providerCharacterDirectExpressionCaptureMethodologyHeaders_() {
  return [
    'generated_ts',
    'capture_run_id',
    'experiment_name',
    'branch_name',
    'purpose',
    'generation_1_proxy_status',
    'generation_1_data_used',
    'prior_fresh_replay_rows_reused',
    'target_total_provider_event_rows',
    'provider_calls_made',
    'prediction_runs_made',
    'production_changes',
    'market_reaction_usage',
    'feature_pack_usage',
    'source_sheets_used',
    'sample_strategy',
    'token_minimization_rule',
    'interpretation_rule',
    'notes'
  ];
}

function _providerCharacterDirectExpressionCaptureLoadSources_(warnings) {
  return {
    freshReplayBundle: _characterResidualReadSheetBundle_('Provider_Character_Fresh_Replay', warnings, false),
    economicBundle: _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false),
    eventBundle: _characterResidualReadSheetBundle_('Event', warnings, true)
  };
}

function _providerCharacterDirectExpressionCaptureReadFreshReplayRows_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (String(row.type || '').trim().toLowerCase() === 'batch') continue;
    if (!String(row.event_id || '').trim() || !String(row.provider || '').trim()) continue;
    out.push(row);
  }
  if (!out.length && warnings) warnings.push('missing_source_rows:Provider_Character_Fresh_Replay');
  return out;
}

function _providerCharacterDirectExpressionCaptureBuildEconomicEventLookup_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBuildEconomicCases_(bundle, warnings);
  return _providerCharacterDirectExpressionCaptureBuildEconomicEventLookupFromRows_(rows, warnings);
}

function _providerCharacterDirectExpressionCaptureBuildEconomicEventLookupFromRows_(rows, warnings) {
  var keyed = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    if (!keyed[eventId] || _providerCharacterDirectExpressionCaptureRowIsNewer_(row, keyed[eventId])) {
      keyed[eventId] = row;
    }
  }
  if (!Object.keys(keyed).length && warnings) warnings.push('economic_event_lookup_empty');
  return keyed;
}

function _providerCharacterDirectExpressionCaptureRowIsNewer_(candidate, existing) {
  var candidateTs = String(candidate && (candidate.generated_ts || candidate.created_ts || candidate.release_ts) || '').trim();
  var existingTs = String(existing && (existing.generated_ts || existing.created_ts || existing.release_ts) || '').trim();
  if (candidateTs !== existingTs) return candidateTs > existingTs;
  return true;
}

function _providerCharacterDirectExpressionCaptureEventIdSet_(rows) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var eventId = String(rows[i] && rows[i].event_id || '').trim();
    if (eventId) out[eventId] = true;
  }
  return out;
}

function _providerCharacterDirectExpressionCaptureBuildEventPool_(eventBundle, econLookup, cohortAEventIds, existingCaptureEventIds, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(eventBundle);
  return _providerCharacterDirectExpressionCaptureBuildEventPoolFromRows_(rows, econLookup, cohortAEventIds, existingCaptureEventIds, warnings);
}

function _providerCharacterDirectExpressionCaptureBuildEventPoolFromRows_(rows, econLookup, cohortAEventIds, existingCaptureEventIds, warnings) {
  var keyed = {};
  var targetFamilies = _providerCharacterDirectExpressionCaptureTargetFamilyKeys_();

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (String(row.type || '').trim().toLowerCase() === 'batch') continue;
    var eventId = String(row.event_id || '').trim();
    if (!eventId || cohortAEventIds[eventId] || existingCaptureEventIds[eventId]) continue;
    var econ = econLookup[eventId];
    if (!econ) continue;
    if (_numOrNull_(econ.released_value) == null || _numOrNull_(econ.consensus_value) == null) continue;

    var indicatorName = String(row.indicator_name || econ.indicator_name || '').trim();
    var family = _providerCharacterDirectExpressionCaptureFamilyKey_(indicatorName, String(row.genre || econ.genre || ''));
    if (!family) family = 'other';
    if (!targetFamilies[family]) family = 'other';
    if (!keyed[eventId] || _providerCharacterDirectExpressionCaptureEventIsNewer_(row, keyed[eventId])) {
      keyed[eventId] = {
        event_id: eventId,
        release_ts: String(row.release_ts || econ.release_ts || '').trim(),
        indicator_name: indicatorName,
        importance: String(row.importance || econ.importance || '').trim(),
        outcome_family: String(econ.outcome_family || family || 'other').trim() || 'other',
        family_key: family,
        country: String(row.country || econ.country || '').trim(),
        interest_score: _providerCharacterDirectExpressionCaptureEventInterestScore_(row, econ)
      };
    }
  }

  var out = Object.keys(keyed).map(function(key) { return keyed[key]; });
  out.sort(function(a, b) {
    var as = _numOrNull_(a.interest_score) || 0;
    var bs = _numOrNull_(b.interest_score) || 0;
    if (bs !== as) return bs - as;
    if (String(a.release_ts || '') !== String(b.release_ts || '')) return String(a.release_ts || '').localeCompare(String(b.release_ts || ''));
    return String(a.event_id || '').localeCompare(String(b.event_id || ''));
  });

  if (!out.length && warnings) warnings.push('event_pool_empty_after_exclusion');
  return out;
}

function _providerCharacterDirectExpressionCaptureEventIsNewer_(candidate, existing) {
  var candidateTs = String(candidate && (candidate.release_ts || candidate.generated_ts || candidate.created_ts) || '').trim();
  var existingTs = String(existing && (existing.release_ts || existing.generated_ts || existing.created_ts) || '').trim();
  if (candidateTs !== existingTs) return candidateTs > existingTs;
  return true;
}

function _providerCharacterDirectExpressionCaptureEventInterestScore_(eventRow, econRow) {
  var releaseTs = String((eventRow && eventRow.release_ts) || (econRow && econRow.release_ts) || '').trim();
  var ts = Date.parse(releaseTs);
  if (!isFinite(ts)) ts = 0;
  var importance = String((eventRow && eventRow.importance) || (econRow && econRow.importance) || '').trim().toLowerCase();
  var importanceWeight = 1;
  if (importance === 'high') importanceWeight = 3;
  else if (importance === 'medium') importanceWeight = 2;
  return ts + (importanceWeight * 1000);
}

function _providerCharacterDirectExpressionCaptureSelectEvents_(eventPool, targetCount, warnings) {
  var pool = (eventPool || []).slice();
  var selected = [];
  var used = {};
  var targetFamilies = _providerCharacterDirectExpressionCaptureTargetFamilyKeys_();
  var byFamily = _providerCharacterDirectExpressionCaptureBucketEventsByFamily_(pool);
  var perFamilyTarget = 5;

  function sortFn(a, b) {
    var as = _numOrNull_(a.interest_score) || 0;
    var bs = _numOrNull_(b.interest_score) || 0;
    if (bs !== as) return bs - as;
    if (String(a.release_ts || '') !== String(b.release_ts || '')) return String(a.release_ts || '').localeCompare(String(b.release_ts || ''));
    return String(a.event_id || '').localeCompare(String(b.event_id || ''));
  }

  Object.keys(targetFamilies).sort().forEach(function(family) {
    var list = (byFamily[family] || []).slice().sort(sortFn);
    for (var i = 0; i < list.length && _providerCharacterDirectExpressionCaptureFamilySelectionCount_(selected, family) < perFamilyTarget && selected.length < targetCount; i++) {
      var item = list[i];
      if (used[item.event_id]) continue;
      used[item.event_id] = true;
      selected.push(item);
    }
  });

  if (selected.length < targetCount) {
    var remainder = pool.filter(function(item) { return !used[item.event_id]; }).sort(sortFn);
    for (var r = 0; r < remainder.length && selected.length < targetCount; r++) {
      var itemR = remainder[r];
      if (used[itemR.event_id]) continue;
      used[itemR.event_id] = true;
      selected.push(itemR);
    }
  }

  if (selected.length > targetCount) selected = selected.slice(0, targetCount);
  if (selected.length < targetCount && warnings) warnings.push('sample_size_below_target:' + selected.length + '/' + targetCount);
  return selected;
}

function _providerCharacterDirectExpressionCaptureBucketEventsByFamily_(events) {
  var buckets = {};
  for (var i = 0; i < (events || []).length; i++) {
    var item = events[i] || {};
    var family = String(item.family_key || item.outcome_family || 'other').trim().toLowerCase() || 'other';
    if (!buckets[family]) buckets[family] = [];
    buckets[family].push(item);
  }
  return buckets;
}

function _providerCharacterDirectExpressionCaptureFamilySelectionCount_(selected, family) {
  var count = 0;
  for (var i = 0; i < (selected || []).length; i++) {
    if (String(selected[i].family_key || selected[i].outcome_family || '').trim().toLowerCase() === String(family || '').trim().toLowerCase()) count += 1;
  }
  return count;
}

function _providerCharacterDirectExpressionCaptureTargetFamilyKeys_() {
  return {
    inflation: true,
    labor: true,
    growth: true,
    central_bank: true,
    consumer: true,
    housing: true,
    manufacturing: true,
    energy: true,
    sentiment: true
  };
}

function _providerCharacterDirectExpressionCaptureTargetCount_() {
  return 50;
}

function _providerCharacterDirectExpressionCaptureFamilyKey_(indicatorName, genre) {
  if (typeof deriveOutcomeFamily_ === 'function') {
    var fam = deriveOutcomeFamily_(String(indicatorName || ''), String(genre || ''));
    if (fam) return String(fam).trim().toLowerCase();
  }
  var name = String(indicatorName || '').toLowerCase();
  if (name.indexOf('inflation') >= 0 || name.indexOf('cpi') >= 0 || name.indexOf('pce') >= 0) return 'inflation';
  if (name.indexOf('job') >= 0 || name.indexOf('labor') >= 0 || name.indexOf('payroll') >= 0 || name.indexOf('unemployment') >= 0) return 'labor';
  if (name.indexOf('housing') >= 0 || name.indexOf('home') >= 0 || name.indexOf('permits') >= 0 || name.indexOf('starts') >= 0) return 'housing';
  if (name.indexOf('manufact') >= 0 || name.indexOf('factory') >= 0 || name.indexOf('pmi') >= 0) return 'manufacturing';
  if (name.indexOf('consumer') >= 0 || name.indexOf('retail') >= 0 || name.indexOf('sales') >= 0 || name.indexOf('confidence') >= 0) return 'consumer';
  if (name.indexOf('energy') >= 0 || name.indexOf('oil') >= 0 || name.indexOf('inventory') >= 0) return 'energy';
  if (name.indexOf('gdp') >= 0 || name.indexOf('growth') >= 0 || name.indexOf('durable') >= 0) return 'growth';
  if (name.indexOf('fed') >= 0 || name.indexOf('rate') >= 0 || name.indexOf('central') >= 0 || name.indexOf('policy') >= 0) return 'central_bank';
  if (name.indexOf('sentiment') >= 0 || name.indexOf('survey') >= 0 || name.indexOf('confidence') >= 0) return 'sentiment';
  return 'other';
}

function _providerCharacterDirectExpressionCaptureBuildCohortARows_(generatedTs, captureRunId, freshReplayRows, econLookup, warnings) {
  var out = [];
  for (var i = 0; i < (freshReplayRows || []).length; i++) {
    var row = freshReplayRows[i] || {};
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    var econ = econLookup[eventId] || {};
    var replayForecastValue = _numOrNull_(row.replay_ai_forecast_value);
    var score = _providerCharacterFreshReplayScoreEconomic_(replayForecastValue, row.replay_qualitative_result, econ, null);
    var betterThanConsensus = _providerCharacterDirectExpressionCaptureBetterThanConsensus_(replayForecastValue, econ);
    out.push({
      generated_ts: generatedTs,
      capture_run_id: captureRunId,
      cohort_id: 'cohort_a_existing_fresh_replay',
      event_id: eventId,
      provider: String(row.provider || '').trim(),
      indicator_name: String(row.indicator_name || econ.indicator_name || '').trim(),
      country: String(econ.country || row.country || '').trim(),
      release_ts: String(row.release_ts || econ.release_ts || '').trim(),
      outcome_family: String(row.outcome_family || econ.outcome_family || '').trim() || 'other',
      importance: String(row.importance || econ.importance || '').trim(),
      consensus_value: _numOrNull_(econ.consensus_value),
      prev_revision: _numOrNull_(econ.prev_revision),
      released_value: _numOrNull_(econ.released_value),
      ai_forecast_value: replayForecastValue == null ? '' : replayForecastValue,
      qualitative_result: String(row.replay_qualitative_result || '').trim(),
      economic_dir_ok: score && score.replay_economic_dir_ok ? String(score.replay_economic_dir_ok || '').trim() : '',
      forecast_error_abs: score && score.replay_forecast_error_abs != null ? score.replay_forecast_error_abs : '',
      better_than_consensus: betterThanConsensus,
      rationale_short: String(row.rationale_short || '').trim(),
      primary_focus_phrase: String(row.primary_focus_phrase || '').trim(),
      secondary_focus_phrase: String(row.secondary_focus_phrase || '').trim(),
      ignored_or_discounted_factor_phrase: String(row.ignored_or_discounted_factor_phrase || '').trim(),
      causal_path_phrase: String(row.causal_path_phrase || '').trim(),
      failure_condition_phrase: String(row.failure_condition_phrase || '').trim(),
      confidence_basis_phrase: String(row.confidence_basis_phrase || '').trim(),
      uncertainty_phrase: String(row.uncertainty_phrase || '').trim(),
      expression_summary_phrase: String(row.expression_summary_phrase || '').trim(),
      attention_terms: String(row.attention_terms || '').trim(),
      provider_call_status: 'reused',
      token_input_estimate: _numOrNull_(row.token_input_estimate) == null ? '' : _numOrNull_(row.token_input_estimate),
      token_output_estimate: _numOrNull_(row.token_output_estimate) == null ? '' : _numOrNull_(row.token_output_estimate),
      latency_ms: _numOrNull_(row.latency_ms) == null ? '' : _numOrNull_(row.latency_ms),
      source_experiment: 'Fresh vs Original Micro-Expression Replay v1',
      notes: _providerCharacterDirectExpressionCaptureNotes_(
        'cohort_a_reused=TRUE',
        'fresh_replay_run_id=' + String(row.replay_run_id || ''),
        'fresh_provider_call_status=' + String(row.provider_call_status || ''),
        'raw_response_captured=' + String(row.raw_provider_response_captured || ''),
        'replay_rowsource=direct_expression'
      )
    });
  }
  if (!out.length && warnings) warnings.push('cohort_a_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionCaptureBuildCohortBRows_(generatedTs, captureRunId, sampledEvents, providers, providerMap, eventBundle, econLookup, warnings, options) {
  options = options || {};
  var cohortId = String(options.cohort_id || '').trim() || 'cohort_c_direct_capture_expansion';
  var sourceExperiment = String(options.source_experiment || '').trim() || 'Direct Expression Capture Expansion v1';
  var notesPrefix = String(options.notes_prefix || '').trim();
  var randomSeed = String(options.random_seed || '').trim();
  var out = [];
  for (var i = 0; i < (sampledEvents || []).length; i++) {
    var eventInfo = sampledEvents[i] || {};
    var eventId = String(eventInfo.event_id || '').trim();
    if (!eventId) continue;
    var ev = _getPredictionEventById_(eventBundle && eventBundle.sheet ? eventBundle.sheet : getSheet('Event'), eventId);
    if (!ev || !ev.event_id) {
      warnings.push('event_missing_from_event_sheet:' + eventId);
      continue;
    }
    var econ = econLookup[eventId] || {};
    var prompt = _providerCharacterDirectExpressionCaptureBuildPrompt_(ev);
    var providerRespMap = _providerCharacterDirectExpressionCaptureCallProvidersParallel_(providers, prompt, warnings, eventId);
    for (var p = 0; p < providers.length; p++) {
      var prov = providers[p];
      var startMs = Date.now();
      var providerResp = providerRespMap[prov.name] || null;
      var callStatus = providerResp && providerResp.call_status ? String(providerResp.call_status) : 'failed';
      var callError = providerResp && providerResp.call_error ? String(providerResp.call_error) : '';
      var latencyMs = providerResp && providerResp.latency_ms != null ? providerResp.latency_ms : '';
      if (providerResp && providerResp.latency_ms == null) latencyMs = Date.now() - startMs;

      var normalized = _providerCharacterDirectExpressionCaptureNormalizeProviderOutput_(providerResp && providerResp.parsed || {}, providerResp && providerResp.raw_output || '');
      var forecastValue = _numOrNull_(normalized.ai_forecast_value);
      var score = _providerCharacterFreshReplayScoreEconomic_(forecastValue, normalized.qualitative_result, econ, ev);
      var betterThanConsensus = _providerCharacterDirectExpressionCaptureBetterThanConsensus_(forecastValue, econ);

      out.push({
        generated_ts: generatedTs,
        capture_run_id: captureRunId,
        cohort_id: cohortId,
        event_id: eventId,
        provider: String(prov.name || '').trim(),
        indicator_name: String(ev.indicator_name || econ.indicator_name || eventInfo.indicator_name || '').trim(),
        country: String(ev.country || econ.country || eventInfo.country || '').trim(),
        release_ts: String(ev.release_ts || econ.release_ts || eventInfo.release_ts || '').trim(),
        outcome_family: String(eventInfo.outcome_family || econ.outcome_family || _providerCharacterDirectExpressionCaptureFamilyKey_(String(ev.indicator_name || ''), String(ev.genre || '')) || 'other').trim() || 'other',
        importance: String(ev.importance || econ.importance || eventInfo.importance || '').trim(),
        consensus_value: _numOrNull_(econ.consensus_value),
        prev_revision: _numOrNull_(econ.prev_revision),
        released_value: _numOrNull_(econ.released_value),
        ai_forecast_value: forecastValue == null ? '' : forecastValue,
        qualitative_result: String(normalized.qualitative_result || '').trim(),
        economic_dir_ok: score && score.replay_economic_dir_ok ? String(score.replay_economic_dir_ok || '').trim() : '',
        forecast_error_abs: score && score.replay_forecast_error_abs != null ? score.replay_forecast_error_abs : '',
        better_than_consensus: betterThanConsensus,
        rationale_short: String(normalized.rationale_short || '').trim(),
        primary_focus_phrase: String(normalized.primary_focus_phrase || '').trim(),
        secondary_focus_phrase: String(normalized.secondary_focus_phrase || '').trim(),
        ignored_or_discounted_factor_phrase: String(normalized.ignored_or_discounted_factor_phrase || '').trim(),
        causal_path_phrase: String(normalized.causal_path_phrase || '').trim(),
        failure_condition_phrase: String(normalized.failure_condition_phrase || '').trim(),
        confidence_basis_phrase: String(normalized.confidence_basis_phrase || '').trim(),
        uncertainty_phrase: String(normalized.uncertainty_phrase || '').trim(),
        expression_summary_phrase: String(normalized.expression_summary_phrase || '').trim(),
        attention_terms: String(normalized.attention_terms || '').trim(),
        provider_call_status: callStatus,
        token_input_estimate: providerResp && providerResp.prompt_tokens != null ? providerResp.prompt_tokens : '',
        token_output_estimate: providerResp && providerResp.completion_tokens != null ? providerResp.completion_tokens : '',
        latency_ms: latencyMs == null ? '' : latencyMs,
        source_experiment: sourceExperiment,
        notes: _providerCharacterDirectExpressionCaptureNotes_(
          notesPrefix,
          'cohort_c_new_capture=TRUE',
          'provider_call_status=' + callStatus,
          'raw_response_captured=' + (providerResp && providerResp.raw_output ? 'TRUE' : 'FALSE'),
          'event_family=' + String(eventInfo.outcome_family || econ.outcome_family || ''),
          'error=' + (callStatus === 'failed' ? callError : ''),
          'capture_run_id=' + captureRunId,
          randomSeed ? ('random_seed=' + randomSeed) : ''
        )
      });
    }
  }
  if (!out.length && warnings) warnings.push('cohort_b_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionCaptureSelectRandomEvents_(eventPool, targetCount, randomSeed, warnings) {
  var pool = (eventPool || []).slice().sort(function(a, b) {
    if (String(a.event_id || '') !== String(b.event_id || '')) return String(a.event_id || '').localeCompare(String(b.event_id || ''));
    return String(a.release_ts || '').localeCompare(String(b.release_ts || ''));
  });
  if (!pool.length) {
    if (warnings) warnings.push('random_event_pool_empty');
    return [];
  }
  var shuffled = _providerCharacterDirectExpressionCaptureDeterministicShuffle_(pool, randomSeed);
  var out = shuffled.slice(0, Math.max(0, Number(targetCount || 0)));
  if (out.length < targetCount && warnings) warnings.push('random_sample_size_below_target:' + out.length + '/' + targetCount);
  return out;
}

function _providerCharacterDirectExpressionCaptureDeterministicShuffle_(items, seed) {
  var out = (items || []).slice();
  var rand = _providerCharacterDirectExpressionCaptureSeededRandom_(seed);
  for (var i = out.length - 1; i > 0; i--) {
    var j = Math.floor(rand() * (i + 1));
    var tmp = out[i];
    out[i] = out[j];
    out[j] = tmp;
  }
  return out;
}

function _providerCharacterDirectExpressionCaptureSeededRandom_(seed) {
  var state = _providerCharacterDirectExpressionCaptureSeedToUint32_(seed);
  if (!state) state = 0x6d2b79f5;
  return function() {
    state = (state + 0x6D2B79F5) >>> 0;
    var t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function _providerCharacterDirectExpressionCaptureSeedToUint32_(seed) {
  var text = String(seed || '').trim();
  var h = 2166136261;
  for (var i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function _providerCharacterDirectExpressionCaptureCallProvidersParallel_(providers, prompt, warnings, eventId) {
  var specs = [];
  var requests = [];
  for (var i = 0; i < (providers || []).length; i++) {
    var prov = providers[i];
    if (!prov || !prov.name) continue;
    var spec = _providerCharacterDirectExpressionCaptureBuildProviderRequest_(prov, prompt);
    if (!spec || !spec.request) continue;
    specs.push({
      provider: prov,
      expected_object: 'ai_prediction'
    });
    requests.push(spec.request);
  }

  var responses = null;
  var fetchAllError = '';
  try {
    responses = UrlFetchApp.fetchAll(requests);
  } catch (e) {
    fetchAllError = (e && e.stack) ? e.stack : String(e);
    if (warnings) warnings.push('fetchAll_failed:' + eventId + ':' + fetchAllError);
  }

  var out = {};
  for (var j = 0; j < specs.length; j++) {
    var spec = specs[j];
    var prov = spec.provider;
    var response = responses && responses[j] ? responses[j] : null;
    var parsedResult = null;
    var callStatus = 'success';
    var callError = '';
    var startMs = Date.now();
    try {
      if (!response) throw new Error('Missing fetchAll response for ' + prov.name);
      parsedResult = _providerCharacterDirectExpressionCaptureParseProviderResponse_(prov, response, spec.expected_object);
    } catch (e) {
      callStatus = 'failed';
      callError = (e && e.stack) ? e.stack : String(e);
      try {
        parsedResult = _callProviderJsonObject_(prov, prompt, spec.expected_object);
        callStatus = 'success';
        callError = '';
      } catch (fallbackErr) {
        parsedResult = {
          parsed: {},
          raw_output: '',
          prompt_tokens: null,
          completion_tokens: null
        };
        callError = (fallbackErr && fallbackErr.stack) ? fallbackErr.stack : String(fallbackErr);
      }
    }
    out[String(prov.name || '').trim()] = {
      parsed: parsedResult && parsedResult.parsed ? parsedResult.parsed : {},
      raw_output: parsedResult && parsedResult.raw_output ? parsedResult.raw_output : '',
      prompt_tokens: parsedResult && parsedResult.prompt_tokens != null ? parsedResult.prompt_tokens : null,
      completion_tokens: parsedResult && parsedResult.completion_tokens != null ? parsedResult.completion_tokens : null,
      latency_ms: Date.now() - startMs,
      call_status: callStatus,
      call_error: callError
    };
  }
  return out;
}

function _providerCharacterDirectExpressionCaptureDedupeRows_(rows) {
  var seen = {};
  var out = [];
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = [
      String(row.cohort_id || '').trim(),
      String(row.event_id || '').trim(),
      String(row.provider || '').trim(),
      String(row.source_experiment || '').trim()
    ].join('|');
    if (!key || seen[key]) continue;
    seen[key] = true;
    out.push(row);
  }
  return out;
}

function _providerCharacterDirectExpressionCaptureBuildProviderRequest_(prov, prompt) {
  if (!prov || !prov.name) return null;
  if (prov.name === 'OpenAI') return _providerCharacterDirectExpressionCaptureBuildOpenAiRequest_(prov, prompt);
  if (prov.name === 'Gemini') return _providerCharacterDirectExpressionCaptureBuildGeminiRequest_(prov, prompt);
  if (prov.name === 'Anthropic') return _providerCharacterDirectExpressionCaptureBuildAnthropicRequest_(prov, prompt);
  return null;
}

function _providerCharacterDirectExpressionCaptureBuildOpenAiRequest_(prov, prompt) {
  var body = {
    model: prov.model,
    temperature: CFG.PREDICTION_TEMPERATURE,
    seed: CFG.PREDICTION_SEED,
    max_tokens: 256,
    response_format: { type: 'json_object' },
    messages: [
      { role: 'system', content: prompt.system },
      { role: 'user', content: prompt.user + '\n\n' + prompt.instruction }
    ]
  };
  return {
    request: {
      url: 'https://api.openai.com/v1/chat/completions',
      method: 'post',
      contentType: 'application/json',
      headers: { 'Authorization': 'Bearer ' + prov.key },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    }
  };
}

function _providerCharacterDirectExpressionCaptureBuildGeminiRequest_(prov, prompt) {
  var body = {
    contents: [{ role: 'user', parts: [{ text: prompt.system + '\n\n' + prompt.user + '\n\n' + prompt.instruction }] }],
    generationConfig: {
      response_mime_type: 'application/json',
      temperature: CFG.PREDICTION_TEMPERATURE,
      seed: CFG.PREDICTION_SEED,
      maxOutputTokens: 256
    }
  };
  return {
    request: {
      url: 'https://generativelanguage.googleapis.com/v1beta/models/' + encodeURIComponent(prov.model) + ':generateContent?key=' + encodeURIComponent(prov.key),
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    }
  };
}

function _providerCharacterDirectExpressionCaptureBuildAnthropicRequest_(prov, prompt) {
  var body = {
    model: prov.model,
    max_tokens: 256,
    temperature: CFG.PREDICTION_TEMPERATURE,
    system: prompt.system,
    messages: [{ role: 'user', content: prompt.user + '\n\n' + prompt.instruction }]
  };
  return {
    request: {
      url: 'https://api.anthropic.com/v1/messages',
      method: 'post',
      contentType: 'application/json',
      headers: { 'x-api-key': prov.key, 'anthropic-version': '2023-06-01' },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    }
  };
}

function _providerCharacterDirectExpressionCaptureParseProviderResponse_(prov, response, expectedObject) {
  if (!prov || !prov.name) throw new Error('Provider metadata missing');
  if (!response) throw new Error('Missing HTTP response');
  var code = response.getResponseCode();
  var txt = response.getContentText();
  if (code === 429) throw _quotaErr_(prov.name + ' 429: ' + txt);
  if (code >= 500) throw _providerErr_(prov.name + ' ' + code);
  if (code < 200 || code > 299) throw _providerErr_(prov.name + ' ' + code + ': ' + txt);
  var j = JSON.parse(txt);
  var c = '';
  var promptTokens = null;
  var completionTokens = null;
  if (prov.name === 'OpenAI') {
    c = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
    promptTokens = (j.usage || {}).prompt_tokens || null;
    completionTokens = (j.usage || {}).completion_tokens || null;
  } else if (prov.name === 'Gemini') {
    c = (j.candidates && j.candidates[0] && j.candidates[0].content && j.candidates[0].content.parts && j.candidates[0].content.parts[0] && j.candidates[0].content.parts[0].text) || '';
    promptTokens = (j.usageMetadata || {}).promptTokenCount || null;
    completionTokens = (j.usageMetadata || {}).candidatesTokenCount || null;
  } else if (prov.name === 'Anthropic') {
    c = (j.content && j.content[0] && j.content[0].text) || '';
    promptTokens = (j.usage || {}).input_tokens || null;
    completionTokens = (j.usage || {}).output_tokens || null;
  }
  if (!c) throw _providerErr_(prov.name + ': empty content');
  return {
    parsed: _strictParseJsonObject_(c, expectedObject),
    raw_output: c,
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens
  };
}

function _providerCharacterDirectExpressionCaptureBuildPrompt_(ev) {
  var eventFamily = (typeof deriveOutcomeFamily_ === 'function')
    ? (deriveOutcomeFamily_(String(ev.indicator_name || ''), String(ev.genre || '')) || 'other')
    : _providerCharacterDirectExpressionCaptureFamilyKey_(String(ev.indicator_name || ''), String(ev.genre || ''));
  var payload = {
    object: 'econ_event',
    event_id: ev.event_id,
    type: ev.type,
    country: String(ev.country || '').trim(),
    indicator_name: ev.indicator_name,
    release_ts: ev.release_ts,
    consensus_value: (typeof ev.consensus_value === 'number') ? ev.consensus_value : _numOrNull_(ev.consensus_value),
    prev_revision: (typeof ev.prev_revision === 'number') ? ev.prev_revision : _numOrNull_(ev.prev_revision),
    unit: String(ev.unit || '').trim(),
    importance: ev.importance || 'medium',
    event_family: eventFamily,
    experiment: 'provider_character_direct_expression_capture_v1',
    policy: {
      micro_expression_capture: 'Provide short free-form attention phrases, not labels.',
      no_taxonomy_labels: 'Do not use old Character labels, roles, historical context packs, market context packs, surprise packs, or attention-label scaffolding.',
      keep_compact: 'Keep micro-expression fields short and concrete.',
      basic_event_payload_only: 'Use only event_id, country, indicator_name, release_ts, consensus_value, prev_revision, unit, importance, and event_family.'
    },
    required_output: {
      object: 'ai_prediction',
      event_id: ev.event_id,
      type: ev.type,
      ai_forecast_value: '(number or null)',
      qualitative_result: '(stronger|weaker|inline)',
      rationale_short: '(short string)',
      primary_focus_phrase: '(3-8 words)',
      secondary_focus_phrase: '(3-8 words)',
      ignored_or_discounted_factor_phrase: '(3-8 words)',
      causal_path_phrase: '(3-8 words)',
      failure_condition_phrase: '(3-8 words)',
      confidence_basis_phrase: '(3-8 words)',
      uncertainty_phrase: '(3-8 words)',
      expression_summary_phrase: '(3-8 words)',
      attention_terms: '(short pipe-separated terms)'
    }
  };
  var instruction =
    'Return ONLY strict JSON (no code fences). Keys required: object,event_id,type,ai_forecast_value,qualitative_result,rationale_short,primary_focus_phrase,secondary_focus_phrase,ignored_or_discounted_factor_phrase,causal_path_phrase,failure_condition_phrase,confidence_basis_phrase,uncertainty_phrase,expression_summary_phrase,attention_terms. ' +
    'Use ai_prediction as the object. ' +
    'Micro-expression fields must be short, concrete, and natural, ideally 3 to 8 words each. ' +
    'Do not use old Character labels, hidden roles, taxonomy selection, historical context packs, market context packs, surprise packs, or attention-label scaffolding. ' +
    'Do not give trading instructions or guaranteed-profit language. ' +
    'Use only the basic event payload fields in the prompt: event_id, country, indicator_name, release_ts, consensus_value, prev_revision, unit, importance, and event_family.';
  return {
    system: 'You are a macroeconomic forecasting model. Output must be strict JSON and safe for parsing.',
    user: JSON.stringify(payload),
    instruction: instruction,
    cache_scaffold: ''
  };
}

function _providerCharacterDirectExpressionCaptureNormalizeProviderOutput_(parsed, rawOutput) {
  parsed = parsed || {};
  return {
    object: 'ai_prediction',
    event_id: String(parsed.event_id || '').trim(),
    type: String(parsed.type || '').trim(),
    ai_forecast_value: _numOrNull_(parsed.ai_forecast_value),
    qualitative_result: _providerCharacterFreshReplayQualitativeResult_(parsed.qualitative_result),
    rationale_short: _providerCharacterFreshReplayPhrase_(parsed.rationale_short, 3, 12),
    primary_focus_phrase: _providerCharacterFreshReplayPhrase_(parsed.primary_focus_phrase, 3, 8),
    secondary_focus_phrase: _providerCharacterFreshReplayPhrase_(parsed.secondary_focus_phrase, 3, 8),
    ignored_or_discounted_factor_phrase: _providerCharacterFreshReplayPhrase_(parsed.ignored_or_discounted_factor_phrase, 3, 8),
    causal_path_phrase: _providerCharacterFreshReplayPhrase_(parsed.causal_path_phrase, 3, 8),
    failure_condition_phrase: _providerCharacterFreshReplayPhrase_(parsed.failure_condition_phrase, 3, 8),
    confidence_basis_phrase: _providerCharacterFreshReplayPhrase_(parsed.confidence_basis_phrase, 3, 8),
    uncertainty_phrase: _providerCharacterFreshReplayPhrase_(parsed.uncertainty_phrase, 3, 8),
    expression_summary_phrase: _providerCharacterFreshReplayPhrase_(parsed.expression_summary_phrase, 3, 8),
    attention_terms: _providerCharacterFreshReplayAttentionTerms_(parsed.attention_terms),
    raw_output: String(rawOutput || '').trim()
  };
}

function _providerCharacterDirectExpressionCaptureBetterThanConsensus_(forecastValue, econRow) {
  var ai = _numOrNull_(forecastValue);
  var released = _numOrNull_(econRow && econRow.released_value);
  var consensus = _numOrNull_(econRow && econRow.consensus_value);
  if (ai == null || released == null || consensus == null) return '';
  return Math.abs(ai - released) < Math.abs(consensus - released) ? 'TRUE' : 'FALSE';
}

function _providerCharacterDirectExpressionCaptureBuildClusterRows_(generatedTs, captureRunId, rows, warnings) {
  var out = [];
  var byGroup = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var cohortId = String(row.cohort_id || '').trim();
    if (!provider) continue;
    var key = provider + '|' + cohortId;
    if (!byGroup[key]) byGroup[key] = [];
    byGroup[key].push(row);
  }

  Object.keys(byGroup).sort().forEach(function(key) {
    var parts = key.split('|');
    var provider = parts[0] || '';
    var cohortId = parts[1] || '';
    var groupRows = byGroup[key].slice();
    var clusterRows = _providerCharacterMicroExpressionBuildClusterRows_(generatedTs, groupRows, warnings);
    for (var i = 0; i < clusterRows.length; i++) {
      var row = clusterRows[i] || {};
      row.capture_run_id = captureRunId;
      row.cohort_id = cohortId;
      row.provider = provider;
      row.notes = String(row.notes || '') + '; cohort_id=' + cohortId;
      out.push(row);
    }
  });

  if (!out.length && warnings) warnings.push('direct_expression_clusters_empty');
  return out;
}

function _providerCharacterDirectExpressionCaptureBuildSummaryRows_(generatedTs, captureRunId, allRows, expressionRows, cohortARowsCount, cohortBRowsCount, clusterRows, warnings) {
  var groups = {};
  for (var i = 0; i < (allRows || []).length; i++) {
    var row = allRows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!groups[provider]) groups[provider] = [];
    groups[provider].push(row);
  }
  groups.ALL = allRows || [];

  var out = [];
  Object.keys(groups).sort(function(a, b) {
    if (a === 'ALL') return 1;
    if (b === 'ALL') return -1;
    return a.localeCompare(b);
  }).forEach(function(provider) {
    var providerRows = groups[provider] || [];
    var providerExprRows = providerRows.filter(function(row) {
      return String(row.provider_call_status || '').toLowerCase() !== 'failed';
    });
    var providerClusterRows = (clusterRows || []).filter(function(row) {
      return provider === 'ALL' ? true : String(row.provider || '') === provider;
    });
    var sampledEventMap = {};
    var uniqueExpr = {};
    var successCount = 0;
    var failCount = 0;
    var callCount = 0;
    var dirValues = [];
    var errValues = [];
    var btcValues = [];
    var tokenInputValues = [];
    var tokenOutputValues = [];
    var latencyValues = [];

    for (var i = 0; i < providerRows.length; i++) {
      var row = providerRows[i];
      if (row.event_id) sampledEventMap[row.event_id] = true;
      if (String(row.provider_call_status || '').toLowerCase() === 'success') successCount += 1;
      if (String(row.provider_call_status || '').toLowerCase() === 'failed') failCount += 1;
      if (String(row.provider_call_status || '').toLowerCase() === 'success' || String(row.provider_call_status || '').toLowerCase() === 'failed') callCount += 1;
      if (row.expression_summary_phrase) uniqueExpr[String(row.expression_summary_phrase)] = true;
      var dir = String(row.economic_dir_ok || '').trim().toUpperCase();
      if (dir === 'TRUE' || dir === 'FALSE') dirValues.push(dir === 'TRUE' ? 1 : 0);
      var err = _numOrNull_(row.forecast_error_abs);
      if (err != null) errValues.push(err);
      var btc = String(row.better_than_consensus || '').trim().toUpperCase();
      if (btc === 'TRUE' || btc === 'FALSE') btcValues.push(btc === 'TRUE' ? 1 : 0);
      var ti = _numOrNull_(row.token_input_estimate);
      var to = _numOrNull_(row.token_output_estimate);
      var lat = _numOrNull_(row.latency_ms);
      if (ti != null) tokenInputValues.push(ti);
      if (to != null) tokenOutputValues.push(to);
      if (lat != null) latencyValues.push(lat);
    }

    var strongest = _providerCharacterDirectExpressionCaptureTopClusterPhrases_(providerClusterRows, 3);
    var positiveHints = _providerCharacterDirectExpressionCaptureHintPhrases_(providerClusterRows, true, 3);
    var negativeHints = _providerCharacterDirectExpressionCaptureHintPhrases_(providerClusterRows, false, 3);
    var readiness = _providerCharacterDirectExpressionCaptureDatasetReadiness_(provider, providerRows, providerExprRows, successCount, failCount, providerClusterRows, uniqueExpr);
    var nextStep = _providerCharacterDirectExpressionCaptureNextStep_(readiness, provider, providerRows, providerClusterRows);

    out.push({
      generated_ts: generatedTs,
      capture_run_id: captureRunId,
      total_rows: providerRows.length,
      cohort_a_rows: providerRows.filter(function(row) { return String(row.cohort_id || '') === 'cohort_a_existing_fresh_replay'; }).length,
      cohort_b_rows: providerRows.filter(function(row) { return String(row.cohort_id || '') === 'cohort_b_direct_capture_expansion'; }).length,
      sampled_events: Object.keys(sampledEventMap).length,
      provider: provider,
      successful_provider_calls: successCount,
      failed_provider_calls: failCount,
      economic_dir_ok_rate: _providerCharacterFreshReplayAverage_(dirValues) == null ? '' : _round4_(_providerCharacterFreshReplayAverage_(dirValues)),
      avg_forecast_error_abs: _providerCharacterFreshReplayAverage_(errValues) == null ? '' : _round4_(_providerCharacterFreshReplayAverage_(errValues)),
      better_than_consensus_rate: _providerCharacterFreshReplayAverage_(btcValues) == null ? '' : _round4_(_providerCharacterFreshReplayAverage_(btcValues)),
      unique_expression_count: Object.keys(uniqueExpr).length,
      cluster_count: providerClusterRows.length,
      avg_token_input_estimate: _providerCharacterFreshReplayAverage_(tokenInputValues) == null ? '' : _round4_(_providerCharacterFreshReplayAverage_(tokenInputValues)),
      avg_token_output_estimate: _providerCharacterFreshReplayAverage_(tokenOutputValues) == null ? '' : _round4_(_providerCharacterFreshReplayAverage_(tokenOutputValues)),
      avg_latency_ms: _providerCharacterFreshReplayAverage_(latencyValues) == null ? '' : _round4_(_providerCharacterFreshReplayAverage_(latencyValues)),
      strongest_expression_clusters: strongest.join(' | '),
      early_positive_expression_hints: positiveHints.join(' | '),
      early_negative_expression_hints: negativeHints.join(' | '),
      dataset_readiness: readiness,
      recommended_next_step: nextStep,
      notes: 'total_rows=' + providerRows.length + '; cohort_a_rows=' + providerRows.filter(function(row) { return String(row.cohort_id || '') === 'cohort_a_existing_fresh_replay'; }).length + '; cohort_b_rows=' + providerRows.filter(function(row) { return String(row.cohort_id || '') === 'cohort_b_direct_capture_expansion'; }).length + '; cohort_c_rows=' + providerRows.filter(function(row) { return String(row.cohort_id || '') === 'cohort_c_direct_capture_expansion'; }).length + '; call_rows=' + callCount
    });
  });

  if (!out.length && warnings) warnings.push('direct_expression_summary_empty');
  return out;
}

function _providerCharacterDirectExpressionCaptureTopClusterPhrases_(clusterRows, limit) {
  var list = (clusterRows || []).slice().sort(function(a, b) {
    var as = _numOrNull_(a.provider_specificity_score) || 0;
    var bs = _numOrNull_(b.provider_specificity_score) || 0;
    if (bs !== as) return bs - as;
    if ((b.row_count || 0) !== (a.row_count || 0)) return (b.row_count || 0) - (a.row_count || 0);
    return String(a.cluster_id || '').localeCompare(String(b.cluster_id || ''));
  }).slice(0, limit || 3);
  return list.map(function(item) { return String(item.cluster_phrase || '').trim(); }).filter(Boolean);
}

function _providerCharacterDirectExpressionCaptureHintPhrases_(clusterRows, positive, limit) {
  var filtered = [];
  for (var i = 0; i < (clusterRows || []).length; i++) {
    var row = clusterRows[i] || {};
    var hint = String(row.economic_separation_hint || '').toLowerCase();
    var isPositive = hint.indexOf('higher dir ok') >= 0 || hint.indexOf('lower error') >= 0 || hint.indexOf('higher better-than-consensus') >= 0;
    var isNegative = hint.indexOf('lower dir ok') >= 0 || hint.indexOf('higher error') >= 0 || hint.indexOf('lower better-than-consensus') >= 0;
    if ((positive && isPositive) || (!positive && isNegative)) {
      filtered.push(String(row.cluster_phrase || '').trim());
    }
  }
  return filtered.filter(Boolean).slice(0, limit || 3);
}

function _providerCharacterDirectExpressionCaptureDatasetReadiness_(provider, providerRows, exprRows, successCount, failCount, clusterRows, uniqueExpr) {
  var totalRows = providerRows.length;
  var clusterCount = (clusterRows || []).length;
  var callRows = successCount + failCount;
  var successRate = callRows ? (successCount / callRows) : 0;
  if (!totalRows || successCount <= 0) return 'failed_runtime_or_extraction';
  if (totalRows < 10) return 'needs_more_rows';
  if (clusterCount < 2 || Object.keys(uniqueExpr || {}).length < 5) return 'weak_do_not_scale';
  if (provider !== 'ALL' && callRows < 12) return 'needs_more_rows';
  if (provider === 'ALL' && totalRows >= 90 && successRate >= 0.8 && clusterCount >= 8) return 'ready_for_next_stage_review';
  if (provider !== 'ALL' && successCount >= 8 && clusterCount >= 2 && successRate >= 0.8) return 'ready_for_next_stage_review';
  if (failCount > successCount * 0.5) return 'weak_do_not_scale';
  return 'needs_more_rows';
}

function _providerCharacterDirectExpressionCaptureNextStep_(readiness, provider, providerRows, clusterRows) {
  if (readiness === 'ready_for_next_stage_review') return 'review cohort balance and choose next stage';
  if (readiness === 'needs_more_rows') return 'add more completed events before next-stage review';
  if (readiness === 'provider_specific_only') return 'review provider-specific clusters before scaling';
  if (readiness === 'weak_do_not_scale') return 'hold and inspect extraction quality';
  return 'inspect runtime and extraction path';
}

function _providerCharacterDirectExpressionCaptureBuildMethodologyRows_(generatedTs, captureRunId, freshReplayRowCount, cohortARowsCount, cohortCRowsCount, batchStart, batchSize, existingCaptureRowCount, warnings, options) {
  options = options || {};
  var experimentName = String(options.experiment_name || '').trim() || 'Provider Character v2 — Direct Expression Capture v1';
  var branchName = String(options.branch_name || '').trim() || 'Provider Character v2 / Direct Expression Capture Branch';
  var purpose = String(options.purpose || '').trim() || 'Build a direct provider-expression dataset for later Provider Character v2 research';
  var sampleStrategy = String(options.sample_strategy || '').trim() || 'Reuse the 36 validated fresh replay rows, then add a stratified historical replay slice excluding existing capture event_ids.';
  var notesSuffix = String(options.notes_suffix || '').trim();
  var targetTotalProviderEventRows = String(options.target_total_provider_event_rows || '').trim() || 'approximately 250';
  return [{
    generated_ts: generatedTs,
    capture_run_id: captureRunId,
    experiment_name: experimentName,
    branch_name: branchName,
    purpose: purpose,
    generation_1_proxy_status: 'rejected',
    generation_1_data_used: 'FALSE',
    prior_fresh_replay_rows_reused: 'TRUE',
    target_total_provider_event_rows: targetTotalProviderEventRows,
    provider_calls_made: 'TRUE',
    prediction_runs_made: 'replay_only',
    production_changes: 'FALSE',
    market_reaction_usage: 'FALSE',
    feature_pack_usage: 'FALSE',
    source_sheets_used: 'Provider_Character_Fresh_Replay|Economic_Value_Accuracy|Event',
    sample_strategy: sampleStrategy,
    token_minimization_rule: '3-8 words per micro-expression field; no long rationale; no predefined labels',
    interpretation_rule: 'dataset construction and recurrence-readiness only; no calibration/routing/weighting approval',
    notes: _providerCharacterDirectExpressionCaptureNotes_(
      'fresh_replay_rows=' + freshReplayRowCount,
      'cohort_a_rows=' + cohortARowsCount,
      'cohort_c_rows=' + cohortCRowsCount,
      'batch_start=' + batchStart,
      'batch_size=' + batchSize,
      'existing_capture_rows=' + existingCaptureRowCount,
      'warnings=' + _uniqueStrings_(warnings).join('|'),
      notesSuffix
    )
  }];
}

function _providerCharacterDirectExpressionCaptureNotes_() {
  var out = [];
  for (var i = 0; i < arguments.length; i++) {
    var item = String(arguments[i] == null ? '' : arguments[i]).trim();
    if (item) out.push(item);
  }
  return out.join('; ');
}

function _providerCharacterDirectExpressionCaptureUniqueEventCount_(rows) {
  var seen = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var eventId = String(rows[i] && rows[i].event_id || '').trim();
    if (eventId) seen[eventId] = true;
  }
  return Object.keys(seen).length;
}
