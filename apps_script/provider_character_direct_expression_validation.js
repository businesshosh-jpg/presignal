/*******************************************************
 * provider_character_direct_expression_validation.js
 * - Diagnostic-only Provider Character v2 - Direct Expression Validation v1
 * - Replays the first 30 eligible direct-expression rows through the same capture path
 * - Appends into the existing validation tab; no new tabs
 *******************************************************/

function menuBuildProviderCharacterDirectExpressionValidation_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterDirectExpressionValidation_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character direct expression validation -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'Rows=' + (res.validation_rows_written || 0) +
      ' | Success=' + (res.provider_calls_succeeded || 0) +
      ' | Failed=' + (res.provider_calls_failed || 0),
      'Provider Character Direct Expression Validation',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character direct expression validation -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterDirectExpressionValidation_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var validationRunId = String(params.validation_run_id || '').trim() || 'same_path_validation_v1';
  var validationMode = String(params.validation_mode || '').trim() || 'same_capture_path_rerun';
  var validationCaptureRunId = String(params.validation_capture_run_id || '').trim() || _uuidFromString_('provider_character_direct_expression_validation_capture:' + generatedTs + ':' + validationRunId);
  var warnings = [];
  var targetCount = 30;
  var batchStart = _numOrNull_(params.batch_start);
  if (batchStart == null || batchStart < 0) batchStart = 0;
  var batchSize = _numOrNull_(params.batch_size);
  if (batchSize == null || batchSize <= 0) batchSize = targetCount;
  var writeOutput = params.write_output !== false;

  try {
    var captureBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false);
    if (!captureBundle) {
      throw new Error('Validation requires Provider_Character_Direct_Expression_Capture.');
    }
    var eventBundle = _characterResidualReadSheetBundle_('Event', warnings, true);
    if (!eventBundle) {
      throw new Error('Validation requires Event sheet access.');
    }

    var captureRows = _providerCharacterMicroExpressionBundleRowsToObjects_(captureBundle);
    var eventRows = _providerCharacterMicroExpressionBundleRowsToObjects_(eventBundle);
    var eventMap = _providerCharacterDirectExpressionValidationBuildEventMap_(eventRows);
    var providers = _resolveProviders_(['Anthropic', 'Gemini', 'OpenAI']);
    if (!providers.length) {
      throw new Error('Validation requires at least one enabled provider.');
    }
    var providerMap = {};
    for (var p = 0; p < providers.length; p++) providerMap[providers[p].name] = providers[p];

    var selected = _providerCharacterDirectExpressionValidationSelectRows_(
      captureRows,
      eventMap,
      targetCount,
      warnings
    );
    if (selected.length < targetCount) {
      throw new Error('Validation expected at least ' + targetCount + ' eligible source rows, got ' + selected.length);
    }
    selected = selected.slice(batchStart, batchStart + batchSize);
    if (!selected.length) {
      throw new Error('Validation batch window empty for batch_start=' + batchStart + ' batch_size=' + batchSize);
    }

    var validationRows = [];
    var attempted = 0;
    var succeeded = 0;
    var failed = 0;
    var similarityTotals = [];
    var forecastDeltas = [];
    var providerStats = {};

    for (var i = 0; i < selected.length; i++) {
      var source = selected[i] || {};
      var row = source.row || {};
      var sourceRowNumber = Number(source.source_capture_row_number || 0);
      var providerName = String(row.provider || '').trim();
      var provider = providerMap[providerName];
      if (!provider) {
        throw new Error('Provider not enabled for validation: ' + providerName);
      }

      var eventId = String(row.event_id || '').trim();
      var eventMeta = eventMap[eventId] || null;
      if (!eventMeta) {
        warnings.push('missing_event_for_validation:' + eventId);
      }

      var promptEvent = _providerCharacterDirectExpressionValidationBuildPromptEvent_(row, eventMeta);
      var startMs = Date.now();
      var captureCall = _providerCharacterDirectExpressionValidationRunSamePathCapture_(provider, promptEvent, eventId, warnings);
      var latencyMs = captureCall.latency_ms == null ? (Date.now() - startMs) : captureCall.latency_ms;
      var providerResp = captureCall.providerResp || {
        parsed: {},
        raw_output: '',
        prompt_tokens: null,
        completion_tokens: null
      };
      var callStatus = String(captureCall.call_status || 'failed').trim().toLowerCase();
      var callError = String(captureCall.call_error || '').trim();
      var normalized = _providerCharacterDirectExpressionCaptureNormalizeProviderOutput_(providerResp.parsed || {}, providerResp.raw_output || '');
      attempted += 1;
      if (callStatus === 'success') succeeded += 1;
      else failed += 1;
      var rowResult = _providerCharacterDirectExpressionValidationBuildRow_(
        generatedTs,
        validationRunId,
        validationMode,
        validationCaptureRunId,
        sourceRowNumber,
        row,
        promptEvent,
        normalized,
        providerResp,
        callStatus,
        callError,
        latencyMs,
        warnings
      );

      if (rowResult.validation_call_status !== 'failed') {
        if (rowResult.overall_expression_similarity !== '') similarityTotals.push(Number(rowResult.overall_expression_similarity || 0));
        if (rowResult.forecast_value_delta !== '') forecastDeltas.push(Number(rowResult.forecast_value_delta || 0));
        var providerKey = providerName || 'UNKNOWN';
        if (!providerStats[providerKey]) {
          providerStats[providerKey] = {
            rows: 0,
            successes: 0,
            failures: 0,
            high_reproducibility: 0,
            medium_reproducibility: 0,
            low_reproducibility: 0,
            forecast_stable_expression_unstable: 0,
            forecast_unstable_expression_stable: 0,
            rerun_failed: 0,
            similarity_sum: 0,
            similarity_count: 0,
            forecast_delta_sum: 0,
            forecast_delta_count: 0
          };
        }
        var ps = providerStats[providerKey];
        ps.rows += 1;
        ps.successes += 1;
        if (rowResult.reproducibility_result === 'high_reproducibility') ps.high_reproducibility += 1;
        else if (rowResult.reproducibility_result === 'medium_reproducibility') ps.medium_reproducibility += 1;
        else if (rowResult.reproducibility_result === 'low_reproducibility') ps.low_reproducibility += 1;
        else if (rowResult.reproducibility_result === 'forecast_stable_expression_unstable') ps.forecast_stable_expression_unstable += 1;
        else if (rowResult.reproducibility_result === 'forecast_unstable_expression_stable') ps.forecast_unstable_expression_stable += 1;
        else if (rowResult.reproducibility_result === 'rerun_failed') ps.rerun_failed += 1;
        if (rowResult.overall_expression_similarity !== '') {
          ps.similarity_sum += Number(rowResult.overall_expression_similarity || 0);
          ps.similarity_count += 1;
        }
        if (rowResult.forecast_value_delta !== '') {
          ps.forecast_delta_sum += Number(rowResult.forecast_value_delta || 0);
          ps.forecast_delta_count += 1;
        }
      } else {
        failed += 1;
        var pkey = providerName || 'UNKNOWN';
        if (!providerStats[pkey]) {
          providerStats[pkey] = {
            rows: 0,
            successes: 0,
            failures: 0,
            high_reproducibility: 0,
            medium_reproducibility: 0,
            low_reproducibility: 0,
            forecast_stable_expression_unstable: 0,
            forecast_unstable_expression_stable: 0,
            rerun_failed: 0,
            similarity_sum: 0,
            similarity_count: 0,
            forecast_delta_sum: 0,
            forecast_delta_count: 0
          };
        }
        providerStats[pkey].rows += 1;
        providerStats[pkey].failures += 1;
        providerStats[pkey].rerun_failed += 1;
      }

      validationRows.push(rowResult);
    }

    var sheetHeaders = _providerCharacterDirectExpressionValidationHeaders_();
    var validationSheet = null;
    var appendedCount = 0;
    if (writeOutput) {
      validationSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Validation', sheetHeaders, warnings);
      var appendRows = _characterResidualObjectsToRows_(validationRows, validationSheet.headers);
      var appendResult = _appendDedupedRowsByKey_(
        validationSheet.sheet,
        validationSheet.headers,
        appendRows,
        _providerCharacterDirectExpressionValidationRowKey_
      );
      appendedCount = Number(appendResult && appendResult.appended_count || 0);
    }

    var result = {
      status: 'ok',
      generated_ts: generatedTs,
      validation_run_id: validationRunId,
      validation_mode: validationMode,
      validation_capture_run_id: validationCaptureRunId,
      validation_sheet: validationSheet ? validationSheet.sheet.getName() : 'Provider_Character_Direct_Expression_Validation',
      source_rows_selected: validationRows.length,
      validation_rows_written: appendedCount || validationRows.length,
      provider_calls_attempted: attempted,
      provider_calls_succeeded: succeeded,
      provider_calls_failed: failed,
      high_reproducibility_count: _providerCharacterDirectExpressionValidationCountResult_(validationRows, 'high_reproducibility'),
      medium_reproducibility_count: _providerCharacterDirectExpressionValidationCountResult_(validationRows, 'medium_reproducibility'),
      low_reproducibility_count: _providerCharacterDirectExpressionValidationCountResult_(validationRows, 'low_reproducibility'),
      forecast_stable_expression_unstable_count: _providerCharacterDirectExpressionValidationCountResult_(validationRows, 'forecast_stable_expression_unstable'),
      forecast_unstable_expression_stable_count: _providerCharacterDirectExpressionValidationCountResult_(validationRows, 'forecast_unstable_expression_stable'),
      rerun_failed_count: _providerCharacterDirectExpressionValidationCountResult_(validationRows, 'rerun_failed'),
      validation_failed_count: _providerCharacterDirectExpressionValidationCountResult_(validationRows, 'validation_failed'),
      average_overall_expression_similarity: _providerCharacterDirectExpressionValidationAverage_(similarityTotals),
      average_forecast_value_delta: _providerCharacterDirectExpressionValidationAverage_(forecastDeltas),
      provider_stats: _providerCharacterDirectExpressionValidationProviderStats_(providerStats),
      warnings: _uniqueStrings_(warnings)
    };
    return result;
  } catch (e) {
    return {
      status: 'error',
      generated_ts: generatedTs,
      validation_run_id: validationRunId,
      error_message: (e && e.stack) ? e.stack : String(e),
      warnings: _uniqueStrings_(warnings)
    };
  }
}

function buildProviderCharacterDirectExpressionValidation(params) {
  return buildProviderCharacterDirectExpressionValidation_(params || {});
}

function menuBuildProviderCharacterDirectExpressionMicrocohortRerun_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildProviderCharacterDirectExpressionMicrocohortRerun_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Provider character direct expression microcohort rerun -> Build sheet', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    ss.toast(
      'New reruns=' + (res.new_provider_calls_made || 0) +
      ' | Success=' + (res.new_provider_calls_succeeded || 0) +
      ' | Failed=' + (res.new_provider_calls_failed || 0),
      'Direct Expression Microcohort',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Provider character direct expression microcohort rerun -> Build sheet failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function buildProviderCharacterDirectExpressionMicrocohortRerun_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var validationRunId = String(params.validation_run_id || '').trim() || 'microcohort_rerun_v1';
  var validationMode = String(params.validation_mode || '').trim() || 'microcohort_same_capture_path_rerun';
  var warnings = [];
  var rerunCount = 4;
  var writeOutput = params.write_output !== false;

  try {
    var captureBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false);
    if (!captureBundle) throw new Error('Microcohort rerun requires Provider_Character_Direct_Expression_Capture.');
    var eventBundle = _characterResidualReadSheetBundle_('Event', warnings, true);
    if (!eventBundle) throw new Error('Microcohort rerun requires Event sheet access.');

    var captureRows = _providerCharacterMicroExpressionBundleRowsToObjects_(captureBundle);
    var eventRows = _providerCharacterMicroExpressionBundleRowsToObjects_(eventBundle);
    var eventMap = _providerCharacterDirectExpressionValidationBuildEventMap_(eventRows);
    var providers = _resolveProviders_(['Anthropic', 'Gemini', 'OpenAI']);
    if (!providers.length) throw new Error('Microcohort rerun requires at least one enabled provider.');
    var providerMap = {};
    for (var p = 0; p < providers.length; p++) providerMap[providers[p].name] = providers[p];

    var selected = _providerCharacterDirectExpressionValidationSelectRows_(captureRows, eventMap, 30, warnings);
    if (!selected.length) throw new Error('Microcohort rerun found no eligible source rows.');

    var requestedSourceRowNumber = _numOrNull_(params.source_capture_row_number);
    var source = null;
    if (requestedSourceRowNumber != null) {
      for (var s = 0; s < captureRows.length; s++) {
        var candidate = captureRows[s] || {};
        var candidateRowNumber = s + 2;
        if (Number(candidateRowNumber || 0) !== Number(requestedSourceRowNumber)) continue;
        if (!_providerCharacterDirectExpressionValidationIsEligibleRow_(candidate)) continue;
        var candidateEventId = String(candidate.event_id || '').trim();
        if (!candidateEventId || !eventMap[candidateEventId]) continue;
        source = {
          source_capture_row_number: candidateRowNumber,
          row: candidate
        };
        break;
      }
      if (!source) {
        for (var ss = 0; ss < selected.length; ss++) {
          if (Number(selected[ss].source_capture_row_number || 0) === Number(requestedSourceRowNumber)) {
            source = selected[ss];
            break;
          }
        }
      }
      if (!source) throw new Error('Requested source_capture_row_number not eligible: ' + requestedSourceRowNumber);
    } else {
      source = selected[0];
    }

    var sourceRow = source.row || {};
    var sourceRowNumber = Number(source.source_capture_row_number || 0);
    var providerName = String(sourceRow.provider || '').trim();
    var provider = providerMap[providerName];
    if (!provider) throw new Error('Provider not enabled for microcohort rerun: ' + providerName);
    var eventId = String(sourceRow.event_id || '').trim();
    var eventMeta = eventMap[eventId] || null;
    var promptEvent = _providerCharacterDirectExpressionValidationBuildPromptEvent_(sourceRow, eventMeta);
    var payloadHash = _providerCharacterDirectExpressionValidationPayloadHash_(promptEvent);
    var sampleGroupId = String(params.sample_group_id || '').trim() || _providerCharacterDirectExpressionMicrocohortSampleGroupId_(eventId, providerName);

    var validationHeaders = _providerCharacterDirectExpressionValidationHeaders_();
    var validationSheet = null;
    var existingValidationRows = [];
    var existingValidationObjects = [];
    if (writeOutput) {
      validationSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Validation', validationHeaders, warnings);
      existingValidationRows = _providerCharacterDirectExpressionValidationReadExistingRows_(validationSheet.sheet, validationSheet.headers);
      existingValidationObjects = _providerCharacterDirectExpressionValidationRowsToObjects_(existingValidationRows, validationSheet.headers);
    }

    var newRows = [];
    var newCallsMade = 0;
    var newCallsSucceeded = 0;
    var newCallsFailed = 0;
    for (var rerunIndex = 1; rerunIndex <= rerunCount; rerunIndex++) {
      if (_providerCharacterDirectExpressionMicrocohortHasExistingRerun_(
        existingValidationObjects,
        validationRunId,
        validationMode,
        sampleGroupId,
        rerunIndex,
        sourceRowNumber,
        eventId,
        providerName
      )) {
        warnings.push('microcohort_rerun_exists:' + rerunIndex);
        continue;
      }

      var captureCall = _providerCharacterDirectExpressionValidationRunSamePathCapture_(provider, promptEvent, eventId, warnings);
      var providerResp = captureCall.providerResp || {
        parsed: {},
        raw_output: '',
        prompt_tokens: null,
        completion_tokens: null
      };
      var callStatus = String(captureCall.call_status || 'failed').trim().toLowerCase();
      var callError = String(captureCall.call_error || '').trim();
      var normalized = _providerCharacterDirectExpressionCaptureNormalizeProviderOutput_(providerResp.parsed || {}, providerResp.raw_output || '');
      newCallsMade += 1;
      if (callStatus === 'success') newCallsSucceeded += 1;
      else newCallsFailed += 1;

      newRows.push(_providerCharacterDirectExpressionValidationBuildRow_(
        generatedTs,
        validationRunId,
        validationMode,
        _uuidFromString_('microcohort:' + sampleGroupId + ':' + rerunIndex + ':' + generatedTs),
        sourceRowNumber,
        sourceRow,
        promptEvent,
        normalized,
        providerResp,
        callStatus,
        callError,
        captureCall.latency_ms,
        warnings,
        {
          sample_group_id: sampleGroupId,
          rerun_index: rerunIndex,
          payload_hash: payloadHash
        }
      ));
    }

    var insertedCount = 0;
    if (writeOutput && newRows.length) {
      var appendRows = _characterResidualObjectsToRows_(newRows, validationSheet.headers);
      var appendResult = _appendDedupedRowsByKey_(
        validationSheet.sheet,
        validationSheet.headers,
        appendRows,
        _providerCharacterDirectExpressionValidationRowKey_
      );
      insertedCount = Number(appendResult && appendResult.appended_count || 0);
      existingValidationRows = _providerCharacterDirectExpressionValidationReadExistingRows_(validationSheet.sheet, validationSheet.headers);
      existingValidationObjects = _providerCharacterDirectExpressionValidationRowsToObjects_(existingValidationRows, validationSheet.headers);
    }

    var summaryRow = _providerCharacterDirectExpressionMicrocohortBuildSummaryRow_(
      generatedTs,
      sampleGroupId,
      sourceRowNumber,
      sourceRow,
      promptEvent,
      payloadHash,
      validationRunId,
      validationMode,
      existingValidationObjects,
      warnings
    );

    var microSheet = null;
    if (writeOutput) {
      microSheet = getDiagnosticsSheet_('Provider_Character_Direct_Expression_Microcohort', _providerCharacterDirectExpressionMicrocohortHeaders_(), warnings);
      _upsertRowsByKey_(
        microSheet.sheet,
        microSheet.headers,
        _characterResidualObjectsToRows_([summaryRow], microSheet.headers),
        function(rowValues, idx) {
          return idx.sample_group_id != null ? rowValues[idx.sample_group_id] : '';
        }
      );
    }

    return {
      status: 'ok',
      generated_ts: generatedTs,
      validation_run_id: validationRunId,
      validation_mode: validationMode,
      source_capture_row_number: sourceRowNumber,
      event_id: eventId,
      provider: providerName,
      sample_group_id: sampleGroupId,
      new_provider_calls_made: newCallsMade,
      new_provider_calls_succeeded: newCallsSucceeded,
      new_provider_calls_failed: newCallsFailed,
      validation_rows_written: insertedCount,
      validation_sheet: validationSheet ? validationSheet.sheet.getName() : 'Provider_Character_Direct_Expression_Validation',
      microcohort_sheet: microSheet ? microSheet.sheet.getName() : 'Provider_Character_Direct_Expression_Microcohort',
      payload_identity_consistent: summaryRow.interpretation_label === 'PAYLOAD_IDENTITY_SUSPECT' ? 'FALSE' : 'TRUE',
      forecast_direction_concentration: summaryRow.forecast_direction_concentration,
      pattern_concentration_score: summaryRow.pattern_concentration_score,
      interpretation_label: summaryRow.interpretation_label,
      warnings: _uniqueStrings_(warnings)
    };
  } catch (e) {
    return {
      status: 'error',
      generated_ts: generatedTs,
      validation_run_id: validationRunId,
      validation_mode: validationMode,
      error_message: (e && e.stack) ? e.stack : String(e),
      warnings: _uniqueStrings_(warnings)
    };
  }
}

function buildProviderCharacterDirectExpressionMicrocohortRerun(params) {
  return buildProviderCharacterDirectExpressionMicrocohortRerun_(params || {});
}

function listProviderCharacterDirectExpressionMicrocohortEligibleRows(params) {
  return listProviderCharacterDirectExpressionMicrocohortEligibleRows_(params || {});
}

function listProviderCharacterDirectExpressionMicrocohortEligibleRows_(params) {
  params = params || {};
  var limit = _numOrNull_(params.limit);
  if (limit == null || limit <= 0) limit = 250;
  var snapshot = _providerCharacterDirectExpressionEligibilitySnapshot_({
    limit: limit,
    include_all_rows: false
  });
  var out = snapshot.preview_rows || [];

  return {
    status: 'ok',
    generated_ts: new Date().toISOString(),
    eligible_rows: out,
    eligible_row_count: Number(snapshot.eligible_rows || out.length),
    already_tested_row_count: Number(snapshot.already_tested_rows || 0),
    remaining_eligible_row_count: Number(snapshot.remaining_eligible_rows || 0),
    capture_workbook_type: String(snapshot.capture_workbook_type || ''),
    capture_spreadsheet_id: String(snapshot.capture_spreadsheet_id || ''),
    event_workbook_type: String(snapshot.event_workbook_type || ''),
    event_spreadsheet_id: String(snapshot.event_spreadsheet_id || ''),
    microcohort_workbook_type: String(snapshot.microcohort_workbook_type || ''),
    microcohort_spreadsheet_id: String(snapshot.microcohort_spreadsheet_id || ''),
    warnings: _uniqueStrings_(snapshot.warnings || [])
  };
}

function buildProviderCharacterDirectExpressionEligibilityAudit_(params) {
  params = params || {};
  var generatedTs = String(params.generated_ts || '').trim() || new Date().toISOString();
  var warnings = [];
  var writeOutput = params.write_output !== false;

  try {
    var snapshot = _providerCharacterDirectExpressionEligibilitySnapshot_({
      generated_ts: generatedTs,
      warnings: warnings,
      include_all_rows: true
    });
    var auditRows = snapshot.audit_rows || [];
    var summaryRows = _providerCharacterDirectExpressionEligibilitySummaryRows_(generatedTs, snapshot);

    var auditSheet = null;
    var summarySheet = null;
    if (writeOutput) {
      auditSheet = getDiagnosticsSheet_(
        'Provider_Character_Direct_Expression_Eligibility_Audit',
        _providerCharacterDirectExpressionEligibilityAuditHeaders_(),
        warnings
      );
      _rewriteSheetRowsPreservingHeaders_(
        auditSheet.sheet,
        auditSheet.headers,
        _characterResidualObjectsToRows_(auditRows, auditSheet.headers)
      );

      summarySheet = getDiagnosticsSheet_(
        'Provider_Character_Direct_Expression_Eligibility_Summary',
        _providerCharacterDirectExpressionEligibilitySummaryHeaders_(),
        warnings
      );
      _rewriteSheetRowsPreservingHeaders_(
        summarySheet.sheet,
        summarySheet.headers,
        _characterResidualObjectsToRows_(summaryRows, summarySheet.headers)
      );
    }

    return {
      status: 'ok',
      generated_ts: generatedTs,
      audit_sheet: auditSheet ? auditSheet.sheet.getName() : 'Provider_Character_Direct_Expression_Eligibility_Audit',
      summary_sheet: summarySheet ? summarySheet.sheet.getName() : 'Provider_Character_Direct_Expression_Eligibility_Summary',
      audit_rows_written: auditRows.length,
      summary_rows_written: summaryRows.length,
      total_capture_rows: Number(snapshot.total_capture_rows || 0),
      total_unique_events: Number(snapshot.total_unique_events || 0),
      eligible_rows: Number(snapshot.eligible_rows || 0),
      ineligible_rows: Number(snapshot.ineligible_rows || 0),
      already_tested_rows: Number(snapshot.already_tested_rows || 0),
      remaining_eligible_rows: Number(snapshot.remaining_eligible_rows || 0),
      rows_with_actuals: Number(snapshot.rows_with_actuals || 0),
      comparable_rows: Number(snapshot.comparable_rows || 0),
      capture_workbook_type: String(snapshot.capture_workbook_type || ''),
      capture_spreadsheet_id: String(snapshot.capture_spreadsheet_id || ''),
      event_workbook_type: String(snapshot.event_workbook_type || ''),
      event_spreadsheet_id: String(snapshot.event_spreadsheet_id || ''),
      microcohort_workbook_type: String(snapshot.microcohort_workbook_type || ''),
      microcohort_spreadsheet_id: String(snapshot.microcohort_spreadsheet_id || ''),
      warnings: _uniqueStrings_(warnings.concat(snapshot.warnings || []))
    };
  } catch (e) {
    return {
      status: 'error',
      generated_ts: generatedTs,
      error_message: (e && e.stack) ? e.stack : String(e),
      warnings: _uniqueStrings_(warnings)
    };
  }
}

function buildProviderCharacterDirectExpressionEligibilityAudit(params) {
  return buildProviderCharacterDirectExpressionEligibilityAudit_(params || {});
}

function _providerCharacterDirectExpressionEligibilitySnapshot_(params) {
  params = params || {};
  var warnings = params.warnings || [];
  var includeAllRows = params.include_all_rows !== false;
  var limit = _numOrNull_(params.limit);
  if (limit == null || limit <= 0) limit = 250;

  var captureBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Capture', warnings, false);
  if (!captureBundle) throw new Error('Eligibility audit requires Provider_Character_Direct_Expression_Capture.');
  var eventBundle = _characterResidualReadSheetBundle_('Event', warnings, true);
  if (!eventBundle) throw new Error('Eligibility audit requires Event sheet access.');
  var microBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Microcohort', warnings, false);
  if (!microBundle) throw new Error('Eligibility audit requires Provider_Character_Direct_Expression_Microcohort.');
  var outcomeBundle = _characterResidualReadSheetBundle_('Provider_Character_Direct_Expression_Outcome_Check', warnings, false);
  if (!outcomeBundle) throw new Error('Eligibility audit requires Provider_Character_Direct_Expression_Outcome_Check.');

  var captureRows = _providerCharacterMicroExpressionBundleRowsToObjects_(captureBundle);
  var eventRows = _providerCharacterMicroExpressionBundleRowsToObjects_(eventBundle);
  var microRows = _providerCharacterMicroExpressionBundleRowsToObjects_(microBundle);
  var outcomeRows = _providerCharacterMicroExpressionBundleRowsToObjects_(outcomeBundle);

  var eventMap = _providerCharacterDirectExpressionValidationBuildEventMap_(eventRows);
  var testedKeySet = _providerCharacterDirectExpressionEligibilityKeySet_(microRows);
  var outcomeKeySet = _providerCharacterDirectExpressionEligibilityKeySet_(outcomeRows);

  var auditRows = [];
  var previewRows = [];
  var uniqueEventMap = {};
  var providerStats = {};
  var familyStats = {};

  var totalCaptureRows = 0;
  var eligibleRows = 0;
  var ineligibleRows = 0;
  var alreadyTestedRows = 0;
  var remainingEligibleRows = 0;
  var rowsWithActuals = 0;
  var rowsWithoutActuals = 0;
  var comparableRows = 0;
  var noncomparableRows = 0;

  for (var i = 0; i < captureRows.length; i++) {
    var row = captureRows[i] || {};
    var sourceCaptureRowNumber = i + 2;
    totalCaptureRows += 1;

    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    var indicatorName = String(row.indicator_name || '').trim();
    var country = String(row.country || '').trim();
    var releaseTs = String(row.release_ts || '').trim();
    var providerCallStatus = String(row.provider_call_status || '').trim();
    var eventRow = eventMap[eventId] || null;
    var eventExistsInMain = !!eventRow;
    var expressionFieldCount = _providerCharacterDirectExpressionEligibilityExpressionFieldCount_(row);
    var eligibilityReason = _providerCharacterDirectExpressionEligibilityReason_(row, eventExistsInMain, expressionFieldCount);
    var microcohortEligible = !eligibilityReason;
    var key = _providerCharacterDirectExpressionEligibilityRowKey_(eventId, provider);
    var alreadyInMicrocohort = !!testedKeySet[key];
    var alreadyInOutcomeCheck = !!outcomeKeySet[key];
    var actualMeta = _providerCharacterDirectExpressionEligibilityActualMeta_(eventRow);
    var eventFamily = String(
      row.outcome_family ||
      (eventRow && (eventRow.outcome_family || eventRow.genre || eventRow.type)) ||
      ''
    ).trim();

    if (eventId) uniqueEventMap[eventId] = true;
    if (microcohortEligible) eligibleRows += 1;
    else ineligibleRows += 1;
    if (microcohortEligible && alreadyInMicrocohort) alreadyTestedRows += 1;
    if (microcohortEligible && !alreadyInMicrocohort) remainingEligibleRows += 1;
    if (actualMeta.actual_available) rowsWithActuals += 1;
    else rowsWithoutActuals += 1;
    if (actualMeta.actual_comparable) comparableRows += 1;
    else noncomparableRows += 1;

    _providerCharacterDirectExpressionEligibilityAccumulateScope_(
      providerStats,
      provider || 'UNKNOWN',
      microcohortEligible,
      alreadyInMicrocohort,
      actualMeta.actual_available
    );
    _providerCharacterDirectExpressionEligibilityAccumulateScope_(
      familyStats,
      eventFamily || 'UNKNOWN',
      microcohortEligible,
      alreadyInMicrocohort,
      actualMeta.actual_available
    );

    var auditRow = {
      source_capture_row_number: sourceCaptureRowNumber,
      event_id: eventId,
      provider: provider,
      indicator_name: indicatorName,
      country: country,
      release_ts: releaseTs,
      provider_call_status: providerCallStatus,
      forecast_value: String(row.ai_forecast_value || '').trim(),
      expression_field_count: expressionFieldCount,
      event_exists_in_main: eventExistsInMain ? 'TRUE' : 'FALSE',
      microcohort_eligible: microcohortEligible ? 'TRUE' : 'FALSE',
      eligibility_reason: microcohortEligible ? 'ELIGIBLE' : eligibilityReason,
      already_in_microcohort: alreadyInMicrocohort ? 'TRUE' : 'FALSE',
      already_in_outcome_check: alreadyInOutcomeCheck ? 'TRUE' : 'FALSE',
      actual_available: actualMeta.actual_available ? 'TRUE' : 'FALSE',
      actual_comparable: actualMeta.actual_comparable ? 'TRUE' : 'FALSE',
      event_family_if_available: eventFamily,
      notes: [
        eventRow ? '' : 'missing_event_lookup',
        actualMeta.note || '',
        'capture_workbook=' + String(captureBundle.workbook_type || '') + ':' + String(captureBundle.spreadsheet_id || ''),
        'event_workbook=' + String(eventBundle.workbook_type || '') + ':' + String(eventBundle.spreadsheet_id || '')
      ].filter(Boolean).join('; ')
    };
    auditRows.push(auditRow);

    if (microcohortEligible && (includeAllRows || previewRows.length < limit)) {
      previewRows.push({
        source_capture_row_number: sourceCaptureRowNumber,
        event_id: eventId,
        provider: provider,
        indicator_name: indicatorName,
        country: country,
        release_ts: releaseTs,
        outcome_family: eventFamily,
        provider_call_status: providerCallStatus,
        ai_forecast_value: String(row.ai_forecast_value || '').trim(),
        expression_field_count: expressionFieldCount,
        already_in_microcohort: alreadyInMicrocohort ? 'TRUE' : 'FALSE',
        actual_available: actualMeta.actual_available ? 'TRUE' : 'FALSE',
        notes: auditRow.notes
      });
    }
  }

  if (!includeAllRows && previewRows.length > limit) previewRows = previewRows.slice(0, limit);

  var remainingRows = auditRows.filter(function(row) {
    return String(row.microcohort_eligible || '') === 'TRUE' && String(row.already_in_microcohort || '') !== 'TRUE';
  });
  var remainingProviderCounts = _providerCharacterDirectExpressionEligibilityRemainingCounts_(remainingRows, 'provider');
  var remainingFamilyCounts = _providerCharacterDirectExpressionEligibilityRemainingCounts_(remainingRows, 'event_family_if_available');

  for (var r = 0; r < remainingRows.length; r++) {
    var rr = remainingRows[r];
    rr.priority_score = _providerCharacterDirectExpressionEligibilityPriorityScore_(
      rr,
      remainingProviderCounts,
      remainingFamilyCounts
    );
  }

  return {
    warnings: _uniqueStrings_(warnings),
    capture_workbook_type: String(captureBundle.workbook_type || ''),
    capture_spreadsheet_id: String(captureBundle.spreadsheet_id || ''),
    event_workbook_type: String(eventBundle.workbook_type || ''),
    event_spreadsheet_id: String(eventBundle.spreadsheet_id || ''),
    microcohort_workbook_type: String(microBundle.workbook_type || ''),
    microcohort_spreadsheet_id: String(microBundle.spreadsheet_id || ''),
    outcome_check_workbook_type: String(outcomeBundle.workbook_type || ''),
    outcome_check_spreadsheet_id: String(outcomeBundle.spreadsheet_id || ''),
    total_capture_rows: totalCaptureRows,
    total_unique_events: Object.keys(uniqueEventMap).length,
    eligible_rows: eligibleRows,
    ineligible_rows: ineligibleRows,
    already_tested_rows: alreadyTestedRows,
    remaining_eligible_rows: remainingEligibleRows,
    rows_with_actuals: rowsWithActuals,
    rows_without_actuals: rowsWithoutActuals,
    comparable_rows: comparableRows,
    noncomparable_rows: noncomparableRows,
    audit_rows: auditRows,
    preview_rows: previewRows.slice(0, limit),
    remaining_rows: remainingRows,
    provider_stats: providerStats,
    family_stats: familyStats
  };
}

function _providerCharacterDirectExpressionEligibilityAuditHeaders_() {
  return [
    'source_capture_row_number',
    'event_id',
    'provider',
    'indicator_name',
    'country',
    'release_ts',
    'provider_call_status',
    'forecast_value',
    'expression_field_count',
    'event_exists_in_main',
    'microcohort_eligible',
    'eligibility_reason',
    'already_in_microcohort',
    'already_in_outcome_check',
    'actual_available',
    'actual_comparable',
    'event_family_if_available',
    'notes'
  ];
}

function _providerCharacterDirectExpressionEligibilitySummaryHeaders_() {
  return [
    'generated_ts',
    'section',
    'scope_type',
    'scope_value',
    'total_capture_rows',
    'total_unique_events',
    'eligible_rows',
    'ineligible_rows',
    'eligible_rate',
    'already_tested_rows',
    'untested_eligible_rows',
    'rows_with_actuals',
    'rows_without_actuals',
    'comparable_rows',
    'noncomparable_rows',
    'source_capture_row_number',
    'event_id',
    'provider',
    'indicator_name',
    'event_family',
    'actual_available',
    'priority_score',
    'notes'
  ];
}

function _providerCharacterDirectExpressionEligibilitySummaryRows_(generatedTs, snapshot) {
  snapshot = snapshot || {};
  var rows = [];
  var eligibleRate = snapshot.total_capture_rows ? _round4_(Number(snapshot.eligible_rows || 0) / Number(snapshot.total_capture_rows || 1)) : '';
  rows.push({
    row_type: 'POPULATION',
    label: 'ALL',
    value: Number(snapshot.total_capture_rows || 0),
    capture_rows: Number(snapshot.total_capture_rows || 0),
    tested_rows: Number(snapshot.already_tested_rows || 0),
    untested_rows: Number(snapshot.remaining_eligible_rows || 0),
    actual_available_rows: Number(snapshot.rows_with_actuals || 0),
    generated_ts: generatedTs,
    section: 'POPULATION',
    scope_type: 'ALL',
    scope_value: 'ALL',
    total_capture_rows: Number(snapshot.total_capture_rows || 0),
    total_unique_events: Number(snapshot.total_unique_events || 0),
    eligible_rows: Number(snapshot.eligible_rows || 0),
    ineligible_rows: Number(snapshot.ineligible_rows || 0),
    eligible_rate: eligibleRate,
    already_tested_rows: Number(snapshot.already_tested_rows || 0),
    untested_eligible_rows: Number(snapshot.remaining_eligible_rows || 0),
    rows_with_actuals: Number(snapshot.rows_with_actuals || 0),
    rows_without_actuals: Number(snapshot.rows_without_actuals || 0),
    comparable_rows: Number(snapshot.comparable_rows || 0),
    noncomparable_rows: Number(snapshot.noncomparable_rows || 0),
    notes: [
      'capture_workbook=' + String(snapshot.capture_workbook_type || '') + ':' + String(snapshot.capture_spreadsheet_id || ''),
      'event_workbook=' + String(snapshot.event_workbook_type || '') + ':' + String(snapshot.event_spreadsheet_id || ''),
      'microcohort_workbook=' + String(snapshot.microcohort_workbook_type || '') + ':' + String(snapshot.microcohort_spreadsheet_id || '')
    ].join('; ')
  });

  var providerKeys = Object.keys(snapshot.provider_stats || {}).sort();
  for (var i = 0; i < providerKeys.length; i++) {
    var providerKey = providerKeys[i];
    var p = snapshot.provider_stats[providerKey] || {};
    rows.push({
      row_type: 'PROVIDER',
      label: providerKey,
      value: Number(p.capture_rows || 0),
      capture_rows: Number(p.capture_rows || 0),
      tested_rows: Number(p.tested_rows || 0),
      untested_rows: Number(p.untested_rows || 0),
      actual_available_rows: Number(p.actual_available_rows || 0),
      generated_ts: generatedTs,
      section: 'PROVIDER',
      scope_type: 'PROVIDER',
      scope_value: providerKey,
      total_capture_rows: Number(p.capture_rows || 0),
      eligible_rows: Number(p.eligible_rows || 0),
      already_tested_rows: Number(p.tested_rows || 0),
      untested_eligible_rows: Number(p.untested_rows || 0),
      rows_with_actuals: Number(p.actual_available_rows || 0),
      notes: 'provider_distribution'
    });
  }

  var familyKeys = Object.keys(snapshot.family_stats || {}).sort();
  for (var j = 0; j < familyKeys.length; j++) {
    var familyKey = familyKeys[j];
    var f = snapshot.family_stats[familyKey] || {};
    rows.push({
      row_type: 'EVENT_FAMILY',
      label: familyKey,
      value: Number(f.capture_rows || 0),
      capture_rows: Number(f.capture_rows || 0),
      tested_rows: Number(f.tested_rows || 0),
      untested_rows: Number(f.untested_rows || 0),
      generated_ts: generatedTs,
      section: 'EVENT_FAMILY',
      scope_type: 'EVENT_FAMILY',
      scope_value: familyKey,
      total_capture_rows: Number(f.capture_rows || 0),
      eligible_rows: Number(f.eligible_rows || 0),
      already_tested_rows: Number(f.tested_rows || 0),
      untested_eligible_rows: Number(f.untested_rows || 0),
      notes: 'family_distribution'
    });
  }

  var topRemaining = (snapshot.remaining_rows || []).slice().sort(function(a, b) {
    var as = Number(a.priority_score || 0);
    var bs = Number(b.priority_score || 0);
    if (bs !== as) return bs - as;
    return Number(a.source_capture_row_number || 0) - Number(b.source_capture_row_number || 0);
  }).slice(0, 50);

  for (var k = 0; k < topRemaining.length; k++) {
    var row = topRemaining[k] || {};
    rows.push({
      row_type: 'TOP_REMAINING',
      label: String(k + 1),
      value: Number(row.priority_score || 0),
      generated_ts: generatedTs,
      section: 'TOP_REMAINING',
      scope_type: 'CANDIDATE',
      scope_value: String(k + 1),
      capture_rows: '',
      tested_rows: '',
      untested_rows: '',
      actual_available_rows: String(row.actual_available || '').trim() === 'TRUE' ? 1 : 0,
      source_capture_row_number: Number(row.source_capture_row_number || 0),
      event_id: String(row.event_id || '').trim(),
      provider: String(row.provider || '').trim(),
      indicator_name: String(row.indicator_name || '').trim(),
      event_family: String(row.event_family_if_available || '').trim(),
      actual_available: String(row.actual_available || '').trim(),
      priority_score: Number(row.priority_score || 0),
      notes: [
        'eligibility_reason=' + String(row.eligibility_reason || '').trim(),
        'already_in_outcome_check=' + String(row.already_in_outcome_check || '').trim()
      ].join('; ')
    });
  }

  return rows;
}

function _providerCharacterDirectExpressionEligibilityExpressionFieldCount_(row) {
  row = row || {};
  var fields = [
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
  for (var i = 0; i < fields.length; i++) {
    if (String(fields[i] || '').trim()) count += 1;
  }
  return count;
}

function _providerCharacterDirectExpressionEligibilityReason_(row, eventExistsInMain, expressionFieldCount) {
  row = row || {};
  var eventId = String(row.event_id || '').trim();
  if (!eventId) return 'missing_event_id';
  var provider = String(row.provider || '').trim();
  if (!provider) return 'missing_provider';
  var status = String(row.provider_call_status || '').trim().toLowerCase();
  if (status !== 'success' && status !== 'reused') return 'failed_provider_call';
  if (String(row.ai_forecast_value || '').trim() === '') return 'missing_forecast_value';
  if (Number(expressionFieldCount || 0) < 3) return 'insufficient_expression_fields';
  if (!eventExistsInMain) return 'missing_event_mapping';
  return '';
}

function _providerCharacterDirectExpressionEligibilityRowKey_(eventId, provider) {
  return String(eventId || '').trim() + '||' + String(provider || '').trim();
}

function _providerCharacterDirectExpressionEligibilityKeySet_(rows) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var eventId = String(row.event_id || '').trim();
    var provider = String(row.provider || '').trim();
    if (!eventId || !provider) continue;
    out[_providerCharacterDirectExpressionEligibilityRowKey_(eventId, provider)] = true;
  }
  return out;
}

function _providerCharacterDirectExpressionEligibilityActualMeta_(eventRow) {
  if (!eventRow) {
    return {
      actual_available: false,
      actual_comparable: false,
      note: 'event_missing'
    };
  }
  var consensusValue = _numOrNull_(eventRow.consensus_value);
  var prevRevision = _numOrNull_(eventRow.prev_revision);
  var releasedValue = _numOrNull_(eventRow.released_value);
  var actualDirection = _providerCharacterDirectExpressionOutcomeCheckActualDirection_(consensusValue, releasedValue, prevRevision);
  return {
    actual_available: releasedValue != null,
    actual_comparable: actualDirection && actualDirection.status === 'ok',
    note: actualDirection ? String(actualDirection.status || '') : ''
  };
}

function _providerCharacterDirectExpressionEligibilityAccumulateScope_(scopeMap, key, eligible, tested, actualAvailable) {
  key = String(key || '').trim() || 'UNKNOWN';
  if (!scopeMap[key]) {
    scopeMap[key] = {
      capture_rows: 0,
      eligible_rows: 0,
      tested_rows: 0,
      untested_rows: 0,
      actual_available_rows: 0
    };
  }
  var target = scopeMap[key];
  target.capture_rows += 1;
  if (eligible) target.eligible_rows += 1;
  if (eligible && tested) target.tested_rows += 1;
  if (eligible && !tested) target.untested_rows += 1;
  if (actualAvailable) target.actual_available_rows += 1;
}

function _providerCharacterDirectExpressionEligibilityRemainingCounts_(rows, fieldName) {
  var out = {};
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    var key = String(row[fieldName] || '').trim() || 'UNKNOWN';
    out[key] = Number(out[key] || 0) + 1;
  }
  return out;
}

function _providerCharacterDirectExpressionEligibilityPriorityScore_(row, providerCounts, familyCounts) {
  row = row || {};
  var provider = String(row.provider || '').trim() || 'UNKNOWN';
  var family = String(row.event_family_if_available || '').trim() || 'UNKNOWN';
  var providerCount = Math.max(1, Number(providerCounts[provider] || 1));
  var familyCount = Math.max(1, Number(familyCounts[family] || 1));
  var actualBonus = String(row.actual_available || '').trim() === 'TRUE' ? 1000 : 0;
  var providerBonus = _round4_(100 / providerCount);
  var familyBonus = _round4_(100 / familyCount);
  return _round4_(actualBonus + providerBonus + familyBonus);
}

function _providerCharacterDirectExpressionValidationHeaders_() {
  return [
    'generated_ts',
    'validation_run_id',
    'validation_mode',
    'original_capture_run_id',
    'original_cohort_id',
    'validation_capture_run_id',
    'source_capture_row_number',
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
    'original_ai_forecast_value',
    'original_qualitative_result',
    'original_rationale_short',
    'original_primary_focus_phrase',
    'original_secondary_focus_phrase',
    'original_ignored_or_discounted_factor_phrase',
    'original_causal_path_phrase',
    'original_failure_condition_phrase',
    'original_confidence_basis_phrase',
    'original_uncertainty_phrase',
    'original_expression_summary_phrase',
    'original_attention_terms',
    'validation_ai_forecast_value',
    'validation_qualitative_result',
    'validation_rationale_short',
    'validation_primary_focus_phrase',
    'validation_secondary_focus_phrase',
    'validation_ignored_or_discounted_factor_phrase',
    'validation_causal_path_phrase',
    'validation_failure_condition_phrase',
    'validation_confidence_basis_phrase',
    'validation_uncertainty_phrase',
    'validation_expression_summary_phrase',
    'validation_attention_terms',
    'forecast_value_delta',
    'forecast_direction_match',
    'qualitative_match',
    'primary_focus_similarity',
    'secondary_focus_similarity',
    'ignored_factor_similarity',
    'causal_path_similarity',
    'failure_condition_similarity',
    'confidence_basis_similarity',
    'uncertainty_similarity',
    'expression_summary_similarity',
    'attention_terms_similarity',
    'overall_expression_similarity',
    'reproducibility_result',
    'validation_call_status',
    'token_input_estimate',
    'token_output_estimate',
    'latency_ms',
    'notes',
    'sample_group_id',
    'rerun_index'
  ];
}

function _providerCharacterDirectExpressionValidationRunSamePathCapture_(provider, promptEvent, eventId, warnings) {
  var prompt = _providerCharacterDirectExpressionCaptureBuildPrompt_(promptEvent);
  var startMs = Date.now();
  var providerRespMap = _providerCharacterDirectExpressionCaptureCallProvidersParallel_([provider], prompt, warnings, eventId);
  var providerKey = String(provider && provider.name || '').trim();
  var providerResp = providerRespMap[providerKey] || null;
  var latencyMs = providerResp && providerResp.latency_ms != null ? providerResp.latency_ms : (Date.now() - startMs);
  return {
    providerResp: providerResp,
    call_status: providerResp && providerResp.call_status ? String(providerResp.call_status).trim().toLowerCase() : 'failed',
    call_error: providerResp && providerResp.call_error ? String(providerResp.call_error).trim() : '',
    latency_ms: latencyMs
  };
}

function _providerCharacterDirectExpressionValidationBuildEventMap_(eventRows) {
  var map = {};
  for (var i = 0; i < (eventRows || []).length; i++) {
    var row = eventRows[i] || {};
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    map[eventId] = row;
  }
  return map;
}

function _providerCharacterDirectExpressionValidationSelectRows_(captureRows, eventMap, limit, warnings) {
  var out = [];
  for (var i = 0; i < (captureRows || []).length && out.length < limit; i++) {
    var row = captureRows[i] || {};
    if (!_providerCharacterDirectExpressionValidationIsEligibleRow_(row)) continue;
    var eventId = String(row.event_id || '').trim();
    if (!eventId) continue;
    if (!eventMap[eventId]) {
      warnings.push('missing_event_for_selection:' + eventId);
      continue;
    }
    out.push({
      source_capture_row_number: i + 2,
      row: row
    });
  }
  return out;
}

function _providerCharacterDirectExpressionValidationIsEligibleRow_(row) {
  row = row || {};
  var status = String(row.provider_call_status || '').trim().toLowerCase();
  if (status !== 'success' && status !== 'reused') return false;
  if (!String(row.event_id || '').trim()) return false;
  if (!String(row.provider || '').trim()) return false;
  if (String(row.ai_forecast_value || '').trim() === '') return false;
  var comparisons = [
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
  for (var i = 0; i < comparisons.length; i++) {
    if (String(comparisons[i] || '').trim()) count += 1;
  }
  return count >= 3;
}

function _providerCharacterDirectExpressionValidationBuildPromptEvent_(sourceRow, eventMeta) {
  sourceRow = sourceRow || {};
  eventMeta = eventMeta || {};
  return {
    event_id: String(sourceRow.event_id || eventMeta.event_id || '').trim(),
    type: String(eventMeta.type || sourceRow.type || '').trim(),
    country: String(eventMeta.country || sourceRow.country || '').trim(),
    indicator_name: String(eventMeta.indicator_name || sourceRow.indicator_name || '').trim(),
    release_ts: String(eventMeta.release_ts || sourceRow.release_ts || '').trim(),
    consensus_value: _numOrNull_(eventMeta.consensus_value != null ? eventMeta.consensus_value : sourceRow.consensus_value),
    prev_revision: _numOrNull_(eventMeta.prev_revision != null ? eventMeta.prev_revision : sourceRow.prev_revision),
    unit: String(eventMeta.unit || sourceRow.unit || '').trim(),
    importance: String(eventMeta.importance || sourceRow.importance || '').trim() || 'medium',
    genre: String(eventMeta.genre || sourceRow.genre || '').trim()
  };
}

function _providerCharacterDirectExpressionValidationBuildRow_(generatedTs, validationRunId, validationMode, validationCaptureRunId, sourceRowNumber, originalRow, promptEvent, normalized, providerResp, callStatus, callError, latencyMs, warnings, extraMeta) {
  originalRow = originalRow || {};
  normalized = normalized || {};
  extraMeta = extraMeta || {};
  var originalForecastValue = _numOrNull_(originalRow.ai_forecast_value);
  var validationForecastValue = _numOrNull_(normalized.ai_forecast_value);
  var consensusValue = _numOrNull_(originalRow.consensus_value);
  var originalDir = _providerCharacterDirectExpressionValidationForecastDirectionBucket_(originalForecastValue, consensusValue);
  var validationDir = _providerCharacterDirectExpressionValidationForecastDirectionBucket_(validationForecastValue, consensusValue);
  var forecastDirectionMatch = (originalDir && validationDir && originalDir === validationDir) ? 'TRUE' : 'FALSE';
  var qualitativeMatch = (String(originalRow.qualitative_result || '').trim().toLowerCase() && String(originalRow.qualitative_result || '').trim().toLowerCase() === String(normalized.qualitative_result || '').trim().toLowerCase()) ? 'TRUE' : 'FALSE';

  var fieldPairs = [
    ['primary_focus_similarity', originalRow.primary_focus_phrase, normalized.primary_focus_phrase],
    ['secondary_focus_similarity', originalRow.secondary_focus_phrase, normalized.secondary_focus_phrase],
    ['ignored_factor_similarity', originalRow.ignored_or_discounted_factor_phrase, normalized.ignored_or_discounted_factor_phrase],
    ['causal_path_similarity', originalRow.causal_path_phrase, normalized.causal_path_phrase],
    ['failure_condition_similarity', originalRow.failure_condition_phrase, normalized.failure_condition_phrase],
    ['confidence_basis_similarity', originalRow.confidence_basis_phrase, normalized.confidence_basis_phrase],
    ['uncertainty_similarity', originalRow.uncertainty_phrase, normalized.uncertainty_phrase],
    ['expression_summary_similarity', originalRow.expression_summary_phrase, normalized.expression_summary_phrase],
    ['attention_terms_similarity', originalRow.attention_terms, normalized.attention_terms]
  ];

  var similarityValues = [];
  var out = {
    generated_ts: generatedTs,
    validation_run_id: validationRunId,
    validation_mode: validationMode,
    original_capture_run_id: String(originalRow.capture_run_id || '').trim(),
    original_cohort_id: String(originalRow.cohort_id || '').trim(),
    validation_capture_run_id: validationCaptureRunId,
    source_capture_row_number: sourceRowNumber,
    event_id: String(originalRow.event_id || promptEvent.event_id || '').trim(),
    provider: String(originalRow.provider || '').trim(),
    indicator_name: String(originalRow.indicator_name || promptEvent.indicator_name || '').trim(),
    country: String(originalRow.country || promptEvent.country || '').trim(),
    release_ts: String(originalRow.release_ts || promptEvent.release_ts || '').trim(),
    outcome_family: String(originalRow.outcome_family || '').trim(),
    importance: String(originalRow.importance || promptEvent.importance || '').trim(),
    consensus_value: consensusValue == null ? '' : consensusValue,
    prev_revision: _numOrNull_(originalRow.prev_revision) == null ? '' : _numOrNull_(originalRow.prev_revision),
    released_value: _numOrNull_(originalRow.released_value) == null ? '' : _numOrNull_(originalRow.released_value),

    original_ai_forecast_value: originalForecastValue == null ? '' : originalForecastValue,
    original_qualitative_result: String(originalRow.qualitative_result || '').trim(),
    original_rationale_short: String(originalRow.rationale_short || '').trim(),
    original_primary_focus_phrase: String(originalRow.primary_focus_phrase || '').trim(),
    original_secondary_focus_phrase: String(originalRow.secondary_focus_phrase || '').trim(),
    original_ignored_or_discounted_factor_phrase: String(originalRow.ignored_or_discounted_factor_phrase || '').trim(),
    original_causal_path_phrase: String(originalRow.causal_path_phrase || '').trim(),
    original_failure_condition_phrase: String(originalRow.failure_condition_phrase || '').trim(),
    original_confidence_basis_phrase: String(originalRow.confidence_basis_phrase || '').trim(),
    original_uncertainty_phrase: String(originalRow.uncertainty_phrase || '').trim(),
    original_expression_summary_phrase: String(originalRow.expression_summary_phrase || '').trim(),
    original_attention_terms: String(originalRow.attention_terms || '').trim(),

    validation_ai_forecast_value: validationForecastValue == null ? '' : validationForecastValue,
    validation_qualitative_result: String(normalized.qualitative_result || '').trim(),
    validation_rationale_short: String(normalized.rationale_short || '').trim(),
    validation_primary_focus_phrase: String(normalized.primary_focus_phrase || '').trim(),
    validation_secondary_focus_phrase: String(normalized.secondary_focus_phrase || '').trim(),
    validation_ignored_or_discounted_factor_phrase: String(normalized.ignored_or_discounted_factor_phrase || '').trim(),
    validation_causal_path_phrase: String(normalized.causal_path_phrase || '').trim(),
    validation_failure_condition_phrase: String(normalized.failure_condition_phrase || '').trim(),
    validation_confidence_basis_phrase: String(normalized.confidence_basis_phrase || '').trim(),
    validation_uncertainty_phrase: String(normalized.uncertainty_phrase || '').trim(),
    validation_expression_summary_phrase: String(normalized.expression_summary_phrase || '').trim(),
    validation_attention_terms: String(normalized.attention_terms || '').trim(),

    forecast_value_delta: (originalForecastValue != null && validationForecastValue != null)
      ? _round4_(validationForecastValue - originalForecastValue)
      : '',
    forecast_direction_match: callStatus === 'success' ? forecastDirectionMatch : '',
    qualitative_match: callStatus === 'success' ? qualitativeMatch : '',

    primary_focus_similarity: '',
    secondary_focus_similarity: '',
    ignored_factor_similarity: '',
    causal_path_similarity: '',
    failure_condition_similarity: '',
    confidence_basis_similarity: '',
    uncertainty_similarity: '',
    expression_summary_similarity: '',
    attention_terms_similarity: '',
    overall_expression_similarity: '',
    reproducibility_result: 'low_reproducibility',
    validation_call_status: callStatus,
    token_input_estimate: providerResp && providerResp.prompt_tokens != null ? providerResp.prompt_tokens : '',
    token_output_estimate: providerResp && providerResp.completion_tokens != null ? providerResp.completion_tokens : '',
    latency_ms: latencyMs == null ? '' : latencyMs,
    notes: '',
    sample_group_id: String(extraMeta.sample_group_id || '').trim(),
    rerun_index: extraMeta.rerun_index == null ? '' : Number(extraMeta.rerun_index)
  };

  if (callStatus !== 'failed') {
    for (var i = 0; i < fieldPairs.length; i++) {
      var pair = fieldPairs[i];
      var sim = _providerCharacterDirectExpressionValidationTextSimilarity_(pair[1], pair[2]);
      out[pair[0]] = sim === '' ? '' : _round4_(sim);
      if (sim !== '') similarityValues.push(Number(sim));
    }
    out.overall_expression_similarity = similarityValues.length ? _round4_(_providerCharacterDirectExpressionValidationAverage_(similarityValues)) : 0;
    out.reproducibility_result = _providerCharacterDirectExpressionValidationClassify_(out.qualitative_match, out.forecast_direction_match, out.overall_expression_similarity, callStatus);
  }

  if (callStatus === 'failed') {
    out.reproducibility_result = 'rerun_failed';
    warnings.push('validation_call_failed:' + String(originalRow.event_id || '') + '|' + String(originalRow.provider || ''));
  }

  out.notes = [
    'source_capture_row=' + sourceRowNumber,
    'validation_mode=' + String(validationMode || ''),
    'original_capture_run_id=' + String(originalRow.capture_run_id || ''),
    'original_cohort_id=' + String(originalRow.cohort_id || ''),
    'validation_capture_run_id=' + String(validationCaptureRunId || ''),
    extraMeta.payload_hash ? ('payload_hash=' + String(extraMeta.payload_hash || '')) : '',
    out.sample_group_id ? ('sample_group_id=' + out.sample_group_id) : '',
    out.rerun_index !== '' ? ('rerun_index=' + out.rerun_index) : '',
    'original_provider_call_status=' + String(originalRow.provider_call_status || ''),
    'prompt_event_id=' + String(promptEvent.event_id || ''),
    'validation_call_status=' + callStatus,
    'reproducibility_result=' + String(out.reproducibility_result || ''),
    callError ? ('call_error=' + callError) : ''
  ].filter(Boolean).join('; ');
  return out;
}

function _providerCharacterDirectExpressionValidationTextSimilarity_(a, b) {
  var ta = _providerCharacterDirectExpressionValidationTokenize_(a);
  var tb = _providerCharacterDirectExpressionValidationTokenize_(b);
  if (!ta.length && !tb.length) return '';
  if (!ta.length || !tb.length) return 0;
  return _providerCharacterDirectExpressionValidationJaccard_(ta, tb);
}

function _providerCharacterDirectExpressionValidationTokenize_(text) {
  if (typeof _providerCharacterMicroExpressionTokenize_ === 'function') {
    return _providerCharacterMicroExpressionTokenize_(text);
  }
  var stop = {
    a: true, an: true, and: true, as: true, at: true, be: true, by: true, for: true, from: true,
    if: true, in: true, into: true, is: true, it: true, its: true, no: true, not: true, of: true,
    on: true, or: true, out: true, the: true, to: true, with: true, without: true, this: true,
    that: true, these: true, those: true, are: true, was: true, were: true, can: true, will: true,
    would: true, should: true, could: true, may: true, might: true, maybe: true
  };
  return String(text || '')
    .toLowerCase()
    .replace(/[_/|]+/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .split(/\s+/)
    .map(function(token) { return String(token || '').trim(); })
    .filter(function(token) { return !!token && !stop[token]; });
}

function _providerCharacterDirectExpressionValidationJaccard_(a, b) {
  if (typeof _providerCharacterMicroExpressionJaccard_ === 'function') {
    return _providerCharacterMicroExpressionJaccard_(a, b);
  }
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

function _providerCharacterDirectExpressionValidationRowKey_(rowValues, idx) {
  var runId = idx.validation_run_id != null ? rowValues[idx.validation_run_id] : '';
  var mode = idx.validation_mode != null ? rowValues[idx.validation_mode] : '';
  var sampleGroupId = idx.sample_group_id != null ? rowValues[idx.sample_group_id] : '';
  var rerunIndex = idx.rerun_index != null ? rowValues[idx.rerun_index] : '';
  var sourceRow = idx.source_capture_row_number != null ? rowValues[idx.source_capture_row_number] : '';
  var eventId = idx.event_id != null ? rowValues[idx.event_id] : '';
  var provider = idx.provider != null ? rowValues[idx.provider] : '';
  return [
    String(runId || '').trim(),
    String(mode || '').trim(),
    String(sampleGroupId || '').trim(),
    String(rerunIndex || '').trim(),
    String(sourceRow || '').trim(),
    String(eventId || '').trim(),
    String(provider || '').trim()
  ].join('|');
}

function _providerCharacterDirectExpressionValidationReadExistingRows_(sheet, headers) {
  var lastRow = sheet ? sheet.getLastRow() : 0;
  if (!sheet || lastRow <= 1) return [];
  var actualHeaders = headers || [];
  return sheet.getRange(2, 1, lastRow - 1, actualHeaders.length).getValues();
}

function _providerCharacterDirectExpressionValidationRowsToObjects_(rows, headers) {
  var out = [];
  var actualHeaders = headers || [];
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || [];
    var obj = {};
    for (var h = 0; h < actualHeaders.length; h++) {
      obj[String(actualHeaders[h] || '')] = h < row.length ? row[h] : '';
    }
    out.push(obj);
  }
  return out;
}

function _providerCharacterDirectExpressionValidationForecastDirectionBucket_(forecastValue, consensusValue) {
  var f = _numOrNull_(forecastValue);
  var c = _numOrNull_(consensusValue);
  if (f == null || c == null) return '';
  var diff = f - c;
  var tol = Math.max(0.01, Math.abs(c) * 0.001);
  if (Math.abs(diff) <= tol) return 'inline';
  return diff > 0 ? 'above' : 'below';
}

function _providerCharacterDirectExpressionValidationClassify_(qualitativeMatch, forecastDirectionMatch, similarity, callStatus) {
  if (String(callStatus || '').trim().toLowerCase() === 'failed') return 'rerun_failed';
  var sim = _numOrNull_(similarity);
  var qMatch = String(qualitativeMatch || '').trim().toUpperCase() === 'TRUE';
  var dMatch = String(forecastDirectionMatch || '').trim().toUpperCase() === 'TRUE';
  if (sim == null) return 'low_reproducibility';
  if (qMatch && dMatch && sim >= 0.70) return 'high_reproducibility';
  if (dMatch && sim >= 0.40) return 'medium_reproducibility';
  if (dMatch && sim < 0.40) return 'forecast_stable_expression_unstable';
  if (!dMatch && sim >= 0.70) return 'forecast_unstable_expression_stable';
  return 'low_reproducibility';
}

function _providerCharacterDirectExpressionValidationPayloadHash_(promptEvent) {
  var payload = {
    event_id: String(promptEvent && promptEvent.event_id || '').trim(),
    type: String(promptEvent && promptEvent.type || '').trim(),
    country: String(promptEvent && promptEvent.country || '').trim(),
    indicator_name: String(promptEvent && promptEvent.indicator_name || '').trim(),
    release_ts: String(promptEvent && promptEvent.release_ts || '').trim(),
    consensus_value: _numOrNull_(promptEvent && promptEvent.consensus_value),
    prev_revision: _numOrNull_(promptEvent && promptEvent.prev_revision),
    unit: String(promptEvent && promptEvent.unit || '').trim(),
    importance: String(promptEvent && promptEvent.importance || '').trim(),
    genre: String(promptEvent && promptEvent.genre || '').trim()
  };
  return _uuidFromString_(JSON.stringify(payload));
}

function _providerCharacterDirectExpressionMicrocohortSampleGroupId_(eventId, provider) {
  return [
    String(eventId || '').trim(),
    String(provider || '').trim().replace(/[^A-Za-z0-9]+/g, '_'),
    'microcohort_v1'
  ].join('_');
}

function _providerCharacterDirectExpressionMicrocohortHasExistingRerun_(rows, validationRunId, validationMode, sampleGroupId, rerunIndex, sourceRowNumber, eventId, provider) {
  for (var i = 0; i < (rows || []).length; i++) {
    var row = rows[i] || {};
    if (String(row.validation_run_id || '').trim() !== String(validationRunId || '').trim()) continue;
    if (String(row.validation_mode || '').trim() !== String(validationMode || '').trim()) continue;
    if (String(row.sample_group_id || '').trim() !== String(sampleGroupId || '').trim()) continue;
    if (String(row.rerun_index || '').trim() !== String(rerunIndex || '').trim()) continue;
    if (String(row.source_capture_row_number || '').trim() !== String(sourceRowNumber || '').trim()) continue;
    if (String(row.event_id || '').trim() !== String(eventId || '').trim()) continue;
    if (String(row.provider || '').trim() !== String(provider || '').trim()) continue;
    return true;
  }
  return false;
}

function _providerCharacterDirectExpressionMicrocohortHeaders_() {
  return [
    'generated_ts',
    'sample_group_id',
    'event_id',
    'provider',
    'indicator_name',
    'country',
    'release_ts',
    'run_count',
    'successful_run_count',
    'failed_run_count',
    'forecast_direction_distribution',
    'dominant_forecast_direction',
    'forecast_direction_concentration',
    'forecast_value_min',
    'forecast_value_max',
    'forecast_value_mean',
    'forecast_value_stddev',
    'primary_focus_terms',
    'secondary_focus_terms',
    'causal_path_terms',
    'failure_condition_terms',
    'confidence_basis_terms',
    'uncertainty_terms',
    'dominant_causal_family_if_classifiable',
    'pattern_concentration_score',
    'expression_similarity_mean_if_available',
    'interpretation_label',
    'notes'
  ];
}

function _providerCharacterDirectExpressionMicrocohortBuildSummaryRow_(generatedTs, sampleGroupId, sourceRowNumber, sourceRow, promptEvent, payloadHash, validationRunId, validationMode, validationRows, warnings) {
  var matching = [];
  for (var i = 0; i < (validationRows || []).length; i++) {
    var row = validationRows[i] || {};
    if (String(row.validation_run_id || '').trim() !== String(validationRunId || '').trim()) continue;
    if (String(row.validation_mode || '').trim() !== String(validationMode || '').trim()) continue;
    if (String(row.sample_group_id || '').trim() !== String(sampleGroupId || '').trim()) continue;
    matching.push(row);
  }

  var runRows = [{
    is_source: true,
    validation_call_status: String(sourceRow.provider_call_status || '').trim() ? 'success' : '',
    ai_forecast_value: sourceRow.ai_forecast_value,
    primary_focus_phrase: sourceRow.primary_focus_phrase,
    secondary_focus_phrase: sourceRow.secondary_focus_phrase,
    causal_path_phrase: sourceRow.causal_path_phrase,
    failure_condition_phrase: sourceRow.failure_condition_phrase,
    confidence_basis_phrase: sourceRow.confidence_basis_phrase,
    uncertainty_phrase: sourceRow.uncertainty_phrase,
    overall_expression_similarity: '',
    notes: 'payload_hash=' + payloadHash
  }];
  for (var m = 0; m < matching.length; m++) {
    var vr = matching[m] || {};
    runRows.push({
      is_source: false,
      validation_call_status: String(vr.validation_call_status || '').trim(),
      ai_forecast_value: vr.validation_ai_forecast_value,
      primary_focus_phrase: vr.validation_primary_focus_phrase,
      secondary_focus_phrase: vr.validation_secondary_focus_phrase,
      causal_path_phrase: vr.validation_causal_path_phrase,
      failure_condition_phrase: vr.validation_failure_condition_phrase,
      confidence_basis_phrase: vr.validation_confidence_basis_phrase,
      uncertainty_phrase: vr.validation_uncertainty_phrase,
      overall_expression_similarity: vr.overall_expression_similarity,
      notes: String(vr.notes || '')
    });
  }

  var knownDirectionCounts = {};
  var knownDirectionTotal = 0;
  var valueList = [];
  var simValues = [];
  var payloadMismatch = false;
  var fieldTokenMaps = {
    primary: {},
    secondary: {},
    causal: {},
    failure: {},
    confidence: {},
    uncertainty: {}
  };
  var fieldRunPresence = {
    primary: 0,
    secondary: 0,
    causal: 0,
    failure: 0,
    confidence: 0,
    uncertainty: 0
  };

  for (var r = 0; r < runRows.length; r++) {
    var rr = runRows[r] || {};
    var dir = _providerCharacterDirectExpressionValidationForecastDirectionBucket_(rr.ai_forecast_value, sourceRow.consensus_value);
    if (dir) {
      knownDirectionCounts[dir] = Number(knownDirectionCounts[dir] || 0) + 1;
      knownDirectionTotal += 1;
    }
    var value = _numOrNull_(rr.ai_forecast_value);
    if (value != null) valueList.push(value);
    var sim = _numOrNull_(rr.overall_expression_similarity);
    if (sim != null) simValues.push(sim);
    if (String(rr.notes || '').indexOf('payload_hash=' + payloadHash) < 0) payloadMismatch = true;
    _providerCharacterDirectExpressionMicrocohortAccumulateTerms_(fieldTokenMaps.primary, rr.primary_focus_phrase, fieldRunPresence, 'primary');
    _providerCharacterDirectExpressionMicrocohortAccumulateTerms_(fieldTokenMaps.secondary, rr.secondary_focus_phrase, fieldRunPresence, 'secondary');
    _providerCharacterDirectExpressionMicrocohortAccumulateTerms_(fieldTokenMaps.causal, rr.causal_path_phrase, fieldRunPresence, 'causal');
    _providerCharacterDirectExpressionMicrocohortAccumulateTerms_(fieldTokenMaps.failure, rr.failure_condition_phrase, fieldRunPresence, 'failure');
    _providerCharacterDirectExpressionMicrocohortAccumulateTerms_(fieldTokenMaps.confidence, rr.confidence_basis_phrase, fieldRunPresence, 'confidence');
    _providerCharacterDirectExpressionMicrocohortAccumulateTerms_(fieldTokenMaps.uncertainty, rr.uncertainty_phrase, fieldRunPresence, 'uncertainty');
  }

  var dominantDirection = '';
  var dominantDirectionCount = 0;
  Object.keys(knownDirectionCounts).forEach(function(key) {
    if (Number(knownDirectionCounts[key] || 0) > dominantDirectionCount) {
      dominantDirection = key;
      dominantDirectionCount = Number(knownDirectionCounts[key] || 0);
    }
  });
  var directionConcentration = knownDirectionTotal ? _round4_(dominantDirectionCount / knownDirectionTotal) : '';
  var patternConcentration = _providerCharacterDirectExpressionMicrocohortPatternConcentration_(fieldTokenMaps, fieldRunPresence);
  var successfulRunCount = 1;
  var failedRunCount = 0;
  for (var z = 0; z < matching.length; z++) {
    var st = String((matching[z] || {}).validation_call_status || '').trim().toLowerCase();
    if (st === 'success') successfulRunCount += 1;
    else failedRunCount += 1;
  }

  return {
    generated_ts: generatedTs,
    sample_group_id: sampleGroupId,
    event_id: String(sourceRow.event_id || '').trim(),
    provider: String(sourceRow.provider || '').trim(),
    indicator_name: String(sourceRow.indicator_name || '').trim(),
    country: String(sourceRow.country || '').trim(),
    release_ts: String(sourceRow.release_ts || '').trim(),
    run_count: runRows.length,
    successful_run_count: successfulRunCount,
    failed_run_count: failedRunCount,
    forecast_direction_distribution: _providerCharacterDirectExpressionMicrocohortFormatCounts_(knownDirectionCounts),
    dominant_forecast_direction: dominantDirection,
    forecast_direction_concentration: directionConcentration,
    forecast_value_min: _providerCharacterDirectExpressionMicrocohortMin_(valueList),
    forecast_value_max: _providerCharacterDirectExpressionMicrocohortMax_(valueList),
    forecast_value_mean: _providerCharacterDirectExpressionValidationAverage_(valueList),
    forecast_value_stddev: _providerCharacterDirectExpressionMicrocohortStdDev_(valueList),
    primary_focus_terms: _providerCharacterDirectExpressionMicrocohortTopTerms_(fieldTokenMaps.primary, 5),
    secondary_focus_terms: _providerCharacterDirectExpressionMicrocohortTopTerms_(fieldTokenMaps.secondary, 5),
    causal_path_terms: _providerCharacterDirectExpressionMicrocohortTopTerms_(fieldTokenMaps.causal, 5),
    failure_condition_terms: _providerCharacterDirectExpressionMicrocohortTopTerms_(fieldTokenMaps.failure, 5),
    confidence_basis_terms: _providerCharacterDirectExpressionMicrocohortTopTerms_(fieldTokenMaps.confidence, 5),
    uncertainty_terms: _providerCharacterDirectExpressionMicrocohortTopTerms_(fieldTokenMaps.uncertainty, 5),
    dominant_causal_family_if_classifiable: _providerCharacterDirectExpressionMicrocohortDominantCausalFamily_(fieldTokenMaps.causal, fieldRunPresence.causal),
    pattern_concentration_score: patternConcentration,
    expression_similarity_mean_if_available: simValues.length ? _providerCharacterDirectExpressionValidationAverage_(simValues) : '',
    interpretation_label: _providerCharacterDirectExpressionMicrocohortInterpretation_(payloadMismatch, failedRunCount, directionConcentration, patternConcentration),
    notes: [
      'source_capture_row_number=' + sourceRowNumber,
      'source_payload_hash=' + payloadHash,
      'rerun_rows=' + matching.length,
      'token_cluster_only=TRUE',
      warnings && warnings.length ? ('warnings=' + _uniqueStrings_(warnings).join('|')) : ''
    ].filter(Boolean).join('; ')
  };
}

function _providerCharacterDirectExpressionMicrocohortAccumulateTerms_(termMap, phrase, presenceMap, key) {
  var tokens = _providerCharacterDirectExpressionValidationTokenize_(phrase);
  if (!tokens.length) return;
  presenceMap[key] = Number(presenceMap[key] || 0) + 1;
  var seen = {};
  for (var i = 0; i < tokens.length; i++) {
    var tok = String(tokens[i] || '').trim();
    if (!tok || seen[tok]) continue;
    seen[tok] = true;
    termMap[tok] = Number(termMap[tok] || 0) + 1;
  }
}

function _providerCharacterDirectExpressionMicrocohortTopTerms_(termMap, limit) {
  var items = Object.keys(termMap || {}).map(function(key) {
    return { key: key, count: Number(termMap[key] || 0) };
  }).sort(function(a, b) {
    if (b.count !== a.count) return b.count - a.count;
    return String(a.key || '').localeCompare(String(b.key || ''));
  }).slice(0, limit || 5);
  return items.map(function(item) { return item.key + '(' + item.count + ')'; }).join('|');
}

function _providerCharacterDirectExpressionMicrocohortPatternConcentration_(fieldTokenMaps, fieldRunPresence) {
  var scores = [];
  ['primary', 'secondary', 'causal', 'failure', 'confidence', 'uncertainty'].forEach(function(key) {
    var denom = Number(fieldRunPresence[key] || 0);
    if (!denom) return;
    var top = 0;
    Object.keys(fieldTokenMaps[key] || {}).forEach(function(term) {
      top = Math.max(top, Number(fieldTokenMaps[key][term] || 0));
    });
    if (top > 0) scores.push(top / denom);
  });
  return scores.length ? _round4_(scores.reduce(function(a, b) { return a + b; }, 0) / scores.length) : '';
}

function _providerCharacterDirectExpressionMicrocohortDominantCausalFamily_(termMap, runPresence) {
  var topTerm = '';
  var topCount = 0;
  Object.keys(termMap || {}).forEach(function(term) {
    var count = Number(termMap[term] || 0);
    if (count > topCount) {
      topCount = count;
      topTerm = term;
    }
  });
  if (!topTerm || !runPresence || (topCount / runPresence) < 0.6) return '';
  if (['demand', 'consumer', 'shipment'].indexOf(topTerm) >= 0) return 'demand';
  if (['inventory', 'stock', 'drawdown'].indexOf(topTerm) >= 0) return 'inventory';
  if (['revision', 'revisions', 'consensus'].indexOf(topTerm) >= 0) return 'revision_consensus';
  if (['seasonal', 'seasonality'].indexOf(topTerm) >= 0) return 'seasonal';
  if (['supply', 'production', 'refinery'].indexOf(topTerm) >= 0) return 'supply';
  return '';
}

function _providerCharacterDirectExpressionMicrocohortInterpretation_(payloadMismatch, failedRunCount, directionConcentration, patternConcentration) {
  if (payloadMismatch) return 'PAYLOAD_IDENTITY_SUSPECT';
  if (Number(failedRunCount || 0) > 0) return 'RERUN_INCOMPLETE';
  var forecastStable = _numOrNull_(directionConcentration) != null && Number(directionConcentration || 0) >= 0.8;
  var patternScore = _numOrNull_(patternConcentration);
  var patternState = 'UNSTABLE';
  if (patternScore != null && patternScore >= 0.75) patternState = 'STABLE';
  else if (patternScore != null && patternScore >= 0.5) patternState = 'MIXED';
  if (forecastStable && patternState === 'STABLE') return 'FORECAST_STABLE_PATTERN_STABLE';
  if (forecastStable && patternState === 'MIXED') return 'FORECAST_STABLE_PATTERN_MIXED';
  if (forecastStable) return 'FORECAST_STABLE_PATTERN_UNSTABLE';
  if (patternState === 'STABLE') return 'FORECAST_UNSTABLE_PATTERN_STABLE';
  return 'FORECAST_UNSTABLE_PATTERN_UNSTABLE';
}

function _providerCharacterDirectExpressionMicrocohortFormatCounts_(counts) {
  return Object.keys(counts || {}).sort().map(function(key) {
    return key + ':' + counts[key];
  }).join('|');
}

function _providerCharacterDirectExpressionMicrocohortMin_(values) {
  if (!(values || []).length) return '';
  var out = null;
  for (var i = 0; i < values.length; i++) {
    var v = _numOrNull_(values[i]);
    if (v == null) continue;
    out = out == null ? v : Math.min(out, v);
  }
  return out == null ? '' : _round4_(out);
}

function _providerCharacterDirectExpressionMicrocohortMax_(values) {
  if (!(values || []).length) return '';
  var out = null;
  for (var i = 0; i < values.length; i++) {
    var v = _numOrNull_(values[i]);
    if (v == null) continue;
    out = out == null ? v : Math.max(out, v);
  }
  return out == null ? '' : _round4_(out);
}

function _providerCharacterDirectExpressionMicrocohortStdDev_(values) {
  if (!(values || []).length) return '';
  var nums = [];
  for (var i = 0; i < values.length; i++) {
    var v = _numOrNull_(values[i]);
    if (v != null) nums.push(Number(v));
  }
  if (!nums.length) return '';
  var mean = nums.reduce(function(a, b) { return a + b; }, 0) / nums.length;
  var variance = nums.reduce(function(acc, v) {
    var diff = v - mean;
    return acc + (diff * diff);
  }, 0) / nums.length;
  return _round4_(Math.sqrt(variance));
}

function _providerCharacterDirectExpressionValidationCountResult_(rows, result) {
  var count = 0;
  for (var i = 0; i < (rows || []).length; i++) {
    if (String((rows[i] || {}).reproducibility_result || '') === result) count += 1;
  }
  return count;
}

function _providerCharacterDirectExpressionValidationAverage_(values) {
  var sum = 0;
  var count = 0;
  for (var i = 0; i < (values || []).length; i++) {
    var v = _numOrNull_(values[i]);
    if (v == null) continue;
    sum += Number(v || 0);
    count += 1;
  }
  return count ? _round4_(sum / count) : '';
}

function _providerCharacterDirectExpressionValidationProviderStats_(providerStats) {
  var out = {};
  Object.keys(providerStats || {}).sort().forEach(function(provider) {
    var p = providerStats[provider] || {};
    out[provider] = {
      rows: Number(p.rows || 0),
      successes: Number(p.successes || 0),
      failures: Number(p.failures || 0),
      high_reproducibility: Number(p.high_reproducibility || 0),
      medium_reproducibility: Number(p.medium_reproducibility || 0),
      low_reproducibility: Number(p.low_reproducibility || 0),
      forecast_stable_expression_unstable: Number(p.forecast_stable_expression_unstable || 0),
      forecast_unstable_expression_stable: Number(p.forecast_unstable_expression_stable || 0),
      rerun_failed: Number(p.rerun_failed || 0),
      avg_overall_expression_similarity: p.similarity_count ? _round4_(Number(p.similarity_sum || 0) / Number(p.similarity_count || 1)) : '',
      avg_forecast_value_delta: p.forecast_delta_count ? _round4_(Number(p.forecast_delta_sum || 0) / Number(p.forecast_delta_count || 1)) : ''
    };
  });
  return out;
}
