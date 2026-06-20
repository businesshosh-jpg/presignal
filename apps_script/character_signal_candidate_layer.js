/*******************************************************
 * character_signal_candidate_layer.js
 * - Diagnostic-only Character Signal Candidate Layer v1
 * - Bridges validated Character traits toward future Meta Intelligence research
 *******************************************************/

function menuBuildCharacterSignalCandidateLayer_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildCharacterSignalCandidateLayer_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Character signal candidate layer -> Build sheets', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Candidates=' + (res.candidate_rows_written || 0) +
      ' | Summary=' + (res.summary_rows_written || 0) +
      ' | Families=' + (res.family_map_rows_written || 0),
      'Character Signal Candidates',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Character signal candidate layer -> Build sheets failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildCharacterSignalCandidateLayer_() {
  var generatedTs = new Date().toISOString();
  var warnings = [];

  var sources = _characterSignalCandidateLoadSources_(warnings);
  var universe = _characterSignalCandidateBuildUniverse_(sources, warnings);
  if (!universe.length) {
    warnings.push('candidate_universe_empty');
  }

  var rows = _characterSignalCandidateBuildRows_(generatedTs, universe, sources, warnings);
  var summaryRows = _characterSignalCandidateBuildSummaryRows_(generatedTs, rows, sources, warnings);
  var familyRows = _characterSignalCandidateBuildFamilyMapRows_(generatedTs, rows, sources, warnings);
  var readinessRows = _characterSignalCandidateBuildReadinessRows_(generatedTs, rows);

  var candidateSheet = getDiagnosticsSheet_('Character_Signal_Candidates', _characterSignalCandidateHeaders_(), warnings);
  var summarySheet = getDiagnosticsSheet_('Character_Signal_Candidate_Summary', _characterSignalCandidateSummaryHeaders_(), warnings);
  var familySheet = getDiagnosticsSheet_('Character_Signal_Candidate_Family_Map', _characterSignalCandidateFamilyHeaders_(), warnings);
  var readinessSheet = getDiagnosticsSheet_('Character_Signal_Readiness_Report', _characterSignalCandidateReadinessHeaders_(), warnings);

  _rewriteSheetRowsPreservingHeaders_(
    candidateSheet.sheet,
    candidateSheet.headers,
    _characterResidualObjectsToRows_(rows, candidateSheet.headers)
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
  _rewriteSheetRowsPreservingHeaders_(
    readinessSheet.sheet,
    readinessSheet.headers,
    _characterResidualObjectsToRows_(readinessRows, readinessSheet.headers)
  );

  return {
    status: 'ok',
    generated_ts: generatedTs,
    candidate_sheet: candidateSheet.sheet.getName(),
    summary_sheet: summarySheet.sheet.getName(),
    family_map_sheet: familySheet.sheet.getName(),
    readiness_sheet: readinessSheet.sheet.getName(),
    candidate_rows_written: rows.length,
    summary_rows_written: summaryRows.length,
    family_map_rows_written: familyRows.length,
    readiness_rows_written: readinessRows.length,
    candidate_count: rows.length,
    warnings: _uniqueStrings_(warnings)
  };
}

function _characterSignalCandidateHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'signal_candidate_id',
    'signal_family',
    'trait_domain',
    'recurrence_classification',
    'recurrence_score',
    'outcome_link_status',
    'falsification_status',
    'drift_status',
    'profile_similarity_score',
    'discovery_score_delta',
    'validation_score_delta',
    'effect_direction',
    'effect_size_stability',
    'sample_size_total',
    'sample_size_discovery',
    'sample_size_validation',
    'sample_depth_warning',
    'confidence_level',
    'candidate_status',
    'recommended_future_use',
    'exclusion_reason',
    'notes'
  ];
}

function _characterSignalCandidateSummaryHeaders_() {
  return [
    'generated_ts',
    'provider',
    'total_traits_reviewed',
    'strong_candidate_count',
    'medium_candidate_count',
    'weak_candidate_count',
    'rejected_count',
    'inconclusive_count',
    'top_positive_candidates',
    'top_negative_candidates',
    'strongest_reliability_candidates',
    'strongest_calibration_candidates',
    'provider_signal_profile_note'
  ];
}

function _characterSignalCandidateFamilyHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'outcome_family',
    'family_sample_size',
    'family_effect_direction',
    'family_score_delta',
    'family_recurrence_strength',
    'family_confidence',
    'family_usefulness_note',
    'sample_depth_warning'
  ];
}

function _characterSignalCandidateReadinessHeaders_() {
  return [
    'generated_ts',
    'provider',
    'trait',
    'candidate_status',
    'recurrence_evidence',
    'outcome_evidence',
    'falsification_evidence',
    'drift_evidence',
    'sample_depth_evidence',
    'readiness_classification',
    'calibration_readiness',
    'reliability_readiness',
    'next_test_recommendation',
    'final_note'
  ];
}

function _characterSignalCandidateLoadSources_(warnings) {
  return {
    falsificationBundle: _characterResidualReadSheetBundle_('Character_Outcome_Falsification_Report', warnings, false),
    recurrenceValidationBundle: _characterResidualReadSheetBundle_('Character_Outcome_Recurrence_Validation', warnings, false),
    recurrenceInterpretationBundle: _characterResidualReadSheetBundle_('Character_Outcome_Recurrence_Interpretation', warnings, false),
    outcomeLinkBundle: _characterResidualReadSheetBundle_('Character_Outcome_Link', warnings, false),
    familyLinkBundle: _characterResidualReadSheetBundle_('Character_Outcome_Family_Link', warnings, false),
    recurrenceFamilyBundle: _characterResidualReadSheetBundle_('Character_Recurrence_Family_Validation', warnings, false),
    driftBundle: _characterResidualReadSheetBundle_('Character_Drift_Assessment', warnings, false),
    providerSummaryBundle: _characterResidualReadSheetBundle_('Provider_Character_Summary', warnings, false),
    providerFamilySummaryBundle: _characterResidualReadSheetBundle_('Provider_Character_Family_Summary', warnings, false),
    robustTraitsBundle: _characterResidualReadSheetBundle_('Character_Outcome_Robust_Traits', warnings, false)
  };
}

function _characterSignalCandidateBuildUniverse_(sources, warnings) {
  var keys = {};
  var rows = [];
  var preferredBundles = [
    sources.falsificationBundle,
    sources.recurrenceInterpretationBundle,
    sources.recurrenceValidationBundle,
    sources.outcomeLinkBundle,
    sources.familyLinkBundle,
    sources.recurrenceFamilyBundle,
    sources.driftBundle,
    sources.providerSummaryBundle,
    sources.providerFamilySummaryBundle,
    sources.robustTraitsBundle
  ];

  for (var b = 0; b < preferredBundles.length; b++) {
    var bundle = preferredBundles[b];
    if (!bundle) continue;
    var bundleRows = _characterSignalCandidateBundleRowsToObjects_(bundle);
    for (var i = 0; i < bundleRows.length; i++) {
      var row = bundleRows[i] || {};
      var provider = String(row.provider || row.ai_name || '').trim();
      var trait = String(row.trait || row.pattern_name || row.signal_trait || '').trim();
      if (!provider || !trait) continue;
      var key = provider + '|' + trait;
      if (!keys[key]) {
        keys[key] = {
          provider: provider,
          trait: trait
        };
      }
    }
  }

  var universe = Object.keys(keys).map(function(key) {
    return keys[key];
  });
  universe.sort(function(a, b) {
    var ap = String(a.provider || '');
    var bp = String(b.provider || '');
    if (ap !== bp) return ap.localeCompare(bp);
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  });

  if (!universe.length) {
    warnings.push('candidate_universe_shortfall:0');
  }

  return universe;
}

function _characterSignalCandidateBuildRows_(generatedTs, universe, sources, warnings) {
  var falsificationRows = _characterSignalCandidateIndexRows_(sources.falsificationBundle, ['provider', 'trait']);
  var recurrenceRows = _characterSignalCandidateIndexRows_(sources.recurrenceValidationBundle, ['provider', 'trait']);
  var recurrenceInterpretRows = _characterSignalCandidateIndexRows_(sources.recurrenceInterpretationBundle, ['provider', 'trait']);
  var outcomeLinkRows = _characterSignalCandidateIndexRows_(sources.outcomeLinkBundle, ['provider', 'trait']);
  var familyLinkRows = _characterSignalCandidateIndexRows_(sources.familyLinkBundle, ['provider', 'trait'], true);
  var recurrenceFamilyRows = _characterSignalCandidateIndexRows_(sources.recurrenceFamilyBundle, ['provider', 'outcome_family']);
  var driftRows = _characterSignalCandidateIndexRows_(sources.driftBundle, ['provider']);
  var providerSummaryRows = _characterSignalCandidateIndexRows_(sources.providerSummaryBundle, ['provider']);
  var robustRows = _characterSignalCandidateIndexRows_(sources.robustTraitsBundle, ['provider', 'trait']);

  var rows = [];
  for (var i = 0; i < universe.length; i++) {
    var base = universe[i] || {};
    var provider = String(base.provider || '').trim();
    var trait = String(base.trait || '').trim();
    if (!provider || !trait) continue;
    var key = provider + '|' + trait;

    var recurrenceRow = recurrenceRows[key] || null;
    var recurrenceInterpRow = recurrenceInterpretRows[key] || null;
    var falsificationRow = falsificationRows[key] || null;
    var outcomeRow = outcomeLinkRows[key] || null;
    var familyRows = familyLinkRows[key] || [];
    var driftRow = driftRows[provider] || null;
    var providerSummaryRow = providerSummaryRows[provider] || null;
    var robustRow = robustRows[key] || null;

    var traitDomains = _characterSignalCandidateTraitDomains_(trait);
    var traitDomain = _characterSignalCandidatePrimaryTraitDomain_(traitDomains);
    var signalFamily = _characterSignalCandidateSignalFamily_(traitDomain);

    var recurrenceClassification = _characterSignalCandidateText_(recurrenceRow && recurrenceRow.recurrence_classification, recurrenceInterpRow && recurrenceInterpRow.recurrence_result, '');
    var recurrenceScore = _characterSignalCandidateNum_(recurrenceRow && recurrenceRow.recurrence_score, falsificationRow && falsificationRow.recurrence_score);
    var outcomeLinkStatus = _characterSignalCandidateText_(outcomeRow && outcomeRow.classification, falsificationRow && falsificationRow.provider_controlled_result, '');
    var falsificationStatus = _characterSignalCandidateText_(falsificationRow && falsificationRow.falsification_status, '');
    var driftStatus = _characterSignalCandidateText_(recurrenceInterpRow && recurrenceInterpRow.drift_result, driftRow && driftRow.drift_classification, '');
    var profileSimilarityScore = _characterSignalCandidateNum_(recurrenceInterpRow && recurrenceInterpRow.profile_similarity_score, driftRow && driftRow.profile_similarity_score);

    var discoveryScoreDelta = _characterSignalCandidateNum_(recurrenceRow && recurrenceRow.discovery_score_delta, outcomeRow && outcomeRow.score_delta, falsificationRow && falsificationRow.recurrence_score);
    var validationScoreDelta = _characterSignalCandidateNum_(recurrenceRow && recurrenceRow.validation_score_delta, '');
    var effectDirection = _characterSignalCandidateEffectDirection_(discoveryScoreDelta, validationScoreDelta, outcomeLinkStatus);
    var effectSizeStability = _characterSignalCandidateNum_(recurrenceRow && recurrenceRow.effect_size_stability, '');

    var sampleSizeDiscovery = Number((recurrenceRow && (recurrenceRow.discovery_present_sample_size || recurrenceRow.discovery_sample_size)) || (outcomeRow && outcomeRow.sample_size) || 0);
    var sampleSizeValidation = recurrenceRow ? Number((recurrenceRow && (recurrenceRow.validation_present_sample_size || recurrenceRow.validation_sample_size)) || 0) : null;
    var sampleSizeTotal = sampleSizeDiscovery + Number(sampleSizeValidation || 0);
    if (!sampleSizeDiscovery && sampleSizeValidation == null && outcomeRow) {
      sampleSizeDiscovery = Number(outcomeRow.sample_size || 0);
      sampleSizeTotal = sampleSizeDiscovery;
    }

    var proxyResult = String(falsificationRow && falsificationRow.proxy_test_result || '').trim();
    var sampleDepthWarning = _characterSignalCandidateSampleDepthWarning_(sampleSizeDiscovery, sampleSizeValidation, outcomeRow, recurrenceRow, falsificationRow, driftStatus, proxyResult);

    var assessment = _characterSignalCandidateAssess_({
      provider: provider,
      trait: trait,
      recurrenceClassification: recurrenceClassification,
      recurrenceScore: recurrenceScore,
      outcomeLinkStatus: outcomeLinkStatus,
      falsificationStatus: falsificationStatus,
      driftStatus: driftStatus,
      profileSimilarityScore: profileSimilarityScore,
      discoveryScoreDelta: discoveryScoreDelta,
      validationScoreDelta: validationScoreDelta,
      effectDirection: effectDirection,
      effectSizeStability: effectSizeStability,
      sampleSizeTotal: sampleSizeTotal,
      sampleSizeDiscovery: sampleSizeDiscovery,
      sampleSizeValidation: sampleSizeValidation,
      sampleDepthWarning: sampleDepthWarning,
      proxyResult: proxyResult,
      recurrenceInterpRow: recurrenceInterpRow,
      outcomeRow: outcomeRow,
      falsificationRow: falsificationRow,
      driftRow: driftRow,
      providerSummaryRow: providerSummaryRow,
      robustRow: robustRow
    });

    rows.push({
      generated_ts: generatedTs,
      provider: provider,
      trait: trait,
      signal_candidate_id: provider + '__' + trait,
      signal_family: signalFamily,
      trait_domain: traitDomain,
      recurrence_classification: recurrenceClassification,
      recurrence_score: recurrenceScore == null ? '' : _round4_(recurrenceScore),
      outcome_link_status: outcomeLinkStatus,
      falsification_status: falsificationStatus,
      drift_status: driftStatus,
      profile_similarity_score: profileSimilarityScore == null ? '' : _round4_(profileSimilarityScore),
      discovery_score_delta: discoveryScoreDelta == null ? '' : _round4_(discoveryScoreDelta),
      validation_score_delta: validationScoreDelta == null ? '' : _round4_(validationScoreDelta),
      effect_direction: effectDirection,
      effect_size_stability: effectSizeStability == null ? '' : _round4_(effectSizeStability),
      sample_size_total: sampleSizeTotal,
      sample_size_discovery: sampleSizeDiscovery,
      sample_size_validation: sampleSizeValidation == null ? '' : sampleSizeValidation,
      sample_depth_warning: sampleDepthWarning,
      confidence_level: assessment.confidence_level,
      candidate_status: assessment.candidate_status,
      recommended_future_use: assessment.recommended_future_use,
      exclusion_reason: assessment.exclusion_reason,
      notes: assessment.notes
    });
  }

  rows.sort(function(a, b) {
    var ap = String(a.provider || '');
    var bp = String(b.provider || '');
    if (ap !== bp) return ap.localeCompare(bp);
    var aBucket = _characterSignalCandidateRankBucket_(a.candidate_status);
    var bBucket = _characterSignalCandidateRankBucket_(b.candidate_status);
    if (aBucket !== bBucket) return aBucket - bBucket;
    var aScore = _characterSignalCandidateNum_(a.recurrence_score, a.discovery_score_delta);
    var bScore = _characterSignalCandidateNum_(b.recurrence_score, b.discovery_score_delta);
    if (aScore !== bScore) return (bScore || 0) - (aScore || 0);
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  });

  return rows;
}

function _characterSignalCandidateBuildSummaryRows_(generatedTs, rows, sources, warnings) {
  var byProvider = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    if (!provider) continue;
    if (!byProvider[provider]) {
      byProvider[provider] = {
        provider: provider,
        total_traits_reviewed: 0,
        strong_candidate_count: 0,
        medium_candidate_count: 0,
        weak_candidate_count: 0,
        rejected_count: 0,
        inconclusive_count: 0,
        positives: [],
        negatives: [],
        reliability: [],
        calibration: []
      };
    }
    var g = byProvider[provider];
    g.total_traits_reviewed += 1;
    var status = String(row.candidate_status || '').trim();
    if (status === 'strong_candidate') g.strong_candidate_count += 1;
    else if (status === 'medium_candidate') g.medium_candidate_count += 1;
    else if (status === 'weak_candidate') g.weak_candidate_count += 1;
    else if (status === 'rejected') g.rejected_count += 1;
    else g.inconclusive_count += 1;

    var effectDirection = String(row.effect_direction || '').trim();
    var score = _characterSignalCandidateNum_(row.validation_score_delta, row.discovery_score_delta, row.recurrence_score);
    if (effectDirection === 'positive') g.positives.push({ trait: row.trait, score: score });
    if (effectDirection === 'negative') g.negatives.push({ trait: row.trait, score: score });
    if (String(row.recommended_future_use || '') === 'reliability_signal_test') g.reliability.push({ trait: row.trait, score: row.recurrence_score });
    if (String(row.recommended_future_use || '') === 'shadow_calibration_test') g.calibration.push({ trait: row.trait, score: score });
  }

  var providerSummaryRows = _characterSignalCandidateIndexRows_(sources.providerSummaryBundle, ['provider']);

  var out = [];
  Object.keys(byProvider).sort().forEach(function(provider) {
    var g = byProvider[provider];
    var providerSummary = providerSummaryRows[provider] || null;
    out.push({
      generated_ts: generatedTs,
      provider: provider,
      total_traits_reviewed: g.total_traits_reviewed,
      strong_candidate_count: g.strong_candidate_count,
      medium_candidate_count: g.medium_candidate_count,
      weak_candidate_count: g.weak_candidate_count,
      rejected_count: g.rejected_count,
      inconclusive_count: g.inconclusive_count,
      top_positive_candidates: _characterSignalCandidateTopTraitText_(g.positives, 5, true),
      top_negative_candidates: _characterSignalCandidateTopTraitText_(g.negatives, 5, false),
      strongest_reliability_candidates: _characterSignalCandidateTopTraitText_(g.reliability, 5, true),
      strongest_calibration_candidates: _characterSignalCandidateTopTraitText_(g.calibration, 5, true),
      provider_signal_profile_note: _characterSignalCandidateProviderNote_(providerSummary, g)
    });
  });

  return out;
}

function _characterSignalCandidateBuildFamilyMapRows_(generatedTs, rows, sources, warnings) {
  var familyLinkRows = _characterSignalCandidateIndexRows_(sources.familyLinkBundle, ['provider', 'trait'], true);
  var recurrenceFamilyRows = _characterSignalCandidateIndexRows_(sources.recurrenceFamilyBundle, ['provider', 'outcome_family']);

  var out = [];
  var seen = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var provider = String(row.provider || '').trim();
    var trait = String(row.trait || '').trim();
    if (!provider || !trait) continue;
    var key = provider + '|' + trait;
    var families = familyLinkRows[key] || [];
    for (var j = 0; j < families.length; j++) {
      var fam = families[j] || {};
      var family = String(fam.outcome_family || '').trim() || 'other';
      var famKey = key + '|' + family;
      if (seen[famKey]) continue;
      seen[famKey] = true;

      var recurrenceFamily = recurrenceFamilyRows[provider + '|' + family] || null;
      var familySampleSize = Number(fam.sample_size || 0);
      var familyScoreDelta = _characterSignalCandidateNum_(fam.score_delta, fam.overall_delta, fam.avg_outcome_score);
      var familyEffectDirection = _characterSignalCandidateEffectDirection_(familyScoreDelta, null, fam.classification || '');
      var familyRecurrenceStrength = String(recurrenceFamily && recurrenceFamily.recurrence_classification || '').trim() || 'inconclusive';
      var familyConfidence = _characterSignalCandidateFamilyConfidence_(familySampleSize, familyRecurrenceStrength, fam.confidence);
      var familyUsefulnessNote = _characterSignalCandidateFamilyUsefulnessNote_(row, fam, recurrenceFamily, familyEffectDirection);
      var sampleDepthWarning = _characterSignalCandidateFamilyDepthWarning_(familySampleSize, recurrenceFamily);
      out.push({
        generated_ts: generatedTs,
        provider: provider,
        trait: trait,
        outcome_family: family,
        family_sample_size: familySampleSize,
        family_effect_direction: familyEffectDirection,
        family_score_delta: familyScoreDelta == null ? '' : _round4_(familyScoreDelta),
        family_recurrence_strength: familyRecurrenceStrength,
        family_confidence: familyConfidence,
        family_usefulness_note: familyUsefulnessNote,
        sample_depth_warning: sampleDepthWarning
      });
    }
  }

  out.sort(function(a, b) {
    var ap = String(a.provider || '');
    var bp = String(b.provider || '');
    if (ap !== bp) return ap.localeCompare(bp);
    var at = String(a.trait || '');
    var bt = String(b.trait || '');
    if (at !== bt) return at.localeCompare(bt);
    return String(a.outcome_family || '').localeCompare(String(b.outcome_family || ''));
  });

  return out;
}

function _characterSignalCandidateBuildReadinessRows_(generatedTs, rows) {
  var out = [];
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var status = String(row.candidate_status || '').trim();
    var recurrenceEvidence = _characterSignalCandidateEvidenceText_('recurrence', row.recurrence_classification, row.recurrence_score, row.sample_size_discovery, row.sample_size_validation);
    var outcomeEvidence = _characterSignalCandidateEvidenceText_('outcome', row.outcome_link_status, row.discovery_score_delta, row.validation_score_delta, '');
    var falsificationEvidence = _characterSignalCandidateEvidenceText_('falsification', row.falsification_status, row.exclusion_reason, row.confidence_level, '');
    var driftEvidence = _characterSignalCandidateEvidenceText_('drift', row.drift_status, row.profile_similarity_score, row.sample_depth_warning, '');
    var sampleEvidence = _characterSignalCandidateEvidenceText_('sample', row.sample_size_total, row.sample_size_discovery, row.sample_size_validation, row.sample_depth_warning);
    var readiness = _characterSignalCandidateReadinessClass_(status, row);
    var calibrationReadiness = _characterSignalCandidateReadinessLevel_(status, row, 'calibration');
    var reliabilityReadiness = _characterSignalCandidateReadinessLevel_(status, row, 'reliability');
    var nextTest = _characterSignalCandidateNextTest_(readiness, row);
    out.push({
      generated_ts: generatedTs,
      provider: row.provider || '',
      trait: row.trait || '',
      candidate_status: status,
      recurrence_evidence: recurrenceEvidence,
      outcome_evidence: outcomeEvidence,
      falsification_evidence: falsificationEvidence,
      drift_evidence: driftEvidence,
      sample_depth_evidence: sampleEvidence,
      readiness_classification: readiness,
      calibration_readiness: calibrationReadiness,
      reliability_readiness: reliabilityReadiness,
      next_test_recommendation: nextTest,
      final_note: _characterSignalCandidateFinalNote_(row, readiness, nextTest)
    });
  }

  out.sort(function(a, b) {
    var ap = String(a.provider || '');
    var bp = String(b.provider || '');
    if (ap !== bp) return ap.localeCompare(bp);
    return String(a.trait || '').localeCompare(String(b.trait || ''));
  });
  return out;
}

function _characterSignalCandidateAssess_(evidence) {
  var provider = String(evidence.provider || '').trim();
  var trait = String(evidence.trait || '').trim();
  var recurrenceClassification = String(evidence.recurrenceClassification || '').trim();
  var falsificationStatus = String(evidence.falsificationStatus || '').trim();
  var driftStatus = String(evidence.driftStatus || '').trim();
  var outcomeLinkStatus = String(evidence.outcomeLinkStatus || '').trim();
  var proxyResult = String(evidence.proxyResult || '').trim();
  var sampleTotal = Number(evidence.sampleSizeTotal || 0);
  var sampleDiscovery = Number(evidence.sampleSizeDiscovery || 0);
  var sampleValidation = Number(evidence.sampleSizeValidation || 0);
  var effectDirection = String(evidence.effectDirection || '').trim();
  var effectSizeStability = _characterSignalCandidateNum_(evidence.effectSizeStability, '');
  var recurrenceScore = _characterSignalCandidateNum_(evidence.recurrenceScore, '');
  var profileSimilarityScore = _characterSignalCandidateNum_(evidence.profileSimilarityScore, '');
  var sampleDepthWarning = String(evidence.sampleDepthWarning || '').trim();

  var reasons = [];
  var candidateStatus = 'inconclusive';
  var recommendedFutureUse = 'monitor_only';
  var confidenceLevel = 'low';

  var recurrenceGood = _characterSignalCandidateIsStrongOrModerate_(recurrenceClassification);
  var recurrenceExists = recurrenceGood || recurrenceClassification === 'weak_recurrence';
  var falsificationGood = falsificationStatus === 'survived' || falsificationStatus === 'partially_survived';
  var driftStable = driftStatus === 'stable' || driftStatus === 'mild_drift';
  var driftContaminated = driftStatus === 'drift_contaminated' || driftStatus === 'severe_drift';
  var outcomePromising = _characterSignalCandidateIsPositiveOrNegative_(outcomeLinkStatus);
  var effectStable = effectSizeStability == null ? false : effectSizeStability >= 0.65;
  var hasValidationSample = sampleValidation != null && sampleValidation > 0;
  var enoughSample = sampleTotal >= 20 && sampleDiscovery >= 10 && (!hasValidationSample || sampleValidation >= 10);
  var tooThin = sampleTotal < 10 || sampleDiscovery < 10 || (hasValidationSample && sampleValidation < 10);
  var proxyDominant = proxyResult === 'proxy_dominant';
  var effectClear = effectDirection === 'positive' || effectDirection === 'negative';

  if (tooThin) reasons.push('thin_sample');
  if (proxyDominant) reasons.push('proxy_dominant');
  if (driftContaminated) reasons.push('drift_contaminated');
  if (falsificationStatus === 'failed') reasons.push('falsification_failed');
  if (recurrenceClassification === 'failed_recurrence') reasons.push('recurrence_failed');
  if (effectDirection === 'mixed' || effectDirection === 'unknown') reasons.push('effect_direction_' + effectDirection);
  if (!outcomePromising) reasons.push('weak_outcome_support');

  if (tooThin || proxyDominant || driftContaminated || falsificationStatus === 'failed' || recurrenceClassification === 'failed_recurrence') {
    candidateStatus = 'rejected';
    recommendedFutureUse = 'reject_for_now';
  } else if (recurrenceGood && falsificationGood && driftStable && effectStable && enoughSample && outcomePromising && effectClear) {
    candidateStatus = 'strong_candidate';
    recommendedFutureUse = _characterSignalCandidateRecommendedUse_(true, driftStable, outcomePromising, effectDirection);
  } else if (recurrenceExists && falsificationGood && (driftStable || driftStatus === 'inconclusive') && (enoughSample || sampleTotal >= 10)) {
    candidateStatus = 'medium_candidate';
    recommendedFutureUse = _characterSignalCandidateRecommendedUse_(false, driftStable, outcomePromising, effectDirection);
  } else if (recurrenceExists) {
    candidateStatus = 'weak_candidate';
    recommendedFutureUse = 'monitor_only';
  } else if (falsificationGood || outcomePromising) {
    candidateStatus = 'inconclusive';
    recommendedFutureUse = 'monitor_only';
  } else {
    candidateStatus = 'rejected';
    recommendedFutureUse = 'reject_for_now';
  }

  if (candidateStatus === 'strong_candidate') {
    confidenceLevel = sampleTotal >= 40 && driftStable ? 'high' : 'medium';
  } else if (candidateStatus === 'medium_candidate') {
    confidenceLevel = sampleTotal >= 20 ? 'medium' : 'low';
  } else if (candidateStatus === 'weak_candidate') {
    confidenceLevel = 'low';
  } else if (candidateStatus === 'rejected') {
    confidenceLevel = tooThin ? 'low' : 'medium';
  } else {
    confidenceLevel = 'low';
  }

  if (candidateStatus === 'strong_candidate' && proxyDominant) {
    candidateStatus = 'rejected';
    recommendedFutureUse = 'reject_for_now';
    confidenceLevel = 'low';
    reasons.push('proxy_dominant');
  }

  if (candidateStatus === 'strong_candidate' && !effectStable) {
    reasons.push('effect_not_stable');
  }
  if (candidateStatus === 'strong_candidate' && !driftStable) {
    reasons.push('drift_not_stable');
  }
  if (candidateStatus === 'strong_candidate' && !enoughSample) {
    reasons.push('sample_depth_not_deep');
  }
  if (candidateStatus === 'medium_candidate' && !effectStable) {
    reasons.push('effect_partial');
  }
  if (candidateStatus === 'weak_candidate' && !falsificationGood) {
    reasons.push('falsification_only_partial');
  }
  if (candidateStatus === 'inconclusive' && !recurrenceExists) {
    reasons.push('insufficient_evidence');
  }

  var exclusionReason = candidateStatus === 'rejected' ? _uniqueStrings_(reasons).join('|') : '';
  var notes = [
    'functional_layer=Character Signal Candidate Layer',
    'source_layers=Character Residual Layer|Character Recurrence Layer|Character Outcome Layer|Character Falsification Layer|Character Drift Layer',
    'provider=' + provider,
    'trait=' + trait,
    'recurrence_score=' + (recurrenceScore == null ? '' : _round4_(recurrenceScore)),
    'profile_similarity=' + (profileSimilarityScore == null ? '' : _round4_(profileSimilarityScore))
  ];
  if (sampleDepthWarning) notes.push('sample_depth_warning=' + sampleDepthWarning);

  return {
    candidate_status: candidateStatus,
    recommended_future_use: recommendedFutureUse,
    confidence_level: confidenceLevel,
    exclusion_reason: exclusionReason,
    notes: notes.join('; ')
  };
}

function _characterSignalCandidateRecommendedUse_(strongCandidate, driftStable, outcomePromising, effectDirection) {
  var strong = !!strongCandidate;
  var driftOk = !!driftStable;
  var outcomeOk = !!outcomePromising;
  var direction = String(effectDirection || '').trim();
  if (strong && driftOk && outcomeOk && (direction === 'positive' || direction === 'negative')) return 'shadow_calibration_test';
  if ((strong || driftOk) && (outcomeOk || direction === 'neutral')) return 'reliability_signal_test';
  return 'monitor_only';
}

function _characterSignalCandidateReadinessClass_(candidateStatus, row) {
  var status = String(candidateStatus || '').trim();
  if (status === 'rejected') return 'reject_for_now';
  if (status === 'strong_candidate') {
    if (row && String(row.recommended_future_use || '') === 'shadow_calibration_test') return 'ready_for_shadow_calibration_test';
    return 'ready_for_reliability_test';
  }
  if (status === 'medium_candidate') {
    return 'ready_for_reliability_test';
  }
  if (status === 'weak_candidate') {
    return 'monitor_more_data';
  }
  return 'inconclusive';
}

function _characterSignalCandidateReadinessLevel_(candidateStatus, row, mode) {
  var status = String(candidateStatus || '').trim();
  var sampleTotal = Number(row.sample_size_total || 0);
  var driftStatus = String(row.drift_status || '').trim();
  var recurrenceClass = String(row.recurrence_classification || '').trim();
  var outcomeStatus = String(row.outcome_link_status || '').trim();
  var effectDirection = String(row.effect_direction || '').trim();
  var effectStable = _characterSignalCandidateNum_(row.effect_size_stability, '') != null && _characterSignalCandidateNum_(row.effect_size_stability, '') >= 0.65;

  if (mode === 'calibration') {
    if (status === 'strong_candidate' && sampleTotal >= 20 && effectStable && _characterSignalCandidateIsPositiveOrNegative_(outcomeStatus) && (effectDirection === 'positive' || effectDirection === 'negative')) return 'high';
    if (status === 'medium_candidate' || status === 'weak_candidate') return sampleTotal >= 20 ? 'medium' : 'low';
    return 'low';
  }

  if (mode === 'reliability') {
    if ((status === 'strong_candidate' || status === 'medium_candidate') && (driftStatus === 'stable' || driftStatus === 'mild_drift') && (recurrenceClass === 'strong_recurrence' || recurrenceClass === 'moderate_recurrence')) return 'high';
    if (status === 'weak_candidate' && sampleTotal >= 20) return 'medium';
    return 'low';
  }

  return 'low';
}

function _characterSignalCandidateNextTest_(readiness, row) {
  var r = String(readiness || '').trim();
  if (r === 'ready_for_shadow_calibration_test') return 'shadow_calibration_test';
  if (r === 'ready_for_reliability_test') return 'reliability_signal_test';
  if (r === 'monitor_more_data') return 'monitor_only';
  if (r === 'reject_for_now') return 'reject_for_now';
  return 'monitor_only';
}

function _characterSignalCandidateFinalNote_(row, readiness, nextTest) {
  var parts = [
    'candidate=' + String(row.candidate_status || ''),
    'readiness=' + String(readiness || ''),
    'next_test=' + String(nextTest || '')
  ];
  if (String(row.exclusion_reason || '').trim()) parts.push('exclusion_reason=' + String(row.exclusion_reason || ''));
  if (String(row.sample_depth_warning || '').trim()) parts.push('sample_depth_warning=' + String(row.sample_depth_warning || ''));
  return parts.join('; ');
}

function _characterSignalCandidateSignalFamily_(traitDomain) {
  var domain = String(traitDomain || '').trim();
  if (domain === 'risk_language') return 'risk_language_signal';
  if (domain === 'uncertainty_pattern') return 'uncertainty_pattern_signal';
  if (domain === 'direction_delta_from_baseline') return 'direction_tendency_signal';
  if (domain === 'emphasized_factor') return 'factor_attention_signal';
  if (domain === 'rationale_style_tag') return 'reasoning_style_signal';
  return 'unknown_signal';
}

function _characterSignalCandidateTraitDomains_(trait) {
  if (typeof _characterOutcomeRecurrenceInferTraitDomains_ === 'function') {
    return _characterOutcomeRecurrenceInferTraitDomains_(trait);
  }
  var name = String(trait || '').trim().toLowerCase();
  var domains = {};
  if (['low_risk_language', 'normal_risk_language', 'high_risk_language', 'tail_risk_language', 'hidden_detail_risk_language', 'crowded_trade_language', 'uncertainty_language'].indexOf(name) >= 0) domains.risk_language = true;
  if (['confident', 'cautious', 'hedged', 'scenario_based', 'low_signal', 'mixed_signal', 'unknown'].indexOf(name) >= 0) domains.uncertainty_pattern = true;
  if (['same_direction', 'provider_more_positive', 'provider_more_negative', 'provider_flat_vs_directional', 'provider_directional_vs_flat'].indexOf(name) >= 0) domains.direction_delta_from_baseline = true;
  if (!Object.keys(domains).length) domains.emphasized_factor = true;
  return domains;
}

function _characterSignalCandidatePrimaryTraitDomain_(domains) {
  if (typeof _characterOutcomeRecurrencePrimaryTraitDomain_ === 'function') {
    return _characterOutcomeRecurrencePrimaryTraitDomain_(domains);
  }
  var keys = Object.keys(domains || {});
  if (!keys.length) return 'emphasized_factor';
  if (keys.indexOf('risk_language') >= 0) return 'risk_language';
  if (keys.indexOf('uncertainty_pattern') >= 0) return 'uncertainty_pattern';
  if (keys.indexOf('direction_delta_from_baseline') >= 0) return 'direction_delta_from_baseline';
  return 'emphasized_factor';
}

function _characterSignalCandidateIndexRows_(bundle, fields, useArrayBucket) {
  var rows = _characterSignalCandidateBundleRowsToObjects_(bundle);
  var out = {};
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i] || {};
    var key = [];
    for (var f = 0; f < fields.length; f++) {
      key.push(String(row[fields[f]] || '').trim());
    }
    var joined = key.join('|');
    if (!joined || joined === '|') continue;
    if (useArrayBucket) {
      if (!out[joined]) out[joined] = [];
      out[joined].push(row);
    } else if (!out[joined]) {
      out[joined] = row;
    }
  }
  return out;
}

function _characterSignalCandidateBundleRowsToObjects_(bundle) {
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

function _characterSignalCandidateText_() {
  for (var i = 0; i < arguments.length; i++) {
    var value = arguments[i];
    var text = String(value == null ? '' : value).trim();
    if (text) return text;
  }
  return '';
}

function _characterSignalCandidateNum_() {
  for (var i = 0; i < arguments.length; i++) {
    var value = arguments[i];
    var n = _characterResidualNum_(value);
    if (n != null) return n;
  }
  return null;
}

function _characterSignalCandidateEffectDirection_(discoveryDelta, validationDelta, fallbackText) {
  var a = _characterSignalCandidateNum_(discoveryDelta, '');
  var b = _characterSignalCandidateNum_(validationDelta, '');
  if (a == null && b == null) {
    var fallback = String(fallbackText || '').trim().toLowerCase();
    if (fallback.indexOf('positive') >= 0) return 'positive';
    if (fallback.indexOf('negative') >= 0) return 'negative';
    if (fallback.indexOf('neutral') >= 0) return 'neutral';
    return 'unknown';
  }
  var signs = [];
  if (a != null) signs.push(_characterSignalCandidateSign_(a));
  if (b != null) signs.push(_characterSignalCandidateSign_(b));
  var hasPos = false;
  var hasNeg = false;
  var hasZero = false;
  for (var i = 0; i < signs.length; i++) {
    if (signs[i] > 0) hasPos = true;
    else if (signs[i] < 0) hasNeg = true;
    else hasZero = true;
  }
  if (hasPos && hasNeg) return 'mixed';
  if (hasPos) return 'positive';
  if (hasNeg) return 'negative';
  if (hasZero) return 'neutral';
  return 'unknown';
}

function _characterSignalCandidateSign_(value) {
  var v = Number(value || 0);
  if (Math.abs(v) < 0.0001) return 0;
  return v > 0 ? 1 : -1;
}

function _characterSignalCandidateIsStrongOrModerate_(classification) {
  var c = String(classification || '').trim().toLowerCase();
  return c === 'strong_recurrence' || c === 'moderate_recurrence';
}

function _characterSignalCandidateIsPositiveOrNegative_(classification) {
  var c = String(classification || '').trim().toLowerCase();
  return c.indexOf('positive') >= 0 || c.indexOf('negative') >= 0;
}

function _characterSignalCandidateRankBucket_(candidateStatus) {
  var s = String(candidateStatus || '').trim().toLowerCase();
  if (s === 'strong_candidate') return 0;
  if (s === 'medium_candidate') return 1;
  if (s === 'weak_candidate') return 2;
  if (s === 'inconclusive') return 3;
  return 4;
}

function _characterSignalCandidateSampleDepthWarning_(sampleDiscovery, sampleValidation, outcomeRow, recurrenceRow, falsificationRow, driftStatus, proxyResult) {
  var notes = [];
  if (Number(sampleDiscovery || 0) < 20) notes.push('discovery_thin_sample');
  if (Number(sampleValidation || 0) < 20 && Number(sampleValidation || 0) > 0) notes.push('validation_thin_sample');
  if (Number(sampleDiscovery || 0) + Number(sampleValidation || 0) < 20) notes.push('total_thin_sample');
  if (!outcomeRow) notes.push('missing_outcome_link');
  if (!recurrenceRow) notes.push('missing_recurrence_validation');
  if (!falsificationRow) notes.push('missing_falsification_report');
  if (driftStatus === 'inconclusive') notes.push('drift_inconclusive');
  if (proxyResult === 'proxy_dominant') notes.push('proxy_dominant');
  return _uniqueStrings_(notes).join('|');
}

function _characterSignalCandidateFamilyConfidence_(sampleSize, recurrenceStrength, fallbackConfidence) {
  var score = Number(sampleSize || 0);
  var rec = String(recurrenceStrength || '').trim().toLowerCase();
  if (score >= 20 && rec === 'strong_recurrence') return 'high';
  if (score >= 10 && (rec === 'strong_recurrence' || rec === 'moderate_recurrence' || rec === 'weak_recurrence')) return 'medium';
  if (String(fallbackConfidence || '').trim().toLowerCase() === 'high') return 'medium';
  return 'low';
}

function _characterSignalCandidateFamilyUsefulnessNote_(candidateRow, familyRow, recurrenceFamilyRow, familyEffectDirection) {
  var notes = [];
  var candidateEffect = String(candidateRow.effect_direction || '').trim();
  var familyClass = String(familyRow.classification || '').trim();
  var recurrence = String(recurrenceFamilyRow && recurrenceFamilyRow.recurrence_classification || '').trim();
  if (familyEffectDirection === candidateEffect && candidateEffect && candidateEffect !== 'unknown') notes.push('family_supports_candidate');
  if (familyClass.indexOf('thin_sample') >= 0) notes.push('family_thin_sample');
  if (recurrence === 'strong_recurrence' || recurrence === 'moderate_recurrence') notes.push('stable_family_context');
  if (!notes.length) notes.push('family_context_mixed');
  return notes.join('|');
}

function _characterSignalCandidateFamilyDepthWarning_(familySampleSize, recurrenceFamilyRow) {
  var notes = [];
  if (Number(familySampleSize || 0) < 20) notes.push('family_thin_sample');
  if (!recurrenceFamilyRow) notes.push('missing_family_recurrence');
  return notes.join('|');
}

function _characterSignalCandidateProviderNote_(providerSummaryRow, counts) {
  var parts = [];
  if (providerSummaryRow) {
    parts.push('dominant_risk=' + String(providerSummaryRow.dominant_risk_language || ''));
    parts.push('dominant_uncertainty=' + String(providerSummaryRow.dominant_uncertainty_pattern || ''));
    parts.push('stability=' + String(providerSummaryRow.character_stability_note || ''));
  } else {
    parts.push('provider_summary_missing');
  }
  parts.push('counts=' + [
    'strong=' + counts.strong_candidate_count,
    'medium=' + counts.medium_candidate_count,
    'weak=' + counts.weak_candidate_count,
    'rejected=' + counts.rejected_count,
    'inconclusive=' + counts.inconclusive_count
  ].join('|'));
  return parts.join('; ');
}

function _characterSignalCandidateTopTraitText_(items, limit, descending) {
  var list = (items || []).slice();
  list.sort(function(a, b) {
    var as = _characterSignalCandidateNum_(a.score, '');
    var bs = _characterSignalCandidateNum_(b.score, '');
    if (descending) return (bs || 0) - (as || 0);
    return (as || 0) - (bs || 0);
  });
  var out = [];
  for (var i = 0; i < list.length && i < (limit || 5); i++) {
    var item = list[i] || {};
    var score = _characterSignalCandidateNum_(item.score, '');
    out.push(String(item.trait || '') + '(' + (score == null ? '' : _round4_(score)) + ')');
  }
  return out.join('|');
}

function _characterSignalCandidateEvidenceText_(label, a, b, c, d) {
  var parts = [String(label || '')];
  var values = [a, b, c, d];
  for (var i = 0; i < values.length; i++) {
    var value = values[i];
    var text = String(value == null ? '' : value).trim();
    if (text) parts.push(text);
  }
  return parts.join('=');
}
