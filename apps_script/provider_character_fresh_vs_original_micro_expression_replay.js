/*******************************************************
 * provider_character_fresh_vs_original_micro_expression_replay.js
 * - Diagnostic-only Provider Character v2 — Fresh vs Original Micro-Expression Replay v1
 * - Fresh provider calls over a small historical sample
 * - Compares original Generation-1 outputs against fresh direct-capture outputs
 * - No production prediction writes, no routing/weighting/calibration changes
 *******************************************************/

function menuBuildProviderCharacterFreshVsOriginalReplay_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterFreshVsOriginalReplay_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character fresh vs original micro-expression replay -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Replay=' + (res.replay_rows_written || 0) +
      ' | Comparison=' + (res.comparison_rows_written || 0) +
      ' | Clusters=' + (res.cluster_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0),
      'Provider Character Fresh vs Original Replay',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character fresh vs original micro-expression replay -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterFreshVsOriginalReplay_() {
  var generatedTs = new Date().toISOString();
  var replayRunId = _uuidFromString_('provider_character_fresh_vs_original_replay:' + generatedTs);
  var warnings = [];

  var sources = _providerCharacterFreshReplayLoadSources_(warnings);
  var providers = _resolveProviders_(['Anthropic', 'Gemini', 'OpenAI']);
  if (!providers.length) {
    throw new Error('Fresh vs original replay requires at least one enabled provider.');
  }
  var providerMap = {};
  for (var p = 0; p < providers.length; p++) providerMap[providers[p].name] = providers[p];

  var eventSheet = (sources.eventBundle && sources.eventBundle.sheet) ? sources.eventBundle.sheet : getSheet('Event');
  if (!eventSheet) {
    throw new Error('Event sheet missing for fresh vs original replay.');
  }

  var originalPredictionLookup = _providerCharacterFreshReplayBuildOriginalPredictionLookup_(sources.predictionsBundle, warnings);
  var originalEconomicLookup = _providerCharacterFreshReplayBuildOriginalEconomicLookup_(sources.economicBundle, sources.predictionsBundle, warnings);
  var eventPool = _providerCharacterFreshReplayBuildEventPool_(
    sources.pilotBundle,
    originalPredictionLookup,
    originalEconomicLookup,
    providers,
    warnings
  );
  if (!eventPool.length) {
    warnings.push('pilot_event_pool_empty');
    eventPool = _providerCharacterFreshReplayBuildFallbackEventPool_(
      originalPredictionLookup,
      originalEconomicLookup,
      providers,
      warnings
    );
  }

  var sampledEvents = _providerCharacterFreshReplaySelectSampleEvents_(
    eventPool,
    _providerCharacterFreshReplayTargetCount_(),
    warnings
  );
  var freshRows = [];

  for (var i = 0; i < sampledEvents.length; i++) {
    var eventInfo = sampledEvents[i] || {};
    var eventId = String(eventInfo.event_id || '').trim();
    if (!eventId) continue;

    var ev = _getPredictionEventById_(eventSheet, eventId);
    if (!ev || !ev.event_id) {
      warnings.push('event_missing_from_event_sheet:' + eventId);
      continue;
    }

    for (var pIdx = 0; pIdx < providers.length; pIdx++) {
      var prov = providers[pIdx];
      var key = eventId + '|' + prov.name;
      var originalPredictionRow = originalPredictionLookup[key] || null;
      var originalEconomicRow = originalEconomicLookup[key] || null;
      if (!originalPredictionRow) {
        warnings.push('missing_original_coverage:' + key);
      }
      var originalSourceRow = originalEconomicRow || originalPredictionRow || {};

      var startMs = Date.now();
      var providerResp = null;
      var callStatus = 'success';
      var callError = '';
      try {
        providerResp = _callProviderJsonObject_(prov, _providerCharacterFreshReplayBuildPrompt_(ev), 'ai_prediction');
      } catch (e) {
        callStatus = 'failed';
        callError = (e && e.stack) ? e.stack : String(e);
        providerResp = {
          parsed: {},
          raw_output: '',
          prompt_tokens: null,
          completion_tokens: null
        };
      }
      var latencyMs = Date.now() - startMs;
      if (providerResp) providerResp.latency_ms = latencyMs;

      var normalized = _providerCharacterFreshReplayNormalizeProviderOutput_(providerResp.parsed || {}, providerResp.raw_output || '', ev);
      var score = _providerCharacterFreshReplayScoreEconomic_(normalized.ai_forecast_value, normalized.qualitative_result, originalSourceRow, ev);
      var replayPredictionText = _providerCharacterFreshReplayPredictionText_(normalized);
      var originalPredictionText = _providerCharacterFreshReplayOriginalPredictionText_(originalPredictionRow);
      var originalErrorAbs = _numOrNull_(originalSourceRow ? (originalSourceRow.value_error_abs != null ? originalSourceRow.value_error_abs : originalSourceRow.forecast_error_abs) : null);
      var replayErrorAbs = score.replay_forecast_error_abs == null ? null : score.replay_forecast_error_abs;
      var expressionGain = _providerCharacterFreshReplayExpressionGainScore_(originalPredictionRow, normalized);

      freshRows.push({
        generated_ts: generatedTs,
        replay_run_id: replayRunId,
        event_id: eventId,
        provider: prov.name,
        indicator_name: String(ev.indicator_name || eventInfo.indicator_name || '').trim(),
        release_ts: String(ev.release_ts || eventInfo.release_ts || '').trim(),
        outcome_family: String(eventInfo.family_key || eventInfo.outcome_family || (originalSourceRow ? originalSourceRow.outcome_family : '') || '').trim() || _providerCharacterFreshReplayFamilyKey_(String(ev.indicator_name || ''), String(ev.genre || '')),
        importance: String(ev.importance || eventInfo.importance || '').trim(),

        original_ai_forecast_value: originalPredictionRow ? _providerCharacterFreshReplayNumber_(originalPredictionRow.ai_forecast_value) : '',
        original_qualitative_result: String(originalPredictionRow ? originalPredictionRow.qualitative_result || '' : '').trim(),
        original_rationale_short: String(originalPredictionRow ? originalPredictionRow.rationale_short || '' : '').trim(),
        original_economic_dir_ok: String(originalSourceRow ? (originalSourceRow.value_dir_ok || originalSourceRow.forecast_dir_ok || '') : '').trim(),
        original_forecast_error_abs: originalErrorAbs == null ? '' : originalErrorAbs,

        replay_ai_forecast_value: normalized.ai_forecast_value == null ? '' : normalized.ai_forecast_value,
        replay_qualitative_result: String(normalized.qualitative_result || '').trim(),
        replay_economic_dir_ok: score.replay_economic_dir_ok,
        replay_forecast_error_abs: replayErrorAbs == null ? '' : replayErrorAbs,

        expected_move_dir: String(normalized.expected_move_dir || '').trim(),
        expected_move_pips_min: normalized.expected_move_pips_min == null ? '' : normalized.expected_move_pips_min,
        expected_move_pips_max: normalized.expected_move_pips_max == null ? '' : normalized.expected_move_pips_max,
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
        raw_provider_response_captured: normalized.raw_output ? 'TRUE' : 'FALSE',
        provider_call_status: callStatus,
        token_input_estimate: providerResp && providerResp.prompt_tokens != null ? providerResp.prompt_tokens : '',
        token_output_estimate: providerResp && providerResp.completion_tokens != null ? providerResp.completion_tokens : '',
        latency_ms: latencyMs == null ? '' : latencyMs,
        notes: _providerCharacterFreshReplayNotes_(
          callStatus,
          callError,
          eventInfo.sample_source || 'pilot',
          originalPredictionRow ? 'original_prediction_match=TRUE' : 'original_prediction_match=FALSE',
          originalSourceRow ? 'original_value_match=TRUE' : 'original_value_match=FALSE',
          providerResp && providerResp.raw_output ? 'raw_response_captured=TRUE' : 'raw_response_captured=FALSE',
          'replay_run_id=' + replayRunId,
          'expression_gain_score=' + (expressionGain == null ? '' : expressionGain)
        )
      });
    }
  }

  var comparisonRows = _providerCharacterFreshReplayBuildComparisonRows_(
    generatedTs,
    replayRunId,
    freshRows,
    originalPredictionLookup,
    originalEconomicLookup,
    warnings
  );
  var successfulFreshRows = freshRows.filter(function(row) {
    return String(row.provider_call_status || '').toLowerCase() === 'success';
  });
  var clusterRows = _providerCharacterMicroExpressionBuildClusterRows_(generatedTs, successfulFreshRows, warnings);
  var summaryRows = _providerCharacterFreshReplayBuildSummaryRows_(
    generatedTs,
    replayRunId,
    sampledEvents,
    freshRows,
    comparisonRows,
    clusterRows,
    originalPredictionLookup,
    originalEconomicLookup,
    warnings
  );

  var replaySheet = getDiagnosticsSheet_('Provider_Character_Fresh_Replay', _providerCharacterFreshReplayHeaders_(), warnings);
  var comparisonSheet = getDiagnosticsSheet_('Provider_Character_Fresh_vs_Original_Comparison', _providerCharacterFreshReplayComparisonHeaders_(), warnings);
  var clusterSheet = getDiagnosticsSheet_('Provider_Character_Fresh_Expression_Clusters', _providerCharacterMicroExpressionClusterHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Provider_Character_Fresh_Replay_Summary', _providerCharacterFreshReplaySummaryHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    replaySheet.sheet,
    replaySheet.headers,
    _characterResidualObjectsToRows_(freshRows, replaySheet.headers)
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
    summarySheet.sheet,
    summarySheet.headers,
    _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    replay_run_id: replayRunId,
    replay_sheet: replaySheet.sheet.getName(),
    comparison_sheet: comparisonSheet.sheet.getName(),
    cluster_sheet: clusterSheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    sampled_events: _providerCharacterFreshReplayUniqueEventCount_(freshRows),
    replay_rows_written: freshRows.length,
    comparison_rows_written: comparisonRows.length,
    cluster_rows_written: clusterRows.length,
    summary_rows_written: summaryRows.length,
    providers_enabled: providers.map(function(p) { return p.name; }).join('|'),
    warnings: _uniqueStrings_(warnings)
  };
}

function buildProviderCharacterFreshVsOriginalReplay() {
  return buildProviderCharacterFreshVsOriginalReplay_();
}

function _providerCharacterFreshReplayHeaders_() {
  return [
    'generated_ts',
    'replay_run_id',
    'event_id',
    'provider',
    'indicator_name',
    'release_ts',
    'outcome_family',
    'importance',
    'original_ai_forecast_value',
    'original_qualitative_result',
    'original_rationale_short',
    'original_economic_dir_ok',
    'original_forecast_error_abs',
    'replay_ai_forecast_value',
    'replay_qualitative_result',
    'replay_economic_dir_ok',
    'replay_forecast_error_abs',
    'expected_move_dir',
    'expected_move_pips_min',
    'expected_move_pips_max',
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
    'raw_provider_response_captured',
    'provider_call_status',
    'token_input_estimate',
    'token_output_estimate',
    'latency_ms',
    'notes'
  ];
}

function _providerCharacterFreshReplayComparisonHeaders_() {
  return [
    'generated_ts',
    'replay_run_id',
    'event_id',
    'provider',
    'original_prediction',
    'replay_prediction',
    'prediction_changed',
    'original_dir_ok',
    'replay_dir_ok',
    'original_error_abs',
    'replay_error_abs',
    'accuracy_change',
    'original_rationale_short',
    'fresh_primary_focus_phrase',
    'fresh_causal_path_phrase',
    'fresh_failure_condition_phrase',
    'expression_gain_score',
    'interpretation',
    'notes'
  ];
}

function _providerCharacterFreshReplaySummaryHeaders_() {
  return [
    'generated_ts',
    'replay_run_id',
    'provider',
    'sampled_events',
    'replay_rows',
    'successful_provider_calls',
    'failed_provider_calls',
    'original_dir_ok_rate',
    'replay_dir_ok_rate',
    'original_error_abs_avg',
    'replay_error_abs_avg',
    'avg_accuracy_change',
    'prediction_change_rate',
    'avg_expression_gain_score',
    'unique_micro_expression_count',
    'cluster_count',
    'avg_token_input_estimate',
    'avg_token_output_estimate',
    'avg_latency_ms',
    'strongest_new_character_patterns',
    'strongest_lost_patterns',
    'comparison_to_original',
    'pilot_result',
    'recommended_next_step',
    'notes'
  ];
}

if (typeof _providerCharacterMicroExpressionClusterHeaders_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionBundleRowsToObjects_ !== 'function') {
  function _providerCharacterMicroExpressionBundleRowsToObjects_(bundle) {
    var rows = (bundle && bundle.rows) || [];
    var headers = (bundle && bundle.headers) || [];
    var out = [];
    for (var i = 0; i < rows.length; i++) {
      var raw = rows[i] || [];
      var obj = {};
      for (var j = 0; j < headers.length; j++) obj[headers[j]] = j < raw.length ? raw[j] : '';
      out.push(obj);
    }
    return out;
  }
}

if (typeof _providerCharacterMicroExpressionSplitPhrases_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionTrimWords_ !== 'function') {
  function _providerCharacterMicroExpressionTrimWords_(text, minWords, maxWords) {
    var tokens = _providerCharacterMicroExpressionTokenize_(text);
    if (!tokens.length) return '';
    var end = Math.min(tokens.length, maxWords || 8);
    if (end < (minWords || 3)) return '';
    return tokens.slice(0, end).join(' ');
  }
}

if (typeof _providerCharacterMicroExpressionTokenize_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionStopTokens_ !== 'function') {
  function _providerCharacterMicroExpressionStopTokens_() {
    return {
      a: true, an: true, and: true, as: true, at: true, be: true, by: true, for: true, from: true,
      if: true, in: true, into: true, is: true, it: true, its: true, no: true, not: true, of: true,
      on: true, or: true, out: true, the: true, to: true, too: true, with: true, without: true,
      this: true, that: true, these: true, those: true, are: true, was: true, were: true, can: true,
      will: true, would: true, should: true, could: true, may: true, might: true, maybe: true,
      provider: true, forecast: true, signal: true, signals: true, print: true, release: true, data: true,
      model: true, models: true, path: true, paths: true, factor: true, factors: true, event: true,
      reaction: true, move: true, moves: true, moveing: true, market: true, usd: false, fx: false, jpy: false
    };
  }
}

if (typeof _providerCharacterMicroExpressionJaccard_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionBuildClusterRows_ !== 'function') {
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
          clusterMatch.representative_row = _providerCharacterMicroExpressionPickRepresentativeRow_(clusterMatch.representative_row, row);
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
        var providerBaseline = _providerCharacterMicroExpressionProviderBaseline_(providerRows);
        var clusterMetrics = _providerCharacterMicroExpressionClusterMetrics_(cluster.rows);
        var specificity = _providerCharacterMicroExpressionProviderSpecificity_(cluster, pilotRows);
        clusters.push({
          generated_ts: generatedTs,
          cluster_id: _providerCharacterMicroExpressionClusterId_(provider, j + 1),
          provider: provider,
          cluster_phrase: _providerCharacterMicroExpressionClusterRepresentativePhrase_(cluster),
          representative_terms: _providerCharacterMicroExpressionClusterRepresentativeTerms_(cluster, 5),
          representative_examples: _providerCharacterMicroExpressionClusterRepresentativeExamples_(cluster, 2),
          row_count: cluster.rows.length,
          event_count: Object.keys(cluster.event_ids || {}).length,
          family_distribution: _providerCharacterMicroExpressionCountMapText_(cluster.family_counts, 5),
          avg_economic_dir_ok: clusterMetrics.avg_economic_dir_ok == null ? '' : clusterMetrics.avg_economic_dir_ok,
          avg_forecast_error_abs: clusterMetrics.avg_forecast_error_abs == null ? '' : clusterMetrics.avg_forecast_error_abs,
          better_than_consensus_rate: clusterMetrics.better_than_consensus_rate == null ? '' : clusterMetrics.better_than_consensus_rate,
          provider_specificity_score: specificity == null ? '' : _round4_(specificity),
          economic_separation_hint: _providerCharacterMicroExpressionSeparationHint_(clusterMetrics, providerBaseline),
          notes: 'cluster_tokens=' + _providerCharacterMicroExpressionClusterRepresentativeTerms_(cluster, 5)
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
}

if (typeof _providerCharacterMicroExpressionClusterTokens_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionClusterSimilarity_ !== 'function') {
  function _providerCharacterMicroExpressionClusterSimilarity_(tokensA, tokensB, rowA, rowB) {
    var j = _providerCharacterMicroExpressionJaccard_(tokensA, tokensB);
    var causalA = _providerCharacterMicroExpressionCausalSignature_(rowA);
    var causalB = _providerCharacterMicroExpressionCausalSignature_(rowB);
    var causal = causalA && causalB && causalA === causalB ? 1 : 0;
    return (j * 0.8) + (causal * 0.2);
  }
}

if (typeof _providerCharacterMicroExpressionCausalSignature_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionInitTokenCounts_ !== 'function') {
  function _providerCharacterMicroExpressionInitTokenCounts_(tokens) {
    var map = {};
    for (var i = 0; i < (tokens || []).length; i++) {
      var token = tokens[i];
      if (!token) continue;
      map[token] = (map[token] || 0) + 1;
    }
    return map;
  }
}

if (typeof _providerCharacterMicroExpressionMergeTokenCounts_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionPickRepresentativeRow_ !== 'function') {
  function _providerCharacterMicroExpressionPickRepresentativeRow_(existing, candidate) {
    if (!existing) return candidate;
    if (String(candidate.expression_summary_phrase || '').length > String(existing.expression_summary_phrase || '').length) return candidate;
    if ((candidate.token_cost_estimate || 0) < (existing.token_cost_estimate || 0)) return candidate;
    return existing;
  }
}

if (typeof _providerCharacterMicroExpressionClusterRepresentativePhrase_ !== 'function') {
  function _providerCharacterMicroExpressionClusterRepresentativePhrase_(cluster) {
    var row = cluster.representative_row || (cluster.rows && cluster.rows[0]) || {};
    var phrase = String(row.expression_summary_phrase || row.primary_focus_phrase || row.causal_path_phrase || '').trim();
    if (!phrase) phrase = _providerCharacterMicroExpressionTopTermPhrase_(cluster.token_counts);
    return _providerCharacterMicroExpressionTrimWords_(phrase, 3, 8);
  }
}

if (typeof _providerCharacterMicroExpressionClusterRepresentativeTerms_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionClusterRepresentativeExamples_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionClusterMetrics_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionProviderBaseline_ !== 'function') {
  function _providerCharacterMicroExpressionProviderBaseline_(rows) {
    var m = _providerCharacterMicroExpressionClusterMetrics_(rows);
    return {
      avg_economic_dir_ok: m.avg_economic_dir_ok,
      avg_forecast_error_abs: m.avg_forecast_error_abs,
      better_than_consensus_rate: m.better_than_consensus_rate
    };
  }
}

if (typeof _providerCharacterMicroExpressionProviderSpecificity_ !== 'function') {
  function _providerCharacterMicroExpressionProviderSpecificity_(cluster, allRows) {
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
}

if (typeof _providerCharacterMicroExpressionClusterSignature_ !== 'function') {
  function _providerCharacterMicroExpressionClusterSignature_(cluster) {
    return _providerCharacterMicroExpressionClusterRepresentativeTerms_(cluster, 4);
  }
}

if (typeof _providerCharacterMicroExpressionClusterSignatureFromRow_ !== 'function') {
  function _providerCharacterMicroExpressionClusterSignatureFromRow_(row) {
    return [row.primary_focus_phrase, row.causal_path_phrase, row.uncertainty_phrase].join(' ');
  }
}

if (typeof _providerCharacterMicroExpressionSeparationHint_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionClusterId_ !== 'function') {
  function _providerCharacterMicroExpressionClusterId_(provider, index) {
    var prefix = String(provider || 'provider').toUpperCase().replace(/[^A-Z0-9]+/g, '');
    return 'MEP_' + prefix + '_' + ('000' + Number(index || 0)).slice(-3);
  }
}

if (typeof _providerCharacterMicroExpressionTopTermPhrase_ !== 'function') {
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
}

if (typeof _providerCharacterMicroExpressionUnionTokens_ !== 'function') {
  function _providerCharacterMicroExpressionUnionTokens_(baseTokens, extraTokens) {
    var map = {};
    for (var i = 0; i < (baseTokens || []).length; i++) map[baseTokens[i]] = true;
    for (var j = 0; j < (extraTokens || []).length; j++) map[extraTokens[j]] = true;
    return Object.keys(map);
  }
}

if (typeof _providerCharacterMicroExpressionCountMapText_ !== 'function') {
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
}

function _providerCharacterFreshReplayLoadSources_(warnings) {
  return {
    pilotBundle: _characterResidualReadSheetBundle_('Provider_Character_MicroExpression_Pilot', warnings, false),
    pilotSummaryBundle: _characterResidualReadSheetBundle_('Provider_Character_MicroExpression_Summary', warnings, false),
    economicBundle: _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false),
    predictionsBundle: _characterResidualReadSheetBundle_('Predictions', warnings, false),
    eventBundle: _characterResidualReadSheetBundle_('Event', warnings, true)
  };
}

function _providerCharacterFreshReplayBuildOriginalPredictionLookup_(bundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var map = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.ai_name || row.provider || '').trim();
    if (String(row.type || '').trim().toLowerCase() === 'batch') continue;
    if (!eventId || !provider) continue;
    var key = eventId + '|' + provider;
    if (!map[key] || _providerCharacterFreshReplayRowIsNewer_(row, map[key])) {
      map[key] = {
      event_id: eventId,
      provider: provider,
      ai_name: provider,
      ai_model: String(row.ai_model || '').trim(),
      created_ts: String(row.created_ts || '').trim(),
      type: String(row.type || '').trim(),
      ai_forecast_value: _numOrNull_(row.ai_forecast_value),
      qualitative_result: String(row.qualitative_result || '').trim(),
      expected_move_dir: String(row.expected_move_dir || row.mr_pred_dir || '').trim(),
      expected_move_pips_min: _numOrNull_(row.expected_move_pips_min),
      expected_move_pips_max: _numOrNull_(row.expected_move_pips_max),
      rationale_short: String(row.rationale_short || '').trim(),
      rationale: String(row.rationale || '').trim(),
      attention_primary_factor: String(row.attention_primary_factor || '').trim(),
      attention_factors: String(row.attention_factors || '').trim(),
      attention_factor_1: String(row.attention_factor_1 || '').trim(),
      attention_factor_2: String(row.attention_factor_2 || '').trim(),
      attention_factor_3: String(row.attention_factor_3 || '').trim(),
      attention_summary: String(row.attention_summary || '').trim(),
      mr_pred_dir: String(row.mr_pred_dir || '').trim(),
      mr_pred_net_pips: _numOrNull_(row.mr_pred_net_pips),
      mr_pred_strength: String(row.mr_pred_strength || '').trim(),
      mr_pred_sustain_min: _numOrNull_(row.mr_pred_sustain_min),
      raw_output: String(row.raw_output || '').trim()
      };
    }
  }
  if (!Object.keys(map).length && warnings) warnings.push('missing_source_rows:Predictions');
  return map;
}

function _providerCharacterFreshReplayBuildOriginalEconomicLookup_(bundle, predictionsBundle, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(bundle);
  var usePredictionsFallback = !rows.length && predictionsBundle;
  if (usePredictionsFallback) rows = _providerCharacterMicroExpressionBundleRowsToObjects_(predictionsBundle);
  var latestByKey = {};
  var order = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (String(row.type || '').trim().toLowerCase() === 'batch') continue;
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.ai_name || row.provider || '').trim();
    if (!eventId || !provider) continue;
    var key = eventId + '|' + provider;
    if (!latestByKey.hasOwnProperty(key)) {
      latestByKey[key] = row;
      order.push(key);
      continue;
    }
    var candidateTs = String(row.created_ts || row.generated_ts || '').trim();
    var existingTs = String(latestByKey[key].created_ts || latestByKey[key].generated_ts || '').trim();
    if (candidateTs > existingTs) {
      latestByKey[key] = row;
    }
  }
  var map = {};
  for (var j = 0; j < order.length; j++) {
    var key2 = order[j];
    var row2 = latestByKey[key2] || {};
    map[key2] = {
      event_id: String(row2.event_id || '').trim(),
      provider: String(row2.ai_name || row2.provider || '').trim(),
      ai_name: String(row2.ai_name || row2.provider || '').trim(),
      type: String(row2.type || '').trim(),
      batch_id: String(row2.batch_id || '').trim(),
      indicator_name: String(row2.indicator_name || '').trim(),
      country: String(row2.country || '').trim(),
      genre: String(row2.genre || '').trim(),
      importance: String(row2.importance || '').trim(),
      release_ts: String(row2.release_ts || '').trim(),
      outcome_family: String(row2.family || '').trim() || 'other',
      consensus_value: _numOrNull_(row2.consensus_value),
      prev_revision: _numOrNull_(row2.prev_revision),
      released_value: _numOrNull_(row2.released_value),
      value_dir_ok: String(row2.value_dir_ok || row2.forecast_dir_ok || '').trim(),
      value_error_abs: _numOrNull_(row2.value_error_abs != null ? row2.value_error_abs : row2.forecast_error_abs),
      value_error_pct: _numOrNull_(row2.value_error_pct),
      actual_surprise_dir: String(row2.actual_surprise_dir || '').trim(),
      qualitative_result: String(row2.qualitative_result || '').trim(),
      attention_primary_factor: String(row2.attention_primary_factor || '').trim(),
      attention_factors: String(row2.attention_factors || '').trim()
    };
  }
  if (!Object.keys(map).length && warnings) warnings.push(usePredictionsFallback ? 'missing_source_rows:PredictionsFallback' : 'missing_source_rows:Economic_Value_Accuracy');
  return map;
}

function _providerCharacterFreshReplayRowIsNewer_(candidate, existing) {
  var candidateTs = String(candidate && (candidate.created_ts || candidate.generated_ts) || '').trim();
  var existingTs = String(existing && (existing.created_ts || existing.generated_ts) || '').trim();
  if (candidateTs !== existingTs) return candidateTs > existingTs;
  return true;
}

function _providerCharacterFreshReplayBuildEventPool_(pilotBundle, originalPredictionLookup, originalEconomicLookup, providers, warnings) {
  var rows = _providerCharacterMicroExpressionBundleRowsToObjects_(pilotBundle);
  var providerNames = (providers || []).map(function(p) { return String(p.name || '').trim(); }).filter(Boolean);
  var byEvent = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    if (String(row.type || '').trim().toLowerCase() === 'batch') continue;
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (!eventId || !provider) continue;
    var key = eventId;
    if (!byEvent[key]) {
      byEvent[key] = {
        event_id: eventId,
        release_ts: String(row.release_ts || '').trim(),
        indicator_name: String(row.indicator_name || '').trim(),
        importance: String(row.importance || '').trim(),
        outcome_family: String(row.outcome_family || '').trim(),
        family_key: _providerCharacterFreshReplayFamilyKey_(String(row.outcome_family || ''), String(row.indicator_name || '')),
        providers: {},
        rows: [],
        sample_source: 'pilot',
        interest_score: 0
      };
    }
    byEvent[key].providers[provider] = true;
    byEvent[key].rows.push(row);
  }

  var out = [];
  Object.keys(byEvent).forEach(function(eventId) {
    var item = byEvent[eventId];
    var coverage = 0;
    for (var i = 0; i < providerNames.length; i++) {
      var providerName = providerNames[i];
      var k = eventId + '|' + providerName;
      if (originalPredictionLookup[k]) coverage += 1;
    }
    if (coverage < providerNames.length) {
      return;
    }
    item.provider_count = coverage;
    item.interest_score = _providerCharacterFreshReplayEventInterestScore_(item.rows, item.provider_count);
    out.push(item);
  });

  if (!out.length && warnings) warnings.push('pilot_event_pool_empty_or_incomplete');
  return out;
}

function _providerCharacterFreshReplayBuildFallbackEventPool_(originalPredictionLookup, originalEconomicLookup, providers, warnings) {
  var providerNames = (providers || []).map(function(p) { return String(p.name || '').trim(); }).filter(Boolean);
  var byEvent = {};
  Object.keys(originalPredictionLookup || {}).forEach(function(key) {
    var pred = originalPredictionLookup[key];
    var econ = originalEconomicLookup[key] || pred;
    if (!pred) return;
    var eventId = String(pred.event_id || '').trim();
    if (!eventId) return;
    if (!byEvent[eventId]) {
      byEvent[eventId] = {
        event_id: eventId,
        release_ts: String(pred.release_ts || econ.release_ts || '').trim(),
        indicator_name: String(pred.indicator_name || econ.indicator_name || '').trim(),
        importance: String(pred.importance || econ.importance || '').trim(),
        outcome_family: String(econ.outcome_family || '').trim() || 'other',
        family_key: _providerCharacterFreshReplayFamilyKey_(String(econ.outcome_family || ''), String(pred.indicator_name || econ.indicator_name || '')),
        providers: {},
        rows: [],
        sample_source: 'economic_fallback',
        interest_score: 0
      };
    }
    byEvent[eventId].providers[pred.provider || pred.ai_name || 'unknown'] = true;
    byEvent[eventId].rows.push({
      token_cost_estimate: '',
      expression_summary_phrase: String(pred.rationale_short || pred.rationale || '').trim()
    });
  });

  var out = [];
  Object.keys(byEvent).forEach(function(eventId) {
    var item = byEvent[eventId];
    var coverage = 0;
    for (var i = 0; i < providerNames.length; i++) {
      var providerName = providerNames[i];
      var k = eventId + '|' + providerName;
      if (originalPredictionLookup[k]) coverage += 1;
    }
    if (coverage < providerNames.length) return;
    item.provider_count = coverage;
    item.interest_score = _providerCharacterFreshReplayEventInterestScore_(item.rows, item.provider_count);
    out.push(item);
  });
  if (!out.length && warnings) warnings.push('fallback_event_pool_empty');
  return out;
}

function _providerCharacterFreshReplaySelectSampleEvents_(eventPool, targetCount, warnings) {
  var pool = (eventPool || []).slice();
  var targetFamilies = _providerCharacterFreshReplayTargetFamilyKeys_();
  var selected = [];
  var used = {};
  var perFamilyTarget = 3;

  function sortFn(a, b) {
    var as = _numOrNull_(a.interest_score) || 0;
    var bs = _numOrNull_(b.interest_score) || 0;
    if (bs !== as) return bs - as;
    if (String(a.release_ts || '') !== String(b.release_ts || '')) return String(a.release_ts || '').localeCompare(String(b.release_ts || ''));
    return String(a.event_id || '').localeCompare(String(b.event_id || ''));
  }

  var byFamily = _providerCharacterFreshReplayBucketEventsByFamily_(pool);
  for (var i = 0; i < targetFamilies.length; i++) {
    var family = targetFamilies[i];
    var list = (byFamily[family] || []).slice().sort(sortFn);
    for (var j = 0; j < list.length && _providerCharacterFreshReplayFamilySelectionCount_(selected, family) < perFamilyTarget && selected.length < targetCount; j++) {
      var item = list[j];
      if (used[item.event_id]) continue;
      used[item.event_id] = true;
      selected.push(item);
    }
  }

  if (selected.length < targetCount) {
    var remainder = pool.filter(function(item) {
      return !used[item.event_id];
    }).sort(sortFn);
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

function _providerCharacterFreshReplayBuildPrompt_(ev) {
  var eventFamily = (typeof deriveOutcomeFamily_ === 'function')
    ? (deriveOutcomeFamily_(String(ev.indicator_name || ''), String(ev.genre || '')) || 'other')
    : _providerCharacterFreshReplayFamilyKey_(String(ev.indicator_name || ''), String(ev.genre || ''));
  var payload = {
    object: 'econ_event',
    event_id: ev.event_id,
    type: ev.type,
    indicator_name: ev.indicator_name,
    release_ts: ev.release_ts,
    consensus_value: (typeof ev.consensus_value === 'number') ? ev.consensus_value : null,
    prev_revision: (typeof ev.prev_revision === 'number') ? ev.prev_revision : null,
    unit: String(ev.unit || '').trim(),
    importance: ev.importance || 'medium',
    event_family: eventFamily,
    experiment: 'provider_character_fresh_vs_original_replay_v1',
    policy: {
      micro_expression_capture: 'Provide short free-form attention phrases, not labels.',
      no_taxonomy_labels: 'Do not use old Character labels, roles, historical context packs, market context packs, surprise packs, or attention-label scaffolding.',
      keep_compact: 'Keep micro-expression fields short and concrete.',
      basic_event_payload_only: 'Use only indicator, release timestamp, consensus, previous/revision, unit, importance, and event family.'
    },
    required_output: {
      object: 'ai_prediction',
      event_id: ev.event_id,
      type: ev.type,
      ai_forecast_value: '(number or null)',
      qualitative_result: '(stronger|weaker|inline)',
      expected_move_dir: '(up|down|flat)',
      expected_move_pips_min: '(number)',
      expected_move_pips_max: '(number)',
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
    'Return ONLY strict JSON (no code fences). Keys required: object,event_id,type,ai_forecast_value,qualitative_result,expected_move_dir,expected_move_pips_min,expected_move_pips_max,rationale_short,primary_focus_phrase,secondary_focus_phrase,ignored_or_discounted_factor_phrase,causal_path_phrase,failure_condition_phrase,confidence_basis_phrase,uncertainty_phrase,expression_summary_phrase,attention_terms. ' +
    'Use ai_prediction as the object. ' +
    'Micro-expression fields must be short, concrete, and natural, ideally 3 to 8 words each. ' +
    'Do not use old Character labels, hidden roles, taxonomy selection, historical context packs, market context packs, surprise packs, or attention-label scaffolding. ' +
    'Do not give trading instructions or guaranteed-profit language. ' +
    'Use only the basic event payload fields in the prompt: indicator_name, release_ts, consensus_value, prev_revision, unit, importance, and event_family.';
  return {
    system: 'You are a macroeconomic forecasting model. Output must be strict JSON and safe for parsing.',
    user: JSON.stringify(payload),
    instruction: instruction,
    cache_scaffold: ''
  };
}

function _providerCharacterFreshReplayNormalizeProviderOutput_(parsed, rawOutput, ev) {
  parsed = parsed || {};
  var out = {
    object: 'ai_prediction',
    event_id: String(parsed.event_id || ev.event_id || '').trim(),
    type: String(parsed.type || ev.type || '').trim(),
    ai_forecast_value: _numOrNull_(parsed.ai_forecast_value),
    qualitative_result: _providerCharacterFreshReplayQualitativeResult_(parsed.qualitative_result),
    expected_move_dir: _providerCharacterFreshReplayDir_(parsed.expected_move_dir),
    expected_move_pips_min: _numOrNull_(parsed.expected_move_pips_min),
    expected_move_pips_max: _numOrNull_(parsed.expected_move_pips_max),
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
  if (!out.expected_move_dir) out.expected_move_dir = out.qualitative_result === 'stronger' ? 'up' : (out.qualitative_result === 'weaker' ? 'down' : 'flat');
  if (!out.expected_move_pips_min && out.expected_move_pips_min !== 0) out.expected_move_pips_min = '';
  if (!out.expected_move_pips_max && out.expected_move_pips_max !== 0) out.expected_move_pips_max = '';
  return out;
}

function _providerCharacterFreshReplayScoreEconomic_(forecastValue, qualitativeResult, economicRow, ev) {
  economicRow = economicRow || {};
  var releasedValue = _numOrNull_(economicRow.released_value);
  var consensusValue = _numOrNull_(economicRow.consensus_value);
  var prevRevision = _numOrNull_(economicRow.prev_revision);
  var actualSurprise = _economicValueAccuracyDirection_(releasedValue, consensusValue, prevRevision);
  var aiValueDir = _economicValueAccuracyAiDirection_({}, {}, forecastValue, consensusValue, prevRevision, false);
  var errorAbs = (releasedValue != null && forecastValue != null) ? _round4_(Math.abs(forecastValue - releasedValue)) : null;
  var dirOk = '';
  if (actualSurprise.dir !== 'unknown' && aiValueDir.dir !== 'unknown') {
    dirOk = aiValueDir.dir === actualSurprise.dir ? 'TRUE' : 'FALSE';
  }
  return {
    replay_economic_dir_ok: dirOk,
    replay_forecast_error_abs: errorAbs,
    actual_surprise_dir: actualSurprise.dir || '',
    ai_value_dir: aiValueDir.dir || ''
  };
}

function _providerCharacterFreshReplayBuildComparisonRows_(generatedTs, replayRunId, freshRows, originalPredictionLookup, originalEconomicLookup, warnings) {
  var rows = [];
  for (var i = 0; i < (freshRows || []).length; i++) {
    var row = freshRows[i] || {};
    var key = String(row.event_id || '').trim() + '|' + String(row.provider || '').trim();
    var originalPred = originalPredictionLookup[key] || {};
    var originalEcon = originalEconomicLookup[key] || originalPred || {};
    var originalPredText = _providerCharacterFreshReplayOriginalPredictionText_(originalPred);
    var replayPredText = _providerCharacterFreshReplayPredictionText_(row);
    var predictionChanged = '';
    if (String(row.provider_call_status || '').toLowerCase() === 'success') {
      var originalForecastValue = _numOrNull_(originalPred.ai_forecast_value);
      var replayForecastValue = _numOrNull_(row.replay_ai_forecast_value);
      var originalQualitativeResult = String(originalPred.qualitative_result || '').trim().toLowerCase();
      var replayQualitativeResult = String(row.replay_qualitative_result || '').trim().toLowerCase();
      var originalMoveDir = String(originalPred.expected_move_dir || originalPred.mr_pred_dir || '').trim().toLowerCase();
      var replayMoveDir = String(row.expected_move_dir || row.replay_expected_move_dir || '').trim().toLowerCase();
      var originalPipsMin = _numOrNull_(originalPred.expected_move_pips_min);
      var replayPipsMin = _numOrNull_(row.expected_move_pips_min);
      var originalPipsMax = _numOrNull_(originalPred.expected_move_pips_max);
      var replayPipsMax = _numOrNull_(row.expected_move_pips_max);
      var valueChanged = (originalForecastValue != null || replayForecastValue != null) ? originalForecastValue !== replayForecastValue : false;
      var qualChanged = originalQualitativeResult !== replayQualitativeResult;
      var dirChanged = originalMoveDir !== replayMoveDir;
      var pipsChanged = originalPipsMin !== replayPipsMin || originalPipsMax !== replayPipsMax;
      predictionChanged = (valueChanged || qualChanged || dirChanged || pipsChanged) ? 'TRUE' : 'FALSE';
    }
    var originalDirOk = String((originalEcon && (originalEcon.value_dir_ok || originalEcon.forecast_dir_ok)) || '').trim();
    var replayDirOk = String(row.replay_economic_dir_ok || '').trim();
    var originalErrorAbs = _numOrNull_(originalEcon ? (originalEcon.value_error_abs != null ? originalEcon.value_error_abs : originalEcon.forecast_error_abs) : null);
    var replayErrorAbs = _numOrNull_(row.replay_forecast_error_abs);
    var accuracyChange = (originalErrorAbs != null && replayErrorAbs != null) ? _round4_(originalErrorAbs - replayErrorAbs) : '';
    var exprGain = _providerCharacterFreshReplayExpressionGainScore_(originalPred, row);
    rows.push({
      generated_ts: generatedTs,
      replay_run_id: replayRunId,
      event_id: String(row.event_id || '').trim(),
      provider: String(row.provider || '').trim(),
      original_prediction: originalPredText,
      replay_prediction: replayPredText,
      prediction_changed: predictionChanged,
      original_dir_ok: originalDirOk,
      replay_dir_ok: replayDirOk,
      original_error_abs: originalErrorAbs == null ? '' : originalErrorAbs,
      replay_error_abs: replayErrorAbs == null ? '' : replayErrorAbs,
      accuracy_change: accuracyChange,
      original_rationale_short: String(originalPred.rationale_short || '').trim(),
      fresh_primary_focus_phrase: String(row.primary_focus_phrase || '').trim(),
      fresh_causal_path_phrase: String(row.causal_path_phrase || '').trim(),
      fresh_failure_condition_phrase: String(row.failure_condition_phrase || '').trim(),
      expression_gain_score: exprGain == null ? '' : exprGain,
      interpretation: _providerCharacterFreshReplayInterpretation_(predictionChanged, exprGain, accuracyChange, row.provider_call_status, originalDirOk, replayDirOk),
      notes: _providerCharacterFreshReplayNotes_(
        'comparison',
        'replay_run_id=' + replayRunId,
        'provider_call_status=' + String(row.provider_call_status || ''),
        'original_prediction=' + (originalPredText ? 'present' : 'missing'),
        'replay_prediction=' + (replayPredText ? 'present' : 'missing')
      )
    });
  }
  if (!rows.length && warnings) warnings.push('comparison_rows_empty');
  return rows;
}

function _providerCharacterFreshReplayBuildSummaryRows_(generatedTs, replayRunId, sampledEvents, freshRows, comparisonRows, clusterRows, originalPredictionLookup, originalEconomicLookup, warnings) {
  var groups = {};
  var providers = {};
  for (var i = 0; i < (freshRows || []).length; i++) {
    var row = freshRows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    providers[provider] = true;
    if (!groups[provider]) groups[provider] = [];
    groups[provider].push(row);
  }
  groups.ALL = freshRows || [];

  var out = [];
  var providerNames = Object.keys(groups).sort(function(a, b) {
    if (a === 'ALL') return 1;
    if (b === 'ALL') return -1;
    return a.localeCompare(b);
  });

  for (var p = 0; p < providerNames.length; p++) {
    var provider = providerNames[p];
    var providerRows = groups[provider] || [];
    var providerComparisons = (comparisonRows || []).filter(function(row) {
      return provider === 'ALL' ? true : String(row.provider || '') === provider;
    });
    var providerClusters = (clusterRows || []).filter(function(row) {
      return provider === 'ALL' ? true : String(row.provider || '') === provider;
    });
    var sampledEventMap = {};
    var successCount = 0;
    var failCount = 0;
    var uniqueExpr = {};
    var gainScores = [];
    var tokenInputValues = [];
    var tokenOutputValues = [];
    var latencyValues = [];
    var originalDirValues = [];
    var replayDirValues = [];
    var originalErrValues = [];
    var replayErrValues = [];
    var changedCount = 0;
    var originalRowsForLostPatterns = [];

    for (var i = 0; i < providerRows.length; i++) {
      var row = providerRows[i];
      if (row.event_id) sampledEventMap[row.event_id] = true;
      if (String(row.provider_call_status || '').toLowerCase() === 'success') successCount += 1;
      else failCount += 1;
      if (row.expression_summary_phrase) uniqueExpr[String(row.expression_summary_phrase)] = true;
      if (_numOrNull_(row.token_input_estimate) != null) tokenInputValues.push(_numOrNull_(row.token_input_estimate));
      if (_numOrNull_(row.token_output_estimate) != null) tokenOutputValues.push(_numOrNull_(row.token_output_estimate));
      if (_numOrNull_(row.latency_ms) != null) latencyValues.push(_numOrNull_(row.latency_ms));
    }

    for (var c = 0; c < providerComparisons.length; c++) {
      var comp = providerComparisons[c];
      if (String(comp.prediction_changed || '').toUpperCase() === 'TRUE') changedCount += 1;
      var gain = _numOrNull_(comp.expression_gain_score);
      if (gain != null) gainScores.push(gain);
      var oDir = String(comp.original_dir_ok || '').trim();
      var rDir = String(comp.replay_dir_ok || '').trim();
      if (oDir === 'TRUE' || oDir === 'FALSE') {
        originalDirValues.push(oDir === 'TRUE' ? 1 : 0);
      }
      if (rDir === 'TRUE' || rDir === 'FALSE') {
        replayDirValues.push(rDir === 'TRUE' ? 1 : 0);
      }
      var oErr = _numOrNull_(comp.original_error_abs);
      var rErr = _numOrNull_(comp.replay_error_abs);
      if (oErr != null) originalErrValues.push(oErr);
      if (rErr != null) replayErrValues.push(rErr);
    }

    Object.keys(originalPredictionLookup || {}).forEach(function(key) {
      var originalRow = originalPredictionLookup[key] || {};
      if (provider !== 'ALL' && String(originalRow.provider || originalRow.ai_name || '').trim() !== String(provider || '').trim()) return;
      if (!sampledEventMap[String(originalRow.event_id || '').trim()]) return;
      originalRowsForLostPatterns.push(originalRow);
    });

    var strongestNew = _providerCharacterFreshReplayStrongestNewPatterns_(providerClusters);
    var strongestLost = _providerCharacterFreshReplayStrongestLostPatterns_(provider, originalRowsForLostPatterns, providerClusters);
    var avgTokenInput = _providerCharacterFreshReplayAverage_(tokenInputValues);
    var avgTokenOutput = _providerCharacterFreshReplayAverage_(tokenOutputValues);
    var avgLatency = _providerCharacterFreshReplayAverage_(latencyValues);
    var avgGain = _providerCharacterFreshReplayAverage_(gainScores);
    var avgOriginalDir = _providerCharacterFreshReplayAverage_(originalDirValues);
    var avgReplayDir = _providerCharacterFreshReplayAverage_(replayDirValues);
    var avgOriginalErr = _providerCharacterFreshReplayAverage_(originalErrValues);
    var avgReplayErr = _providerCharacterFreshReplayAverage_(replayErrValues);
    var predictionChangeRate = providerComparisons.length ? _round4_(changedCount / providerComparisons.length) : '';
    var comparisonNote = _providerCharacterFreshReplayComparisonNote_(avgGain, predictionChangeRate, providerClusters.length, failCount, successCount);
    var result = _providerCharacterFreshReplayResultClass_(avgGain, predictionChangeRate, providerClusters.length, failCount, successCount);

    out.push({
      generated_ts: generatedTs,
      replay_run_id: replayRunId,
      provider: provider,
      sampled_events: Object.keys(sampledEventMap).length,
      replay_rows: providerRows.length,
      successful_provider_calls: successCount,
      failed_provider_calls: failCount,
      original_dir_ok_rate: avgOriginalDir == null ? '' : _round4_(avgOriginalDir),
      replay_dir_ok_rate: avgReplayDir == null ? '' : _round4_(avgReplayDir),
      original_error_abs_avg: avgOriginalErr == null ? '' : _round4_(avgOriginalErr),
      replay_error_abs_avg: avgReplayErr == null ? '' : _round4_(avgReplayErr),
      avg_accuracy_change: _providerCharacterFreshReplayAverageAccuracyChange_(providerComparisons),
      prediction_change_rate: predictionChangeRate,
      avg_expression_gain_score: avgGain == null ? '' : _round4_(avgGain),
      unique_micro_expression_count: Object.keys(uniqueExpr).length,
      cluster_count: providerClusters.length,
      avg_token_input_estimate: avgTokenInput == null ? '' : _round4_(avgTokenInput),
      avg_token_output_estimate: avgTokenOutput == null ? '' : _round4_(avgTokenOutput),
      avg_latency_ms: avgLatency == null ? '' : _round4_(avgLatency),
      strongest_new_character_patterns: strongestNew,
      strongest_lost_patterns: strongestLost,
      comparison_to_original: comparisonNote,
      pilot_result: result.result,
      recommended_next_step: result.next_step,
      notes: result.note + '; sampled_events=' + Object.keys(sampledEventMap).length + '; comparison_rows=' + providerComparisons.length
    });
  }

  if (!out.length && warnings) warnings.push('fresh_replay_summary_empty');
  return out;
}

function _providerCharacterFreshReplayTargetFamilyKeys_() {
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

function _providerCharacterFreshReplayTargetCount_() {
  var raw = '';
  if (typeof PropertiesService !== 'undefined') {
    try {
      raw = PropertiesService.getScriptProperties().getProperty('FRESH_REPLAY_SAMPLE_COUNT') || '';
    } catch (e) {
      raw = '';
    }
  }
  var n = Number(String(raw || '').trim());
  if (!isFinite(n) || n < 1) n = 12;
  return Math.floor(n);
}

function _providerCharacterFreshReplayBucketEventsByFamily_(events) {
  var buckets = {};
  var target = _providerCharacterFreshReplayTargetFamilyKeys_();
  for (var i = 0; i < (events || []).length; i++) {
    var item = events[i] || {};
    var family = String(item.family_key || 'other').trim().toLowerCase() || 'other';
    if (!target[family]) family = 'other';
    if (!buckets[family]) buckets[family] = [];
    buckets[family].push(item);
  }
  return buckets;
}

function _providerCharacterFreshReplayFamilySelectionCount_(selected, family) {
  var count = 0;
  for (var i = 0; i < (selected || []).length; i++) {
    if (String(selected[i].family_key || '') === family) count += 1;
  }
  return count;
}

function _providerCharacterFreshReplayEventInterestScore_(rows, providerCount) {
  var tokenScores = [];
  var uniqueExpr = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var token = _numOrNull_(row.token_cost_estimate);
    if (token != null) tokenScores.push(token);
    var expr = String(row.expression_summary_phrase || '').trim();
    if (expr) uniqueExpr[expr] = true;
  }
  var avgToken = _providerCharacterFreshReplayAverage_(tokenScores) || 0;
  return _round4_(avgToken + (Object.keys(uniqueExpr).length * 2) + (providerCount || 0));
}

function _providerCharacterFreshReplayPhrase_(value, minWords, maxWords) {
  var text = String(value == null ? '' : value).trim();
  if (!text) return '';
  return _providerCharacterMicroExpressionTrimWords_(text, minWords || 3, maxWords || 8);
}

function _providerCharacterFreshReplayAttentionTerms_(value) {
  if (Array.isArray(value)) {
    value = value.join(' ');
  }
  var tokens = _providerCharacterMicroExpressionTokenize_(String(value == null ? '' : value));
  var out = [];
  var seen = {};
  for (var i = 0; i < tokens.length; i++) {
    var token = tokens[i];
    if (!token || seen[token]) continue;
    seen[token] = true;
    out.push(token);
    if (out.length >= 8) break;
  }
  return out.join('|');
}

function _providerCharacterFreshReplayQualitativeResult_(value) {
  var s = String(value == null ? '' : value).trim().toLowerCase();
  return _oneOf_(s, ['stronger', 'weaker', 'inline']) || s;
}

function _providerCharacterFreshReplayDir_(value) {
  var s = String(value == null ? '' : value).trim().toLowerCase();
  return _oneOf_(s, ['up', 'down', 'flat']) || s;
}

function _providerCharacterFreshReplayNumber_(value) {
  var n = _numOrNull_(value);
  return n == null ? '' : n;
}

function _providerCharacterFreshReplayPredictionText_(row) {
  row = row || {};
  var forecastValue = row.ai_forecast_value;
  if (forecastValue == null || forecastValue === '') forecastValue = row.replay_ai_forecast_value;
  var qualitativeResult = row.qualitative_result;
  if (!qualitativeResult) qualitativeResult = row.replay_qualitative_result;
  var moveDir = row.expected_move_dir;
  if (!moveDir) moveDir = row.replay_expected_move_dir;
  var pipsMin = row.expected_move_pips_min;
  if (pipsMin == null || pipsMin === '') pipsMin = row.replay_expected_move_pips_min;
  var pipsMax = row.expected_move_pips_max;
  if (pipsMax == null || pipsMax === '') pipsMax = row.replay_expected_move_pips_max;
  return [
    'value=' + (forecastValue == null || forecastValue === '' ? '' : forecastValue),
    'qual=' + String(qualitativeResult || '').trim(),
    'dir=' + String(moveDir || '').trim(),
    'pips=' + (pipsMin == null || pipsMin === '' ? '' : pipsMin) + '-' + (pipsMax == null || pipsMax === '' ? '' : pipsMax)
  ].join('; ');
}

function _providerCharacterFreshReplayOriginalPredictionText_(row) {
  row = row || {};
  return [
    'value=' + (row.ai_forecast_value == null || row.ai_forecast_value === '' ? '' : row.ai_forecast_value),
    'qual=' + String(row.qualitative_result || '').trim(),
    'dir=' + String(row.expected_move_dir || row.mr_pred_dir || '').trim(),
    'pips=' + (row.expected_move_pips_min == null || row.expected_move_pips_min === '' ? '' : row.expected_move_pips_min) + '-' + (row.expected_move_pips_max == null || row.expected_move_pips_max === '' ? '' : row.expected_move_pips_max)
  ].join('; ');
}

function _providerCharacterFreshReplayExpressionGainScore_(originalRow, freshRow) {
  var originalScore = _providerCharacterFreshReplayExpressionFootprint_(originalRow, true);
  var freshScore = _providerCharacterFreshReplayExpressionFootprint_(freshRow, false);
  if (originalScore == null || freshScore == null) return '';
  return _round4_(freshScore - originalScore);
}

function _providerCharacterFreshReplayExpressionFootprint_(row, isOriginal) {
  row = row || {};
  var fields = isOriginal
    ? [
        row.rationale_short,
        row.rationale,
        row.attention_primary_factor,
        row.attention_factors,
        row.attention_factor_1,
        row.attention_factor_2,
        row.attention_factor_3,
        row.attention_summary
      ]
    : [
        row.primary_focus_phrase,
        row.secondary_focus_phrase,
        row.ignored_or_discounted_factor_phrase,
        row.causal_path_phrase,
        row.failure_condition_phrase,
        row.confidence_basis_phrase,
        row.uncertainty_phrase,
        row.expression_summary_phrase,
        row.attention_terms
      ];
  var count = 0;
  var text = [];
  for (var i = 0; i < fields.length; i++) {
    var item = String(fields[i] || '').trim();
    if (!item) continue;
    count += 1;
    text.push(item);
  }
  var tokens = _providerCharacterMicroExpressionTokenize_(text.join(' '));
  return count + (tokens.length / 25);
}

function _providerCharacterFreshReplayInterpretation_(predictionChanged, exprGain, accuracyChange, status, originalDirOk, replayDirOk) {
  if (String(status || '').toLowerCase() !== 'success') return 'inconclusive';
  var gain = _numOrNull_(exprGain);
  var acc = _numOrNull_(accuracyChange);
  if (gain == null) {
    return 'inconclusive';
  }
  if (gain >= 2 && predictionChanged === 'FALSE' && acc != null && acc >= 0) {
    return 'same prediction, richer direct capture';
  }
  if (gain >= 2 && predictionChanged === 'TRUE') {
    return 'richer capture with replay drift';
  }
  if (gain >= 0.5 && predictionChanged === 'FALSE') {
    return 'slightly richer, largely stable';
  }
  if (gain < 0.5 && predictionChanged === 'FALSE') {
    return 'little new character visibility';
  }
  if (gain < 0.5 && predictionChanged === 'TRUE') {
    return 'prediction drift without clear gain';
  }
  if (acc != null && acc > 0) {
    return 'fresh capture improves accuracy';
  }
  if (acc != null && acc < 0) {
    return 'fresh capture weakens accuracy';
  }
  return 'mixed';
}

function _providerCharacterFreshReplayComparisonNote_(avgGain, predictionChangeRate, clusterCount, failCount, successCount) {
  var gain = _numOrNull_(avgGain);
  var change = _numOrNull_(predictionChangeRate);
  if (successCount <= 0) return 'no successful provider calls';
  if (failCount > successCount) return 'runtime heavy with low capture confidence';
  if (gain != null && gain >= 2 && change != null && change <= 0.6 && clusterCount >= 4) {
    return 'fresh capture is richer than original compressed outputs';
  }
  if (gain != null && gain >= 1) {
    return 'fresh capture adds meaningful structure';
  }
  if (gain != null && gain < 1 && change != null && change <= 0.6) {
    return 'fresh capture is only modestly richer';
  }
  return 'fresh capture differs but remains mixed';
}

function _providerCharacterFreshReplayResultClass_(avgGain, predictionChangeRate, clusterCount, failCount, successCount) {
  if (successCount <= 0) {
    return { result: 'failed_runtime_or_extraction', next_step: 'fix_extraction_path', note: 'no_successful_provider_calls' };
  }
  var gain = _numOrNull_(avgGain);
  var change = _numOrNull_(predictionChangeRate);
  if (failCount > successCount * 0.5) {
    return { result: 'failed_runtime_or_extraction', next_step: 'reduce_scope_or_retry', note: 'failures_exceed_successes' };
  }
  if (gain != null && gain >= 1.5 && clusterCount >= 4) {
    return { result: 'promising_continue', next_step: 'run_larger_fresh_replay', note: 'richer_capture_and_clean_clusters' };
  }
  if (gain != null && gain >= 0.5) {
    return { result: 'mixed_continue_cautiously', next_step: 'expand_sample_and_monitor_drift', note: 'some_richer_structure_but_not_uniform' };
  }
  if (change != null && change > 0.75) {
    return { result: 'mixed_continue_cautiously', next_step: 'separate_prediction_drift_from_expression_gain', note: 'high_prediction_drift' };
  }
  return { result: 'weak_do_not_scale', next_step: 'hold_for_review', note: 'limited_expression_gain' };
}

function _providerCharacterFreshReplayStrongestNewPatterns_(clusters) {
  var list = (clusters || []).slice().sort(function(a, b) {
    var as = _numOrNull_(a.provider_specificity_score) || 0;
    var bs = _numOrNull_(b.provider_specificity_score) || 0;
    if (bs !== as) return bs - as;
    if ((b.row_count || 0) !== (a.row_count || 0)) return (b.row_count || 0) - (a.row_count || 0);
    return String(a.cluster_id || '').localeCompare(String(b.cluster_id || ''));
  }).slice(0, 3);
  return list.map(function(item) {
    return String(item.cluster_phrase || '').trim();
  }).filter(Boolean).join(' | ');
}

function _providerCharacterFreshReplayStrongestLostPatterns_(provider, originalRows, clusters) {
  var originalCounts = {};
  for (var j = 0; j < originalRows.length; j++) {
    var phrases = _providerCharacterFreshReplayOriginalPhraseCandidates_(originalRows[j]);
    for (var p = 0; p < phrases.length; p++) {
      var phrase = phrases[p];
      if (!phrase) continue;
      originalCounts[phrase] = (originalCounts[phrase] || 0) + 1;
    }
  }

  var freshClusterPhrases = [];
  for (var k = 0; k < (clusters || []).length; k++) {
    var cluster = clusters[k] || {};
    if (String(cluster.provider || '').trim() !== String(provider || '').trim()) continue;
    if (cluster.cluster_phrase) freshClusterPhrases.push(String(cluster.cluster_phrase || '').trim());
    if (cluster.representative_terms) freshClusterPhrases.push(String(cluster.representative_terms || '').replace(/\|/g, ' '));
    if (cluster.representative_examples) freshClusterPhrases.push(String(cluster.representative_examples || '').replace(/\|/g, ' '));
  }

  var candidates = [];
  Object.keys(originalCounts).forEach(function(phrase) {
    var best = 0;
    for (var x = 0; x < freshClusterPhrases.length; x++) {
      var score = _providerCharacterFreshReplayPhraseSimilarity_(phrase, freshClusterPhrases[x]);
      if (score > best) best = score;
    }
    if (best < 0.42) {
      candidates.push({ phrase: phrase, count: originalCounts[phrase], score: best });
    }
  });

  candidates.sort(function(a, b) {
    if (b.count !== a.count) return b.count - a.count;
    if (b.score !== a.score) return b.score - a.score;
    return String(a.phrase || '').localeCompare(String(b.phrase || ''));
  });
  return candidates.slice(0, 3).map(function(item) {
    return item.phrase;
  }).join(' | ');
}

function _providerCharacterFreshReplayBuildOriginalRowsForProvider_(originalPredictionLookup, provider, sampledEventMap) {
  var rows = [];
  Object.keys(originalPredictionLookup || {}).forEach(function(key) {
    var row = originalPredictionLookup[key] || {};
    if (String(row.provider || row.ai_name || '').trim() !== String(provider || '').trim()) return;
    if (!sampledEventMap[String(row.event_id || '').trim()]) return;
    rows.push(row);
  });
  return rows;
}

function _providerCharacterFreshReplayOriginalPhraseCandidates_(row) {
  row = row || {};
  var fields = [
    row.original_rationale_short,
    row.rationale_short,
    row.rationale,
    row.attention_primary_factor,
    row.attention_factors,
    row.attention_summary,
    row.attention_factor_1,
    row.attention_factor_2,
    row.attention_factor_3
  ];
  var out = [];
  var seen = {};
  for (var i = 0; i < fields.length; i++) {
    var text = String(fields[i] || '').trim();
    if (!text) continue;
    var phrases = _providerCharacterMicroExpressionSplitPhrases_(text);
    for (var j = 0; j < phrases.length; j++) {
      var phrase = _providerCharacterMicroExpressionTrimWords_(phrases[j], 3, 8);
      if (!phrase || seen[phrase]) continue;
      seen[phrase] = true;
      out.push(phrase);
    }
  }
  return out;
}

function _providerCharacterFreshReplayPhraseSimilarity_(a, b) {
  var ta = _providerCharacterMicroExpressionTokenize_(String(a || ''));
  var tb = _providerCharacterMicroExpressionTokenize_(String(b || ''));
  return _providerCharacterMicroExpressionJaccard_(ta, tb);
}

function _providerCharacterFreshReplayAverage(values) {
  var sum = 0;
  var count = 0;
  for (var i = 0; i < (values || []).length; i++) {
    var n = _numOrNull_(values[i]);
    if (n == null) continue;
    sum += Number(n || 0);
    count += 1;
  }
  return count ? (sum / count) : null;
}

function _providerCharacterFreshReplayAverage_(values) {
  return _providerCharacterFreshReplayAverage(values);
}

function _providerCharacterFreshReplayAverageAccuracyChange_(comparisons) {
  var vals = [];
  for (var i = 0; i < (comparisons || []).length; i++) {
    var row = comparisons[i] || {};
    var change = _numOrNull_(row.accuracy_change);
    if (change != null) vals.push(change);
  }
  return _providerCharacterFreshReplayAverage(vals);
}

function _providerCharacterFreshReplayUniqueEventCount_(rows) {
  var seen = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (String(row.event_id || '').trim()) seen[String(row.event_id || '').trim()] = true;
  }
  return Object.keys(seen).length;
}

function _providerCharacterFreshReplayNotes_() {
  var parts = [];
  for (var i = 0; i < arguments.length; i++) {
    var item = String(arguments[i] || '').trim();
    if (item) parts.push(item);
  }
  return parts.join('; ');
}

function _providerCharacterFreshReplayFamilyKey_(family, indicatorName) {
  var text = (String(family || '') + ' ' + String(indicatorName || '')).toLowerCase();
  if (/inflation|cpi|ppi|prices|core pce/.test(text)) return 'inflation';
  if (/labor|employment|payroll|jobs|unemployment|claims|wage/.test(text)) return 'labor';
  if (/growth|gdp|activity|production|orders|sales/.test(text)) return 'growth';
  if (/central bank|fomc|fed|rate|rates|yield|treasury|policy|powell|minutes|speech|testimony/.test(text)) return 'central_bank';
  if (/sentiment|consumer confidence|u\.?michigan|consumer sentiment|confidence/.test(text)) return 'sentiment';
  if (/consumer|retail|spending|demand/.test(text)) return 'consumer';
  if (/housing|mortgage|home|building permits|starts/.test(text)) return 'housing';
  if (/manufactur|pmi|ism|factory|durable/.test(text)) return 'manufacturing';
  if (/energy|oil|wti|crude|inventory|gas/.test(text)) return 'energy';
  return String(family || 'other').trim().toLowerCase() || 'other';
}
