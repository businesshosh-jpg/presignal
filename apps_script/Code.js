/*******************************************************
 * Code.gs
 * - Menus + high-level runners
 * - Enforces "no tab auto-creation" policy
 * - Calls applyBatchingForKeys_() from runner_rules_patch.gs
 * - Logs every run to the "log" tab via appendLog() (00_logging_shim.gs)
 *******************************************************/

var CFG = {
  SHEET_EVENT: 'Event',
  SHEET_PRED: 'Predictions',
  SHEET_LOG: 'log',
  FMP_API_KEY: '',
  FMP_BASE: 'https://financialmodelingprep.com/api/v3',

  // ↓ NEW: country scoping
  FMP_COUNTRY: 'US',             // attempt server-side filter if the endpoint supports it
  COUNTRY_FILTER: ['US'],         // always enforced locally after normalization

  SHEET_SERIESMAP_SUGGESTIONS: 'SeriesMap_Suggestions',
  SHEET_SERIESMAP: 'SeriesMap',
};


/** ===== UI Menu ===== **/
function onOpen() {
  var ui = SpreadsheetApp.getUi();

  var menu = ui.createMenu('PreSignal v1.4');

  // ① Events
  menu.addSubMenu(
    ui.createMenu('① Events')
      .addItem('Fetch & Upsert (next 72h)', 'menuUpsertNext72h_')
      .addItem('Fetch & Upsert (Config Window)', 'menuUpsertToEvent_')
      .addItem('Build SeriesMap Suggestions (Window / next 72h fallback)', 'menuSeriesMapBuildSuggestions_')
      .addItem('SeriesMap → Auto-suggest from FRED (Selected rows)', 'menuSeriesMapAutoSuggestFRED_')
      .addItem('Build FRED Series Catalog', 'menuBuildFredSeriesCatalog_')
      .addItem('Rebuild Suggestions from FMP Catalog', 'menuSeriesMapRebuildSuggestionsFromFmpCatalog_')
      .addItem('AI Review Suggestion Batch', 'menuSeriesMapAiReviewBatch_')
      .addItem('Promote Selected Suggestions → SeriesMap', 'menuSeriesMapPromoteSelected_')
  );

  // ② Predictions
  menu.addSubMenu(
    ui.createMenu('② Predictions')
      .addItem('Run Predictions (All Providers)', 'menuRunPredictionsAll_')
      .addItem('Run Predictions (Config Window)', 'menuRunPredictionsWindow_')
      .addItem('Resume Predictions', 'runPredictionsResume_')
      .addSeparator()
      .addItem('Gemini (manual)', 'menuRunPredictionsGemini_')
      .addItem('OpenAI (manual)', 'menuRunPredictionsOpenAI_')
      .addItem('Claude (manual)', 'menuRunPredictionsClaude_')
      .addSeparator()
      .addItem('Clear Prediction Checkpoint', 'menuClearPredictionCheckpoint_')
  );

  // ③ Actuals
  menu.addSubMenu(
    ui.createMenu('③ Actuals')
      .addItem('Start Hourly Actuals Fetch', 'menuActualsStartHourly_')
      .addItem('Stop Hourly Actuals Fetch', 'menuActualsStopHourly_')
      .addItem('Fetch Actuals (Config Window)', 'menuActualsConfigWindowFetch_')
  );

  // ④ Market Reaction
  menu.addSubMenu(
    ui.createMenu('④ Market Reaction')
      .addItem('Score Market Reaction (past 24h)', 'scoreMarketReactionPast24h_')
      .addItem('Score Market Reaction (Config Window)', 'scoreMarketReactionByConfigWindow_')
      .addItem('Build Evaluation Sheets', 'menuBuildEvaluationSheets_')
      .addItem('Debug Timestamp Sample', 'debugEventTimestampSample_')
  );

  // ⑤ Maintenance (must be last)
  menu.addSubMenu(
    ui.createMenu('⑤ Maintenance')
      .addItem('Backfill Missing Actuals', 'menuMaintenanceBackfillActuals_')
      .addItem('Backfill Market Reaction', 'menuMaintenanceBackfillMarketReaction_')
      .addItem('Build Outcome Ledger', 'menuBuildOutcomeLedgerSheet_')
      .addItem('Build Outcome Summaries', 'menuBuildOutcomeSummaries_')
      .addItem('Build Attention Factor Summary', 'menuBuildAttentionFactorSummary_')
      .addItem('Build Provider Character Diagnostics', 'menuBuildProviderCharacterDiagnostics_')
      .addItem('Build Attention Provider Individuality', 'menuBuildAttentionProviderIndividuality_')
      .addItem('Build Attention Evidence Report', 'menuBuildAttentionEvidenceReport_')
      .addItem('Build Attention Block Stability', 'menuBuildAttentionBlockStability_')
      .addItem('Build Attention Disagreement Review', 'menuBuildAttentionDisagreementReview_')
      .addItem('Build Attention Disagreement Summary', 'menuBuildAttentionDisagreementSummary_')
      .addItem('Build Attention Phase3 Candidates', 'menuBuildAttentionPhase3Candidates_')
      .addItem('Build Attention Shadow Experiments', 'menuBuildAttentionShadowExperiments_')
      .addItem('Build Family Structure Report', 'menuBuildFamilyStructureReport_')
      .addItem('Build Outcome Diagnostics', 'menuBuildOutcomeDiagnostics_')
      .addItem('Rebuild Logs / Diagnostics', 'menuMaintenanceDiagnostics_')
      .addItem('System Health Check', 'menuMaintenanceHealthCheck_')
  );

  menu.addToUi();
}


/** ===== Menu entries ===== **/
function menuUpsertFmpUpcomingToEvent24h_() {
  _guardCoreTabsExist_(['Event', 'log']); // Predictions not needed for this pass
  _menuRunWrapper_(1);
}
function menuUpsertFmpUpcomingToEvent7d_() {
  _guardCoreTabsExist_(['Event', 'log']);
  _menuRunWrapper_(7);
}


/** Add menu handler for SeriesMap 2025-10-15 13:00 */
function menuSeriesMapBuildSuggestions_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = buildSeriesMapSuggestionsUsingWindow_();
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'SeriesMap → Build suggestions', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
  } catch (e) {
    if (typeof showErrorPopup_ === 'function') {
      showErrorPopup_('SeriesMap Suggestions — Error', (e && e.message) ? e.message : String(e));
    }
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'SeriesMap → Build suggestions failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuSeriesMapPromoteSelected_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = promoteSelectedSeriesMapSuggestions_();

    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'SeriesMap → Promote selected suggestions', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }

    ss.toast('Promoted=' + res.promoted + ' | Skipped=' + res.skipped + ' | Reason=' + (res.reason || 'ok'), 'SeriesMap', 8);
    return res;

  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'SeriesMap → Promote selected suggestions failed', {
        error: String(e && e.message || e),
        stack: String(e && e.stack || '')
      });
    }
    ss.toast('Promote failed: ' + String(e && e.message || e), 'SeriesMap', 10);
    throw e;
  }
}

function menuSeriesMapRebuildSuggestionsFromFmpCatalog_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = rebuildSeriesMapSuggestionsFromFmpCatalog_({
      clearExisting: true,
      notesPrefix: 'FMP_CATALOG_V1'
    });

    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'SeriesMap → Rebuild suggestions from FMP catalog', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }

    SpreadsheetApp.getActive().toast(
      'SeriesMap FMP rebuild: rebuilt=' + (res.rebuilt || 0) +
      ', filtered=' + (res.filtered_out || 0) +
      ', review=' + (res.review_only || 0),
      'SeriesMap',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'SeriesMap → Rebuild suggestions from FMP catalog failed', {
        error: String(e && e.message || e),
        stack: String(e && e.stack || ''),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuSeriesMapAiReviewBatch_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = reviewSeriesMapSuggestionsBatch_({
      batchSize: 12
    });

    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'SeriesMap → AI review batch', {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }

    SpreadsheetApp.getActive().toast(
      'SeriesMap AI batch: reviewed=' + (res.reviewed || 0) +
      ', suggested=' + (res.suggested || 0) +
      ', remaining=' + (res.remaining_uncertain || 0),
      'SeriesMap',
      8
    );
    return res;
  } catch (e) {
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'SeriesMap → AI review batch failed', {
        error: String(e && e.message || e),
        stack: String(e && e.stack || ''),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}


function menuRunPredictionsAll_(){          return menuPredDispatch_('all'); }
function menuRunPredictionsWindow_(){       return menuPredDispatch_('window'); }
function menuRunPredictionsGemini_(){       return menuPredDispatch_('gemini'); }
function menuRunPredictionsOpenAI_(){       return menuPredDispatch_('openai'); }
function menuRunPredictionsClaude_(){       return menuPredDispatch_('claude'); }
function runPredictionsAll_(){          return menuPredDispatch_('all'); }
function runPredictionsWindow(){        return menuPredDispatch_('window'); }

function menuPredDispatch_(mode){
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res;
    if (String(mode || '').toLowerCase() === 'all') {
      res = (typeof runPredictionsCore_ === 'function')
        ? runPredictionsCore_({ windowMinBeforeMin: 24*60, windowMaxAfterMin: 36*60, providers: CFG.PROVIDERS })
        : runPredictionsAll_();
    } else if (String(mode || '').toLowerCase() === 'window') {
      res = (typeof runPredictionsUsingWindow_ === 'function')
        ? runPredictionsUsingWindow_()
        : runPredictionsCore_({ windowMinBeforeMin: CFG.WINDOW_MIN_BEFORE_MIN, windowMaxAfterMin: CFG.WINDOW_MAX_AFTER_MIN, providers: CFG.PROVIDERS });
    } else if (String(mode || '').toLowerCase() === 'gemini') {
      res = runPredictionsCore_({ windowMinBeforeMin: 24*60, windowMaxAfterMin: 36*60, providers: ['Gemini'] });
    } else if (String(mode || '').toLowerCase() === 'openai') {
      res = runPredictionsCore_({ windowMinBeforeMin: 24*60, windowMaxAfterMin: 36*60, providers: ['OpenAI'] });
    } else if (String(mode || '').toLowerCase() === 'claude') {
      res = runPredictionsCore_({ windowMinBeforeMin: 24*60, windowMaxAfterMin: 36*60, providers: ['Anthropic'] });
    } else {
      throw new Error('Unknown prediction mode: ' + mode);
    }
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Predictions → ' + String(mode||'all').toUpperCase(), {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    if (typeof flushLogs_ === 'function') flushLogs_();
    SpreadsheetApp.getActive().toast(
      'Predictions (' + String(mode||'all').toUpperCase() + '): status=' + String((res && res.status) || 'ok') +
      ', inspected=' + Number((res && res.inspected) || 0) +
      ', created=' + Number((res && res.created) || 0) +
      ', updated=' + Number((res && res.updated) || 0) +
      ', errors=' + Number((res && res.errors) || 0),
      'Predictions',
      8
    );
    return res;
  } catch (e) {
    if (typeof showErrorPopup_ === 'function') {
      showErrorPopup_('Predictions — Error', (e && e.message) ? e.message : String(e));
    }
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Predictions → ' + String(mode||'all').toUpperCase() + ' failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    if (typeof flushLogs_ === 'function') flushLogs_();
    throw e;
  }
}

function menuActualsManualFetch_(){
  return menuActualsConfigWindowFetch_();
}

function menuActualsConfigWindowFetch_(){
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var cap = 2000;
    var used = { mode: 'fallback:lookback24h' };
    var res;

    var win = (typeof resolveWindow_ === 'function') ? resolveWindow_('actuals_manual') : null;
    if (win && win.windowEnabled && win.fromUtcIso && win.toUtcIso) {
      used = { mode: 'config_window', fromUtcIso: win.fromUtcIso, toUtcIso: win.toUtcIso, note: win.note||'' };
      res = (typeof runFetchActualsWindowBounds_ === 'function')
        ? runFetchActualsWindowBounds_(win.fromUtcIso, win.toUtcIso, cap)
        : (function(){ throw new Error('runFetchActualsWindowBounds_ not found in actuals_fetcher.gs'); })();
    } else {
      res = (typeof runFetchActualsWindow_ === 'function')
        ? runFetchActualsWindow_(24*60, 0, cap)
        : (function(){ throw new Error('runFetchActualsWindow_ not found in actuals_fetcher.gs'); })();
    }

    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Actuals → Config Window fetch', {
        window_used: used,
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    SpreadsheetApp.getActive().toast(
    'Actuals config window: inspected=' + (res.inspected||0) +
    ', updated=' + (res.updated||0) +
    ', released=' + (res.released||0) +
    ', revised=' + (res.revised||0),
    'Actuals',
    8
    );
  } catch (e) {
    if (typeof showErrorPopup_ === 'function') {
      showErrorPopup_('Actuals Config Window — Error', (e && e.message) ? e.message : String(e));
    }
    throw e;
  }
}

function menuActualsStartHourly_(){
  // Creates an hourly installable trigger to call the Config Window actuals fetch.
  var fn = 'menuActualsConfigWindowFetch_';
  var legacyFn = 'menuActualsManualFetch_';
  // De-dupe existing triggers
  var triggers = ScriptApp.getProjectTriggers() || [];
  for (var i=0;i<triggers.length;i++){
    var handler = triggers[i].getHandlerFunction && triggers[i].getHandlerFunction();
    if (handler === fn || handler === legacyFn) {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger(fn).timeBased().everyHours(1).create();
  SpreadsheetApp.getActive().toast('Actuals: Hourly automation started', 'Actuals', 5);
}

function menuActualsStopHourly_(){
  var fn = 'menuActualsConfigWindowFetch_';
  var legacyFn = 'menuActualsManualFetch_';
  var triggers = ScriptApp.getProjectTriggers() || [];
  var removed = 0;
  for (var i=0;i<triggers.length;i++){
    var handler = triggers[i].getHandlerFunction && triggers[i].getHandlerFunction();
    if (handler === fn || handler === legacyFn) {
      ScriptApp.deleteTrigger(triggers[i]);
      removed++;
    }
  }
  SpreadsheetApp.getActive().toast('Actuals: Stopped ' + removed + ' trigger(s)', 'Actuals', 5);
}




/**
 * Guard: check that required tabs exist; throw if missing (policy).
 */
function _guardCoreTabsExist_(names) {
  var ss = SpreadsheetApp.getActive();
  names.forEach(function(n){
    if (!ss.getSheetByName(n)) {
      throw new Error('Required sheet "' + n + '" is missing. Create it first (policy: no auto-creation).');
    }
  });
}

/**
 * Wrap a full run:
 *  1) fetch/normalize/upsert (fmp_calendar.gs)
 *  2) apply post-pass batching (runner_rules_patch.gs)
 *  3) log + toast
 */
function _menuRunWrapper_(days) {
  var started = new Date();
  var summary = null, postSummary = null, err = null;

  try {
    // Step 1: upsert normalized rows using fallback key
    summary = runFmpUpcomingToEvent_(days); // from fmp_calendar.gs

    // Step 2: authoritative post-pass to fill event_id/batch_id/type
    // (function lives in runner_rules_patch.gs; we assume you still have that file)
    if (typeof applyBatchingForKeys_ !== 'function') {
      throw new Error('applyBatchingForKeys_() not found. Ensure runner_rules_patch.gs is present.');
    }
    postSummary = applyBatchingForKeys_(); // returns a count object if you implemented it that way (optional)

    // Step 3: log + toast
    var ctx = {
      phase: 'FMP upcoming → Event',
      days_ahead: days,
      fetched: summary.fetched,
      appended: summary.appended,
      upserts: summary.upserts,
      skipped: summary.skipped,
      skipped_reasons: summary.skipped_reasons || {},
      post_pass: postSummary || {},
      duration_ms: (new Date()) - started
    };
    _logInfo_('FMP upcoming → Event summary', ctx);
    _toast_('FMP upcoming → Event: fetched=' + summary.fetched +
            ', appended=' + summary.appended +
            ', upserts=' + summary.upserts +
            ', skipped=' + summary.skipped);

  } catch (e) {
    err = String(e && e.message ? e.message : e);
    _logError_('FMP upcoming → Event failed', { days_ahead: days, error: err });
    _toast_('FMP upcoming → Event failed: ' + err);
    throw e; // surface to UI
  }
}


/** 
 * Actuals fetch  
 * Create hourly trigger for actuals 
 */
function menuStartActualsAutomation_() {
  // Avoid duplicates: if a trigger for this function exists, keep one
  var fn = 'runFetchActualsHourly_';
  var existing = ScriptApp.getProjectTriggers().filter(function(t){
    return t.getHandlerFunction && t.getHandlerFunction() === fn;
  });
  if (existing.length === 0) {
    ScriptApp.newTrigger(fn).timeBased().everyHours(1).atMinute(10).create(); // :10 each hour
  }
  SpreadsheetApp.getActive().toast('Hourly actuals automation is ON', 'Automation', 5);
}

/** Remove hourly trigger for actuals **/
function menuStopActualsAutomation_() {
  var fn = 'runFetchActualsHourly_';
  ScriptApp.getProjectTriggers().forEach(function(t){
    if (t.getHandlerFunction && t.getHandlerFunction() === fn) {
      ScriptApp.deleteTrigger(t);
    }
  });
  SpreadsheetApp.getActive().toast('Hourly actuals automation is OFF', 'Automation', 5);
}

/** Manual: fetch actuals for past 24h **/
function menuRunActualsPast24h_() {
  try {
    var res = runFetchActualsWindow_(24*60, 0, 1000); // minutesBack, minutesAhead, maxScan
    showErrorPopup_(
      'Actuals (past 24h) complete',
      (res
        ? 'inspected=' + res.inspected +
          '\nupdated='   + res.updated +
          '\nreleased='  + res.released +
          '\nrevised='   + res.revised +
          '\nfrom='      + res.window_from +
          '\nto='        + res.window_to
        : 'Completed.')
    );
  } catch (err) {
    showErrorPopup_('Actuals Error (past 24h)', String(err && err.message || err) + '\n\n' + (err && err.stack || ''));
  }
}

/** Manual: fetch actuals for past 7d **/
function menuRunActualsPast7d_() {
  try {
    var res = runFetchActualsWindow_(7*24*60, 0, 2000);
    showErrorPopup_(
      'Actuals (past 7d) complete',
      (res
        ? 'inspected=' + res.inspected +
          '\nupdated='   + res.updated +
          '\nreleased='  + res.released +
          '\nrevised='   + res.revised +
          '\nfrom='      + res.window_from +
          '\nto='        + res.window_to
        : 'Completed.')
    );
  } catch (err) {
    showErrorPopup_('Actuals Error (past 7d)', String(err && err.message || err) + '\n\n' + (err && err.stack || ''));
  }
}


/** add the new menu handler (uses config if present) 2025-10-15 13:00 **/
/**
 * Action → Upsert to Event
 * Uses config window if available (config.gs → resolveWindow_),
 * otherwise defaults to next 7 days (upcoming).
 */

/**
 * Events → Fetch & Upsert (next 72h)
 * v1.4 control-plane wrapper: MUST bypass Config windowing.
 * Uses upcoming 3 days (72h) in UTC, then applies batching patch.
 */
function menuUpsertNext72h_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    // Hard window: upcoming 72h (3 days) — do NOT call resolveWindow_ / Config.
    var res = runFmpUpcomingToEvent_(3);

    // Post-pass batching (type/event_id/batch_id)
    var patch = (typeof applyBatchingForKeys_ === 'function') ? applyBatchingForKeys_() : null;

    // Log
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Upsert (next 72h) finished', {
        window: { mode: 'upcoming', daysAhead: 3, note: 'next 72h (hard; bypass Config)' },
        result: res,
        batching: patch,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }

    var msg = 'Upsert 72h OK — fetched: ' + (res.fetched||0)
            + ', appended: ' + (res.appended||0)
            + ', upserts: ' + (res.upserts||0)
            + (patch ? (', batched: ' + (patch.assigned||0)) : '');
    SpreadsheetApp.getActive().toast(msg, 'Upsert (next 72h)', 7);
    return res;
  } catch (e) {
    if (typeof showErrorPopup_ === 'function') {
      showErrorPopup_('Upsert (next 72h) — Error', (e && e.message ? e.message : String(e)));
    } else {
      SpreadsheetApp.getUi().alert('Upsert (next 72h) — Error\n' + (e && e.message ? e.message : String(e)));
    }
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Upsert (next 72h) failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}

function menuUpsertToEvent_() {
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var usedWindow = null;
    var res;
    if (typeof resolveWindow_ === 'function') {
      var win = resolveWindow_('upsert_event'); // {fromUtcIso,toUtcIso,windowEnabled,tz,note}
      if (win && win.windowEnabled && win.fromUtcIso && win.toUtcIso) {
        usedWindow = win;
        res = runFmpRangeToEvent_(win.fromUtcIso, win.toUtcIso);
      }
    }
    if (!res) {
      // fallback: upcoming 7d
      res = runFmpUpcomingToEvent_(7);
    }

    // Post-pass batching (type/event_id/batch_id)
    var patch = (typeof applyBatchingForKeys_ === 'function') ? applyBatchingForKeys_() : null;

    // Log
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Upsert to Event finished', {
        window: usedWindow ? usedWindow : { default: 'upcoming 7d' },
        result: res,
        batching: patch,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }

    var msg = 'Upsert OK — fetched: ' + (res.fetched||0)
            + ', appended: ' + (res.appended||0)
            + ', upserts: ' + (res.upserts||0)
            + (patch ? (', batched: ' + (patch.assigned||0)) : '');
    SpreadsheetApp.getActive().toast(msg, 'Upsert to Event', 7);
  } catch (e) {
    if (typeof showErrorPopup_ === 'function') {
      showErrorPopup_('Upsert to Event — Error', (e && e.message ? e.message : String(e)));
    } else {
      SpreadsheetApp.getUi().alert('Upsert to Event — Error\n' + (e && e.message ? e.message : String(e)));
    }
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'error', 'Upsert to Event failed', {
        error: (e && e.stack) ? e.stack : String(e),
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    throw e;
  }
}


function menuDumpLast3Months_() {
  var rows = fetchEventsLast3Months_();
  Logger.log('found=%s', rows.length);
  rows.slice(0, 5).forEach(function(ev){
    Logger.log('%s | %s | %s', ev.country, ev.indicator_name, ev.release_ts);
  });
}/**
 * Return all Raw events whose release_ts is within [startIso, endIso] inclusive.
 * Expects ISO-8601 UTC timestamps (e.g., "2025-07-14T00:00:00Z").
 */
function fetchEventsInDateRangeUtc_(startIso, endIso) {
  if (!startIso || !endIso) return [];
  var start = new Date(startIso);
  var end   = new Date(endIso);
  if (isNaN(start.getTime()) || isNaN(end.getTime())) return [];

  function coerceIsoZ(s){
    s = String(s || '').trim();
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(s) && !/[Zz]|[+\-]\d{2}:\d{2}$/.test(s)) return s + 'Z';
    return s;
  }

  var all = (typeof _readEventAsObjects_ === 'function') ? _readEventAsObjects_() : [];
  var out = [];
  for (var i = 0; i < all.length; i++) {
    var ev = all[i];
    var t = new Date(coerceIsoZ(ev.release_ts));
    if (isNaN(t.getTime())) continue;
    var ms = t.getTime();
    if (ms >= start.getTime() && ms <= end.getTime()) out.push(ev);
  }
  return out;
}



/**
 * Compute a fixed 3-month UTC window ending "now" (calendar months, not 90d).
 * Returns { startIso, endIso } in ISO-8601 Z.
 */
function computeFixed3MonthWindowUtc_() {
  var now = new Date();
  var end = new Date(now.getTime());
  var start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 3, now.getUTCDate(), 0, 0, 0));
  return { startIso: start.toISOString(), endIso: end.toISOString() };
}




/** ===== Logging helpers (00_logging_shim.gs provides appendLog) ===== **/

function _logInfo_(msg, ctx) {
  try {
    var sh = SpreadsheetApp.getActive().getSheetByName(CFG.SHEET_LOG);
    if (!sh) throw new Error('log sheet missing');
    if (typeof appendLog === 'function') {
      appendLog(sh, 'info', msg, ctx || {});
    } else {
      // Fallback minimal log
      sh.appendRow([ new Date().toISOString(), 'info', msg, JSON.stringify(ctx || {}) ]);
    }
  } catch (e) {
    // Swallow logging errors to not break core flow
  }
}

function _logWarn_(msg, ctx) {
  try {
    var sh = SpreadsheetApp.getActive().getSheetByName(CFG.SHEET_LOG);
    if (!sh) throw new Error('log sheet missing');
    if (typeof appendLog === 'function') {
      appendLog(sh, 'warn', msg, ctx || {});
    } else {
      sh.appendRow([ new Date().toISOString(), 'warn', msg, JSON.stringify(ctx || {}) ]);
    }
  } catch (e) {}
}

function _logError_(msg, ctx) {
  try {
    var sh = SpreadsheetApp.getActive().getSheetByName(CFG.SHEET_LOG);
    if (!sh) throw new Error('log sheet missing');
    if (typeof appendLog === 'function') {
      appendLog(sh, 'error', msg, ctx || {});
    } else {
      sh.appendRow([ new Date().toISOString(), 'error', msg, JSON.stringify(ctx || {}) ]);
    }
  } catch (e) {}
}

/** ===== Small UI helper ===== **/
function _toast_(s) {
  try {
    SpreadsheetApp.getActive().toast(s, 'Status', 6);
  } catch (e) {}
}



/**
 * Return the Raw sheet using CFG.SHEET_RAW_PRIMARY with fallback to CFG.SHEET_RAW_FALLBACK.
 */
/**
 * Return the Event sheet. We no longer use RawCalendar.
 * Honors CFG.SHEET_EVENT when present; defaults to "Event".
 * Verifies core headers exist.
 */
function _getEventSheet_() {
  var ss = SpreadsheetApp.getActive();
  var name = (typeof CFG !== 'undefined' && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event';
  var sh = ss.getSheetByName(name);
  if (!sh) throw new Error('Event sheet not found: tried "' + name + '"');

  // Basic header sanity check (at least: country, indicator_name, release_ts)
  var values = sh.getDataRange().getValues();
  if (!values || values.length < 1) {
    throw new Error('Event sheet "' + name + '" is empty.');
  }
  var header = (values[0] || []).map(function(h){ return String(h || '').trim().toLowerCase(); });
  ['country','indicator_name','release_ts'].forEach(function(req){
    if (header.indexOf(req) === -1) {
      throw new Error('Event sheet "' + name + '" is missing required header: ' + req);
    }
  });
  return sh;
}

/**
 * Backward-compatible shim: old code that calls _getRawSheet_ will now
 * get the Event sheet. (Keeps other modules working without refactors.)
 */
function _getRawSheet_() {
  return _getEventSheet_();
}


function _getEventSheet_() {
  var ss = SpreadsheetApp.getActive();
  var name = (typeof CFG !== 'undefined' && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event';
  var sh = ss.getSheetByName(name);
  if (!sh) throw new Error('Event sheet not found: tried "' + name + '"');
  return sh;
}




/**
 * Read all rows from Event and map headers to objects.
 */
function _readEventAsObjects_() {
  var sh = _getEventSheet_();
  var values = sh.getDataRange().getValues();
  if (!values || values.length < 2) return [];

  var header = values[0].map(function(h){ return String(h || '').trim(); });
  var idx = {};
  header.forEach(function(h, i){ idx[String(h).trim()] = i; });

  function pick(row, name) {
    var i = idx[name];
    return (i == null ? '' : row[i]);
  }
  function pickFirst(row, names) {
    for (var i=0;i<names.length;i++){
      var v = pick(row, names[i]);
      if (v !== '' && v != null) return v;
    }
    return '';
  }
  function toIsoZ(val) {
    if (val instanceof Date) return new Date(val.getTime()).toISOString();
    if (typeof val === 'number') {
      var ms = (val - 25569) * 86400 * 1000;
      return new Date(ms).toISOString();
    }
    var s = String(val || '').trim();
    if (!s) return '';
    if (/^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$/.test(s) && !/[Zz]|[+\-]\d{2}:\d{2}$/.test(s)) {
      if (s.indexOf('T') < 0 && s.indexOf(' ') > 0) s = s.replace(' ', 'T');
      if (s.length === 10) s += 'T00:00:00';
      return s + 'Z';
    }
    return s;
  }

  var out = [];
  for (var r = 1; r < values.length; r++) {
    var row = values[r];
    var releaseTs = toIsoZ(pickFirst(row, ['release_ts','datetime','date','time']));
    var indicator  = String(pickFirst(row, ['indicator_name','indicator'])).trim();
    var country    = String(pick(row, 'country') || '').trim().toUpperCase();
    if (!releaseTs || !indicator || !country) continue;

    out.push({
      country: country,
      indicator_name: indicator,
      release_ts: releaseTs,
      event_id: String(pick(row, 'event_id') || '').trim(),
      importance: String(pick(row, 'importance') || '').trim(),
      source_cal: String(pick(row, 'source_cal') || '').trim()
    });
  }
  return out;
}


/**
 * show error on popup
 */
function showErrorPopup_(title, msg) {
  try {
    var ui = SpreadsheetApp.getUi();
    ui.alert(title, msg, ui.ButtonSet.OK);
  } catch (err) {
    // fallback if no UI context
    SpreadsheetApp.getActive().toast(title + ': ' + msg, 'Error', 8);
  }
}


/**
 * Fetch Raw events that occurred between now-<months> and now (UTC).
 * @param {number} months - how many calendar months to look back (default 3)
 * @return {Array<Object>} filtered events
 */
function fetchEventsInLastMonths_(months) {
  months = (months == null ? 3 : months);
  var now = new Date();
  // Start = now minus N calendar months (preserves day-of-month when possible)
  var start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - months, now.getUTCDate(), 0, 0, 0));
  var end   = now; // up to "now"

  var all = _readRawAsObjects_();
  var out = [];
  for (var i = 0; i < all.length; i++) {
    var ev = all[i];
    var t = new Date(ev.release_ts); // ISO expected
    if (isNaN(t.getTime())) continue;
    // Keep events where start <= release_ts <= now (compare UTC)
    if (t.getTime() >= start.getTime() && t.getTime() <= end.getTime()) {
      out.push(ev);
    }
  }
  return out;
}

/**
 * Convenience wrapper: exactly last 3 months.
 */
function fetchEventsLast3Months_() {
  return fetchEventsInLastMonths_(3);
}


/** ===== v1.4 Menu Maintenance Wrappers (control-plane only) ===== **/

function menuMaintenanceBackfillActuals_() {
  if (typeof fetchActualsIgnoreWindowOnce !== 'function') {
    _maintenanceLog_('ERROR', 'Maintenance: backfill actuals function missing', { fn: 'fetchActualsIgnoreWindowOnce' });
    throw new Error('Missing function: fetchActualsIgnoreWindowOnce');
  }
  _maintenanceLog_('INFO', 'Maintenance: backfill missing actuals start', {});
  return fetchActualsIgnoreWindowOnce();
}

function menuMaintenanceBackfillMarketReaction_() {
  if (typeof scoreMarketReactionByConfigWindow_ !== 'function') {
    _maintenanceLog_('ERROR', 'Maintenance: market reaction scorer missing', { fn: 'scoreMarketReactionByConfigWindow_' });
    throw new Error('Missing function: scoreMarketReactionByConfigWindow_');
  }
  _maintenanceLog_('INFO', 'Maintenance: backfill market reaction start (Config Window)', {});
  return scoreMarketReactionByConfigWindow_();
}

function menuMaintenanceDiagnostics_() {
  // Non-destructive: just emit a few safe checks + log completion.
  var report = {
    hasEventSheet: !!SpreadsheetApp.getActive().getSheetByName((CFG && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event'),
    hasPredSheet:  !!SpreadsheetApp.getActive().getSheetByName((CFG && CFG.SHEET_PRED) ? CFG.SHEET_PRED : 'Predictions'),
    hasLogSheet:   !!SpreadsheetApp.getActive().getSheetByName((CFG && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log'),
    hasAppendLog:  (typeof appendLog === 'function'),
    hasProvidersResolver: (typeof _resolveProviders_ === 'function'),
    ts: new Date().toISOString()
  };

  _maintenanceLog_('INFO', 'Maintenance: diagnostics report', report);
  SpreadsheetApp.getUi().alert('Diagnostics complete. See log for details.');
  return report;
}

function menuMaintenanceHealthCheck_() {
  var ss = SpreadsheetApp.getActive();

  var requiredSheets = [
    (CFG && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event',
    (CFG && CFG.SHEET_PRED)  ? CFG.SHEET_PRED  : 'Predictions',
    (CFG && CFG.SHEET_LOG)   ? CFG.SHEET_LOG   : 'log'
  ];

  var missing = requiredSheets.filter(function(n){ return !ss.getSheetByName(n); });

  // Check for core entrypoints (presence only; no logic changes)
  var missingFns = [];
  [
    'menuUpsertToEvent_',
    'menuPredAll_',
    'runPredictionsWindow',
    'menuActualsStartHourly_',
    'menuActualsConfigWindowFetch_',
    'menuActualsManualFetch_',
    'scoreMarketReactionPast24h_',
    'scoreMarketReactionByConfigWindow_'
  ].forEach(function(fn){
    var G = (typeof globalThis !== 'undefined') ? globalThis : this;
    if (typeof G[fn] !== 'function') missingFns.push(fn);
  });

  // Key presence (do not reveal values)
  var keyFlags = {
    hasFmpKey: !!((CFG && CFG.FMP_API_KEY) ? String(CFG.FMP_API_KEY).trim() : ''),
    hasAnyAiKey: (typeof _getKey_ === 'function') ? !!_getKey_(['GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_AI_STUDIO_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY']) : null
  };

  var ok = (missing.length === 0 && missingFns.length === 0);

  var payload = {
    ok: ok,
    missingSheets: missing,
    missingFunctions: missingFns,
    keyFlags: keyFlags,
    ts: new Date().toISOString()
  };

  _maintenanceLog_('INFO', 'Maintenance: health check', payload);

  SpreadsheetApp.getUi().alert(
    ok
      ? 'System Health Check: OK\n(Details in log)'
      : 'System Health Check: NOT OK\nMissing sheets: ' + JSON.stringify(missing) + '\nMissing functions: ' + JSON.stringify(missingFns) + '\n(Details in log)'
  );

  return payload;
}

function _maintenanceLog_(level, message, context) {
  try {
    // Prefer your stable logger
    if (typeof appendLog === 'function') {
      appendLog(level, message, context || {});
      return;
    }
  } catch (e) {}

  try {
    Logger.log(level + ': ' + message + ' ' + JSON.stringify(context || {}));
  } catch (e2) {}
}
