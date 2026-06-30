/*******************************************************
 * provider_character_direct_expression_recurrence.js
 * - Diagnostic-only Provider Character v2 — Direct Expression Recurrence v1
 * - Reads Provider_Character_Direct_Expression_Capture
 * - No provider calls, no predictions, no production changes
 *******************************************************/

function menuBuildProviderCharacterDirectExpressionRecurrence_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterDirectExpressionRecurrence_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character direct expression recurrence -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Clusters=' + (res.cluster_rows_written || 0) +
      ' | Profiles=' + (res.profile_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0),
      'Provider Character Direct Expression Recurrence',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character direct expression recurrence -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterDirectExpressionRecurrence_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var recurrenceRunId = String(params.recurrence_run_id || '').trim() || _uuidFromString_('provider_character_direct_expression_recurrence:' + generatedTs);
  var warnings = [];
  var phase = String(params.phase || 'all').trim().toLowerCase();
  var writeOutput = params.write_output !== false;
  var writeClusters = phase === 'all' || phase === 'clusters';
  var writeProfiles = phase === 'all' || phase === 'profiles';
  var writeSummary = phase === 'all' || phase === 'summary';
  var writeMethodology = phase === 'all' || phase === 'methodology';

  try {
    var sources = params.source_bundle || (!Array.isArray(params.capture_rows) ? _providerCharacterDirectExpressionRecurrenceLoadSources_(warnings) : {});
    var captureRows = Array.isArray(params.capture_rows)
      ? params.capture_rows
      : _providerCharacterDirectExpressionRecurrenceReadCaptureRows_(sources.captureBundle, warnings);
    var analyzedRows = _providerCharacterDirectExpressionRecurrenceFilterAnalyzableRows_(captureRows, warnings);
    var clusterRows = _providerCharacterDirectExpressionRecurrenceBuildClusterRows_(generatedTs, recurrenceRunId, analyzedRows, warnings);
    var statsMap = null;
    var profileRows = [];
    var summaryRows = [];
    var methodologyRows = [];
    if (writeProfiles || writeSummary) {
      statsMap = _providerCharacterDirectExpressionRecurrenceBuildStatsMap_(analyzedRows, clusterRows);
    }
    if (writeProfiles) {
      profileRows = _providerCharacterDirectExpressionRecurrenceBuildProfileRows_(generatedTs, recurrenceRunId, statsMap, warnings);
    }
    if (writeSummary || writeMethodology) {
      if (!statsMap) {
        statsMap = _providerCharacterDirectExpressionRecurrenceBuildStatsMap_(analyzedRows, clusterRows);
      }
    }
    if (writeSummary) {
      summaryRows = _providerCharacterDirectExpressionRecurrenceBuildSummaryRows_(generatedTs, recurrenceRunId, statsMap, warnings);
    }
    if (writeMethodology) {
      methodologyRows = _providerCharacterDirectExpressionRecurrenceBuildMethodologyRows_(
        generatedTs,
        recurrenceRunId,
        captureRows.length,
        analyzedRows,
        clusterRows.length,
        warnings
      );
    }

    var recurrenceSheet = null;
    var profileSheet = null;
    var summarySheet = null;
    var methodologySheet = null;

    var result = {
      status: 'ok',
      generated_ts: generatedTs,
      recurrence_run_id: recurrenceRunId,
      phase: phase,
      source_rows_read: captureRows.length,
      analyzed_rows: analyzedRows.length,
      cluster_rows_written: 0,
      profile_rows_written: 0,
      summary_rows_written: 0,
      methodology_rows_written: 0,
      warnings: _uniqueStrings_(warnings)
    };

    if (writeOutput && writeClusters) {
      recurrenceSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Recurrence', _providerCharacterDirectExpressionRecurrenceHeaders_(), warnings);
      _rewriteSheetRowsPreservingHeaders_(
        recurrenceSheet.sheet,
        recurrenceSheet.headers,
        _characterResidualObjectsToRows_(clusterRows, recurrenceSheet.headers)
      );
      result.recurrence_sheet = recurrenceSheet.sheet.getName();
      result.cluster_rows_written = clusterRows.length;
    }

    if (writeOutput && writeProfiles) {
      profileSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Provider_Profile', _providerCharacterDirectExpressionRecurrenceProfileHeaders_(), warnings);
      _rewriteSheetRowsPreservingHeaders_(
        profileSheet.sheet,
        profileSheet.headers,
        _characterResidualObjectsToRows_(profileRows, profileSheet.headers)
      );
      result.profile_sheet = profileSheet.sheet.getName();
      result.profile_rows_written = profileRows.length;
    }

    if (writeOutput && writeSummary) {
      summarySheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Recurrence_Summary', _providerCharacterDirectExpressionRecurrenceSummaryHeaders_(), warnings);
      _rewriteSheetRowsPreservingHeaders_(
        summarySheet.sheet,
        summarySheet.headers,
        _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
      );
      result.summary_sheet = summarySheet.sheet.getName();
      result.summary_rows_written = summaryRows.length;
    }

    if (writeOutput && writeMethodology) {
      methodologySheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Recurrence_Methodology', _providerCharacterDirectExpressionRecurrenceMethodologyHeaders_(), warnings);
      _rewriteSheetRowsPreservingHeaders_(
        methodologySheet.sheet,
        methodologySheet.headers,
        _characterResidualObjectsToRows_(methodologyRows, methodologySheet.headers)
      );
      result.methodology_sheet = methodologySheet.sheet.getName();
      result.methodology_rows_written = methodologyRows.length;
    }

    if (!writeOutput) {
      result.cluster_rows = clusterRows;
      result.profile_rows = profileRows;
      result.summary_rows = summaryRows;
      result.methodology_rows = methodologyRows;
    }
    result.warnings = _uniqueStrings_(warnings);
    return result;
  } catch (e) {
    return {
      status: 'error',
      generated_ts: generatedTs,
      recurrence_run_id: recurrenceRunId,
      phase: phase,
      error_message: (e && e.stack) ? e.stack : String(e),
      warnings: _uniqueStrings_(warnings)
    };
  }
}

function buildProviderCharacterDirectExpressionRecurrence(params) {
  return buildProviderCharacterDirectExpressionRecurrence_(params || {});
}

function _providerCharacterDirectExpressionRecurrenceHeaders_() {
  return [
    'generated_ts',
    'recurrence_run_id',
    'cluster_id',
    'cluster_phrase',
    'expression_field_source',
    'representative_terms',
    'representative_examples',
    'providers_present',
    'dominant_provider',
    'provider_row_counts',
    'total_row_count',
    'event_count',
    'family_count',
    'family_distribution',
    'cohort_distribution',
    'cross_provider_overlap_rate',
    'provider_specificity_score',
    'generic_expression_score',
    'recurrence_strength',
    'stable_character_candidate_flag',
    'economic_dir_ok_rate_descriptive',
    'avg_forecast_error_abs_descriptive',
    'better_than_consensus_rate_descriptive',
    'interpretation',
    'notes'
  ];
}

function _providerCharacterDirectExpressionRecurrenceProfileHeaders_() {
  return [
    'generated_ts',
    'recurrence_run_id',
    'provider',
    'total_rows',
    'unique_expression_count',
    'recurring_cluster_count',
    'provider_specific_cluster_count',
    'generic_cluster_count',
    'strongest_recurring_clusters',
    'strongest_provider_specific_clusters',
    'broadest_family_spread_clusters',
    'dominant_expression_style_summary',
    'family_spread_count',
    'cross_provider_overlap_rate',
    'provider_specificity_avg',
    'recurrence_strength_avg',
    'recurrence_readiness',
    'recommended_next_step',
    'notes',
    'total_events'
  ];
}

function _providerCharacterDirectExpressionRecurrenceSummaryHeaders_() {
  return [
    'generated_ts',
    'recurrence_run_id',
    'scope',
    'provider',
    'outcome_family',
    'total_rows',
    'total_events',
    'total_clusters',
    'recurring_clusters',
    'provider_specific_clusters',
    'generic_clusters',
    'stable_character_candidates',
    'avg_provider_specificity_score',
    'avg_cross_provider_overlap_rate',
    'avg_generic_expression_score',
    'families_covered',
    'cohorts_covered',
    'recurrence_result',
    'dataset_status',
    'recommended_next_step',
    'what_is_supported',
    'what_is_not_supported',
    'notes'
  ];
}

function _providerCharacterDirectExpressionRecurrenceMethodologyHeaders_() {
  return [
    'generated_ts',
    'recurrence_run_id',
    'experiment_name',
    'branch_name',
    'source_dataset',
    'source_dataset_status',
    'source_total_rows',
    'generation_1_data_used',
    'ai_provider_calls_made',
    'prediction_runs_made',
    'production_changes',
    'market_reaction_usage',
    'feature_pack_usage',
    'purpose',
    'accuracy_linkage_tested',
    'interpretation_rule',
    'notes',
    'source_provider_event_rows',
    'source_unique_event_count'
  ];
}

function _providerCharacterDirectExpressionRecurrenceLoadSources_(warnings) {
  return {
    captureBundle: _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false)
  };
}

function _providerCharacterDirectExpressionRecurrenceReadCaptureRows_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var status = String(row.provider_call_status || '').trim().toLowerCase();
    if (status !== 'success' && status !== 'reused') continue;
    if (!String(row.cohort_id || '').trim()) continue;
    if (!String(row.event_id || '').trim()) continue;
    if (!String(row.provider || '').trim()) continue;
    if (!_providerCharacterDirectExpressionRecurrenceHasExpression_(row)) continue;
    out.push(row);
  }
  if (!out.length && warnings) warnings.push('capture_success_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionRecurrenceHasExpression_(row) {
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

function _providerCharacterDirectExpressionRecurrenceFilterAnalyzableRows_(rows, warnings) {
  var out = [];
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var normalized = _providerCharacterDirectExpressionRecurrenceNormalizeRow_(row);
    if (!normalized.tokens.length) continue;
    out.push(normalized);
  }
  if (!out.length && warnings) warnings.push('analyzable_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionRecurrenceNormalizeRow_(row) {
  var sourceField = _providerCharacterDirectExpressionRecurrenceBestFieldSource_(row);
  var tokens = _providerCharacterDirectExpressionRecurrenceRowTokens_(row);
  var attentionTokens = _providerCharacterDirectExpressionRecurrenceAttentionTokens_(row);
  return {
    generated_ts: String(row.generated_ts || '').trim(),
    recurrence_run_id: '',
    cohort_id: String(row.cohort_id || '').trim(),
    event_id: String(row.event_id || '').trim(),
    provider: String(row.provider || '').trim(),
    indicator_name: String(row.indicator_name || '').trim(),
    country: String(row.country || '').trim(),
    release_ts: String(row.release_ts || '').trim(),
    outcome_family: String(row.outcome_family || '').trim() || 'other',
    importance: String(row.importance || '').trim(),
    consensus_value: _numOrNull_(row.consensus_value),
    prev_revision: _numOrNull_(row.prev_revision),
    released_value: _numOrNull_(row.released_value),
    ai_forecast_value: _numOrNull_(row.ai_forecast_value),
    qualitative_result: String(row.qualitative_result || '').trim(),
    economic_dir_ok: String(row.economic_dir_ok || '').trim(),
    forecast_error_abs: _numOrNull_(row.forecast_error_abs),
    better_than_consensus: String(row.better_than_consensus || '').trim().toUpperCase(),
    primary_focus_phrase: String(row.primary_focus_phrase || '').trim(),
    secondary_focus_phrase: String(row.secondary_focus_phrase || '').trim(),
    ignored_or_discounted_factor_phrase: String(row.ignored_or_discounted_factor_phrase || '').trim(),
    causal_path_phrase: String(row.causal_path_phrase || '').trim(),
    failure_condition_phrase: String(row.failure_condition_phrase || '').trim(),
    confidence_basis_phrase: String(row.confidence_basis_phrase || '').trim(),
    uncertainty_phrase: String(row.uncertainty_phrase || '').trim(),
    expression_summary_phrase: String(row.expression_summary_phrase || '').trim(),
    attention_terms: String(row.attention_terms || '').trim(),
    provider_call_status: String(row.provider_call_status || '').trim(),
    token_input_estimate: _numOrNull_(row.token_input_estimate),
    token_output_estimate: _numOrNull_(row.token_output_estimate),
    latency_ms: _numOrNull_(row.latency_ms),
    source_experiment: String(row.source_experiment || '').trim(),
    notes: String(row.notes || '').trim(),
    source_field: sourceField,
    tokens: tokens,
    attention_tokens: attentionTokens,
    token_set: _providerCharacterDirectExpressionRecurrenceTokensToSet_(tokens),
    attention_token_set: _providerCharacterDirectExpressionRecurrenceTokensToSet_(attentionTokens),
    causal_signature: _providerCharacterDirectExpressionRecurrenceCausalSignature_(row),
    recurrence_signature: _providerCharacterDirectExpressionRecurrenceSignature_(row, sourceField, tokens)
  };
}

function _providerCharacterDirectExpressionRecurrenceRowTokens_(row) {
  var text = [
    row.primary_focus_phrase,
    row.secondary_focus_phrase,
    row.ignored_or_discounted_factor_phrase,
    row.causal_path_phrase,
    row.failure_condition_phrase,
    row.confidence_basis_phrase,
    row.uncertainty_phrase,
    row.expression_summary_phrase,
    String(row.attention_terms || '').replace(/\|/g, ' ')
  ].join(' ');
  return _providerCharacterMicroExpressionTokenize_(text);
}

function _providerCharacterDirectExpressionRecurrenceAttentionTokens_(row) {
  var text = String(row.attention_terms || '').replace(/\|/g, ' ');
  return _providerCharacterMicroExpressionTokenize_(text);
}

function _providerCharacterDirectExpressionRecurrenceTokensToSet_(tokens) {
  var out = {};
  for (var i = 0; i < (tokens || []).length; i++) {
    var token = String(tokens[i] || '').trim();
    if (token) out[token] = true;
  }
  return out;
}

function _providerCharacterDirectExpressionRecurrenceSignature_(row, sourceField, tokens) {
  var pieces = [];
  pieces.push(sourceField || 'expression_summary_phrase');
  pieces.push(_providerCharacterMicroExpressionCausalSignature_(row));
  pieces.push(_providerCharacterDirectExpressionRecurrenceTopTokenSignature_(tokens, 4));
  return pieces.join('|');
}

function _providerCharacterDirectExpressionRecurrenceCausalSignature_(row) {
  return _providerCharacterMicroExpressionCausalSignature_(row);
}

function _providerCharacterDirectExpressionRecurrenceTopTokenSignature_(tokens, limit) {
  var seen = {};
  var out = [];
  for (var i = 0; i < (tokens || []).length; i++) {
    var token = String(tokens[i] || '').trim();
    if (!token || seen[token]) continue;
    seen[token] = true;
    out.push(token);
    if (out.length >= (limit || 4)) break;
  }
  return out.join('|');
}

function _providerCharacterDirectExpressionRecurrenceBestFieldSource_(row) {
  var fields = [
    { name: 'expression_summary_phrase', value: row.expression_summary_phrase, weight: 9 },
    { name: 'causal_path_phrase', value: row.causal_path_phrase, weight: 8 },
    { name: 'primary_focus_phrase', value: row.primary_focus_phrase, weight: 7 },
    { name: 'secondary_focus_phrase', value: row.secondary_focus_phrase, weight: 6 },
    { name: 'failure_condition_phrase', value: row.failure_condition_phrase, weight: 5 },
    { name: 'confidence_basis_phrase', value: row.confidence_basis_phrase, weight: 5 },
    { name: 'uncertainty_phrase', value: row.uncertainty_phrase, weight: 5 },
    { name: 'ignored_or_discounted_factor_phrase', value: row.ignored_or_discounted_factor_phrase, weight: 4 },
    { name: 'attention_terms', value: row.attention_terms, weight: 3 }
  ];
  var best = 'expression_summary_phrase';
  var bestScore = -1;
  for (var i = 0; i < fields.length; i++) {
    var item = fields[i];
    var tokens = _providerCharacterMicroExpressionTokenize_(String(item.value || '').replace(/\|/g, ' '));
    if (!tokens.length) continue;
    var score = tokens.length * 100 + item.weight;
    if (score > bestScore) {
      bestScore = score;
      best = item.name;
    }
  }
  return best;
}

function _providerCharacterDirectExpressionRecurrenceBuildClusterRows_(generatedTs, recurrenceRunId, rows, warnings) {
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
    var row = ordered[i] || {};
    var tokens = row.tokens || _providerCharacterDirectExpressionRecurrenceRowTokens_(row);
    var bestIdx = -1;
    var bestScore = 0;
    for (var c = 0; c < clusters.length; c++) {
      var cluster = clusters[c];
      var score = _providerCharacterDirectExpressionRecurrenceSimilarity_(row, tokens, cluster.representative_row, cluster.representative_tokens);
      if (score > bestScore) {
        bestScore = score;
        bestIdx = c;
      }
    }

    if (bestIdx >= 0 && bestScore >= threshold) {
      _providerCharacterDirectExpressionRecurrenceAddRowToCluster_(clusters[bestIdx], row, tokens, bestScore);
    } else {
      clusters.push(_providerCharacterDirectExpressionRecurrenceNewCluster_(row, tokens, bestScore));
    }
  }

  var out = [];
  var index = 1;
  for (var j = 0; j < clusters.length; j++) {
    var cluster = clusters[j];
    _providerCharacterDirectExpressionRecurrenceFinalizeCluster_(cluster);
    if (cluster.total_row_count < 2 || cluster.event_count < 2) continue;
    var row = _providerCharacterDirectExpressionRecurrenceClusterRow_(generatedTs, recurrenceRunId, cluster, index, rows);
    out.push(row);
    index += 1;
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

  if (!out.length && warnings) warnings.push('recurrence_clusters_empty');
  return out;
}

function _providerCharacterDirectExpressionRecurrenceNewCluster_(row, tokens, similarity) {
  var provider = String(row.provider || '').trim();
  var sourceField = String(row.source_field || _providerCharacterDirectExpressionRecurrenceBestFieldSource_(row)).trim();
  return {
    rows: [row],
    representative_row: row,
    representative_tokens: (tokens || []).slice(),
    token_counts: _providerCharacterDirectExpressionRecurrenceTokenCounts_(tokens),
    attention_token_counts: _providerCharacterDirectExpressionRecurrenceTokenCounts_(row.attention_tokens || []),
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

function _providerCharacterDirectExpressionRecurrenceAddRowToCluster_(cluster, row, tokens, similarity) {
  cluster.rows.push(row);
  cluster.token_counts = _providerCharacterDirectExpressionRecurrenceMergeCounts_(cluster.token_counts, _providerCharacterDirectExpressionRecurrenceTokenCounts_(tokens));
  cluster.attention_token_counts = _providerCharacterDirectExpressionRecurrenceMergeCounts_(cluster.attention_token_counts, _providerCharacterDirectExpressionRecurrenceTokenCounts_(row.attention_tokens || []));
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
  cluster.better_than_values.push(_providerCharacterDirectExpressionRecurrenceBoolToNum_(row.better_than_consensus));
  cluster.dir_ok_values.push(_providerCharacterDirectExpressionRecurrenceBoolToNum_(row.economic_dir_ok));
  cluster.recurrence_signature_counts[row.recurrence_signature] = (cluster.recurrence_signature_counts[row.recurrence_signature] || 0) + 1;
  if (_providerCharacterDirectExpressionRecurrenceShouldReplaceRepresentative_(cluster.representative_row, row, cluster)) {
    cluster.representative_row = row;
    cluster.representative_tokens = (tokens || []).slice();
  }
}

function _providerCharacterDirectExpressionRecurrenceShouldReplaceRepresentative_(existing, candidate, cluster) {
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
    var candidatePriority = _providerCharacterDirectExpressionRecurrenceFieldSourcePriority_(candidateSource);
    var existingPriority = _providerCharacterDirectExpressionRecurrenceFieldSourcePriority_(existingSource);
    if (candidatePriority !== existingPriority) return candidatePriority > existingPriority;
  }
  return false;
}

function _providerCharacterDirectExpressionRecurrenceFieldSourcePriority_(field) {
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

function _providerCharacterDirectExpressionRecurrenceFinalizeCluster_(cluster) {
  var providerCounts = cluster.provider_counts || {};
  var totalRows = cluster.rows.length;
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
  cluster.total_row_count = totalRows;
  cluster.event_count = Object.keys(cluster.event_ids || {}).length;
  cluster.family_count = Object.keys(cluster.family_counts || {}).length;
  cluster.cohort_count = Object.keys(cluster.cohort_counts || {}).length;
  cluster.expression_field_source = _providerCharacterDirectExpressionRecurrenceModeKey_(cluster.source_field_counts);
  cluster.representative_example = _providerCharacterDirectExpressionRecurrenceRepresentativeExample_(cluster.rows, cluster.representative_row);
  cluster.representative_terms = _providerCharacterMicroExpressionTopTermPhrase_(cluster.token_counts || {});
  cluster.cluster_phrase = _providerCharacterDirectExpressionRecurrenceClusterPhrase_(cluster);
  cluster.family_distribution = _providerCharacterDirectExpressionRecurrenceCountsText_(cluster.family_counts);
  cluster.cohort_distribution = _providerCharacterDirectExpressionRecurrenceCountsText_(cluster.cohort_counts);
  cluster.provider_row_counts = _providerCharacterDirectExpressionRecurrenceProviderCountsText_(cluster.provider_counts);
  cluster.average_similarity = cluster.similarity_count ? _round4_(cluster.similarity_sum / cluster.similarity_count) : '';
  cluster.cross_provider_overlap_rate = _round4_(cluster.providers_present_count / 3);
  cluster.provider_specificity_score = totalRows ? _round4_(dominantProviderCount / totalRows) : '';
  cluster.generic_expression_score = _providerCharacterDirectExpressionRecurrenceGenericExpressionScore_(cluster);
  cluster.recurrence_strength = _providerCharacterDirectExpressionRecurrenceRecurrenceStrength_(cluster);
  cluster.stable_character_candidate_flag = _providerCharacterDirectExpressionRecurrenceStableFlag_(cluster);
  cluster.economic_dir_ok_rate_descriptive = _providerCharacterDirectExpressionRecurrenceAverage_(cluster.dir_ok_values);
  cluster.avg_forecast_error_abs_descriptive = _providerCharacterDirectExpressionRecurrenceAverage_(cluster.forecast_error_values);
  cluster.better_than_consensus_rate_descriptive = _providerCharacterDirectExpressionRecurrenceAverage_(cluster.better_than_values);
  cluster.notes = _providerCharacterDirectExpressionRecurrenceClusterNotes_(cluster);
}

function _providerCharacterDirectExpressionRecurrenceClusterRow_(generatedTs, recurrenceRunId, cluster, index, rows) {
  return {
    generated_ts: generatedTs,
    recurrence_run_id: recurrenceRunId,
    cluster_id: 'DER_' + ('000' + index).slice(-3),
    cluster_phrase: cluster.cluster_phrase,
    expression_field_source: cluster.expression_field_source,
    representative_terms: cluster.representative_terms,
    representative_examples: cluster.representative_example,
    providers_present: cluster.providers_present.join('|'),
    dominant_provider: cluster.dominant_provider,
    provider_row_counts: cluster.provider_row_counts,
    total_row_count: cluster.total_row_count,
    event_count: cluster.event_count,
    family_count: cluster.family_count,
    family_distribution: cluster.family_distribution,
    cohort_distribution: cluster.cohort_distribution,
    cross_provider_overlap_rate: cluster.cross_provider_overlap_rate,
    provider_specificity_score: cluster.provider_specificity_score,
    generic_expression_score: cluster.generic_expression_score,
    recurrence_strength: cluster.recurrence_strength,
    stable_character_candidate_flag: cluster.stable_character_candidate_flag,
    economic_dir_ok_rate_descriptive: cluster.economic_dir_ok_rate_descriptive,
    avg_forecast_error_abs_descriptive: cluster.avg_forecast_error_abs_descriptive,
    better_than_consensus_rate_descriptive: cluster.better_than_consensus_rate_descriptive,
    interpretation: _providerCharacterDirectExpressionRecurrenceInterpretation_(cluster),
    notes: cluster.notes
  };
}

function _providerCharacterDirectExpressionRecurrenceSimilarity_(rowA, tokensA, rowB, tokensB) {
  var jaccard = _providerCharacterMicroExpressionJaccard_(tokensA || [], tokensB || []);
  var causalA = _providerCharacterMicroExpressionCausalSignature_(rowA);
  var causalB = _providerCharacterMicroExpressionCausalSignature_(rowB);
  var causal = causalA && causalB && causalA === causalB ? 1 : 0;
  var attentionA = rowA.attention_tokens || [];
  var attentionB = rowB.attention_tokens || [];
  var attention = _providerCharacterMicroExpressionJaccard_(attentionA, attentionB);
  return (jaccard * 0.58) + (attention * 0.17) + (causal * 0.20) + ((_providerCharacterDirectExpressionRecurrenceFieldSourcePriority_(rowA.source_field) === _providerCharacterDirectExpressionRecurrenceFieldSourcePriority_(rowB.source_field) ? 1 : 0) * 0.05);
}

function _providerCharacterDirectExpressionRecurrenceTokenCounts_(tokens) {
  var map = {};
  for (var i = 0; i < (tokens || []).length; i++) {
    var token = String(tokens[i] || '').trim();
    if (!token) continue;
    map[token] = (map[token] || 0) + 1;
  }
  return map;
}

function _providerCharacterDirectExpressionRecurrenceMergeCounts_(base, extra) {
  var out = {};
  Object.keys(base || {}).forEach(function(key) { out[key] = Number(base[key] || 0); });
  Object.keys(extra || {}).forEach(function(key) { out[key] = (out[key] || 0) + Number(extra[key] || 0); });
  return out;
}

function _providerCharacterDirectExpressionRecurrenceModeKey_(map) {
  var best = '';
  var bestCount = -1;
  Object.keys(map || {}).sort().forEach(function(key) {
    var count = Number(map[key] || 0);
    if (count > bestCount || (count === bestCount && key < best)) {
      best = key;
      bestCount = count;
    }
  });
  return best;
}

function _providerCharacterDirectExpressionRecurrenceRepresentativeExample_(rows, representativeRow) {
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

function _providerCharacterDirectExpressionRecurrenceClusterPhrase_(cluster) {
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

function _providerCharacterDirectExpressionRecurrenceCountsText_(map) {
  var arr = [];
  Object.keys(map || {}).forEach(function(key) {
    arr.push({ key: key, count: Number(map[key] || 0) });
  });
  arr.sort(function(a, b) {
    if (b.count !== a.count) return b.count - a.count;
    return String(a.key).localeCompare(String(b.key));
  });
  return arr.map(function(item) {
    return item.key + '(' + item.count + ')';
  }).join('|');
}

function _providerCharacterDirectExpressionRecurrenceProviderCountsText_(map) {
  return _providerCharacterDirectExpressionRecurrenceCountsText_(map);
}

function _providerCharacterDirectExpressionRecurrenceGenericExpressionScore_(cluster) {
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
  var score = (tokenRatio * 0.42) + (overlapRate * 0.33) + (specificityPenalty * 0.25);
  return _round4_(Math.max(0, Math.min(1, score)));
}

function _providerCharacterDirectExpressionRecurrenceGenericTokens_() {
  return {
    expected: true, expect: true, expectedly: true, slight: true, slightly: true, modest: true, mild: true,
    steady: true, stable: true, weak: true, weaker: true, weakly: true, strong: true, stronger: true,
    mixed: true, muted: true, neutral: true, broad: true, broadly: true, generic: true, general: true,
    generally: true, likely: true, outlook: true, pressure: true, pressures: true, risk: true, risks: true,
    uncertainty: true, cautious: true, cautiously: true, trend: true, trajectory: true, momentum: true,
    movement: true, move: true, moves: true, balance: true, inline: true, flat: true, decline: true,
    declines: true, rise: true, rises: true, increase: true, increases: true, lower: true, higher: true,
    normal: true, usual: true, common: true, broadest: true, soft: true, softness: true, easing: true
  };
}

function _providerCharacterDirectExpressionRecurrenceRecurrenceStrength_(cluster) {
  var rowScore = Math.min(1, cluster.total_row_count / 5);
  var eventScore = Math.min(1, cluster.event_count / 4);
  var familyScore = Math.min(1, cluster.family_count / 3);
  var consistencyScore = _numOrNull_(cluster.average_similarity) == null ? 0 : Number(cluster.average_similarity || 0);
  var score = (rowScore * 0.30) + (eventScore * 0.25) + (familyScore * 0.15) + (consistencyScore * 0.30);
  return _round4_(Math.max(0, Math.min(1, score)));
}

function _providerCharacterDirectExpressionRecurrenceStableFlag_(cluster) {
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

function _providerCharacterDirectExpressionRecurrenceInterpretation_(cluster) {
  var parts = [];
  if (String(cluster.stable_character_candidate_flag || '').toUpperCase() === 'TRUE') parts.push('stable recurrence candidate');
  else parts.push('recurrent but not yet stable');
  if (_numOrNull_(cluster.provider_specificity_score) != null && Number(cluster.provider_specificity_score || 0) >= 0.6) parts.push('provider concentrated');
  else if (_numOrNull_(cluster.cross_provider_overlap_rate) != null && Number(cluster.cross_provider_overlap_rate || 0) >= 0.66) parts.push('cross provider overlap');
  if (_numOrNull_(cluster.generic_expression_score) != null && Number(cluster.generic_expression_score || 0) >= 0.65) parts.push('generic wording');
  if (_numOrNull_(cluster.family_count) != null && Number(cluster.family_count || 0) >= 3) parts.push('spans multiple families');
  return _providerCharacterMicroExpressionTrimWords_(parts.join('; '), 3, 16);
}

function _providerCharacterDirectExpressionRecurrenceClusterNotes_(cluster) {
  return [
    'source_field=' + String(cluster.expression_field_source || ''),
    'avg_similarity=' + String(cluster.average_similarity || ''),
    'provider_specificity=' + String(cluster.provider_specificity_score || ''),
    'generic_score=' + String(cluster.generic_expression_score || '')
  ].join('; ');
}

function _providerCharacterDirectExpressionRecurrenceAverage_(values) {
  var sum = 0;
  var count = 0;
  for (var i = 0; i < (values || []).length; i++) {
    var val = _numOrNull_(values[i]);
    if (val == null) continue;
    sum += Number(val || 0);
    count += 1;
  }
  return count ? _round4_(sum / count) : '';
}

function _providerCharacterDirectExpressionRecurrenceBoolToNum_(value) {
  var s = String(value || '').trim().toUpperCase();
  if (s === 'TRUE') return 1;
  if (s === 'FALSE') return 0;
  return null;
}

function _providerCharacterDirectExpressionRecurrenceBuildStatsMap_(rows, clusters) {
  var map = {
    ALL: _providerCharacterDirectExpressionRecurrenceInitStats_('ALL')
  };

  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!map[provider]) map[provider] = _providerCharacterDirectExpressionRecurrenceInitStats_(provider);
    _providerCharacterDirectExpressionRecurrenceAddRowToStats_(map.ALL, row);
    _providerCharacterDirectExpressionRecurrenceAddRowToStats_(map[provider], row);
  }

  for (var j = 0; j < (clusters || []).length; j++) {
    var cluster = clusters[j] || {};
    _providerCharacterDirectExpressionRecurrenceAddClusterToStats_(map.ALL, cluster);
    var providers = cluster.providers_present || [];
    if (typeof providers === 'string') {
      providers = providers.split('|');
    }
    for (var p = 0; p < providers.length; p++) {
      var providerName = String(providers[p] || '').trim();
      if (!providerName) continue;
      if (!map[providerName]) map[providerName] = _providerCharacterDirectExpressionRecurrenceInitStats_(providerName);
      _providerCharacterDirectExpressionRecurrenceAddClusterToStats_(map[providerName], cluster);
    }
  }

  Object.keys(map).forEach(function(key) {
    _providerCharacterDirectExpressionRecurrenceFinalizeStats_(map[key]);
  });

  return map;
}

function _providerCharacterDirectExpressionRecurrenceInitStats_(provider) {
  return {
    provider: provider,
    total_rows: 0,
    total_events: 0,
    event_ids: {},
    unique_expression_signatures: {},
    families: {},
    cohorts: {},
    recurring_clusters: [],
    provider_specific_clusters: [],
    generic_clusters: [],
    all_clusters: [],
    stable_character_candidates: 0,
    provider_specificity_sum: 0,
    cross_provider_overlap_sum: 0,
    generic_expression_sum: 0,
    recurrence_strength_sum: 0,
    cluster_weight_sum: 0
  };
}

function _providerCharacterDirectExpressionRecurrenceAddRowToStats_(stats, row) {
  stats.total_rows += 1;
  if (row.event_id) stats.total_events += 1;
  if (row.event_id) stats.event_ids[String(row.event_id || '').trim()] = true;
  if (row.recurrence_signature) stats.unique_expression_signatures[row.recurrence_signature] = true;
  if (row.outcome_family) stats.families[String(row.outcome_family || 'other').trim() || 'other'] = true;
  if (row.cohort_id) stats.cohorts[String(row.cohort_id || '').trim()] = true;
}

function _providerCharacterDirectExpressionRecurrenceAddClusterToStats_(stats, cluster) {
  if (!cluster || !cluster.total_row_count) return;
  var weight = Math.max(1, Number(cluster.total_row_count || 0));
  stats.all_clusters.push(cluster);
  stats.cluster_weight_sum += weight;
  stats.provider_specificity_sum += (Number(cluster.provider_specificity_score || 0) * weight);
  stats.cross_provider_overlap_sum += (Number(cluster.cross_provider_overlap_rate || 0) * weight);
  stats.generic_expression_sum += (Number(cluster.generic_expression_score || 0) * weight);
  stats.recurrence_strength_sum += (Number(cluster.recurrence_strength || 0) * weight);
  if (String(cluster.stable_character_candidate_flag || '').toUpperCase() === 'TRUE') stats.stable_character_candidates += 1;
  if (Number(cluster.total_row_count || 0) > 1 && Number(cluster.event_count || 0) > 1) stats.recurring_clusters.push(cluster);
  if (Number(cluster.provider_specificity_score || 0) >= 0.6) stats.provider_specific_clusters.push(cluster);
  if (Number(cluster.generic_expression_score || 0) >= 0.65) stats.generic_clusters.push(cluster);
}

function _providerCharacterDirectExpressionRecurrenceFinalizeStats_(stats) {
  var uniqueExpressionCount = Object.keys(stats.unique_expression_signatures || {}).length;
  stats.unique_expression_count = uniqueExpressionCount;
  stats.total_events = Object.keys(stats.event_ids || {}).length;
  stats.recurring_cluster_count = (stats.recurring_clusters || []).length;
  stats.provider_specific_cluster_count = (stats.provider_specific_clusters || []).length;
  stats.generic_cluster_count = (stats.generic_clusters || []).length;
  stats.family_spread_count = Object.keys(stats.families || {}).length;
  stats.cohorts_covered = Object.keys(stats.cohorts || {}).length;
  stats.avg_provider_specificity_score = stats.cluster_weight_sum ? _round4_(stats.provider_specificity_sum / stats.cluster_weight_sum) : '';
  stats.avg_cross_provider_overlap_rate = stats.cluster_weight_sum ? _round4_(stats.cross_provider_overlap_sum / stats.cluster_weight_sum) : '';
  stats.avg_generic_expression_score = stats.cluster_weight_sum ? _round4_(stats.generic_expression_sum / stats.cluster_weight_sum) : '';
  stats.avg_recurrence_strength = stats.cluster_weight_sum ? _round4_(stats.recurrence_strength_sum / stats.cluster_weight_sum) : '';
}

function _providerCharacterDirectExpressionRecurrenceBuildProfileRows_(generatedTs, recurrenceRunId, statsMap, warnings) {
  var out = [];
  Object.keys(statsMap || {}).sort(function(a, b) {
    if (a === 'ALL') return -1;
    if (b === 'ALL') return 1;
    return a.localeCompare(b);
  }).forEach(function(provider) {
    var stats = statsMap[provider];
    out.push(_providerCharacterDirectExpressionRecurrenceProfileRow_(generatedTs, recurrenceRunId, provider, stats));
  });
  if (!out.length && warnings) warnings.push('recurrence_profile_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionRecurrenceProfileRow_(generatedTs, recurrenceRunId, provider, stats) {
  var strongestRecurring = _providerCharacterDirectExpressionRecurrenceTopClusterPhrases_(stats.recurring_clusters, 3, 'recurrence_strength');
  var strongestSpecific = _providerCharacterDirectExpressionRecurrenceTopClusterPhrases_(stats.provider_specific_clusters, 3, 'provider_specificity');
  var broadestFamilies = _providerCharacterDirectExpressionRecurrenceTopClusterPhrases_(stats.recurring_clusters, 3, 'family_count');
  var dominantStyle = strongestRecurring || strongestSpecific || 'no clear recurring style';
  var readiness = _providerCharacterDirectExpressionRecurrenceReadiness_(stats, provider);
  return {
    generated_ts: generatedTs,
    recurrence_run_id: recurrenceRunId,
    provider: provider,
    total_rows: stats.total_rows,
    unique_expression_count: stats.unique_expression_count,
    recurring_cluster_count: stats.recurring_cluster_count,
    provider_specific_cluster_count: stats.provider_specific_cluster_count,
    generic_cluster_count: stats.generic_cluster_count,
    strongest_recurring_clusters: strongestRecurring,
    strongest_provider_specific_clusters: strongestSpecific,
    broadest_family_spread_clusters: broadestFamilies,
    dominant_expression_style_summary: dominantStyle,
    family_spread_count: stats.family_spread_count,
    cross_provider_overlap_rate: stats.avg_cross_provider_overlap_rate,
    provider_specificity_avg: stats.avg_provider_specificity_score,
    recurrence_strength_avg: stats.avg_recurrence_strength,
    recurrence_readiness: readiness,
    recommended_next_step: _providerCharacterDirectExpressionRecurrenceNextStep_(readiness),
    notes: _providerCharacterDirectExpressionRecurrenceProfileNotes_(stats),
    total_events: stats.total_events
  };
}

function _providerCharacterDirectExpressionRecurrenceReadiness_(stats, provider) {
  if (!stats || !stats.total_rows || !stats.recurring_cluster_count) return 'failed_extraction_or_clustering';
  if (stats.generic_cluster_count >= stats.recurring_cluster_count && Number(stats.avg_provider_specificity_score || 0) < 0.45) return 'generic_patterns_only';
  if (stats.recurring_cluster_count >= 4 && Number(stats.avg_provider_specificity_score || 0) >= 0.6 && Number(stats.avg_recurrence_strength || 0) >= 0.55 && stats.family_spread_count >= 3) {
    return 'strong_recurrence_ready_for_next_stage';
  }
  if (stats.recurring_cluster_count >= 2 && Number(stats.avg_recurrence_strength || 0) >= 0.4) {
    return 'moderate_recurrence_continue_cautiously';
  }
  if (stats.recurring_cluster_count > 0) return 'weak_recurrence_needs_more_rows';
  return 'failed_extraction_or_clustering';
}

function _providerCharacterDirectExpressionRecurrenceNextStep_(readiness) {
  if (readiness === 'strong_recurrence_ready_for_next_stage') return 'review direct expression economic-link readiness';
  if (readiness === 'moderate_recurrence_continue_cautiously') return 'collect more direct capture rows and monitor';
  if (readiness === 'weak_recurrence_needs_more_rows') return 'expand direct capture sample before next stage';
  if (readiness === 'generic_patterns_only') return 'refine capture scope or phrase selection';
  return 'inspect extraction and clustering path';
}

function _providerCharacterDirectExpressionRecurrenceProfileNotes_(stats) {
  return [
    'rows=' + String(stats.total_rows || 0),
    'recurring_clusters=' + String(stats.recurring_cluster_count || 0),
    'provider_specific_clusters=' + String(stats.provider_specific_cluster_count || 0),
    'generic_clusters=' + String(stats.generic_cluster_count || 0),
    'families=' + String(stats.family_spread_count || 0),
    'cohorts=' + String(stats.cohorts_covered || 0)
  ].join('; ');
}

function _providerCharacterDirectExpressionRecurrenceTopClusterPhrases_(clusters, limit, sortField) {
  var list = (clusters || []).slice().sort(function(a, b) {
    var as = _numOrNull_(a[sortField]) || 0;
    var bs = _numOrNull_(b[sortField]) || 0;
    if (bs !== as) return bs - as;
    if ((b.total_row_count || 0) !== (a.total_row_count || 0)) return (b.total_row_count || 0) - (a.total_row_count || 0);
    return String(a.cluster_phrase || '').localeCompare(String(b.cluster_phrase || ''));
  }).slice(0, limit || 3);
  return list.map(function(item) { return String(item.cluster_phrase || '').trim(); }).filter(Boolean).join(' | ');
}

function _providerCharacterDirectExpressionRecurrenceBuildSummaryRows_(generatedTs, recurrenceRunId, statsMap, warnings) {
  var out = [];
  var allStats = statsMap.ALL || _providerCharacterDirectExpressionRecurrenceInitStats_('ALL');
  out.push(_providerCharacterDirectExpressionRecurrenceSummaryRow_(generatedTs, recurrenceRunId, 'all', 'ALL', '', allStats));
  Object.keys(statsMap || {}).sort().forEach(function(provider) {
    if (provider === 'ALL') return;
    out.push(_providerCharacterDirectExpressionRecurrenceSummaryRow_(generatedTs, recurrenceRunId, 'provider', provider, '', statsMap[provider]));
  });
  if (!out.length && warnings) warnings.push('recurrence_summary_rows_empty');
  return out;
}

function _providerCharacterDirectExpressionRecurrenceSummaryRow_(generatedTs, recurrenceRunId, scope, provider, outcomeFamily, stats) {
  var totalClusters = (stats.all_clusters || []).length;
  var recurringClusters = stats.recurring_cluster_count || 0;
  var providerSpecificClusters = stats.provider_specific_cluster_count || 0;
  var genericClusters = stats.generic_cluster_count || 0;
  var stableCandidates = stats.stable_character_candidates || 0;
  var recurrenceResult = _providerCharacterDirectExpressionRecurrenceSummaryResult_(stats);
  var datasetStatus = _providerCharacterDirectExpressionRecurrenceDatasetStatus_(stats, recurrenceResult);
  var supported = _providerCharacterDirectExpressionRecurrenceSupportedText_(recurrenceResult, stats);
  var unsupported = 'Accuracy linkage, routing, weighting, calibration, and production changes are not supported here.';
  return {
    generated_ts: generatedTs,
    recurrence_run_id: recurrenceRunId,
    scope: scope,
    provider: provider,
    outcome_family: outcomeFamily || '',
    total_rows: stats.total_rows || 0,
    total_events: stats.total_events || 0,
    total_clusters: totalClusters,
    recurring_clusters: recurringClusters,
    provider_specific_clusters: providerSpecificClusters,
    generic_clusters: genericClusters,
    stable_character_candidates: stableCandidates,
    avg_provider_specificity_score: stats.avg_provider_specificity_score,
    avg_cross_provider_overlap_rate: stats.avg_cross_provider_overlap_rate,
    avg_generic_expression_score: stats.avg_generic_expression_score,
    families_covered: _providerCharacterDirectExpressionRecurrenceJoinedKeys_(stats.families),
    cohorts_covered: _providerCharacterDirectExpressionRecurrenceJoinedKeys_(stats.cohorts),
    recurrence_result: recurrenceResult,
    dataset_status: datasetStatus,
    recommended_next_step: _providerCharacterDirectExpressionRecurrenceSummaryNextStep_(datasetStatus),
    what_is_supported: supported,
    what_is_not_supported: unsupported,
    notes: _providerCharacterDirectExpressionRecurrenceSummaryNotes_(stats, recurrenceResult, datasetStatus)
  };
}

function _providerCharacterDirectExpressionRecurrenceSummaryResult_(stats) {
  if (!stats || !stats.total_rows || stats.total_rows < 10 || !stats.all_clusters.length) return 'insufficient_data';
  if (!stats.recurring_cluster_count) return 'recurrence_not_supported';
  if (stats.stable_character_candidates >= 4 && stats.recurring_cluster_count >= 6 && Number(stats.avg_provider_specificity_score || 0) >= 0.5) return 'recurrence_supported';
  if (stats.recurring_cluster_count >= 3 && Number(stats.avg_provider_specificity_score || 0) >= 0.4) return 'recurrence_partially_supported';
  return 'recurrence_weak';
}

function _providerCharacterDirectExpressionRecurrenceDatasetStatus_(stats, recurrenceResult) {
  if (recurrenceResult === 'insufficient_data') return 'failed_runtime_or_extraction';
  if (recurrenceResult === 'recurrence_not_supported') return 'needs_more_direct_capture_rows';
  if (stats.generic_cluster_count >= stats.recurring_cluster_count && Number(stats.avg_provider_specificity_score || 0) < 0.45) return 'too_generic_to_proceed';
  if (stats.stable_character_candidates >= 4 && stats.recurring_cluster_count >= 6) return 'ready_for_direct_expression_economic_link_review';
  if (recurrenceResult === 'recurrence_partially_supported' || recurrenceResult === 'recurrence_weak') return 'needs_more_direct_capture_rows';
  return 'provider_specific_only';
}

function _providerCharacterDirectExpressionRecurrenceSummaryNextStep_(datasetStatus) {
  if (datasetStatus === 'ready_for_direct_expression_economic_link_review') return 'review direct expression economic-link experiment design';
  if (datasetStatus === 'needs_more_direct_capture_rows') return 'collect additional direct capture rows and rerun';
  if (datasetStatus === 'too_generic_to_proceed') return 'refine expression capture or clustering thresholds';
  if (datasetStatus === 'provider_specific_only') return 'inspect provider-local recurrence before next stage';
  return 'inspect runtime and extraction path';
}

function _providerCharacterDirectExpressionRecurrenceSupportedText_(recurrenceResult, stats) {
  var cohortNote = _providerCharacterDirectExpressionRecurrenceCombinedCohortNote_(stats);
  if (recurrenceResult === 'recurrence_supported') {
    return 'Direct expression recurrence is supported across the combined Cohort A + Cohort B dataset' + cohortNote + ', with provider-specific and cross-family repetition visible.';
  }
  if (recurrenceResult === 'recurrence_partially_supported') {
    return 'Some direct expression recurrence is visible across the combined Cohort A + Cohort B dataset' + cohortNote + ', but the signal is still mixed or incomplete.';
  }
  if (recurrenceResult === 'recurrence_weak') {
    return 'Only weak direct expression recurrence is visible across the combined Cohort A + Cohort B dataset' + cohortNote + ' so far.';
  }
  if (recurrenceResult === 'recurrence_not_supported') {
    return 'Recurring structure is not yet supported by the current combined Cohort A + Cohort B direct expression sample' + cohortNote + '.';
  }
  return 'The current combined Cohort A + Cohort B direct expression sample' + cohortNote + ' is too small or inconsistent to judge recurrence.';
}

function _providerCharacterDirectExpressionRecurrenceSummaryNotes_(stats, recurrenceResult, datasetStatus) {
  return [
    'rows=' + String(stats.total_rows || 0),
    'events=' + String(stats.total_events || 0),
    'clusters=' + String((stats.all_clusters || []).length),
    'recurring_clusters=' + String(stats.recurring_cluster_count || 0),
    'stable_candidates=' + String(stats.stable_character_candidates || 0),
    'cohorts=' + _providerCharacterDirectExpressionRecurrenceCombinedCohortNote_(stats),
    'result=' + recurrenceResult,
    'dataset_status=' + datasetStatus
  ].join('; ');
}

function _providerCharacterDirectExpressionRecurrenceCombinedCohortNote_(stats) {
  var cohorts = _providerCharacterDirectExpressionRecurrenceJoinedKeys_(stats && stats.cohorts);
  if (!cohorts) return '';
  return ' cohorts=' + cohorts;
}

function _providerCharacterDirectExpressionRecurrenceJoinedKeys_(map) {
  return Object.keys(map || {}).sort().join('|');
}

function _providerCharacterDirectExpressionRecurrenceBuildMethodologyRows_(generatedTs, recurrenceRunId, sourceTotalRows, analyzedRows, clusterRows, warnings) {
  var uniqueEventCount = 0;
  var seenEvents = {};
  for (var i = 0; i < (analyzedRows || []).length; i++) {
    var eventId = String((analyzedRows[i] || {}).event_id || '').trim();
    if (!eventId || seenEvents[eventId]) continue;
    seenEvents[eventId] = true;
    uniqueEventCount += 1;
  }
  return [{
    generated_ts: generatedTs,
    recurrence_run_id: recurrenceRunId,
    experiment_name: 'Provider Character v2 — Direct Expression Recurrence v1',
    branch_name: 'Provider Character v2 / Direct Expression Branch',
    source_dataset: 'Provider_Character_Direct_Expression_Capture',
    source_dataset_status: 'completed',
    source_total_rows: sourceTotalRows,
    generation_1_data_used: 'FALSE',
    ai_provider_calls_made: 'FALSE',
    prediction_runs_made: 'FALSE',
    production_changes: 'FALSE',
    market_reaction_usage: 'FALSE',
    feature_pack_usage: 'FALSE',
    purpose: 'test recurrence and provider-specificity of direct expressions',
    accuracy_linkage_tested: 'FALSE',
    interpretation_rule: 'recurrence and provider-specificity only; no accuracy, routing, weighting, calibration, or production approval',
    notes: 'source_total_rows=' + sourceTotalRows + '; source_provider_event_rows=' + (analyzedRows || []).length + '; source_unique_event_count=' + uniqueEventCount + '; recurring_clusters=' + clusterRows + '; combined_dataset=Cohort A reused + Cohort B success; warnings=' + _uniqueStrings_(warnings).join('|'),
    source_provider_event_rows: (analyzedRows || []).length,
    source_unique_event_count: uniqueEventCount
  }];
}
