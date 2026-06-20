/*******************************************************
 * provider_character_economic_outcome_link.js
 * - Diagnostic-only Provider Character Economic Outcome Link v1
 * - Compares provider character traits against Economic Value outcomes only
 * - Read-only over existing diagnostic sheets; no provider calls or prediction runs
 *******************************************************/

function menuBuildProviderCharacterEconomicOutcomeLink_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterEconomicOutcomeLink_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character economic outcome link -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Link=' + (res.link_rows_written || 0) +
      ' | Family=' + (res.family_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0),
      'Provider Character Economic Outcome Link',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character economic outcome link -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterEconomicOutcomeLink_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _providerCharacterEconomicLoadSources_(warnings);
  var casePack = _providerCharacterEconomicBuildCasePack_(sources, generatedTs, warnings);
  var residualLookup = _providerCharacterEconomicBuildResidualLookup_(sources.residualBundle, warnings);
  var traitDefs = _providerCharacterEconomicBuildTraitUniverse_(sources.residualBundle, warnings);

  if (!casePack.cases.length) {
    warnings.push('missing_economic_cases');
  }
  if (!traitDefs.length) {
    warnings.push('missing_character_traits');
  }

  var linkRows = _providerCharacterEconomicBuildLinkRows_(generatedTs, traitDefs, casePack.cases, residualLookup, warnings);
  var familyRows = _providerCharacterEconomicBuildFamilyRows_(generatedTs, traitDefs, casePack.cases, residualLookup, warnings);
  var summaryRows = _providerCharacterEconomicBuildSummaryRows_(generatedTs, linkRows, familyRows, warnings);
  var methodologyRows = _providerCharacterEconomicBuildMethodologyRows_(generatedTs, sources, casePack, warnings);

  var linkSheet = getDiagnosticsSheet_('Character_Economic_Outcome_Link', _providerCharacterEconomicOutcomeLinkHeaders_(), warnings);
  var familySheet = getDiagnosticsSheet_('Character_Economic_Outcome_Family_Link', _providerCharacterEconomicOutcomeFamilyHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Character_Economic_Outcome_Summary', _providerCharacterEconomicOutcomeSummaryHeaders_(), warnings);
  var methodologySheet = getDiagnosticsSheet_('Character_Economic_Outcome_Methodology', _providerCharacterEconomicOutcomeMethodologyHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    linkSheet.sheet,
    linkSheet.headers,
    _providerCharacterEconomicObjectsToRows_(linkRows, linkSheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    familySheet.sheet,
    familySheet.headers,
    _providerCharacterEconomicObjectsToRows_(familyRows, familySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    summarySheet.sheet,
    summarySheet.headers,
    _providerCharacterEconomicObjectsToRows_(summaryRows, summarySheet.headers)
  );
  _rewriteSheetRowsPreservingHeaders_(
    methodologySheet.sheet,
    methodologySheet.headers,
    _providerCharacterEconomicObjectsToRows_(methodologyRows, methodologySheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    link_sheet: linkSheet.sheet.getName(),
    family_sheet: familySheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    methodology_sheet: methodologySheet.sheet.getName(),
    link_rows_written: linkRows.length,
    family_rows_written: familyRows.length,
    summary_rows_written: summaryRows.length,
    methodology_rows_written: methodologyRows.length,
    trait_count: traitDefs.length,
    case_count: casePack.cases.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function buildProviderCharacterEconomicOutcomeLink() {
  return buildProviderCharacterEconomicOutcomeLink_();
}

function _providerCharacterEconomicOutcomeLinkHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'trait_domain',
    'row_count_trait_present',
    'row_count_trait_absent',
    'economic_dir_ok_present_count',
    'economic_dir_ok_present_rate',
    'economic_dir_ok_absent_count',
    'economic_dir_ok_absent_rate',
    'economic_dir_ok_delta',
    'avg_abs_error_present',
    'avg_abs_error_absent',
    'avg_abs_error_delta',
    'better_than_consensus_present_rate',
    'better_than_consensus_absent_rate',
    'better_than_consensus_delta',
    'economic_link_result',
    'sample_depth_warning',
    'interpretation',
    'source_basis',
    'notes'
  ];
}

function _providerCharacterEconomicOutcomeFamilyHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'trait_domain',
    'outcome_family',
    'row_count_trait_present',
    'row_count_trait_absent',
    'economic_dir_ok_present_rate',
    'economic_dir_ok_absent_rate',
    'economic_dir_ok_delta',
    'avg_abs_error_present',
    'avg_abs_error_absent',
    'avg_abs_error_delta',
    'better_than_consensus_present_rate',
    'better_than_consensus_absent_rate',
    'better_than_consensus_delta',
    'family_link_result',
    'sample_depth_warning',
    'interpretation',
    'notes'
  ];
}

function _providerCharacterEconomicOutcomeSummaryHeaders_() {
  return [
    'generated_ts',
    'provider',
    'tested_trait_count',
    'economic_positive_count',
    'economic_negative_count',
    'economic_neutral_count',
    'thin_sample_count',
    'insufficient_sample_count',
    'top_positive_traits',
    'top_negative_traits',
    'strongest_family_pockets',
    'overall_provider_interpretation',
    'next_recommended_test',
    'notes'
  ];
}

function _providerCharacterEconomicOutcomeMethodologyHeaders_() {
  return [
    'generated_ts',
    'experiment_name',
    'branch_name',
    'allowed_outcome_layer',
    'forbidden_outcome_layer',
    'source_sheets_used',
    'economic_fields_used',
    'market_reaction_fields_excluded',
    'retired_tabs_not_recreated',
    'interpretation_rule',
    'production_behavior_changed',
    'provider_calls_made',
    'prediction_runs_made',
    'notes'
  ];
}

function _providerCharacterEconomicLoadSources_(warnings) {
  return {
    economicBundle: _characterResidualReadSheetBundle_('Economic_Value_Accuracy', warnings, false),
    providerFamilyEconomicBundle: _characterResidualReadSheetBundle_('Provider_Family_Economic_Accuracy', warnings, false),
    residualBundle: _characterResidualReadSheetBundle_('Provider_Character_Residuals', warnings, false),
    summaryBundle: _characterResidualReadSheetBundle_('Provider_Character_Summary', warnings, false),
    familySummaryBundle: _characterResidualReadSheetBundle_('Provider_Character_Family_Summary', warnings, false),
    baselineBundle: _characterResidualReadSheetBundle_('Character_Baseline_E', warnings, false),
    recurrenceBundle: _characterResidualReadSheetBundle_('Character_Recurrence_Validation', warnings, false),
    driftBundle: _characterResidualReadSheetBundle_('Character_Drift_Assessment', warnings, false),
    diagnosticsBundle: _characterResidualReadSheetBundle_('Provider_Character_Diagnostics', warnings, false),
    attentionIndividualityBundle: _characterResidualReadSheetBundle_('Attention_Provider_Individuality', warnings, false),
    attentionEvidenceBundle: _characterResidualReadSheetBundle_('Attention_Evidence_Report', warnings, false),
    attentionDisagreementReviewBundle: _characterResidualReadSheetBundle_('Attention_Disagreement_Review', warnings, false),
    attentionDisagreementSummaryBundle: _characterResidualReadSheetBundle_('Attention_Disagreement_Summary', warnings, false),
    predictionsBundle: _characterResidualReadSheetBundle_('Predictions', warnings, false),
    eventBundle: _characterResidualReadSheetBundle_('Event', warnings, true)
  };
}

function _providerCharacterEconomicBuildCasePack_(sources, generatedTs, warnings) {
  var cases = [];
  var sourceBasis = [];

  if (sources.economicBundle && sources.economicBundle.rows && sources.economicBundle.rows.length) {
    var econRows = _providerCharacterEconomicBundleRowsToObjects_(sources.economicBundle);
    for (var i = 0; i < econRows.length; i++) {
      var row = econRows[i] || {};
      if (String(row.row_type || '').trim() !== 'case') continue;
      if (String(row.value_scored_flag || '').trim().toUpperCase() !== 'TRUE') continue;
      var econCase = _providerCharacterEconomicNormalizeCase_(row, 'Economic_Value_Accuracy');
      if (econCase) cases.push(econCase);
    }
    if (cases.length) sourceBasis.push('Economic_Value_Accuracy.case');
  }

  if (!cases.length) {
    var predBundle = sources.predictionsBundle;
    var eventBundle = sources.eventBundle;
    if (predBundle && eventBundle) {
      var predIdx = predBundle.idx || {};
      var deduped = _characterResidualDedupePredictionRows_(predBundle.rows || [], predIdx);
      var eventSource = _economicValueAccuracyEventSource_(eventBundle.sheet, warnings);
      var fallbackRows = _economicValueAccuracyCaseObjects_(deduped, predIdx, eventSource, generatedTs, warnings);
      for (var j = 0; j < fallbackRows.length; j++) {
        var fallbackCase = _providerCharacterEconomicNormalizeCase_(fallbackRows[j], 'Predictions+Event');
        if (fallbackCase) cases.push(fallbackCase);
      }
      if (cases.length) sourceBasis.push('Predictions+Event.fallback');
    }
  }

  if (sources.providerFamilyEconomicBundle && sources.providerFamilyEconomicBundle.rows && sources.providerFamilyEconomicBundle.rows.length) {
    sourceBasis.push('Provider_Family_Economic_Accuracy');
  }

  return {
    cases: cases,
    source_basis: sourceBasis.join('|')
  };
}

function _providerCharacterEconomicNormalizeCase_(row, sourceLabel) {
  row = row || {};
  var aiForecastValue = _numOrNull_(row.ai_forecast_value);
  var releasedValue = _numOrNull_(row.released_value);
  var consensusValue = _numOrNull_(row.consensus_value);
  var prevRevision = _numOrNull_(row.prev_revision);
  var baselineValue = consensusValue != null ? consensusValue : prevRevision;
  var actualSurprise = _providerCharacterEconomicDirection_(releasedValue, consensusValue, prevRevision);
  var aiDirection = _providerCharacterEconomicDirection_(aiForecastValue, consensusValue, prevRevision);
  var directionOk = '';
  if (String(row.value_dir_ok || '').trim().toUpperCase() === 'TRUE') directionOk = 'TRUE';
  else if (String(row.value_dir_ok || '').trim().toUpperCase() === 'FALSE') directionOk = 'FALSE';
  else if (aiDirection.dir !== 'unknown' && actualSurprise.dir !== 'unknown') {
    directionOk = (aiDirection.dir === actualSurprise.dir) ? 'TRUE' : 'FALSE';
  }

  var absError = _numOrNull_(row.value_error_abs);
  if (absError == null && aiForecastValue != null && releasedValue != null) {
    absError = _round4_(Math.abs(aiForecastValue - releasedValue));
  }
  var pctError = _numOrNull_(row.value_error_pct);
  if (pctError == null && aiForecastValue != null && releasedValue != null) {
    var base = Math.abs(releasedValue);
    if (base > 1e-9) pctError = _round4_(Math.abs(aiForecastValue - releasedValue) / base);
  }

  var betterThanConsensus = '';
  if (aiForecastValue != null && releasedValue != null && baselineValue != null) {
    betterThanConsensus = (Math.abs(aiForecastValue - releasedValue) < Math.abs(baselineValue - releasedValue)) ? 'TRUE' : 'FALSE';
  }

  var indicatorName = String(row.indicator_name || '').trim();
  var family = String(row.outcome_family || row.family || '').trim();
  if (!family) {
    family = (typeof deriveOutcomeFamily_ === 'function')
      ? (deriveOutcomeFamily_(indicatorName, String(row.genre || '')) || '')
      : '';
  }
  if (!family) family = 'other';

  return {
    generated_ts: String(row.generated_ts || '').trim(),
    event_id: String(row.event_id || '').trim(),
    batch_id: String(row.batch_id || '').trim(),
    type: String(row.type || '').trim(),
    provider: String(row.ai_name || row.provider || '').trim(),
    ai_name: String(row.ai_name || row.provider || '').trim(),
    ai_model: String(row.ai_model || '').trim(),
    indicator_name: indicatorName,
    country: String(row.country || '').trim(),
    release_ts: String(row.release_ts || '').trim(),
    outcome_family: family,
    consensus_value: consensusValue,
    prev_revision: prevRevision,
    ai_forecast_value: aiForecastValue,
    released_value: releasedValue,
    economic_dir_ok: directionOk,
    actual_surprise_dir: actualSurprise.dir,
    ai_value_dir: aiDirection.dir,
    forecast_error_abs: absError,
    forecast_error_pct: pctError,
    better_than_consensus: betterThanConsensus,
    source_label: sourceLabel
  };
}

function _providerCharacterEconomicDirection_(value, consensusValue, prevRevision) {
  var ref = consensusValue != null ? consensusValue : prevRevision;
  if (value == null || ref == null) return { dir: 'unknown', ref_value: ref };
  var delta = Number(value) - Number(ref);
  if (Math.abs(delta) <= _providerCharacterEconomicInlineTolerance_(ref, value)) {
    return { dir: 'inline', ref_value: ref };
  }
  return { dir: delta > 0 ? 'above' : 'below', ref_value: ref };
}

function _providerCharacterEconomicInlineTolerance_(referenceValue, actualValue) {
  var ref = Math.abs(Number(referenceValue || 0));
  var val = Math.abs(Number(actualValue || 0));
  var scale = Math.max(ref, val, 1);
  return Math.max(1e-9, scale * 0.001);
}

function _providerCharacterEconomicBuildResidualLookup_(bundle, warnings) {
  var rows = _providerCharacterEconomicBundleRowsToObjects_(bundle);
  var out = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var key = eventId + '|' + provider;
    if (!out[key]) {
      out[key] = row;
      continue;
    }
    if (_providerCharacterEconomicResidualRowIsNewer_(row, out[key])) {
      out[key] = row;
    }
  }
  return out;
}

function _providerCharacterEconomicResidualRowIsNewer_(candidate, existing) {
  var candidateTs = _characterResidualDateMs_(candidate.generated_ts || candidate.release_ts || candidate.created_ts);
  var existingTs = _characterResidualDateMs_(existing.generated_ts || existing.release_ts || existing.created_ts);
  if (candidateTs !== existingTs) return candidateTs > existingTs;
  return true;
}

function _providerCharacterEconomicBuildTraitUniverse_(residualBundle, warnings) {
  var rows = _providerCharacterEconomicBundleRowsToObjects_(residualBundle);
  var traitMap = {};
  var knownFields = [
    { field: 'risk_language', domain: 'risk_language' },
    { field: 'uncertainty_pattern', domain: 'uncertainty_pattern' },
    { field: 'direction_delta_from_baseline', domain: 'direction_delta_from_baseline' },
    { field: 'emphasized_factors', domain: 'emphasized_factor' },
    { field: 'ignored_factors', domain: 'ignored_factor' },
    { field: 'rationale_style_tags', domain: 'rationale_style_tag' }
  ];

  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim() || 'unknown';
    for (var f = 0; f < knownFields.length; f++) {
      var meta = knownFields[f];
      var tokens = meta.domain === 'risk_language' || meta.domain === 'uncertainty_pattern' || meta.domain === 'direction_delta_from_baseline'
        ? _providerCharacterEconomicTokenList_(row[meta.field])
        : _providerCharacterEconomicTokenList_(row[meta.field]);
      for (var t = 0; t < tokens.length; t++) {
        var token = tokens[t];
        if (!token) continue;
        if (!_providerCharacterEconomicLooksLikeTrait_(token)) continue;
        var key = provider + '|' + token;
        if (!traitMap[key]) {
          traitMap[key] = {
            provider: provider,
            trait: token,
            support: 0,
            domain_counts: {}
          };
        }
        traitMap[key].support += 1;
        traitMap[key].domain_counts[meta.domain] = Number(traitMap[key].domain_counts[meta.domain] || 0) + 1;
      }
    }
  }

  var traits = Object.keys(traitMap).map(function(key) {
    var item = traitMap[key];
    return {
      provider: item.provider,
      trait: item.trait,
      trait_domain: _providerCharacterEconomicPickTraitDomain_(item.domain_counts),
      support: item.support
    };
  }).filter(function(item) {
    return Number(item.support || 0) >= 2;
  });

  traits.sort(function(a, b) {
    if (a.provider !== b.provider) return a.provider.localeCompare(b.provider);
    if (Number(a.support || 0) !== Number(b.support || 0)) return Number(b.support || 0) - Number(a.support || 0);
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  });

  if (!traits.length) {
    warnings.push('trait_universe_shortfall:0');
  }

  return traits;
}

function _providerCharacterEconomicLooksLikeTrait_(token) {
  var t = String(token || '').trim();
  if (!t) return false;
  if (t.length > 80) return false;
  if (/[\r\n]/.test(t)) return false;
  return true;
}

function _providerCharacterEconomicPickTraitDomain_(domainCounts) {
  var entries = [];
  Object.keys(domainCounts || {}).forEach(function(domain) {
    entries.push({ domain: domain, count: Number(domainCounts[domain] || 0) });
  });
  if (!entries.length) return 'unknown';
  entries.sort(function(a, b) {
    if (a.count !== b.count) return b.count - a.count;
    return String(a.domain).localeCompare(String(b.domain));
  });
  if (entries.length > 1 && entries[0].count === entries[1].count) return 'mixed';
  return entries[0].domain || 'unknown';
}

function _providerCharacterEconomicTokenList_(value) {
  var raw = String(value || '').trim();
  if (!raw) return [];
  if (raw.charAt(0) === '[' || raw.charAt(0) === '{') {
    try {
      var parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.map(function(item) { return String(item || '').trim(); }).filter(function(v) { return !!v; });
      }
    } catch (e) {}
  }
  return raw.split(/[|,;]/).map(function(part) {
    return String(part || '').trim();
  }).filter(function(v) { return !!v; });
}

function _providerCharacterEconomicBuildLinkRows_(generatedTs, traitDefs, cases, residualLookup, warnings) {
  var byProviderTrait = {};
  var providerTotals = {};
  var coverageMisses = {};

  for (var i = 0; i < (cases || []).length; i++) {
    var row = cases[i] || {};
    var provider = String(row.provider || row.ai_name || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var residual = residualLookup[eventId + '|' + provider] || null;
    if (!residual) {
      coverageMisses[provider] = Number(coverageMisses[provider] || 0) + 1;
      continue;
    }
    providerTotals[provider] = Number(providerTotals[provider] || 0) + 1;

    for (var t = 0; t < (traitDefs || []).length; t++) {
      var traitDef = traitDefs[t];
      if (traitDef.provider !== provider) continue;
      if (!_providerCharacterEconomicTraitMatchesResidual_(traitDef.trait, residual)) continue;
      var key = provider + '|' + traitDef.trait;
      if (!byProviderTrait[key]) {
        byProviderTrait[key] = {
          generated_ts: generatedTs,
          provider: provider,
          trait: traitDef.trait,
          trait_domain: traitDef.trait_domain,
          present_rows: [],
          absent_rows: [],
          source_basis: [],
          coverage_gap: 0
        };
      }
      byProviderTrait[key].present_rows.push(row);
      byProviderTrait[key].source_basis.push(residual.source_sheet || 'Provider_Character_Residuals');
    }
  }

  var byProvider = {};
  for (var c = 0; c < (cases || []).length; c++) {
    var caseRow = cases[c] || {};
    var caseProvider = String(caseRow.provider || caseRow.ai_name || '').trim();
    var caseEventId = String(caseRow.event_id || '').trim();
    if (!caseProvider || !caseEventId) continue;
    var caseResidual = residualLookup[caseEventId + '|' + caseProvider] || null;
    if (!caseResidual) continue;
    if (!byProvider[caseProvider]) byProvider[caseProvider] = [];
    byProvider[caseProvider].push(caseRow);
  }

  Object.keys(byProviderTrait).forEach(function(key) {
    var g = byProviderTrait[key];
    var providerRows = byProvider[g.provider] || [];
    g.absent_rows = providerRows.filter(function(row) {
      var residual = residualLookup[String(row.event_id || '').trim() + '|' + g.provider];
      return residual ? !_providerCharacterEconomicTraitMatchesResidual_(g.trait, residual) : false;
    });
    g.coverage_gap = Math.max(0, Number(providerTotals[g.provider] || 0) - (g.present_rows.length + g.absent_rows.length));
  });

  var rows = [];
  Object.keys(byProviderTrait).sort().forEach(function(key) {
    var g = byProviderTrait[key];
    rows.push(_providerCharacterEconomicFinalizeLinkRow_(generatedTs, g, warnings));
  });
  return rows;
}

function _providerCharacterEconomicTraitMatchesResidual_(trait, residual) {
  var name = String(trait || '').trim();
  if (!name || !residual) return false;
  if (String(residual.risk_language || '').trim() === name) return true;
  if (String(residual.uncertainty_pattern || '').trim() === name) return true;
  if (String(residual.direction_delta_from_baseline || '').trim() === name) return true;
  if (_providerCharacterEconomicTokenList_(residual.emphasized_factors).indexOf(name) >= 0) return true;
  if (_providerCharacterEconomicTokenList_(residual.ignored_factors).indexOf(name) >= 0) return true;
  if (_providerCharacterEconomicTokenList_(residual.rationale_style_tags).indexOf(name) >= 0) return true;
  return false;
}

function _providerCharacterEconomicFinalizeLinkRow_(generatedTs, g, warnings) {
  var presentMetrics = _providerCharacterEconomicMetrics_(g.present_rows);
  var absentMetrics = _providerCharacterEconomicMetrics_(g.absent_rows);
  var dirDelta = _providerCharacterEconomicDelta_(presentMetrics.dir_ok_rate, absentMetrics.dir_ok_rate);
  var absErrorDelta = _providerCharacterEconomicDelta_(presentMetrics.avg_abs_error, absentMetrics.avg_abs_error);
  var consensusDelta = _providerCharacterEconomicDelta_(presentMetrics.better_than_consensus_rate, absentMetrics.better_than_consensus_rate);
  var result = _providerCharacterEconomicClassify_(g.present_rows.length, g.absent_rows.length, dirDelta, absErrorDelta, consensusDelta);
  var warning = _providerCharacterEconomicSampleWarning_(g.present_rows.length, g.absent_rows.length);
  var interpretation = _providerCharacterEconomicInterpretation_(result, dirDelta, absErrorDelta, consensusDelta, g.present_rows.length, g.absent_rows.length);
  var sourceBasis = _uniqueStrings_(g.source_basis || []).join('|') || 'Provider_Character_Residuals|Economic_Value_Accuracy';

  return {
    generated_ts: generatedTs,
    provider: g.provider,
    trait: g.trait,
    trait_domain: g.trait_domain || _providerCharacterEconomicPickTraitDomain_({}),
    row_count_trait_present: g.present_rows.length,
    row_count_trait_absent: g.absent_rows.length,
    economic_dir_ok_present_count: presentMetrics.dir_ok_count,
    economic_dir_ok_present_rate: presentMetrics.dir_ok_rate == null ? '' : presentMetrics.dir_ok_rate,
    economic_dir_ok_absent_count: absentMetrics.dir_ok_count,
    economic_dir_ok_absent_rate: absentMetrics.dir_ok_rate == null ? '' : absentMetrics.dir_ok_rate,
    economic_dir_ok_delta: dirDelta == null ? '' : _round4_(dirDelta),
    avg_abs_error_present: presentMetrics.avg_abs_error == null ? '' : presentMetrics.avg_abs_error,
    avg_abs_error_absent: absentMetrics.avg_abs_error == null ? '' : absentMetrics.avg_abs_error,
    avg_abs_error_delta: absErrorDelta == null ? '' : _round4_(absErrorDelta),
    better_than_consensus_present_rate: presentMetrics.better_than_consensus_rate == null ? '' : presentMetrics.better_than_consensus_rate,
    better_than_consensus_absent_rate: absentMetrics.better_than_consensus_rate == null ? '' : absentMetrics.better_than_consensus_rate,
    better_than_consensus_delta: consensusDelta == null ? '' : _round4_(consensusDelta),
    economic_link_result: result,
    sample_depth_warning: warning,
    interpretation: interpretation,
    source_basis: sourceBasis,
    notes: _providerCharacterEconomicNotes_(
      g.provider,
      g.trait,
      presentMetrics,
      absentMetrics,
      dirDelta,
      absErrorDelta,
      consensusDelta,
      g.coverage_gap
    )
  };
}

function _providerCharacterEconomicMetrics_(rows) {
  var stats = {
    row_count: 0,
    dir_ok_count: 0,
    dir_ok_coverage: 0,
    abs_error_sum: 0,
    abs_error_count: 0,
    better_than_consensus_count: 0,
    better_than_consensus_coverage: 0
  };
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    stats.row_count += 1;
    var dirOk = _providerCharacterEconomicTruth_(row.economic_dir_ok);
    if (dirOk === true) {
      stats.dir_ok_count += 1;
      stats.dir_ok_coverage += 1;
    } else if (dirOk === false) {
      stats.dir_ok_coverage += 1;
    }

    var absError = _numOrNull_(row.forecast_error_abs);
    if (absError != null) {
      stats.abs_error_sum += Number(absError || 0);
      stats.abs_error_count += 1;
    }

    var better = _providerCharacterEconomicTruth_(row.better_than_consensus);
    if (better === true) {
      stats.better_than_consensus_count += 1;
      stats.better_than_consensus_coverage += 1;
    } else if (better === false) {
      stats.better_than_consensus_coverage += 1;
    }
  }
  return {
    row_count: stats.row_count,
    dir_ok_count: stats.dir_ok_count,
    dir_ok_rate: stats.dir_ok_coverage ? _round4_(stats.dir_ok_count / stats.dir_ok_coverage) : null,
    avg_abs_error: stats.abs_error_count ? _round4_(stats.abs_error_sum / stats.abs_error_count) : null,
    better_than_consensus_count: stats.better_than_consensus_count,
    better_than_consensus_rate: stats.better_than_consensus_coverage ? _round4_(stats.better_than_consensus_count / stats.better_than_consensus_coverage) : null
  };
}

function _providerCharacterEconomicTruth_(value) {
  if (value === true || value === 'TRUE' || value === 'true' || value === 1 || value === '1') return true;
  if (value === false || value === 'FALSE' || value === 'false' || value === 0 || value === '0') return false;
  return null;
}

function _providerCharacterEconomicDelta_(presentValue, absentValue) {
  var p = _numOrNull_(presentValue);
  var a = _numOrNull_(absentValue);
  if (p == null || a == null) return null;
  return p - a;
}

function _providerCharacterEconomicClassify_(presentRows, absentRows, dirDelta, absErrorDelta, consensusDelta) {
  var thin = presentRows < 10 || absentRows < 20;
  var insufficient = presentRows < 5 || absentRows < 10;
  if (insufficient) return 'insufficient_sample';

  var score = 0;
  var dir = _numOrNull_(dirDelta);
  var err = _numOrNull_(absErrorDelta);
  var cons = _numOrNull_(consensusDelta);

  if (dir != null) {
    if (dir >= 0.05) score += 2;
    else if (dir > 0) score += 1;
    else if (dir <= -0.05) score -= 2;
    else if (dir < 0) score -= 1;
  }
  if (err != null) {
    if (err < 0) score += 1;
    else if (err > 0) score -= 1;
  }
  if (cons != null) {
    if (cons > 0) score += 1;
    else if (cons < 0) score -= 1;
  }

  var label = 'economic_neutral';
  if (score >= 2) label = 'economic_positive';
  else if (score <= -2) label = 'economic_negative';

  if (thin) {
    if (label === 'economic_positive') return 'thin_sample_positive';
    if (label === 'economic_negative') return 'thin_sample_negative';
    return 'thin_sample_neutral';
  }
  return label;
}

function _providerCharacterEconomicSampleWarning_(presentRows, absentRows) {
  var parts = [];
  if (presentRows < 10) parts.push('present_thin_sample');
  if (absentRows < 20) parts.push('absent_thin_sample');
  if (presentRows < 5 || absentRows < 10) parts.push('insufficient_sample');
  return parts.join('|');
}

function _providerCharacterEconomicInterpretation_(result, dirDelta, absErrorDelta, consensusDelta, presentRows, absentRows) {
  var dir = _numOrNull_(dirDelta);
  var err = _numOrNull_(absErrorDelta);
  var cons = _numOrNull_(consensusDelta);
  var base;
  if (result === 'economic_positive' || result === 'thin_sample_positive') {
    base = 'Trait-present rows are associated with stronger economic-value performance in this sample.';
  } else if (result === 'economic_negative' || result === 'thin_sample_negative') {
    base = 'Trait-present rows are associated with weaker economic-value performance in this sample.';
  } else if (result === 'insufficient_sample') {
    base = 'Evidence is too thin to interpret this trait reliably.';
  } else {
    base = 'Trait-present rows look economically neutral relative to the provider baseline in this sample.';
  }
  var details = [];
  if (dir != null) details.push('dir_delta=' + _round4_(dir));
  if (err != null) details.push('abs_error_delta=' + _round4_(err));
  if (cons != null) details.push('better_than_consensus_delta=' + _round4_(cons));
  details.push('present=' + presentRows);
  details.push('absent=' + absentRows);
  return base + ' ' + details.join('; ') + '.';
}

function _providerCharacterEconomicNotes_(provider, trait, presentMetrics, absentMetrics, dirDelta, absErrorDelta, consensusDelta, coverageGap) {
  var parts = [];
  parts.push('provider=' + provider);
  parts.push('trait=' + trait);
  parts.push('present_n=' + presentMetrics.row_count);
  parts.push('absent_n=' + absentMetrics.row_count);
  parts.push('dir_delta=' + (dirDelta == null ? 'n/a' : _round4_(dirDelta)));
  parts.push('abs_error_delta=' + (absErrorDelta == null ? 'n/a' : _round4_(absErrorDelta)));
  parts.push('better_than_consensus_delta=' + (consensusDelta == null ? 'n/a' : _round4_(consensusDelta)));
  if (coverageGap) parts.push('residual_coverage_gap=' + coverageGap);
  return parts.join('; ');
}

function _providerCharacterEconomicBuildFamilyRows_(generatedTs, traitDefs, cases, residualLookup, warnings) {
  var rows = [];
  var familyGroups = {};

  for (var i = 0; i < (cases || []).length; i++) {
    var row = cases[i] || {};
    var provider = String(row.provider || row.ai_name || '').trim();
    var eventId = String(row.event_id || '').trim();
    if (!provider || !eventId) continue;
    var residual = residualLookup[eventId + '|' + provider] || null;
    if (!residual) continue;
    var family = String(row.outcome_family || row.family || 'other').trim() || 'other';

    for (var t = 0; t < (traitDefs || []).length; t++) {
      var traitDef = traitDefs[t];
      if (traitDef.provider !== provider) continue;
      if (!_providerCharacterEconomicTraitMatchesResidual_(traitDef.trait, residual)) continue;
      var key = provider + '|' + traitDef.trait + '|' + family;
      if (!familyGroups[key]) {
        familyGroups[key] = {
          generated_ts: generatedTs,
          provider: provider,
          trait: traitDef.trait,
          trait_domain: traitDef.trait_domain,
          outcome_family: family,
          present_rows: [],
          absent_rows: [],
          source_basis: []
        };
      }
      familyGroups[key].present_rows.push(row);
      familyGroups[key].source_basis.push(residual.source_sheet || 'Provider_Character_Residuals');
    }
  }

  var providerFamilyMap = {};
  for (var j = 0; j < (cases || []).length; j++) {
    var prow = cases[j] || {};
    var pprovider = String(prow.provider || prow.ai_name || '').trim();
    var peventId = String(prow.event_id || '').trim();
    if (!pprovider || !peventId) continue;
    var pres = residualLookup[peventId + '|' + pprovider] || null;
    if (!pres) continue;
    var pfam = String(prow.outcome_family || prow.family || 'other').trim() || 'other';
    var pkey = pprovider + '|' + pfam;
    if (!providerFamilyMap[pkey]) providerFamilyMap[pkey] = [];
    providerFamilyMap[pkey].push(prow);
  }

  Object.keys(familyGroups).forEach(function(key) {
    var g = familyGroups[key];
    var providerFamilyRows = providerFamilyMap[g.provider + '|' + g.outcome_family] || [];
    g.absent_rows = providerFamilyRows.filter(function(row) {
      var residual = residualLookup[String(row.event_id || '').trim() + '|' + g.provider];
      return residual ? !_providerCharacterEconomicTraitMatchesResidual_(g.trait, residual) : false;
    });
    rows.push(_providerCharacterEconomicFinalizeFamilyRow_(generatedTs, g, warnings));
  });

  rows.sort(function(a, b) {
    if (a.provider !== b.provider) return a.provider.localeCompare(b.provider);
    if (a.trait !== b.trait) return a.trait.localeCompare(b.trait);
    return a.outcome_family.localeCompare(b.outcome_family);
  });
  return rows;
}

function _providerCharacterEconomicFinalizeFamilyRow_(generatedTs, g, warnings) {
  var presentMetrics = _providerCharacterEconomicMetrics_(g.present_rows);
  var absentMetrics = _providerCharacterEconomicMetrics_(g.absent_rows);
  var dirDelta = _providerCharacterEconomicDelta_(presentMetrics.dir_ok_rate, absentMetrics.dir_ok_rate);
  var absErrorDelta = _providerCharacterEconomicDelta_(presentMetrics.avg_abs_error, absentMetrics.avg_abs_error);
  var consensusDelta = _providerCharacterEconomicDelta_(presentMetrics.better_than_consensus_rate, absentMetrics.better_than_consensus_rate);
  var result = _providerCharacterEconomicClassify_(g.present_rows.length, g.absent_rows.length, dirDelta, absErrorDelta, consensusDelta);
  var warning = _providerCharacterEconomicSampleWarning_(g.present_rows.length, g.absent_rows.length);
  var interpretation = _providerCharacterEconomicInterpretation_(result, dirDelta, absErrorDelta, consensusDelta, g.present_rows.length, g.absent_rows.length);
  var sourceBasis = _uniqueStrings_(g.source_basis || []).join('|') || 'Provider_Character_Residuals|Economic_Value_Accuracy';

  return {
    generated_ts: generatedTs,
    provider: g.provider,
    trait: g.trait,
    trait_domain: g.trait_domain || 'unknown',
    outcome_family: g.outcome_family,
    row_count_trait_present: g.present_rows.length,
    row_count_trait_absent: g.absent_rows.length,
    economic_dir_ok_present_rate: presentMetrics.dir_ok_rate == null ? '' : presentMetrics.dir_ok_rate,
    economic_dir_ok_absent_rate: absentMetrics.dir_ok_rate == null ? '' : absentMetrics.dir_ok_rate,
    economic_dir_ok_delta: dirDelta == null ? '' : _round4_(dirDelta),
    avg_abs_error_present: presentMetrics.avg_abs_error == null ? '' : presentMetrics.avg_abs_error,
    avg_abs_error_absent: absentMetrics.avg_abs_error == null ? '' : absentMetrics.avg_abs_error,
    avg_abs_error_delta: absErrorDelta == null ? '' : _round4_(absErrorDelta),
    better_than_consensus_present_rate: presentMetrics.better_than_consensus_rate == null ? '' : presentMetrics.better_than_consensus_rate,
    better_than_consensus_absent_rate: absentMetrics.better_than_consensus_rate == null ? '' : absentMetrics.better_than_consensus_rate,
    better_than_consensus_delta: consensusDelta == null ? '' : _round4_(consensusDelta),
    family_link_result: result,
    sample_depth_warning: warning,
    interpretation: interpretation,
    notes: _providerCharacterEconomicNotes_(
      g.provider,
      g.trait + '|' + g.outcome_family,
      presentMetrics,
      absentMetrics,
      dirDelta,
      absErrorDelta,
      consensusDelta,
      0
    ) + '; source_basis=' + sourceBasis
  };
}

function _providerCharacterEconomicBuildSummaryRows_(generatedTs, linkRows, familyRows, warnings) {
  var byProvider = {};
  for (var i = 0; i < (linkRows || []).length; i++) {
    var row = linkRows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!byProvider[provider]) {
      byProvider[provider] = {
        provider: provider,
        tested_traits: {},
        positive: [],
        negative: [],
        neutral: [],
        thin: [],
        insufficient: [],
        familyPockets: []
      };
    }
    var g = byProvider[provider];
    g.tested_traits[row.trait] = true;
    var result = String(row.economic_link_result || '').trim();
    if (result.indexOf('positive') >= 0) g.positive.push(row);
    else if (result.indexOf('negative') >= 0) g.negative.push(row);
    else if (result.indexOf('thin_sample') >= 0) g.thin.push(row);
    else if (result === 'insufficient_sample') g.insufficient.push(row);
    else g.neutral.push(row);
  }

  var familyPocketMap = {};
  for (var j = 0; j < (familyRows || []).length; j++) {
    var frow = familyRows[j] || {};
    var fprovider = String(frow.provider || '').trim();
    if (!fprovider) continue;
    var key = fprovider + '|' + String(frow.trait || '').trim() + '|' + String(frow.outcome_family || '').trim();
    familyPocketMap[key] = frow;
  }

  var rows = [];
  Object.keys(byProvider).sort().forEach(function(provider) {
    var g = byProvider[provider];
    var testedCount = Object.keys(g.tested_traits).length;
    var topPositive = _providerCharacterEconomicTraitSummaryText_(g.positive, 5, true);
    var topNegative = _providerCharacterEconomicTraitSummaryText_(g.negative, 5, false);
    var strongestFamilyPockets = _providerCharacterEconomicFamilyPocketText_(familyRows, provider);
    var interpretation = _providerCharacterEconomicProviderInterpretation_(g);
    var nextTest = _providerCharacterEconomicNextTest_(g, interpretation);
    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      tested_trait_count: testedCount,
      economic_positive_count: g.positive.length,
      economic_negative_count: g.negative.length,
      economic_neutral_count: g.neutral.length,
      thin_sample_count: g.thin.length,
      insufficient_sample_count: g.insufficient.length,
      top_positive_traits: topPositive,
      top_negative_traits: topNegative,
      strongest_family_pockets: strongestFamilyPockets,
      overall_provider_interpretation: interpretation,
      next_recommended_test: nextTest,
      notes: _providerCharacterEconomicProviderNotes_(g)
    });
  });

  return rows;
}

function _providerCharacterEconomicTraitSummaryText_(rows, limit, positive) {
  var list = (rows || []).slice().sort(function(a, b) {
    var ad = _numOrNull_(a.economic_dir_ok_delta);
    var bd = _numOrNull_(b.economic_dir_ok_delta);
    if (ad !== bd) {
      if (positive) return (bd == null ? -999 : bd) - (ad == null ? -999 : ad);
      return (ad == null ? 999 : ad) - (bd == null ? 999 : bd);
    }
    var aa = Math.abs(_numOrNull_(a.avg_abs_error_delta) || 0);
    var ba = Math.abs(_numOrNull_(b.avg_abs_error_delta) || 0);
    if (aa !== ba) return positive ? aa - ba : ba - aa;
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  }).slice(0, limit || 5);
  if (!list.length) return '';
  return list.map(function(row) {
    return row.trait + '(' +
      'delta=' + (row.economic_dir_ok_delta === '' ? 'n/a' : row.economic_dir_ok_delta) +
      ',err_delta=' + (row.avg_abs_error_delta === '' ? 'n/a' : row.avg_abs_error_delta) +
      ',n=' + row.row_count_trait_present +
      ',cls=' + row.economic_link_result +
      ')';
  }).join(' | ');
}

function _providerCharacterEconomicFamilyPocketText_(familyRows, provider) {
  var list = [];
  for (var i = 0; i < (familyRows || []).length; i++) {
    var row = familyRows[i] || {};
    if (String(row.provider || '').trim() !== provider) continue;
    var delta = _numOrNull_(row.economic_dir_ok_delta);
    if (delta == null) continue;
    if (String(row.family_link_result || '').indexOf('positive') >= 0 || String(row.family_link_result || '').indexOf('negative') >= 0) {
      list.push(row);
    }
  }
  list.sort(function(a, b) {
    var ad = Math.abs(_numOrNull_(a.economic_dir_ok_delta) || 0);
    var bd = Math.abs(_numOrNull_(b.economic_dir_ok_delta) || 0);
    if (ad !== bd) return bd - ad;
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  });
  list = list.slice(0, 5);
  if (!list.length) return '';
  return list.map(function(row) {
    return row.trait + '/' + row.outcome_family + '(' +
      (row.economic_dir_ok_delta === '' ? 'n/a' : row.economic_dir_ok_delta) +
      ',n=' + row.row_count_trait_present +
      ',cls=' + row.family_link_result +
      ')';
  }).join(' | ');
}

function _providerCharacterEconomicProviderInterpretation_(group) {
  var positive = group.positive.length;
  var negative = group.negative.length;
  var thin = group.thin.length;
  var insufficient = group.insufficient.length;
  if (insufficient >= 1 && positive === 0 && negative === 0 && group.neutral.length === 0) {
    return 'insufficient_evidence';
  }
  if (positive >= 3 && positive >= negative * 2) return 'broad_economic_positive_skew';
  if (negative >= 3 && negative >= positive * 2) return 'broad_economic_negative_skew';
  if (positive > 0 && negative === 0) return 'economic_positive_with_some_thin_slices';
  if (negative > 0 && positive === 0) return 'economic_negative_with_some_thin_slices';
  if (thin > positive + negative + group.neutral.length) return 'thin_or_inconclusive';
  return 'mixed_or_neutral';
}

function _providerCharacterEconomicNextTest_(group, interpretation) {
  if (interpretation === 'broad_economic_positive_skew' || interpretation === 'broad_economic_negative_skew') {
    return 'Economic_Falsification_v1';
  }
  if (interpretation === 'thin_or_inconclusive' || interpretation === 'insufficient_evidence') {
    return 'Collect_more_economic_rows';
  }
  return 'Economic_Family_Controlled_Check';
}

function _providerCharacterEconomicProviderNotes_(group) {
  return [
    'traits_tested=' + Object.keys(group.tested_traits || {}).length,
    'positive=' + group.positive.length,
    'negative=' + group.negative.length,
    'neutral=' + group.neutral.length,
    'thin=' + group.thin.length,
    'insufficient=' + group.insufficient.length
  ].join('; ');
}

function _providerCharacterEconomicBuildMethodologyRows_(generatedTs, sources, casePack, warnings) {
  var sourceSheetsUsed = [];
  if (sources.economicBundle) sourceSheetsUsed.push('Economic_Value_Accuracy');
  if (sources.providerFamilyEconomicBundle) sourceSheetsUsed.push('Provider_Family_Economic_Accuracy');
  if (sources.residualBundle) sourceSheetsUsed.push('Provider_Character_Residuals');
  if (sources.summaryBundle) sourceSheetsUsed.push('Provider_Character_Summary');
  if (sources.familySummaryBundle) sourceSheetsUsed.push('Provider_Character_Family_Summary');
  if (sources.baselineBundle) sourceSheetsUsed.push('Character_Baseline_E');
  if (sources.recurrenceBundle) sourceSheetsUsed.push('Character_Recurrence_Validation');
  if (sources.driftBundle) sourceSheetsUsed.push('Character_Drift_Assessment');
  if (sources.diagnosticsBundle) sourceSheetsUsed.push('Provider_Character_Diagnostics');
  if (sources.attentionIndividualityBundle) sourceSheetsUsed.push('Attention_Provider_Individuality');
  if (sources.attentionEvidenceBundle) sourceSheetsUsed.push('Attention_Evidence_Report');
  if (sources.attentionDisagreementReviewBundle) sourceSheetsUsed.push('Attention_Disagreement_Review');
  if (sources.attentionDisagreementSummaryBundle) sourceSheetsUsed.push('Attention_Disagreement_Summary');
  if (casePack && String(casePack.source_basis || '').indexOf('Predictions+Event.fallback') >= 0) {
    sourceSheetsUsed.push('Predictions');
    sourceSheetsUsed.push('Event');
  }
  sourceSheetsUsed = _uniqueStrings_(sourceSheetsUsed);
  if (!sourceSheetsUsed.length) sourceSheetsUsed = ['Economic_Value_Accuracy', 'Provider_Character_Residuals'];

  var notes = [];
  if (warnings && warnings.length) {
    notes.push('warnings=' + _uniqueStrings_(warnings).join('|'));
  }
  if (casePack && casePack.source_basis) {
    notes.push('source_basis=' + casePack.source_basis);
  }
  notes.push('residuals_used_for_trait_matching');
  notes.push('economic_scoring_is_value_only');
  notes.push('no_provider_calls');
  notes.push('no_prediction_runs');

  return [{
    generated_ts: generatedTs,
    experiment_name: 'Provider Character Economic Outcome Link v1',
    branch_name: 'Provider Character Economic Validation Branch',
    allowed_outcome_layer: 'Economic Value Prediction Layer',
    forbidden_outcome_layer: 'Market Reaction Prediction Layer',
    source_sheets_used: sourceSheetsUsed.join('|'),
    economic_fields_used: [
      'ai_forecast_value',
      'released_value',
      'consensus_value',
      'prev_revision',
      'forecast_error_abs',
      'forecast_error_pct',
      'economic_dir_ok',
      'actual_surprise_dir',
      'ai_value_dir',
      'better_than_consensus',
      'Economic_Value_Accuracy.case'
    ].join('|'),
    market_reaction_fields_excluded: [
      'mr_dir_ok',
      'mr_strength_ok',
      'mr_sustain_ok',
      'overall_ok',
      'realized_pips',
      'mr_real_dir',
      'mr_real_strength',
      'mr_real_sustain_min',
      'outcome_score',
      'Evaluation_Rows',
      'Evaluation_Summary'
    ].join('|'),
    retired_tabs_not_recreated: [
      'Character_Outcome_Link',
      'Character_Outcome_Summary',
      'Character_Outcome_Family_Link',
      'Character_Outcome_Provider_Controlled',
      'Character_Outcome_Family_Controlled',
      'Character_Outcome_Permutation_Test',
      'Character_Outcome_Robust_Traits',
      'Character_Good_Reasoning_Proxy_Test',
      'Character_Outcome_Falsification_Report',
      'Character_Signal_Candidates',
      'Character_Signal_Candidate_Summary',
      'Character_Signal_Candidate_Family_Map',
      'Character_Signal_Readiness_Report',
      'Character_Signal_Shadow_Test',
      'Character_Signal_Shadow_Summary',
      'Character_Signal_Shadow_Family',
      'Character_Signal_Shadow_Readiness'
    ].join('|'),
    interpretation_rule: 'Classify positive when economic_dir_ok improves by at least +0.05 or when error and consensus metrics improve in the same direction; classify negative when the reverse holds; otherwise neutral. Prefix thin_sample_ when present rows are below 10 or absent rows are below 20; use insufficient_sample when comparison coverage is too small to judge.',
    production_behavior_changed: 'FALSE',
    provider_calls_made: 'FALSE',
    prediction_runs_made: 'FALSE',
    notes: notes.join(' | ')
  }];
}

function _providerCharacterEconomicObjectsToRows_(rows, headers) {
  return _characterResidualObjectsToRows_(rows, headers);
}

function _providerCharacterEconomicBundleRowsToObjects_(bundle) {
  var rows = (bundle && bundle.rows) || [];
  var headers = (bundle && bundle.headers) || [];
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = row[j];
    }
    out.push(obj);
  }
  return out;
}

function _providerCharacterEconomicKey_(name) {
  return String(name || '').trim();
}
