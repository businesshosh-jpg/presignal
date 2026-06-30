/*******************************************************
 * provider_character_direct_expression_economic_link.js
 * - Diagnostic-only Provider Character v2 — Direct Expression Economic Link v1
 * - Reads Provider_Character_Direct_Expression_Capture and recurrence outputs
 * - No provider calls, no predictions, no production changes
 *******************************************************/

function menuBuildProviderCharacterDirectExpressionEconomicLink_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterDirectExpressionEconomicLink_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character direct expression economic link -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Link=' + (res.link_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0),
      'Provider Character Direct Expression Economic Link',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character direct expression economic link -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterDirectExpressionEconomicLink_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var economicLinkRunId = String(params.economic_link_run_id || '').trim() || _uuidFromString_('provider_character_direct_expression_economic_link:' + generatedTs);
  var phase = String(params.phase || 'all').trim().toLowerCase();
  var dryRun = params.dry_run === true || phase === 'dry_run';
  var writeOutput = !dryRun && params.write_output !== false;
  var returnPayloadMode = String(params.return_payload || '').trim().toLowerCase();
  var writeLink = phase === 'all' || phase === 'link' || phase === 'link_only';
  var writeSummary = phase === 'all' || phase === 'summary' || phase === 'summary_only';
  var writeMethodology = phase === 'all' || phase === 'methodology' || phase === 'methodology_only';
  var warnings = [];

  try {
    var sources = params.source_bundle || (!Array.isArray(params.capture_rows) ? _providerCharacterDirectExpressionEconomicLinkLoadSources_(warnings) : {});
    var captureRows = Array.isArray(params.capture_rows)
      ? params.capture_rows
      : _providerCharacterDirectExpressionEconomicLinkReadCaptureRows_(sources.captureBundle, warnings);
    var recurrenceRows = Array.isArray(params.recurrence_rows)
      ? params.recurrence_rows
      : _providerCharacterDirectExpressionEconomicLinkReadRecurrenceRows_(sources.recurrenceBundle, warnings);
    var profileRows = Array.isArray(params.profile_rows)
      ? params.profile_rows
      : _providerCharacterDirectExpressionEconomicLinkReadProviderProfileRows_(sources.profileBundle, warnings);
    var summaryRowsSource = Array.isArray(params.summary_rows_source)
      ? params.summary_rows_source
      : _providerCharacterDirectExpressionEconomicLinkReadSummaryRows_(sources.summaryBundle, warnings);
    var methodologyRowsSource = Array.isArray(params.methodology_rows_source)
      ? params.methodology_rows_source
      : _providerCharacterDirectExpressionEconomicLinkReadMethodologyRows_(sources.methodologyBundle, warnings);

    var captureStats = _providerCharacterDirectExpressionEconomicLinkBuildCaptureStats_(captureRows);
    var baselines = _providerCharacterDirectExpressionEconomicLinkBuildBaselines_(captureRows);
    var clusterPack = _providerCharacterDirectExpressionEconomicLinkBuildClusterPack_(captureRows, warnings);
    var recurrenceLookup = _providerCharacterDirectExpressionEconomicLinkBuildRecurrenceLookup_(recurrenceRows, warnings);
    var providerProfileLookup = _providerCharacterDirectExpressionEconomicLinkBuildProviderProfileLookup_(profileRows, warnings);
    var summaryContext = _providerCharacterDirectExpressionEconomicLinkBuildSummaryContext_(summaryRowsSource, methodologyRowsSource);

    var linkRows = _providerCharacterDirectExpressionEconomicLinkBuildLinkRows_(
      generatedTs,
      economicLinkRunId,
      clusterPack,
      recurrenceLookup,
      baselines,
      providerProfileLookup,
      warnings
    );
    var summaryRows = _providerCharacterDirectExpressionEconomicLinkBuildSummaryRows_(
      generatedTs,
      economicLinkRunId,
      linkRows,
      captureStats,
      baselines,
      summaryContext,
      warnings
    );
    var methodologyRows = _providerCharacterDirectExpressionEconomicLinkBuildMethodologyRows_(
      generatedTs,
      economicLinkRunId,
      captureStats,
      warnings
    );

    if (dryRun) {
    return {
        status: 'ok',
        generated_ts: generatedTs,
        economic_link_run_id: economicLinkRunId,
        dry_run: true,
        source_total_rows: captureStats.total_rows,
        source_total_events: captureStats.total_events,
        cohort_a_rows_included: captureStats.cohort_a_rows,
        cohort_b_rows_included: captureStats.cohort_b_rows,
        cluster_rows: linkRows.length,
        summary_rows: summaryRows.length,
        methodology_rows: methodologyRows.length,
        positive_candidates: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'positive_candidate'),
        negative_candidates: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'negative_candidate'),
        neutral_or_unclear: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'neutral_or_unclear'),
        insufficient_sample: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'insufficient_sample'),
        unstable_or_generic: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'unstable_or_generic'),
        warnings: _uniqueStrings_(warnings),
        preview: {
          first_link_rows: linkRows.slice(0, 3),
          first_summary_rows: summaryRows.slice(0, 3),
          methodology_rows: methodologyRows
        }
      };
    }

    var linkSheet = null;
    var summarySheet = null;
    var methodologySheet = null;

    if (writeOutput && writeLink) {
      linkSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Economic_Link', _providerCharacterDirectExpressionEconomicLinkHeaders_(), warnings);
      _rewriteSheetRowsPreservingHeaders_(
        linkSheet.sheet,
        linkSheet.headers,
        _characterResidualObjectsToRows_(linkRows, linkSheet.headers)
      );
    }
    if (writeOutput && writeSummary) {
      summarySheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Economic_Link_Summary', _providerCharacterDirectExpressionEconomicLinkSummaryHeaders_(), warnings);
      _rewriteSheetRowsPreservingHeaders_(
        summarySheet.sheet,
        summarySheet.headers,
        _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
      );
    }
    if (writeOutput && writeMethodology) {
      methodologySheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Economic_Link_Methodology', _providerCharacterDirectExpressionEconomicLinkMethodologyHeaders_(), warnings);
      _rewriteSheetRowsPreservingHeaders_(
        methodologySheet.sheet,
        methodologySheet.headers,
        _characterResidualObjectsToRows_(methodologyRows, methodologySheet.headers)
      );
    }

    var result = {
      status: 'ok',
      generated_ts: generatedTs,
      economic_link_run_id: economicLinkRunId,
      link_sheet: linkSheet ? linkSheet.sheet.getName() : '',
      summary_sheet: summarySheet ? summarySheet.sheet.getName() : '',
      methodology_sheet: methodologySheet ? methodologySheet.sheet.getName() : '',
      source_total_rows: captureStats.total_rows,
      cohort_a_rows_included: captureStats.cohort_a_rows,
      cohort_b_rows_included: captureStats.cohort_b_rows,
      clusters_tested: linkRows.length,
      positive_candidates: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'positive_candidate'),
      negative_candidates: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'negative_candidate'),
      neutral_or_unclear: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'neutral_or_unclear'),
      insufficient_sample: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'insufficient_sample'),
      unstable_or_generic: _providerCharacterDirectExpressionEconomicLinkCountBy_(linkRows, 'unstable_or_generic'),
      link_rows_written: linkRows.length,
      summary_rows_written: summaryRows.length,
      methodology_rows_written: methodologyRows.length,
      warnings: _uniqueStrings_(warnings)
    };
    if (!writeOutput) {
      if (returnPayloadMode === 'link' || returnPayloadMode === 'all' || !returnPayloadMode) {
        result.link_rows = linkRows;
      }
      if (returnPayloadMode === 'summary' || returnPayloadMode === 'all') {
        result.summary_rows = summaryRows;
      }
      if (returnPayloadMode === 'methodology' || returnPayloadMode === 'all') {
        result.methodology_rows = methodologyRows;
      }
    }
    return result;
  } catch (e) {
    return {
      status: 'error',
      generated_ts: generatedTs,
      economic_link_run_id: economicLinkRunId,
      error_message: (e && e.stack) ? e.stack : String(e),
      warnings: _uniqueStrings_(warnings)
    };
  }
}

function buildProviderCharacterDirectExpressionEconomicLink(params) {
  return buildProviderCharacterDirectExpressionEconomicLink_(params || {});
}

function _providerCharacterDirectExpressionEconomicLinkHeaders_() {
  return [
    'generated_ts',
    'economic_link_run_id',
    'cluster_id',
    'cluster_phrase',
    'expression_field_source',
    'provider',
    'scope',
    'total_rows',
    'event_count',
    'cohort_distribution',
    'family_distribution',
    'recurrence_strength',
    'provider_specificity_score',
    'stable_character_candidate_flag',
    'economic_dir_ok_count',
    'economic_dir_ok_rate',
    'better_than_consensus_count',
    'better_than_consensus_rate',
    'avg_forecast_error_abs',
    'baseline_economic_dir_ok_rate',
    'baseline_better_than_consensus_rate',
    'baseline_avg_forecast_error_abs',
    'economic_dir_ok_delta_vs_baseline',
    'better_than_consensus_delta_vs_baseline',
    'forecast_error_delta_vs_baseline',
    'sample_warning',
    'link_strength',
    'interpretation',
    'notes'
  ];
}

function _providerCharacterDirectExpressionEconomicLinkSummaryHeaders_() {
  return [
    'generated_ts',
    'economic_link_run_id',
    'scope',
    'provider',
    'outcome_family',
    'total_rows',
    'total_events',
    'clusters_tested',
    'positive_candidates',
    'negative_candidates',
    'neutral_or_unclear',
    'insufficient_sample',
    'best_positive_clusters',
    'worst_negative_clusters',
    'economic_dir_ok_rate',
    'better_than_consensus_rate',
    'avg_forecast_error_abs',
    'baseline_economic_dir_ok_rate',
    'baseline_better_than_consensus_rate',
    'baseline_avg_forecast_error_abs',
    'overall_result',
    'dataset_status',
    'recommended_next_step',
    'what_is_supported',
    'what_is_not_supported',
    'notes'
  ];
}

function _providerCharacterDirectExpressionEconomicLinkMethodologyHeaders_() {
  return [
    'generated_ts',
    'economic_link_run_id',
    'experiment_name',
    'branch_name',
    'source_capture_sheet',
    'source_recurrence_sheet',
    'source_total_rows',
    'cohort_a_rows_included',
    'cohort_b_rows_included',
    'accepted_provider_call_statuses',
    'generation_1_data_used',
    'fresh_vs_original_comparison_used',
    'old_attention_labels_used_as_seed',
    'ai_provider_calls_made',
    'prediction_runs_made',
    'production_changes',
    'market_reaction_primary_target',
    'accuracy_linkage_tested',
    'routing_approved',
    'weighting_approved',
    'calibration_approved',
    'interpretation_rule',
    'notes'
  ];
}

function _providerCharacterDirectExpressionEconomicLinkLoadSources_(warnings) {
  return {
    captureBundle: _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false),
    recurrenceBundle: _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Recurrence', warnings, false),
    profileBundle: _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Provider_Profile', warnings, false),
    summaryBundle: _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Recurrence_Summary', warnings, false),
    methodologyBundle: _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Recurrence_Methodology', warnings, false)
  };
}

function _providerCharacterDirectExpressionEconomicLinkReadCaptureRows_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var status = String(row.provider_call_status || '').trim().toLowerCase();
    if (status !== 'success' && status !== 'reused') continue;
    if (!String(row.cohort_id || '').trim()) continue;
    if (!String(row.event_id || '').trim()) continue;
    if (!String(row.provider || '').trim()) continue;
    if (!_providerCharacterDirectExpressionEconomicLinkHasExpression_(row)) continue;
    out.push(row);
  }
  if (!out.length && warnings) warnings.push('economic_link_capture_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkHasExpression_(row) {
  return !!(
    String(row.primary_focus_phrase || '').trim() ||
    String(row.secondary_focus_phrase || '').trim() ||
    String(row.ignored_or_discounted_factor_phrase || '').trim() ||
    String(row.causal_path_phrase || '').trim() ||
    String(row.failure_condition_phrase || '').trim() ||
    String(row.confidence_basis_phrase || '').trim() ||
    String(row.uncertainty_phrase || '').trim() ||
    String(row.expression_summary_phrase || '').trim() ||
    String(row.attention_terms || '').trim()
  );
}

function _providerCharacterDirectExpressionEconomicLinkReadRecurrenceRows_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (!String(row.cluster_id || '').trim()) continue;
    out.push(row);
  }
  if (!out.length && warnings) warnings.push('economic_link_recurrence_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkReadProviderProfileRows_(bundle, warnings) {
  return _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
}

function _providerCharacterDirectExpressionEconomicLinkReadSummaryRows_(bundle, warnings) {
  return _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
}

function _providerCharacterDirectExpressionEconomicLinkReadMethodologyRows_(bundle, warnings) {
  return _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
}

function _providerCharacterDirectExpressionEconomicLinkBuildCaptureStats_(rows) {
  var out = {
    total_rows: 0,
    total_events: 0,
    cohort_a_rows: 0,
    cohort_b_rows: 0,
    event_ids: {},
    provider_event_ids: {},
    provider_events: {}
  };
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (!eventId) continue;
    out.total_rows += 1;
    if (!out.event_ids[eventId]) {
      out.event_ids[eventId] = true;
      out.total_events += 1;
    }
    if (provider) {
      if (!out.provider_event_ids[provider]) out.provider_event_ids[provider] = {};
      if (!out.provider_event_ids[provider][eventId]) {
        out.provider_event_ids[provider][eventId] = true;
        if (!out.provider_events[provider]) out.provider_events[provider] = 0;
        out.provider_events[provider] += 1;
      }
    }
    var cohort = String(row.cohort_id || '').trim().toLowerCase();
    if (cohort.indexOf('cohort_a') === 0 || String(row.provider_call_status || '').trim().toLowerCase() === 'reused') {
      out.cohort_a_rows += 1;
    } else if (cohort.indexOf('cohort_b') === 0 || String(row.provider_call_status || '').trim().toLowerCase() === 'success') {
      out.cohort_b_rows += 1;
    }
  }
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkBuildBaselines_(rows) {
  var baselines = {
    all: _providerCharacterDirectExpressionEconomicLinkInitBaseline_('ALL'),
    provider: {},
    provider_family: {}
  };
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var family = String(row.outcome_family || '').trim() || 'other';
    if (!provider) continue;
    if (!baselines.provider[provider]) baselines.provider[provider] = _providerCharacterDirectExpressionEconomicLinkInitBaseline_(provider);
    var familyKey = provider + '|' + family;
    if (!baselines.provider_family[familyKey]) baselines.provider_family[familyKey] = _providerCharacterDirectExpressionEconomicLinkInitBaseline_(familyKey);
    _providerCharacterDirectExpressionEconomicLinkAddBaselineRow_(baselines.all, row);
    _providerCharacterDirectExpressionEconomicLinkAddBaselineRow_(baselines.provider[provider], row);
    _providerCharacterDirectExpressionEconomicLinkAddBaselineRow_(baselines.provider_family[familyKey], row);
  }
  Object.keys(baselines.provider).forEach(function(key) {
    _providerCharacterDirectExpressionEconomicLinkFinalizeBaseline_(baselines.provider[key]);
  });
  Object.keys(baselines.provider_family).forEach(function(key) {
    _providerCharacterDirectExpressionEconomicLinkFinalizeBaseline_(baselines.provider_family[key]);
  });
  _providerCharacterDirectExpressionEconomicLinkFinalizeBaseline_(baselines.all);
  return baselines;
}

function _providerCharacterDirectExpressionEconomicLinkInitBaseline_(label) {
  return {
    label: label,
    total_rows: 0,
    total_events: 0,
    event_ids: {},
    dir_ok_count: 0,
    dir_ok_rows: 0,
    better_count: 0,
    better_rows: 0,
    error_sum: 0,
    error_count: 0
  };
}

function _providerCharacterDirectExpressionEconomicLinkAddBaselineRow_(baseline, row) {
  baseline.total_rows += 1;
  var eventId = String(row.event_id || '').trim();
  if (eventId && !baseline.event_ids[eventId]) {
    baseline.event_ids[eventId] = true;
    baseline.total_events += 1;
  }
  var dir = _providerCharacterDirectExpressionEconomicLinkBool_(row.economic_dir_ok);
  if (dir != null) {
    baseline.dir_ok_rows += 1;
    if (dir) baseline.dir_ok_count += 1;
  }
  var better = _providerCharacterDirectExpressionEconomicLinkBool_(row.better_than_consensus);
  if (better != null) {
    baseline.better_rows += 1;
    if (better) baseline.better_count += 1;
  }
  var err = _numOrNull_(row.forecast_error_abs);
  if (err != null) {
    baseline.error_sum += Number(err || 0);
    baseline.error_count += 1;
  }
}

function _providerCharacterDirectExpressionEconomicLinkFinalizeBaseline_(baseline) {
  baseline.economic_dir_ok_rate = baseline.dir_ok_rows ? _round4_(baseline.dir_ok_count / baseline.dir_ok_rows) : '';
  baseline.better_than_consensus_rate = baseline.better_rows ? _round4_(baseline.better_count / baseline.better_rows) : '';
  baseline.avg_forecast_error_abs = baseline.error_count ? _round4_(baseline.error_sum / baseline.error_count) : '';
}

function _providerCharacterDirectExpressionEconomicLinkBuildClusterPack_(rows, warnings) {
  var clusters = [];
  var threshold = 0.37;
  var ordered = (rows || []).slice().sort(function(a, b) {
    var ap = String(a.provider || '');
    var bp = String(b.provider || '');
    if (ap !== bp) return ap.localeCompare(bp);
    if (String(a.release_ts || '') !== String(b.release_ts || '')) return String(a.release_ts || '').localeCompare(String(b.release_ts || ''));
    return String(a.event_id || '').localeCompare(String(b.event_id || ''));
  });

  for (var i = 0; i < ordered.length; i++) {
    var row = _providerCharacterDirectExpressionRecurrenceNormalizeRow_(ordered[i] || {});
    var bestIdx = -1;
    var bestScore = 0;
    for (var c = 0; c < clusters.length; c++) {
      var cluster = clusters[c];
      var score = _providerCharacterDirectExpressionRecurrenceSimilarity_(row, row.tokens, cluster.representative_row, cluster.representative_tokens);
      if (score > bestScore) {
        bestScore = score;
        bestIdx = c;
      }
    }
    if (bestIdx >= 0 && bestScore >= threshold) {
      _providerCharacterDirectExpressionEconomicLinkAddRowToCluster_(clusters[bestIdx], row, bestScore);
    } else {
      clusters.push(_providerCharacterDirectExpressionEconomicLinkNewCluster_(row, bestScore));
    }
  }

  var out = [];
  for (var j = 0; j < clusters.length; j++) {
    var cluster = clusters[j];
    _providerCharacterDirectExpressionEconomicLinkFinalizeCluster_(cluster);
    if (cluster.total_row_count < 2 || cluster.event_count < 2) continue;
    out.push(cluster);
  }

  out.sort(function(a, b) {
    var as = _numOrNull_(a.recurrence_strength) || 0;
    var bs = _numOrNull_(b.recurrence_strength) || 0;
    if (bs !== as) return bs - as;
    var ap = _numOrNull_(a.provider_specificity_score) || 0;
    var bp = _numOrNull_(b.provider_specificity_score) || 0;
    if (bp !== ap) return bp - ap;
    if ((b.total_row_count || 0) !== (a.total_row_count || 0)) return (b.total_row_count || 0) - (a.total_row_count || 0);
    return String(a.cluster_phrase || '').localeCompare(String(b.cluster_phrase || ''));
  });

  if (!out.length && warnings) warnings.push('economic_link_clusters_empty');
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkNewCluster_(row, similarity) {
  var provider = String(row.provider || '').trim();
  var sourceField = String(row.source_field || _providerCharacterDirectExpressionRecurrenceBestFieldSource_(row)).trim();
  return {
    rows: [row],
    representative_row: row,
    representative_tokens: (row.tokens || []).slice(),
    token_counts: _providerCharacterDirectExpressionEconomicLinkTokenCounts_(row.tokens || []),
    attention_token_counts: _providerCharacterDirectExpressionEconomicLinkTokenCounts_(row.attention_tokens || []),
    source_field_counts: (function() { var m = {}; m[sourceField] = 1; return m; })(),
    provider_counts: (function() { var m = {}; m[provider] = 1; return m; })(),
    family_counts: (function() { var m = {}; m[String(row.outcome_family || 'other').trim() || 'other'] = 1; return m; })(),
    cohort_counts: (function() { var m = {}; m[String(row.cohort_id || 'unknown').trim() || 'unknown'] = 1; return m; })(),
    event_ids: (function() { var m = {}; m[String(row.event_id || '').trim()] = true; return m; })(),
    similarity_sum: Number(similarity || 0),
    similarity_count: 0,
    consensus_values: [],
    forecast_error_values: [],
    better_than_values: [],
    dir_ok_values: [],
    recurrence_signature_counts: (function() { var m = {}; m[row.recurrence_signature] = 1; return m; })()
  };
}

function _providerCharacterDirectExpressionEconomicLinkTokenCounts_(tokens) {
  return _providerCharacterDirectExpressionRecurrenceTokenCounts_(tokens || []);
}

function _providerCharacterDirectExpressionEconomicLinkMergeCounts_(base, extra) {
  return _providerCharacterDirectExpressionRecurrenceMergeCounts_(base || {}, extra || {});
}

function _providerCharacterDirectExpressionEconomicLinkAddRowToCluster_(cluster, row, similarity) {
  cluster.rows.push(row);
  cluster.token_counts = _providerCharacterDirectExpressionEconomicLinkMergeCounts_(cluster.token_counts, _providerCharacterDirectExpressionEconomicLinkTokenCounts_(row.tokens || []));
  cluster.attention_token_counts = _providerCharacterDirectExpressionEconomicLinkMergeCounts_(cluster.attention_token_counts, _providerCharacterDirectExpressionEconomicLinkTokenCounts_(row.attention_tokens || []));
  var sourceField = String(row.source_field || _providerCharacterDirectExpressionRecurrenceBestFieldSource_(row)).trim();
  cluster.source_field_counts[sourceField] = (cluster.source_field_counts[sourceField] || 0) + 1;
  var provider = String(row.provider || '').trim();
  cluster.provider_counts[provider] = (cluster.provider_counts[provider] || 0) + 1;
  var family = String(row.outcome_family || 'other').trim() || 'other';
  cluster.family_counts[family] = (cluster.family_counts[family] || 0) + 1;
  var cohort = String(row.cohort_id || 'unknown').trim() || 'unknown';
  cluster.cohort_counts[cohort] = (cluster.cohort_counts[cohort] || 0) + 1;
  cluster.event_ids[String(row.event_id || '').trim()] = true;
  cluster.similarity_sum += Number(similarity || 0);
  cluster.similarity_count += 1;
  cluster.consensus_values.push(_numOrNull_(row.consensus_value));
  cluster.forecast_error_values.push(_numOrNull_(row.forecast_error_abs));
  cluster.better_than_values.push(_providerCharacterDirectExpressionEconomicLinkBoolToNum_(row.better_than_consensus));
  cluster.dir_ok_values.push(_providerCharacterDirectExpressionEconomicLinkBoolToNum_(row.economic_dir_ok));
  if (_providerCharacterDirectExpressionEconomicLinkShouldReplaceRepresentative_(cluster.representative_row, row)) {
    cluster.representative_row = row;
    cluster.representative_tokens = (row.tokens || []).slice();
  }
}

function _providerCharacterDirectExpressionEconomicLinkShouldReplaceRepresentative_(existing, candidate) {
  if (!existing) return true;
  var candidateSummary = String(candidate.expression_summary_phrase || '').length;
  var existingSummary = String(existing.expression_summary_phrase || '').length;
  if (candidateSummary !== existingSummary) return candidateSummary > existingSummary;
  var candidateTokenCount = (candidate.tokens || []).length;
  var existingTokenCount = (existing.tokens || []).length;
  if (candidateTokenCount !== existingTokenCount) return candidateTokenCount > existingTokenCount;
  var candidateSource = String(candidate.source_field || '').trim();
  var existingSource = String(existing.source_field || '').trim();
  if (candidateSource !== existingSource) {
    var candidatePriority = _providerCharacterDirectExpressionEconomicLinkFieldSourcePriority_(candidateSource);
    var existingPriority = _providerCharacterDirectExpressionEconomicLinkFieldSourcePriority_(existingSource);
    if (candidatePriority !== existingPriority) return candidatePriority > existingPriority;
  }
  return false;
}

function _providerCharacterDirectExpressionEconomicLinkFieldSourcePriority_(field) {
  var map = {
    expression_summary_phrase: 9,
    causal_path_phrase: 8,
    primary_focus_phrase: 7,
    secondary_focus_phrase: 6,
    failure_condition_phrase: 5,
    confidence_basis_phrase: 5,
    uncertainty_phrase: 5,
    ignored_or_discounted_factor_phrase: 4,
    attention_terms: 3
  };
  return map[String(field || '').trim()] || 0;
}

function _providerCharacterDirectExpressionEconomicLinkFinalizeCluster_(cluster) {
  var providerCounts = cluster.provider_counts || {};
  var providers = Object.keys(providerCounts).sort();
  var dominantProvider = '';
  var dominantProviderCount = 0;
  for (var i = 0; i < providers.length; i++) {
    var provider = providers[i];
    var count = Number(providerCounts[provider] || 0);
    if (count > dominantProviderCount || (count === dominantProviderCount && provider < dominantProvider)) {
      dominantProvider = provider;
      dominantProviderCount = count;
    }
  }
  cluster.providers_present = providers;
  cluster.providers_present_count = providers.length;
  cluster.dominant_provider = dominantProvider;
  cluster.dominant_provider_count = dominantProviderCount;
  cluster.total_row_count = cluster.rows.length;
  cluster.event_count = Object.keys(cluster.event_ids || {}).length;
  cluster.family_count = Object.keys(cluster.family_counts || {}).length;
  cluster.cohort_count = Object.keys(cluster.cohort_counts || {}).length;
  cluster.expression_field_source = _providerCharacterDirectExpressionRecurrenceModeKey_(cluster.source_field_counts);
  cluster.representative_example = _providerCharacterDirectExpressionEconomicLinkRepresentativeExample_(cluster.rows, cluster.representative_row);
  cluster.representative_terms = _providerCharacterMicroExpressionTopTermPhrase_(cluster.token_counts || {});
  cluster.cluster_phrase = _providerCharacterDirectExpressionEconomicLinkClusterPhrase_(cluster);
  cluster.family_distribution = _providerCharacterDirectExpressionEconomicLinkCountsText_(cluster.family_counts);
  cluster.cohort_distribution = _providerCharacterDirectExpressionEconomicLinkCountsText_(cluster.cohort_counts);
  cluster.provider_row_counts = _providerCharacterDirectExpressionEconomicLinkProviderCountsText_(cluster.provider_counts);
  cluster.average_similarity = cluster.similarity_count ? _round4_(cluster.similarity_sum / cluster.similarity_count) : '';
  cluster.cross_provider_overlap_rate = _round4_(cluster.providers_present_count / 3);
  cluster.provider_specificity_score = cluster.total_row_count ? _round4_(dominantProviderCount / cluster.total_row_count) : '';
  cluster.generic_expression_score = _providerCharacterDirectExpressionEconomicLinkGenericExpressionScore_(cluster);
  cluster.recurrence_strength = _providerCharacterDirectExpressionEconomicLinkRecurrenceStrength_(cluster);
  cluster.stable_character_candidate_flag = _providerCharacterDirectExpressionEconomicLinkStableFlag_(cluster);
  cluster.notes = _providerCharacterDirectExpressionEconomicLinkClusterNotes_(cluster);
}

function _providerCharacterDirectExpressionEconomicLinkRepresentativeExample_(rows, representativeRow) {
  var examples = [];
  var seen = {};
  function addIf(text) {
    var phrase = _providerCharacterMicroExpressionTrimWords_(String(text || '').trim(), 3, 8);
    if (!phrase || seen[phrase]) return;
    seen[phrase] = true;
    examples.push(phrase);
  }
  addIf(representativeRow && representativeRow.expression_summary_phrase);
  addIf(representativeRow && representativeRow.primary_focus_phrase);
  for (var i = 0; i < (rows || []).length && examples.length < 2; i++) {
    var row = rows[i] || {};
    addIf(row.expression_summary_phrase || row.primary_focus_phrase || row.causal_path_phrase);
  }
  return examples.join(' | ');
}

function _providerCharacterDirectExpressionEconomicLinkClusterPhrase_(cluster) {
  var row = cluster.representative_row || (cluster.rows && cluster.rows[0]) || {};
  var phrases = [
    row.expression_summary_phrase,
    row.causal_path_phrase,
    row.primary_focus_phrase,
    row.secondary_focus_phrase
  ];
  for (var i = 0; i < phrases.length; i++) {
    var phrase = _providerCharacterMicroExpressionTrimWords_(String(phrases[i] || '').trim(), 3, 8);
    if (phrase) return phrase;
  }
  return _providerCharacterMicroExpressionTrimWords_(cluster.representative_terms || 'recurring expression', 3, 8);
}

function _providerCharacterDirectExpressionEconomicLinkCountsText_(map) {
  var arr = [];
  Object.keys(map || {}).forEach(function(key) {
    arr.push({ key: key, count: Number(map[key] || 0) });
  });
  arr.sort(function(a, b) {
    if (b.count !== a.count) return b.count - a.count;
    return String(a.key).localeCompare(String(b.key));
  });
  return arr.map(function(item) { return item.key + '(' + item.count + ')'; }).join('|');
}

function _providerCharacterDirectExpressionEconomicLinkProviderCountsText_(map) {
  return _providerCharacterDirectExpressionEconomicLinkCountsText_(map);
}

function _providerCharacterDirectExpressionEconomicLinkGenericExpressionScore_(cluster) {
  var genericTokens = _providerCharacterDirectExpressionRecurrenceGenericTokens_();
  var tokenCounts = cluster.token_counts || {};
  var total = 0;
  var genericHits = 0;
  Object.keys(tokenCounts).forEach(function(token) {
    var count = Number(tokenCounts[token] || 0);
    total += count;
    if (genericTokens[token]) genericHits += count;
  });
  var tokenRatio = total ? (genericHits / total) : 0;
  var overlapRate = _numOrNull_(cluster.cross_provider_overlap_rate) || 0;
  var specificityPenalty = cluster.provider_specificity_score != null ? (1 - Number(cluster.provider_specificity_score || 0)) : 0;
  return _round4_(Math.max(0, Math.min(1, (tokenRatio * 0.42) + (overlapRate * 0.33) + (specificityPenalty * 0.25))));
}

function _providerCharacterDirectExpressionEconomicLinkRecurrenceStrength_(cluster) {
  var rowScore = Math.min(1, cluster.total_row_count / 5);
  var eventScore = Math.min(1, cluster.event_count / 4);
  var familyScore = Math.min(1, cluster.family_count / 3);
  var consistencyScore = _numOrNull_(cluster.average_similarity) == null ? 0 : Number(cluster.average_similarity || 0);
  var score = (rowScore * 0.30) + (eventScore * 0.25) + (familyScore * 0.15) + (consistencyScore * 0.30);
  return _round4_(Math.max(0, Math.min(1, score)));
}

function _providerCharacterDirectExpressionEconomicLinkStableFlag_(cluster) {
  var rowCount = Number(cluster.total_row_count || 0);
  var eventCount = Number(cluster.event_count || 0);
  var recurrenceStrength = _numOrNull_(cluster.recurrence_strength) || 0;
  var genericScore = _numOrNull_(cluster.generic_expression_score) || 0;
  var providerSpecificity = _numOrNull_(cluster.provider_specificity_score) || 0;
  if (rowCount < 2 || eventCount < 2) return 'FALSE';
  if (genericScore >= 0.75) return 'FALSE';
  if (recurrenceStrength >= 0.55 && (providerSpecificity >= 0.6 || cluster.family_count >= 2)) return 'TRUE';
  return 'FALSE';
}

function _providerCharacterDirectExpressionEconomicLinkClusterNotes_(cluster) {
  return [
    'source_field=' + String(cluster.expression_field_source || ''),
    'avg_similarity=' + String(cluster.average_similarity || ''),
    'provider_specificity=' + String(cluster.provider_specificity_score || ''),
    'generic_score=' + String(cluster.generic_expression_score || '')
  ].join('; ');
}

function _providerCharacterDirectExpressionEconomicLinkBuildRecurrenceLookup_(rows, warnings) {
  var keyed = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = _providerCharacterDirectExpressionEconomicLinkClusterKeyFromRow_(row);
    if (!key) continue;
    if (!keyed[key] || Number(_numOrNull_(row.recurrence_strength) || 0) > Number(_numOrNull_(keyed[key].recurrence_strength) || 0)) {
      keyed[key] = row;
    }
  }
  if (!Object.keys(keyed).length && warnings) warnings.push('economic_link_recurrence_lookup_empty');
  return keyed;
}

function _providerCharacterDirectExpressionEconomicLinkClusterKeyFromRow_(row) {
  row = row || {};
  return [
    String(row.cluster_phrase || '').trim().toLowerCase(),
    String(row.dominant_provider || '').trim().toLowerCase(),
    String(row.provider_row_counts || '').trim().toLowerCase(),
    String(row.total_row_count || '').trim(),
    String(row.event_count || '').trim(),
    String(row.family_count || '').trim(),
    String(row.expression_field_source || '').trim().toLowerCase()
  ].join('|');
}

function _providerCharacterDirectExpressionEconomicLinkClusterKeyFromCluster_(cluster) {
  cluster = cluster || {};
  return [
    String(cluster.cluster_phrase || '').trim().toLowerCase(),
    String(cluster.dominant_provider || '').trim().toLowerCase(),
    String(cluster.provider_row_counts || '').trim().toLowerCase(),
    String(cluster.total_row_count || '').trim(),
    String(cluster.event_count || '').trim(),
    String(cluster.family_count || '').trim(),
    String(cluster.expression_field_source || '').trim().toLowerCase()
  ].join('|');
}

function _providerCharacterDirectExpressionEconomicLinkBuildProviderProfileLookup_(rows, warnings) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    out[provider] = row;
  }
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkBuildSummaryContext_(summaryRows, methodologyRows) {
  var out = {
    recurrence_result: '',
    dataset_status: '',
    summary_note: '',
    methodology_note: ''
  };
  for (var i = 0; i < (summaryRows || []).length; i++) {
    var row = summaryRows[i] || {};
    if (String(row.scope || '').trim().toLowerCase() === 'all') {
      out.recurrence_result = String(row.recurrence_result || '').trim();
      out.dataset_status = String(row.dataset_status || '').trim();
      out.summary_note = String(row.notes || '').trim();
      break;
    }
  }
  if ((methodologyRows || []).length) {
    out.methodology_note = String(methodologyRows[0].notes || '').trim();
  }
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkBuildLinkRows_(generatedTs, economicLinkRunId, clusterPack, recurrenceLookup, baselines, providerProfileLookup, warnings) {
  var out = [];
  for (var i = 0; i < (clusterPack || []).length; i++) {
    var cluster = clusterPack[i] || {};
    var clusterKey = _providerCharacterDirectExpressionEconomicLinkClusterKeyFromCluster_(cluster);
    var recurrenceRow = recurrenceLookup[clusterKey] || null;
    if (!recurrenceRow) {
      warnings.push('cluster_match_missing:' + String(cluster.cluster_phrase || ''));
      continue;
    }

    var providerGroups = _providerCharacterDirectExpressionEconomicLinkGroupRowsByProvider_(cluster.rows || []);
    var providers = Object.keys(providerGroups).sort();
    for (var p = 0; p < providers.length; p++) {
      var provider = providers[p];
      var providerRows = providerGroups[provider] || [];
      if (!providerRows.length) continue;
        var providerMetrics = _providerCharacterDirectExpressionEconomicLinkComputeOutcomeStats_(providerRows);
        var familyMode = _providerCharacterDirectExpressionEconomicLinkDominantFamily_(providerRows);
        var baselineChoice = _providerCharacterDirectExpressionEconomicLinkChooseBaseline_(provider, cluster, providerRows, familyMode, baselines);
        var baselineStats = baselineChoice.stats;
        var sampleWarning = _providerCharacterDirectExpressionEconomicLinkSampleWarning_(cluster, providerRows, familyMode, providerProfileLookup);
        var linkStrength = _providerCharacterDirectExpressionEconomicLinkClassifyLink_(cluster, providerRows, providerMetrics, baselineStats, sampleWarning);
        out.push({
        generated_ts: generatedTs,
        economic_link_run_id: economicLinkRunId,
        cluster_id: String(recurrenceRow.cluster_id || '').trim(),
        cluster_phrase: String(recurrenceRow.cluster_phrase || '').trim(),
        expression_field_source: String(recurrenceRow.expression_field_source || '').trim(),
        provider: provider,
        scope: _providerCharacterDirectExpressionEconomicLinkScope_(cluster, providerRows, recurrenceRow),
        total_rows: providerMetrics.total_rows,
        event_count: providerMetrics.event_count,
        cohort_distribution: _providerCharacterDirectExpressionEconomicLinkCountsText_(providerMetrics.cohorts),
        family_distribution: _providerCharacterDirectExpressionEconomicLinkCountsText_(providerMetrics.families),
        recurrence_strength: recurrenceRow.recurrence_strength,
        provider_specificity_score: recurrenceRow.provider_specificity_score,
        stable_character_candidate_flag: recurrenceRow.stable_character_candidate_flag,
        economic_dir_ok_count: providerMetrics.dir_ok_count,
        economic_dir_ok_rate: providerMetrics.economic_dir_ok_rate,
        better_than_consensus_count: providerMetrics.better_than_count,
        better_than_consensus_rate: providerMetrics.better_than_consensus_rate,
        avg_forecast_error_abs: providerMetrics.avg_forecast_error_abs,
        baseline_economic_dir_ok_rate: baselineStats.economic_dir_ok_rate,
        baseline_better_than_consensus_rate: baselineStats.better_than_consensus_rate,
        baseline_avg_forecast_error_abs: baselineStats.avg_forecast_error_abs,
        economic_dir_ok_delta_vs_baseline: _providerCharacterDirectExpressionEconomicLinkRateDelta_(providerMetrics.economic_dir_ok_rate, baselineStats.economic_dir_ok_rate),
        better_than_consensus_delta_vs_baseline: _providerCharacterDirectExpressionEconomicLinkRateDelta_(providerMetrics.better_than_consensus_rate, baselineStats.better_than_consensus_rate),
        forecast_error_delta_vs_baseline: _providerCharacterDirectExpressionEconomicLinkErrorDelta_(providerMetrics.avg_forecast_error_abs, baselineStats.avg_forecast_error_abs),
        sample_warning: sampleWarning,
        link_strength: linkStrength,
        interpretation: _providerCharacterDirectExpressionEconomicLinkInterpretation_(linkStrength, cluster, providerMetrics, baselineStats, sampleWarning, baselineChoice),
        notes: _providerCharacterDirectExpressionEconomicLinkNotes_(cluster, providerRows, baselineChoice, sampleWarning, recurrenceRow),
        __event_ids: _providerCharacterDirectExpressionEconomicLinkEventIdMap_(providerRows)
      });
    }
  }

  out.sort(function(a, b) {
    if (a.provider !== b.provider) return a.provider.localeCompare(b.provider);
    var as = _providerCharacterDirectExpressionEconomicLinkStrengthOrder_(a.link_strength);
    var bs = _providerCharacterDirectExpressionEconomicLinkStrengthOrder_(b.link_strength);
    if (bs !== as) return bs - as;
    if ((b.total_rows || 0) !== (a.total_rows || 0)) return (b.total_rows || 0) - (a.total_rows || 0);
    return String(a.cluster_phrase || '').localeCompare(String(b.cluster_phrase || ''));
  });

  if (!out.length && warnings) warnings.push('economic_link_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkGroupRowsByProvider_(rows) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!out[provider]) out[provider] = [];
    out[provider].push(row);
  }
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkComputeOutcomeStats_(rows) {
  var stats = {
    total_rows: 0,
    event_count: 0,
    events: {},
    cohorts: {},
    families: {},
    dir_ok_count: 0,
    dir_ok_rows: 0,
    better_count: 0,
    better_rows: 0,
    error_sum: 0,
    error_count: 0,
    economic_dir_ok_rate: '',
    better_than_consensus_rate: '',
    avg_forecast_error_abs: ''
  };
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    stats.total_rows += 1;
    var eventId = String(row.event_id || '').trim();
    if (eventId && !stats.events[eventId]) {
      stats.events[eventId] = true;
      stats.event_count += 1;
    }
    var cohort = String(row.cohort_id || 'unknown').trim() || 'unknown';
    stats.cohorts[cohort] = (stats.cohorts[cohort] || 0) + 1;
    var family = String(row.outcome_family || 'other').trim() || 'other';
    stats.families[family] = (stats.families[family] || 0) + 1;
    var dir = _providerCharacterDirectExpressionEconomicLinkBool_(row.economic_dir_ok);
    if (dir != null) {
      stats.dir_ok_rows += 1;
      if (dir) stats.dir_ok_count += 1;
    }
    var better = _providerCharacterDirectExpressionEconomicLinkBool_(row.better_than_consensus);
    if (better != null) {
      stats.better_rows += 1;
      if (better) stats.better_count += 1;
    }
    var err = _numOrNull_(row.forecast_error_abs);
    if (err != null) {
      stats.error_sum += Number(err || 0);
      stats.error_count += 1;
    }
  }
  stats.economic_dir_ok_rate = stats.dir_ok_rows ? _round4_(stats.dir_ok_count / stats.dir_ok_rows) : '';
  stats.better_than_consensus_rate = stats.better_rows ? _round4_(stats.better_count / stats.better_rows) : '';
  stats.avg_forecast_error_abs = stats.error_count ? _round4_(stats.error_sum / stats.error_count) : '';
  return stats;
}

function _providerCharacterDirectExpressionEconomicLinkDominantFamily_(rows) {
  var counts = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var family = String((rows[i] || {}).outcome_family || 'other').trim() || 'other';
    counts[family] = (counts[family] || 0) + 1;
  }
  var best = '';
  var bestCount = -1;
  Object.keys(counts).sort().forEach(function(key) {
    var count = Number(counts[key] || 0);
    if (count > bestCount || (count === bestCount && key < best)) {
      best = key;
      bestCount = count;
    }
  });
  return best || 'other';
}

function _providerCharacterDirectExpressionEconomicLinkChooseBaseline_(provider, cluster, providerRows, familyMode, baselines) {
  var scope = _providerCharacterDirectExpressionEconomicLinkScope_(cluster, providerRows, cluster);
  var providerBaseline = baselines.provider[provider] || baselines.all;
  var familyKey = provider + '|' + familyMode;
  var providerFamilyBaseline = baselines.provider_family[familyKey] || null;
  var baselineStats = providerBaseline;
  var baselineSource = 'provider';

  if (scope === 'all_provider_cluster' || scope === 'field_cluster') {
    baselineStats = baselines.all;
    baselineSource = 'all';
  } else if (familyMode && providerFamilyBaseline && providerRows.length >= 3 && Number(providerFamilyBaseline.total_rows || 0) >= 5) {
    baselineStats = providerFamilyBaseline;
    baselineSource = 'provider_family';
  }

  return {
    stats: baselineStats,
    source: baselineSource
  };
}

function _providerCharacterDirectExpressionEconomicLinkScope_(cluster, providerRows, recurrenceRow) {
  var stable = String((recurrenceRow || {}).stable_character_candidate_flag || '').trim().toUpperCase() === 'TRUE';
  var providersCount = Number((recurrenceRow || {}).providers_present_count || 0) || (cluster && cluster.providers_present_count) || 0;
  var specificity = _numOrNull_((recurrenceRow || {}).provider_specificity_score);
  if (stable) return 'stable_candidate_cluster';
  if (providersCount > 1 && (specificity == null || specificity < 0.6)) return 'all_provider_cluster';
  if (specificity != null && specificity >= 0.6) return 'provider_cluster';
  return 'field_cluster';
}

function _providerCharacterDirectExpressionEconomicLinkSampleWarning_(cluster, providerRows, familyMode, providerProfileLookup) {
  var warnings = [];
  var rowCount = Number((providerRows || []).length || 0);
  var eventCount = _providerCharacterDirectExpressionEconomicLinkUniqueEventCount_(providerRows);
  if (rowCount < 3 || eventCount < 2) warnings.push('insufficient_sample');
  else if (rowCount < 5) warnings.push('very_thin_sample');
  if (eventCount === 1) warnings.push('single_event_cluster');
  if (Number(cluster.family_count || 0) === 1) warnings.push('single_family_only');
  if (Number(cluster.providers_present_count || 0) > 1) warnings.push('provider_mixed_cluster');
  if (_numOrNull_(cluster.generic_expression_score) != null && Number(cluster.generic_expression_score || 0) >= 0.65) warnings.push('generic_expression_cluster');
  if (_numOrNull_(cluster.recurrence_strength) != null && Number(cluster.recurrence_strength || 0) < 0.45) warnings.push('unstable_recurrence');
  if (!warnings.length) warnings.push('ok');
  return _uniqueStrings_(warnings).join('|');
}

function _providerCharacterDirectExpressionEconomicLinkEventIdMap_(rows) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var eventId = String((rows[i] || {}).event_id || '').trim();
    if (!eventId) continue;
    out[eventId] = true;
  }
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkClassifyLink_(cluster, providerRows, providerMetrics, baselineStats, sampleWarning) {
  var rowCount = Number(providerMetrics.total_rows || 0);
  if (rowCount < 3 || Number(providerMetrics.event_count || 0) < 2) return 'insufficient_sample';
  if (Number(cluster.generic_expression_score || 0) >= 0.7 || Number(cluster.recurrence_strength || 0) < 0.35) return 'unstable_or_generic';

  var favorable = 0;
  var unfavorable = 0;
  if (_providerCharacterDirectExpressionEconomicLinkDeltaIsFavorable_('rate', providerMetrics.economic_dir_ok_rate, baselineStats.economic_dir_ok_rate)) favorable += 1;
  else if (_providerCharacterDirectExpressionEconomicLinkDeltaIsUnfavorable_('rate', providerMetrics.economic_dir_ok_rate, baselineStats.economic_dir_ok_rate)) unfavorable += 1;
  if (_providerCharacterDirectExpressionEconomicLinkDeltaIsFavorable_('rate', providerMetrics.better_than_consensus_rate, baselineStats.better_than_consensus_rate)) favorable += 1;
  else if (_providerCharacterDirectExpressionEconomicLinkDeltaIsUnfavorable_('rate', providerMetrics.better_than_consensus_rate, baselineStats.better_than_consensus_rate)) unfavorable += 1;
  if (_providerCharacterDirectExpressionEconomicLinkDeltaIsFavorable_('error', providerMetrics.avg_forecast_error_abs, baselineStats.avg_forecast_error_abs)) favorable += 1;
  else if (_providerCharacterDirectExpressionEconomicLinkDeltaIsUnfavorable_('error', providerMetrics.avg_forecast_error_abs, baselineStats.avg_forecast_error_abs)) unfavorable += 1;

  if (favorable >= 2 && unfavorable === 0) return 'positive_candidate';
  if (unfavorable >= 2 && favorable === 0) return 'negative_candidate';
  return 'neutral_or_unclear';
}

function _providerCharacterDirectExpressionEconomicLinkDeltaIsFavorable_(metricType, value, baseline) {
  var v = _numOrNull_(value);
  var b = _numOrNull_(baseline);
  if (v == null || b == null) return false;
  var delta = Number(v) - Number(b);
  if (metricType === 'error') return delta <= -0.03;
  return delta >= 0.03;
}

function _providerCharacterDirectExpressionEconomicLinkDeltaIsUnfavorable_(metricType, value, baseline) {
  var v = _numOrNull_(value);
  var b = _numOrNull_(baseline);
  if (v == null || b == null) return false;
  var delta = Number(v) - Number(b);
  if (metricType === 'error') return delta >= 0.03;
  return delta <= -0.03;
}

function _providerCharacterDirectExpressionEconomicLinkInterpretation_(linkStrength, cluster, providerMetrics, baselineStats, sampleWarning, baselineChoice) {
  if (linkStrength === 'positive_candidate') {
    return 'Recurring direct-expression pattern shows a positive diagnostic association versus the chosen baseline.';
  }
  if (linkStrength === 'negative_candidate') {
    return 'Recurring direct-expression pattern shows a negative diagnostic association versus the chosen baseline.';
  }
  if (linkStrength === 'unstable_or_generic') {
    return 'Recurrence is visible, but the expression looks generic or unstable against baseline.';
  }
  if (linkStrength === 'insufficient_sample') {
    return 'Sample is too thin for a stable diagnostic reading.';
  }
  return 'Direct-expression pattern is neutral or unclear versus baseline.';
}

function _providerCharacterDirectExpressionEconomicLinkNotes_(cluster, providerRows, baselineChoice, sampleWarning, recurrenceRow) {
  return [
    'baseline=' + String(baselineChoice.source || 'provider'),
    'provider_rows=' + String((providerRows || []).length),
    'cluster_rows=' + String(cluster.total_row_count || 0),
    'family_count=' + String(cluster.family_count || 0),
    'event_count=' + String(cluster.event_count || 0),
    'recurrence_id=' + String((recurrenceRow || {}).cluster_id || ''),
    'warnings=' + String(sampleWarning || 'ok')
  ].join('; ');
}

function _providerCharacterDirectExpressionEconomicLinkRateDelta_(value, baseline) {
  var v = _numOrNull_(value);
  var b = _numOrNull_(baseline);
  if (v == null || b == null) return '';
  return _round4_(Number(v) - Number(b));
}

function _providerCharacterDirectExpressionEconomicLinkErrorDelta_(value, baseline) {
  var v = _numOrNull_(value);
  var b = _numOrNull_(baseline);
  if (v == null || b == null) return '';
  return _round4_(Number(v) - Number(b));
}

function _providerCharacterDirectExpressionEconomicLinkBool_(value) {
  var s = String(value == null ? '' : value).trim().toLowerCase();
  if (!s) return null;
  if (s === 'true' || s === '1' || s === 'yes' || s === 'y') return true;
  if (s === 'false' || s === '0' || s === 'no' || s === 'n') return false;
  if (value === true) return true;
  if (value === false) return false;
  return null;
}

function _providerCharacterDirectExpressionEconomicLinkBoolToNum_(value) {
  var b = _providerCharacterDirectExpressionEconomicLinkBool_(value);
  if (b == null) return null;
  return b ? 1 : 0;
}

function _providerCharacterDirectExpressionEconomicLinkUniqueEventCount_(rows) {
  var seen = {};
  var count = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    var eventId = String((rows[i] || {}).event_id || '').trim();
    if (!eventId || seen[eventId]) continue;
    seen[eventId] = true;
    count += 1;
  }
  return count;
}

function _providerCharacterDirectExpressionEconomicLinkCountBy_(rows, classification) {
  var count = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    if (String((rows[i] || {}).link_strength || '').trim() === classification) count += 1;
  }
  return count;
}

function _providerCharacterDirectExpressionEconomicLinkStrengthOrder_(strength) {
  var map = {
    positive_candidate: 5,
    negative_candidate: 4,
    neutral_or_unclear: 3,
    unstable_or_generic: 2,
    insufficient_sample: 1
  };
  return map[String(strength || '').trim()] || 0;
}

function _providerCharacterDirectExpressionEconomicLinkTopClusters_(rows, limit, predicate) {
  var list = (rows || []).filter(function(row) {
    return predicate ? predicate(row) : true;
  }).slice().sort(function(a, b) {
    var av = Math.abs(_numOrNull_(a.economic_dir_ok_delta_vs_baseline) || 0) + Math.abs(_numOrNull_(a.better_than_consensus_delta_vs_baseline) || 0);
    var bv = Math.abs(_numOrNull_(b.economic_dir_ok_delta_vs_baseline) || 0) + Math.abs(_numOrNull_(b.better_than_consensus_delta_vs_baseline) || 0);
    if (bv !== av) return bv - av;
    return String(a.cluster_phrase || '').localeCompare(String(b.cluster_phrase || ''));
  });
  return list.slice(0, limit || 3).map(function(row) {
    return String(row.provider || '') + ': ' + String(row.cluster_phrase || '');
  }).filter(Boolean).join(' | ');
}

function _providerCharacterDirectExpressionEconomicLinkBuildSummaryRows_(generatedTs, economicLinkRunId, linkRows, captureStats, baselines, summaryContext, warnings) {
  var out = [];
  out.push(_providerCharacterDirectExpressionEconomicLinkSummaryRow_(generatedTs, economicLinkRunId, 'all', 'ALL', '', linkRows, captureStats, baselines.all, summaryContext, warnings));

  var byProvider = {};
  for (var i = 0; i < (linkRows || []).length; i++) {
    var row = linkRows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!byProvider[provider]) byProvider[provider] = [];
    byProvider[provider].push(row);
  }

  Object.keys(byProvider).sort().forEach(function(provider) {
    out.push(_providerCharacterDirectExpressionEconomicLinkSummaryRow_(generatedTs, economicLinkRunId, 'provider', provider, '', byProvider[provider], captureStats, baselines.provider[provider] || baselines.all, summaryContext, warnings));
  });

  if (!out.length && warnings) warnings.push('economic_link_summary_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionEconomicLinkSummaryRow_(generatedTs, economicLinkRunId, scope, provider, outcomeFamily, rows, captureStats, baselineStats, summaryContext, warnings) {
  rows = rows || [];
  var totalRows = 0;
  var totalEvents = {};
  var dirOkCount = 0;
  var betterCount = 0;
  var errorSum = 0;
  var errorCount = 0;
  var positive = 0;
  var negative = 0;
  var neutral = 0;
  var thin = 0;
  var bestPositive = [];
  var worstNegative = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    totalRows += Number(row.total_rows || 0);
    var rowEvents = String(row.event_count || 0).trim();
    if (row.cluster_id) totalEvents[row.cluster_id + '|' + row.provider] = true;
    if (String(row.link_strength || '') === 'positive_candidate') positive += 1;
    else if (String(row.link_strength || '') === 'negative_candidate') negative += 1;
    else if (String(row.link_strength || '') === 'insufficient_sample') thin += 1;
    else neutral += 1;
    Object.keys(row.__event_ids || {}).forEach(function(eventId) {
      if (eventId) totalEvents[eventId] = true;
    });

    var rowDirCount = _numOrNull_(row.economic_dir_ok_count);
    if (rowDirCount != null) dirOkCount += Number(rowDirCount || 0);
    var rowBetterCount = _numOrNull_(row.better_than_consensus_count);
    if (rowBetterCount != null) betterCount += Number(rowBetterCount || 0);
    var rowErr = _numOrNull_(row.avg_forecast_error_abs);
    var rowCount = Number(row.total_rows || 0);
    if (rowErr != null && rowCount > 0) {
      errorSum += Number(rowErr || 0) * rowCount;
      errorCount += rowCount;
    }
  }

  var totalEventsCount = _providerCharacterDirectExpressionEconomicLinkSummaryEventCount_(scope, provider, captureStats, totalEvents);
  var econRate = totalRows ? _round4_(dirOkCount / totalRows) : '';
  var betterRate = totalRows ? _round4_(betterCount / totalRows) : '';
  var avgErr = errorCount ? _round4_(errorSum / errorCount) : '';
  var overallResult = _providerCharacterDirectExpressionEconomicLinkOverallResult_(rows, positive, negative, neutral, thin, summaryContext);
  var datasetStatus = _providerCharacterDirectExpressionEconomicLinkDatasetStatus_(rows, positive, negative, neutral, thin, summaryContext, overallResult);

  bestPositive = _providerCharacterDirectExpressionEconomicLinkTopClusters_(rows, 3, function(row) {
    return String(row.link_strength || '') === 'positive_candidate';
  });
  worstNegative = _providerCharacterDirectExpressionEconomicLinkTopClusters_(rows, 3, function(row) {
    return String(row.link_strength || '') === 'negative_candidate';
  });

  return {
    generated_ts: generatedTs,
    economic_link_run_id: economicLinkRunId,
    scope: scope,
    provider: provider,
    outcome_family: outcomeFamily || '',
    total_rows: totalRows,
    total_events: totalEventsCount,
    clusters_tested: rows.length,
    positive_candidates: positive,
    negative_candidates: negative,
    neutral_or_unclear: neutral,
    insufficient_sample: thin,
    best_positive_clusters: bestPositive,
    worst_negative_clusters: worstNegative,
    economic_dir_ok_rate: econRate,
    better_than_consensus_rate: betterRate,
    avg_forecast_error_abs: avgErr,
    baseline_economic_dir_ok_rate: baselineStats.economic_dir_ok_rate,
    baseline_better_than_consensus_rate: baselineStats.better_than_consensus_rate,
    baseline_avg_forecast_error_abs: baselineStats.avg_forecast_error_abs,
    overall_result: overallResult,
    dataset_status: datasetStatus,
    recommended_next_step: _providerCharacterDirectExpressionEconomicLinkRecommendedNextStep_(datasetStatus),
    what_is_supported: _providerCharacterDirectExpressionEconomicLinkSupportedText_(overallResult, datasetStatus),
    what_is_not_supported: 'Accuracy causation, routing, weighting, calibration, production changes, and market-reaction approval are not supported here.',
    notes: 'scope=' + scope + '; rows=' + totalRows + '; events=' + totalEventsCount + '; clusters=' + rows.length + '; baseline=' + (baselineStats.label || 'unknown') + '; recurrence=' + String(summaryContext.recurrence_result || '')
  };
}

function _providerCharacterDirectExpressionEconomicLinkSummaryEventCount_(scope, provider, captureStats, totalEvents) {
  if (String(scope || '').trim().toLowerCase() === 'all') {
    return Number((captureStats && captureStats.total_events) || 0);
  }
  var providerCount = captureStats && captureStats.provider_events ? captureStats.provider_events[provider] : null;
  providerCount = _numOrNull_(providerCount);
  if (providerCount != null) {
    return Number(providerCount || 0);
  }
  return Object.keys(totalEvents || {}).length;
}

function _providerCharacterDirectExpressionEconomicLinkOverallResult_(rows, positive, negative, neutral, thin, summaryContext) {
  var total = (rows || []).length;
  if (!total) return 'insufficient_data';
  if (positive + negative >= 4 && thin <= Math.floor(total / 3)) return 'economic_link_supported_for_review';
  if (positive + negative >= 1) return 'economic_link_partially_supported';
  if (neutral + thin >= total && total >= 5) return 'economic_link_weak';
  return 'economic_link_not_supported';
}

function _providerCharacterDirectExpressionEconomicLinkDatasetStatus_(rows, positive, negative, neutral, thin, summaryContext, overallResult) {
  var total = (rows || []).length;
  if (!total) return 'failed_runtime_or_matching';
  if (overallResult === 'economic_link_supported_for_review') return 'ready_for_falsification_review';
  if (positive + negative >= 1 && _providerCharacterDirectExpressionEconomicLinkDominantProviderCount_(rows) === 1) return 'provider_specific_only';
  if (thin >= Math.ceil(total / 2)) return 'needs_more_direct_capture_rows';
  if (neutral + thin >= total) return 'too_noisy_to_continue';
  return 'needs_more_direct_capture_rows';
}

function _providerCharacterDirectExpressionEconomicLinkDominantProviderCount_(rows) {
  var counts = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var provider = String((rows[i] || {}).provider || '').trim();
    if (!provider) continue;
    counts[provider] = (counts[provider] || 0) + 1;
  }
  var top = 0;
  Object.keys(counts).forEach(function(key) {
    if (Number(counts[key] || 0) > top) top = Number(counts[key] || 0);
  });
  return top;
}

function _providerCharacterDirectExpressionEconomicLinkRecommendedNextStep_(datasetStatus) {
  if (datasetStatus === 'ready_for_falsification_review') return 'Move to Direct Expression Economic Falsification v1';
  if (datasetStatus === 'needs_more_direct_capture_rows') return 'Collect more direct-expression rows';
  if (datasetStatus === 'provider_specific_only') return 'Narrow to provider-specific clusters only';
  if (datasetStatus === 'too_noisy_to_continue') return 'Stop this branch as too noisy';
  return 'Inspect runtime and matching';
}

function _providerCharacterDirectExpressionEconomicLinkSupportedText_(overallResult, datasetStatus) {
  if (overallResult === 'economic_link_supported_for_review') {
    return 'Some recurring direct-expression clusters show a diagnostic association with economic-value outcomes.';
  }
  if (overallResult === 'economic_link_partially_supported') {
    return 'A smaller direct-expression link signal is visible, but it remains mixed or incomplete.';
  }
  if (overallResult === 'economic_link_weak') {
    return 'Only weak direct-expression association is visible so far.';
  }
  if (overallResult === 'economic_link_not_supported') {
    return 'The current direct-expression sample does not yet support a stable economic link.';
  }
  return 'The current direct-expression sample is too small or inconsistent to judge economic linkage.';
}

function _providerCharacterDirectExpressionEconomicLinkBuildMethodologyRows_(generatedTs, economicLinkRunId, captureStats, warnings) {
  return [{
    generated_ts: generatedTs,
    economic_link_run_id: economicLinkRunId,
    experiment_name: 'Provider Character v2 — Direct Expression Economic Link v1',
    branch_name: 'Provider Character v2 / Direct Expression Branch',
    source_capture_sheet: 'Provider_Character_Direct_Expression_Capture',
    source_recurrence_sheet: 'Provider_Character_Direct_Expression_Recurrence',
    source_total_rows: captureStats.total_rows,
    cohort_a_rows_included: captureStats.cohort_a_rows,
    cohort_b_rows_included: captureStats.cohort_b_rows,
    accepted_provider_call_statuses: 'success, reused',
    generation_1_data_used: 'FALSE',
    fresh_vs_original_comparison_used: 'FALSE',
    old_attention_labels_used_as_seed: 'FALSE',
    ai_provider_calls_made: 'FALSE',
    prediction_runs_made: 'FALSE',
    production_changes: 'FALSE',
    market_reaction_primary_target: 'FALSE',
    accuracy_linkage_tested: 'TRUE',
    routing_approved: 'FALSE',
    weighting_approved: 'FALSE',
    calibration_approved: 'FALSE',
    interpretation_rule: 'diagnostic correlation only; no causal or production claim',
    notes: 'combined_dataset=Cohort A reused + Cohort B success; source_rows=' + captureStats.total_rows + '; unique_events=' + captureStats.total_events + '; warnings=' + _uniqueStrings_(warnings).join('|')
  }];
}
