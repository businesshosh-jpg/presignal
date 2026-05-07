// prediction_runner.gs — v1.4 Robust Window + Config + Providers
// ------------------------------------------------------------------
// Purpose:
// * Read upcoming events from the Event sheet (canonical).
// * Call one or more LLM providers (Gemini, OpenAI, Anthropic/Claude) with strict-JSON prompt.
// * Normalize output and upsert into Predictions (dedupe: event_id|ai_name).
// * Capture ai_version/model, tokens, latency, raw_output, status.
//
// Requires (already in your project):
// * getSheet(name), getHeaderNames(sheet), appendLog(level,msg,ctx) from 00_logging_shim.gs
// * _uuidFromString_(seed) from runner_rules_patch.gs
//
// Menus:
// * This file exposes: runPredictionsAll_(), runPredictionsUsingWindow_(),
//   menuRunPredictionsGemini_(), menuRunPredictionsOpenAI_(), menuRunPredictionsClaude_().
// * If your onOpen() uses different names (e.g., menuPredGemini_, runPredictionsWindow),
//   keep your tiny wrappers in Code.gs as discussed.
//
// ------------------------------------------------------------------

/** =========================
 *  Configuration (defaults)
 *  ========================= */
var CFG = (typeof CFG !== 'undefined') ? CFG : {
  PROVIDERS: ['Gemini','OpenAI','Anthropic'],
  GEMINI_MODEL: 'gemini-2.5-flash-lite',
  OPENAI_MODEL: 'gpt-4o-mini',
  CLAUDE_MODEL: 'claude-haiku-4-5',
  PREDICTION_MODE: 'LIVE',
  PREDICTION_TEMPERATURE: 0,
  PREDICTION_SEED: 42,
  DEFAULT_FX: 'USDJPY',
  WINDOW_MIN_BEFORE_MIN: 24*60,  // fallback minutes window (used if local override disabled/invalid)
  WINDOW_MAX_AFTER_MIN: 36*60,
  PRED_MAX_WORK_UNITS_PER_RUN: 12,
  PRED_RESUME_ENABLED: true,
  PRED_AUTO_CONTINUE_ENABLED: true,
  PRED_AUTO_CONTINUE_DELAY_MIN: 1,
  PRED_AUTO_CONTINUE_DELAY_SEC: 15,
  ANTHROPIC_PROMPT_CACHE_ENABLED: true,
  ANTHROPIC_PROMPT_CACHE_TTL: '5m',
  DRY_RUN_PREDICT: false,
  PIPS_BY_IMPORTANCE: { low:[3,10], medium:[8,25], high:[15,45], critical:[25,80] },
  SCHEMA_VERSION: '1.4',
  RULE_VERSION: '1.4'
};


function _ensureCfgDefaults_() {
  var defaults = {
    PROVIDERS: ['Gemini','OpenAI','Anthropic'],
    GEMINI_MODEL: 'gemini-2.5-flash-lite',
    OPENAI_MODEL: 'gpt-4o-mini',
    CLAUDE_MODEL: 'claude-haiku-4-5',
    PREDICTION_MODE: 'LIVE',
    PREDICTION_TEMPERATURE: 0,
    PREDICTION_SEED: 42,
    DEFAULT_FX: 'USDJPY',
    WINDOW_MIN_BEFORE_MIN: 24*60,
    WINDOW_MAX_AFTER_MIN: 36*60,
    PRED_MAX_WORK_UNITS_PER_RUN: 12,
    PRED_RESUME_ENABLED: true,
    PRED_AUTO_CONTINUE_ENABLED: true,
    PRED_AUTO_CONTINUE_DELAY_MIN: 1,
    PRED_AUTO_CONTINUE_DELAY_SEC: 15,
    ANTHROPIC_PROMPT_CACHE_ENABLED: true,
    ANTHROPIC_PROMPT_CACHE_TTL: '5m',
    DRY_RUN_PREDICT: false,
    PIPS_BY_IMPORTANCE: { low:[3,10], medium:[8,25], high:[15,45], critical:[25,80] },
    SCHEMA_VERSION: '1.4',
    RULE_VERSION: '1.4'
  };
  if (typeof CFG !== 'object' || CFG === null) CFG = {};
  // Fill any missing key
  Object.keys(defaults).forEach(function(k){
    if (CFG[k] === undefined || CFG[k] === null || CFG[k] === '') CFG[k] = defaults[k];
  });
}


/** =========================
 *  Config sheet overrides
 *  ========================= */
// Reads key/value pairs from sheet "Config" (A:key, B:value) and overrides CFG.
// Supports:
// - PROVIDERS (comma list: Gemini,OpenAI,Anthropic / "Claude" alias → Anthropic)
// - OPENAI_MODEL, GEMINI_MODEL, CLAUDE_MODEL
// - PREDICTION_MODE (LIVE|BACKTEST; BACKTRACK alias → BACKTEST)
// - PREDICTION_TEMPERATURE (number), PREDICTION_SEED (integer)
// - DEFAULT_FX, DRY_RUN_PREDICT (bool), PIPS_*_MIN/MAX
// - Prediction-specific local window override (preferred):
//     PRED_WINDOW_ENABLED (true/false), PRED_WINDOW_FROM_LOCAL ("YYYY-MM-DD HH:mm" or Date),
//     PRED_WINDOW_TO_LOCAL, PRED_WINDOW_TZ (IANA, e.g., "Asia/Tokyo")
// - Legacy shared window fallback:
//     WINDOW_ENABLED, WINDOW_FROM_LOCAL, WINDOW_TO_LOCAL, WINDOW_TZ
function _applyConfigOverridesFromSheet_() {
  var sh;
  try {
    sh = SpreadsheetApp.getActive().getSheetByName('Config');
    if (!sh) return;
  } catch (e) { return; }

  var last = sh.getLastRow();
  if (last < 1) return;

  var rows = sh.getRange(1,1,last,2).getValues();
  var map = {};
  for (var r=0; r<rows.length; r++) {
    var k = (rows[r][0] || '').toString().trim();
    if (!k) continue;
    map[k.toUpperCase()] = rows[r][1];
  }

  if (map.PROVIDERS) {
    var wanted = String(map.PROVIDERS).split(',').map(function(s){return s.trim();}).filter(Boolean);
    var normalized = wanted.map(function(p){ return (p==='Claude') ? 'Anthropic' : p; });
    var known = ['Gemini','OpenAI','Anthropic'];
    var filtered = normalized.filter(function(p){ return known.indexOf(p)>=0; });
    if (filtered.length) CFG.PROVIDERS = filtered;
  }
  if (map.GEMINI_MODEL != null) CFG.GEMINI_MODEL = String(map.GEMINI_MODEL).trim() || CFG.GEMINI_MODEL;
  if (map.OPENAI_MODEL != null) CFG.OPENAI_MODEL = String(map.OPENAI_MODEL).trim() || CFG.OPENAI_MODEL;
  if (map.CLAUDE_MODEL != null) CFG.CLAUDE_MODEL = String(map.CLAUDE_MODEL).trim() || CFG.CLAUDE_MODEL;
  if (map.PREDICTION_MODE != null) {
    CFG.PREDICTION_MODE = _normalizePredictionMode_(map.PREDICTION_MODE);
  }
  if (map.PREDICTION_TEMPERATURE != null) {
    CFG.PREDICTION_TEMPERATURE = _cfgNumber_(map.PREDICTION_TEMPERATURE, CFG.PREDICTION_TEMPERATURE);
  }
  if (map.PREDICTION_SEED != null) {
    CFG.PREDICTION_SEED = _cfgInteger_(map.PREDICTION_SEED, CFG.PREDICTION_SEED);
  }
  if (map.PRED_MAX_WORK_UNITS_PER_RUN != null) {
    CFG.PRED_MAX_WORK_UNITS_PER_RUN = _cfgInteger_(map.PRED_MAX_WORK_UNITS_PER_RUN, CFG.PRED_MAX_WORK_UNITS_PER_RUN);
  }
  if (map.PRED_RESUME_ENABLED != null) {
    CFG.PRED_RESUME_ENABLED = _cfgBoolean_(map.PRED_RESUME_ENABLED, CFG.PRED_RESUME_ENABLED);
  }
  if (map.PRED_AUTO_CONTINUE_ENABLED != null) {
    CFG.PRED_AUTO_CONTINUE_ENABLED = _cfgBoolean_(map.PRED_AUTO_CONTINUE_ENABLED, CFG.PRED_AUTO_CONTINUE_ENABLED);
  }
  if (map.PRED_AUTO_CONTINUE_DELAY_MIN != null) {
    CFG.PRED_AUTO_CONTINUE_DELAY_MIN = _cfgInteger_(map.PRED_AUTO_CONTINUE_DELAY_MIN, CFG.PRED_AUTO_CONTINUE_DELAY_MIN);
  }
  if (map.PRED_AUTO_CONTINUE_DELAY_SEC != null) {
    CFG.PRED_AUTO_CONTINUE_DELAY_SEC = _cfgInteger_(map.PRED_AUTO_CONTINUE_DELAY_SEC, CFG.PRED_AUTO_CONTINUE_DELAY_SEC);
  }
  if (map.ANTHROPIC_PROMPT_CACHE_ENABLED != null) {
    CFG.ANTHROPIC_PROMPT_CACHE_ENABLED = _cfgBoolean_(map.ANTHROPIC_PROMPT_CACHE_ENABLED, CFG.ANTHROPIC_PROMPT_CACHE_ENABLED);
  }
  if (map.ANTHROPIC_PROMPT_CACHE_TTL != null) {
    CFG.ANTHROPIC_PROMPT_CACHE_TTL = String(map.ANTHROPIC_PROMPT_CACHE_TTL).trim() || CFG.ANTHROPIC_PROMPT_CACHE_TTL;
  }
  if (map.DEFAULT_FX != null) CFG.DEFAULT_FX = String(map.DEFAULT_FX).trim();
  if (map.DRY_RUN_PREDICT != null) CFG.DRY_RUN_PREDICT = _cfgBoolean_(map.DRY_RUN_PREDICT, CFG.DRY_RUN_PREDICT);

  // Pips bands
  var p = CFG.PIPS_BY_IMPORTANCE || { low:[3,10], medium:[8,25], high:[15,45], critical:[25,80] };
  if (map.PIPS_LOW_MIN      != null) p.low[0]      = _cfgNumber_(map.PIPS_LOW_MIN, p.low[0]);
  if (map.PIPS_LOW_MAX      != null) p.low[1]      = _cfgNumber_(map.PIPS_LOW_MAX, p.low[1]);
  if (map.PIPS_MEDIUM_MIN   != null) p.medium[0]   = _cfgNumber_(map.PIPS_MEDIUM_MIN, p.medium[0]);
  if (map.PIPS_MEDIUM_MAX   != null) p.medium[1]   = _cfgNumber_(map.PIPS_MEDIUM_MAX, p.medium[1]);
  if (map.PIPS_HIGH_MIN     != null) p.high[0]     = _cfgNumber_(map.PIPS_HIGH_MIN, p.high[0]);
  if (map.PIPS_HIGH_MAX     != null) p.high[1]     = _cfgNumber_(map.PIPS_HIGH_MAX, p.high[1]);
  if (map.PIPS_CRITICAL_MIN != null) p.critical[0] = _cfgNumber_(map.PIPS_CRITICAL_MIN, p.critical[0]);
  if (map.PIPS_CRITICAL_MAX != null) p.critical[1] = _cfgNumber_(map.PIPS_CRITICAL_MAX, p.critical[1]);
  CFG.PIPS_BY_IMPORTANCE = p;

  // Prediction-specific window override keys
  CFG.WINDOW_OVERRIDE = CFG.WINDOW_OVERRIDE || { enabled:false };
  var predWindowEnabled = (map.PRED_WINDOW_ENABLED != null) ? map.PRED_WINDOW_ENABLED : map.WINDOW_ENABLED;
  var predWindowFromLocal = (map.PRED_WINDOW_FROM_LOCAL != null) ? map.PRED_WINDOW_FROM_LOCAL : map.WINDOW_FROM_LOCAL;
  var predWindowToLocal = (map.PRED_WINDOW_TO_LOCAL != null) ? map.PRED_WINDOW_TO_LOCAL : map.WINDOW_TO_LOCAL;
  var predWindowTz = (map.PRED_WINDOW_TZ != null) ? map.PRED_WINDOW_TZ : map.WINDOW_TZ;
  if (predWindowEnabled != null) CFG.WINDOW_OVERRIDE.enabled = _cfgBoolean_(predWindowEnabled, false);
  if (predWindowFromLocal != null) CFG.WINDOW_OVERRIDE.fromLocal = predWindowFromLocal;
  if (predWindowToLocal   != null) CFG.WINDOW_OVERRIDE.toLocal   = predWindowToLocal;
  if (predWindowTz        != null) CFG.WINDOW_OVERRIDE.tz        = String(predWindowTz).trim();
}

// Convert local window (Config) into UTC ISO bounds.
// Invalid enabled config is treated as an operator error rather than silently ignored.
function _maybeOverrideWindowFromConfig_(bounds) {
  var o = CFG.WINDOW_OVERRIDE || {};
  if (!o.enabled) return bounds;

  var tz = o.tz || Session.getScriptTimeZone() || 'UTC';
  if (o.fromLocal == null || o.toLocal == null || String(o.fromLocal).trim() === '' || String(o.toLocal).trim() === '') {
    throw new Error('Prediction window config requires FROM and TO in YYYY-MM-DD HH:mm format.');
  }
  var fromIso = _localToUtcIso_(o.fromLocal, tz);
  var toIso   = _localToUtcIso_(o.toLocal,   tz);

  if (!fromIso || !toIso) {
    throw new Error('Invalid prediction window config. Use PRED_WINDOW_FROM_LOCAL / PRED_WINDOW_TO_LOCAL in YYYY-MM-DD HH:mm format.');
  }
  if (Date.parse(fromIso) >= Date.parse(toIso)) {
    throw new Error('Invalid prediction window config. FROM must be earlier than TO.');
  }

  return { window_start_iso: fromIso, window_end_iso: toIso };
}

// Accepts strings OR Date cells like those entered in Config; returns UTC ISO or null.
function _localToUtcIso_(localStr, tz) {
  if (!localStr) return null;

  if (localStr instanceof Date) {
    if (isNaN(localStr.getTime())) return null;
    var wall = Utilities.formatDate(localStr, tz || Session.getScriptTimeZone() || 'UTC', 'yyyy-MM-dd HH:mm');
    return _localToUtcIso_(String(wall), tz);
  }

  var raw = String(localStr).trim().replace(/\u3000/g,' ').replace(/：/g,':');
  var m = raw.match(/^(\d{4})[-/](\d{2})[-/](\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) return null;

  var y=+m[1], mo=+m[2], d=+m[3], h=+m[4], mi=+m[5], se=m[6]?+m[6]:0;
  if (!(mo>=1&&mo<=12&&d>=1&&d<=31&&h>=0&&h<=23&&mi>=0&&mi<=59&&se>=0&&se<=59)) return null;

  var utcGuess = Date.UTC(y, mo-1, d, h, mi, se, 0);
  for (var i=0;i<3;i++){
    var offMs = _tzOffsetAt_(utcGuess, tz || Session.getScriptTimeZone() || 'UTC');
    var next = Date.UTC(y, mo-1, d, h, mi, se, 0) - offMs;
    if (next === utcGuess) break;
    utcGuess = next;
  }
  var dt = new Date(utcGuess);
  return isNaN(dt.getTime()) ? null : dt.toISOString();
}

function _tzOffsetAt_(utcMillis, tz) {
  var z = Utilities.formatDate(new Date(utcMillis), tz, 'Z'); // e.g., +0900
  var m = z.match(/^([+-])(\d{2})(\d{2})$/);
  if (!m) return 0;
  var sign = (m[1]==='-')?-1:1, hh=+m[2], mm=+m[3];
  return sign*((hh*60+mm)*60*1000);
}

function _normalizePredictionMode_(raw) {
  var s = String(raw == null ? '' : raw).trim().toUpperCase();
  if (s === 'BACKTRACK') s = 'BACKTEST';
  return (s === 'BACKTEST') ? 'BACKTEST' : 'LIVE';
}

/** =========================
 *  Public entrypoints
 *  ========================= */
function runPredictionsAll_() {
  return runPredictionsCore_({ windowMinBeforeMin: 24*60, windowMaxAfterMin: 36*60, providers: CFG.PROVIDERS });
}
function runPredictionsUsingWindow_() {
  return runPredictionsCore_({ windowMinBeforeMin: CFG.WINDOW_MIN_BEFORE_MIN, windowMaxAfterMin: CFG.WINDOW_MAX_AFTER_MIN, providers: CFG.PROVIDERS });
}
function menuRunPredictionsGemini_()  { return runPredictionsCore_({ windowMinBeforeMin: 24*60, windowMaxAfterMin: 36*60, providers: ['Gemini'] }); }
function menuRunPredictionsOpenAI_()  { return runPredictionsCore_({ windowMinBeforeMin: 24*60, windowMaxAfterMin: 36*60, providers: ['OpenAI'] }); }
function menuRunPredictionsClaude_()  { return runPredictionsCore_({ windowMinBeforeMin: 24*60, windowMaxAfterMin: 36*60, providers: ['Anthropic'] }); }
function menuClearPredictionCheckpoint_() {
  _clearPredictionCheckpoint_();
  _clearPredictionContinuationTriggers_();
  appendLog('info', 'Prediction checkpoint cleared', {
    module: 'prediction_runner',
    cleared_at: new Date().toISOString()
  });
  _flushPredictionLogs_();
  return { status: 'checkpoint_cleared' };
}

/** =========================
 *  Core runner
 *  ========================= */
function runPredictionsCore_(opts) {
  _applyConfigOverridesFromSheet_(); // read Config sheet overrides
  _ensureCfgDefaults_();
  if (opts && opts.autoContinueEnabledOverride != null) {
    CFG.PRED_AUTO_CONTINUE_ENABLED = !!opts.autoContinueEnabledOverride;
  }
  CFG.PREDICTION_MODE = _normalizePredictionMode_(CFG.PREDICTION_MODE);
  var runStartedMs = Date.now();
  _clearPredictionContinuationTriggers_();
  
  var runId = _uuidFromString_('predict:'+new Date().toISOString());
  var context = {
    module:'prediction_runner',
    rule_version: CFG.RULE_VERSION,
    run_id: runId,
    prediction_mode: CFG.PREDICTION_MODE,
    prediction_temperature: CFG.PREDICTION_TEMPERATURE,
    prediction_seed: CFG.PREDICTION_SEED
  };

  var eventSheet = getSheet('Event');
  var predSheet  = getSheet('Predictions');
  getSheet('log'); // ensure exists

  var predHeaders = _ensurePredHeaders_(predSheet);
  var predIdx     = _getPredHeaderIndex_(predHeaders);

  var windowBounds = _computeWindow_(opts && opts.windowMinBeforeMin, opts && opts.windowMaxAfterMin);
  windowBounds = _maybeOverrideWindowFromConfig_(windowBounds);

  appendLog('info','Effective prediction window', Object.assign({}, context, {
    window_start_iso: windowBounds.window_start_iso, window_end_iso: windowBounds.window_end_iso
  }));

  var selStats = { scanned:0, skipped_bad_ts:0, skipped_out_of_window:0, skipped_missing_id_type:0, skipped_has_actuals:0, selected:0 };
  var events = _selectEventsForWindow_(eventSheet, windowBounds, selStats);

  appendLog('info','Event selection summary', Object.assign({}, context, selStats));

  if (events.length === 0) {
    _clearPredictionCheckpoint_();
    _clearPredictionContinuationTriggers_();
    appendLog('info','No events found in window', Object.assign({}, context, windowBounds, { status:'no_events' }));
    _flushPredictionLogs_();
    return { status:'no_events', inspected:0, created:0, updated:0, duplicates:0, errors:0 };
  }

  // Resolve providers once, then enforce per-call override if present
  var providerOverride = (opts && Array.isArray(opts.providers) && opts.providers.length > 0)
    ? opts.providers.map(_normalizeProviderName_)
    : null;

  // First resolve everything the project COULD use (keys present via Config)
  var resolvedAll = _resolveProviders_(CFG.PROVIDERS);

  // If caller asked for a subset (e.g., ['OpenAI']), filter strictly
  var enabledProviders = providerOverride
    ? resolvedAll.filter(function (p) { return providerOverride.indexOf(p.name) >= 0; })
    : resolvedAll;

  // If caller explicitly requested a subset but none resolved, fail fast
  if (providerOverride && enabledProviders.length === 0) {
    appendLog('error', 'No providers enabled after explicit override', {
      module: 'prediction_runner',
      requested: providerOverride,
      available: resolvedAll.map(function (p) { return p.name; })
    });
    _flushPredictionLogs_();
    return { status: 'validation_error', message: 'No providers enabled' };
  }

  // If no override, still protect against empty resolution
  if (!providerOverride && enabledProviders.length === 0) {
    appendLog('error', 'No providers enabled (no API keys found)', {
      module: 'prediction_runner',
      requested: CFG.PROVIDERS
    });
    _flushPredictionLogs_();
    return { status: 'validation_error', message: 'No providers enabled' };
  }

  appendLog('info', 'Providers resolved', {
    module: 'prediction_runner',
    requested: providerOverride || CFG.PROVIDERS,
    enabled: enabledProviders.map(function (p) { return p.name + '(' + p.model + ')'; })
  });

  var workUnits = _buildPredictionWorkUnits_(events);
  var checkpointSig = _predictionCheckpointSignature_(windowBounds, enabledProviders, context.prediction_mode);
  var checkpoint = _getPredictionCheckpoint_();
  var resumeInfo = _resolvePredictionResumeState_(workUnits, checkpoint, checkpointSig);
  var maxUnits = _getPredictionMaxWorkUnitsPerRun_();
  var maxRuntimeMs = _getPredictionMaxRuntimeMs_();
  var endIndex = Math.min(workUnits.length, resumeInfo.startIndex + maxUnits);
  var resumeRequest = _buildPredictionResumeRequest_(opts, enabledProviders);

  appendLog('info','Prediction execution plan', Object.assign({}, context, {
    total_selected_events: events.length,
    total_work_units: workUnits.length,
    resume_enabled: !!CFG.PRED_RESUME_ENABLED,
    resume_active: !!CFG.PRED_RESUME_ENABLED && endIndex < workUnits.length,
    resumed_from_checkpoint: !!resumeInfo.resumed,
    start_unit_index: resumeInfo.startIndex,
    end_unit_exclusive: endIndex,
    max_work_units_per_run: maxUnits,
    max_runtime_ms: maxRuntimeMs
  }));

  var results = { inspected:0, created:0, updated:0, duplicates:0, errors:0 };
  var processedUnits = 0;
  var partial = false;
  var resumeScheduled = false;

  for (var u = resumeInfo.startIndex; u < endIndex; u++) {
    var unit = workUnits[u];
    if (!unit) continue;

    if ((Date.now() - runStartedMs) >= maxRuntimeMs) {
      partial = true;
      break;
    }

    _runPredictionWorkUnit_(unit, enabledProviders, predSheet, predIdx, runId, context, results);
    processedUnits++;
    _setPredictionCheckpoint_({
      signature: checkpointSig,
      last_completed_unit_key: unit.key,
      resume_request: resumeRequest,
      updated_at: new Date().toISOString()
    });
  }

  if (!partial && endIndex < workUnits.length) {
    partial = true;
  }

  SpreadsheetApp.flush();
  _sortPredictionsSheet_(predSheet);

  if (!partial) {
    _clearPredictionCheckpoint_();
    _clearPredictionContinuationTriggers_();
  } else if (_predictionAutoContinueEnabled_()) {
    _ensurePredictionContinuationTrigger_();
    resumeScheduled = true;
  }

  var nextWorkUnitIndex = resumeInfo.startIndex + processedUnits;
  var remainingWorkUnits = Math.max(0, workUnits.length - nextWorkUnitIndex);
  var completionState = 'complete';
  var summaryMessage = 'Prediction run summary';
  if (partial) {
    if (resumeScheduled) {
      completionState = 'checkpointed_for_resume';
      summaryMessage = 'Prediction run checkpoint summary';
    } else if (CFG.PRED_RESUME_ENABLED && remainingWorkUnits > 0) {
      completionState = 'checkpoint_pending_manual_resume';
      summaryMessage = 'Prediction run pending resume summary';
    } else {
      completionState = 'incomplete';
      summaryMessage = 'Prediction run partial summary';
    }
  }

  var summary = Object.assign({
    status: partial ? 'partial' : 'ok'
  }, results, windowBounds, {
    providers: enabledProviders.map(function(p){return p.name;}),
    total_selected_events: events.length,
    total_work_units: workUnits.length,
    processed_work_units: processedUnits,
    remaining_work_units: remainingWorkUnits,
    next_work_unit_index: remainingWorkUnits > 0 ? nextWorkUnitIndex : '',
    resume_enabled: !!CFG.PRED_RESUME_ENABLED,
    resume_active: !!CFG.PRED_RESUME_ENABLED && remainingWorkUnits > 0,
    resumed_from_checkpoint: !!resumeInfo.resumed,
    resume_scheduled: resumeScheduled,
    completion_state: completionState
  });
  appendLog('info', summaryMessage, Object.assign({}, context, summary));
  _flushPredictionLogs_();
  return summary;
}

function _flushPredictionLogs_() {
  if (typeof flushLogs_ === 'function') {
    flushLogs_();
  }
}

function runPredictionsResume_() {
  _applyConfigOverridesFromSheet_();
  _ensureCfgDefaults_();
  _clearPredictionContinuationTriggers_();

  var checkpoint = _getPredictionCheckpoint_();
  if (!checkpoint || !checkpoint.resume_request) {
    appendLog('info', 'Prediction resume skipped', {
      module: 'prediction_runner',
      reason: 'no_checkpoint'
    });
    _flushPredictionLogs_();
    return { status: 'no_checkpoint' };
  }

  return runPredictionsCore_(checkpoint.resume_request);
}

function _getPredictionMaxWorkUnitsPerRun_() {
  var n = Number(CFG && CFG.PRED_MAX_WORK_UNITS_PER_RUN);
  if (!isFinite(n)) n = 12;
  n = Math.floor(n);
  if (n < 1) n = 1;
  if (n > 200) n = 200;
  return n;
}

function _getPredictionMaxRuntimeMs_() {
  // Exit early enough to avoid Apps Script's execution ceiling.
  return 270000;
}

function _predictionAutoContinueEnabled_() {
  return !!CFG.PRED_AUTO_CONTINUE_ENABLED;
}

function _getPredictionAutoContinueDelayMs_() {
  var sec = Number(CFG && CFG.PRED_AUTO_CONTINUE_DELAY_SEC);
  if (isFinite(sec)) {
    sec = Math.floor(sec);
    if (sec < 5) sec = 5;
    if (sec > 1800) sec = 1800;
    return sec * 1000;
  }

  var min = Number(CFG && CFG.PRED_AUTO_CONTINUE_DELAY_MIN);
  if (!isFinite(min)) min = 1;
  min = Math.floor(min);
  if (min < 1) min = 1;
  if (min > 30) min = 30;
  return min * 60 * 1000;
}

function _predictionCheckpointPropKey_() {
  return 'PREDICTION_RESUME_CHECKPOINT_V1';
}

function _predictionContinuationHandlerName_() {
  return 'runPredictionsResume_';
}

function _clearPredictionContinuationTriggers_() {
  var fn = _predictionContinuationHandlerName_();
  var triggers = ScriptApp.getProjectTriggers() || [];
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction && triggers[i].getHandlerFunction() === fn) {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
}

function _ensurePredictionContinuationTrigger_() {
  var fn = _predictionContinuationHandlerName_();
  var triggers = ScriptApp.getProjectTriggers() || [];
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction && triggers[i].getHandlerFunction() === fn) {
      return;
    }
  }
  var delayMs = _getPredictionAutoContinueDelayMs_();
  ScriptApp.newTrigger(fn)
    .timeBased()
    .after(delayMs)
    .create();
}

function _getPredictionCheckpoint_() {
  try {
    var raw = PropertiesService.getScriptProperties().getProperty(_predictionCheckpointPropKey_());
    if (!raw) return null;
    var parsed = JSON.parse(raw);
    return (parsed && typeof parsed === 'object') ? parsed : null;
  } catch (e) {
    return null;
  }
}

function _setPredictionCheckpoint_(checkpoint) {
  if (!checkpoint || typeof checkpoint !== 'object') return;
  PropertiesService.getScriptProperties().setProperty(
    _predictionCheckpointPropKey_(),
    JSON.stringify(checkpoint)
  );
}

function _clearPredictionCheckpoint_() {
  PropertiesService.getScriptProperties().deleteProperty(_predictionCheckpointPropKey_());
}

function _predictionCheckpointSignature_(windowBounds, enabledProviders, predictionMode) {
  var providers = (enabledProviders || []).map(function(p) {
    return [p.name || '', p.model || ''].join(':');
  });
  return JSON.stringify({
    checkpoint_format: 'v2',
    window_start_iso: windowBounds && windowBounds.window_start_iso || '',
    window_end_iso: windowBounds && windowBounds.window_end_iso || '',
    prediction_mode: predictionMode || '',
    providers: providers
  });
}

function _buildPredictionResumeRequest_(opts, enabledProviders) {
  return {
    windowMinBeforeMin: _cfgInteger_(opts && opts.windowMinBeforeMin, 24 * 60),
    windowMaxAfterMin: _cfgInteger_(opts && opts.windowMaxAfterMin, 36 * 60),
    providers: (enabledProviders || []).map(function(p) { return p.name; }),
    resume_mode: 'checkpoint'
  };
}

function _buildPredictionWorkUnits_(events) {
  var batchGroups = _groupBatchEvents_(events);
  var units = [];

  (events || []).forEach(function(ev) {
    var type = String(ev && ev.type || '').toLowerCase();
    if (type === 'member' && ev.batch_id) {
      units.push({
        kind: 'member',
        key: 'member:' + ev.event_id,
        event: ev
      });
      var members = batchGroups[ev.batch_id] || [ev];
      var lastMember = members[members.length - 1];
      if (lastMember && String(lastMember.event_id) === String(ev.event_id)) {
        units.push({
          kind: 'batch',
          key: 'batch:' + ev.batch_id,
          batch_id: ev.batch_id,
          members: members,
          batch_ref: _buildBatchReferenceEvent_(members)
        });
      }
      return;
    }

    units.push({
      kind: 'single',
      key: 'single:' + ev.event_id,
      event: ev
    });
  });

  return units;
}

function _resolvePredictionResumeState_(workUnits, checkpoint, signature) {
  if (!CFG.PRED_RESUME_ENABLED) {
    return { startIndex: 0, resumed: false };
  }
  if (!checkpoint || checkpoint.signature !== signature) {
    return { startIndex: 0, resumed: false };
  }

  var lastKey = String(checkpoint.last_completed_unit_key || '').trim();
  if (!lastKey) return { startIndex: 0, resumed: false };

  for (var i = 0; i < workUnits.length; i++) {
    if (String(workUnits[i] && workUnits[i].key || '') !== lastKey) continue;
    return { startIndex: i + 1, resumed: true };
  }

  return { startIndex: 0, resumed: false };
}

function _runPredictionWorkUnit_(unit, enabledProviders, predSheet, predIdx, runId, context, results) {
  if (!unit) return;

  if (unit.kind === 'member') {
    _runPredictionEvent_(unit.event, enabledProviders, predSheet, predIdx, runId, context, results, { isBatchMember: true });
    return;
  }

  if (unit.kind === 'batch') {
    _runPredictionBatch_(unit.batch_ref, enabledProviders, predSheet, predIdx, runId, context, results);
    return;
  }

  if (unit.kind === 'single') {
    _runPredictionEvent_(unit.event, enabledProviders, predSheet, predIdx, runId, context, results, {});
  }
}

function _runPredictionEvent_(ev, enabledProviders, predSheet, predIdx, runId, context, results, opt) {
  opt = opt || {};
  results.inspected++;

  var qualOnly = _isQualitativeOnly_(ev);
  var prompt = _buildPredictionJsonPrompt_(ev, {
    qualOnly: qualOnly,
    fxPair: ev.fx_pair || CFG.DEFAULT_FX
  });

  (enabledProviders || []).forEach(function(prov) {
    var startedMs = Date.now();
    try {
      var providerResp = prov.fn(prov, prompt);
      providerResp.latency_ms = Date.now() - startedMs;
      var norm = _normalizePrediction_(ev, providerResp, { qualOnly: qualOnly });
      var rowObj = _buildPredictionRow_(ev, norm, runId);
      var action = _upsertPredictions_(predSheet, rowObj, predIdx);
      if (action === 'created') results.created++;
      else if (action === 'updated') results.updated++;
      else if (action === 'duplicate') results.duplicates++;

      appendLog('info', 'Prediction ok', Object.assign({}, context, {
        event_id: ev.event_id,
        batch_id: ev.batch_id || '',
        type: ev.type,
        provider: prov.name,
        model: prov.model,
        action: action,
        qualitative_only: qualOnly,
        latency_ms: providerResp.latency_ms,
        cache_creation_input_tokens: providerResp.cache_creation_input_tokens || 0,
        cache_read_input_tokens: providerResp.cache_read_input_tokens || 0
      }));
    } catch (e) {
      results.errors++;
      var errRow = _buildErrorPredictionRow_(ev, runId, e, prov);
      var errAction = _upsertPredictions_(predSheet, errRow, predIdx);
      if (errAction === 'created') results.created++;
      else if (errAction === 'updated') results.updated++;

      appendLog('error', 'Prediction error', Object.assign({}, context, {
        event_id: ev.event_id,
        batch_id: ev.batch_id || '',
        type: ev.type,
        provider: prov.name,
        model: prov.model,
        message: String(e),
        latency_ms: Date.now() - startedMs
      }));
    }
  });
}

function _runPredictionBatch_(batchEv, enabledProviders, predSheet, predIdx, runId, context, results) {
  if (!batchEv) return;

  var prompt = _buildBatchPredictionJsonPrompt_(batchEv, {
    fxPair: batchEv.fx_pair || CFG.DEFAULT_FX
  });

  (enabledProviders || []).forEach(function(prov) {
    var startedMs = Date.now();
    try {
      var providerResp = prov.fn(prov, prompt);
      providerResp.latency_ms = Date.now() - startedMs;
      var norm = _normalizePrediction_(batchEv, providerResp, { qualOnly: true, isBatch: true });
      var rowObj = _buildPredictionRow_(batchEv, norm, runId);
      var action = _upsertPredictions_(predSheet, rowObj, predIdx);
      if (action === 'created') results.created++;
      else if (action === 'updated') results.updated++;
      else if (action === 'duplicate') results.duplicates++;

      appendLog('info', 'Batch prediction ok', Object.assign({}, context, {
        batch_id: batchEv.event_id,
        member_count: batchEv.member_count || 0,
        anchor_mode: batchEv.batch_anchor_mode || '',
        anchor_confidence: batchEv.batch_anchor_confidence || '',
        anchor_event_id: batchEv.batch_anchor ? batchEv.batch_anchor.event_id : '',
        anchor_indicator_name: batchEv.batch_anchor ? batchEv.batch_anchor.indicator_name : '',
        anchor_score: batchEv.anchor_score || 0,
        anchor_margin: batchEv.anchor_margin || 0,
        anchor_reason: batchEv.anchor_reason || '',
        provider: prov.name,
        model: prov.model,
        action: action,
        latency_ms: providerResp.latency_ms,
        cache_creation_input_tokens: providerResp.cache_creation_input_tokens || 0,
        cache_read_input_tokens: providerResp.cache_read_input_tokens || 0
      }));
    } catch (e) {
      results.errors++;
      var errRow = _buildErrorPredictionRow_(batchEv, runId, e, prov);
      var errAction = _upsertPredictions_(predSheet, errRow, predIdx);
      if (errAction === 'created') results.created++;
      else if (errAction === 'updated') results.updated++;

      appendLog('error', 'Batch prediction error', Object.assign({}, context, {
        batch_id: batchEv.event_id,
        member_count: batchEv.member_count || 0,
        anchor_mode: batchEv.batch_anchor_mode || '',
        anchor_confidence: batchEv.batch_anchor_confidence || '',
        anchor_event_id: batchEv.batch_anchor ? batchEv.batch_anchor.event_id : '',
        anchor_indicator_name: batchEv.batch_anchor ? batchEv.batch_anchor.indicator_name : '',
        anchor_score: batchEv.anchor_score || 0,
        anchor_margin: batchEv.anchor_margin || 0,
        anchor_reason: batchEv.anchor_reason || '',
        provider: prov.name,
        model: prov.model,
        message: String(e),
        latency_ms: Date.now() - startedMs
      }));
    }
  });
}

/** =========================
 *  Window compute (robust)
 *  ========================= */
function _computeWindow_(minBeforeMin, maxAfterMin) {
  var now = new Date();
  var mb = Number(minBeforeMin);
  var ma = Number(maxAfterMin);
  if (!isFinite(mb) || mb < 0) mb = Number(CFG && CFG.WINDOW_MIN_BEFORE_MIN) || 24*60;
  if (!isFinite(ma) || ma < 0) ma = Number(CFG && CFG.WINDOW_MAX_AFTER_MIN) || 36*60;

  var startMs = now.getTime() - (mb * 60 * 1000);
  var endMs   = now.getTime() + (ma * 60 * 1000);

  var start = new Date(startMs);
  var end   = new Date(endMs);

  return {
    window_start_iso: isNaN(start.getTime()) ? new Date(0).toISOString() : start.toISOString(),
    window_end_iso:   isNaN(end.getTime())   ? new Date(now.getTime()+36*60*60*1000).toISOString() : end.toISOString()
  };
}

/** =========================
 *  Event selection (hardened)
 *  ========================= */
function _selectEventsForWindow_(sheet, bounds, stats) {
  stats = stats || { scanned:0, skipped_bad_ts:0, skipped_out_of_window:0, skipped_missing_id_type:0, selected:0 };

  var headers = getHeaderNames(sheet);
  var idx = {}; headers.forEach(function(h,i){ idx[h.toLowerCase()] = i; });

  var ws = Date.parse(bounds.window_start_iso);
  var we = Date.parse(bounds.window_end_iso);

  var values = sheet.getRange(2,1, Math.max(sheet.getLastRow()-1,0), headers.length).getValues();
  var out = [];

  for (var r=0; r<values.length; r++) {
    stats.scanned++;
    var row = values[r];

    var obj  = _cell(row, idx['object']);
    if (obj && String(obj).toLowerCase() !== 'econ_event') continue;

    var releaseTs = _cell(row, idx['release_ts']);
    var eventId   = _cell(row, idx['event_id']);
    var type      = _cell(row, idx['type']);
    var releasedValue = _cell(row, idx['released_value']);
    var releasedTs = _cell(row, idx['released_ts']);
    var releaseStatus = _cell(row, idx['release_status']);
    var importance= _cell(row, idx['importance']);
    var indicator = _cell(row, idx['indicator_name']);

    if (!eventId || !type) { stats.skipped_missing_id_type++; continue; }

    var relIso = _toIsoOrNull_(releaseTs);
    if (!relIso) { stats.skipped_bad_ts++; continue; }

    var relMs = Date.parse(relIso);
    if (!(relMs >= ws && relMs <= we)) { stats.skipped_out_of_window++; continue; }
    if (_normalizePredictionMode_(CFG.PREDICTION_MODE) === 'LIVE' &&
        _eventHasActuals_(releasedValue, releasedTs, releaseStatus)) {
      stats.skipped_has_actuals++;
      continue;
    }

    out.push({
      object: 'econ_event',
      event_id: eventId,
      batch_id: _cell(row, idx['batch_id']),
      type: type,
      country: _cell(row, idx['country']),
      indicator_name: indicator,
      genre: _cell(row, idx['genre']),
      importance: (importance||'').toLowerCase(),
      release_ts: relIso,
      source_cal: _cell(row, idx['source_cal']),
      consensus_value: _numOrNull_(_cell(row, idx['consensus_value'])),
      prev_revision: _numOrNull_(_cell(row, idx['prev_revision'])),
      fx_pair: _cell(row, idx['fx_pair']) || CFG.DEFAULT_FX
    });

    stats.selected++;
  }
  return out;
}

function _eventHasActuals_(releasedValue, releasedTs, releaseStatus) {
  var hasReleasedValue = !(releasedValue === '' || releasedValue === null || releasedValue === undefined);
  var hasReleasedTs = !(releasedTs === '' || releasedTs === null || releasedTs === undefined);
  var status = String(releaseStatus || '').trim().toLowerCase();
  var statusImpliesActual = (status === 'released' || status === 'revised' || status === 'fetched');
  return hasReleasedValue || hasReleasedTs || statusImpliesActual;
}

/** =========================
 *  Prompt & parsing
 *  ========================= */
function _buildPredictionJsonPrompt_(ev, opt) {
  var qualOnly = !!opt.qualOnly;
  var mrWindowMin = _getPredictionMrWindowMin_();
  var preSignalPlan = ev.pre_signal_plan || _buildPreSignalPlan_(ev);
  ev.pre_signal_plan = preSignalPlan;
  var payload = {
    schema_version: CFG.SCHEMA_VERSION,
    object: 'econ_event',
    country: ev.country,
    indicator_name: ev.indicator_name,
    genre: ev.genre || _inferGenreFromName_(ev.indicator_name || ''),
    importance: ev.importance || 'medium',
    release_ts: ev.release_ts,
    consensus_value: (typeof ev.consensus_value === 'number') ? ev.consensus_value : null,
    prev_revision: (typeof ev.prev_revision === 'number') ? ev.prev_revision : null,
    fx_pair: opt.fxPair || CFG.DEFAULT_FX,
    pre_release_signal: _preSignalPromptView_(preSignalPlan),
    policy: {
      qualitative_only: qualOnly,
      defaults: { pips_band_by_importance: CFG.PIPS_BY_IMPORTANCE },
      prediction_discipline: {
        primary_baseline: 'Compare expected release value against consensus_value when consensus_value is available.',
        previous_value_role: 'Use prev_revision as context only; do not treat it as the market surprise baseline when consensus_value exists.',
        missing_consensus: 'Missing consensus lowers confidence. If there is no consensus, avoid precise directional surprise unless the indicator is high-importance and has a direct USDJPY transmission path.',
        low_importance: 'Low-importance or indirect indicators should usually be flat/weak unless the rationale explains a clear direct FX channel.',
        indirect_examples: 'Fiscal statements, budget data, auctions, balance-sheet/liquidity data, and oil/gas inventory data are usually indirect for USDJPY and should default to small or flat reactions.',
        hidden_detail_rule: 'If market-moving surprise usually depends on subcomponents or post-release internals that are not present in this payload, default to conservative flat/weak behavior instead of inventing directional confidence.',
        consistency: 'qualitative_result, mr_pred_dir, mr_pred_net_pips, mr_pred_strength, and rationale must describe the same view.'
      },
      market_reaction: {
        prediction_window_min: mrWindowMin,
        max_window_min: 15,
        strength_allowed: ['weak','medium','strong']
      }
    },
    required_output: {
      object: 'ai_prediction',
      event_id: ev.event_id,
      type: ev.type,
      ai_forecast_value: qualOnly ? null : '(number or null)',
      qualitative_result: '(stronger|weaker|inline)',
      mr_window_min: '(' + mrWindowMin + ' only)',
      mr_pred_dir: '(up|down|flat)',
      mr_pred_net_pips: '(number)',
      mr_pred_strength: '(weak|medium|strong)',
      mr_pred_sustain_min: '(number, can exceed mr_window_min if you expect continuation)',
      rationale_short: '(short string)',
      rationale: '(longer string)'
    }
  };
  var instruction =
    "Return ONLY strict JSON (no code fences). Keys required: " +
    "object,event_id,type,ai_forecast_value,qualitative_result,mr_window_min," +
    "mr_pred_dir,mr_pred_net_pips,mr_pred_strength,mr_pred_sustain_min,rationale_short,rationale. " +
    "mr_window_min must equal " + mrWindowMin + ". " +
    "mr_pred_net_pips must be a plain number in pips. " +
    "ai_forecast_value must be a PLAIN number with no units or symbols (no %, k, m, bn). " +
    "Use consensus_value as the primary market-surprise baseline when present; prev_revision is context. " +
    "When consensus_value is null, be conservative: low-importance or indirect events should normally be flat/weak with small pips. " +
    "Treat pre_release_signal as operator planning guidance. If pre_release_signal.mode is scenario, keep blind directional claims conservative and let the rationale explain what would imply up, down, or flat. " +
    "Fiscal statements, budget releases, auctions, balance-sheet/liquidity updates, and oil/gas inventory data are usually indirect USDJPY drivers and should stay small unless the transmission path is unusually direct. " +
    "If the true market surprise usually lives in hidden subcomponents or post-release internals not present here, do not invent confidence; default to flat or weak. " +
    "Before assigning up/down pips, explain the USDJPY transmission path in rationale.";
  return {
    system: "You are a macroeconomic forecasting model. Output must be strict JSON and safe for parsing.",
    user: JSON.stringify(payload),
    instruction: instruction,
    cache_scaffold: _buildAnthropicPromptCacheScaffold_()
  };
}

function _buildBatchPredictionJsonPrompt_(batchEv, opt) {
  var mrWindowMin = _getPredictionMrWindowMin_();
  var preSignalPlan = batchEv.pre_signal_plan || _buildPreSignalPlan_(batchEv);
  batchEv.pre_signal_plan = preSignalPlan;
  var members = (batchEv.batch_members || []).map(function(m){
    return {
      event_id: m.event_id,
      indicator_name: m.indicator_name,
      genre: m.genre || _inferGenreFromName_(m.indicator_name || ''),
      importance: m.importance || 'medium',
      consensus_value: (typeof m.consensus_value === 'number') ? m.consensus_value : null,
      prev_revision: (typeof m.prev_revision === 'number') ? m.prev_revision : null
    };
  });
  var anchorMember = String(batchEv.batch_anchor_mode || '') === 'clear_anchor'
    ? (batchEv.batch_anchor || null)
    : null;
  var supportingMembers = members.filter(function(m){
    return !anchorMember || String(m.event_id || '') !== String(anchorMember.event_id || '');
  });
  var anchorSelection = {
    mode: batchEv.batch_anchor_mode || '',
    confidence: batchEv.batch_anchor_confidence || '',
    score: batchEv.anchor_score || 0,
    margin: batchEv.anchor_margin || 0,
    runner_up_event_id: batchEv.anchor_runner_up_event_id || '',
    runner_up_indicator_name: batchEv.anchor_runner_up_indicator_name || '',
    reason: batchEv.anchor_reason || ''
  };
  var payload = {
    schema_version: CFG.SCHEMA_VERSION,
    object: 'econ_event_batch',
    batch_id: batchEv.event_id,
    country: batchEv.country,
    release_ts: batchEv.release_ts,
    fx_pair: opt.fxPair || CFG.DEFAULT_FX,
    member_count: batchEv.member_count || members.length,
    members: members,
    pre_release_signal: _preSignalPromptView_(preSignalPlan),
    anchor_selection: anchorSelection,
    anchor_member: anchorMember ? {
      event_id: anchorMember.event_id,
      indicator_name: anchorMember.indicator_name,
      genre: anchorMember.genre || _inferGenreFromName_(anchorMember.indicator_name || ''),
      importance: anchorMember.importance || 'medium',
      consensus_value: (typeof anchorMember.consensus_value === 'number') ? anchorMember.consensus_value : null,
      prev_revision: (typeof anchorMember.prev_revision === 'number') ? anchorMember.prev_revision : null,
      anchor_score: batchEv.anchor_score,
      anchor_reason: batchEv.anchor_reason || ''
    } : null,
    supporting_members: supportingMembers,
    policy: {
      qualitative_only: true,
      defaults: { pips_band_by_importance: CFG.PIPS_BY_IMPORTANCE },
      prediction_discipline: {
        primary_goal: 'Predict the combined 5-minute USDJPY market reaction of the full release cluster, not each member separately.',
        no_clear_anchor_rule: 'If anchor_selection.mode is no_clear_anchor, do not force a single dominant member. Treat the cluster as ambiguous and prefer conservative flat or weak behavior unless the members still point clearly the same way.',
        weak_anchor_rule: 'If anchor_selection.mode is weak_anchor, treat the anchor as a watchlist clue, not the answer. Do not use it as the default market focus unless the rest of the release cluster confirms it.',
        anchor_rule: 'Only start with anchor_member as the default market focus when anchor_selection.mode is clear_anchor and anchor_member is present. Let supporting members confirm, soften, or offset the anchor view rather than replacing it automatically.',
        dominance_rule: 'Acknowledge when one member is likely to dominate the cluster reaction, but do not invent hidden details not present in the payload.',
        offset_rule: 'If member effects offset or no direct member clearly dominates, prefer flat or weak.',
        hidden_detail_rule: 'If the true surprise usually depends on subcomponents or post-release internals not present here, default to conservative flat/weak behavior.',
        consistency: 'qualitative_result, mr_pred_dir, mr_pred_net_pips, mr_pred_strength, and rationale must describe the same combined batch view.'
      },
      market_reaction: {
        prediction_window_min: mrWindowMin,
        max_window_min: 15,
        strength_allowed: ['weak','medium','strong']
      }
    },
    required_output: {
      object: 'ai_prediction',
      event_id: batchEv.event_id,
      type: 'batch',
      ai_forecast_value: null,
      qualitative_result: '(stronger|weaker|inline)',
      mr_window_min: '(' + mrWindowMin + ' only)',
      mr_pred_dir: '(up|down|flat)',
      mr_pred_net_pips: '(number)',
      mr_pred_strength: '(weak|medium|strong)',
      mr_pred_sustain_min: '(number)',
      rationale_short: '(short string)',
      rationale: '(longer string describing the combined batch view)'
    }
  };
  var instruction =
    "Return ONLY strict JSON (no code fences). Keys required: " +
    "object,event_id,type,ai_forecast_value,qualitative_result,mr_window_min," +
    "mr_pred_dir,mr_pred_net_pips,mr_pred_strength,mr_pred_sustain_min,rationale_short,rationale. " +
    "event_id must equal the batch_id and type must equal batch. " +
    "If anchor_selection.mode is no_clear_anchor, do not force a dominant member. " +
    "If anchor_selection.mode is weak_anchor, treat the anchor as a watchlist clue, not the answer. " +
    "Treat pre_release_signal as operator planning guidance. If pre_release_signal.mode is scenario, keep blind directional claims conservative and let the rationale explain what would imply up, down, or flat. " +
    "Use anchor_member as the default market focus only when anchor_selection.mode is clear_anchor and anchor_member is present; otherwise compare the watched members as a cluster. " +
    "Assess the combined release cluster, not each member separately. " +
    "If the members offset each other or no direct member clearly dominates, default to flat or weak. " +
    "If the true surprise depends on hidden details not present here, do not invent confidence.";
  return {
    system: "You are a macroeconomic forecasting model. Output must be strict JSON and safe for parsing.",
    user: JSON.stringify(payload),
    instruction: instruction,
    cache_scaffold: _buildAnthropicPromptCacheScaffold_()
  };
}

function _buildAnthropicPromptCacheScaffold_() {
  var sections = [
    "REFERENCE MANUAL FOR USDJPY EVENT PREDICTION",
    "Core mission: predict the first meaningful 5-minute USDJPY market reaction to a macro release using only the payload provided. Do not invent subcomponents, private estimates, leaks, or hidden internals. When the payload is incomplete, confidence should fall rather than rise.",

    "DECISION LADDER",
    "Step 1. Identify whether the release is direct or indirect for USDJPY. Direct releases include inflation, labor, growth, rates, consumer demand, broad business activity, and major sentiment data that can plausibly shift Federal Reserve expectations or broad risk sentiment. Indirect releases include fiscal releases, auctions, balance-sheet items, weekly energy inventory prints, liquidity operations, and niche administrative data. Indirect releases usually deserve flat or weak outcomes unless there is an unusually clear transmission path.",
    "Step 2. If consensus_value exists, compare the likely realized print against consensus_value. That is the market surprise baseline. prev_revision is context only. A higher consensus than previous does not itself mean the market will move on release day; what matters is realized versus consensus, not consensus versus previous. Since the model is forecasting before release, the correct behavior is to judge how sensitive the market is likely to be, and whether the event typically creates clean directional reactions.",
    "Step 3. If consensus_value is missing, confidence must drop. Missing consensus does not force flat every time, but it should strongly bias toward conservative behavior. Missing consensus plus low importance usually means flat and weak. Missing consensus plus direct high-importance data can still justify direction only when the rationale clearly explains why the event is structurally important for USDJPY.",
    "Step 4. Check whether the event usually moves markets through hidden details not present in the payload. Examples include CPI where traders care about core details, supercore interpretation, shelter mix, or breadth; payrolls where revisions and wages matter; GDP where components matter; inventories where the crude number can be offset by gasoline or Cushing details. If the payload does not contain the deciding internals, default to conservative flat or weak rather than pretending certainty.",
    "Step 5. Translate the event into USDJPY logic. Stronger US inflation or labor data often supports higher US yields and a stronger USD, which usually means USDJPY up. Softer US inflation or labor data often lowers yield expectations and can mean USDJPY down. Risk-off behavior can complicate the path because JPY can strengthen as a haven, so the rationale should mention when risk sentiment may interfere with the simple rates story.",
    "Step 6. Keep all output fields internally consistent. qualitative_result, mr_pred_dir, mr_pred_net_pips, mr_pred_strength, and rationale must all tell the same story. If the view is flat, pips should stay small. If the rationale says confidence is limited, do not output strong strength or large pips.",

    "INTERPRETING QUALITATIVE RESULT",
    "stronger means the release is interpreted as more USD-supportive or tighter-policy-supportive than baseline. weaker means the release is interpreted as more USD-negative or looser-policy-supportive than baseline. inline means the release is likely to produce no clear directional edge from the top-line information provided. For indirect events or missing-consensus events, inline is often the safest honest answer.",

    "IMPORTANCE AND PIP DISCIPLINE",
    "Low importance should usually live near flat to weak and near the low end of the allowed pip band. Medium importance can justify movement, but only when the transmission path is real and not mostly hidden in subcomponents. High and critical importance can justify stronger moves, but only when the signal is direct and the payload actually contains enough information. Importance alone is not a license to issue large pips. If the deciding information is absent, stay conservative even for a famous release.",

    "DIRECT VERSUS INDIRECT USDJPY CHANNELS",
    "Direct: CPI, PCE, payrolls, unemployment, wages, GDP, retail sales, ISM, PMIs, policy decisions, FOMC guidance, major consumer confidence, major housing if it affects growth sentiment broadly, and important Treasury-sensitive macro releases. Indirect: budget statements, tax receipts, auctions, balance-sheet changes, weekly petroleum status, niche inventories, administrative revisions, and local surveys with no clear Fed path. Indirect categories should usually map to flat or weak unless the rationale can name an immediate channel such as rates, growth surprise, or broad risk sentiment.",

    "HIDDEN DETAIL RULE",
    "When the top-line value is not enough to know whether traders will perceive the release as hawkish or dovish, be honest. Examples: inflation may depend on core versus headline or breadth; jobs may depend on revisions, wages, or household details; GDP may depend on inventories or consumer demand; inventory reports may depend on product mix. In such cases, default to a smaller reaction. The model is rewarded for disciplined uncertainty, not storytelling.",

    "BATCH RULES",
    "When type is batch, predict the combined cluster reaction rather than ranking each member independently. Ask whether one member is likely to dominate. If one member is clearly the market focus and the others are secondary, it can dominate the batch. If members point in opposite directions, or if the dominant interpretation depends on missing internal details, prefer flat or weak. Batch rows should act like a cluster-level judgment, not a copy of the loudest single member unless the payload truly supports that dominance.",

    "REFERENCE EXAMPLE 1: LOW-IMPORTANCE INDIRECT EVENT",
    "Input pattern: low-importance fiscal or administrative release, consensus missing or not economically central, no obvious rates channel. Good reasoning: this release is not a primary driver of Fed expectations, does not directly alter growth or inflation pricing in the next five minutes, and may matter only as background context. Best output shape: qualitative_result inline, mr_pred_dir flat, weak strength, very small pips, rationale centered on weak transmission. Bad behavior to avoid: claiming a strong directional move because one number is above or below a previous value.",

    "REFERENCE EXAMPLE 2: HIGH-IMPORTANCE INFLATION WITH MIXED SIGNALS",
    "Input pattern: headline inflation year-over-year cools while month-over-month remains warm, and the payload lacks enough core detail to settle the story. Good reasoning: the market could debate whether disinflation is intact or whether sticky monthly pressure matters more. Since the deciding internals are absent, confidence should be reduced. Best output shape: flat or weak rather than a forceful directional claim, especially for a batch cluster where the signals offset. Bad behavior to avoid: choosing a strong up or down move solely because one of the inflation measures moved in isolation.",

    "REFERENCE EXAMPLE 3: DIRECT LABOR DATA WITH CLEAR POLICY CHANNEL",
    "Input pattern: payrolls or wages with a strong consensus and historically high market sensitivity. Good reasoning: labor data can move front-end yields and policy expectations quickly. If the payload clearly indicates stronger-than-expected labor pressure, USDJPY can move up; softer-than-expected labor pressure can move down. However, if revisions or wage details are absent and usually decisive, reduce confidence. Best output shape: only medium or strong when the payload truly contains the crucial signal. Bad behavior to avoid: always issuing strong because payrolls are famous.",

    "REFERENCE EXAMPLE 4: WEEKLY ENERGY INVENTORY DATA",
    "Input pattern: crude or petroleum inventory figures, possibly with a surprise, but no full product mix or broader risk context. Good reasoning: this is usually indirect for USDJPY. Energy prices can affect inflation expectations at the margin, but the first-order channel is weak and the deciding details often lie in gasoline, distillates, refinery runs, or risk sentiment not present here. Best output shape: flat or weak with small pips. Bad behavior to avoid: turning an oil inventory print into a confident USDJPY directional macro call.",

    "REFERENCE EXAMPLE 5: BUSINESS SURVEY WITH PARTIAL DETAILS",
    "Input pattern: PMI or ISM top-line present, but not every subindex or pricing detail. Good reasoning: top-line manufacturing data can matter for growth sentiment and yields, but traders often care about new orders, employment, prices paid, or breadth. If the payload lacks the deciding mix, use moderate confidence at most. If both growth and inflation implications are mixed, prefer smaller pips. Bad behavior to avoid: assuming every PMI surprise has a clean one-direction reaction.",

    "REFERENCE EXAMPLE 6: CONSUMER SENTIMENT OR CONFIDENCE",
    "Input pattern: sentiment release with consensus present but modest direct policy transmission. Good reasoning: sentiment can matter, but it is often secondary unless the surprise is large and tied to inflation expectations or spending behavior. In the absence of detailed subcomponents, confidence should stay limited. Best output shape: often weak, sometimes flat, rarely strong. Bad behavior to avoid: making sentiment behave like CPI or payrolls.",

    "REFERENCE EXAMPLE 7: GDP TOP-LINE WITHOUT COMPONENTS",
    "Input pattern: GDP annualized number, but limited or no component detail. Good reasoning: GDP can be important, yet the market often reacts differently depending on whether strength came from consumer demand, inventories, government spending, or trade. If the payload lacks those details, do not overstate confidence. Best output shape: conservative unless the event is paired with clear component information. Bad behavior to avoid: treating all GDP upside as equally USD-positive.",

    "REFERENCE EXAMPLE 8: POLICY OR CENTRAL BANK COMMUNICATION",
    "Input pattern: speech or statement with no explicit new policy detail in the payload. Good reasoning: speeches can move markets, but only when they contain fresh guidance. Without actual hawkish or dovish language in the payload, prediction confidence should be low. Best output shape: flat or weak unless the payload includes explicit surprising guidance. Bad behavior to avoid: assuming every Fed speech causes a strong move.",

    "REFERENCE EXAMPLE 9: BATCH WITH ONE DOMINANT MEMBER",
    "Input pattern: a release cluster contains one clearly market-moving member such as CPI MoM while the others are lower-importance supporting releases. Good reasoning: it is acceptable for the batch call to lean toward the dominant member if the payload clearly shows that dominance and the other members do not offset it. Best output shape: directional, but still sized according to confidence and hidden-detail risk. Bad behavior to avoid: averaging all members mechanically when one is clearly the focus.",

    "REFERENCE EXAMPLE 10: BATCH WITH OFFSETTING MEMBERS",
    "Input pattern: one member suggests hotter inflation while another suggests cooler inflation or weaker growth, and missing consensus affects some members. Good reasoning: this often means the batch reaction should be weak or flat because the narrative is unresolved. Best output shape: flat/weak, especially if the deciding internals are missing. Bad behavior to avoid: forcing a direction because one member alone looks dramatic.",

    "REFERENCE EXAMPLE 11: MISSING CONSENSUS FOR A DIRECT HIGH-IMPORTANCE EVENT",
    "Input pattern: a direct event matters, but consensus is unavailable. Good reasoning: missing consensus lowers the model's ability to judge surprise. The correct move is not automatic flat every time, but confidence should clearly fall. If the rationale cannot identify a reliable directional edge from the payload alone, use flat or weak. Bad behavior to avoid: using previous value as though it were the market expectation when consensus is absent.",

    "REFERENCE EXAMPLE 12: WHEN TO USE STRONG",
    "Strong should be rare. Use strong only when the event is direct, important, and the payload contains enough information to support a clear surprise story with an immediate USDJPY channel. If any of those pieces are missing, medium or weak is safer. Strong should not be used simply because the event is famous or because previous values moved a lot.",

    "REFERENCE EXAMPLE 13: WHEN TO USE FLAT",
    "Flat is appropriate when the release is low-importance, indirect, missing consensus, internally offsetting, or dependent on hidden details not present here. Flat does not mean the event is worthless; it means the payload does not justify directional conviction for the first five minutes in USDJPY.",

    "REFERENCE EXAMPLE 14: HOW TO WRITE RATIONALE",
    "A good rationale is short but causal. It explains baseline versus surprise, the Fed or yields or risk channel, and why the confidence is high or low. It should say why the event affects USDJPY, not just repeat the event name. If confidence is low because consensus is missing or details are hidden, say that explicitly.",

    "REFERENCE EXAMPLE 15: CONSISTENCY CHECK BEFORE ANSWERING",
    "Before finalizing, mentally ask: If rationale says low confidence, are pips small? If rationale says signals offset, is direction flat or at least weak? If rationale says one member dominates the batch, did the direction reflect that and not the opposite? If rationale says hidden details matter, did I avoid strong certainty? The best answer is internally coherent, conservative when information is incomplete, and specific about the USDJPY transmission path.",

    "REFERENCE EXAMPLE 16: RETAIL SALES WITH CONTROL GROUP UNCERTAINTY",
    "Input pattern: retail sales top-line is present, but the payload does not include the control group, ex-auto, ex-gas, or revisions that often shape the true market read. Good reasoning: retail sales can move growth and rate expectations, but traders frequently look past the headline if the internals disagree. If the payload only shows the top-line setup, confidence should be reduced because the deciding details may be missing. Best output shape: medium or weak unless the release structure is unusually clean. Bad behavior to avoid: calling a strong USDJPY move from a headline retail sales number while ignoring missing internals.",

    "REFERENCE EXAMPLE 17: JOBLESS CLAIMS",
    "Input pattern: weekly claims with consensus available, medium importance, direct but not always dominant transmission. Good reasoning: claims can affect labor sentiment and rates, but the signal is often noisy and mean-reverting. A modest surprise usually deserves weak strength unless it clearly changes labor-market perception. Best output shape: smaller pips than payrolls, often weak, occasionally medium if the surprise is very large and unambiguous. Bad behavior to avoid: treating weekly claims as if they carry the same force as monthly payrolls.",

    "REFERENCE EXAMPLE 18: HOUSING DATA",
    "Input pattern: housing starts, permits, or home sales with consensus present but mixed macro relevance. Good reasoning: housing data matters for growth, yet the direct USDJPY channel is weaker than inflation, labor, or policy. It can matter more when the housing cycle is a central macro theme, but absent that context, confidence should remain moderate at best. Best output shape: weak to medium depending on importance and clarity. Bad behavior to avoid: projecting a large USDJPY move from a secondary housing release without a strong rates channel.",

    "REFERENCE EXAMPLE 19: TREASURY AUCTIONS",
    "Input pattern: 2-year, 5-year, 7-year, 10-year, or 30-year auction announcements or results. Good reasoning: auctions can matter for rates and term premium, but the first-order interpretation usually depends on bid-to-cover, tail, indirect bidders, and broader market positioning. If those details are not in the payload, the event is incomplete for confident FX prediction. Best output shape: often flat or weak. Bad behavior to avoid: turning a simple auction schedule or result headline into a forceful USDJPY call without the auction diagnostics.",

    "REFERENCE EXAMPLE 20: CENTRAL BANK RATE DECISION WITHOUT DOTS OR STATEMENT DETAIL",
    "Input pattern: policy decision known to be important, but the payload lacks statement language, dot plot, or press-conference guidance. Good reasoning: the top-line rate decision may be less important than the communication around it. If the payload only provides the decision shell, the event can be major in reality while still being under-specified here. Best output shape: conservative unless the payload contains the actual surprise dimension. Bad behavior to avoid: strong directional certainty on an under-described central bank event.",

    "REFERENCE EXAMPLE 21: PCE OR CPI WHEN ENERGY MAY DISTORT THE HEADLINE",
    "Input pattern: inflation series where a top-line surprise could be driven by volatile energy components, but the payload lacks the decomposition. Good reasoning: FX traders care whether the surprise changes the core inflation or policy story, not just whether the headline moved. If the payload does not reveal whether the move is broad-based or energy-driven, reduce conviction. Best output shape: conservative directional sizing, especially for headline-only data. Bad behavior to avoid: assuming every higher headline inflation print deserves strong USDJPY up.",

    "REFERENCE EXAMPLE 22: UNIVERSITY OR PRIVATE SURVEYS",
    "Input pattern: survey-based data such as regional sentiment or niche private indicators. Good reasoning: these can add color, but often lack the policy weight needed for a strong first-five-minute FX reaction. If consensus is missing or the survey is niche, flat or weak is usually best. Best output shape: inline or small directional view. Bad behavior to avoid: treating survey noise as a major macro catalyst.",

    "REFERENCE EXAMPLE 23: WHEN CONSENSUS AND PREVIOUS POINT THE SAME WAY",
    "Input pattern: consensus_value is above prev_revision for an inflation or labor print. Good reasoning: this tells you the market already expects some strength. It does not mean the release is automatically USD-positive. The release only becomes strongly USD-positive if the realized print beats consensus or if the event is inherently capable of strong price discovery even before details arrive. Since we are forecasting before the release, the right use of this pattern is to understand how much sensitivity may already be priced. Bad behavior to avoid: converting consensus-above-previous directly into stronger without acknowledging that the market already knows the consensus.",

    "REFERENCE EXAMPLE 24: WHEN CONSENSUS IS MISSING BUT THE EVENT IS STILL FAMOUS",
    "Input pattern: a famous data release with no consensus field in the payload. Good reasoning: fame does not replace missing baseline information. Even a famous release should receive reduced conviction if the payload is incomplete. If the event is direct and important, direction may still be possible, but pips and strength should be trimmed unless the payload itself provides a very clear structural clue. Bad behavior to avoid: using the event's reputation as a substitute for real information.",

    "REFERENCE EXAMPLE 25: STRONGER DOES NOT ALWAYS MEAN BIGGER PIPS",
    "Input pattern: the qualitative interpretation is stronger, but the event is only medium importance or partly hidden in detail. Good reasoning: stronger can coexist with weak or medium strength when the transmission path is real but limited. The sign and the size are separate decisions. Best output shape: stronger plus modest pips when confidence is real but not overwhelming. Bad behavior to avoid: mapping stronger automatically to strong strength.",

    "REFERENCE EXAMPLE 26: FLAT WITH AN EXPLANATION",
    "Input pattern: mixed or incomplete macro information. Good reasoning: a flat forecast still needs a rationale. It should say whether the flat view comes from offsetting members, missing consensus, indirect transmission, hidden details, or a weak rates channel. Best output shape: flat/weak with an explicit explanation of why no directional edge is justified. Bad behavior to avoid: writing a shallow rationale that merely repeats 'mixed signals' without identifying the source of uncertainty.",

    "REFERENCE EXAMPLE 27: BATCH WHERE LOW-IMPORTANCE MEMBERS SHOULD NOT OVERRULE A DIRECT HIGH-IMPORTANCE MEMBER",
    "Input pattern: one high-importance inflation or labor member is paired with several lower-importance side releases. Good reasoning: the lower-importance members can add nuance but usually should not overpower the direct high-importance macro signal unless they clearly contradict it in a material way. Best output shape: let the dominant high-importance member lead, while trimming pips if side members create uncertainty. Bad behavior to avoid: flattening every batch just because it has several members.",

    "REFERENCE EXAMPLE 28: BATCH WHERE NO MEMBER CLEARLY DOMINATES",
    "Input pattern: multiple medium or high releases arrive together, each with a plausible but different narrative, and none clearly outranks the others. Good reasoning: when there is no obvious dominant member, the batch row should represent net uncertainty, often resulting in flat or weak. Best output shape: conservative cluster judgment. Bad behavior to avoid: picking a direction simply to avoid saying flat.",

    "REFERENCE EXAMPLE 29: HOW TO TREAT REVISIONS",
    "Input pattern: prev_revision exists and may be large. Good reasoning: revisions matter as context, but if consensus exists they are not the primary surprise baseline. Mention revisions when they help explain why traders may care, but do not use them as the main comparison target in place of consensus. Best output shape: rationale can mention revisions while keeping the core logic anchored to consensus and transmission. Bad behavior to avoid: treating previous revision as if it were the expected value when consensus is present.",

    "REFERENCE EXAMPLE 30: FINAL SANITY FILTER",
    "Before answering, ask five questions. One: is the event direct or indirect for USDJPY? Two: is consensus present, and if not, did confidence fall? Three: do hidden subcomponents likely decide the real surprise? Four: is the chosen pip size consistent with importance and confidence? Five: does the batch or member logic match the payload rather than a generic macro story? If any answer is weak, reduce confidence rather than overstate certainty.",

    "OUTPUT STYLE REMINDER",
    "The model should sound calm, precise, and disciplined. Avoid hype words, certainty without evidence, or dramatic narratives unsupported by the payload. The rationale should explain why the move is likely small when it is small, and why confidence is limited when confidence is limited. The best answer is not the most exciting answer. It is the most internally consistent answer that respects the information actually provided.",

    "FINAL REMINDER",
    "Be disciplined, not imaginative. The job is not to predict the actual future release. The job is to output a plausible, internally consistent market-reaction forecast from the limited payload in a way that respects consensus, importance, hidden-detail risk, and direct versus indirect USDJPY transmission."
  ];
  return sections.join("\n\n");
}

function _buildPreSignalPlan_(ev) {
  ev = ev || {};
  var mode = _preSignalMode_(ev);
  var riskLevel = _preSignalRiskLevel_(ev, mode);
  var volatilityLevel = _preSignalVolatilityLevel_(ev, mode);
  var confidence = _preSignalScenarioConfidence_(ev, mode);
  var watchMembers = _preSignalWatchMembers_(ev, mode);
  var plan = {
    mode: mode,
    risk_level: riskLevel,
    volatility_level: volatilityLevel,
    confidence: confidence,
    watch_members: watchMembers,
    up_case: '',
    down_case: '',
    flat_case: '',
    trigger_reason: _preSignalTriggerReason_(ev, mode),
    qualitative_only: ev.type === 'batch' ? true : _isQualitativeOnly_(ev),
    hidden_detail_risk: _preSignalHiddenDetailRisk_(ev),
    direct_fx: _isDirectFxIndicator_(ev),
    anchor_mode: ev.type === 'batch' ? String(ev.batch_anchor_mode || '') : '',
    anchor_confidence: ev.type === 'batch' ? String(ev.batch_anchor_confidence || '') : ''
  };
  plan.watch_member_event_ids = watchMembers.map(function(m){ return m.event_id || ''; }).filter(Boolean).join('|');
  plan.watch_member_indicator_names = watchMembers.map(function(m){ return m.indicator_name || ''; }).filter(Boolean).join(' | ');
  plan.up_case = _preSignalCaseText_(ev, plan, 'up');
  plan.down_case = _preSignalCaseText_(ev, plan, 'down');
  plan.flat_case = _preSignalCaseText_(ev, plan, 'flat');
  plan.plan_json = _preSignalPlanJsonString_(plan);
  return plan;
}

function _preSignalPromptView_(plan) {
  plan = plan || {};
  return {
    mode: plan.mode || 'directional',
    risk_level: plan.risk_level || '',
    volatility_level: plan.volatility_level || '',
    confidence: plan.confidence || '',
    watch_members: (plan.watch_members || []).map(function(m){
      return {
        event_id: m.event_id || '',
        indicator_name: m.indicator_name || '',
        priority: m.priority || ''
      };
    }),
    up_case: plan.up_case || '',
    down_case: plan.down_case || '',
    flat_case: plan.flat_case || '',
    trigger_reason: plan.trigger_reason || ''
  };
}

function _preSignalMode_(ev) {
  var familyKey = _preSignalDominantFamilyKey_(ev);
  var importanceRank = _batchAnchorImportanceRank_(ev && ev.importance || 'medium');
  if (_isLowSignalScenarioFamilyKey_(familyKey)) return 'scenario';
  if (String(ev && ev.type || '') === 'batch') {
    if (_batchAnchorModeIsUncertain_(ev.batch_anchor_mode)) return 'scenario';
    return 'directional';
  }
  if (_isQualitativeOnly_(ev) && importanceRank >= 3) return 'scenario';
  if (_preSignalHiddenDetailRisk_(ev) && importanceRank >= 3) return 'scenario';
  return 'directional';
}

function _preSignalDominantFamilyKey_(ev) {
  ev = ev || {};
  if (String(ev.type || '') !== 'batch') return _batchAnchorFamilyKey_(String(ev.indicator_name || '').toLowerCase());
  var ranked = [];
  (ev.batch_members || []).forEach(function(member, i){
    ranked.push({
      member: member,
      meta: _scoreBatchAnchorCandidate_(member, i)
    });
  });
  return _preSignalScenarioFamilyKey_(ranked);
}

function _preSignalRiskLevel_(ev, mode) {
  var familyKey = _preSignalDominantFamilyKey_(ev);
  if (_isLowSignalScenarioFamilyKey_(familyKey)) return 'low';
  var importanceRank = _batchAnchorImportanceRank_(ev && ev.importance || 'medium');
  var directFx = _isDirectFxIndicator_(ev);
  var qualOnly = String(ev && ev.type || '') === 'batch' ? true : _isQualitativeOnly_(ev);
  var hiddenRisk = _preSignalHiddenDetailRisk_(ev);
  var score = Math.max(0, importanceRank - 1);
  if (directFx) score += 2;
  if (hiddenRisk) score += 1;
  if (mode === 'scenario') score += 1;
  if (qualOnly && importanceRank >= 3) score += 1;
  if (String(ev && ev.type || '') === 'batch' && _batchAnchorModeIsUncertain_(ev.batch_anchor_mode) && !directFx && importanceRank <= 2) score -= 1;
  if (score >= 5) return 'high';
  if (score >= 2) return 'medium';
  return 'low';
}

function _preSignalVolatilityLevel_(ev, mode) {
  var familyKey = _preSignalDominantFamilyKey_(ev);
  if (_isLowSignalScenarioFamilyKey_(familyKey)) return 'low';
  var importanceRank = _batchAnchorImportanceRank_(ev && ev.importance || 'medium');
  var directFx = _isDirectFxIndicator_(ev);
  var qualOnly = String(ev && ev.type || '') === 'batch' ? true : _isQualitativeOnly_(ev);
  var hiddenRisk = _preSignalHiddenDetailRisk_(ev);
  var score = Math.max(0, importanceRank - 1);
  if (directFx) score += 2;
  if (hiddenRisk && importanceRank >= 3) score += 1;
  if (qualOnly && importanceRank >= 3) score += 1;
  if (String(ev && ev.type || '') === 'batch' && _batchAnchorModeIsUncertain_(ev.batch_anchor_mode) && directFx && importanceRank >= 2) score += 1;
  if (!directFx && importanceRank <= 1) score -= 1;
  if (mode === 'scenario' && String(ev && ev.type || '') !== 'batch' && hiddenRisk && importanceRank >= 3) score += 1;
  if (score >= 5) return 'high';
  if (score >= 2) return 'medium';
  return 'low';
}

function _preSignalScenarioConfidence_(ev, mode) {
  var familyKey = _preSignalDominantFamilyKey_(ev);
  if (_isLowSignalScenarioFamilyKey_(familyKey)) return 'low';
  var importanceRank = _batchAnchorImportanceRank_(ev && ev.importance || 'medium');
  var directFx = _isDirectFxIndicator_(ev);
  var hasConsensus = String(ev && ev.type || '') === 'batch' ? !!ev.batch_has_consensus : _hasNumericValue_(ev && ev.consensus_value);
  var hiddenRisk = _preSignalHiddenDetailRisk_(ev);
  if (mode === 'directional') {
    if (directFx && hasConsensus && !hiddenRisk) return 'high';
    return 'medium';
  }
  if (String(ev && ev.type || '') === 'batch' && _batchAnchorModeIsUncertain_(ev.batch_anchor_mode)) return 'medium';
  if (_isQualitativeOnly_(ev) && importanceRank >= 3) return 'medium';
  if (hiddenRisk && importanceRank >= 3) return 'medium';
  return 'low';
}

function _preSignalTriggerReason_(ev, mode) {
  var familyKey = _preSignalDominantFamilyKey_(ev);
  var importanceRank = _batchAnchorImportanceRank_(ev && ev.importance || 'medium');
  if (mode === 'directional') return 'directional_allowed';
  if (familyKey === 'cftc_positions') return 'low_signal_positions_cluster';
  if (familyKey === 'treasury_auctions') return 'low_signal_auction_cluster';
  if (familyKey === 'fed_speeches') return 'text_event_speech_cluster';
  if (familyKey === 'statement_report_text') return 'text_event_report_cluster';
  if (String(ev && ev.type || '') === 'batch' && String(ev.batch_anchor_mode || '') === 'weak_anchor') return 'weak_anchor_batch';
  if (String(ev && ev.type || '') === 'batch' && String(ev.batch_anchor_mode || '') === 'no_clear_anchor') return 'no_clear_anchor_batch';
  if (_isQualitativeOnly_(ev) && importanceRank >= 3) return 'high_importance_qualitative_event';
  if (_preSignalHiddenDetailRisk_(ev) && importanceRank >= 3) return 'high_importance_hidden_detail_risk';
  return 'scenario_needed';
}

function _isLowSignalScenarioFamilyKey_(familyKey) {
  return [
    'cftc_positions',
    'treasury_auctions',
    'fed_speeches',
    'statement_report_text'
  ].indexOf(String(familyKey || '')) >= 0;
}

function _preSignalHiddenDetailRisk_(ev) {
  ev = ev || {};
  if (String(ev.type || '') === 'batch' && _batchAnchorModeIsUncertain_(ev.batch_anchor_mode)) return true;
  var names = [];
  if (ev.indicator_name) names.push(String(ev.indicator_name));
  (ev.batch_members || []).forEach(function(m){
    if (m && m.indicator_name) names.push(String(m.indicator_name));
  });
  var hay = names.join(' | ').toLowerCase();
  return /\bcpi\b|\bpce\b|\bnon[\s-]?farm payrolls?\b|\bnfp\b|\baverage hourly earnings\b|\bgdp\b|\bretail sales\b|\bism\b|\bpmi\b|\bfomc\b|\brate decision\b|\bpress conference\b|\bstatement\b|\bminutes\b/.test(hay);
}

function _preSignalWatchMembers_(ev, mode) {
  ev = ev || {};
  if (String(ev.type || '') === 'batch') return _preSignalWatchBatchMembers_(ev, mode);
  return [{
    event_id: ev.event_id || '',
    indicator_name: ev.indicator_name || '',
    priority: 1,
    reason: 'primary_event'
  }];
}

function _preSignalWatchBatchMembers_(ev, mode) {
  var ranked = [];
  (ev.batch_members || []).forEach(function(member, i){
    ranked.push({
      member: member,
      meta: _scoreBatchAnchorCandidate_(member, i)
    });
  });
  ranked.sort(function(a, b){
    return _isBetterBatchAnchorScore_(a.meta, b.meta) ? -1 : (_isBetterBatchAnchorScore_(b.meta, a.meta) ? 1 : 0);
  });
  var chosen = ranked;
  var preferredFamily = _preSignalScenarioFamilyKey_(ranked);
  var limit = _preSignalWatchLimit_(mode, preferredFamily);
  if (preferredFamily) {
    chosen = ranked.filter(function(item){
      return String(item.meta && item.meta.family_key || '') === preferredFamily;
    });
  }
  if (mode === 'scenario') {
    chosen = _preSignalProfileWatchItems_(ranked, chosen, preferredFamily, limit);
  }
  return _preSignalWatchRowsFromItems_(chosen.slice(0, limit));
}

function _preSignalWatchRowsFromItems_(items) {
  return (items || []).map(function(item, idx){
    return {
      event_id: item.member && item.member.event_id || '',
      indicator_name: item.member && item.member.indicator_name || '',
      priority: idx + 1,
      score: item.meta && item.meta.score || 0,
      importance: item.member && item.member.importance || '',
      genre: item.member && item.member.genre || '',
      role: _batchAnchorFamilyRole_(item.meta && item.meta.name || '', item.meta && item.meta.family_key || '')
    };
  });
}

function _preSignalWatchLimit_(mode, preferredFamily) {
  if (mode !== 'scenario') return 2;
  var profile = _batchAnchorFamilyProfile_(preferredFamily);
  if (profile && profile.watch_limit) return profile.watch_limit;
  return 3;
}

function _batchAnchorModeIsUncertain_(mode) {
  mode = String(mode || '');
  return mode === 'weak_anchor' || mode === 'no_clear_anchor';
}

function _preSignalProfileWatchItems_(ranked, fallbackChosen, familyKey, limit) {
  var profile = _batchAnchorFamilyProfile_(familyKey);
  if (!profile || !profile.watch_roles || !profile.watch_roles.length) return fallbackChosen;

  var familyItems = (ranked || []).filter(function(item){
    return String(item && item.meta && item.meta.family_key || '') === String(familyKey || '');
  });
  var byRole = {};
  familyItems.forEach(function(item){
    var role = _batchAnchorFamilyRole_(item.meta && item.meta.name || '', familyKey);
    if (profile.watch_roles.indexOf(role) < 0) return;
    if (!byRole[role] || _isBetterBatchAnchorScore_(item.meta, byRole[role].meta)) {
      byRole[role] = item;
    }
  });

  var chosen = [];
  var seen = {};
  profile.watch_roles.forEach(function(role){
    var item = byRole[role];
    if (!item || chosen.length >= limit) return;
    var id = String(item.member && item.member.event_id || item.meta && item.meta.name || role);
    if (seen[id]) return;
    seen[id] = true;
    chosen.push(item);
  });

  (fallbackChosen || []).forEach(function(item){
    if (!item || chosen.length >= limit) return;
    var id = String(item.member && item.member.event_id || item.meta && item.meta.name || '');
    if (!id || seen[id]) return;
    seen[id] = true;
    chosen.push(item);
  });

  return chosen.length ? chosen : fallbackChosen;
}

function _preSignalScenarioFamilyKey_(ranked) {
  ranked = ranked || [];
  var buckets = {};
  ranked.forEach(function(item){
    var key = String(item && item.meta && item.meta.family_key || '');
    if (!key || !_batchAnchorFamilyNeedsCaution_(key)) return;
    if (!buckets[key]) buckets[key] = [];
    buckets[key].push(item);
  });
  var bestKey = '';
  var bestScore = Number.NEGATIVE_INFINITY;
  Object.keys(buckets).forEach(function(key){
    var items = buckets[key];
    if (!items || items.length < 2) return;
    var score = Number(items[0].meta.score || 0) + Number(items[1].meta.score || 0);
    if (score > bestScore) {
      bestScore = score;
      bestKey = key;
    }
  });
  return bestKey;
}

function _preSignalCaseText_(ev, plan, kind) {
  var watchNames = plan.watch_member_indicator_names || (ev && ev.indicator_name) || 'the event';
  var prefix = (plan.mode === 'scenario') ? ('Watch ' + watchNames + '. ') : '';
  var qualOnly = !!plan.qualitative_only;
  var hiddenRisk = !!plan.hidden_detail_risk;
  if (kind === 'up') {
    if (String(ev && ev.type || '') === 'batch') return prefix + 'If the watched members align in a USD-supportive direction versus expectations, USDJPY likely up.';
    if (qualOnly) return prefix + 'If the communication lands more hawkish or more USD-supportive than expected, USDJPY likely up.';
    if (hiddenRisk) return prefix + 'If the release and its key internals land in a USD-supportive direction versus expectations, USDJPY likely up.';
    return prefix + 'If the release is stronger than expected in a USD-supportive way, USDJPY likely up.';
  }
  if (kind === 'down') {
    if (String(ev && ev.type || '') === 'batch') return prefix + 'If the watched members align in a USD-negative or softer direction versus expectations, USDJPY likely down.';
    if (qualOnly) return prefix + 'If the communication lands more dovish or more USD-negative than expected, USDJPY likely down.';
    if (hiddenRisk) return prefix + 'If the release and its key internals land in a USD-negative or softer direction versus expectations, USDJPY likely down.';
    return prefix + 'If the release is weaker than expected in a USD-negative way, USDJPY likely down.';
  }
  return prefix + 'If the signals are mixed, close to expectations, or the deciding detail sits outside the payload, reaction likely flat or weak.';
}

function _preSignalPlanJsonString_(plan) {
  return JSON.stringify({
    mode: plan.mode || 'directional',
    risk_level: plan.risk_level || '',
    volatility_level: plan.volatility_level || '',
    confidence: plan.confidence || '',
    trigger_reason: plan.trigger_reason || '',
    qualitative_only: !!plan.qualitative_only,
    hidden_detail_risk: !!plan.hidden_detail_risk,
    direct_fx: !!plan.direct_fx,
    anchor_mode: plan.anchor_mode || '',
    anchor_confidence: plan.anchor_confidence || '',
    watch_members: plan.watch_members || [],
    up_case: plan.up_case || '',
    down_case: plan.down_case || '',
    flat_case: plan.flat_case || ''
  });
}

function _strictParsePredictionJson_(raw) {
  // First parse attempt
  var obj = JSON.parse(raw);

  // Case A: provider returned a quoted JSON blob → parse the inner JSON
  if (typeof obj === 'string') {
    var s = obj.trim();

    // tolerate simple code fences inside quoted content (rare but seen)
    if (/^```/i.test(s)) {
      s = s.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim();
    }
    obj = JSON.parse(s);
  }

  // Case B: provider returned a top-level array → take the first object
  if (Array.isArray(obj)) {
    var chosen = null;
    for (var i = 0; i < obj.length; i++) {
      var it = obj[i];
      if (it && typeof it === 'object' && !Array.isArray(it)) {
        // Prefer the item that declares object: "ai_prediction"
        if (String(it.object || '').toLowerCase() === 'ai_prediction') { chosen = it; break; }
        if (!chosen) chosen = it;
      }
    }
    if (!chosen) throw _schemaErr_('array_has_no_object');
    obj = chosen;
  }

  // Keep your strict validations
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) throw _schemaErr_('not_an_object');
  if ((obj.object || '').toLowerCase() !== 'ai_prediction') throw _schemaErr_('bad_object');
  if (!obj.event_id) throw _schemaErr_('missing_event_id');
  if (!obj.type) throw _schemaErr_('missing_type');

  return obj;
}

/** =========================
 *  Provider resolution & calls
 *  ========================= */
function _resolveProviders_(want) {
  var out = [];
  var ask = (want || []).map(_normalizeProviderName_);
  (ask||[]).forEach(function(name){
    if (name === 'Gemini') {
      var key = _getKey_(['GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_AI_STUDIO_API_KEY']);
      if (key) out.push({ name:'Gemini', key:key, model: CFG.GEMINI_MODEL, fn:_callGemini_ });
    } else if (name === 'OpenAI') {
      var k = _getKey_(['OPENAI_API_KEY']);
      if (k) {
        var mdl = (CFG.OPENAI_MODEL || '').trim() || 'gpt-4o-mini';
        out.push({ name:'OpenAI', key:k, model: mdl, fn:_callOpenAI_ });
      }
    } else if (name === 'Anthropic' || name === 'Claude') {
      var ka = _getKey_(['ANTHROPIC_API_KEY']);
      if (ka) out.push({ name:'Anthropic', key:ka, model: CFG.CLAUDE_MODEL, fn:_callClaude_ });
    }
  });
  return out;
}



// --- OpenAI ---
function _callOpenAI_(prov, prompt) {
  if (!prov.model || String(prov.model).trim() === '') {
  throw _providerErr_('OpenAI: model not set (CFG.OPENAI_MODEL is empty)');
  }
  var url = 'https://api.openai.com/v1/chat/completions';
  var body = {
    model: prov.model,
    temperature: CFG.PREDICTION_TEMPERATURE,
    seed: CFG.PREDICTION_SEED,
    response_format: { type: 'json_object' },
    messages: [
      { role:'system', content: prompt.system },
      { role:'user',   content: prompt.user + "\n\n" + prompt.instruction }
    ]
  };
  return _withRetries_(function(){
    var resp = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'Authorization':'Bearer '+prov.key },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = resp.getResponseCode();
    if (code === 429) throw _quotaErr_('OpenAI 429');
    if (code>=500) throw _providerErr_('OpenAI '+code);
    if (code<200 || code>299) throw _providerErr_('OpenAI '+code+': '+resp.getContentText());
    var j = JSON.parse(resp.getContentText());
    var c = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
    if (!c) throw _providerErr_('OpenAI: empty content');
    var parsed = _strictParsePredictionJson_(c);
    var usage = j.usage || {};
    return {
      ai_name: 'OpenAI',
      ai_version: j.model || prov.model,
      ai_model: j.model || prov.model,
      parsed: parsed,
      raw_output: c,
      prompt_tokens: usage.prompt_tokens || null,
      completion_tokens: usage.completion_tokens || null,
      cache_creation_input_tokens: null,
      cache_read_input_tokens: usage.prompt_tokens_details && usage.prompt_tokens_details.cached_tokens || null
    };
  }, { provider:'OpenAI' });
}

// --- Gemini ---
function _callGemini_(prov, prompt) {
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(prov.model)+':generateContent?key='+encodeURIComponent(prov.key);
  var body = {
    contents: [{ role:'user', parts:[{ text: prompt.system+"\n\n"+prompt.user+"\n\n"+prompt.instruction }] }],
    generationConfig: {
      response_mime_type: 'application/json',
      temperature: CFG.PREDICTION_TEMPERATURE,
      seed: CFG.PREDICTION_SEED
    }
  };
  return _withRetries_(function(){
    var resp = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = resp.getResponseCode();
    var txt  = resp.getContentText();
    if (code === 429) throw _quotaErr_('Gemini 429: '+txt);
    if (code>=500) throw _providerErr_('Gemini '+code);
    if (code<200 || code>299) throw _providerErr_('Gemini '+code+': '+txt);
    var j = JSON.parse(txt);
    var c = (j.candidates && j.candidates[0] && j.candidates[0].content && j.candidates[0].content.parts && j.candidates[0].content.parts[0] && j.candidates[0].content.parts[0].text) || '';
    if (!c) throw _providerErr_('Gemini: empty content');
    var cleaned = _stripCodeFences_(c);
    var jsonText = _extractFirstJsonObject_(cleaned) || cleaned;
    var parsed = _strictParsePredictionJson_(jsonText);
    var usage = j.usageMetadata || {};
    return {
      ai_name: 'Gemini',
      ai_version: prov.model,
      ai_model: prov.model,
      parsed: parsed,
      raw_output: c,
      prompt_tokens: usage.promptTokenCount || null,
      completion_tokens: usage.candidatesTokenCount || null,
      cache_creation_input_tokens: null,
      cache_read_input_tokens: usage.cachedContentTokenCount || null
    };
  }, { provider:'Gemini' });
}

function _stripCodeFences_(s) {
  if (!s) return s;
  return String(s)
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/, '')
    .trim();
}

function _extractFirstJsonObject_(s) {
  if (!s) return null;
  var txt = String(s);
  var start = txt.indexOf('{');
  if (start < 0) return null;
  var depth = 0;
  for (var i = start; i < txt.length; i++) {
    var ch = txt[i];
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return txt.slice(start, i + 1);
    }
  }
  return null;
}


// --- Claude (Anthropic) ---
function _callClaude_(prov, prompt) {
  var url = 'https://api.anthropic.com/v1/messages';
  var staticPromptText = [
    prompt.system,
    prompt.instruction,
    prompt.cache_scaffold || ''
  ].filter(function(part){ return !!part; }).join("\n\n");
  var staticPromptBlock = {
    type: 'text',
    text: staticPromptText
  };
  if (_anthropicPromptCacheEnabled_()) {
    staticPromptBlock.cache_control = _anthropicPromptCacheControl_();
  }
  var body = {
    model: prov.model,
    max_tokens: 2048,
    temperature: CFG.PREDICTION_TEMPERATURE,
    system: [ staticPromptBlock ],
    messages: [ { role:'user', content: [ { type:'text', text: prompt.user } ] } ]
  };
  return _withRetries_(function(){
    var resp = UrlFetchApp.fetch(url, {
      method: 'post',
      contentType: 'application/json',
      headers: { 'x-api-key': prov.key, 'anthropic-version': '2023-06-01' },
      muteHttpExceptions: true,
      payload: JSON.stringify(body)
    });
    var code = resp.getResponseCode();
    var txt  = resp.getContentText();
    if (code === 429) throw _quotaErr_('Anthropic 429: '+txt);
    if (code>=500) throw _providerErr_('Anthropic '+code);
    if (code<200 || code>299) throw _providerErr_('Anthropic '+code+': '+txt);
    var j = JSON.parse(txt);
    var c = (j.content && j.content[0] && j.content[0].text) || '';
    if (!c) throw _providerErr_('Anthropic: empty content');
    var cleaned = _stripCodeFences_(c);
    var jsonText = _extractFirstJsonObject_(cleaned) || cleaned;
    var parsed = _strictParsePredictionJson_(jsonText);
    var usage = j.usage || {};
    return {
      ai_name: 'Anthropic',
      ai_version: prov.model,
      ai_model: prov.model,
      parsed: parsed,
      raw_output: c,
      prompt_tokens: usage.input_tokens || null,
      completion_tokens: usage.output_tokens || null,
      cache_creation_input_tokens: usage.cache_creation_input_tokens || null,
      cache_read_input_tokens: usage.cache_read_input_tokens || null
    };
  }, { provider:'Anthropic' });
}

function _anthropicPromptCacheEnabled_() {
  return !!CFG.ANTHROPIC_PROMPT_CACHE_ENABLED;
}

function _anthropicPromptCacheControl_() {
  var ttl = String(CFG.ANTHROPIC_PROMPT_CACHE_TTL || '').trim();
  if (ttl === '1h') {
    return { type: 'ephemeral', ttl: '1h' };
  }
  return { type: 'ephemeral' };
}

/** =========================
 *  Normalization
 *  ========================= */
function _normalizePrediction_(ev, providerResp, opt) {
  opt = opt || {};
  var parsed = providerResp.parsed || {};
  parsed.event_id = ev.event_id;
  parsed.type = ev.type;
  var mrWindowMin = _getPredictionMrWindowMin_();
  var mrPredDir = _oneOf_((parsed.mr_pred_dir || '').toLowerCase(), ['up','down','flat']);
  var mrPredNetPips = _numOrNull_(parsed.mr_pred_net_pips);
  var mrPredStrength = _oneOf_((parsed.mr_pred_strength || '').toLowerCase(), ['weak','medium','strong']);
  var mrPredSustainMin = _numOrNull_(parsed.mr_pred_sustain_min);
  var preSignalPlan = ev.pre_signal_plan || _buildPreSignalPlan_(ev);
  ev.pre_signal_plan = preSignalPlan;
  var out = {
    ai_name: providerResp.ai_name,
    ai_version: providerResp.ai_version,
    ai_model: providerResp.ai_model || providerResp.ai_version,
    raw_output: _formatPredictionRawOutputCsv_(parsed, providerResp.raw_output),
    prompt_tokens: providerResp.prompt_tokens || null,
    completion_tokens: providerResp.completion_tokens || null,
    cache_creation_input_tokens: providerResp.cache_creation_input_tokens || null,
    cache_read_input_tokens: providerResp.cache_read_input_tokens || null,
    latency_ms: providerResp.latency_ms || null,

    object: 'ai_prediction',
    event_id: ev.event_id,
    batch_id: ev.batch_id || null,
    type: ev.type,
    ai_forecast_value: (opt.qualOnly ? null : _numOrNull_(parsed.ai_forecast_value)),
    qualitative_result: _oneOf_((parsed.qualitative_result||'').toLowerCase(), ['stronger','weaker','inline']) || _inferQualFromConsensus_(ev, parsed),
    expected_move_dir: mrPredDir || _oneOf_((parsed.expected_move_dir||'').toLowerCase(), ['up','down','flat']) || _dirFromQual_((parsed.qualitative_result||'').toLowerCase()),
    expected_move_pips_min: _numOrNull_(parsed.expected_move_pips_min),
    expected_move_pips_max: _numOrNull_(parsed.expected_move_pips_max),
    expected_holding_minutes: mrPredSustainMin != null ? mrPredSustainMin : _numOrNull_(parsed.expected_holding_minutes),
    mr_window_min: mrWindowMin,
    mr_pred_dir: mrPredDir,
    mr_pred_net_pips: mrPredNetPips,
    mr_pred_strength: mrPredStrength,
    mr_pred_sustain_min: mrPredSustainMin,
    rationale_short: parsed.rationale_short || '',
    rationale: parsed.rationale || '',
    pre_signal_mode: preSignalPlan.mode || 'directional',
    pre_risk_level: preSignalPlan.risk_level || '',
    pre_volatility_level: preSignalPlan.volatility_level || '',
    watch_member_event_ids: preSignalPlan.watch_member_event_ids || '',
    watch_member_indicator_names: preSignalPlan.watch_member_indicator_names || '',
    scenario_up_case: preSignalPlan.up_case || '',
    scenario_down_case: preSignalPlan.down_case || '',
    scenario_flat_case: preSignalPlan.flat_case || '',
    scenario_confidence: preSignalPlan.confidence || '',
    scenario_plan_json: preSignalPlan.plan_json || ''
  };

  var imp = (ev.importance || 'medium').toLowerCase();
  var band = CFG.PIPS_BY_IMPORTANCE[imp] || CFG.PIPS_BY_IMPORTANCE.medium;
  if (!(out.mr_pred_net_pips >= 0)) out.mr_pred_net_pips = _midpointPips_(band[0], band[1]);
  if (!out.mr_pred_dir) out.mr_pred_dir = out.expected_move_dir || ((out.mr_pred_net_pips<=1) ? 'flat' : 'up');
  if (!out.mr_pred_strength) out.mr_pred_strength = _mrStrengthFromPips_(out.mr_pred_net_pips);
  if (!(out.mr_pred_sustain_min > 0)) out.mr_pred_sustain_min = out.expected_holding_minutes;
  if (!(out.mr_pred_sustain_min > 0)) out.mr_pred_sustain_min = 15;

  if (!(typeof out.expected_move_pips_min === 'number' && isFinite(out.expected_move_pips_min)) && typeof out.mr_pred_net_pips === 'number') {
    out.expected_move_pips_min = Math.max(0, Math.round((out.mr_pred_net_pips - 2) * 100) / 100);
  }
  if (!(typeof out.expected_move_pips_min === 'number' && isFinite(out.expected_move_pips_min))) {
    out.expected_move_pips_min = band[0];
  }
  if (!(typeof out.expected_move_pips_max === 'number' && isFinite(out.expected_move_pips_max) && out.expected_move_pips_max >= out.expected_move_pips_min) && typeof out.mr_pred_net_pips === 'number') {
    out.expected_move_pips_max = Math.max(out.expected_move_pips_min, Math.round((out.mr_pred_net_pips + 2) * 100) / 100);
  }
  if (!(typeof out.expected_move_pips_max === 'number' && isFinite(out.expected_move_pips_max) && out.expected_move_pips_max >= out.expected_move_pips_min)) {
    out.expected_move_pips_max = band[1];
  }
  if (!out.expected_move_dir) out.expected_move_dir = (out.expected_move_pips_max<=1) ? 'flat' : 'up';
  if (!out.expected_holding_minutes) out.expected_holding_minutes = 60;
  var beforeGuardrails = _snapshotPredictionShape_(out);
  out = _applyPredictionQualityGuardrails_(ev, out, band, opt);
  out = _annotatePredictionNormalization_(out, beforeGuardrails);
  return out;
}

function _applyPredictionQualityGuardrails_(ev, out, band, opt) {
  opt = opt || {};
  var imp = String(ev.importance || 'medium').toLowerCase();
  var hasConsensus = (typeof ev.batch_has_consensus === 'boolean') ? ev.batch_has_consensus : _hasNumericValue_(ev.consensus_value);
  var hasPrev = _hasNumericValue_(ev.prev_revision);
  var directFx = _isDirectFxIndicator_(ev);
  var indirectCap = directFx ? null : _indirectIndicatorPipsCap_(imp);
  var missingConsensusCap = _missingConsensusPipsCap_(imp, directFx, hasPrev);
  var bandMax = (band && typeof band[1] === 'number') ? band[1] : null;
  var cap = bandMax;

  if (typeof indirectCap === 'number') {
    cap = (typeof cap === 'number') ? Math.min(cap, indirectCap) : indirectCap;
  }

  if (!hasConsensus) {
    cap = (typeof cap === 'number') ? Math.min(cap, missingConsensusCap) : missingConsensusCap;
  }

  if (typeof cap === 'number' && isFinite(cap) && typeof out.mr_pred_net_pips === 'number' && out.mr_pred_net_pips > cap) {
    out.mr_pred_net_pips = _roundPips_(cap);
  }

  if (!hasConsensus && (!directFx || imp === 'low' || !hasPrev || opt.qualOnly)) {
    out.mr_pred_strength = 'weak';
    if (!directFx || !hasPrev || opt.qualOnly) {
      out.mr_pred_dir = 'flat';
      out.qualitative_result = 'inline';
      out.mr_pred_net_pips = Math.min(out.mr_pred_net_pips, 2);
    }
  }

  if (typeof indirectCap === 'number') {
    if (imp === 'low') {
      out.mr_pred_dir = 'flat';
      out.qualitative_result = 'inline';
      out.mr_pred_net_pips = Math.min(out.mr_pred_net_pips, 2);
    } else if (imp === 'medium' && out.mr_pred_net_pips <= 5) {
      out.mr_pred_strength = 'weak';
    }
  }

  if (out.mr_pred_dir === 'flat') {
    out.mr_pred_net_pips = Math.min(out.mr_pred_net_pips, 2);
    out.qualitative_result = 'inline';
  }

  if (opt.isBatch) {
    var batchHorizon = (typeof out.mr_window_min === 'number' && out.mr_window_min > 0) ? out.mr_window_min : 5;
    if (String(ev.batch_anchor_mode || '') === 'no_clear_anchor') {
      out.mr_pred_strength = 'weak';
      out.mr_pred_net_pips = Math.min(out.mr_pred_net_pips, 5);
      if (!hasConsensus || !directFx) {
        out.mr_pred_dir = 'flat';
        out.qualitative_result = 'inline';
        out.mr_pred_net_pips = Math.min(out.mr_pred_net_pips, 2);
      }
    }
    if (!(out.mr_pred_sustain_min > 0)) out.mr_pred_sustain_min = batchHorizon;
    out.mr_pred_sustain_min = Math.min(_roundPips_(out.mr_pred_sustain_min), batchHorizon);
    out.expected_holding_minutes = out.mr_pred_sustain_min;
  }

  out.mr_pred_net_pips = _roundPips_(Math.max(0, Number(out.mr_pred_net_pips) || 0));
  out.mr_pred_strength = _mrStrengthFromPips_(out.mr_pred_net_pips);
  out.expected_move_dir = out.mr_pred_dir;
  out.expected_move_pips_min = Math.max(0, _roundPips_(out.mr_pred_net_pips - 2));
  out.expected_move_pips_max = Math.max(out.expected_move_pips_min, _roundPips_(out.mr_pred_net_pips + 2));
  return out;
}

function _hasNumericValue_(v) {
  return typeof v === 'number' && isFinite(v);
}

function _missingConsensusPipsCap_(importance, directFx, hasPrev) {
  var imp = String(importance || 'medium').toLowerCase();
  if (!hasPrev) return directFx && (imp === 'high' || imp === 'critical') ? 8 : 2;
  if (!directFx) return 3;
  if (imp === 'critical') return 12;
  if (imp === 'high') return 8;
  if (imp === 'medium') return 5;
  return 3;
}

function _indirectIndicatorPipsCap_(importance) {
  var imp = String(importance || 'medium').toLowerCase();
  if (imp === 'critical') return 8;
  if (imp === 'high') return 6;
  if (imp === 'medium') return 4;
  return 2;
}

function _isDirectFxIndicator_(ev) {
  if (typeof ev.batch_direct_fx === 'boolean') return ev.batch_direct_fx;
  var genre = String(ev.genre || '').toLowerCase();
  var name = String(ev.indicator_name || '').toLowerCase();
  if (/energy|fiscal|markets|auction|fedbalance|liquidity|balance/.test(genre)) return false;
  if (/\bauction\b|bond auction|note auction|oil|crude|inventory|inventories|balance sheet|fed balance|walcl|budget|fiscal|refund/i.test(name)) return false;
  if (/inflation|labor|gdp|manufacturing|sentiment/.test(genre)) return true;
  if (/cpi|pce|inflation|payroll|employment|jobless|claims|unemployment|wage|earnings|gdp|retail sales|ism|pmi|consumer confidence|umich|fed rate|fomc/.test(name)) return true;
  return false;
}

function _roundPips_(value) {
  var n = Number(value);
  if (!isFinite(n)) return 0;
  return Math.round(n * 100) / 100;
}

function _groupBatchEvents_(events) {
  var groups = {};
  (events || []).forEach(function(ev){
    if (String(ev.type || '').toLowerCase() !== 'member' || !ev.batch_id) return;
    if (!groups[ev.batch_id]) groups[ev.batch_id] = [];
    groups[ev.batch_id].push(ev);
  });
  return groups;
}

function _buildBatchReferenceEvent_(members) {
  members = members || [];
  if (!members.length) throw new Error('batch_members_required');
  var first = members[0];
  var memberIds = members.map(function(m){ return m.event_id; });
  var memberNames = members.map(function(m){ return m.indicator_name; });
  var anchor = _selectBatchAnchorMember_(members);
  return {
    object: 'econ_event_batch',
    event_id: first.batch_id,
    batch_id: first.batch_id,
    type: 'batch',
    country: first.country,
    indicator_name: 'Batch: ' + memberNames.join(' | '),
    genre: 'Batch',
    importance: _maxImportance_(members.map(function(m){ return m.importance; })),
    release_ts: first.release_ts,
    source_cal: first.source_cal || '',
    fx_pair: first.fx_pair || CFG.DEFAULT_FX,
    consensus_value: null,
    prev_revision: null,
    qualitative_only: true,
    member_count: members.length,
    member_event_ids: memberIds.join('|'),
    member_indicator_names: memberNames.join(' | '),
    batch_members: members,
    batch_anchor: anchor && anchor.member || null,
    batch_anchor_mode: anchor && anchor.mode || '',
    batch_anchor_confidence: anchor && anchor.confidence || '',
    anchor_score: anchor && anchor.score || 0,
    anchor_margin: anchor && anchor.margin || 0,
    anchor_runner_up_event_id: anchor && anchor.runner_up_member ? anchor.runner_up_member.event_id : '',
    anchor_runner_up_indicator_name: anchor && anchor.runner_up_member ? anchor.runner_up_member.indicator_name : '',
    anchor_reason: anchor && anchor.reason || '',
    batch_has_consensus: members.some(function(m){ return _hasNumericValue_(m.consensus_value); }),
    batch_direct_fx: members.some(function(m){ return _isDirectFxIndicator_(m); })
  };
}

function _selectBatchAnchorMember_(members) {
  members = members || [];
  if (!members.length) return null;
  var ranked = [];
  for (var i = 0; i < members.length; i++) {
    ranked.push({
      member: members[i],
      meta: _scoreBatchAnchorCandidate_(members[i], i)
    });
  }
  ranked.sort(function(a, b){
    return _isBetterBatchAnchorScore_(a.meta, b.meta) ? -1 : (_isBetterBatchAnchorScore_(b.meta, a.meta) ? 1 : 0);
  });

  var top = ranked[0];
  var second = ranked.length > 1 ? ranked[1] : null;
  var margin = top && second ? (top.meta.score - second.meta.score) : (top ? top.meta.score : 0);
  var sameFamily = !!(top && second && top.meta.family_key && top.meta.family_key === second.meta.family_key);
  var familyCaution = !!(sameFamily && _batchAnchorFamilyNeedsCaution_(top.meta.family_key));
  var confidence = _batchAnchorConfidence_(top && top.meta, second && second.meta, familyCaution);
  var mode = _batchAnchorMode_(top && top.meta, second && second.meta, confidence, familyCaution);
  var topName = top && top.member ? top.member.indicator_name : '';
  var secondName = second && second.member ? second.member.indicator_name : '';
  var reasonParts = [];
  if (topName) reasonParts.push('top=' + topName);
  if (secondName) reasonParts.push('runner_up=' + secondName);
  reasonParts.push('margin=' + margin);
  if (sameFamily && top && top.meta.family_key) reasonParts.push('same_family=' + top.meta.family_key);
  if (familyCaution && top && top.meta.family_key) reasonParts.push('family_caution');
  if (top && top.meta && top.meta.reason) reasonParts.push(top.meta.reason);
  var reason = reasonParts.join(', ');

  return {
    member: mode === 'no_clear_anchor' ? null : (top && top.member || null),
    runner_up_member: second && second.member || null,
    mode: mode,
    confidence: confidence,
    score: top && top.meta ? top.meta.score : 0,
    margin: margin,
    reason: reason
  };
}

function _scoreBatchAnchorCandidate_(ev, orderIndex) {
  var name = String(ev && ev.indicator_name || '');
  var nameLc = name.toLowerCase();
  var genre = String((ev && ev.genre) || _inferGenreFromName_(name) || '').toLowerCase();
  var importance = String(ev && ev.importance || 'medium').toLowerCase();
  var directFx = _isDirectFxIndicator_(ev);
  var familyKey = _batchAnchorFamilyKey_(nameLc);
  var score = 0;
  var reasons = [];

  score += _batchAnchorImportanceScore_(importance);
  if (_batchAnchorImportanceScore_(importance) > 0) reasons.push('importance=' + importance);

  var genreBonus = _batchAnchorGenreScore_(genre);
  score += genreBonus;
  if (genreBonus !== 0) reasons.push('genre=' + genre);

  var nameBonus = _batchAnchorHeadlineScore_(nameLc);
  score += nameBonus;
  if (nameBonus !== 0) reasons.push('headline=' + nameBonus);

  var supportPenalty = _batchAnchorSupportingPenalty_(nameLc, genre);
  score += supportPenalty;
  if (supportPenalty !== 0) reasons.push('supporting=' + supportPenalty);

  var familyAdjustment = _batchAnchorFamilyAdjustment_(nameLc, familyKey);
  score += familyAdjustment;
  if (familyAdjustment !== 0) reasons.push('family_adjustment=' + familyAdjustment);

  if (directFx) {
    score += 4;
    reasons.push('direct_fx');
  }
  if (_hasNumericValue_(ev && ev.consensus_value)) {
    score += 3;
    reasons.push('has_consensus');
  }
  if (_hasNumericValue_(ev && ev.prev_revision)) {
    score += 1;
    reasons.push('has_prev');
  }
  if (_isQualitativeOnly_(ev)) {
    score -= 4;
    reasons.push('qual_only=-4');
  }

  return {
    score: score,
    order_index: orderIndex,
    importance_rank: _batchAnchorImportanceRank_(importance),
    direct_fx: directFx ? 1 : 0,
    family_key: familyKey,
    name: nameLc,
    reason: reasons.join(', ')
  };
}

function _isBetterBatchAnchorScore_(a, b) {
  if (a.score !== b.score) return a.score > b.score;
  if (a.importance_rank !== b.importance_rank) return a.importance_rank > b.importance_rank;
  if (a.direct_fx !== b.direct_fx) return a.direct_fx > b.direct_fx;
  if (a.order_index !== b.order_index) return a.order_index < b.order_index;
  return a.name < b.name;
}

function _batchAnchorImportanceRank_(importance) {
  var rank = { low: 1, medium: 2, high: 3, critical: 4 };
  return rank[String(importance || '').toLowerCase()] || 2;
}

function _batchAnchorImportanceScore_(importance) {
  var rank = _batchAnchorImportanceRank_(importance);
  return rank * 10;
}

function _batchAnchorConfidence_(topMeta, secondMeta, familyCaution) {
  var topScore = topMeta ? Number(topMeta.score) : 0;
  var margin = secondMeta ? (topScore - Number(secondMeta.score || 0)) : topScore;
  if (familyCaution) {
    if (topScore >= 58 && margin >= 30) return 'high';
    if (topScore >= 44 && margin >= 18) return 'medium';
    if (topScore >= 34 && margin >= 8) return 'low';
    return 'none';
  }
  if (topScore >= 50 && margin >= 8) return 'high';
  if (topScore >= 38 && margin >= 5) return 'medium';
  if (topScore >= 30 && margin >= 3) return 'low';
  return 'none';
}

function _batchAnchorMode_(topMeta, secondMeta, confidence, familyCaution) {
  var topScore = topMeta ? Number(topMeta.score) : 0;
  var margin = secondMeta ? (topScore - Number(secondMeta.score || 0)) : topScore;
  if (familyCaution) {
    if (confidence === 'high' && topScore >= 58 && margin >= 30) return 'clear_anchor';
    if ((confidence === 'medium' || confidence === 'low') && topScore >= 34 && margin >= 8) return 'weak_anchor';
    return 'no_clear_anchor';
  }
  if (confidence === 'high' || confidence === 'medium') return 'clear_anchor';
  if (confidence === 'low' && topScore >= 32 && margin >= 3) return 'weak_anchor';
  return 'no_clear_anchor';
}

function _batchAnchorFamilyNeedsCaution_(familyKey) {
  return [
    'monthly_labor',
    'ism_services',
    'ism_manufacturing',
    'sp_global_pmi',
    'macro_inflation_retail',
    'cftc_positions',
    'treasury_auctions',
    'fed_speeches',
    'statement_report_text',
    'factory_orders',
    'jobless_claims',
    'eia_petroleum',
    'mba_mortgage',
    'mortgage_rates',
    'vehicle_sales'
  ].indexOf(String(familyKey || '')) >= 0;
}

function _batchAnchorFamilyKey_(nameLc) {
  if (!nameLc) return '';
  if (/non[\s-]?farm payrolls|unemployment rate|average hourly earnings|average weekly hours|participation rate|private.*payroll|payroll.*private|manufacturing payroll|government payroll|u-6 unemployment/.test(nameLc)) return 'monthly_labor';
  if (/initial jobless claims|continuing jobless claims|jobless claims 4-week average|jobless claims four-week average/.test(nameLc)) return 'jobless_claims';
  if (/ism services|ism non-manufacturing/.test(nameLc)) return 'ism_services';
  if (/ism manufacturing/.test(nameLc)) return 'ism_manufacturing';
  if (/s&p global services|s&p global composite/.test(nameLc)) return 'sp_global_pmi';
  if (/\b(cpi\b|cpi s\.a\b|inflation rate|core inflation rate|retail sales|empire state manufacturing index)\b/.test(nameLc)) return 'macro_inflation_retail';
  if (/\bcftc\b.*\bspeculative net positions?\b/.test(nameLc)) return 'cftc_positions';
  if (/\b(?:\d{1,2}-week bill auction|\d{1,2}-month bill auction|\d+-year note auction|\d+-year bond auction|bill auction|note auction|bond auction)\b/.test(nameLc)) return 'treasury_auctions';
  if (/\b(?:fed .*speech|speech|testimony|press conference)\b/.test(nameLc)) return 'fed_speeches';
  if (/\b(?:fomc minutes|minutes|beige book|wasde report|monthly budget statement|treasury refunding announcement|statement)\b/.test(nameLc)) return 'statement_report_text';
  if (/factory orders/.test(nameLc)) return 'factory_orders';
  if (/\beia\b/.test(nameLc) && /\b(crude|gasoline|distillate|heating oil|refinery|cushing)\b/.test(nameLc)) return 'eia_petroleum';
  if (/\bcrude oil imports\b/.test(nameLc) || /\beia weekly refinery utilization rates\b/.test(nameLc)) return 'eia_petroleum';
  if (/30-year mortgage rate|15-year mortgage rate/.test(nameLc)) return 'mortgage_rates';
  if (/all car sales|all truck sales/.test(nameLc)) return 'vehicle_sales';
  if (/mba mortgage|\bmba purchase index\b|\bmba mortgage market index\b|\bmba mortgage refinance index\b|\bmba refinance index\b|\bmba mortgage applications\b|\bmba 30-year mortgage rate\b/.test(nameLc)) return 'mba_mortgage';
  return '';
}

function _batchAnchorFamilyProfile_(familyKey) {
  familyKey = String(familyKey || '');
  if (familyKey === 'monthly_labor') {
    return {
      watch_limit: 5,
      watch_roles: ['headline_nfp', 'unemployment', 'wages', 'manufacturing_payrolls', 'private_payrolls'],
      role_adjustments: {
        headline_nfp: 12,
        unemployment: 14,
        wages: 12,
        manufacturing_payrolls: 10,
        private_payrolls: 8,
        government_payrolls: 4,
        participation: 4,
        weekly_hours: 2,
        u6: 2
      }
    };
  }
  if (familyKey === 'jobless_claims') {
    return {
      watch_limit: 3,
      watch_roles: ['initial_claims', 'continuing_claims', 'four_week_average'],
      role_adjustments: {
        initial_claims: 12,
        continuing_claims: 10,
        four_week_average: 6
      }
    };
  }
  if (familyKey === 'factory_orders') {
    return {
      watch_limit: 3,
      watch_roles: ['ex_transportation', 'headline_orders', 'ex_defense'],
      role_adjustments: {
        ex_transportation: 14,
        headline_orders: 10,
        ex_defense: 6,
        shipments: 2,
        inventories: 2,
        unfilled_orders: 2
      }
    };
  }
  if (familyKey === 'ism_services') {
    return {
      watch_limit: 4,
      watch_roles: ['prices', 'new_orders', 'business_activity', 'employment'],
      role_adjustments: {
        headline_pmi: -20,
        prices: 14,
        new_orders: 16,
        business_activity: 16,
        employment: 14,
        supplier_deliveries: -4,
        inventories: -4
      }
    };
  }
  if (familyKey === 'macro_inflation_retail') {
    return {
      watch_limit: 6,
      watch_roles: ['core_cpi', 'headline_cpi', 'retail_mom', 'retail_core_mom', 'retail_yoy', 'headline_cpi_sa'],
      role_adjustments: {
        core_cpi: 18,
        headline_cpi: 16,
        headline_cpi_sa: 12,
        retail_mom: 16,
        retail_core_mom: 14,
        retail_yoy: 10,
        empire_state: -6
      }
    };
  }
  if (familyKey === 'cftc_positions') {
    return {
      watch_limit: 5,
      watch_roles: ['sp500', 'nasdaq', 'gold', 'silver', 'crude_oil'],
      role_adjustments: {
        sp500: 10,
        nasdaq: 10,
        gold: 8,
        silver: 6,
        crude_oil: 6,
        copper: 2,
        natural_gas: 0,
        corn: -2,
        wheat: -2,
        soybeans: -2,
        aluminium: -2
      }
    };
  }
  if (familyKey === 'treasury_auctions') {
    return {
      watch_limit: 3,
      watch_roles: ['short_bill', 'benchmark_note', 'long_bond'],
      role_adjustments: {
        short_bill: 4,
        benchmark_note: 6,
        long_bond: 6,
        other_auction: 2
      }
    };
  }
  if (familyKey === 'fed_speeches') {
    return {
      watch_limit: 3,
      watch_roles: ['press_conference', 'chair_or_core_board', 'regional_fed'],
      role_adjustments: {
        press_conference: 8,
        chair_or_core_board: 6,
        regional_fed: 4,
        other_speech: 2
      }
    };
  }
  if (familyKey === 'statement_report_text') {
    return {
      watch_limit: 3,
      watch_roles: ['fomc_minutes', 'beige_book', 'budget_or_refunding'],
      role_adjustments: {
        fomc_minutes: 8,
        beige_book: 6,
        budget_or_refunding: 4,
        report_text: 2
      }
    };
  }
  if (familyKey === 'eia_petroleum') {
    return {
      watch_limit: 6,
      watch_roles: ['distillate_production', 'refinery_activity', 'crude_stocks', 'gasoline_stocks', 'gasoline_production', 'distillate_stocks'],
      role_adjustments: {
        distillate_production: 18,
        refinery_activity: 14,
        crude_stocks: 10,
        gasoline_stocks: 10,
        gasoline_production: 9,
        distillate_stocks: 10,
        crude_imports: -4,
        cushing_stocks: -6,
        heating_oil_stocks: -4
      }
    };
  }
  if (familyKey === 'mba_mortgage') {
    return {
      watch_limit: 4,
      watch_roles: ['purchase_index', 'market_index', 'refinance_index', 'thirty_year_rate'],
      role_adjustments: {
        purchase_index: 14,
        market_index: 12,
        refinance_index: 10,
        applications: 8,
        thirty_year_rate: 8
      }
    };
  }
  return null;
}

function _batchAnchorFamilyRole_(nameLc, familyKey) {
  nameLc = String(nameLc || '');
  familyKey = String(familyKey || '');
  if (familyKey === 'monthly_labor') {
    if (/\bmanufacturing payroll/.test(nameLc)) return 'manufacturing_payrolls';
    if (/\bprivate\b/.test(nameLc) && /\bpayrolls?\b/.test(nameLc)) return 'private_payrolls';
    if (/\bgovernment payroll/.test(nameLc)) return 'government_payrolls';
    if (/\bnon[\s-]?farm payrolls?\b|\bnfp\b/.test(nameLc)) return 'headline_nfp';
    if (/\bunemployment rate\b/.test(nameLc)) return 'unemployment';
    if (/\baverage hourly earnings\b|\bwages?\b/.test(nameLc)) return 'wages';
    if (/\bparticipation rate\b|\blabor force participation\b/.test(nameLc)) return 'participation';
    if (/\baverage weekly hours\b/.test(nameLc)) return 'weekly_hours';
    if (/\bu[\s-]?6 unemployment\b/.test(nameLc)) return 'u6';
  }
  if (familyKey === 'jobless_claims') {
    if (/\b(initial jobless claims|jobless claims)\b/.test(nameLc) && !/\b(4-week|4 week|four-week average|continuing)\b/.test(nameLc)) return 'initial_claims';
    if (/\bcontinuing jobless claims\b/.test(nameLc)) return 'continuing_claims';
    if (/\b(4-week|4 week|four-week average)\b/.test(nameLc)) return 'four_week_average';
  }
  if (familyKey === 'factory_orders') {
    if (/\bex transportation\b|\bexcluding transportation\b/.test(nameLc)) return 'ex_transportation';
    if (/\bex defense\b|\bexcluding defense\b/.test(nameLc)) return 'ex_defense';
    if (/\bshipments\b/.test(nameLc)) return 'shipments';
    if (/\binventories\b/.test(nameLc)) return 'inventories';
    if (/\bunfilled orders\b/.test(nameLc)) return 'unfilled_orders';
    if (/\bfactory orders\b/.test(nameLc)) return 'headline_orders';
  }
  if (familyKey === 'ism_services') {
    if (/\bprices\b/.test(nameLc)) return 'prices';
    if (/\bnew orders\b/.test(nameLc)) return 'new_orders';
    if (/\bbusiness activity\b/.test(nameLc)) return 'business_activity';
    if (/\bemployment\b/.test(nameLc)) return 'employment';
    if (/\bsupplier deliveries\b/.test(nameLc)) return 'supplier_deliveries';
    if (/\binventories\b/.test(nameLc)) return 'inventories';
    if (/\bism\b.*\bpmi\b/.test(nameLc)) return 'headline_pmi';
  }
  if (familyKey === 'macro_inflation_retail') {
    if (/\bcore inflation rate\b|\bcore cpi\b/.test(nameLc)) return 'core_cpi';
    if (/\bcpi s\.a\b/.test(nameLc)) return 'headline_cpi_sa';
    if ((/\binflation rate\b/.test(nameLc) || /\bcpi\b/.test(nameLc)) && !/\bcore\b/.test(nameLc) && !/\bs\.a\b/.test(nameLc)) return 'headline_cpi';
    if (/\bretail sales ex gas\/autos\b|\bretail sales ex autos\b/.test(nameLc)) return 'retail_core_mom';
    if (/\bretail sales\b/.test(nameLc) && /\bmom\b/.test(nameLc)) return 'retail_mom';
    if (/\bretail sales\b/.test(nameLc) && /\byoy\b/.test(nameLc)) return 'retail_yoy';
    if (/\bempire state manufacturing index\b/.test(nameLc)) return 'empire_state';
  }
  if (familyKey === 'cftc_positions') {
    if (/\bs&p 500\b/.test(nameLc)) return 'sp500';
    if (/\bnasdaq 100\b/.test(nameLc)) return 'nasdaq';
    if (/\bgold\b/.test(nameLc)) return 'gold';
    if (/\bsilver\b/.test(nameLc)) return 'silver';
    if (/\bcrude oil\b/.test(nameLc)) return 'crude_oil';
    if (/\bcopper\b/.test(nameLc)) return 'copper';
    if (/\bnatural gas\b/.test(nameLc)) return 'natural_gas';
    if (/\bcorn\b/.test(nameLc)) return 'corn';
    if (/\bwheat\b/.test(nameLc)) return 'wheat';
    if (/\bsoybeans\b/.test(nameLc)) return 'soybeans';
    if (/\baluminium\b/.test(nameLc)) return 'aluminium';
  }
  if (familyKey === 'treasury_auctions') {
    if (/\b(?:4-week|8-week|17-week|26-week|42-day|43-day|52-week|3-month|6-month)\b/.test(nameLc)) return 'short_bill';
    if (/\b(?:2-year|3-year|5-year|7-year|10-year)\b/.test(nameLc)) return 'benchmark_note';
    if (/\b(?:20-year|30-year)\b/.test(nameLc)) return 'long_bond';
    if (/\bauction\b/.test(nameLc)) return 'other_auction';
  }
  if (familyKey === 'fed_speeches') {
    if (/\bpress conference\b/.test(nameLc)) return 'press_conference';
    if (/\b(?:powell|waller|jefferson|barr|cook|bowman)\b/.test(nameLc)) return 'chair_or_core_board';
    if (/\bfed\b/.test(nameLc)) return 'regional_fed';
    if (/\b(?:speech|testimony)\b/.test(nameLc)) return 'other_speech';
  }
  if (familyKey === 'statement_report_text') {
    if (/\bfomc minutes\b|\bminutes\b/.test(nameLc)) return 'fomc_minutes';
    if (/\bbeige book\b/.test(nameLc)) return 'beige_book';
    if (/\bmonthly budget statement\b|\btreasury refunding announcement\b/.test(nameLc)) return 'budget_or_refunding';
    if (/\b(?:statement|wasde report)\b/.test(nameLc)) return 'report_text';
  }
  if (familyKey === 'eia_petroleum') {
    if (/\bdistillate fuel production\b/.test(nameLc)) return 'distillate_production';
    if (/\bweekly refinery utilization rates\b|\brefinery crude runs\b/.test(nameLc)) return 'refinery_activity';
    if (/\bcrude oil stocks\b/.test(nameLc) && !/\bcushing\b/.test(nameLc)) return 'crude_stocks';
    if (/\bgasoline stocks\b/.test(nameLc)) return 'gasoline_stocks';
    if (/\bdistillate stocks\b/.test(nameLc)) return 'distillate_stocks';
    if (/\bgasoline production\b/.test(nameLc)) return 'gasoline_production';
    if (/\bcrude oil imports\b/.test(nameLc)) return 'crude_imports';
    if (/\bcushing crude oil stocks\b/.test(nameLc)) return 'cushing_stocks';
    if (/\bheating oil stocks\b/.test(nameLc)) return 'heating_oil_stocks';
  }
  if (familyKey === 'mba_mortgage') {
    if (/\bpurchase index\b/.test(nameLc)) return 'purchase_index';
    if (/\bmortgage market index\b/.test(nameLc)) return 'market_index';
    if (/\brefinance index\b/.test(nameLc)) return 'refinance_index';
    if (/\bmortgage applications\b/.test(nameLc)) return 'applications';
    if (/\b30-year mortgage rate\b/.test(nameLc)) return 'thirty_year_rate';
  }
  return '';
}

function _batchAnchorFamilyAdjustment_(nameLc, familyKey) {
  if (!nameLc) return 0;
  familyKey = String(familyKey || '');
  var profile = _batchAnchorFamilyProfile_(familyKey);
  if (profile && profile.role_adjustments) {
    var role = _batchAnchorFamilyRole_(nameLc, familyKey);
    if (profile.role_adjustments.hasOwnProperty(role)) return profile.role_adjustments[role];
  }
  var score = 0;
  if (familyKey === 'ism_manufacturing' || familyKey === 'ism_services') {
    var isToplinePmi = /\bism\b.*\bpmi\b/.test(nameLc) &&
      !(/\bemployment\b|\bprices\b|\bnew orders\b|\bbusiness activity\b|\bsupplier deliveries\b|\binventories\b/.test(nameLc));
    if (isToplinePmi) score -= 12;
    if (/\bemployment\b/.test(nameLc)) score += 14;
    if (/\bprices\b/.test(nameLc)) score += 12;
    if (/\bnew orders\b/.test(nameLc)) score += 10;
    if (/\bbusiness activity\b/.test(nameLc)) score += 8;
    if (/\bsupplier deliveries\b|\binventories\b/.test(nameLc)) score -= 4;
  }
  return score;
}

function _batchAnchorGenreScore_(genre) {
  var bonuses = {
    inflation: 16,
    labor: 16,
    gdp: 14,
    manufacturing: 10,
    sentiment: 6,
    housing: 4,
    consumption: 6,
    trade: 2,
    energy: -6,
    'fiscal/markets': -8,
    fedbalance: -10,
    batch: -4,
    general: 0,
    other: 0
  };
  return bonuses.hasOwnProperty(genre) ? bonuses[genre] : 0;
}

function _batchAnchorHeadlineScore_(nameLc) {
  if (!nameLc) return 0;
  var score = 0;
  if (/\bnon[\s-]?farm payrolls?\b|\bnfp\b/.test(nameLc)) score += 22;
  if (/\bcpi\b|\bpce\b/.test(nameLc)) score += 20;
  if (/\bunemployment rate\b/.test(nameLc)) score += 18;
  if (/\baverage hourly earnings\b|\bwages?\b/.test(nameLc)) score += 16;
  if (/\bfomc\b|\bfed rate\b|interest rate decision|rate decision/.test(nameLc)) score += 18;
  if (/\bgdp\b/.test(nameLc)) score += 16;
  if (/\bretail sales\b/.test(nameLc)) score += 14;
  if (/\bism\b.*\bpmi\b|\bpmi\b/.test(nameLc)) score += 12;
  if (/\bjobless claims\b|\binitial jobless claims\b/.test(nameLc)) score += 10;
  if (/\bconsumer confidence\b|\bsentiment\b|\bumich\b/.test(nameLc)) score += 8;
  if (/\bhome sales\b|\bhousing starts\b|\bbuilding permits\b/.test(nameLc)) score += 8;
  if (/\bcrude oil stocks\b|\beia natural gas stocks\b/.test(nameLc)) score += 4;
  return score;
}

function _batchAnchorSupportingPenalty_(nameLc, genre) {
  if (!nameLc) return 0;
  var score = 0;
  if (/\b4-week\b|\b4 week\b|four-week average/.test(nameLc)) score -= 14;
  if (/\baverage weekly hours\b/.test(nameLc)) score -= 8;
  if (/\bimports?\b|\bexports?\b/.test(nameLc)) score -= 8;
  if (/\brefinery\b|\bcushing\b|\bdistillate\b|\bgasoline\b|\bheating oil\b/.test(nameLc)) score -= 10;
  if (/\bauction\b|\bbill auction\b|\bnote auction\b|\bbond auction\b/.test(nameLc)) score -= 14;
  if (/\bspeech\b|\bstatement\b|\bminutes\b|\bhearing\b|\btestimony\b/.test(nameLc)) score -= 12;
  if (/\bprices\b|\bnew orders\b|\bbusiness activity\b/.test(nameLc) && /manufactur|ism|pmi/.test(nameLc)) score -= 6;
  if (/\bemployment\b/.test(nameLc) && /ism|pmi/.test(nameLc)) score -= 5;
  if (/\bprivate\b/.test(nameLc) && /\bpayroll/.test(nameLc)) score -= 3;
  if (String(genre || '').toLowerCase() === 'batch') score -= 4;
  return score;
}

function _maxImportance_(vals) {
  var rank = { low:1, medium:2, high:3, critical:4 };
  var best = 'medium';
  var bestRank = rank[best];
  (vals || []).forEach(function(v){
    var key = String(v || '').toLowerCase();
    var r = rank[key];
    if (r && r > bestRank) {
      best = key;
      bestRank = r;
    }
  });
  return best;
}

function _snapshotPredictionShape_(out) {
  return {
    qualitative_result: out.qualitative_result || '',
    expected_move_dir: out.expected_move_dir || '',
    expected_move_pips_min: _roundPips_(out.expected_move_pips_min),
    expected_move_pips_max: _roundPips_(out.expected_move_pips_max),
    mr_pred_dir: out.mr_pred_dir || '',
    mr_pred_net_pips: _roundPips_(out.mr_pred_net_pips),
    mr_pred_strength: out.mr_pred_strength || '',
    mr_pred_sustain_min: _roundPips_(out.mr_pred_sustain_min)
  };
}

function _annotatePredictionNormalization_(out, before) {
  if (!before) return out;
  var parts = [];
  if ((before.mr_pred_dir || '') !== (out.mr_pred_dir || '')) {
    parts.push('dir ' + (before.mr_pred_dir || 'blank') + ' -> ' + (out.mr_pred_dir || 'blank'));
  }
  if (_roundPips_(before.mr_pred_net_pips) !== _roundPips_(out.mr_pred_net_pips)) {
    parts.push('net_pips ' + _roundPips_(before.mr_pred_net_pips) + ' -> ' + _roundPips_(out.mr_pred_net_pips));
  }
  if ((before.mr_pred_strength || '') !== (out.mr_pred_strength || '')) {
    parts.push('strength ' + (before.mr_pred_strength || 'blank') + ' -> ' + (out.mr_pred_strength || 'blank'));
  }
  if ((before.qualitative_result || '') !== (out.qualitative_result || '')) {
    parts.push('qual ' + (before.qualitative_result || 'blank') + ' -> ' + (out.qualitative_result || 'blank'));
  }
  if (_roundPips_(before.expected_move_pips_min) !== _roundPips_(out.expected_move_pips_min) ||
      _roundPips_(before.expected_move_pips_max) !== _roundPips_(out.expected_move_pips_max)) {
    parts.push(
      'range ' + _roundPips_(before.expected_move_pips_min) + '-' + _roundPips_(before.expected_move_pips_max) +
      ' -> ' + _roundPips_(out.expected_move_pips_min) + '-' + _roundPips_(out.expected_move_pips_max)
    );
  }
  if ((before.expected_move_dir || '') !== (out.expected_move_dir || '')) {
    parts.push('expected_dir ' + (before.expected_move_dir || 'blank') + ' -> ' + (out.expected_move_dir || 'blank'));
  }
  if (_roundPips_(before.mr_pred_sustain_min) !== _roundPips_(out.mr_pred_sustain_min)) {
    parts.push('sustain ' + _roundPips_(before.mr_pred_sustain_min) + ' -> ' + _roundPips_(out.mr_pred_sustain_min));
  }

  if (!parts.length) return out;

  var note = 'Normalized for consistency: ' + parts.join('; ') + '.';
  if (!out.rationale_short) {
    out.rationale_short = 'Normalized prediction output.';
  }
  if (out.rationale) {
    if (out.rationale.indexOf(note) === -1) out.rationale += ' ' + note;
  } else {
    out.rationale = note;
  }
  if (out.raw_output) {
    var rawNote = ' normalization_note=' + _collapseToSingleLine_(note);
    if (out.raw_output.indexOf(rawNote.trim()) === -1) out.raw_output += rawNote;
  } else {
    out.raw_output = 'normalization_note=' + _collapseToSingleLine_(note);
  }
  return out;
}

function _formatPredictionRawOutputCsv_(parsed, rawOutput) {
  var obj = (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) ? parsed : null;
  if (obj) {
    var orderedKeys = [
      'object','event_id','type','ai_forecast_value','qualitative_result',
      'mr_window_min','mr_pred_dir','mr_pred_net_pips','mr_pred_strength',
      'mr_pred_sustain_min',
      'expected_move_dir','expected_move_pips_min','expected_move_pips_max',
      'expected_holding_minutes','rationale_short','rationale'
    ];
    var keys = orderedKeys.filter(function(k){ return obj[k] !== undefined; });
    Object.keys(obj).forEach(function(k){
      if (keys.indexOf(k) === -1) keys.push(k);
    });
    return keys.map(function(k){
      return _csvEscape_(obj[k]);
    }).join(',');
  }
  return _collapseToSingleLine_(rawOutput);
}

function _csvEscape_(val) {
  if (val === null || val === undefined) return '';
  var s = _collapseToSingleLine_(val);
  if (/[",\n]/.test(s)) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function _collapseToSingleLine_(val) {
  return String(val == null ? '' : val)
    .replace(/\r\n/g, ' ')
    .replace(/[\r\n]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function _inferQualFromConsensus_(ev, parsed) {
  if (typeof ev.consensus_value==='number' && typeof ev.prev_revision==='number') {
    var delta = ev.consensus_value - ev.prev_revision;
    if (Math.abs(delta) < 1e-9) return 'inline';
    return (delta>0) ? 'stronger' : 'weaker';
  }
  return 'inline';
}
function _dirFromQual_(qual) {
  if (qual==='stronger') return 'up';
  if (qual==='weaker')  return 'down';
  return 'flat';
}

function _getPredictionMrWindowMin_() {
  var cfg = _readConfigMap_('Config');
  var n = Number(cfg && cfg['MR_HORIZON_MIN']);
  if (!isFinite(n)) n = 5;
  n = Math.floor(n);
  if (n < 1) n = 1;
  if (n > 15) n = 15;
  return n;
}

function _midpointPips_(minPips, maxPips) {
  if (typeof minPips === 'number' && typeof maxPips === 'number') {
    return Math.round(((minPips + maxPips) / 2) * 100) / 100;
  }
  if (typeof maxPips === 'number') return maxPips;
  if (typeof minPips === 'number') return minPips;
  return null;
}

function _mrStrengthFromPips_(pips) {
  var n = Math.abs(Number(pips));
  if (!isFinite(n)) return '';
  if (n < 5) return 'weak';
  if (n < 15) return 'medium';
  return 'strong';
}

/** =========================
 *  Predictions sheet schema
 *  ========================= */
function _ensurePredHeaders_(sheet) {
  var required = [
    'object','event_id','batch_id','type',
    'indicator_name','country','release_ts','source_cal','genre','importance','fx_pair',
    'ai_name','ai_version','ai_model','model_version',
    'run_id','prediction_id','created_ts','schema_version','status','error_message',
    'consensus_value','prev_revision','ai_forecast_value','released_value',
    'forecast_error_abs','forecast_error_pct','forecast_dir_ok',
    'qualitative_result','qualitative_only',
    'expected_move_dir','expected_move_pips_min','expected_move_pips_max','expected_holding_minutes',
    'mr_window_min','mr_pred_dir','mr_pred_net_pips','mr_pred_strength','mr_pred_sustain_min',
    'mr_real_dir','mr_dir_ok','mr_real_strength','mr_strength_ok',
    'mr_real_sustain_min','mr_sustain_error_min','mr_sustain_grade','mr_sustain_ok',
    'mr_real_max_up_pips','mr_real_max_down_pips',
    'mr_final_provider','mr_compare_status','mr_compare_dir_agree','mr_compare_anchor_delta_min',
    'mr_compare_pips_delta','mr_compare_confidence','mr_compare_note',
    'eval_ts','eval_interval','start_ts','end_ts','start_price','end_price',
    'realized_pips','dir_ok','band_ok','overall_ok','eval_note',
    'rationale_short','rationale','raw_output',
    'prompt_tokens','completion_tokens','latency_ms',
    'batch_anchor_mode','batch_anchor_confidence','batch_anchor_event_id','batch_anchor_indicator_name',
    'batch_anchor_score','batch_anchor_margin','batch_anchor_runner_up_event_id',
    'batch_anchor_runner_up_indicator_name','batch_anchor_reason',
    'cache_creation_input_tokens','cache_read_input_tokens',
    'pre_signal_mode','pre_risk_level','pre_volatility_level','watch_member_event_ids',
    'watch_member_indicator_names','scenario_up_case','scenario_down_case',
    'scenario_flat_case','scenario_confidence','scenario_plan_json'
  ];
  var headers = getHeaderNames(sheet);
  var lower = headers.map(function(h){return String(h).toLowerCase();});
  var toAdd = [];
  required.forEach(function(k){ if (lower.indexOf(k.toLowerCase())<0) toAdd.push(k); });
  if (toAdd.length>0) sheet.getRange(1, headers.length+1, 1, toAdd.length).setValues([toAdd]);
  return getHeaderNames(sheet);
}
function _getPredHeaderIndex_(headers) { var idx={}; headers.forEach(function(h,i){ idx[String(h).toLowerCase()] = i; }); return idx; }

function _sortPredictionsSheet_(sheet) {
  if (!sheet || CFG.DRY_RUN_PREDICT) return;
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow < 3 || lastCol < 1) return;

  var headers = getHeaderNames(sheet);
  var idx = _getPredHeaderIndex_(headers);
  var eventCol = idx['event_id'];
  var aiNameCol = idx['ai_name'];
  var releaseTsCol = idx['release_ts'];
  if (eventCol == null || aiNameCol == null || releaseTsCol == null) return;

  var range = sheet.getRange(2, 1, lastRow - 1, lastCol);
  var rows = range.getValues();
  rows.sort(function(a, b) {
    var at = _predictionSortTimestampMs_(a[releaseTsCol]);
    var bt = _predictionSortTimestampMs_(b[releaseTsCol]);
    if (at !== bt) return at - bt;

    var ae = String(a[eventCol] || '');
    var be = String(b[eventCol] || '');
    if (ae < be) return -1;
    if (ae > be) return 1;

    var aa = String(a[aiNameCol] || '');
    var ba = String(b[aiNameCol] || '');
    if (aa < ba) return -1;
    if (aa > ba) return 1;
    return 0;
  });
  range.setValues(rows);
}

function _predictionSortTimestampMs_(value) {
  if (value instanceof Date && isFinite(value.getTime())) return value.getTime();
  var raw = String(value || '').trim();
  if (!raw) return Number.POSITIVE_INFINITY;
  var parsed = Date.parse(raw);
  return isFinite(parsed) ? parsed : Number.POSITIVE_INFINITY;
}

function _buildPredictionRow_(ev, norm, runId) {
  var createdTs = new Date().toISOString();
  var predictionId = _uuidFromString_(ev.event_id + '|' + norm.ai_name);
  var mrNetPips = (typeof norm.mr_pred_net_pips === 'number') ? norm.mr_pred_net_pips : _midpointPips_(norm.expected_move_pips_min, norm.expected_move_pips_max);
  var mrWindowMin = (typeof norm.mr_window_min === 'number') ? norm.mr_window_min : _getPredictionMrWindowMin_();
  var mrSustainMin = (typeof norm.mr_pred_sustain_min === 'number') ? norm.mr_pred_sustain_min :
    ((typeof norm.expected_holding_minutes === 'number') ? norm.expected_holding_minutes : '');

  return {
    object: 'ai_prediction',
    run_id: runId,
    prediction_id: predictionId,
    schema_version: CFG.SCHEMA_VERSION,
    created_ts: createdTs,

    event_id: ev.event_id,
    batch_id: ev.batch_id || '',
    type: ev.type,

    ai_name: norm.ai_name,
    ai_version: norm.ai_version,
    ai_model: norm.ai_model,
    model_version: norm.ai_version,

    indicator_name: ev.indicator_name || '',
    country: ev.country || '',
    release_ts: ev.release_ts || '',
    consensus_value: (typeof ev.consensus_value==='number') ? ev.consensus_value : '',
    prev_revision: (typeof ev.prev_revision==='number') ? ev.prev_revision : '',
    source_cal: ev.source_cal || '',
    genre: ev.genre || _inferGenreFromName_(ev.indicator_name||''),
    importance:      (ev.importance !== null && ev.importance !== undefined && ev.importance !== '') ? ev.importance : '',
    fx_pair: ev.fx_pair || CFG.DEFAULT_FX,

    ai_forecast_value: (typeof norm.ai_forecast_value==='number') ? norm.ai_forecast_value : '',
    qualitative_result: norm.qualitative_result || '',
    expected_move_dir: norm.expected_move_dir || '',
    expected_move_pips_min: (typeof norm.expected_move_pips_min==='number') ? norm.expected_move_pips_min : '',
    expected_move_pips_max: (typeof norm.expected_move_pips_max==='number') ? norm.expected_move_pips_max : '',
    expected_holding_minutes: (typeof norm.expected_holding_minutes==='number') ? norm.expected_holding_minutes : '',
    mr_window_min: mrWindowMin,
    mr_pred_dir: norm.mr_pred_dir || norm.expected_move_dir || '',
    mr_pred_net_pips: (typeof mrNetPips === 'number') ? mrNetPips : '',
    mr_pred_strength: norm.mr_pred_strength || _mrStrengthFromPips_(mrNetPips),
    mr_pred_sustain_min: mrSustainMin,
    rationale_short: norm.rationale_short || '',
    rationale: norm.rationale || '',

    prompt_tokens: (norm.prompt_tokens!=null)? norm.prompt_tokens : '',
    completion_tokens: (norm.completion_tokens!=null)? norm.completion_tokens : '',
    cache_creation_input_tokens: (norm.cache_creation_input_tokens!=null)? norm.cache_creation_input_tokens : '',
    cache_read_input_tokens: (norm.cache_read_input_tokens!=null)? norm.cache_read_input_tokens : '',
    latency_ms: (norm.latency_ms!=null)? norm.latency_ms : '',
    raw_output: norm.raw_output || '',
    batch_anchor_mode: ev && ev.type === 'batch' ? (ev.batch_anchor_mode || '') : '',
    batch_anchor_confidence: ev && ev.type === 'batch' ? (ev.batch_anchor_confidence || '') : '',
    batch_anchor_event_id: ev && ev.type === 'batch' && ev.batch_anchor ? (ev.batch_anchor.event_id || '') : '',
    batch_anchor_indicator_name: ev && ev.type === 'batch' && ev.batch_anchor ? (ev.batch_anchor.indicator_name || '') : '',
    batch_anchor_score: ev && ev.type === 'batch' ? (ev.anchor_score || 0) : '',
    batch_anchor_margin: ev && ev.type === 'batch' ? (ev.anchor_margin || 0) : '',
    batch_anchor_runner_up_event_id: ev && ev.type === 'batch' ? (ev.anchor_runner_up_event_id || '') : '',
    batch_anchor_runner_up_indicator_name: ev && ev.type === 'batch' ? (ev.anchor_runner_up_indicator_name || '') : '',
    batch_anchor_reason: ev && ev.type === 'batch' ? (ev.anchor_reason || '') : '',
    pre_signal_mode: norm.pre_signal_mode || '',
    pre_risk_level: norm.pre_risk_level || '',
    pre_volatility_level: norm.pre_volatility_level || '',
    watch_member_event_ids: norm.watch_member_event_ids || '',
    watch_member_indicator_names: norm.watch_member_indicator_names || '',
    scenario_up_case: norm.scenario_up_case || '',
    scenario_down_case: norm.scenario_down_case || '',
    scenario_flat_case: norm.scenario_flat_case || '',
    scenario_confidence: norm.scenario_confidence || '',
    scenario_plan_json: norm.scenario_plan_json || '',
    status: 'ok',
    error_message: '',

    qualitative_only: (norm.ai_forecast_value==null) ? 'true' : ''
  };
}

function _buildErrorPredictionRow_(ev, runId, err, providerMeta) {
  var createdTs = new Date().toISOString();
  var aiName = providerMeta && providerMeta.name ? providerMeta.name : 'runner';
  var aiVersion = providerMeta && providerMeta.model ? providerMeta.model : '';
  var predictionId = _uuidFromString_(((ev && ev.event_id) || 'unknown') + '|' + aiName);
  var preSignalPlan = ev && ev.pre_signal_plan ? ev.pre_signal_plan : _buildPreSignalPlan_(ev || {});
  return {
    object:'ai_prediction', run_id:runId, prediction_id:predictionId, schema_version:CFG.SCHEMA_VERSION, created_ts:createdTs,
    event_id: ev && ev.event_id || '', batch_id: ev && ev.batch_id || '', type: ev && ev.type || '',
    ai_name:aiName, ai_version:aiVersion, ai_model:aiVersion, model_version:aiVersion,
    indicator_name: ev && ev.indicator_name || '',
    country: ev && ev.country || '',
    release_ts: ev && ev.release_ts || '',
    consensus_value: ev && typeof ev.consensus_value==='number' ? ev.consensus_value : '',
    prev_revision:   ev && typeof ev.prev_revision==='number'   ? ev.prev_revision   : '',
    source_cal: ev && ev.source_cal || '', genre: ev && (ev.genre || _inferGenreFromName_(ev.indicator_name||'')) || '',
    importance: ev && ev.importance || '',
    fx_pair: ev && (ev.fx_pair || CFG.DEFAULT_FX) || CFG.DEFAULT_FX,
    ai_forecast_value:'', qualitative_result:'', expected_move_dir:'',
    expected_move_pips_min:'', expected_move_pips_max:'', expected_holding_minutes:'',
    mr_window_min: '',
    mr_pred_dir: '',
    mr_pred_net_pips: '',
    mr_pred_strength: '',
    mr_pred_sustain_min: '',
    rationale_short:'', rationale:'',
    prompt_tokens:'', completion_tokens:'', cache_creation_input_tokens:'', cache_read_input_tokens:'', latency_ms:'', raw_output:'',
    batch_anchor_mode: ev && ev.type === 'batch' ? (ev.batch_anchor_mode || '') : '',
    batch_anchor_confidence: ev && ev.type === 'batch' ? (ev.batch_anchor_confidence || '') : '',
    batch_anchor_event_id: ev && ev.type === 'batch' && ev.batch_anchor ? (ev.batch_anchor.event_id || '') : '',
    batch_anchor_indicator_name: ev && ev.type === 'batch' && ev.batch_anchor ? (ev.batch_anchor.indicator_name || '') : '',
    batch_anchor_score: ev && ev.type === 'batch' ? (ev.anchor_score || 0) : '',
    batch_anchor_margin: ev && ev.type === 'batch' ? (ev.anchor_margin || 0) : '',
    batch_anchor_runner_up_event_id: ev && ev.type === 'batch' ? (ev.anchor_runner_up_event_id || '') : '',
    batch_anchor_runner_up_indicator_name: ev && ev.type === 'batch' ? (ev.anchor_runner_up_indicator_name || '') : '',
    batch_anchor_reason: ev && ev.type === 'batch' ? (ev.anchor_reason || '') : '',
    pre_signal_mode: preSignalPlan.mode || '',
    pre_risk_level: preSignalPlan.risk_level || '',
    pre_volatility_level: preSignalPlan.volatility_level || '',
    watch_member_event_ids: preSignalPlan.watch_member_event_ids || '',
    watch_member_indicator_names: preSignalPlan.watch_member_indicator_names || '',
    scenario_up_case: preSignalPlan.up_case || '',
    scenario_down_case: preSignalPlan.down_case || '',
    scenario_flat_case: preSignalPlan.flat_case || '',
    scenario_confidence: preSignalPlan.confidence || '',
    scenario_plan_json: preSignalPlan.plan_json || '',
    status: _statusFromErr_(err), error_message: String(err),
    qualitative_only:''
  };
}

function _upsertPredictions_(sheet, rowObj, idxMap) {
  var headers = getHeaderNames(sheet);
  var idx = idxMap || _getPredHeaderIndex_(headers);

  var eventCol = idx['event_id']; var aiNameCol= idx['ai_name'];
  if (eventCol == null || aiNameCol == null) throw new Error('Predictions headers missing (event_id/ai_name)');

  var last = sheet.getLastRow();
  if (last < 2) {
    var vals = _rowObjToRow_(rowObj, headers);
    if (!CFG.DRY_RUN_PREDICT) sheet.getRange(2,1,1,headers.length).setValues([vals]);
    return 'created';
  }

  var data = sheet.getRange(2,1,last-1,headers.length).getValues();
  var foundRow = -1;
  for (var r=0; r<data.length; r++) {
    if (String(data[r][eventCol]).trim() === String(rowObj.event_id).trim() &&
        String(data[r][aiNameCol]).trim() === String(rowObj.ai_name).trim()) {
      foundRow = r+2; break;
    }
  }

  if (foundRow > -1) {
    var existingRow = data[foundRow - 2];
    var valsToWrite = _mergeRowObjOverExisting_(rowObj, headers, existingRow);
    if (!CFG.DRY_RUN_PREDICT) sheet.getRange(foundRow, 1, 1, headers.length).setValues([valsToWrite]);
    return 'updated';
  } else {
    var valsToWrite = _rowObjToRow_(rowObj, headers);
    if (!CFG.DRY_RUN_PREDICT) sheet.appendRow(valsToWrite);
    return 'created';
  }
}

function _rowObjToRow_(obj, headers) {
  var arr = [];
  for (var i=0; i<headers.length; i++) {
    var key = String(headers[i]).toLowerCase();
    var v = (obj.hasOwnProperty(key) ? obj[key] : (obj[headers[i]]));
    if (v === undefined) v = '';
    arr.push(v);
  }
  return arr;
}

function _mergeRowObjOverExisting_(obj, headers, existingRow) {
  var arr = [];
  for (var i = 0; i < headers.length; i++) {
    var key = String(headers[i]).toLowerCase();
    var hasValue = obj.hasOwnProperty(key) || obj.hasOwnProperty(headers[i]);
    if (hasValue) {
      var v = obj.hasOwnProperty(key) ? obj[key] : obj[headers[i]];
      arr.push(v === undefined ? '' : v);
    } else {
      arr.push(existingRow && i < existingRow.length ? existingRow[i] : '');
    }
  }
  return arr;
}


/** =========================
 *  Qualitative detection
 *  ========================= */
function _isQualitativeOnly_(ev) {
  // 1) Explicit overrides from Event sheet take priority if present
  if (ev.hasOwnProperty('qualitative_only') && ev.qualitative_only !== '' && ev.qualitative_only !== null && ev.qualitative_only !== undefined) {
    var ov = String(ev.qualitative_only).trim().toLowerCase();
    if (ov === 'true' || ov === '1' || ov === 'yes' || ov === 'y') return true;
    if (ov === 'false' || ov === '0' || ov === 'no'  || ov === 'n') return false;
  }

  // 2) Curated genre list (exact match, case-insensitive)
  var g = (ev.genre || '').toString().trim().toLowerCase();
  var QUAL_GENRES = ['speech','press_conference','statement','minutes','hearing','testimony'];
  if (QUAL_GENRES.indexOf(g) !== -1) return true;

  // 3) Word-boundary indicator patterns (avoid substring accidents)
  var name = (ev.indicator_name || '').toString().toLowerCase();
  var rx = /\b(speech|press\s*conference|statement|minutes|hearing|testimony)\b/i;
  if (rx.test(name)) return true;

  // 4) Auctions: qualitative only if there is no numeric context (no consensus and no prev)
  //    Prevents over-suppression when an upstream feed happens to include numeric expectations.
  if (/\bauction(s)?\b/i.test(name) || g === 'auction') {
    var hasConsensus = !(ev.consensus_value === '' || ev.consensus_value === null || ev.consensus_value === undefined);
    var hasPrev      = !(ev.prev_revision   === '' || ev.prev_revision   === null || ev.prev_revision   === undefined);
    if (!hasConsensus && !hasPrev) return true; // no numeric context → treat as qualitative
    // otherwise allow numeric forecasts
  }

  // 5) GDPNow / nowcasts: TREAT AS NUMERIC (do NOT force qualitative)
  //    We explicitly allow numeric forecasts for GDPNow/Nowcast style indicators.
  //    Also, many feeds tag GDPNow under "Growth"; keep numeric there too.
  if (/\bgdp\s*now\b/i.test(name) || g === 'gdpnow' || g === 'nowcast' || g === 'growth') {
    return false; // explicitly non-qualitative
  }

  // Default: numeric event
  return false;
}




/** =========================
 *  Utilities
 *  ========================= */

function _normalizeProviderName_(name) {
  var s = String(name || '').trim();
  if (/^claude$/i.test(s))  return 'Anthropic';
  if (/^openai$/i.test(s))  return 'OpenAI';
  if (/^gemini$/i.test(s))  return 'Gemini';
  return s;
}


function _numOrNull_(v) {
  if (v === null || v === '' || v === undefined) return null;
  if (typeof v === 'number') return isFinite(v) ? v : null;

  var s = String(v).trim();
  if (s === '') return null;

  // Accounting negative: "(0.3)" -> "-0.3"
  // Do this before other stripping so inner content gets normalized too.
  if (/^\(.*\)$/.test(s)) {
    s = '-' + s.slice(1, -1).trim();
  }

  // normalize unicode minus, commas, leading ~ / ≈, leading plus
  s = s
    .replace(/\u2212/g, '-')            // unicode minus → ASCII
    .replace(/,/g, '')                  // remove thousand separators
    .replace(/^[~≈]\s*/, '')            // strip leading ~ or ≈
    .replace(/^\+/, '');                // drop leading '+'

  // strip common currency prefixes (and the space after), conservative
  s = s.replace(/^\s*(?:[$€£¥]|usd|eur|jpy|gbp)\s*/i, '');
  // strip trailing currency symbols, conservative
  s = s.replace(/\s*(?:[$€£¥])\s*$/i, '');

  // percentages: keep 0.3% -> 0.3  (if you prefer fraction, divide by 100 here)
  if (/%$/.test(s)) {
    var tPct = s.slice(0, -1).trim();
    var nPct = Number(tPct);
    return isFinite(nPct) ? nPct : null;
  }

  // per-mille: "0.3‰" -> 0.3  (keeps same convention as % block above)
  if (/‰$/.test(s)) {
    var tPermille = s.slice(0, -1).trim();
    var nPermille = Number(tPermille);
    return isFinite(nPermille) ? nPermille : null;
  }

  // k/m/b/bn suffixes (allow optional space): 210k -> 210000 ; 1.2 m -> 1200000 ; 0.8bn -> 800000000
  var m = s.match(/^([+-]?\d+(?:\.\d+)?)\s*(k|m|b|bn)$/i);
  if (m) {
    var base = Number(m[1]); if (!isFinite(base)) return null;
    var suf = m[2].toLowerCase();
    var mul = (suf === 'k') ? 1e3 : (suf === 'm') ? 1e6 : 1e9;
    return base * mul;
  }

  // plain numbers (incl. scientific)
  var n2 = Number(s);
  return isFinite(n2) ? n2 : null;
}

function _stripCodeFences_(s) {
  if (!s) return s;
  return String(s)
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/, '')
    .trim();
}

function _extractFirstJsonObject_(s) {
  if (!s) return null;
  var txt = String(s);
  var start = txt.indexOf('{');
  if (start < 0) return null;
  var depth = 0;
  for (var i = start; i < txt.length; i++) {
    var ch = txt[i];
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return txt.slice(start, i + 1);
    }
  }
  return null;
}


function _oneOf_(val, arr) { return arr.indexOf(val)>=0 ? val : null; }
function _cell(row, i) { return (i!=null && i<row.length) ? row[i] : ''; }

function _cfgNumber_(val, fallback) {
  // Accept numbers, numeric strings (with commas / %), or blank.
  if (val === null || val === undefined || val === '') return fallback;
  if (typeof val === 'number' && isFinite(val)) return val;
  var s = String(val).trim().replace(/,/g, '');
  if (s.endsWith('%')) s = s.slice(0, -1);
  var n = Number(s);
  return isFinite(n) ? n : fallback;
}

function _cfgInteger_(val, fallback) {
  var n = _cfgNumber_(val, fallback);
  return isFinite(n) ? Math.round(n) : fallback;
}

function _cfgBoolean_(val, fallback) {
  // Accept boolean, 1/0, yes/no, true/false (case-insensitive)
  if (typeof val === 'boolean') return val;
  if (val === null || val === undefined || val === '') return fallback;
  var s = String(val).trim().toLowerCase();
  if (s === 'true'  || s === '1' || s === 'yes' || s === 'y') return true;
  if (s === 'false' || s === '0' || s === 'no'  || s === 'n') return false;
  return fallback;
}


function _inferGenreFromName_(name) {
  var s = (name||'').toLowerCase();
  if (/cpi|pce|inflation/.test(s)) return 'Inflation';
  if (/payroll|employment|jobless|claims|unemployment|wage|earnings/.test(s)) return 'Labor';
  if (/gdp/.test(s)) return 'GDP';
  if (/housing|mortgage|home/.test(s)) return 'Housing';
  if (/manufactur|pm[iy]|ism/.test(s)) return 'Manufacturing';
  if (/sentiment|confidence|umich/.test(s)) return 'Sentiment';
  if (/fed balance|walcl/.test(s)) return 'FedBalance';
  return 'General';
}

function _statusFromErr_(e) {
  var s = String(e||'');
  if (/schema/i.test(s)) return 'schema_error';
  if (/quota/i.test(s) || /429/.test(s)) return 'quota_exceeded';
  if (/provider/i.test(s)) return 'provider_error';
  return 'provider_error';
}
function _schemaErr_(msg){ var er = new Error('schema_error: '+msg); er.name='schema_error'; return er; }
function _providerErr_(msg){ var er = new Error('provider_error: '+msg); er.name='provider_error'; return er; }
function _quotaErr_(msg){ var er = new Error('quota_exceeded: '+msg); er.name='quota_exceeded'; return er; }

function _withRetries_(fn, meta) {
  var attempts = 4, baseMs = 800;
  var lastErr;
  for (var i=0;i<attempts;i++){
    try { return fn(); }
    catch(e){
      lastErr = e;
      var status = _statusFromErr_(e);
      if (i === attempts-1) throw e;
      var jitter = Math.random()*0.4 + 0.8;
      var wait = Math.round(Math.pow(2,i) * baseMs * jitter);
      appendLog(status==='quota_exceeded' ? 'warn' : 'error', 'Retrying '+(i+1)+'/'+attempts, {
        provider: meta && meta.provider, status: status, wait_ms: wait, message: String(e)
      });
      Utilities.sleep(wait);
    }
  }
  throw (lastErr || new Error('retry_exhausted'));
}

function _getKey_(names) {
  var sp = PropertiesService.getScriptProperties();
  var up = PropertiesService.getUserProperties();
  var dp = PropertiesService.getDocumentProperties();
  for (var i=0; i<names.length; i++) {
    var n = names[i];
    var v = (sp.getProperty(n) || up.getProperty(n) || dp.getProperty(n) || '').trim();
    if (v) return v;
  }
  return '';
}

function _toIsoOrNull_(val) {
  if (val instanceof Date) return isNaN(val.getTime()) ? null : val.toISOString();
  if (val == null) return null;
  var s = String(val).trim();
  if (!s) return null;
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$/.test(s)) {
    var d0 = new Date(s); return isNaN(d0.getTime()) ? null : d0.toISOString();
  }
  var m = s.replace(/\u3000/g,' ').replace(/：/g,':').match(/^(\d{4})[-/](\d{2})[-/](\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (m) {
    var y=+m[1], mo=+m[2], d=+m[3], h=+m[4], mi=+m[5], se=m[6]?+m[6]:0;
    var ms = Date.UTC(y, mo-1, d, h, mi, se, 0);
    var d1 = new Date(ms); return isNaN(d1.getTime()) ? null : d1.toISOString();
  }
  var d2 = new Date(s);
  return isNaN(d2.getTime()) ? null : d2.toISOString();
}




/** =========================
 *  debug
 *  ========================= */

function debugQualFor_(eventId) {
  var sh = getSheet('Event');
  var H  = getHeaderNames(sh).map(function(h){ return String(h).toLowerCase(); });
  var idx = {}; H.forEach(function(h,i){ idx[h]=i; });
  var last = sh.getLastRow(); if (last < 2) throw new Error('No Event rows.');

  var data = sh.getRange(2,1,last-1,H.length).getValues();
  var ev = null;
  for (var r=0; r<data.length; r++) {
    var row = data[r];
    if (String(row[idx['event_id']]||'').trim() === String(eventId).trim()) {
      ev = {};
      H.forEach(function(h,i){ ev[h] = row[i]; });
      break;
    }
  }
  if (!ev) throw new Error('Event not found: '+eventId);

  var verdict = _isQualitativeOnly_(ev);
  var explain = {
    event_id: ev.event_id,
    genre: ev.genre,
    indicator_name: ev.indicator_name,
    consensus_value: ev.consensus_value,
    prev_revision: ev.prev_revision,
    explicit_flag: ev.qualitative_only,
    detector_says_qualitative: verdict
  };
  Logger.log(JSON.stringify(explain, null, 2));
  try { SpreadsheetApp.getUi().alert(JSON.stringify(explain, null, 2)); } catch(e) {}
  return explain;
}
