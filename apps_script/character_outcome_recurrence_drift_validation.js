/*******************************************************
 * character_outcome_recurrence_drift_validation.js
 * - Diagnostic-only Character -> Outcome Recurrence + Drift Validation v1
 * - Compares recurrence of surviving Character -> Outcome traits across
 *   independent chronological blocks and measures provider-character drift
 *******************************************************/

function menuBuildCharacterOutcomeRecurrenceDriftValidation_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildCharacterOutcomeRecurrenceDriftValidation_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Character outcome recurrence drift validation -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Recurrence=' + (res.recurrence_rows_written || 0) +
      ' | Drift=' + (res.drift_rows_written || 0) +
      ' | Detail=' + (res.block_detail_rows_written || 0),
      'Character Outcome Recurrence + Drift',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Character outcome recurrence drift validation -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildCharacterOutcomeRecurrenceDriftValidation_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _characterOutcomeRecurrenceLoadSources_(warnings);
  var traitDefs = _characterOutcomeRecurrenceLoadTraitUniverse_(warnings);
  var traitDefsByProvider = _characterOutcomeRecurrenceGroupTraitsByProvider_(traitDefs);

  if (!traitDefs.length) {
    warnings.push('missing_traits:falsification_report_and_fallback_list');
  }

  var eventPool = _characterOutcomeRecurrenceBuildEventPool_(sources, warnings);
  var blocks = _characterOutcomeRecurrenceSelectBlocks_(eventPool, warnings);

  var discoveryResult = _characterOutcomeRecurrenceBuildBlockResult_(
    generatedTs,
    'discovery',
    blocks.discovery.eventIds,
    traitDefsByProvider,
    sources.outcomeLookup,
    sources.residualLookup,
    warnings
  );
  var validationResult = _characterOutcomeRecurrenceBuildBlockResult_(
    generatedTs,
    'validation',
    blocks.validation.eventIds,
    traitDefsByProvider,
    sources.outcomeLookup,
    sources.residualLookup,
    warnings
  );

  var recurrenceRows = _characterOutcomeRecurrenceBuildRecurrenceRows_(
    generatedTs,
    discoveryResult.rowsByProviderTrait,
    validationResult.rowsByProviderTrait,
    warnings
  );
  var driftRows = _characterOutcomeRecurrenceBuildDriftRows_(
    generatedTs,
    discoveryResult.providerProfiles,
    validationResult.providerProfiles,
    warnings
  );
  var blockDetailRows = discoveryResult.rows.concat(validationResult.rows);
  var interpretationRows = _characterOutcomeRecurrenceBuildInterpretationRows_(
    generatedTs,
    recurrenceRows,
    driftRows,
    warnings
  );

  var recurrenceSheet = getDiagnosticsSheet_('Character_Outcome_Recurrence_Validation', _characterOutcomeRecurrenceValidationHeaders_(), warnings);
  var driftSheet = getDiagnosticsSheet_('Character_Drift_Assessment', _characterOutcomeDriftAssessmentHeaders_(), warnings);
  var blockSheet = getDiagnosticsSheet_('Character_Outcome_Recurrence_Block_Detail', _characterOutcomeRecurrenceBlockHeaders_(), warnings);
  var interpretationSheet = getDiagnosticsSheet_('Character_Outcome_Recurrence_Interpretation', _characterOutcomeRecurrenceInterpretationHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    recurrenceSheet.sheet,
    recurrenceSheet.headers,
    _characterResidualObjectsToRows_(recurrenceRows, recurrenceSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    driftSheet.sheet,
    driftSheet.headers,
    _characterResidualObjectsToRows_(driftRows, driftSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    blockSheet.sheet,
    blockSheet.headers,
    _characterResidualObjectsToRows_(blockDetailRows, blockSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    interpretationSheet.sheet,
    interpretationSheet.headers,
    _characterResidualObjectsToRows_(interpretationRows, interpretationSheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    recurrence_sheet: recurrenceSheet.sheet.getName(),
    drift_sheet: driftSheet.sheet.getName(),
    block_sheet: blockSheet.sheet.getName(),
    interpretation_sheet: interpretationSheet.sheet.getName(),
    recurrence_rows_written: recurrenceRows.length,
    drift_rows_written: driftRows.length,
    block_detail_rows_written: blockDetailRows.length,
    interpretation_rows_written: interpretationRows.length,
    discovery_event_count: blocks.discovery.eventIds.length,
    validation_event_count: blocks.validation.eventIds.length,
    trait_count: traitDefs.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function _characterOutcomeRecurrenceValidationHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'discovery_sample_size',
    'discovery_present_sample_size',
    'discovery_absent_sample_size',
    'discovery_provider_sample_size',
    'discovery_overall_ok_rate',
    'discovery_dir_ok_rate',
    'discovery_strength_ok_rate',
    'discovery_sustain_ok_rate',
    'discovery_avg_outcome_score',
    'discovery_overall_delta',
    'discovery_dir_delta',
    'discovery_strength_delta',
    'discovery_sustain_delta',
    'discovery_score_delta',
    'validation_sample_size',
    'validation_present_sample_size',
    'validation_absent_sample_size',
    'validation_provider_sample_size',
    'validation_overall_ok_rate',
    'validation_dir_ok_rate',
    'validation_strength_ok_rate',
    'validation_sustain_ok_rate',
    'validation_avg_outcome_score',
    'validation_overall_delta',
    'validation_dir_delta',
    'validation_strength_delta',
    'validation_sustain_delta',
    'validation_score_delta',
    'sign_stability',
    'effect_size_stability',
    'sample_depth_warning',
    'confidence',
    'recurrence_score',
    'recurrence_classification',
    'notes'
  ];
}

function _characterOutcomeRecurrenceBlockHeaders_() {
  return [
    'generated_ts',
    'block_label',
    'provider',
    'trait',
    'sample_size',
    'present_sample_size',
    'absent_sample_size',
    'provider_sample_size',
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
    'confidence',
    'classification',
    'sample_depth_warning',
    'notes'
  ];
}

function _characterOutcomeDriftAssessmentHeaders_() {
  return [
    'generated_ts',
    'provider',
    'block_label',
    'comparison_block_label',
    'row_count',
    'trait_prevalence_summary',
    'direction_distribution',
    'risk_language_distribution',
    'uncertainty_pattern_distribution',
    'emphasized_factor_distribution',
    'ignored_factor_distribution',
    'rationale_style_tag_distribution',
    'dominant_risk_language',
    'dominant_uncertainty_pattern',
    'dominant_emphasized_factors',
    'dominant_ignored_factors',
    'dominant_rationale_style_tags',
    'profile_similarity_score',
    'drift_classification',
    'notes'
  ];
}

function _characterOutcomeRecurrenceInterpretationHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'recurrence_result',
    'drift_result',
    'final_interpretation',
    'discovery_score_delta',
    'validation_score_delta',
    'recurrence_score',
    'profile_similarity_score',
    'confidence_level',
    'notes'
  ];
}

function _characterOutcomeRecurrenceLoadSources_(warnings) {
  var outcomeBundle = _characterResidualReadSheetBundle_('Outcome_Ledger', warnings, true);
  var residualBundle = _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false);
  return {
    outcomeBundle: outcomeBundle,
    residualBundle: residualBundle,
    outcomeLookup: _characterOutcomeBuildOutcomeLookup_(outcomeBundle, warnings),
    residualLookup: _characterOutcomeRecurrenceBuildResidualLookup_(residualBundle, warnings)
  };
}

function _characterOutcomeRecurrenceLoadTraitUniverse_(warnings) {
  var bundle = _characterResidualReadSheetBundle_('Character_Outcome_Falsification_Report', warnings, false);
  var traits = [];
  if (bundle) {
    var rows = _characterOutcomeBundleRowsToObjects_(bundle);
    traits = _characterOutcomeRecurrenceLoadTraitUniverseFromReport_(rows);
  }
  if (!traits.length) {
    traits = _characterOutcomeRecurrenceFallbackTraits_();
    warnings.push('trait_universe_fallback:default_survivor_set');
  }
  return traits;
}

function _characterOutcomeRecurrenceLoadTraitUniverseFromReport_(rows) {
  var byKey = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var trait = String(row.trait || '').trim();
    if (!provider || !trait) continue;
    var status = String(row.falsification_status || row.recurrence_status || '').trim().toLowerCase();
    if (status && status !== 'survived' && status !== 'partially_survived') continue;
    var key = provider + '|' + trait;
    if (!byKey[key]) {
      var traitDomains = _characterOutcomeRecurrenceInferTraitDomains_(trait);
      byKey[key] = {
        provider: provider,
        trait: trait,
        domains: traitDomains,
        domain: _characterOutcomeRecurrencePrimaryTraitDomain_(traitDomains),
        source_status: status || 'unknown',
        recurrence_score: _characterResidualNum_(row.recurrence_score),
        confidence_level: String(row.confidence_level || '').trim(),
        priority: _characterOutcomeRecurrenceTraitPriority_(status, row)
      };
    }
  }
  var list = Object.keys(byKey).map(function(key) { return byKey[key]; });
  list.sort(function(a, b) {
    var aPriority = Number(a.priority || 0);
    var bPriority = Number(b.priority || 0);
    if (aPriority !== bPriority) return bPriority - aPriority;
    var aScore = _characterResidualNum_(a.recurrence_score);
    var bScore = _characterResidualNum_(b.recurrence_score);
    if (aScore !== bScore) return (bScore || 0) - (aScore || 0);
    if (String(a.provider).localeCompare(String(b.provider)) !== 0) return String(a.provider).localeCompare(String(b.provider));
    return String(a.trait).localeCompare(String(b.trait));
  });
  return list;
}

function _characterOutcomeRecurrenceTraitPriority_(status, row) {
  var s = String(status || '').toLowerCase();
  var score = _characterResidualNum_(row && row.recurrence_score);
  var conf = String(row && row.confidence_level || '').toLowerCase();
  var priority = 0;
  if (s === 'survived') priority += 100;
  else if (s === 'partially_survived') priority += 50;
  if (conf === 'high') priority += 10;
  else if (conf === 'medium') priority += 5;
  if (score != null) priority += Math.round(score * 10);
  return priority;
}

function _characterOutcomeRecurrenceFallbackTraits_() {
  var pairs = [
    ['Gemini', 'low_signal'],
    ['Gemini', 'confident'],
    ['Gemini', 'mixed_signal'],
    ['Gemini', 'same_direction'],
    ['Gemini', 'provider_directional_vs_flat'],
    ['Gemini', 'unknown'],
    ['OpenAI', 'confident'],
    ['OpenAI', 'uncertainty_language'],
    ['OpenAI', 'mixed_signal'],
    ['Anthropic', 'hidden_detail_risk_language'],
    ['Anthropic', 'scenario_based'],
    ['Anthropic', 'uncertainty_language']
  ];
  var out = [];
  for (var i = 0; i < pairs.length; i++) {
    var provider = pairs[i][0];
    var trait = pairs[i][1];
    var traitDomains = _characterOutcomeRecurrenceInferTraitDomains_(trait);
    out.push({
      provider: provider,
      trait: trait,
      domains: traitDomains,
      domain: _characterOutcomeRecurrencePrimaryTraitDomain_(traitDomains),
      source_status: 'fallback',
      recurrence_score: null,
      confidence_level: '',
      priority: 0
    });
  }
  return out;
}

function _characterOutcomeRecurrenceInferTraitDomains_(trait) {
  var name = String(trait || '').trim().toLowerCase();
  var domains = {};
  var riskLanguage = {
    'low_risk_language': true,
    'normal_risk_language': true,
    'high_risk_language': true,
    'tail_risk_language': true,
    'hidden_detail_risk_language': true,
    'crowded_trade_language': true,
    'uncertainty_language': true
  };
  var uncertaintyPattern = {
    'confident': true,
    'cautious': true,
    'hedged': true,
    'scenario_based': true,
    'low_signal': true,
    'mixed_signal': true,
    'unknown': true
  };
  var direction = {
    'same_direction': true,
    'provider_more_positive': true,
    'provider_more_negative': true,
    'provider_flat_vs_directional': true,
    'provider_directional_vs_flat': true
  };
  var factor = {
    'consensus': true,
    'previous_value': true,
    'surprise_history': true,
    'revision_history': true,
    'family_context': true,
    'signal_quality': true,
    'rates': true,
    'yield_curve': true,
    'usdjpy': true,
    'dxy': true,
    'spx': true,
    'gold': true,
    'wti': true,
    'jp10y': true,
    'us_jp_spread': true,
    'inflation_persistence': true,
    'labor_strength': true,
    'consumer_demand': true,
    'housing_weakness': true,
    'manufacturing_cycle': true,
    'energy_inventory': true,
    'hidden_detail_risk': true,
    'missing_consensus': true,
    'low_signal_event': true,
    'direct_fx_transmission': true,
    'market_whipsaw_risk': true,
    'positioning_or_crowding': true,
    'uncertainty': true,
    'other': true
  };
  if (riskLanguage[name]) domains.risk_language = true;
  if (uncertaintyPattern[name]) domains.uncertainty_pattern = true;
  if (direction[name]) domains.direction_delta_from_baseline = true;
  if (factor[name] || !Object.keys(domains).length) domains.emphasized_factor = true;
  return domains;
}

function _characterOutcomeRecurrencePrimaryTraitDomain_(domains) {
  var keys = Object.keys(domains || {});
  if (!keys.length) return 'emphasized_factor';
  if (keys.indexOf('risk_language') >= 0) return 'risk_language';
  if (keys.indexOf('uncertainty_pattern') >= 0) return 'uncertainty_pattern';
  if (keys.indexOf('direction_delta_from_baseline') >= 0) return 'direction_delta_from_baseline';
  return 'emphasized_factor';
}

function _characterOutcomeRecurrenceGroupTraitsByProvider_(traitDefs) {
  var out = {};
  for (var i = 0; i < (traitDefs || []).length; i++) {
    var def = traitDefs[i] || {};
    var provider = String(def.provider || '').trim();
    if (!provider) continue;
    if (!out[provider]) out[provider] = [];
    out[provider].push(def);
  }
  return out;
}

function _characterOutcomeRecurrenceBuildEventPool_(sources, warnings) {
  var outcomeLookup = sources.outcomeLookup || { by_key: {} };
  var residualLookup = sources.residualLookup || {};
  var eventMap = {};
  var eventsWithResidual = {};

  Object.keys(residualLookup || {}).forEach(function(key) {
    var parts = String(key || '').split('|');
    var eventId = String(parts[0] || '').trim();
    if (eventId) eventsWithResidual[eventId] = true;
  });

  Object.keys(outcomeLookup.by_key || {}).forEach(function(key) {
    var outcome = outcomeLookup.by_key[key] || {};
    var eventId = String(outcome.event_id || '').trim();
    if (!eventId || !eventsWithResidual[eventId]) return;
    var releaseMs = _characterResidualDateMs_(outcome.release_ts);
    if (!eventMap[eventId]) {
      eventMap[eventId] = {
        event_id: eventId,
        release_ms: releaseMs,
        release_ts: String(outcome.release_ts || '').trim(),
        indicator_name: String(outcome.indicator_name || '').trim(),
        country: String(outcome.country || '').trim(),
        outcome_family: String(outcome.outcome_family || '').trim() || 'other',
        count: 0
      };
    }
    eventMap[eventId].count += 1;
    if ((!eventMap[eventId].release_ms || releaseMs < eventMap[eventId].release_ms) && releaseMs) {
      eventMap[eventId].release_ms = releaseMs;
      eventMap[eventId].release_ts = String(outcome.release_ts || '').trim();
    }
  });

  var eventIds = Object.keys(eventMap).sort(function(a, b) {
    var ea = eventMap[a] || {};
    var eb = eventMap[b] || {};
    if ((ea.release_ms || 0) !== (eb.release_ms || 0)) return (ea.release_ms || 0) - (eb.release_ms || 0);
    return String(a).localeCompare(String(b));
  });

  if (eventIds.length < 200) {
    warnings.push('event_pool_shortfall:' + eventIds.length);
  }

  return {
    eventMap: eventMap,
    eventIds: eventIds
  };
}

function _characterOutcomeRecurrenceSelectBlocks_(eventPool, warnings) {
  var eventIds = (eventPool && eventPool.eventIds) || [];
  var discoveryIds = eventIds.slice(0, 100);
  var validationIds = eventIds.slice(100, 200);
  if (discoveryIds.length < 100) warnings.push('discovery_block_shortfall:' + discoveryIds.length);
  if (validationIds.length < 100) warnings.push('validation_block_shortfall:' + validationIds.length);
  var discoverySet = {};
  var validationSet = {};
  for (var i = 0; i < discoveryIds.length; i++) discoverySet[discoveryIds[i]] = true;
  for (var j = 0; j < validationIds.length; j++) validationSet[validationIds[j]] = true;
  return {
    discovery: { label: 'discovery', eventIds: discoveryIds, eventSet: discoverySet },
    validation: { label: 'validation', eventIds: validationIds, eventSet: validationSet }
  };
}

function _characterOutcomeRecurrenceBuildResidualLookup_(bundle, warnings) {
  var rows = _characterOutcomeBundleRowsToObjects_(bundle);
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var key = eventId + '|' + provider;
    if (!out[key]) {
      out[key] = row;
      continue;
    }
    if (_characterOutcomeRecurrenceResidualRowIsNewer_(row, out[key])) {
      out[key] = row;
    }
  }
  return out;
}

function _characterOutcomeRecurrenceResidualRowIsNewer_(candidate, existing) {
  var candidateTs = _characterResidualDateMs_(candidate.generated_ts || candidate.release_ts || candidate.created_ts);
  var existingTs = _characterResidualDateMs_(existing.generated_ts || existing.release_ts || existing.created_ts);
  if (candidateTs !== existingTs) return candidateTs > existingTs;
  return true;
}

function _characterOutcomeRecurrenceBuildBlockResult_(generatedTs, blockLabel, eventIds, traitDefsByProvider, outcomeLookup, residualLookup, warnings) {
  var eventSet = {};
  for (var i = 0; i < (eventIds || []).length; i++) eventSet[eventIds[i]] = true;

  var providerAggs = {};
  var providerTraitAggs = {};
  var providerProfiles = {};
  var rows = [];

  Object.keys(outcomeLookup.by_key || {}).forEach(function(key) {
    var outcome = outcomeLookup.by_key[key] || {};
    var eventId = String(outcome.event_id || '').trim();
    if (!eventId || !eventSet[eventId]) return;
    var provider = String(outcome.provider || '').trim();
    if (!provider) return;
    var residual = residualLookup[key] || null;
    if (!residual) return;

    if (!providerAggs[provider]) providerAggs[provider] = _characterOutcomeRecurrenceBlankOutcomeGroup_();
    _characterOutcomeRecurrenceAccumulateOutcome_(providerAggs[provider], outcome);
    _characterOutcomeRecurrenceAccumulateProfile_(providerProfiles, provider, residual, traitDefsByProvider);

    var traits = traitDefsByProvider[provider] || [];
    for (var t = 0; t < traits.length; t++) {
      var traitDef = traits[t];
      var traitKey = provider + '|' + traitDef.trait;
      if (!providerTraitAggs[traitKey]) {
        providerTraitAggs[traitKey] = {
          provider: provider,
          trait: traitDef.trait,
          present: _characterOutcomeRecurrenceBlankOutcomeGroup_(),
          absent: _characterOutcomeRecurrenceBlankOutcomeGroup_(),
          provider_sample_size: 0
        };
      }
      providerTraitAggs[traitKey].provider_sample_size += 1;
      if (_characterOutcomeTraitMatchesResidual_(traitDef, residual)) {
        _characterOutcomeRecurrenceAccumulateOutcome_(providerTraitAggs[traitKey].present, outcome);
      } else {
        _characterOutcomeRecurrenceAccumulateOutcome_(providerTraitAggs[traitKey].absent, outcome);
      }
    }
  });

  var joinedRows = [];
  Object.keys(providerTraitAggs).sort().forEach(function(key) {
    var g = providerTraitAggs[key];
    var providerBaseline = providerAggs[g.provider] || _characterOutcomeRecurrenceBlankOutcomeGroup_();
    var row = _characterOutcomeRecurrenceFinalizeBlockTraitRow_(generatedTs, blockLabel, g, providerBaseline, warnings);
    joinedRows.push(row);
  });

  return {
    rows: joinedRows,
    rowsByProviderTrait: _characterOutcomeRecurrenceRowsByProviderTrait_(joinedRows),
    providerAggs: providerAggs,
    providerProfiles: providerProfiles
  };
}

function _characterOutcomeRecurrenceBlankOutcomeGroup_() {
  return {
    sample_size: 0,
    overall_ok_count: 0,
    dir_ok_count: 0,
    strength_ok_count: 0,
    sustain_ok_count: 0,
    score_sum: 0
  };
}

function _characterOutcomeRecurrenceAccumulateOutcome_(group, outcome) {
  if (!group || !outcome) return;
  group.sample_size += 1;
  if (String(outcome.overall_ok || '').toUpperCase() === 'TRUE') group.overall_ok_count += 1;
  if (String(outcome.dir_ok || '').toUpperCase() === 'TRUE') group.dir_ok_count += 1;
  if (String(outcome.strength_ok || '').toUpperCase() === 'TRUE') group.strength_ok_count += 1;
  if (String(outcome.sustain_ok || '').toUpperCase() === 'TRUE') group.sustain_ok_count += 1;
  if (outcome.outcome_score !== null && outcome.outcome_score !== undefined && outcome.outcome_score !== '') {
    group.score_sum += Number(outcome.outcome_score || 0);
  }
  group.overall_ok_rate = group.sample_size ? _round4_(group.overall_ok_count / group.sample_size) : null;
  group.dir_ok_rate = group.sample_size ? _round4_(group.dir_ok_count / group.sample_size) : null;
  group.strength_ok_rate = group.sample_size ? _round4_(group.strength_ok_count / group.sample_size) : null;
  group.sustain_ok_rate = group.sample_size ? _round4_(group.sustain_ok_count / group.sample_size) : null;
  group.avg_outcome_score = group.sample_size ? _round4_(group.score_sum / group.sample_size) : null;
}

function _characterOutcomeRecurrenceFinalizeBlockTraitRow_(generatedTs, blockLabel, group, providerBaseline, warnings) {
  var present = group.present || _characterOutcomeRecurrenceBlankOutcomeGroup_();
  var absent = group.absent || _characterOutcomeRecurrenceBlankOutcomeGroup_();
  var sampleSize = Number(present.sample_size || 0);
  var providerSampleSize = Number(group.provider_sample_size || 0);

  var overallDelta = _characterOutcomeDelta_(present.overall_ok_rate, providerBaseline.overall_ok_rate);
  var dirDelta = _characterOutcomeDelta_(present.dir_ok_rate, providerBaseline.dir_ok_rate);
  var strengthDelta = _characterOutcomeDelta_(present.strength_ok_rate, providerBaseline.strength_ok_rate);
  var sustainDelta = _characterOutcomeDelta_(present.sustain_ok_rate, providerBaseline.sustain_ok_rate);
  var scoreDelta = _characterOutcomeDelta_(present.avg_outcome_score, providerBaseline.avg_outcome_score);
  var classification = _characterOutcomeClassify_(scoreDelta, sampleSize);
  var confidence = _characterOutcomeConfidence_(sampleSize);
  var sampleDepthWarning = sampleSize < 20 ? 'thin_sample' : '';
  if (sampleSize < 10) sampleDepthWarning = 'thin_sample;excluded_from_ranking_calculations';

  var notes = [
    'block=' + blockLabel,
    'source=Outcome_Ledger',
    'trait_source=Character_Outcome_Falsification_Report',
    'provider_baseline_rows=' + Number(providerBaseline.sample_size || 0)
  ];
  if (sampleSize < 20) notes.push('thin_sample');
  if (sampleSize < 10) notes.push('excluded_from_ranking_calculations');

  return {
    generated_ts: generatedTs,
    block_label: blockLabel,
    provider: group.provider,
    trait: group.trait,
    sample_size: sampleSize,
    present_sample_size: sampleSize,
    absent_sample_size: Number(absent.sample_size || 0),
    provider_sample_size: providerSampleSize,
    present_overall_ok_rate: present.overall_ok_rate == null ? '' : present.overall_ok_rate,
    absent_overall_ok_rate: absent.overall_ok_rate == null ? '' : absent.overall_ok_rate,
    present_dir_ok_rate: present.dir_ok_rate == null ? '' : present.dir_ok_rate,
    absent_dir_ok_rate: absent.dir_ok_rate == null ? '' : absent.dir_ok_rate,
    present_strength_ok_rate: present.strength_ok_rate == null ? '' : present.strength_ok_rate,
    absent_strength_ok_rate: absent.strength_ok_rate == null ? '' : absent.strength_ok_rate,
    present_sustain_ok_rate: present.sustain_ok_rate == null ? '' : present.sustain_ok_rate,
    absent_sustain_ok_rate: absent.sustain_ok_rate == null ? '' : absent.sustain_ok_rate,
    present_avg_outcome_score: present.avg_outcome_score == null ? '' : present.avg_outcome_score,
    absent_avg_outcome_score: absent.avg_outcome_score == null ? '' : absent.avg_outcome_score,
    overall_delta: overallDelta == null ? '' : overallDelta,
    dir_delta: dirDelta == null ? '' : dirDelta,
    strength_delta: strengthDelta == null ? '' : strengthDelta,
    sustain_delta: sustainDelta == null ? '' : sustainDelta,
    score_delta: scoreDelta == null ? '' : scoreDelta,
    confidence: confidence,
    classification: classification,
    sample_depth_warning: sampleDepthWarning,
    notes: notes.join('; ')
  };
}

function _characterOutcomeRecurrenceRowsByProviderTrait_(rows) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = String(row.provider || '').trim() + '|' + String(row.trait || '').trim();
    if (!key || key === '|') continue;
    out[key] = row;
  }
  return out;
}

function _characterOutcomeRecurrenceAccumulateProfile_(providerProfiles, provider, residual, traitDefsByProvider) {
  if (!providerProfiles[provider]) {
    providerProfiles[provider] = _characterOutcomeRecurrenceBlankProfile_();
  }
  var profile = providerProfiles[provider];
  profile.row_count += 1;

  _characterResidualIncSingle_(profile.risk, String(residual.risk_language || '').trim());
  _characterResidualIncSingle_(profile.uncertainty, String(residual.uncertainty_pattern || '').trim());
  _characterResidualIncSingle_(profile.direction, String(residual.direction_delta_from_baseline || '').trim());
  _characterResidualIncTokens_(profile.factors, _characterResidualPipeSplit_(residual.emphasized_factors));
  _characterResidualIncTokens_(profile.ignored, _characterResidualPipeSplit_(residual.ignored_factors));
  _characterResidualIncTokens_(profile.style_tags, _characterResidualPipeSplit_(residual.rationale_style_tags));

  var traits = traitDefsByProvider[provider] || [];
  for (var i = 0; i < traits.length; i++) {
    if (_characterOutcomeTraitMatchesResidual_(traits[i], residual)) {
      _characterResidualIncSingle_(profile.traits, traits[i].trait);
    }
  }
}

function _characterOutcomeRecurrenceBlankProfile_() {
  return {
    row_count: 0,
    traits: {},
    risk: {},
    uncertainty: {},
    direction: {},
    factors: {},
    ignored: {},
    style_tags: {}
  };
}

function _characterOutcomeRecurrenceBuildDriftRows_(generatedTs, discoveryProfiles, validationProfiles, warnings) {
  var providers = {};
  Object.keys(discoveryProfiles || {}).forEach(function(provider) { providers[provider] = true; });
  Object.keys(validationProfiles || {}).forEach(function(provider) { providers[provider] = true; });

  var rows = [];
  Object.keys(providers).sort().forEach(function(provider) {
    var discovery = discoveryProfiles[provider] || _characterOutcomeRecurrenceBlankProfile_();
    var validation = validationProfiles[provider] || _characterOutcomeRecurrenceBlankProfile_();
    var sim = _characterOutcomeRecurrenceProfileSimilarity_(discovery, validation);
    var classif = _characterOutcomeRecurrenceDriftClassify_(sim);
    var discoverySummary = _characterResidualCountMapText_(discovery.traits, 6);
    var validationSummary = _characterResidualCountMapText_(validation.traits, 6);
    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      block_label: 'discovery',
      comparison_block_label: 'validation',
      row_count: Number(discovery.row_count || 0),
      trait_prevalence_summary: discoverySummary,
      direction_distribution: _characterResidualCountMapText_(discovery.direction, 6),
      risk_language_distribution: _characterResidualCountMapText_(discovery.risk, 6),
      uncertainty_pattern_distribution: _characterResidualCountMapText_(discovery.uncertainty, 6),
      emphasized_factor_distribution: _characterResidualCountMapText_(discovery.factors, 6),
      ignored_factor_distribution: _characterResidualCountMapText_(discovery.ignored, 6),
      rationale_style_tag_distribution: _characterResidualCountMapText_(discovery.style_tags, 6),
      dominant_risk_language: _characterResidualDominantKey_(discovery.risk),
      dominant_uncertainty_pattern: _characterResidualDominantKey_(discovery.uncertainty),
      dominant_emphasized_factors: _characterResidualCountMapText_(discovery.factors, 5),
      dominant_ignored_factors: _characterResidualCountMapText_(discovery.ignored, 5),
      dominant_rationale_style_tags: _characterResidualCountMapText_(discovery.style_tags, 5),
      profile_similarity_score: _round4_(sim),
      drift_classification: classif,
      notes: 'compared_against=validation'
    });
    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      block_label: 'validation',
      comparison_block_label: 'discovery',
      row_count: Number(validation.row_count || 0),
      trait_prevalence_summary: validationSummary,
      direction_distribution: _characterResidualCountMapText_(validation.direction, 6),
      risk_language_distribution: _characterResidualCountMapText_(validation.risk, 6),
      uncertainty_pattern_distribution: _characterResidualCountMapText_(validation.uncertainty, 6),
      emphasized_factor_distribution: _characterResidualCountMapText_(validation.factors, 6),
      ignored_factor_distribution: _characterResidualCountMapText_(validation.ignored, 6),
      rationale_style_tag_distribution: _characterResidualCountMapText_(validation.style_tags, 6),
      dominant_risk_language: _characterResidualDominantKey_(validation.risk),
      dominant_uncertainty_pattern: _characterResidualDominantKey_(validation.uncertainty),
      dominant_emphasized_factors: _characterResidualCountMapText_(validation.factors, 5),
      dominant_ignored_factors: _characterResidualCountMapText_(validation.ignored, 5),
      dominant_rationale_style_tags: _characterResidualCountMapText_(validation.style_tags, 5),
      profile_similarity_score: _round4_(sim),
      drift_classification: classif,
      notes: 'compared_against=discovery'
    });
  });

  return rows;
}

function _characterOutcomeRecurrenceProfileSimilarity_(a, b) {
  var traitSim = _characterOutcomeRecurrenceSimilarity_((a && a.traits) || {}, (b && b.traits) || {});
  var riskSim = _characterOutcomeRecurrenceSimilarity_((a && a.risk) || {}, (b && b.risk) || {});
  var uncertaintySim = _characterOutcomeRecurrenceSimilarity_((a && a.uncertainty) || {}, (b && b.uncertainty) || {});
  var directionSim = _characterOutcomeRecurrenceSimilarity_((a && a.direction) || {}, (b && b.direction) || {});
  var factorSim = _characterOutcomeRecurrenceSimilarity_((a && a.factors) || {}, (b && b.factors) || {});
  var ignoredSim = _characterOutcomeRecurrenceSimilarity_((a && a.ignored) || {}, (b && b.ignored) || {});
  var styleSim = _characterOutcomeRecurrenceSimilarity_((a && a.style_tags) || {}, (b && b.style_tags) || {});
  return (
    (traitSim * 0.25) +
    (riskSim * 0.15) +
    (uncertaintySim * 0.15) +
    (directionSim * 0.10) +
    (factorSim * 0.20) +
    (ignoredSim * 0.10) +
    (styleSim * 0.05)
  );
}

function _characterOutcomeRecurrenceSimilarity_(mapA, mapB) {
  var normA = _characterOutcomeRecurrenceNormalizeMap_(mapA);
  var normB = _characterOutcomeRecurrenceNormalizeMap_(mapB);
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

function _characterOutcomeRecurrenceNormalizeMap_(map) {
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

function _characterOutcomeRecurrenceDriftClassify_(score) {
  var s = Number(score || 0);
  if (s >= 0.85) return 'stable';
  if (s >= 0.70) return 'mild_drift';
  if (s >= 0.55) return 'moderate_drift';
  return 'severe_drift';
}

function _characterOutcomeRecurrenceBuildRecurrenceRows_(generatedTs, discoveryRowsByKey, validationRowsByKey, warnings) {
  var keys = {};
  Object.keys(discoveryRowsByKey || {}).forEach(function(k) { keys[k] = true; });
  Object.keys(validationRowsByKey || {}).forEach(function(k) { keys[k] = true; });

  var rows = [];
  Object.keys(keys).sort().forEach(function(key) {
    var discovery = discoveryRowsByKey[key] || null;
    var validation = validationRowsByKey[key] || null;
    var provider = discovery ? discovery.provider : (validation ? validation.provider : '');
    var trait = discovery ? discovery.trait : (validation ? validation.trait : '');
    var discoveryDelta = discovery ? _characterOutcomeNum_(discovery.score_delta) : null;
    var validationDelta = validation ? _characterOutcomeNum_(validation.score_delta) : null;
    var signStability = _characterOutcomeRecurrenceSignStability_(discoveryDelta, validationDelta);
    var effectStability = _characterOutcomeRecurrenceEffectStability_(discoveryDelta, validationDelta);
    var discoveryDepth = discovery ? Number(discovery.present_sample_size || discovery.sample_size || 0) : 0;
    var validationDepth = validation ? Number(validation.present_sample_size || validation.sample_size || 0) : 0;
    var depthScore = Math.min(1, Math.min(discoveryDepth, validationDepth) / 20);
    var recurrenceScore = (
      (signStability.score * 0.40) +
      (effectStability * 0.50) +
      (depthScore * 0.10)
    );
    var recurrenceClass = _characterOutcomeRecurrenceClassify_(recurrenceScore, discoveryDepth, validationDepth, signStability.label);
    var confidence = _characterOutcomeRecurrenceConfidence_(recurrenceScore, discoveryDepth, validationDepth);
    var sampleDepthWarning = [];
    if (discoveryDepth < 20) sampleDepthWarning.push('discovery_thin_sample');
    if (validationDepth < 20) sampleDepthWarning.push('validation_thin_sample');
    if (discoveryDepth < 10 || validationDepth < 10) sampleDepthWarning.push('excluded_from_ranking_calculations');

    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      trait: trait,
      discovery_sample_size: discovery ? discovery.sample_size : 0,
      discovery_present_sample_size: discovery ? discovery.present_sample_size : 0,
      discovery_absent_sample_size: discovery ? discovery.absent_sample_size : 0,
      discovery_provider_sample_size: discovery ? discovery.provider_sample_size : 0,
      discovery_overall_ok_rate: discovery ? discovery.present_overall_ok_rate : '',
      discovery_dir_ok_rate: discovery ? discovery.present_dir_ok_rate : '',
      discovery_strength_ok_rate: discovery ? discovery.present_strength_ok_rate : '',
      discovery_sustain_ok_rate: discovery ? discovery.present_sustain_ok_rate : '',
      discovery_avg_outcome_score: discovery ? discovery.present_avg_outcome_score : '',
      discovery_overall_delta: discovery ? discovery.overall_delta : '',
      discovery_dir_delta: discovery ? discovery.dir_delta : '',
      discovery_strength_delta: discovery ? discovery.strength_delta : '',
      discovery_sustain_delta: discovery ? discovery.sustain_delta : '',
      discovery_score_delta: discovery ? discovery.score_delta : '',
      validation_sample_size: validation ? validation.sample_size : 0,
      validation_present_sample_size: validation ? validation.present_sample_size : 0,
      validation_absent_sample_size: validation ? validation.absent_sample_size : 0,
      validation_provider_sample_size: validation ? validation.provider_sample_size : 0,
      validation_overall_ok_rate: validation ? validation.present_overall_ok_rate : '',
      validation_dir_ok_rate: validation ? validation.present_dir_ok_rate : '',
      validation_strength_ok_rate: validation ? validation.present_strength_ok_rate : '',
      validation_sustain_ok_rate: validation ? validation.present_sustain_ok_rate : '',
      validation_avg_outcome_score: validation ? validation.present_avg_outcome_score : '',
      validation_overall_delta: validation ? validation.overall_delta : '',
      validation_dir_delta: validation ? validation.dir_delta : '',
      validation_strength_delta: validation ? validation.strength_delta : '',
      validation_sustain_delta: validation ? validation.sustain_delta : '',
      validation_score_delta: validation ? validation.score_delta : '',
      sign_stability: signStability.label,
      effect_size_stability: _round4_(effectStability),
      sample_depth_warning: sampleDepthWarning.join('|'),
      confidence: confidence,
      recurrence_score: _round4_(recurrenceScore),
      recurrence_classification: recurrenceClass,
      notes: _characterOutcomeRecurrenceNotes_(discovery, validation, signStability.label, sampleDepthWarning)
    });
  });
  return rows;
}

function _characterOutcomeRecurrenceSignStability_(discoveryDelta, validationDelta) {
  var a = _characterOutcomeNum_(discoveryDelta);
  var b = _characterOutcomeNum_(validationDelta);
  if (a == null || b == null) return { label: 'unknown', score: 0 };
  var aSign = _characterOutcomeRecurrenceSign_(a);
  var bSign = _characterOutcomeRecurrenceSign_(b);
  if (aSign === 0 && bSign === 0) return { label: 'same_direction', score: 1 };
  if (aSign === bSign) return { label: 'same_direction', score: 1 };
  if (aSign === 0 || bSign === 0) return { label: 'one_neutral', score: 0.5 };
  return { label: 'opposite_direction', score: 0 };
}

function _characterOutcomeRecurrenceSign_(value) {
  var v = Number(value || 0);
  if (Math.abs(v) < 0.0001) return 0;
  return v > 0 ? 1 : -1;
}

function _characterOutcomeRecurrenceEffectStability_(discoveryDelta, validationDelta) {
  var a = _characterOutcomeNum_(discoveryDelta);
  var b = _characterOutcomeNum_(validationDelta);
  if (a == null || b == null) return 0;
  var denom = Math.max(0.05, Math.abs(a) + Math.abs(b));
  var score = 1 - Math.min(1, Math.abs(a - b) / denom);
  return Math.max(0, Math.min(1, score));
}

function _characterOutcomeRecurrenceClassify_(score, discoveryDepth, validationDepth, signLabel) {
  if (Number(discoveryDepth || 0) < 10 || Number(validationDepth || 0) < 10) return 'inconclusive';
  var s = Number(score || 0);
  if (signLabel === 'opposite_direction' && s < 0.75) return 'failed_recurrence';
  if (s >= 0.80) return 'strong_recurrence';
  if (s >= 0.65) return 'moderate_recurrence';
  if (s >= 0.50) return 'weak_recurrence';
  return 'failed_recurrence';
}

function _characterOutcomeRecurrenceConfidence_(score, discoveryDepth, validationDepth) {
  var minDepth = Math.min(Number(discoveryDepth || 0), Number(validationDepth || 0));
  if (minDepth < 10) return 'low';
  if (minDepth < 20) return 'medium';
  if (score >= 0.80 && minDepth >= 20) return 'high';
  if (score >= 0.65) return 'medium';
  return 'low';
}

function _characterOutcomeRecurrenceNotes_(discovery, validation, signLabel, sampleDepthWarning) {
  var notes = [
    'sign_stability=' + signLabel,
    'discovery_rows=' + Number((discovery && discovery.sample_size) || 0),
    'validation_rows=' + Number((validation && validation.sample_size) || 0)
  ];
  if (sampleDepthWarning && sampleDepthWarning.length) notes.push('depth=' + sampleDepthWarning.join('|'));
  return notes.join('; ');
}

function _characterOutcomeRecurrenceBuildInterpretationRows_(generatedTs, recurrenceRows, driftRows, warnings) {
  var driftByProvider = {};
  for (var i = 0; i < (driftRows || []).length; i++) {
    var row = driftRows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!driftByProvider[provider]) {
      driftByProvider[provider] = {
        profile_similarity_score: _characterOutcomeNum_(row.profile_similarity_score),
        drift_classification: String(row.drift_classification || '').trim()
      };
    }
  }

  var rows = [];
  for (var j = 0; j < (recurrenceRows || []).length; j++) {
    var r = recurrenceRows[j] || {};
    var provider = String(r.provider || '').trim();
    var trait = String(r.trait || '').trim();
    var drift = driftByProvider[provider] || { profile_similarity_score: null, drift_classification: 'inconclusive' };
    var recurrenceResult = String(r.recurrence_classification || '').trim();
    var driftResult = String(drift.drift_classification || '').trim() || 'inconclusive';
    var finalInterpretation = _characterOutcomeRecurrenceInterpretFinal_(recurrenceResult, driftResult, r);
    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      trait: trait,
      recurrence_result: recurrenceResult,
      drift_result: driftResult,
      final_interpretation: finalInterpretation,
      discovery_score_delta: r.discovery_score_delta,
      validation_score_delta: r.validation_score_delta,
      recurrence_score: r.recurrence_score,
      profile_similarity_score: drift.profile_similarity_score == null ? '' : _round4_(drift.profile_similarity_score),
      confidence_level: r.confidence || 'low',
      notes: [
        'recurrence=' + recurrenceResult,
        'drift=' + driftResult,
        'sign=' + String(r.sign_stability || '')
      ].join('; ')
    });
  }
  return rows;
}

function _characterOutcomeRecurrenceInterpretFinal_(recurrenceResult, driftResult, row) {
  var recurrence = String(recurrenceResult || '').trim();
  var drift = String(driftResult || '').trim();
  var score = _characterOutcomeNum_(row && row.recurrence_score);
  var discoveryDepth = Number(row && row.discovery_present_sample_size || row && row.discovery_sample_size || 0);
  var validationDepth = Number(row && row.validation_present_sample_size || row && row.validation_sample_size || 0);

  if (discoveryDepth < 10 || validationDepth < 10) return 'inconclusive';
  if (recurrence === 'failed_recurrence') {
    if (drift === 'moderate_drift' || drift === 'severe_drift') return 'drift_contaminated';
    return 'failed_recurrence';
  }
  if (recurrence === 'weak_recurrence') {
    if (drift === 'severe_drift') return 'drift_contaminated';
    return 'weak_recurrence';
  }
  if (recurrence === 'moderate_recurrence') {
    if (drift === 'severe_drift') return 'drift_contaminated';
    return 'moderate_recurrence';
  }
  if (recurrence === 'strong_recurrence') {
    return 'strong_recurrence';
  }
  if (score != null && score < 0.5) {
    if (drift === 'moderate_drift' || drift === 'severe_drift') return 'drift_contaminated';
  }
  return recurrence || 'inconclusive';
}

function _characterOutcomeRecurrenceDominantKey_(map) {
  var top = _characterOutcomeRecurrenceTopCountItems_(map, 1);
  if (!top.length) return '';
  return top[0].key;
}

function _characterOutcomeRecurrenceTopCountItems_(map, limit) {
  var items = [];
  Object.keys(map || {}).forEach(function(key) {
    items.push({ key: key, count: Number(map[key] || 0) });
  });
  items.sort(function(a, b) {
    if (a.count !== b.count) return b.count - a.count;
    return String(a.key).localeCompare(String(b.key));
  });
  return items.slice(0, limit || items.length);
}
