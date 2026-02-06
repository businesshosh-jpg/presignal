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
  SHEET_SERIESMAP_PROPOSALS: 'SeriesMap_Proposals',
  SHEET_SERIESMAP: 'SeriesMap',

    // SeriesMap triage (Proposals) mode:
  // - 'MANUAL' (default): create PENDING_MANUAL rows + show copy/paste triage pack (off-API)
  // - 'GPT52': call OpenAI with the model name below (future)
  SERIESMAP_TRIAGE_MODE: 'MANUAL',
  // Future: set this when you actually enable GPT-5.2 via API
  SERIESMAP_TRIAGE_OPENAI_MODEL: 'gpt-5.2',
  // Hard guard: proposals must NOT fall back to other models
  SERIESMAP_TRIAGE_ALLOW_FALLBACK_MODELS: false,
};


/** ===== UI Menu ===== **/
function onOpen() {
  var ui = SpreadsheetApp.getUi();

  var menu = ui.createMenu('PreSignal v1.3');

  // ① Events
  menu.addSubMenu(
    ui.createMenu('① Events')
      .addItem('Fetch & Upsert (next 72h)', 'menuUpsertNext72h_')
      .addItem('Build SeriesMap Suggestions (Window / next 72h fallback)', 'menuSeriesMapBuildSuggestions_')
      .addItem('SeriesMap → Auto-suggest from FRED (Selected rows)', 'menuSeriesMapAutoSuggestFRED_')
      .addItem('SeriesMap → Generate Proposals from Selected Suggestions', 'menuSeriesMapGenerateProposalsSelected_')
      .addItem('Promote Selected Suggestions → SeriesMap', 'menuSeriesMapPromoteSelected_')
  );

  // ② Predictions
  menu.addSubMenu(
    ui.createMenu('② Predictions')
      .addItem('Run Predictions (All Providers)', 'runPredictionsAll_')
      .addItem('Run Predictions (Config Window)', 'runPredictionsWindow')
      .addSeparator()
      .addItem('Gemini (manual)', 'menuRunPredictionsGemini_')
      .addItem('OpenAI (manual)', 'menuRunPredictionsOpenAI_')
      .addItem('Claude (manual)', 'menuRunPredictionsClaude_')
  );

  // ③ Actuals
  menu.addSubMenu(
    ui.createMenu('③ Actuals')
      .addItem('Start Hourly Actuals Fetch', 'menuActualsStartHourly_')
      .addItem('Stop Hourly Actuals Fetch', 'menuActualsStopHourly_')
      .addItem('Fetch Actuals (Manual)', 'menuActualsManualFetch_')
  );

  // ④ Market Reaction
  menu.addSubMenu(
    ui.createMenu('④ Market Reaction')
      .addItem('Score Market Reaction (past 24h)', 'scoreMarketReactionPast24h_')
      .addItem('Score Market Reaction (Config Window)', 'scoreMarketReactionByConfigWindow_')
      .addItem('Debug Timestamp Sample', 'debugEventTimestampSample_')
  );

  // ⑤ Maintenance (must be last)
  menu.addSubMenu(
    ui.createMenu('⑤ Maintenance')
      .addItem('Backfill Missing Actuals', 'menuMaintenanceBackfillActuals_')
      .addItem('Backfill Market Reaction', 'menuMaintenanceBackfillMarketReaction_')
      .addItem('Rebuild Logs / Diagnostics', 'menuMaintenanceDiagnostics_')
      .addItem('System Health Check', 'menuMaintenanceHealthCheck_')
  );

  menu.addToUi();
}


/**
 * Shared worker used by:
 *  - hourly trigger: runFetchActualsHourly_() → calls this with ACTUALS_CFG defaults
 *  - manual menu actions: pass custom lookback/lookahead/rowCap windows
 */
function runFetchActualsWindow_(lookbackMinutes, lookaheadMinutes, rowCap) {
  var ss = SpreadsheetApp.getActive();
  var EVENT = (typeof CFG !== 'undefined' && CFG.SHEET_EVENT) ? CFG.SHEET_EVENT : 'Event';
  var LOG   = (typeof CFG !== 'undefined' && CFG.SHEET_LOG)   ? CFG.SHEET_LOG   : 'log';

  var shEvent = ss.getSheetByName(EVENT);
  var shLog   = ss.getSheetByName(LOG);
  if (!shEvent || !shLog) throw new Error('Missing required sheet: Event or log');

  var started = new Date();
  _log_(shLog, 'info', 'Actuals: scan start (window)', {
    lookbackMinutes: lookbackMinutes,
    lookaheadMinutes: lookaheadMinutes,
    rowCap: rowCap
  });

  // Headers + body
  var headers = _getHeaderNames_(shEvent);
  var H = _buildHeaderIndex_(headers);
  var lastRow = shEvent.getLastRow(), lastCol = shEvent.getLastColumn();
  if (lastRow < 2 || lastCol < 1) {
    _log_(shLog, 'info', 'Actuals: Event empty', {});
    return;
  }
  var data = shEvent.getRange(2, 1, lastRow - 1, lastCol).getValues();

  // Time window
  var now = new Date();
  var lo  = new Date(now.getTime() - (Number(lookbackMinutes) || 0) * 60 * 1000);
  var hi  = new Date(now.getTime() + (Number(lookaheadMinutes) || 0) * 60 * 1000);

  // Load SeriesMap (ok if missing; we just skip those rows and log a warn)
  var seriesMap = (typeof _loadSeriesMap_ === 'function') ? _loadSeriesMap_() : [];

  // Select candidates
  var candIdx = [];
  for (var i = 0; i < data.length; i++) {
    var row = data[i];
    var status = String(row[H('release_status')] || '').toLowerCase();
    var rel = row[H('release_ts')];
    var relDate = (rel instanceof Date) ? rel : new Date(String(rel || ''));
    if (String(relDate) === 'Invalid Date') continue;

    if (status === 'scheduled') {
      if (relDate >= lo && relDate <= hi) candIdx.push(i);
    } else if (status === 'released' || status === 'revised') {
      // re-check within lookback to catch revisions
      if (relDate >= lo) candIdx.push(i);
    }
  }

  // Cap rows per run
  var cap = Number(rowCap || 0);
  if (cap > 0 && candIdx.length > cap) candIdx = candIdx.slice(0, cap);

  var updated = 0, released = 0, revised = 0;
  var pending = {}; // i -> updates

  // Process candidates
  for (var k = 0; k < candIdx.length; k++) {
    var idx = candIdx[k];
    var r = data[idx];

    var event_id       = String(r[H('event_id')] || '');
    var indicator_name = String(r[H('indicator_name')] || '');
    var country        = String(r[H('country')] || '').toUpperCase();
    var release_ts     = r[H('release_ts')];
    if (!event_id || !indicator_name || !release_ts) continue;

    // Resolve provider/series/transform
    var map = (typeof _resolveSeriesForEvent_ === 'function')
      ? _resolveSeriesForEvent_(seriesMap, indicator_name, country)
      : null;
    if (!map) {
      _log_(shLog, 'warn', 'Actuals: No SeriesMap match', { event_id: event_id, indicator_name: indicator_name, country: country });
      continue;
    }

    // Reference period (month end heuristic)
    var ref = (typeof _refMonthEnd_ === 'function') ? _refMonthEnd_(release_ts) : new Date(release_ts);

    // Fetch from providers (FRED-first, then FMP, etc.)
    var res = (typeof _fetchActualFromProviders_ === 'function')
      ? _fetchActualFromProviders_({
          provider: map.provider,
          series_id: map.series_id,
          transform: map.transform,
          freq: map.freq || '',
          ref: ref,
          event_id: event_id,
          indicator_name: indicator_name
        })
      : { hasActual: false };

    if (!res || !res.hasActual) continue;

    // Current state
    var currentStatus = String(r[H('release_status')] || '').toLowerCase();
    var newStatus = (currentStatus === 'scheduled') ? 'released' : currentStatus;

    // Revision detection
    var previousVal = r[H('released_value')];
    var prevNum = (previousVal === '' || previousVal === null || previousVal === undefined) ? null : Number(previousVal);
    var isDiff = (prevNum === null && (res.value === 0 || res.value)) ||
                 (prevNum !== null && (Number(prevNum).toFixed(10) !== Number(res.value || '').toFixed(10)));
    if (currentStatus === 'released' || currentStatus === 'revised') {
      if (isDiff) newStatus = 'revised';
    }

    // Stage updates
    pending[idx] = {
      released_value: (res.value === 0 || res.value) ? Number(res.value) : '',
      released_ts: res.ts ? _parseReleaseTsUtcMinute_(res.ts) : (r[H('released_ts')] || ''),
      source_provider: res.provider || map.provider || '',
      source_series_id: res.series_id || map.series_id || '',
      transform: res.transform || map.transform || '',
      release_status: newStatus
    };

    updated++;
    if (newStatus === 'released') released++;
    if (newStatus === 'revised')  revised++;
  }

  // Apply updates
  var keys = Object.keys(pending);
  if (keys.length) {
    for (var x = 0; x < keys.length; x++) {
      var i = Number(keys[x]);
      var upd = pending[i];
      if (H.has('released_value'))  data[i][H('released_value')]  = upd.released_value;
      if (H.has('released_ts'))     data[i][H('released_ts')]     = upd.released_ts;
      if (H.has('source_provider')) data[i][H('source_provider')] = upd.source_provider;
      if (H.has('source_series_id'))data[i][H('source_series_id')]= upd.source_series_id;
      if (H.has('transform'))       data[i][H('transform')]       = upd.transform;
      if (H.has('release_status'))  data[i][H('release_status')]  = upd.release_status;
    }
    shEvent.getRange(2, 1, data.length, lastCol).setValues(data);
    SpreadsheetApp.flush();
  }

  _log_(shLog, 'info', 'Actuals: scan done (window)', {
    inspected: candIdx.length, updated: updated, released: released, revised: revised,
    window_from: lo.toISOString(), window_to: hi.toISOString(), duration_ms: (new Date()) - started
  });
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


function menuRunPredictionsGemini_(){       return menuPredDispatch_('gemini'); }
function menuRunPredictionsOpenAI_(){       return menuPredDispatch_('openai'); }
function menuRunPredictionsClaude_(){       return menuPredDispatch_('claude'); }
function runPredictionsAll_(){          return menuPredDispatch_('all'); }

function menuPredDispatch_(mode){
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    var res = runPredictionsUsingWindow_(mode);
    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Predictions → ' + String(mode||'all').toUpperCase(), {
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    SpreadsheetApp.getActive().toast('Predictions (' + String(mode||'all').toUpperCase() + '): selected=' + (res.selected||0) + ', submitted=' + (res.submitted||0), 'Predictions', 8);
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
    throw e;
  }
}

function menuActualsManualFetch_(){
  var ss = SpreadsheetApp.getActive();
  var shLog = ss.getSheetByName((typeof CFG !== 'undefined' && CFG.SHEET_LOG) ? CFG.SHEET_LOG : 'log');
  var started = new Date();
  try {
    // Resolve window → convert to minutes for the windowed fetcher
    var minsBack = 24*60, minsFwd = 0, cap = 2000;
    var used = { mode: 'fallback:lookback24h' };

    var win = (typeof resolveWindow_ === 'function') ? resolveWindow_('actuals_manual') : null;
    if (win && win.windowEnabled && win.fromUtcIso && win.toUtcIso) {
      // Convert explicit from/to → minutes relative to now (floor/ceil to safe side)
      var now = new Date();
      var fromMs = (new Date(win.fromUtcIso)).getTime();
      var toMs   = (new Date(win.toUtcIso)).getTime();
      minsBack = Math.max(0, Math.ceil((now.getTime() - fromMs)/60000));
      minsFwd  = Math.max(0, Math.ceil((toMs - now.getTime())/60000));
      used = { mode: 'window', fromUtcIso: win.fromUtcIso, toUtcIso: win.toUtcIso, note: win.note||'' };
    }

    // Delegates to your existing windowed fetcher in actuals_fetcher.gs
    var res = (typeof runFetchActualsWindow_ === 'function')
      ? runFetchActualsWindow_(minsBack, minsFwd, cap)
      : (function(){ throw new Error('runFetchActualsWindow_ not found in actuals_fetcher.gs'); })();

    if (typeof _log_ === 'function' && shLog) {
      _log_(shLog, 'info', 'Actuals → Manual fetch', {
        window_used: used,
        result: res,
        started_ts: started.toISOString(),
        ended_ts: (new Date()).toISOString()
      });
    }
    SpreadsheetApp.getActive().toast(
    'Actuals manual: inspected=' + (res.inspected||0) +
    ', updated=' + (res.updated||0) +
    ', released=' + (res.released||0) +
    ', revised=' + (res.revised||0),
    'Actuals',
    8
    );
  } catch (e) {
    if (typeof showErrorPopup_ === 'function') {
      showErrorPopup_('Actuals Manual — Error', (e && e.message) ? e.message : String(e));
    }
    throw e;
  }
}

function menuActualsStartHourly_(){
  // Creates an hourly installable trigger to call menuActualsManualFetch_()
  var fn = 'menuActualsManualFetch_';
  // De-dupe existing triggers
  var triggers = ScriptApp.getProjectTriggers() || [];
  for (var i=0;i<triggers.length;i++){
    if (triggers[i].getHandlerFunction && triggers[i].getHandlerFunction() === fn) {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger(fn).timeBased().everyHours(1).create();
  SpreadsheetApp.getActive().toast('Actuals: Hourly automation started', 'Actuals', 5);
}

function menuActualsStopHourly_(){
  var fn = 'menuActualsManualFetch_';
  var triggers = ScriptApp.getProjectTriggers() || [];
  var removed = 0;
  for (var i=0;i<triggers.length;i++){
    if (triggers[i].getHandlerFunction && triggers[i].getHandlerFunction() === fn) {
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

/** Manual: fetch actuals for past 31days **/
function menuBuildSeriesMapFromLast31d_() {
  var now = new Date();
  var start = new Date(now.getTime() - 31 * 24 * 3600 * 1000);
  var added = _buildSeriesMapFromRange_(start.toISOString(), now.toISOString(), { append:true });
  if (typeof _logInfo === 'function') _logInfo('SeriesMap builder: added rows', { added: added });
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
 * v1.3.x control-plane wrapper: MUST bypass Config windowing.
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


/** ===== v1.3.x Menu Maintenance Wrappers (control-plane only) ===== **/

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



/** =========================================================
 * SeriesMap Proposals (Option 1)
 * - Selection-only: SeriesMap_Suggestions → LLM → SeriesMap_Proposals
 * - Dedupe key: UPPER(country) + "|" + normalized indicator_name_pattern
 * - NEVER writes to SeriesMap (canonical)
 * ========================================================= */

function menuSeriesMapGenerateProposalsSelected_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getActiveSheet();
  var logSh = getSheet(CFG.SHEET_LOG);

  if (!sh || sh.getName() !== CFG.SHEET_SERIESMAP_SUGGESTIONS) {
    SpreadsheetApp.getUi().alert('Please run this from the SeriesMap_Suggestions sheet with some rows selected.');
    return;
  }

  var rows = _readSelectedSuggestionRows_();
  if (!rows.length) {
    SpreadsheetApp.getUi().alert('No data rows selected. Select one or more suggestion rows (not header).');
    return;
  }

  var res = _generateSeriesMapProposalsCore_({ rows: rows, dry_run: false, source: 'menu' });

  var mode = String(CFG.SERIESMAP_TRIAGE_MODE || 'MANUAL').toUpperCase();

  var msg =
    'Generate Proposals complete.\n\n' +
    'Selected: ' + rows.length + '\n' +
    'Written: ' + (res.proposals_written || 0) + '\n' +
    'Updated: ' + (res.proposals_updated || 0) + '\n' +
    'Appended: ' + (res.proposals_appended || 0) + '\n' +
    'Errors: ' + (res.errors || 0);
  try { SpreadsheetApp.getUi().alert(msg); } catch(_) {}
  appendLog(logSh, 'INFO', 'SeriesMap proposals: menu run', res);
}

/** WebApp endpoint */
function doPost(e) {
  var logSh = getSheet(CFG.SHEET_LOG);
  try {
    var raw = (e && e.postData && e.postData.contents) ? e.postData.contents : '';
    if (!raw) return _jsonOut_({ status:'error', error:'empty_body' });

    var req = JSON.parse(raw);
    if (!req || req.action !== 'generate_proposals') {
      return _jsonOut_({ status:'error', error:'bad_action', got:(req && req.action) });
    }

    var rows = Array.isArray(req.rows) ? req.rows : [];
    if (!rows.length) return _jsonOut_({ status:'error', error:'no_rows' });

    var res = _generateSeriesMapProposalsCore_({
      rows: rows,
      dry_run: !!req.dry_run,
      source: 'webapp'
    });

    appendLog(logSh, 'INFO', 'SeriesMap proposals: webapp run', res);
    return _jsonOut_(Object.assign({ status:'ok' }, res));
  } catch (err) {
    appendLog(logSh, 'ERROR', 'SeriesMap proposals: webapp error', { error:String(err), stack:(err && err.stack) });
    return _jsonOut_({ status:'error', error:String(err) });
  }
}

/** Optional: quick GET healthcheck */
function doGet() {
  return _jsonOut_({ status:'ok', service:'presignal', module:'seriesmap_proposals' });
}

function _jsonOut_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj || {}))
    .setMimeType(ContentService.MimeType.JSON);
}

/** Read selected rows from SeriesMap_Suggestions (selection-only, no fallback). */
function _readSelectedSuggestionRows_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getActiveSheet();
  var headers = getHeaderNames(sh);
  var hmap = _headerMap_(headers);

  var rl = sh.getActiveRangeList();
  if (!rl) return [];

  var ranges = rl.getRanges();
  var out = [];

  for (var r = 0; r < ranges.length; r++) {
    var range = ranges[r];
    var values = range.getValues();
    var startRow = range.getRow();
    var startCol = range.getColumn();

    for (var i = 0; i < values.length; i++) {
      var sheetRow = startRow + i;

      // Skip header row explicitly
      if (sheetRow === 1) continue;

      // Read the full row, not just the selected columns
      var full = sh.getRange(sheetRow, 1, 1, sh.getLastColumn()).getValues()[0];
      var rowObj = _rowToObj_(full, headers);

      // Must have country + indicator_name_pattern at minimum
      var country = (rowObj.country || '').trim();
      var pat = (rowObj.indicator_name_pattern || '').trim();
      if (!country || !pat) continue;

      // Capture row index for traceability
      rowObj._sheet_row = sheetRow;

      out.push(rowObj);
    }
  }

  // De-dupe within the selection (same key appears twice in multi-range)
  var seen = {};
  var deduped = [];
  for (var k = 0; k < out.length; k++) {
    var key = _seriesMapKey_(out[k].country, out[k].indicator_name_pattern);
    if (seen[key]) continue;
    seen[key] = true;
    deduped.push(out[k]);
  }
  return deduped;
}

function _headerMap_(headers) {
  var m = {};
  for (var i = 0; i < headers.length; i++) {
    var h = String(headers[i] || '').trim();
    if (!h) continue;
    m[h.toLowerCase()] = i;
  }
  return m;
}

function _rowToObj_(rowArr, headers) {
  var o = {};
  for (var i = 0; i < headers.length; i++) {
    var h = String(headers[i] || '').trim();
    if (!h) continue;
    o[h] = rowArr[i];
  }
  return o;
}

function _seriesMapKey_(country, indicatorPattern) {
  var c = String(country || '').trim().toUpperCase();
  var p = String(indicatorPattern || '').trim().toLowerCase();
  // normalize basic whitespace
  p = p.replace(/\s+/g, ' ');
  return c + '|' + p;
}


function _manualProposalsFromSuggestions_(payloadRows) {
  var nowIso = new Date().toISOString();
  return payloadRows.map(function(r){
    var title = r.cand_1_title || r.cand_2_title || '';
    return {
      country: r.country || '',
      indicator_name: r.indicator_name || '',
      indicator_name_pattern: r.indicator_name_pattern || '',
      provider: '(MANUAL)',
      series_id: '',
      title: title,
      freq: 'IRREGULAR',
      unit_type: '',
      transform: '',
      seasonal_adjustment: '',
      precision_dp: '',
      lag_rule: '',
      notes: 'Manual triage required. Use the triage pack dialog and paste into GPT-5.2 chat (off-API).',
      confidence: '',
      rationale: '',
      source: 'manual',
      created_ts: nowIso,
      status: 'PENDING_MANUAL',
      promoted_ts: '',
      promoted_by: '',
      cand_1_series_id: r.cand_1_series_id || '',
      cand_2_series_id: r.cand_2_series_id || '',
      event_id: r.event_id || '',
      proposal_model: 'manual/off-api'
    };
  });
}

function _buildGPT52SeriesMapTriagePrompt_(payloadRows) {
  var triageSpec =
    'PreSignal v1.3 — SeriesMap Triage (Human-AI Joint Review)\n' +
    'This is ONLY for SeriesMap triage and promotion decisions.\n' +
    'Goal: Decide which indicators map to which provider + series_id.\n' +
    'Prioritize semantic correctness over automation. Produce ready-to-copy rows.\n' +
    'Non-goals: no Apps Script edits, no auto-promotion, no “close enough” mappings.\n\n' +
    'Rules:\n' +
    '- Output MUST be valid JSON object with a single key: "proposals" (array).\n' +
    '- Produce exactly ONE proposal per input row.\n' +
    '- You MAY output regex-style indicator_name_pattern when it improves robustness.\n' +
    '- If mapping is not conceptually clean, set provider="(REVIEW)" and series_id="" and explain briefly.\n' +
    '- Do NOT invent series IDs.\n\n' +
    'Output fields per proposal:\n' +
    'country, indicator_name, indicator_name_pattern, provider, series_id, title, freq,\n' +
    'unit_type, transform, seasonal_adjustment, precision_dp, lag_rule,\n' +
    'notes, confidence (HIGH|MEDIUM|LOW), rationale, source, created_ts, status,\n' +
    'cand_1_series_id, cand_2_series_id, event_id, proposal_model.\n\n' +
    'Set:\n' +
    '- status = "AI_PROPOSED"\n' +
    '- source = "GPT52"\n' +
    '- proposal_model = "OpenAI:' + String(CFG.SERIESMAP_TRIAGE_OPENAI_MODEL || '') + '"\n';

  var user =
    triageSpec +
    '\nInput rows JSON:\n' +
    JSON.stringify({ rows: payloadRows }, null, 2) +
    '\n\nReturn JSON ONLY.';

  return {
    system: 'You are a macroeconomics data-mapping expert. You perform SeriesMap triage with strict correctness.',
    user: user
  };
}

function _showSeriesMapTriagePackDialog_(payloadRows) {
  var title = 'SeriesMap Triage Pack (Copy/Paste into GPT-5.2 chat)';
  var promptText =
    'Paste everything below into your GPT-5.2 triage chat:\n\n' +
    '---\n' +
    'PreSignal v1.3 — SeriesMap Triage (Human-AI Joint Review)\n' +
    'Purpose: SeriesMap triage + promotion decisions.\n' +
    'Goal: Decide provider + series_id. Prefer semantic correctness.\n' +
    'Output: PROMOTE / NEEDS DECISION / REJECT + mapping + confidence + notes.\n' +
    'Non-goals: no apps script edits, no auto-promotion, no speculative mappings.\n' +
    '---\n\n' +
    'INPUT ROWS (JSON):\n' +
    JSON.stringify({ rows: payloadRows }, null, 2);

  var html =
    '<div style="font-family:monospace; white-space:pre-wrap; font-size:12px; padding:12px;">' +
    _escapeHtml_(promptText) +
    '</div>';

  var output = HtmlService.createHtmlOutput(html).setWidth(900).setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(output, title);
}

function _escapeHtml_(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}


/** Core: calls LLM, writes to SeriesMap_Proposals (unless dry_run). */
function _generateSeriesMapProposalsCore_(args) {
  var rows = (args && args.rows) ? args.rows : [];
  var dryRun = !!(args && args.dry_run);

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sugSh = getSheet(CFG.SHEET_SERIESMAP_SUGGESTIONS);
  var propSh = getSheet(CFG.SHEET_SERIESMAP_PROPOSALS);
  var logSh = getSheet(CFG.SHEET_LOG);

  if (!propSh) throw new Error('Missing sheet: ' + CFG.SHEET_SERIESMAP_PROPOSALS);
  if (!sugSh) throw new Error('Missing sheet: ' + CFG.SHEET_SERIESMAP_SUGGESTIONS);

  var proposalHeaders = _proposalHeaders_();
  ensureHeaders(propSh, proposalHeaders);

  // Build payload rows (compact + candidates)
  var payloadRows = rows.map(function(r){
    return {
      country: r.country || '',
      indicator_name: r.indicator_name || r.indicator_name_clean || '',
      indicator_name_pattern: r.indicator_name_pattern || '',
      event_id: r.event_id || '',
      notes: r.notes || '',
      created_ts: r.created_ts || '',

      cand_1_provider: r.cand_1_provider || '',
      cand_1_series_id: r.cand_1_series_id || '',
      cand_1_title: r.cand_1_title || '',
      cand_1_freq: r.cand_1_freq || '',
      cand_1_units: r.cand_1_units || '',

      cand_2_provider: r.cand_2_provider || '',
      cand_2_series_id: r.cand_2_series_id || '',
      cand_2_title: r.cand_2_title || '',
      cand_2_freq: r.cand_2_freq || '',
      cand_2_units: r.cand_2_units || '',

      _sheet_row: r._sheet_row || null
    };
  });

  // === MODE ROUTER ===
  var mode = String(CFG.SERIESMAP_TRIAGE_MODE || 'MANUAL').toUpperCase();

  // HARD GUARD: if operator expects GPT52, do not silently run MANUAL behavior
  if (mode === 'GPT52') {
    // sanity: surface what model we will call
    if (!CFG.SERIESMAP_TRIAGE_OPENAI_MODEL) {
      throw new Error('GPT52 mode enabled but SERIESMAP_TRIAGE_OPENAI_MODEL is empty.');
    }
    // must have key
    var k = _getKey_(['OPENAI_API_KEY']);
    if (!k) throw new Error('GPT52 mode enabled but OPENAI_API_KEY is missing.');
  }

  if (mode === 'MANUAL') {
    // 1) Write “pending manual” proposals so you have a review buffer
    var manualProposals = _manualProposalsFromSuggestions_(payloadRows);
    var up = _upsertProposals_(propSh, proposalHeaders, manualProposals, { dry_run: dryRun });

    // 2) Show copy/paste triage pack (your GPT-5.2 triage prompt + JSON rows)
    if (!dryRun) {
      _showSeriesMapTriagePackDialog_(payloadRows);
    }

    return {
      dry_run: dryRun,
      source: args && args.source,
      selected_rows: rows.length,
      proposals_written: up.written,
      proposals_updated: up.updated,
      proposals_appended: up.appended,
      errors: up.errors.length,
      error_items: up.errors,
      ai_name: 'MANUAL',
      ai_version: 'off-api'
    };
  }

  if (mode === 'GPT52') {
    // HARD GUARD: do NOT fall back to other models
    if (CFG.SERIESMAP_TRIAGE_ALLOW_FALLBACK_MODELS) {
      throw new Error('Refusing: SERIESMAP_TRIAGE_ALLOW_FALLBACK_MODELS must be false for GPT52-only behavior.');
    }

    var llm = _callOpenAI_GPT52_SeriesMapTriage_(payloadRows);

    var proposals = (llm && llm.parsed && Array.isArray(llm.parsed.proposals)) ? llm.parsed.proposals : [];
    if (!proposals.length) {
      return {
        dry_run: dryRun,
        source: args && args.source,
        selected_rows: rows.length,
        proposals_written: 0,
        proposals_updated: 0,
        proposals_appended: 0,
        errors: 1,
        error_items: [{ error:'no_proposals_returned' }],
        ai_name: llm && llm.ai_name,
        ai_version: llm && llm.ai_version
      };
    }

    var up2 = _upsertProposals_(propSh, proposalHeaders, proposals, { dry_run: dryRun });

    return {
      dry_run: dryRun,
      source: args && args.source,
      selected_rows: rows.length,
      proposals_written: up2.written,
      proposals_updated: up2.updated,
      proposals_appended: up2.appended,
      errors: up2.errors.length,
      error_items: up2.errors,
      ai_name: llm.ai_name,
      ai_version: llm.ai_version
    };
  }

  throw new Error('Unknown SERIESMAP_TRIAGE_MODE=' + CFG.SERIESMAP_TRIAGE_MODE + ' (use MANUAL or GPT52)');
}

/** Proposal sheet headers (must match your existing SeriesMap_* schema philosophy). */
function _proposalHeaders_() {
  // Align to your SeriesMap_Proposals (buffer/review) schema.
  // We include SeriesMap-ready optional fields too (unit_type/transform/etc.)
  // so GPT-5.2 can output “SeriesMap-grade” rows later without schema surgery.
  return [
    'country',
    'indicator_name',
    'indicator_name_pattern',
    'provider',
    'series_id',
    'title',
    'freq',
    'unit_type',
    'transform',
    'seasonal_adjustment',
    'precision_dp',
    'lag_rule',
    'notes',
    'confidence',
    'rationale',
    'source',
    'created_ts',
    'status',
    'promoted_ts',
    'promoted_by',
    'cand_1_series_id',
    'cand_2_series_id',
    'event_id',
    'proposal_model'
  ];
}

/** Upsert proposals into SeriesMap_Proposals (dedupe key = country|pattern). */
function _upsertProposals_(propSh, headers, proposals, opt) {
  var dryRun = !!(opt && opt.dry_run);

  var lastRow = propSh.getLastRow();
  var lastCol = propSh.getLastColumn();
  var existing = (lastRow >= 2) ? propSh.getRange(2, 1, lastRow - 1, lastCol).getValues() : [];
  var hmap = _headerMap_(headers);

  // Build index: key -> rowIndexInSheet (1-based sheet row)
  var idx = {};
  for (var i = 0; i < existing.length; i++) {
    var row = existing[i];
    var country = String(row[hmap['country']] || '').trim();
    var pat = String(row[hmap['indicator_name_pattern']] || '').trim();
    if (!country || !pat) continue;
    idx[_seriesMapKey_(country, pat)] = (2 + i);
  }

  var toAppend = [];
  var toUpdate = [];
  var errors = [];

  for (var p = 0; p < proposals.length; p++) {
    var pr = proposals[p] || {};
    var c = (pr.country || '').trim();
    var pat2 = (pr.indicator_name_pattern || '').trim();
    if (!c || !pat2) {
      errors.push({ error:'missing_key_fields', item: pr });
      continue;
    }
    var key = _seriesMapKey_(c, pat2);

    var rowArr = new Array(headers.length).fill('');
    function setH(name, val) {
      var j = hmap[String(name).toLowerCase()];
      if (j == null) return;
      rowArr[j] = (val == null) ? '' : val;
    }

    // Core fields
    setH('country', c);
    setH('indicator_name', pr.indicator_name || '');
    setH('indicator_name_pattern', pat2);
    setH('provider', pr.provider || '(REVIEW)');
    setH('series_id', pr.series_id || '');
    setH('freq', pr.freq || 'IRREGULAR');
    setH('title', pr.title || '');

    // SeriesMap-ready optionals (kept blank unless provided)
    setH('unit_type', pr.unit_type || '');
    setH('transform', pr.transform || '');
    setH('seasonal_adjustment', pr.seasonal_adjustment || '');
    setH('precision_dp', pr.precision_dp || '');
    setH('lag_rule', pr.lag_rule || '');

    // Notes / confidence / rationale
    setH('notes', pr.notes || '');
    setH('confidence', pr.confidence || pr.proposal_confidence || '');
    setH('rationale', pr.rationale || pr.proposal_rationale_short || '');

    // Provenance
    setH('source', pr.source || '');
    setH('created_ts', pr.created_ts || new Date().toISOString());
    setH('status', pr.status || '');

    // Promotion bookkeeping (unused now)
    setH('promoted_ts', pr.promoted_ts || '');
    setH('promoted_by', pr.promoted_by || '');

    // Candidate + linkage
    setH('cand_1_series_id', pr.cand_1_series_id || '');
    setH('cand_2_series_id', pr.cand_2_series_id || '');
    setH('event_id', pr.event_id || '');

    // Model stamp
    setH('proposal_model', pr.proposal_model || pr.proposal_model_name || '');

    var hitRow = idx[key];
    if (hitRow) {
      toUpdate.push({ sheetRow: hitRow, values: rowArr });
    } else {
      toAppend.push(rowArr);
    }
  }

  if (!dryRun) {
    // Updates (row by row to keep it simple + safe)
    for (var u = 0; u < toUpdate.length; u++) {
      propSh.getRange(toUpdate[u].sheetRow, 1, 1, headers.length).setValues([toUpdate[u].values]);
    }
    // Appends (batch)
    if (toAppend.length) {
      propSh.getRange(propSh.getLastRow() + 1, 1, toAppend.length, headers.length).setValues(toAppend);
    }
  }

  return {
    written: (toUpdate.length + toAppend.length),
    updated: toUpdate.length,
    appended: toAppend.length,
    errors: errors
  };
}

/** LLM caller: prefer OpenAI if OPENAI_API_KEY exists, else Gemini if key exists. */
function _callOpenAI_GPT52_SeriesMapTriage_(payloadRows) {
  var openaiKey = _getKey_(['OPENAI_API_KEY']);
  if (!openaiKey) throw new Error('OPENAI_API_KEY missing (required for GPT52 mode).');

  var model = String(CFG.SERIESMAP_TRIAGE_OPENAI_MODEL || '').trim();
  if (!model) throw new Error('SERIESMAP_TRIAGE_OPENAI_MODEL is empty.');

  var prompt = _buildGPT52SeriesMapTriagePrompt_(payloadRows);

  // NOTE: this reuses your existing OpenAI chat completions call style.
  var url = 'https://api.openai.com/v1/chat/completions';
  var body = {
    model: model,
    response_format: { type: 'json_object' },
    messages: [
      { role: 'system', content: prompt.system },
      { role: 'user', content: prompt.user }
    ]
  };

  var resp = _withRetries_(function(){
    var r = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'Authorization': 'Bearer ' + openaiKey },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = r.getResponseCode();
    if (code === 429) throw new Error('OpenAI 429');
    if (code >= 500) throw new Error('OpenAI ' + code);
    if (code < 200 || code > 299) throw new Error('OpenAI ' + code + ': ' + r.getContentText());
    return r.getContentText();
  }, { provider: 'OpenAI' });

  var j = JSON.parse(resp);
  var c = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
  if (!c) throw new Error('OpenAI: empty content');

  var parsed = JSON.parse(c);
  return {
    ai_name: 'OpenAI',
    ai_version: j.model || model,
    parsed: parsed,
    raw_output: c
  };
}

function _buildSeriesMapProposalPrompt_(rows) {
  var system =
    'You are a strict data-mapping assistant for an economic SeriesMap system.\n' +
    'You receive suggestion rows (country + indicator_name_pattern + candidate series IDs).\n' +
    'Your job is to output promotion-ready proposal rows for SeriesMap_Proposals.\n' +
    'Rules:\n' +
    '- Output MUST be valid JSON.\n' +
    '- Output MUST be an object with a single field: "proposals" (array).\n' +
    '- For each input row, produce exactly one proposal.\n' +
    '- Prefer cand_1_* if it looks like a valid FRED mapping; else use cand_2_* if valid.\n' +
    '- If uncertain, set provider="(REVIEW)" and series_id="" and explain briefly in notes.\n' +
    '- Do NOT invent series IDs.\n' +
    '- Keep notes short.\n';

  var user =
    'Here are suggestion rows:\n' +
    JSON.stringify({ rows: rows }, null, 2);

  var instruction =
    'Return JSON exactly like:\n' +
    '{\n' +
    '  "proposals": [\n' +
    '    {\n' +
    '      "country": "US",\n' +
    '      "indicator_name_pattern": "Initial Jobless Claims",\n' +
    '      "provider": "FRED",\n' +
    '      "series_id": "ICSA",\n' +
    '      "freq": "W",\n' +
    '      "unit_type": "level",\n' +
    '      "transform": "level",\n' +
    '      "seasonal_adjustment": "SA",\n' +
    '      "precision_dp": "0",\n' +
    '      "lag_rule": "",\n' +
    '      "notes": "short note",\n' +
    '      "created_ts": "2026-01-30T00:00:00Z",\n' +
    '      "proposal_confidence": "high|medium|low",\n' +
    '      "proposal_rationale_short": "one sentence",\n' +
    '      "proposal_source_candidate": "cand_1|cand_2|none",\n' +
    '      "proposal_model": "OpenAI:gpt-4o-mini"\n' +
    '    }\n' +
    '  ]\n' +
    '}\n';

  return { system: system, user: user, instruction: instruction };
}

/** OpenAI call (SeriesMap proposals). */
function _callOpenAI_SeriesMap_(prov, prompt) {
  var url = 'https://api.openai.com/v1/chat/completions';
  var body = {
    model: prov.model,
    response_format: { type: 'json_object' },
    messages: [
      { role: 'system', content: prompt.system },
      { role: 'user', content: prompt.user + "\n\n" + prompt.instruction }
    ]
  };

  var resp = _withRetries_(function(){
    var r = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'Authorization': 'Bearer ' + prov.key },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = r.getResponseCode();
    if (code === 429) throw new Error('OpenAI 429');
    if (code >= 500) throw new Error('OpenAI ' + code);
    if (code < 200 || code > 299) throw new Error('OpenAI ' + code + ': ' + r.getContentText());
    return r.getContentText();
  }, { provider: 'OpenAI' });

  var j = JSON.parse(resp);
  var c = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
  if (!c) throw new Error('OpenAI: empty content');

  var parsed = JSON.parse(c);
  return {
    ai_name: 'OpenAI',
    ai_version: j.model || prov.model,
    parsed: parsed,
    raw_output: c
  };
}

/** Gemini call (SeriesMap proposals). */
function _callGemini_SeriesMap_(prov, prompt) {
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/' +
            encodeURIComponent(prov.model) +
            ':generateContent?key=' + encodeURIComponent(prov.key);

  var body = {
    contents: [{ role:'user', parts:[{ text: prompt.system + "\n\n" + prompt.user + "\n\n" + prompt.instruction }] }],
    generationConfig: { response_mime_type: 'application/json' }
  };

  var respText = _withRetries_(function(){
    var r = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = r.getResponseCode();
    if (code === 429) throw new Error('Gemini 429');
    if (code >= 500) throw new Error('Gemini ' + code);
    if (code < 200 || code > 299) throw new Error('Gemini ' + code + ': ' + r.getContentText());
    return r.getContentText();
  }, { provider: 'Gemini' });

  var j = JSON.parse(respText);
  var t = j.candidates && j.candidates[0] && j.candidates[0].content && j.candidates[0].content.parts && j.candidates[0].content.parts[0] && j.candidates[0].content.parts[0].text;
  if (!t) throw new Error('Gemini: empty content');

  var parsed = JSON.parse(t);
  return {
    ai_name: 'Gemini',
    ai_version: prov.model,
    parsed: parsed,
    raw_output: t
  };
}
