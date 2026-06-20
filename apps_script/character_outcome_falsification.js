/*******************************************************
 * character_outcome_falsification.js
 * - Diagnostic-only Character -> Outcome falsification layer
 * - Attempts to break the Character_Outcome_Link result via controls and null tests
 *******************************************************/

function menuBuildCharacterOutcomeFalsification_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildCharacterOutcomeFalsification_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Character outcome falsification -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Provider=' + (res.provider_rows_written || 0) +
      ' | Family=' + (res.family_rows_written || 0) +
      ' | Perm=' + (res.permutation_rows_written || 0),
      'Character Outcome Falsification',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Character outcome falsification -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildCharacterOutcomeFalsification_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _characterFalsificationLoadSources_(warnings);
  var traitDefs = _characterFalsificationBuildTraitDefinitions_(sources, warnings);
  if (!traitDefs.length) {
    warnings.push('missing_traits:character_outcome_link_and_fallback');
  }

  var recurrenceMap = _characterFalsificationBuildRecurrenceMap_(sources.recurrenceBundle, warnings);
  var outcomeModel = _characterFalsificationBuildOutcomeModel_(sources.outcomeBundle, sources.residualBundle, traitDefs, warnings);

  var providerControlledRows = _characterFalsificationBuildProviderControlledRows_(generatedTs, traitDefs, outcomeModel, warnings);
  var familyControlledRows = _characterFalsificationBuildFamilyControlledRows_(generatedTs, traitDefs, outcomeModel, warnings);
  var permutationRows = _characterFalsificationBuildPermutationRows_(generatedTs, traitDefs, outcomeModel, providerControlledRows, warnings);
  var robustRows = _characterFalsificationBuildRobustRows_(generatedTs, providerControlledRows);
  var proxyRows = _characterFalsificationBuildProxyRows_(generatedTs, traitDefs, outcomeModel, warnings);
  var reportRows = _characterFalsificationBuildReportRows_(
    generatedTs,
    traitDefs,
    recurrenceMap,
    providerControlledRows,
    familyControlledRows,
    permutationRows,
    robustRows,
    proxyRows
  );

  var providerSheet = getDiagnosticsSheet_('Character_Outcome_Provider_Controlled', _characterFalsificationProviderHeaders_(), warnings);
  var familySheet = getDiagnosticsSheet_('Character_Outcome_Family_Controlled', _characterFalsificationFamilyHeaders_(), warnings);
  var permutationSheet = getDiagnosticsSheet_('Character_Outcome_Permutation_Test', _characterFalsificationPermutationHeaders_(), warnings);
  var robustSheet = getDiagnosticsSheet_('Character_Outcome_Robust_Traits', _characterFalsificationRobustHeaders_(), warnings);
  var proxySheet = getDiagnosticsSheet_('Character_Good_Reasoning_Proxy_Test', _characterFalsificationProxyHeaders_(), warnings);
  var reportSheet = getDiagnosticsSheet_('Character_Outcome_Falsification_Report', _characterFalsificationReportHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(providerSheet.sheet, providerSheet.headers, _characterResidualObjectsToRows_(providerControlledRows, providerSheet.headers));
  _rewriteSheetRowsPreservingHeaders_(familySheet.sheet, familySheet.headers, _characterResidualObjectsToRows_(familyControlledRows, familySheet.headers));
  _rewriteSheetRowsPreservingHeaders_(permutationSheet.sheet, permutationSheet.headers, _characterResidualObjectsToRows_(permutationRows, permutationSheet.headers));
  _rewriteSheetRowsPreservingHeaders_(robustSheet.sheet, robustSheet.headers, _characterResidualObjectsToRows_(robustRows, robustSheet.headers));
  _rewriteSheetRowsPreservingHeaders_(proxySheet.sheet, proxySheet.headers, _characterResidualObjectsToRows_(proxyRows, proxySheet.headers));
  _rewriteSheetRowsPreservingHeaders_(reportSheet.sheet, reportSheet.headers, _characterResidualObjectsToRows_(reportRows, reportSheet.headers));

  return {
    status: 'ok',
    generated_ts: generatedTs,
    provider_sheet: providerSheet.sheet.getName(),
    family_sheet: familySheet.sheet.getName(),
    permutation_sheet: permutationSheet.sheet.getName(),
    robust_sheet: robustSheet.sheet.getName(),
    proxy_sheet: proxySheet.sheet.getName(),
    report_sheet: reportSheet.sheet.getName(),
    provider_rows_written: providerControlledRows.length,
    family_rows_written: familyControlledRows.length,
    permutation_rows_written: permutationRows.length,
    robust_rows_written: robustRows.length,
    proxy_rows_written: proxyRows.length,
    report_rows_written: reportRows.length,
    trait_count: traitDefs.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function _characterFalsificationProviderHeaders_() {
  return [
    'generated_ts',
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
    'notes'
  ];
}

function _characterFalsificationFamilyHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'outcome_family',
    'sample_size',
    'present_sample_size',
    'absent_sample_size',
    'family_sample_size',
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

function _characterFalsificationPermutationHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'sample_size',
    'present_sample_size',
    'provider_sample_size',
    'observed_score_delta',
    'random_mean_delta',
    'random_std_delta',
    'z_score',
    'percentile_rank',
    'permutation_count',
    'permutation_result',
    'notes'
  ];
}

function _characterFalsificationRobustHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'sample_size',
    'present_sample_size',
    'absent_sample_size',
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
    'ranking_note',
    'notes'
  ];
}

function _characterFalsificationProxyHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'sample_size',
    'present_sample_size',
    'absent_sample_size',
    'provider_sample_size',
    'trait_present_avg_richness_score',
    'trait_absent_avg_richness_score',
    'richness_delta',
    'provider_richness_high_low_score_delta',
    'trait_present_avg_outcome_score',
    'trait_absent_avg_outcome_score',
    'score_delta',
    'trait_present_rationale_words',
    'trait_absent_rationale_words',
    'rationale_words_delta',
    'trait_present_factor_count',
    'trait_absent_factor_count',
    'factor_count_delta',
    'trait_present_context_reference_count',
    'trait_absent_context_reference_count',
    'context_reference_delta',
    'trait_present_attention_factor_count',
    'trait_absent_attention_factor_count',
    'attention_factor_count_delta',
    'proxy_test_result',
    'notes'
  ];
}

function _characterFalsificationReportHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'recurrence_score',
    'provider_controlled_result',
    'family_controlled_result',
    'permutation_result',
    'robust_sample_result',
    'proxy_test_result',
    'falsification_status',
    'confidence_level'
  ];
}

function _characterFalsificationLoadSources_(warnings) {
  return {
    traitBundle: _characterResidualReadSheetBundle_('Character_Outcome_Link', warnings, false) || _characterResidualReadSheetBundle_('Character_Recurrence_Validation', warnings, false),
    recurrenceBundle: _characterResidualReadSheetBundle_('Character_Recurrence_Validation', warnings, false),
    residualBundle: _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false),
    outcomeBundle: _characterFalsificationReadOutcomeBundle_(warnings)
  };
}

function _characterFalsificationReadOutcomeBundle_(warnings) {
  var bundle = _characterResidualReadSheetBundle_('Outcome_Ledger', warnings, true);
  if (bundle) return bundle;

  var fallback = _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false);
  if (!fallback) return null;

  var rows = _characterFalsificationBundleRowsToObjects_(fallback);
  var caseRows = [];
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i].row_type || '').trim().toLowerCase() === 'case') caseRows.push(rows[i]);
  }
  if (!caseRows.length) return null;
  fallback.rows = _characterResidualObjectsToRows_(caseRows, fallback.headers);
  return fallback;
}

function _characterFalsificationBuildTraitDefinitions_(sources, warnings) {
  var seen = {};
  var traits = [];
  var traitRows = _characterFalsificationBundleRowsToObjects_(sources.traitBundle);
  for (var i = 0; i < traitRows.length; i++) {
    var row = traitRows[i] || {};
    var provider = String(row.provider || '').trim();
    var trait = String(row.trait || '').trim();
    if (!provider || !trait) continue;
    var key = provider + '|' + trait;
    if (seen[key]) continue;
    seen[key] = true;
    traits.push({
      provider: provider,
      trait: trait,
      observed_sample_size: _characterFalsificationNum_(row.sample_size),
      observed_score_delta: _characterFalsificationNum_(row.score_delta),
      observed_classification: String(row.classification || '').trim(),
      observed_ranking_note: String(row.ranking_note || '').trim()
    });
  }

  if (traits.length) return traits;

  var recurrenceRows = _characterFalsificationBundleRowsToObjects_(sources.recurrenceBundle);
  for (var j = 0; j < recurrenceRows.length; j++) {
    var rec = recurrenceRows[j] || {};
    var providerName = String(rec.provider || '').trim();
    if (!providerName) continue;
    var terms = [];
    terms = terms.concat(_characterFalsificationParseCountMap_(rec.sample_a_risk_distribution));
    terms = terms.concat(_characterFalsificationParseCountMap_(rec.sample_a_uncertainty_distribution));
    terms = terms.concat(_characterFalsificationParseCountMap_(rec.sample_a_top_emphasized_factors));
    terms = terms.concat(_characterFalsificationParseCountMap_(rec.sample_a_direction_distribution));
    for (var t = 0; t < terms.length; t++) {
      var traitName = terms[t];
      var fallbackKey = providerName + '|' + traitName;
      if (seen[fallbackKey]) continue;
      seen[fallbackKey] = true;
      traits.push({
        provider: providerName,
        trait: traitName,
        observed_sample_size: '',
        observed_score_delta: '',
        observed_classification: '',
        observed_ranking_note: ''
      });
    }
  }

  if (!traits.length) warnings.push('trait_universe_missing');
  return traits;
}

function _characterFalsificationBuildRecurrenceMap_(bundle, warnings) {
  var rows = _characterFalsificationBundleRowsToObjects_(bundle);
  var out = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    var score = _characterFalsificationNum_(row.recurrence_score);
    if (score == null && _characterFalsificationNum_(row.recurrence_score) !== 0) continue;
    out[provider] = {
      recurrence_score: score == null ? '' : _round4_(score),
      recurrence_classification: String(row.recurrence_classification || '').trim(),
      sample_a_rows: String(row.sample_a_rows || '').trim(),
      sample_b_rows: String(row.sample_b_rows || '').trim()
    };
  }
  return out;
}

function _characterFalsificationBuildOutcomeModel_(outcomeBundle, residualBundle, traitDefs, warnings) {
  var outcomeRows = _characterFalsificationBundleRowsToObjects_(outcomeBundle);
  var residualRows = _characterFalsificationBundleRowsToObjects_(residualBundle);
  var residualLookup = _characterFalsificationBuildResidualLookup_(residualRows);
  var traitsByProvider = _characterFalsificationTraitsByProvider_(traitDefs);

  var out = {
    by_provider: {},
    by_provider_family: {},
    provider_sample_sizes: {},
    provider_richness_summary: {}
  };

  for (var i = 0; i < outcomeRows.length; i++) {
    var row = outcomeRows[i] || {};
    if (!_characterFalsificationIsScoredOutcomeRow_(row)) continue;
    var provider = String(row.ai_name || row.provider || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var family = String(row.outcome_family || '').trim() || 'other';
    var key = eventId + '|' + provider;
    var residual = residualLookup[key] || null;
    var joined = _characterFalsificationJoinOutcomeRow_(row, residual);
    var matchedTraits = _characterFalsificationMatchTraitsForProvider_(traitsByProvider[provider] || [], residual);
    joined.matched_traits = matchedTraits;
    joined.matched_traits_text = matchedTraits.join('|');

    if (!out.by_provider[provider]) out.by_provider[provider] = [];
    out.by_provider[provider].push(joined);
    var pfKey = provider + '|' + family;
    if (!out.by_provider_family[pfKey]) out.by_provider_family[pfKey] = [];
    out.by_provider_family[pfKey].push(joined);
  }

  Object.keys(out.by_provider).forEach(function(provider) {
    out.provider_sample_sizes[provider] = out.by_provider[provider].length;
    out.provider_richness_summary[provider] = _characterFalsificationBuildProviderRichnessSummary_(out.by_provider[provider]);
  });

  return out;
}

function _characterFalsificationJoinOutcomeRow_(row, residual) {
  var rationaleShort = residual ? String(residual.rationale_short || '').trim() : '';
  var rationalePreview = residual ? String(residual.rationale_preview || '').trim() : '';
  var emphasizedFactors = residual ? _characterResidualPipeSplit_(residual.emphasized_factors) : [];
  var ignoredFactors = residual ? _characterResidualPipeSplit_(residual.ignored_factors) : [];
  var riskLanguage = residual ? String(residual.risk_language || '').trim() : '';
  var uncertaintyPattern = residual ? String(residual.uncertainty_pattern || '').trim() : '';
  var rationaleStyleTags = residual ? _characterResidualPipeSplit_(residual.rationale_style_tags) : [];
  var rationaleText = [rationaleShort, rationalePreview].join(' ').trim();
  var rationaleWords = _characterFalsificationCountWords_(rationaleText);
  var factorCount = emphasizedFactors.length + rationaleStyleTags.length;
  var attentionFactorCount = emphasizedFactors.length;
  var contextReferenceCount = _characterFalsificationCountContextReferences_(rationaleText);
  var richnessScore = _round4_(rationaleWords + (factorCount * 2) + contextReferenceCount + attentionFactorCount);
  var outcomeScore = _characterFalsificationNormalizedOutcomeScore_(row);
  return {
    generated_ts: String(row.generated_ts || '').trim(),
    event_id: String(row.event_id || '').trim(),
    batch_id: String(row.batch_id || '').trim(),
    type: String(row.type || '').trim(),
    indicator_name: String(row.indicator_name || '').trim(),
    country: String(row.country || '').trim(),
    release_ts: String(row.release_ts || '').trim(),
    outcome_family: String(row.outcome_family || '').trim() || 'other',
    provider: String(row.ai_name || row.provider || '').trim(),
    overall_ok: _characterFalsificationTruth_(row.overall_ok),
    dir_ok: _characterFalsificationTruth_(row.mr_dir_ok || row.dir_ok),
    strength_ok: _characterFalsificationTruth_(row.mr_strength_ok),
    sustain_ok: _characterFalsificationTruth_(row.mr_sustain_ok),
    outcome_score: outcomeScore,
    residual_exists: residual ? 'TRUE' : 'FALSE',
    rationale_short: rationaleShort,
    rationale_preview: rationalePreview,
    emphasized_factors: emphasizedFactors.join('|'),
    ignored_factors: ignoredFactors.join('|'),
    risk_language: riskLanguage,
    uncertainty_pattern: uncertaintyPattern,
    rationale_style_tags: rationaleStyleTags.join('|'),
    rationale_words: rationaleWords,
    factor_count: factorCount,
    attention_factor_count: attentionFactorCount,
    context_reference_count: contextReferenceCount,
    richness_score: richnessScore,
    raw_character_vector_json: residual && residual.raw_character_vector_json ? String(residual.raw_character_vector_json) : ''
  };
}

function _characterFalsificationBuildResidualLookup_(rows) {
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
    if (_characterFalsificationResidualRowIsNewer_(row, out[key])) out[key] = row;
  }
  return out;
}

function _characterFalsificationResidualRowIsNewer_(candidate, existing) {
  var candidateTs = _characterResidualDateMs_(candidate.generated_ts || candidate.release_ts || candidate.created_ts);
  var existingTs = _characterResidualDateMs_(existing.generated_ts || existing.release_ts || existing.created_ts);
  if (candidateTs !== existingTs) return candidateTs > existingTs;
  return true;
}

function _characterFalsificationTraitsByProvider_(traitDefs) {
  var out = {};
  for (var i = 0; i < (traitDefs || []).length; i++) {
    var row = traitDefs[i] || {};
    var provider = String(row.provider || '').trim();
    var trait = String(row.trait || '').trim();
    if (!provider || !trait) continue;
    if (!out[provider]) out[provider] = [];
    out[provider].push(trait);
  }
  return out;
}

function _characterFalsificationMatchTraitsForProvider_(traits, residual) {
  var matched = [];
  if (!residual) return matched;
  for (var i = 0; i < (traits || []).length; i++) {
    var trait = String(traits[i] || '').trim();
    if (!trait) continue;
    if (_characterFalsificationTraitMatchesResidual_(trait, residual)) matched.push(trait);
  }
  return _uniqueStrings_(matched);
}

function _characterFalsificationTraitMatchesResidual_(trait, residual) {
  var name = String(trait || '').trim();
  if (!name || !residual) return false;
  if (String(residual.risk_language || '').trim() === name) return true;
  if (String(residual.uncertainty_pattern || '').trim() === name) return true;
  if (String(residual.direction_delta_from_baseline || '').trim() === name) return true;
  if (_characterResidualPipeSplit_(residual.emphasized_factors).indexOf(name) >= 0) return true;
  if (_characterResidualPipeSplit_(residual.rationale_style_tags).indexOf(name) >= 0) return true;
  return false;
}

function _characterFalsificationIsScoredOutcomeRow_(row) {
  return _characterFalsificationTruth_(row.scored_flag) || _characterFalsificationNormalizedOutcomeScore_(row) !== null;
}

function _characterFalsificationTruth_(value) {
  return _isTrueCell_(value) ? 'TRUE' : 'FALSE';
}

function _characterFalsificationNormalizedOutcomeScore_(row) {
  if (!row) return null;
  var raw = _characterFalsificationNum_(row.outcome_score);
  if (raw == null && typeof computeOutcomeScore_ === 'function') {
    var computed = computeOutcomeScore_({
      scored_flag: _isTrueCell_(row.scored_flag) ? 'TRUE' : 'FALSE',
      mr_dir_ok: _isTrueCell_(row.mr_dir_ok || row.dir_ok) ? 'TRUE' : 'FALSE',
      mr_strength_ok: _isTrueCell_(row.mr_strength_ok) ? 'TRUE' : 'FALSE',
      mr_sustain_ok: _isTrueCell_(row.mr_sustain_ok) ? 'TRUE' : 'FALSE',
      overall_ok: _isTrueCell_(row.overall_ok) ? 'TRUE' : 'FALSE'
    });
    raw = _characterFalsificationNum_(computed);
  }
  if (raw == null) return null;
  return raw > 1 ? _round4_(raw / 6) : _round4_(raw);
}

function _characterFalsificationNum_(value) {
  var s = String(value == null ? '' : value).trim();
  if (!s) return null;
  var n = Number(s);
  return isFinite(n) ? n : null;
}

function _characterFalsificationBuildProviderControlledRows_(generatedTs, traitDefs, outcomeModel, warnings) {
  var rows = [];
  var traitsByProvider = _characterFalsificationTraitsByProvider_(traitDefs);
  Object.keys(outcomeModel.by_provider || {}).sort().forEach(function(provider) {
    var providerRows = outcomeModel.by_provider[provider] || [];
    var providerTraits = traitsByProvider[provider] || [];
    for (var i = 0; i < providerTraits.length; i++) {
      var trait = providerTraits[i];
      var presentRows = _characterFalsificationRowsMatchingTrait_(providerRows, trait, true);
      var absentRows = _characterFalsificationRowsMatchingTrait_(providerRows, trait, false);
      rows.push(_characterFalsificationFinalizeControlRow_(generatedTs, provider, trait, presentRows, absentRows, providerRows.length));
    }
  });
  return rows;
}

function _characterFalsificationBuildFamilyControlledRows_(generatedTs, traitDefs, outcomeModel, warnings) {
  var rows = [];
  var traitsByProvider = _characterFalsificationTraitsByProvider_(traitDefs);
  Object.keys(outcomeModel.by_provider_family || {}).sort().forEach(function(key) {
    var provider = String(key.split('|')[0] || '').trim();
    var family = String(key.split('|').slice(1).join('|') || '').trim() || 'other';
    var familyRows = outcomeModel.by_provider_family[key] || [];
    var providerTraits = traitsByProvider[provider] || [];
    for (var i = 0; i < providerTraits.length; i++) {
      var trait = providerTraits[i];
      var presentRows = _characterFalsificationRowsMatchingTrait_(familyRows, trait, true);
      var absentRows = _characterFalsificationRowsMatchingTrait_(familyRows, trait, false);
      rows.push(_characterFalsificationFinalizeFamilyRow_(generatedTs, provider, trait, family, presentRows, absentRows, familyRows.length));
    }
  });
  return rows;
}

function _characterFalsificationRowsMatchingTrait_(rows, trait, present) {
  var out = [];
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var has = (row.matched_traits || []).indexOf(trait) >= 0;
    if ((present && has) || (!present && !has)) out.push(row);
  }
  return out;
}

function _characterFalsificationFinalizeControlRow_(generatedTs, provider, trait, presentRows, absentRows, providerSampleSize) {
  var presentAgg = _characterFalsificationAggregateRows_(presentRows);
  var absentAgg = _characterFalsificationAggregateRows_(absentRows);
  var sampleSize = Math.min(presentAgg.sample_size, absentAgg.sample_size);
  var overallDelta = _characterFalsificationDelta_(presentAgg.overall_ok_rate, absentAgg.overall_ok_rate);
  var dirDelta = _characterFalsificationDelta_(presentAgg.dir_ok_rate, absentAgg.dir_ok_rate);
  var strengthDelta = _characterFalsificationDelta_(presentAgg.strength_ok_rate, absentAgg.strength_ok_rate);
  var sustainDelta = _characterFalsificationDelta_(presentAgg.sustain_ok_rate, absentAgg.sustain_ok_rate);
  var scoreDelta = _characterFalsificationDelta_(presentAgg.avg_outcome_score, absentAgg.avg_outcome_score);
  var classification = _characterFalsificationClassifyScoreDelta_(scoreDelta, sampleSize);
  var confidence = _characterFalsificationConfidence_(sampleSize, providerSampleSize);
  var notes = [
    'present_rows=' + presentAgg.sample_size,
    'absent_rows=' + absentAgg.sample_size,
    'provider_rows=' + providerSampleSize,
    'source=Outcome_Ledger',
    'trait_source=Character_Outcome_Link'
  ];
  if (sampleSize < 20) notes.push('thin_sample');
  if (presentRows.length < 1) notes.push('no_trait_present_rows');
  return {
    generated_ts: generatedTs,
    provider: provider,
    trait: trait,
    sample_size: sampleSize,
    present_sample_size: presentAgg.sample_size,
    absent_sample_size: absentAgg.sample_size,
    provider_sample_size: providerSampleSize,
    present_overall_ok_rate: presentAgg.overall_ok_rate == null ? '' : presentAgg.overall_ok_rate,
    absent_overall_ok_rate: absentAgg.overall_ok_rate == null ? '' : absentAgg.overall_ok_rate,
    present_dir_ok_rate: presentAgg.dir_ok_rate == null ? '' : presentAgg.dir_ok_rate,
    absent_dir_ok_rate: absentAgg.dir_ok_rate == null ? '' : absentAgg.dir_ok_rate,
    present_strength_ok_rate: presentAgg.strength_ok_rate == null ? '' : presentAgg.strength_ok_rate,
    absent_strength_ok_rate: absentAgg.strength_ok_rate == null ? '' : absentAgg.strength_ok_rate,
    present_sustain_ok_rate: presentAgg.sustain_ok_rate == null ? '' : presentAgg.sustain_ok_rate,
    absent_sustain_ok_rate: absentAgg.sustain_ok_rate == null ? '' : absentAgg.sustain_ok_rate,
    present_avg_outcome_score: presentAgg.avg_outcome_score == null ? '' : presentAgg.avg_outcome_score,
    absent_avg_outcome_score: absentAgg.avg_outcome_score == null ? '' : absentAgg.avg_outcome_score,
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

function _characterFalsificationFinalizeFamilyRow_(generatedTs, provider, trait, family, presentRows, absentRows, familySampleSize) {
  var presentAgg = _characterFalsificationAggregateRows_(presentRows);
  var absentAgg = _characterFalsificationAggregateRows_(absentRows);
  var sampleSize = Math.min(presentAgg.sample_size, absentAgg.sample_size);
  var overallDelta = _characterFalsificationDelta_(presentAgg.overall_ok_rate, absentAgg.overall_ok_rate);
  var dirDelta = _characterFalsificationDelta_(presentAgg.dir_ok_rate, absentAgg.dir_ok_rate);
  var strengthDelta = _characterFalsificationDelta_(presentAgg.strength_ok_rate, absentAgg.strength_ok_rate);
  var sustainDelta = _characterFalsificationDelta_(presentAgg.sustain_ok_rate, absentAgg.sustain_ok_rate);
  var scoreDelta = _characterFalsificationDelta_(presentAgg.avg_outcome_score, absentAgg.avg_outcome_score);
  var classification = _characterFalsificationClassifyScoreDelta_(scoreDelta, sampleSize);
  var confidence = _characterFalsificationConfidence_(sampleSize, familySampleSize);
  var sampleDepthWarning = sampleSize < 20 ? 'thin_sample' : '';
  var notes = [
    'present_rows=' + presentAgg.sample_size,
    'absent_rows=' + absentAgg.sample_size,
    'family_rows=' + familySampleSize,
    'source=Outcome_Ledger',
    'family_scope=' + family
  ];
  if (sampleSize < 20) notes.push('thin_sample');
  return {
    generated_ts: generatedTs,
    provider: provider,
    trait: trait,
    outcome_family: family,
    sample_size: sampleSize,
    present_sample_size: presentAgg.sample_size,
    absent_sample_size: absentAgg.sample_size,
    family_sample_size: familySampleSize,
    present_overall_ok_rate: presentAgg.overall_ok_rate == null ? '' : presentAgg.overall_ok_rate,
    absent_overall_ok_rate: absentAgg.overall_ok_rate == null ? '' : absentAgg.overall_ok_rate,
    present_dir_ok_rate: presentAgg.dir_ok_rate == null ? '' : presentAgg.dir_ok_rate,
    absent_dir_ok_rate: absentAgg.dir_ok_rate == null ? '' : absentAgg.dir_ok_rate,
    present_strength_ok_rate: presentAgg.strength_ok_rate == null ? '' : presentAgg.strength_ok_rate,
    absent_strength_ok_rate: absentAgg.strength_ok_rate == null ? '' : absentAgg.strength_ok_rate,
    present_sustain_ok_rate: presentAgg.sustain_ok_rate == null ? '' : presentAgg.sustain_ok_rate,
    absent_sustain_ok_rate: absentAgg.sustain_ok_rate == null ? '' : absentAgg.sustain_ok_rate,
    present_avg_outcome_score: presentAgg.avg_outcome_score == null ? '' : presentAgg.avg_outcome_score,
    absent_avg_outcome_score: absentAgg.avg_outcome_score == null ? '' : absentAgg.avg_outcome_score,
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

function _characterFalsificationAggregateRows_(rows) {
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
    var score = _characterFalsificationNormalizedOutcomeScore_(row);
    if (score == null) continue;
    agg.sample_size += 1;
    if (String(row.overall_ok || '').toUpperCase() === 'TRUE') agg.overall_ok_count += 1;
    if (String(row.dir_ok || '').toUpperCase() === 'TRUE') agg.dir_ok_count += 1;
    if (String(row.strength_ok || '').toUpperCase() === 'TRUE') agg.strength_ok_count += 1;
    if (String(row.sustain_ok || '').toUpperCase() === 'TRUE') agg.sustain_ok_count += 1;
    agg.score_sum += score;
  }
  agg.overall_ok_rate = agg.sample_size ? _round4_(agg.overall_ok_count / agg.sample_size) : null;
  agg.dir_ok_rate = agg.sample_size ? _round4_(agg.dir_ok_count / agg.sample_size) : null;
  agg.strength_ok_rate = agg.sample_size ? _round4_(agg.strength_ok_count / agg.sample_size) : null;
  agg.sustain_ok_rate = agg.sample_size ? _round4_(agg.sustain_ok_count / agg.sample_size) : null;
  agg.avg_outcome_score = agg.sample_size ? _round4_(agg.score_sum / agg.sample_size) : null;
  return agg;
}

function _characterFalsificationBuildPermutationRows_(generatedTs, traitDefs, outcomeModel, providerControlledRows, warnings) {
  var rows = [];
  var traitsByProvider = _characterFalsificationTraitsByProvider_(traitDefs);
  var controlMap = _characterFalsificationIndexRows_(providerControlledRows, ['provider', 'trait'], false);
  Object.keys(outcomeModel.by_provider || {}).sort().forEach(function(provider) {
    var providerRows = outcomeModel.by_provider[provider] || [];
    var providerTraits = traitsByProvider[provider] || [];
    var scores = [];
    for (var i = 0; i < providerRows.length; i++) {
      var score = _characterFalsificationNormalizedOutcomeScore_(providerRows[i]);
      if (score != null) scores.push(score);
    }
    for (var t = 0; t < providerTraits.length; t++) {
      var trait = providerTraits[t];
      var presentRows = _characterFalsificationRowsMatchingTrait_(providerRows, trait, true);
      var presentCount = presentRows.length;
      var absentCount = Math.max(0, providerRows.length - presentCount);
      var controlSampleSize = Math.min(presentCount, absentCount);
      var controlKey = provider + '|' + trait;
      var controlRow = controlMap[controlKey] || null;
      var observedScoreDelta = controlRow ? _characterFalsificationNum_(controlRow.score_delta) : null;
      if (!providerRows.length || controlSampleSize < 1) {
        rows.push({
          generated_ts: generatedTs,
          provider: provider,
          trait: trait,
          sample_size: controlSampleSize,
          present_sample_size: presentCount,
          provider_sample_size: providerRows.length,
          observed_score_delta: '',
          random_mean_delta: '',
          random_std_delta: '',
          z_score: '',
          percentile_rank: '',
          permutation_count: 100,
          permutation_result: 'inconclusive_thin_sample',
          notes: 'insufficient_rows'
        });
        continue;
      }
      var perm = _characterFalsificationPermutationStats_(provider, trait, scores, presentCount, observedScoreDelta, 100);
      rows.push({
        generated_ts: generatedTs,
        provider: provider,
        trait: trait,
        sample_size: controlSampleSize,
        present_sample_size: presentCount,
        provider_sample_size: providerRows.length,
        observed_score_delta: _characterFalsificationClassifyNumber_(perm.observed_delta),
        random_mean_delta: _characterFalsificationClassifyNumber_(perm.random_mean_delta),
        random_std_delta: _characterFalsificationClassifyNumber_(perm.random_std_delta),
        z_score: _characterFalsificationClassifyNumber_(perm.z_score),
        percentile_rank: _characterFalsificationClassifyNumber_(perm.percentile_rank),
        permutation_count: 100,
        permutation_result: _characterFalsificationPermutationClassify_(perm, controlSampleSize, providerRows.length),
        notes: 'observed_present_rows=' + presentCount
      });
    }
  });
  return rows;
}

function _characterFalsificationPermutationStats_(provider, trait, scores, presentCount, observedDelta, permutationCount) {
  var total = 0;
  for (var i = 0; i < scores.length; i++) total += scores[i];
  var n = scores.length;
  var sampleCount = Math.max(0, Math.min(presentCount, n));
  var seedBase = _characterFalsificationSeed_(provider + '|' + trait);
  var randomValues = [];
  for (var p = 0; p < permutationCount; p++) {
    var rng = _characterFalsificationMulberry32_(seedBase + p * 1013);
    var idx = _characterFalsificationSampleIndexSet_(n, sampleCount, rng);
    var sumA = 0;
    for (var a = 0; a < idx.length; a++) sumA += scores[idx[a]];
    var sumB = total - sumA;
    var delta = _characterFalsificationRound4_((sumA / sampleCount) - (sumB / Math.max(1, n - sampleCount)));
    randomValues.push(delta);
  }
  var mean = _characterFalsificationMean_(randomValues);
  var std = _characterFalsificationStd_(randomValues, mean);
  var obs = _characterFalsificationNum_(observedDelta);
  if (obs == null) obs = mean;
  var z = std > 0 ? _characterFalsificationRound4_((obs - mean) / std) : 0;
  var percentile = _characterFalsificationPercentile_(randomValues, obs);
  return {
    observed_delta: obs,
    random_mean_delta: mean,
    random_std_delta: std,
    z_score: z,
    percentile_rank: percentile
  };
}

function _characterFalsificationPermutationClassify_(perm, controlSampleSize, providerSampleSize) {
  if (controlSampleSize < 20 || providerSampleSize < 20) return 'inconclusive_thin_sample';
  var z = _characterFalsificationNum_(perm.z_score);
  var pct = _characterFalsificationNum_(perm.percentile_rank);
  if (z == null || pct == null) return 'inconclusive';
  if (Math.abs(z) >= 1.96 && (pct <= 0.025 || pct >= 0.975)) return 'survived_null';
  if (Math.abs(z) >= 1.0 && (pct <= 0.10 || pct >= 0.90)) return 'partially_survived_null';
  return 'null_like';
}

function _characterFalsificationBuildRobustRows_(generatedTs, providerControlledRows) {
  var eligible = [];
  for (var i = 0; i < (providerControlledRows || []).length; i++) {
    var row = providerControlledRows[i] || {};
    if (Number(row.present_sample_size || 0) < 20) continue;
    eligible.push({
      generated_ts: generatedTs,
      provider: row.provider || '',
      trait: row.trait || '',
      sample_size: Number(row.present_sample_size || 0),
      present_sample_size: row.present_sample_size || 0,
      absent_sample_size: row.absent_sample_size || 0,
      present_overall_ok_rate: row.present_overall_ok_rate === '' ? '' : row.present_overall_ok_rate,
      absent_overall_ok_rate: row.absent_overall_ok_rate === '' ? '' : row.absent_overall_ok_rate,
      present_dir_ok_rate: row.present_dir_ok_rate === '' ? '' : row.present_dir_ok_rate,
      absent_dir_ok_rate: row.absent_dir_ok_rate === '' ? '' : row.absent_dir_ok_rate,
      present_strength_ok_rate: row.present_strength_ok_rate === '' ? '' : row.present_strength_ok_rate,
      absent_strength_ok_rate: row.absent_strength_ok_rate === '' ? '' : row.absent_strength_ok_rate,
      present_sustain_ok_rate: row.present_sustain_ok_rate === '' ? '' : row.present_sustain_ok_rate,
      absent_sustain_ok_rate: row.absent_sustain_ok_rate === '' ? '' : row.absent_sustain_ok_rate,
      present_avg_outcome_score: row.present_avg_outcome_score === '' ? '' : row.present_avg_outcome_score,
      absent_avg_outcome_score: row.absent_avg_outcome_score === '' ? '' : row.absent_avg_outcome_score,
      overall_delta: row.overall_delta === '' ? '' : row.overall_delta,
      dir_delta: row.dir_delta === '' ? '' : row.dir_delta,
      strength_delta: row.strength_delta === '' ? '' : row.strength_delta,
      sustain_delta: row.sustain_delta === '' ? '' : row.sustain_delta,
      score_delta: row.score_delta === '' ? '' : row.score_delta,
      confidence: row.confidence || '',
      classification: row.classification || '',
      ranking_note: '',
      notes: 'rare_trait_penalty_applied'
    });
  }

  eligible.sort(function(a, b) {
    var aBucket = _characterFalsificationRankBucket_(a.classification);
    var bBucket = _characterFalsificationRankBucket_(b.classification);
    if (aBucket !== bBucket) return aBucket - bBucket;
    var aScore = _characterFalsificationNum_(a.score_delta);
    var bScore = _characterFalsificationNum_(b.score_delta);
    if (aBucket === 0) return (bScore || 0) - (aScore || 0);
    if (aBucket === 1) return (aScore || 0) - (bScore || 0);
    var aAbs = Math.abs(aScore || 0);
    var bAbs = Math.abs(bScore || 0);
    if (aAbs !== bAbs) return aAbs - bAbs;
    return (a.provider + '|' + a.trait).localeCompare(b.provider + '|' + b.trait);
  });

  for (var j = 0; j < eligible.length; j++) {
    eligible[j].ranking_note = 'rank=' + (j + 1) + '/' + eligible.length;
  }
  return eligible;
}

function _characterFalsificationBuildProxyRows_(generatedTs, traitDefs, outcomeModel, warnings) {
  var rows = [];
  var traitsByProvider = _characterFalsificationTraitsByProvider_(traitDefs);
  Object.keys(outcomeModel.by_provider || {}).sort().forEach(function(provider) {
    var providerRows = outcomeModel.by_provider[provider] || [];
    var providerRich = outcomeModel.provider_richness_summary[provider] || _characterFalsificationBuildProviderRichnessSummary_(providerRows);
    var providerTraits = traitsByProvider[provider] || [];
    for (var i = 0; i < providerTraits.length; i++) {
      var trait = providerTraits[i];
      var presentRows = _characterFalsificationRowsMatchingTrait_(providerRows, trait, true);
      var absentRows = _characterFalsificationRowsMatchingTrait_(providerRows, trait, false);
      var presentAgg = _characterFalsificationAggregateRichnessRows_(presentRows);
      var absentAgg = _characterFalsificationAggregateRichnessRows_(absentRows);
      var richnessDelta = _characterFalsificationDelta_(presentAgg.avg_richness_score, absentAgg.avg_richness_score);
      var scoreDelta = _characterFalsificationDelta_(presentAgg.avg_outcome_score, absentAgg.avg_outcome_score);
      rows.push({
        generated_ts: generatedTs,
        provider: provider,
        trait: trait,
        sample_size: Math.min(presentAgg.sample_size, absentAgg.sample_size),
        present_sample_size: presentAgg.sample_size,
        absent_sample_size: absentAgg.sample_size,
        provider_sample_size: providerRows.length,
        trait_present_avg_richness_score: presentAgg.avg_richness_score == null ? '' : presentAgg.avg_richness_score,
        trait_absent_avg_richness_score: absentAgg.avg_richness_score == null ? '' : absentAgg.avg_richness_score,
        richness_delta: richnessDelta == null ? '' : richnessDelta,
        provider_richness_high_low_score_delta: providerRich.high_low_score_delta == null ? '' : providerRich.high_low_score_delta,
        trait_present_avg_outcome_score: presentAgg.avg_outcome_score == null ? '' : presentAgg.avg_outcome_score,
        trait_absent_avg_outcome_score: absentAgg.avg_outcome_score == null ? '' : absentAgg.avg_outcome_score,
        score_delta: scoreDelta == null ? '' : scoreDelta,
        trait_present_rationale_words: presentAgg.avg_rationale_words == null ? '' : presentAgg.avg_rationale_words,
        trait_absent_rationale_words: absentAgg.avg_rationale_words == null ? '' : absentAgg.avg_rationale_words,
        rationale_words_delta: _characterFalsificationDelta_(presentAgg.avg_rationale_words, absentAgg.avg_rationale_words) || '',
        trait_present_factor_count: presentAgg.avg_factor_count == null ? '' : presentAgg.avg_factor_count,
        trait_absent_factor_count: absentAgg.avg_factor_count == null ? '' : absentAgg.avg_factor_count,
        factor_count_delta: _characterFalsificationDelta_(presentAgg.avg_factor_count, absentAgg.avg_factor_count) || '',
        trait_present_context_reference_count: presentAgg.avg_context_reference_count == null ? '' : presentAgg.avg_context_reference_count,
        trait_absent_context_reference_count: absentAgg.avg_context_reference_count == null ? '' : absentAgg.avg_context_reference_count,
        context_reference_delta: _characterFalsificationDelta_(presentAgg.avg_context_reference_count, absentAgg.avg_context_reference_count) || '',
        trait_present_attention_factor_count: presentAgg.avg_attention_factor_count == null ? '' : presentAgg.avg_attention_factor_count,
        trait_absent_attention_factor_count: absentAgg.avg_attention_factor_count == null ? '' : absentAgg.avg_attention_factor_count,
        attention_factor_count_delta: _characterFalsificationDelta_(presentAgg.avg_attention_factor_count, absentAgg.avg_attention_factor_count) || '',
        proxy_test_result: _characterFalsificationProxyClassify_(scoreDelta, providerRich.high_low_score_delta, Math.min(presentAgg.sample_size, absentAgg.sample_size)),
        notes: 'richness_score combines words, factor counts, and context references'
      });
    }
  });
  return rows;
}

function _characterFalsificationBuildProviderRichnessSummary_(rows) {
  var values = [];
  for (var i = 0; i < (rows || []).length; i++) {
    var score = _characterFalsificationNum_(rows[i].richness_score);
    if (score == null) continue;
    values.push({
      score: score,
      outcome: _characterFalsificationNormalizedOutcomeScore_(rows[i])
    });
  }
  if (!values.length) {
    return { high_low_score_delta: '' };
  }
  values.sort(function(a, b) { return a.score - b.score; });
  var mid = Math.floor(values.length / 2);
  var low = values.slice(0, mid);
  var high = values.slice(mid);
  var lowAgg = _characterFalsificationAggregateScoreItems_(low);
  var highAgg = _characterFalsificationAggregateScoreItems_(high);
  return {
    high_low_score_delta: _characterFalsificationDelta_(highAgg.avg_outcome_score, lowAgg.avg_outcome_score),
    high_sample_size: highAgg.sample_size,
    low_sample_size: lowAgg.sample_size,
    high_avg_richness_score: highAgg.avg_richness_score,
    low_avg_richness_score: lowAgg.avg_richness_score
  };
}

function _characterFalsificationAggregateRichnessRows_(rows) {
  var agg = {
    sample_size: 0,
    rationale_words_sum: 0,
    factor_count_sum: 0,
    context_reference_count_sum: 0,
    attention_factor_count_sum: 0,
    richness_score_sum: 0,
    score_sum: 0
  };
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var score = _characterFalsificationNormalizedOutcomeScore_(row);
    if (score == null) continue;
    agg.sample_size += 1;
    agg.rationale_words_sum += _characterFalsificationNum_(row.rationale_words) || 0;
    agg.factor_count_sum += _characterFalsificationNum_(row.factor_count) || 0;
    agg.context_reference_count_sum += _characterFalsificationNum_(row.context_reference_count) || 0;
    agg.attention_factor_count_sum += _characterFalsificationNum_(row.attention_factor_count) || 0;
    agg.richness_score_sum += _characterFalsificationNum_(row.richness_score) || 0;
    agg.score_sum += score;
  }
  agg.avg_rationale_words = agg.sample_size ? _round4_(agg.rationale_words_sum / agg.sample_size) : null;
  agg.avg_factor_count = agg.sample_size ? _round4_(agg.factor_count_sum / agg.sample_size) : null;
  agg.avg_context_reference_count = agg.sample_size ? _round4_(agg.context_reference_count_sum / agg.sample_size) : null;
  agg.avg_attention_factor_count = agg.sample_size ? _round4_(agg.attention_factor_count_sum / agg.sample_size) : null;
  agg.avg_richness_score = agg.sample_size ? _round4_(agg.richness_score_sum / agg.sample_size) : null;
  agg.avg_outcome_score = agg.sample_size ? _round4_(agg.score_sum / agg.sample_size) : null;
  return agg;
}

function _characterFalsificationAggregateScoreItems_(items) {
  var agg = { sample_size: 0, score_sum: 0, richness_sum: 0 };
  for (var i = 0; i < (items || []).length; i++) {
    var item = items[i] || {};
    agg.sample_size += 1;
    agg.score_sum += item.outcome || 0;
    agg.richness_sum += item.score || 0;
  }
  agg.avg_outcome_score = agg.sample_size ? _round4_(agg.score_sum / agg.sample_size) : null;
  agg.avg_richness_score = agg.sample_size ? _round4_(agg.richness_sum / agg.sample_size) : null;
  return agg;
}

function _characterFalsificationBuildReportRows_(generatedTs, traitDefs, recurrenceMap, providerControlledRows, familyControlledRows, permutationRows, robustRows, proxyRows) {
  var report = [];
  var controlledByKey = _characterFalsificationIndexRows_(providerControlledRows, ['provider', 'trait']);
  var permutationByKey = _characterFalsificationIndexRows_(permutationRows, ['provider', 'trait']);
  var robustByKey = _characterFalsificationIndexRows_(robustRows, ['provider', 'trait']);
  var proxyByKey = _characterFalsificationIndexRows_(proxyRows, ['provider', 'trait']);
  var familyByKey = _characterFalsificationIndexRows_(familyControlledRows, ['provider', 'trait'], true);

  for (var i = 0; i < (traitDefs || []).length; i++) {
    var traitDef = traitDefs[i] || {};
    var provider = String(traitDef.provider || '').trim();
    var trait = String(traitDef.trait || '').trim();
    if (!provider || !trait) continue;
    var key = provider + '|' + trait;
    var controlRow = controlledByKey[key] || null;
    var familySummary = _characterFalsificationSummarizeFamilyRows_(familyByKey[key] || []);
    var permRow = permutationByKey[key] || null;
    var robustRow = robustByKey[key] || null;
    var proxyRow = proxyByKey[key] || null;
    var recurrence = recurrenceMap[provider] || {};
    var providerControlledResult = controlRow ? controlRow.classification : 'inconclusive';
    var familyControlledResult = familySummary.classification;
    var permutationResult = permRow ? permRow.permutation_result : 'inconclusive';
    var robustSampleResult = robustRow ? robustRow.classification : 'inconclusive';
    var proxyTestResult = proxyRow ? proxyRow.proxy_test_result : 'inconclusive';
    var status = _characterFalsificationStatus_(
      providerControlledResult,
      familyControlledResult,
      permutationResult,
      robustSampleResult,
      proxyTestResult,
      controlRow,
      familySummary,
      permRow,
      robustRow
    );
    var confidence = _characterFalsificationConfidenceLevel_(status, controlRow, familySummary, permRow, robustRow, proxyRow);
    report.push({
      generated_ts: generatedTs,
      provider: provider,
      trait: trait,
      recurrence_score: recurrence.recurrence_score == null ? '' : recurrence.recurrence_score,
      provider_controlled_result: providerControlledResult,
      family_controlled_result: familyControlledResult,
      permutation_result: permutationResult,
      robust_sample_result: robustSampleResult,
      proxy_test_result: proxyTestResult,
      falsification_status: status,
      confidence_level: confidence
    });
  }

  report.sort(function(a, b) {
    var ap = String(a.provider || '');
    var bp = String(b.provider || '');
    if (ap !== bp) return ap.localeCompare(bp);
    var as = _characterFalsificationNum_(a.recurrence_score) || 0;
    var bs = _characterFalsificationNum_(b.recurrence_score) || 0;
    if (as !== bs) return bs - as;
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  });
  return report;
}

function _characterFalsificationIndexRows_(rows, fields, useFamilyAggregation) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = [];
    for (var j = 0; j < fields.length; j++) key.push(String(row[fields[j]] || '').trim());
    var joined = key.join('|');
    if (!out[joined]) {
      if (useFamilyAggregation) out[joined] = [];
      else out[joined] = null;
    }
    if (useFamilyAggregation) out[joined].push(row);
    else out[joined] = row;
  }
  return out;
}

function _characterFalsificationSummarizeFamilyRows_(rows) {
  if (!rows || !rows.length) {
    return { classification: 'inconclusive', weighted_score_delta: '', sample_size: 0, support_count: 0 };
  }
  var weightedScore = 0;
  var weightedCount = 0;
  var supportCount = 0;
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var sampleSize = Number(row.sample_size || 0);
    if (sampleSize < 1) continue;
    var score = _characterFalsificationNum_(row.score_delta);
    if (score == null) continue;
    weightedScore += score * sampleSize;
    weightedCount += sampleSize;
    supportCount += 1;
  }
  if (!weightedCount) {
    return { classification: 'inconclusive', weighted_score_delta: '', sample_size: 0, support_count: 0 };
  }
  var delta = _round4_(weightedScore / weightedCount);
  return {
    classification: _characterFalsificationClassifyScoreDelta_(delta, weightedCount),
    weighted_score_delta: delta,
    sample_size: weightedCount,
    support_count: supportCount
  };
}

function _characterFalsificationStatus_(providerControlledResult, familyControlledResult, permutationResult, robustSampleResult, proxyTestResult, controlRow, familySummary, permRow, robustRow) {
  var providerStable = _characterFalsificationHasDirection_(providerControlledResult);
  var familyStable = _characterFalsificationHasDirection_(familyControlledResult);
  var permutationStable = String(permutationResult || '').indexOf('survived') === 0;
  var robustStable = _characterFalsificationHasDirection_(robustSampleResult);
  var proxyDominant = String(proxyTestResult || '').indexOf('proxy_dominant') === 0;
  var thin = _characterFalsificationIsThin_(controlRow) || _characterFalsificationIsThin_(familySummary) || _characterFalsificationIsThin_(permRow) || _characterFalsificationIsThin_(robustRow);

  if (thin) return 'inconclusive';
  if (providerStable && familyStable && permutationStable && robustStable && !proxyDominant) return 'survived';
  if (providerStable && (familyStable || permutationStable || robustStable) && !proxyDominant) return 'partially_survived';
  if (!providerStable || proxyDominant || String(permutationResult || '') === 'null_like') return 'failed';
  return 'inconclusive';
}

function _characterFalsificationConfidenceLevel_(status, controlRow, familySummary, permRow, robustRow, proxyRow) {
  var strongSignals = 0;
  if (controlRow && _characterFalsificationHasDirection_(controlRow.classification)) strongSignals += 1;
  if (familySummary && _characterFalsificationHasDirection_(familySummary.classification)) strongSignals += 1;
  if (permRow && String(permRow.permutation_result || '').indexOf('survived') === 0) strongSignals += 1;
  if (robustRow && _characterFalsificationHasDirection_(robustRow.classification)) strongSignals += 1;
  if (proxyRow && String(proxyRow.proxy_test_result || '').indexOf('proxy_dominant') !== 0) strongSignals += 1;
  if (status === 'survived' && strongSignals >= 4) return 'high';
  if (status === 'partially_survived' && strongSignals >= 3) return 'medium';
  return 'low';
}

function _characterFalsificationHasDirection_(classification) {
  var c = String(classification || '').toLowerCase();
  return c.indexOf('outcome_positive') === 0 || c.indexOf('outcome_negative') === 0;
}

function _characterFalsificationIsThin_(value) {
  if (value == null) return false;
  var sampleSize = _characterFalsificationNum_(value.sample_size);
  if (sampleSize != null && sampleSize < 20) return true;
  if (String(value.classification || '').indexOf('_thin_sample') >= 0) return true;
  if (String(value.sample_depth_warning || '').indexOf('thin_sample') >= 0) return true;
  return false;
}

function _characterFalsificationClassifyScoreDelta_(delta, sampleSize) {
  var label = 'outcome_neutral';
  var d = _characterFalsificationNum_(delta);
  if (d != null) {
    if (d >= 0.05) label = 'outcome_positive';
    else if (d <= -0.05) label = 'outcome_negative';
  }
  if (Number(sampleSize || 0) < 20) label += '_thin_sample';
  return label;
}

function _characterFalsificationRankBucket_(classification) {
  var c = String(classification || '').toLowerCase();
  if (c.indexOf('outcome_positive') === 0) return 0;
  if (c.indexOf('outcome_negative') === 0) return 1;
  if (c.indexOf('outcome_neutral') === 0) return 2;
  return 3;
}

function _characterFalsificationConfidence_(sampleSize, supportSize) {
  var n = Math.min(Number(sampleSize || 0), Number(supportSize || 0));
  if (n < 10) return 'insufficient_sample';
  if (n < 20) return 'thin_sample';
  if (n >= 100) return 'deep_sample';
  return 'usable_sample';
}

function _characterFalsificationProxyClassify_(traitScoreDelta, richnessScoreDelta, sampleSize) {
  var trait = _characterFalsificationNum_(traitScoreDelta);
  var rich = _characterFalsificationNum_(richnessScoreDelta);
  if (Number(sampleSize || 0) < 20) return 'inconclusive_thin_sample';
  if (trait == null || rich == null) return 'inconclusive';
  if (Math.abs(rich) >= Math.abs(trait) * 1.25) return 'proxy_dominant';
  if (Math.abs(trait) >= Math.abs(rich) * 1.25) return 'trait_dominant';
  if (Math.abs(trait) < 0.05 && Math.abs(rich) < 0.05) return 'inconclusive';
  return 'mixed';
}

function _characterFalsificationDelta_(a, b) {
  var aa = _characterFalsificationNum_(a);
  var bb = _characterFalsificationNum_(b);
  if (aa == null || bb == null) return null;
  return _round4_(aa - bb);
}

function _characterFalsificationClassifyNumber_(value) {
  var n = _characterFalsificationNum_(value);
  return n == null ? '' : _round4_(n);
}

function _characterFalsificationCountWords_(text) {
  var s = String(text || '').trim();
  if (!s) return 0;
  return s.split(/\s+/).filter(function(part) { return !!String(part || '').trim(); }).length;
}

function _characterFalsificationNormalizeText_(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function _characterFalsificationCountContextReferences_(text) {
  var normalized = _characterFalsificationNormalizeText_(text);
  if (!normalized) return 0;
  var vocab = [
    'consensus',
    'previous value',
    'surprise history',
    'revision history',
    'family context',
    'signal quality',
    'rates',
    'yield curve',
    'usdjpy',
    'dxy',
    'spx',
    'gold',
    'wti',
    'jp10y',
    'us jp spread',
    'direct fx transmission',
    'hidden detail risk',
    'missing consensus',
    'low signal event',
    'market whipsaw risk',
    'uncertainty'
  ];
  var count = 0;
  for (var i = 0; i < vocab.length; i++) {
    if (normalized.indexOf(vocab[i]) >= 0) count += 1;
  }
  return count;
}

function _characterFalsificationParseCountMap_(text) {
  var out = [];
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
    out.push(key);
  }
  return out;
}

function _characterFalsificationSeed_(text) {
  var s = String(text || '');
  var h = 2166136261;
  for (var i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function _characterFalsificationMulberry32_(seed) {
  var a = seed >>> 0;
  return function() {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    var t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function _characterFalsificationSampleIndexSet_(n, k, rng) {
  var arr = [];
  for (var i = 0; i < n; i++) arr.push(i);
  var limit = Math.max(0, Math.min(k, n));
  for (var j = 0; j < limit; j++) {
    var r = j + Math.floor(rng() * (n - j));
    var tmp = arr[j];
    arr[j] = arr[r];
    arr[r] = tmp;
  }
  return arr.slice(0, limit);
}

function _characterFalsificationMean_(values) {
  if (!values || !values.length) return 0;
  var sum = 0;
  for (var i = 0; i < values.length; i++) sum += Number(values[i] || 0);
  return _round4_(sum / values.length);
}

function _characterFalsificationStd_(values, mean) {
  if (!values || values.length < 2) return 0;
  var m = Number(mean || 0);
  var sum = 0;
  for (var i = 0; i < values.length; i++) {
    var d = Number(values[i] || 0) - m;
    sum += d * d;
  }
  return _round4_(Math.sqrt(sum / (values.length - 1)));
}

function _characterFalsificationPercentile_(values, observed) {
  if (!values || !values.length) return 0.5;
  var obs = Number(observed || 0);
  var lessOrEqual = 0;
  for (var i = 0; i < values.length; i++) {
    if (Number(values[i] || 0) <= obs) lessOrEqual += 1;
  }
  return _round4_(lessOrEqual / values.length);
}

function _characterFalsificationRound4_(value) {
  var n = Number(value || 0);
  if (!isFinite(n)) return 0;
  return _round4_(n);
}

function _characterFalsificationBuildReportRowsFromMaps_() {
  return [];
}

function _characterFalsificationBundleRowsToObjects_(bundle) {
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
