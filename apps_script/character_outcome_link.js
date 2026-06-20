/*******************************************************
 * character_outcome_link.js
 * - Diagnostic-only Character -> Outcome Link v1
 * - Links recurring character traits to outcome deltas
 * - Read-only over Outcome_Ledger / Provider_Character_Residuals / Character_Recurrence_Validation
 *******************************************************/

function menuBuildCharacterOutcomeLink_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildCharacterOutcomeLink_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Character outcome link -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Rows=' + (res.link_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0) +
      ' | Family=' + (res.family_rows_written || 0),
      'Character Outcome Link',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Character outcome link -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildCharacterOutcomeLink_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _characterOutcomeLoadSources_(warnings);
  var traits = _characterOutcomeBuildTraitUniverse_(sources, warnings);
  if (!traits.length) {
    warnings.push('missing_traits:recurrence_validation_and_residual_fallback');
  }

  var residualLookup = _characterOutcomeBuildResidualLookup_(sources.residualBundle, warnings);
  var outcomeLookup = _characterOutcomeBuildOutcomeLookup_(sources.outcomeBundle, warnings);
  var providerBaseline = _characterOutcomeBuildProviderBaselineMap_(outcomeLookup);
  var providerFamilyBaseline = _characterOutcomeBuildProviderFamilyBaselineMap_(outcomeLookup);

  var linkRows = _characterOutcomeBuildLinkRows_(
    generatedTs,
    traits,
    residualLookup,
    outcomeLookup,
    providerBaseline,
    warnings
  );
  var summaryRows = _characterOutcomeBuildSummaryRows_(generatedTs, linkRows);
  var familyRows = _characterOutcomeBuildFamilyRows_(
    generatedTs,
    traits,
    residualLookup,
    outcomeLookup,
    providerFamilyBaseline,
    warnings
  );

  var linkSheet = getDiagnosticsSheet_('Character_Outcome_Link', _characterOutcomeLinkHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Character_Outcome_Summary', _characterOutcomeSummaryHeaders_(), warnings);
  var familySheet = getDiagnosticsSheet_('Character_Outcome_Family_Link', _characterOutcomeFamilyHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    linkSheet.sheet,
    linkSheet.headers,
    _characterResidualObjectsToRows_(linkRows, linkSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    summarySheet.sheet,
    summarySheet.headers,
    _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    familySheet.sheet,
    familySheet.headers,
    _characterResidualObjectsToRows_(familyRows, familySheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    link_sheet: linkSheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    family_sheet: familySheet.sheet.getName(),
    link_rows_written: linkRows.length,
    summary_rows_written: summaryRows.length,
    family_rows_written: familyRows.length,
    trait_count: traits.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function _characterOutcomeLinkHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'sample_size',
    'overall_ok_rate',
    'dir_ok_rate',
    'strength_ok_rate',
    'sustain_ok_rate',
    'avg_outcome_score',
    'baseline_overall_ok_rate',
    'baseline_dir_ok_rate',
    'baseline_strength_ok_rate',
    'baseline_sustain_ok_rate',
    'baseline_outcome_score',
    'overall_delta',
    'dir_delta',
    'strength_delta',
    'sustain_delta',
    'score_delta',
    'confidence',
    'classification',
    'notes'
  ];
}

function _characterOutcomeSummaryHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'sample_size',
    'score_delta',
    'overall_delta',
    'dir_delta',
    'classification',
    'ranking_note'
  ];
}

function _characterOutcomeFamilyHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'outcome_family',
    'sample_size',
    'overall_ok_rate',
    'dir_ok_rate',
    'strength_ok_rate',
    'sustain_ok_rate',
    'avg_outcome_score',
    'baseline_overall_ok_rate',
    'baseline_dir_ok_rate',
    'baseline_strength_ok_rate',
    'baseline_sustain_ok_rate',
    'baseline_outcome_score',
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

function _characterOutcomeLoadSources_(warnings) {
  return {
    recurrenceBundle: _characterResidualReadSheetBundle_('Character_Recurrence_Validation', warnings, false),
    residualBundle: _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false),
    outcomeBundle: _characterOutcomeReadOutcomeBundle_(warnings)
  };
}

function _characterOutcomeReadOutcomeBundle_(warnings) {
  var bundle = _characterResidualReadSheetBundle_('Outcome_Ledger', warnings, true);
  if (bundle) return bundle;

  var fallback = _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false);
  if (!fallback) return null;

  var rows = _characterOutcomeBundleRowsToObjects_(fallback);
  var caseRows = [];
  for (var i = 0; i < rows.length; i++) {
    var rowType = String(rows[i].row_type || '').trim().toLowerCase();
    if (rowType !== 'case') continue;
    caseRows.push(rows[i]);
  }
  if (!caseRows.length) return null;
  fallback.rows = _characterResidualObjectsToRows_(caseRows, fallback.headers);
  return fallback;
}

function _characterOutcomeBuildTraitUniverse_(sources, warnings) {
  var traits = {};
  var recurrenceRows = _characterOutcomeBundleRowsToObjects_(sources.recurrenceBundle);
  if (recurrenceRows && recurrenceRows.length) {
    _characterOutcomeCollectTraitsFromRecurrenceRows_(traits, recurrenceRows);
  }

  if (!Object.keys(traits).length) {
    var residualRows = _characterOutcomeBundleRowsToObjects_(sources.residualBundle);
    if (residualRows && residualRows.length) {
      _characterOutcomeCollectTraitsFromResidualRows_(traits, residualRows);
      warnings.push('trait_universe_fallback:Provider_Character_Residuals');
    }
  }

  var list = Object.keys(traits).map(function(key) { return traits[key]; });
  list.sort(function(a, b) {
    var aSupport = Number(a.support || 0);
    var bSupport = Number(b.support || 0);
    if (aSupport !== bSupport) return bSupport - aSupport;
    return String(a.trait).localeCompare(String(b.trait));
  });
  return list;
}

function _characterOutcomeCollectTraitsFromRecurrenceRows_(traits, rows) {
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim() || 'unknown';
    _characterOutcomeMergeRecurringMap_(traits, provider, 'risk_language', _characterOutcomeParseCountMap_(row.sample_a_risk_distribution), _characterOutcomeParseCountMap_(row.sample_b_risk_distribution));
    _characterOutcomeMergeRecurringMap_(traits, provider, 'uncertainty_pattern', _characterOutcomeParseCountMap_(row.sample_a_uncertainty_distribution), _characterOutcomeParseCountMap_(row.sample_b_uncertainty_distribution));
    _characterOutcomeMergeRecurringMap_(traits, provider, 'emphasized_factor', _characterOutcomeParseCountMap_(row.sample_a_top_emphasized_factors), _characterOutcomeParseCountMap_(row.sample_b_top_emphasized_factors));
    _characterOutcomeMergeRecurringMap_(traits, provider, 'direction_delta_from_baseline', _characterOutcomeParseCountMap_(row.sample_a_direction_distribution), _characterOutcomeParseCountMap_(row.sample_b_direction_distribution));
  }
}

function _characterOutcomeCollectTraitsFromResidualRows_(traits, rows) {
  var counts = {};
  var domains = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim() || 'unknown';
    var risk = String(row.risk_language || '').trim();
    var uncertainty = String(row.uncertainty_pattern || '').trim();
    var direction = String(row.direction_delta_from_baseline || '').trim();
    var factors = _characterResidualPipeSplit_(row.emphasized_factors);
    var styleTags = _characterResidualPipeSplit_(row.rationale_style_tags);
    _characterOutcomeCountTrait_(counts, domains, provider, risk, 'risk_language');
    _characterOutcomeCountTrait_(counts, domains, provider, uncertainty, 'uncertainty_pattern');
    _characterOutcomeCountTrait_(counts, domains, provider, direction, 'direction_delta_from_baseline');
    for (var f = 0; f < factors.length; f++) _characterOutcomeCountTrait_(counts, domains, provider, factors[f], 'emphasized_factor');
    for (var s = 0; s < styleTags.length; s++) _characterOutcomeCountTrait_(counts, domains, provider, styleTags[s], 'rationale_style_tag');
  }

  Object.keys(counts).forEach(function(trait) {
    if (Number(counts[trait] || 0) < 2) return;
    traits[trait] = {
      trait: trait,
      domains: domains[trait] || {},
      support: counts[trait] || 0,
      providers: {}
    };
  });
}

function _characterOutcomeMergeRecurringMap_(traits, provider, domain, mapA, mapB) {
  var all = {};
  Object.keys(mapA || {}).forEach(function(k) { all[k] = true; });
  Object.keys(mapB || {}).forEach(function(k) { all[k] = true; });
  Object.keys(all).forEach(function(trait) {
    if (!mapA[trait] || !mapB[trait]) return;
    if (!traits[trait]) {
      traits[trait] = {
        trait: trait,
        domains: {},
        support: 0,
        providers: {}
      };
    }
    traits[trait].domains[domain] = true;
    traits[trait].support += Math.min(Number(mapA[trait] || 0), Number(mapB[trait] || 0));
    traits[trait].providers[provider] = true;
  });
}

function _characterOutcomeCountTrait_(counts, domains, provider, trait, domain) {
  var t = String(trait || '').trim();
  if (!t) return;
  if (!counts[t]) counts[t] = 0;
  counts[t] += 1;
  if (!domains[t]) domains[t] = {};
  domains[t][domain] = true;
}

function _characterOutcomeParseCountMap_(text) {
  var out = {};
  var s = String(text || '').trim();
  if (!s) return out;
  var parts = s.split('|');
  for (var i = 0; i < parts.length; i++) {
    var part = String(parts[i] || '').trim();
    if (!part) continue;
    var eq = part.lastIndexOf('=');
    if (eq <= 0) continue;
    var key = String(part.slice(0, eq) || '').trim();
    var num = Number(String(part.slice(eq + 1) || '').trim());
    if (!key || !isFinite(num) || num <= 0) continue;
    out[key] = num;
  }
  return out;
}

function _characterOutcomeBuildResidualLookup_(bundle, warnings) {
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
    if (_characterOutcomeResidualRowIsNewer_(row, out[key])) out[key] = row;
  }
  return out;
}

function _characterOutcomeResidualRowIsNewer_(candidate, existing) {
  var candidateTs = _characterResidualDateMs_(candidate.generated_ts || candidate.release_ts || candidate.created_ts);
  var existingTs = _characterResidualDateMs_(existing.generated_ts || existing.release_ts || existing.created_ts);
  if (candidateTs !== existingTs) return candidateTs > existingTs;
  return true;
}

function _characterOutcomeBuildOutcomeLookup_(bundle, warnings) {
  var rows = _characterOutcomeBundleRowsToObjects_(bundle);
  var out = {
    by_key: {},
    by_provider: {},
    by_provider_family: {}
  };

  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (!_characterOutcomeIsScoredRow_(row)) continue;
    var provider = String(row.ai_name || row.provider || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var family = String(row.outcome_family || '').trim() || 'other';
    var key = eventId + '|' + provider;
    var normalizedScore = _characterOutcomeNormalizedScore_(row);
    var obj = {
      generated_ts: String(row.generated_ts || '').trim(),
      event_id: eventId,
      provider: provider,
      batch_id: String(row.batch_id || '').trim(),
      type: String(row.type || '').trim(),
      indicator_name: String(row.indicator_name || '').trim(),
      country: String(row.country || '').trim(),
      outcome_family: family,
      overall_ok: _characterOutcomeTruth_(row.overall_ok),
      dir_ok: _characterOutcomeTruth_(row.mr_dir_ok || row.dir_ok),
      strength_ok: _characterOutcomeTruth_(row.mr_strength_ok),
      sustain_ok: _characterOutcomeTruth_(row.mr_sustain_ok),
      outcome_score: normalizedScore,
      scored_flag: 'TRUE'
    };
    out.by_key[key] = obj;
    if (!out.by_provider[provider]) out.by_provider[provider] = [];
    out.by_provider[provider].push(obj);
    var pfKey = provider + '|' + family;
    if (!out.by_provider_family[pfKey]) out.by_provider_family[pfKey] = [];
    out.by_provider_family[pfKey].push(obj);
  }

  return out;
}

function _characterOutcomeIsScoredRow_(row) {
  return _characterOutcomeTruth_(row.scored_flag) || _characterOutcomeNormalizedScore_(row) !== null;
}

function _characterOutcomeTruth_(value) {
  return _isTrueCell_(value) ? 'TRUE' : 'FALSE';
}

function _characterOutcomeNormalizedScore_(row) {
  if (!row) return null;
  var raw = _characterOutcomeNum_(row.outcome_score);
  if (raw == null && typeof computeOutcomeScore_ === 'function') {
    var computed = computeOutcomeScore_({
      scored_flag: _isTrueCell_(row.scored_flag) ? 'TRUE' : 'FALSE',
      mr_dir_ok: _isTrueCell_(row.mr_dir_ok || row.dir_ok) ? 'TRUE' : 'FALSE',
      mr_strength_ok: _isTrueCell_(row.mr_strength_ok) ? 'TRUE' : 'FALSE',
      mr_sustain_ok: _isTrueCell_(row.mr_sustain_ok) ? 'TRUE' : 'FALSE',
      overall_ok: _isTrueCell_(row.overall_ok) ? 'TRUE' : 'FALSE'
    });
    raw = _characterOutcomeNum_(computed);
  }
  if (raw == null) return null;
  return _round4_(raw / 6);
}

function _characterOutcomeNum_(value) {
  var s = String(value == null ? '' : value).trim();
  if (!s) return null;
  var n = Number(s);
  return isFinite(n) ? n : null;
}

function _characterOutcomeBuildProviderBaselineMap_(outcomeLookup) {
  var out = {};
  Object.keys(outcomeLookup.by_provider || {}).forEach(function(provider) {
    out[provider] = _characterOutcomeAggregateOutcomeRows_(outcomeLookup.by_provider[provider]);
  });
  return out;
}

function _characterOutcomeBuildProviderFamilyBaselineMap_(outcomeLookup) {
  var out = {};
  Object.keys(outcomeLookup.by_provider_family || {}).forEach(function(key) {
    out[key] = _characterOutcomeAggregateOutcomeRows_(outcomeLookup.by_provider_family[key]);
  });
  return out;
}

function _characterOutcomeAggregateOutcomeRows_(rows) {
  var agg = {
    sample_size: 0,
    overall_ok_count: 0,
    dir_ok_count: 0,
    strength_ok_count: 0,
    sustain_ok_count: 0,
    score_sum: 0
  };
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (_characterOutcomeNormalizedScore_(row) == null) continue;
    agg.sample_size += 1;
    if (_characterOutcomeTruth_(row.overall_ok) === 'TRUE') agg.overall_ok_count += 1;
    if (_characterOutcomeTruth_(row.dir_ok) === 'TRUE') agg.dir_ok_count += 1;
    if (_characterOutcomeTruth_(row.strength_ok) === 'TRUE') agg.strength_ok_count += 1;
    if (_characterOutcomeTruth_(row.sustain_ok) === 'TRUE') agg.sustain_ok_count += 1;
    agg.score_sum += _characterOutcomeNormalizedScore_(row);
  }
  agg.overall_ok_rate = agg.sample_size ? _round4_(agg.overall_ok_count / agg.sample_size) : null;
  agg.dir_ok_rate = agg.sample_size ? _round4_(agg.dir_ok_count / agg.sample_size) : null;
  agg.strength_ok_rate = agg.sample_size ? _round4_(agg.strength_ok_count / agg.sample_size) : null;
  agg.sustain_ok_rate = agg.sample_size ? _round4_(agg.sustain_ok_count / agg.sample_size) : null;
  agg.avg_outcome_score = agg.sample_size ? _round4_(agg.score_sum / agg.sample_size) : null;
  return agg;
}

function _characterOutcomeBuildLinkRows_(generatedTs, traits, residualLookup, outcomeLookup, providerBaseline, warnings) {
  var byProviderTrait = {};
  var providers = {};
  Object.keys(residualLookup || {}).forEach(function(key) {
    var residual = residualLookup[key] || {};
    var outcome = outcomeLookup.by_key[key];
    if (!outcome) return;
    var provider = String(residual.provider || outcome.provider || '').trim();
    if (!provider) return;
    providers[provider] = true;
    for (var i = 0; i < (traits || []).length; i++) {
      var trait = traits[i];
      if (!_characterOutcomeTraitMatchesResidual_(trait, residual)) continue;
      var groupKey = provider + '|' + trait.trait;
      if (!byProviderTrait[groupKey]) {
        byProviderTrait[groupKey] = {
          generated_ts: generatedTs,
          provider: provider,
          trait: trait.trait,
          sample_size: 0,
          overall_ok_count: 0,
          dir_ok_count: 0,
          strength_ok_count: 0,
          sustain_ok_count: 0,
          score_sum: 0,
          trait_support_notes: [],
          trait_domains: _characterOutcomeTraitDomainList_(trait)
        };
      }
      _characterOutcomeAccumulateOutcome_(byProviderTrait[groupKey], outcome);
    }
  });

  var rows = [];
  Object.keys(byProviderTrait).sort().forEach(function(key) {
    var g = byProviderTrait[key];
    var baseline = providerBaseline[g.provider] || {
      sample_size: 0,
      overall_ok_rate: null,
      dir_ok_rate: null,
      strength_ok_rate: null,
      sustain_ok_rate: null,
      avg_outcome_score: null
    };
    var row = _characterOutcomeFinalizeTraitRow_(generatedTs, g, baseline);
    rows.push(row);
  });
  return rows;
}

function _characterOutcomeAccumulateOutcome_(group, outcome) {
  if (!group || !outcome) return;
  group.sample_size += 1;
  if (String(outcome.overall_ok || '').toUpperCase() === 'TRUE') group.overall_ok_count += 1;
  if (String(outcome.dir_ok || '').toUpperCase() === 'TRUE') group.dir_ok_count += 1;
  if (String(outcome.strength_ok || '').toUpperCase() === 'TRUE') group.strength_ok_count += 1;
  if (String(outcome.sustain_ok || '').toUpperCase() === 'TRUE') group.sustain_ok_count += 1;
  if (outcome.outcome_score !== null && outcome.outcome_score !== undefined && outcome.outcome_score !== '') {
    group.score_sum += Number(outcome.outcome_score || 0);
  }
}

function _characterOutcomeFinalizeTraitRow_(generatedTs, group, baseline) {
  var sampleSize = Number(group.sample_size || 0);
  var overall = sampleSize ? _round4_(group.overall_ok_count / sampleSize) : null;
  var dir = sampleSize ? _round4_(group.dir_ok_count / sampleSize) : null;
  var strength = sampleSize ? _round4_(group.strength_ok_count / sampleSize) : null;
  var sustain = sampleSize ? _round4_(group.sustain_ok_count / sampleSize) : null;
  var score = sampleSize ? _round4_(group.score_sum / sampleSize) : null;

  var overallDelta = _characterOutcomeDelta_(overall, baseline.overall_ok_rate);
  var dirDelta = _characterOutcomeDelta_(dir, baseline.dir_ok_rate);
  var strengthDelta = _characterOutcomeDelta_(strength, baseline.strength_ok_rate);
  var sustainDelta = _characterOutcomeDelta_(sustain, baseline.sustain_ok_rate);
  var scoreDelta = _characterOutcomeDelta_(score, baseline.avg_outcome_score);
  var classification = _characterOutcomeClassify_(scoreDelta, sampleSize);
  var confidence = _characterOutcomeConfidence_(sampleSize);
  var notes = [
    'source=Outcome_Ledger',
    'trait_source=Character_Recurrence_Validation',
    'score_normalized_to_0_1_from_ledger_outcome_score',
    'provider_baseline_rows=' + Number(baseline.sample_size || 0)
  ];
  if (sampleSize < 20) notes.push('thin_sample');
  if (sampleSize < 10) notes.push('excluded_from_ranking_calculations');
  if (group.trait_domains && group.trait_domains.length) notes.push('domains=' + group.trait_domains.join('|'));

  return {
    generated_ts: generatedTs,
    provider: group.provider,
    trait: group.trait,
    sample_size: sampleSize,
    overall_ok_rate: overall == null ? '' : overall,
    dir_ok_rate: dir == null ? '' : dir,
    strength_ok_rate: strength == null ? '' : strength,
    sustain_ok_rate: sustain == null ? '' : sustain,
    avg_outcome_score: score == null ? '' : score,
    baseline_overall_ok_rate: baseline.overall_ok_rate == null ? '' : baseline.overall_ok_rate,
    baseline_dir_ok_rate: baseline.dir_ok_rate == null ? '' : baseline.dir_ok_rate,
    baseline_strength_ok_rate: baseline.strength_ok_rate == null ? '' : baseline.strength_ok_rate,
    baseline_sustain_ok_rate: baseline.sustain_ok_rate == null ? '' : baseline.sustain_ok_rate,
    baseline_outcome_score: baseline.avg_outcome_score == null ? '' : baseline.avg_outcome_score,
    overall_delta: overallDelta == null ? '' : overallDelta,
    dir_delta: dirDelta == null ? '' : dirDelta,
    strength_delta: strengthDelta == null ? '' : strengthDelta,
    sustain_delta: sustainDelta == null ? '' : sustainDelta,
    score_delta: scoreDelta == null ? '' : scoreDelta,
    confidence: confidence,
    classification: classification,
    notes: notes.join('; ')
  };
}

function _characterOutcomeTraitMatchesResidual_(trait, residual) {
  if (!trait || !residual) return false;
  var name = String(trait.trait || '').trim();
  if (!name) return false;
  var domains = trait.domains || {};
  if (domains.risk_language && String(residual.risk_language || '').trim() === name) return true;
  if (domains.uncertainty_pattern && String(residual.uncertainty_pattern || '').trim() === name) return true;
  if (domains.direction_delta_from_baseline && String(residual.direction_delta_from_baseline || '').trim() === name) return true;
  if (domains.emphasized_factor && _characterResidualPipeSplit_(residual.emphasized_factors).indexOf(name) >= 0) return true;
  if (domains.rationale_style_tag && _characterResidualPipeSplit_(residual.rationale_style_tags).indexOf(name) >= 0) return true;
  return false;
}

function _characterOutcomeTraitDomainList_(trait) {
  var out = [];
  var domains = (trait && trait.domains) || {};
  Object.keys(domains).sort().forEach(function(domain) {
    if (domains[domain]) out.push(domain);
  });
  return out;
}

function _characterOutcomeDelta_(traitValue, baselineValue) {
  var a = _characterOutcomeNum_(traitValue);
  var b = _characterOutcomeNum_(baselineValue);
  if (a == null || b == null) return null;
  return _round4_(a - b);
}

function _characterOutcomeClassify_(scoreDelta, sampleSize) {
  var label = 'outcome_neutral';
  var delta = _characterOutcomeNum_(scoreDelta);
  if (delta != null) {
    if (delta >= 0.05) label = 'outcome_positive';
    else if (delta <= -0.05) label = 'outcome_negative';
  }
  if (Number(sampleSize || 0) < 20) label += '_thin_sample';
  return label;
}

function _characterOutcomeConfidence_(sampleSize) {
  var n = Number(sampleSize || 0);
  if (n < 10) return 'insufficient_sample';
  if (n < 20) return 'thin_sample';
  if (n >= 100) return 'deep_sample';
  return 'usable_sample';
}

function _characterOutcomeBuildSummaryRows_(generatedTs, linkRows) {
  var rows = [];
  for (var i = 0; i < (linkRows || []).length; i++) {
    var row = linkRows[i] || {};
    rows.push({
      generated_ts: generatedTs,
      provider: row.provider || '',
      trait: row.trait || '',
      sample_size: row.sample_size || 0,
      score_delta: row.score_delta === '' ? '' : row.score_delta,
      overall_delta: row.overall_delta === '' ? '' : row.overall_delta,
      dir_delta: row.dir_delta === '' ? '' : row.dir_delta,
      classification: row.classification || '',
      ranking_note: ''
    });
  }

  rows.sort(function(a, b) {
    var aEligible = Number(a.sample_size || 0) >= 10;
    var bEligible = Number(b.sample_size || 0) >= 10;
    if (aEligible !== bEligible) return aEligible ? -1 : 1;
    var order = _characterOutcomeRankingBucket_(a.classification) - _characterOutcomeRankingBucket_(b.classification);
    if (order !== 0) return order;
    var aScore = _characterOutcomeNum_(a.score_delta);
    var bScore = _characterOutcomeNum_(b.score_delta);
    if (a.classification.indexOf('positive') >= 0) {
      if (aScore !== bScore) return (bScore || 0) - (aScore || 0);
    } else if (a.classification.indexOf('negative') >= 0) {
      if (aScore !== bScore) return (aScore || 0) - (bScore || 0);
    } else {
      var aAbs = Math.abs(aScore || 0);
      var bAbs = Math.abs(bScore || 0);
      if (aAbs !== bAbs) return aAbs - bAbs;
    }
    if (Number(a.sample_size || 0) !== Number(b.sample_size || 0)) return Number(b.sample_size || 0) - Number(a.sample_size || 0);
    return (a.provider + '|' + a.trait).localeCompare(b.provider + '|' + b.trait);
  });

  var eligibleByBucket = {};
  for (var j = 0; j < rows.length; j++) {
    var r = rows[j];
    if (Number(r.sample_size || 0) < 10) continue;
    var bucket = _characterOutcomeRankingBucket_(r.classification);
    if (!eligibleByBucket[bucket]) eligibleByBucket[bucket] = 0;
    eligibleByBucket[bucket] += 1;
  }

  var seenByBucket = {};
  for (var k = 0; k < rows.length; k++) {
    var row = rows[k];
    var bucketKey = _characterOutcomeRankingBucket_(row.classification);
    if (Number(row.sample_size || 0) < 10) {
      row.ranking_note = 'excluded_from_ranking_sample_lt_10';
      continue;
    }
    if (!seenByBucket[bucketKey]) seenByBucket[bucketKey] = 0;
    seenByBucket[bucketKey] += 1;
    var total = eligibleByBucket[bucketKey] || 0;
    row.ranking_note = 'rank=' + seenByBucket[bucketKey] + '/' + total;
  }

  return rows;
}

function _characterOutcomeRankingBucket_(classification) {
  var c = String(classification || '').toLowerCase();
  if (c.indexOf('outcome_positive') === 0) return 0;
  if (c.indexOf('outcome_negative') === 0) return 1;
  if (c.indexOf('outcome_neutral') === 0) return 2;
  return 3;
}

function _characterOutcomeBuildFamilyRows_(generatedTs, traits, residualLookup, outcomeLookup, providerFamilyBaseline, warnings) {
  var byKey = {};
  Object.keys(residualLookup || {}).forEach(function(key) {
    var residual = residualLookup[key] || {};
    var outcome = outcomeLookup.by_key[key];
    if (!outcome) return;
    var provider = String(residual.provider || outcome.provider || '').trim();
    if (!provider) return;
    var family = String(outcome.outcome_family || residual.outcome_family || '').trim() || 'other';
    var familyBaseline = providerFamilyBaseline[provider + '|' + family] || {
      sample_size: 0,
      overall_ok_rate: null,
      dir_ok_rate: null,
      strength_ok_rate: null,
      sustain_ok_rate: null,
      avg_outcome_score: null
    };
    for (var i = 0; i < (traits || []).length; i++) {
      var trait = traits[i];
      if (!_characterOutcomeTraitMatchesResidual_(trait, residual)) continue;
      var groupKey = provider + '|' + trait.trait + '|' + family;
      if (!byKey[groupKey]) {
        byKey[groupKey] = {
          generated_ts: generatedTs,
          provider: provider,
          trait: trait.trait,
          outcome_family: family,
          sample_size: 0,
          overall_ok_count: 0,
          dir_ok_count: 0,
          strength_ok_count: 0,
          sustain_ok_count: 0,
          score_sum: 0,
          sample_depth_warning: ''
        };
      }
      _characterOutcomeAccumulateOutcome_(byKey[groupKey], outcome);
      byKey[groupKey].sample_depth_warning = (byKey[groupKey].sample_size < 20 || familyBaseline.sample_size < 20) ? 'thin_sample' : '';
    }
  });

  var rows = [];
  Object.keys(byKey).sort().forEach(function(key) {
    var g = byKey[key];
    var provider = g.provider;
    var family = g.outcome_family;
    var baseline = providerFamilyBaseline[provider + '|' + family] || {
      sample_size: 0,
      overall_ok_rate: null,
      dir_ok_rate: null,
      strength_ok_rate: null,
      sustain_ok_rate: null,
      avg_outcome_score: null
    };
    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      trait: g.trait,
      outcome_family: family,
      sample_size: g.sample_size,
      overall_ok_rate: g.sample_size ? _round4_(g.overall_ok_count / g.sample_size) : '',
      dir_ok_rate: g.sample_size ? _round4_(g.dir_ok_count / g.sample_size) : '',
      strength_ok_rate: g.sample_size ? _round4_(g.strength_ok_count / g.sample_size) : '',
      sustain_ok_rate: g.sample_size ? _round4_(g.sustain_ok_count / g.sample_size) : '',
      avg_outcome_score: g.sample_size ? _round4_(g.score_sum / g.sample_size) : '',
      baseline_overall_ok_rate: baseline.overall_ok_rate == null ? '' : baseline.overall_ok_rate,
      baseline_dir_ok_rate: baseline.dir_ok_rate == null ? '' : baseline.dir_ok_rate,
      baseline_strength_ok_rate: baseline.strength_ok_rate == null ? '' : baseline.strength_ok_rate,
      baseline_sustain_ok_rate: baseline.sustain_ok_rate == null ? '' : baseline.sustain_ok_rate,
      baseline_outcome_score: baseline.avg_outcome_score == null ? '' : baseline.avg_outcome_score,
      overall_delta: _characterOutcomeDelta_(g.sample_size ? _round4_(g.overall_ok_count / g.sample_size) : null, baseline.overall_ok_rate) || '',
      dir_delta: _characterOutcomeDelta_(g.sample_size ? _round4_(g.dir_ok_count / g.sample_size) : null, baseline.dir_ok_rate) || '',
      strength_delta: _characterOutcomeDelta_(g.sample_size ? _round4_(g.strength_ok_count / g.sample_size) : null, baseline.strength_ok_rate) || '',
      sustain_delta: _characterOutcomeDelta_(g.sample_size ? _round4_(g.sustain_ok_count / g.sample_size) : null, baseline.sustain_ok_rate) || '',
      score_delta: _characterOutcomeDelta_(g.sample_size ? _round4_(g.score_sum / g.sample_size) : null, baseline.avg_outcome_score) || '',
      confidence: _characterOutcomeConfidence_(g.sample_size),
      classification: _characterOutcomeClassify_(_characterOutcomeDelta_(g.sample_size ? _round4_(g.score_sum / g.sample_size) : null, baseline.avg_outcome_score), g.sample_size),
      sample_depth_warning: g.sample_depth_warning || '',
      notes: 'family_baseline_rows=' + Number(baseline.sample_size || 0) + '; source=Outcome_Ledger'
    });
  });
  return rows;
}

function _characterOutcomeRowsToNumeric_(rows) {
  return (rows || []).map(function(row) {
    return {
      provider: String(row.provider || '').trim(),
      trait: String(row.trait || '').trim(),
      sample_size: Number(row.sample_size || 0),
      score_delta: _characterOutcomeNum_(row.score_delta),
      overall_delta: _characterOutcomeNum_(row.overall_delta),
      dir_delta: _characterOutcomeNum_(row.dir_delta),
      classification: String(row.classification || '').trim(),
      row: row
    };
  });
}

function _characterOutcomeBundleRowsToObjects_(bundle) {
  var rows = (bundle && bundle.rows) || [];
  var headers = (bundle && bundle.headers) || [];
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || [];
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = row[j];
    }
    out.push(obj);
  }
  return out;
}
