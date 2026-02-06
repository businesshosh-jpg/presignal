// prediction_runner.gs — v1.3.1 Robust Window + Config + Providers
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
  CLAUDE_MODEL: 'claude-3-5-sonnet-latest',
  DEFAULT_FX: 'USDJPY',
  WINDOW_MIN_BEFORE_MIN: 24*60,  // fallback minutes window (used if local override disabled/invalid)
  WINDOW_MAX_AFTER_MIN: 36*60,
  DRY_RUN_PREDICT: false,
  PIPS_BY_IMPORTANCE: { low:[3,10], medium:[8,25], high:[15,45], critical:[25,80] },
  SCHEMA_VERSION: '1.3',
  RULE_VERSION: '1.3'
};


function _ensureCfgDefaults_() {
  var defaults = {
    PROVIDERS: ['Gemini','OpenAI','Anthropic'],
    GEMINI_MODEL: 'gemini-2.5-flash-lite',
    OPENAI_MODEL: 'gpt-4o-mini',
    CLAUDE_MODEL: 'claude-3-5-sonnet-latest',
    DEFAULT_FX: 'USDJPY',
    WINDOW_MIN_BEFORE_MIN: 24*60,
    WINDOW_MAX_AFTER_MIN: 36*60,
    DRY_RUN_PREDICT: false,
    PIPS_BY_IMPORTANCE: { low:[3,10], medium:[8,25], high:[15,45], critical:[25,80] },
    SCHEMA_VERSION: '1.3',
    RULE_VERSION: '1.3'
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
// - DEFAULT_FX, DRY_RUN_PREDICT (bool), PIPS_*_MIN/MAX
// - Local window override (preferred):
//     WINDOW_ENABLED (true/false), WINDOW_FROM_LOCAL ("YYYY-MM-DD HH:mm" or Date),
//     WINDOW_TO_LOCAL, WINDOW_TZ (IANA, e.g., "Asia/Tokyo")
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

  // Local window override keys
  CFG.WINDOW_OVERRIDE = CFG.WINDOW_OVERRIDE || { enabled:false };
  if (map.WINDOW_ENABLED != null) CFG.WINDOW_OVERRIDE.enabled = _cfgBoolean_(map.WINDOW_ENABLED, false);
  if (map.WINDOW_FROM_LOCAL != null) CFG.WINDOW_OVERRIDE.fromLocal = map.WINDOW_FROM_LOCAL;
  if (map.WINDOW_TO_LOCAL   != null) CFG.WINDOW_OVERRIDE.toLocal   = map.WINDOW_TO_LOCAL;
  if (map.WINDOW_TZ         != null) CFG.WINDOW_OVERRIDE.tz        = String(map.WINDOW_TZ).trim();
}

// Convert local window (Config) into UTC ISO bounds; fallback to given bounds if invalid/disabled.
function _maybeOverrideWindowFromConfig_(bounds) {
  var o = CFG.WINDOW_OVERRIDE || {};
  if (!o.enabled) return bounds;

  var tz = o.tz || Session.getScriptTimeZone() || 'UTC';
  var fromIso = _localToUtcIso_(o.fromLocal, tz);
  var toIso   = _localToUtcIso_(o.toLocal,   tz);

  if (!fromIso || !toIso) return bounds; // fallback gracefully

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

/** =========================
 *  Core runner
 *  ========================= */
function runPredictionsCore_(opts) {
  _applyConfigOverridesFromSheet_(); // read Config sheet overrides
  _ensureCfgDefaults_();
  
  var runId = _uuidFromString_('predict:'+new Date().toISOString());
  var context = { module:'prediction_runner', rule_version: CFG.RULE_VERSION, run_id: runId };

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

  var selStats = { scanned:0, skipped_bad_ts:0, skipped_out_of_window:0, skipped_missing_id_type:0, selected:0 };
  var events = _selectEventsForWindow_(eventSheet, windowBounds, selStats);

  appendLog('info','Event selection summary', Object.assign({}, context, selStats));

  if (events.length === 0) {
    appendLog('info','No events found in window', Object.assign({}, context, windowBounds, { status:'no_events' }));
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
    return { status: 'validation_error', message: 'No providers enabled' };
  }

  // If no override, still protect against empty resolution
  if (!providerOverride && enabledProviders.length === 0) {
    appendLog('error', 'No providers enabled (no API keys found)', {
      module: 'prediction_runner',
      requested: CFG.PROVIDERS
    });
    return { status: 'validation_error', message: 'No providers enabled' };
  }

  appendLog('info', 'Providers resolved', {
    module: 'prediction_runner',
    requested: providerOverride || CFG.PROVIDERS,
    enabled: enabledProviders.map(function (p) { return p.name + '(' + p.model + ')'; })
  });



  var results = { inspected:0, created:0, updated:0, duplicates:0, errors:0 };
  var seenKey = {};

  events.forEach(function(ev){
    results.inspected++;

    var qualOnly = _isQualitativeOnly_(ev);
    var fxPair   = ev.fx_pair || CFG.DEFAULT_FX;
    var prompt   = _buildPredictionJsonPrompt_(ev, { qualOnly: qualOnly, fxPair: fxPair });

    enabledProviders.forEach(function(p){
      try {
        var t0 = Date.now();
        var r = p.fn(p, prompt);                 // call THIS provider only
        r.latency_ms = r.latency_ms || (Date.now() - t0);

        var norm = _normalizePrediction_(ev, r, { qualOnly: qualOnly, fxPair: fxPair });
        var row  = _buildPredictionRow_(ev, norm, runId);

        var up   = _upsertPredictions_(predSheet, row, predIdx);
        results[ up === 'updated' ? 'updated'
              : up === 'duplicate' ? 'duplicates'
              : 'created' ]++;

        if (ev.type === 'member' && ev.batch_id) {
          _ensureSyntheticBatchRow_(predSheet, ev, runId, predIdx);
        }

        appendLog('info','Prediction ok', Object.assign({}, context, {
          provider: norm.ai_name,
          model_name: norm.ai_version,
          event_id: ev.event_id,
          status: 'ok',
          duration_ms: r.latency_ms || null
        }));

      } catch (err) {
        results.errors++;
        try {
          var errRow = _buildErrorPredictionRow_(ev, runId, err);
          errRow.ai_name = p.name;
          errRow.model_version = p.model;
          _upsertPredictions_(predSheet, errRow, predIdx);
        } catch(inner) {}
        appendLog('error','Prediction error', Object.assign({}, context, {
          provider: p.name,
          model: p.model,
          event_id: ev.event_id,
          status: _statusFromErr_(err),
          message: String(err)
        }));
      }
    });
  });

  SpreadsheetApp.flush();
  var summary = Object.assign({ status:'ok' }, results, windowBounds, { providers: enabledProviders.map(function(p){return p.name;}) });
  appendLog('info','Prediction run summary', Object.assign({}, context, summary));
  return summary;
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
    var importance= _cell(row, idx['importance']);
    var indicator = _cell(row, idx['indicator_name']);

    if (!eventId || !type) { stats.skipped_missing_id_type++; continue; }

    var relIso = _toIsoOrNull_(releaseTs);
    if (!relIso) { stats.skipped_bad_ts++; continue; }

    var relMs = Date.parse(relIso);
    if (!(relMs >= ws && relMs <= we)) { stats.skipped_out_of_window++; continue; }

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

/** =========================
 *  Prompt & parsing
 *  ========================= */
function _buildPredictionJsonPrompt_(ev, opt) {
  var qualOnly = !!opt.qualOnly;
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
    policy: {
      qualitative_only: qualOnly,
      defaults: { pips_band_by_importance: CFG.PIPS_BY_IMPORTANCE }
    },
    required_output: {
      object: 'ai_prediction',
      event_id: ev.event_id,
      type: ev.type,
      ai_forecast_value: qualOnly ? null : '(number or null)',
      qualitative_result: '(stronger|weaker|inline)',
      expected_move_dir: '(up|down|flat)',
      expected_move_pips_min: '(number)',
      expected_move_pips_max: '(number)',
      expected_holding_minutes: '(number)',
      rationale_short: '(short string)',
      rationale: '(longer string)'
    }
  };
  var instruction =
    "Return ONLY strict JSON (no code fences). Keys required: " +
    "object,event_id,type,ai_forecast_value,qualitative_result,expected_move_dir," +
    "expected_move_pips_min,expected_move_pips_max,expected_holding_minutes,rationale_short,rationale. " +
    "ai_forecast_value must be a PLAIN number with no units or symbols (no %, k, m, bn).";
  return {
    system: "You are a macroeconomic forecasting model. Output must be strict JSON and safe for parsing.",
    user: JSON.stringify(payload),
    instruction: instruction
  };
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
      completion_tokens: usage.completion_tokens || null
    };
  }, { provider:'OpenAI' });
}

// --- Gemini ---
function _callGemini_(prov, prompt) {
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/'+encodeURIComponent(prov.model)+':generateContent?key='+encodeURIComponent(prov.key);
  var body = {
    contents: [{ role:'user', parts:[{ text: prompt.system+"\n\n"+prompt.user+"\n\n"+prompt.instruction }] }],
    generationConfig: { response_mime_type: 'application/json' }
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
      completion_tokens: usage.candidatesTokenCount || null
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
  var body = {
    model: prov.model,
    max_tokens: 2048,
    system: prompt.system,
    messages: [ { role:'user', content: prompt.user+"\n\n"+prompt.instruction } ]
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
    var parsed = _strictParsePredictionJson_(c);
    var usage = j.usage || {};
    return {
      ai_name: 'Anthropic',
      ai_version: prov.model,
      ai_model: prov.model,
      parsed: parsed,
      raw_output: c,
      prompt_tokens: usage.input_tokens || null,
      completion_tokens: usage.output_tokens || null
    };
  }, { provider:'Anthropic' });
}

/** =========================
 *  Normalization
 *  ========================= */
function _normalizePrediction_(ev, providerResp, opt) {
  var parsed = providerResp.parsed || {};
    parsed.event_id = ev.event_id;
    parsed.type     = ev.type;
  var out = {
    ai_name: providerResp.ai_name,
    ai_version: providerResp.ai_version,
    ai_model: providerResp.ai_model || providerResp.ai_version,
    raw_output: providerResp.raw_output,
    prompt_tokens: providerResp.prompt_tokens || null,
    completion_tokens: providerResp.completion_tokens || null,
    latency_ms: providerResp.latency_ms || null,

    object: 'ai_prediction',
    event_id: ev.event_id,
    batch_id: ev.batch_id || null,
    type: ev.type,
    ai_forecast_value: (opt.qualOnly ? null : _numOrNull_(parsed.ai_forecast_value)),
    qualitative_result: _oneOf_((parsed.qualitative_result||'').toLowerCase(), ['stronger','weaker','inline']) || _inferQualFromConsensus_(ev, parsed),
    expected_move_dir: _oneOf_((parsed.expected_move_dir||'').toLowerCase(), ['up','down','flat']) || _dirFromQual_((parsed.qualitative_result||'').toLowerCase()),
    expected_move_pips_min: _numOrNull_(parsed.expected_move_pips_min),
    expected_move_pips_max: _numOrNull_(parsed.expected_move_pips_max),
    expected_holding_minutes: _numOrNull_(parsed.expected_holding_minutes),
    rationale_short: parsed.rationale_short || '',
    rationale: parsed.rationale || ''
  };

  var imp = (ev.importance || 'medium').toLowerCase();
  var band = CFG.PIPS_BY_IMPORTANCE[imp] || CFG.PIPS_BY_IMPORTANCE.medium;
  if (!(out.expected_move_pips_min>=0)) out.expected_move_pips_min = band[0];
  if (!(out.expected_move_pips_max>=out.expected_move_pips_min)) out.expected_move_pips_max = band[1];
  if (!out.expected_move_dir) out.expected_move_dir = (out.expected_move_pips_max<=1) ? 'flat' : 'up';
  if (!out.expected_holding_minutes) out.expected_holding_minutes = 60;
  return out;
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

/** =========================
 *  Predictions sheet schema
 *  ========================= */
function _ensurePredHeaders_(sheet) {
  var required = [
    'object','run_id','prediction_id','schema_version','created_ts',
    'event_id','batch_id','type',
    'ai_name','ai_version','ai_model','model_version',
    'consensus_value','prev_revision','source_cal','genre','importance','fx_pair',
    'ai_forecast_value','qualitative_result','expected_move_dir',
    'expected_move_pips_min','expected_move_pips_max','expected_holding_minutes',
    'rationale_short','rationale',
    'prompt_tokens','completion_tokens','latency_ms','raw_output','status','error_message',
    'qualitative_only'
  ];
  var headers = getHeaderNames(sheet);
  var lower = headers.map(function(h){return String(h).toLowerCase();});
  var toAdd = [];
  required.forEach(function(k){ if (lower.indexOf(k.toLowerCase())<0) toAdd.push(k); });
  if (toAdd.length>0) sheet.getRange(1, headers.length+1, 1, toAdd.length).setValues([toAdd]);
  return getHeaderNames(sheet);
}
function _getPredHeaderIndex_(headers) { var idx={}; headers.forEach(function(h,i){ idx[String(h).toLowerCase()] = i; }); return idx; }

function _buildPredictionRow_(ev, norm, runId) {
  var createdTs = new Date().toISOString();
  var predictionId = _uuidFromString_(ev.event_id + '|' + norm.ai_name);

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
    rationale_short: norm.rationale_short || '',
    rationale: norm.rationale || '',

    prompt_tokens: (norm.prompt_tokens!=null)? norm.prompt_tokens : '',
    completion_tokens: (norm.completion_tokens!=null)? norm.completion_tokens : '',
    latency_ms: (norm.latency_ms!=null)? norm.latency_ms : '',
    raw_output: norm.raw_output || '',
    status: 'ok',
    error_message: '',

    qualitative_only: (norm.ai_forecast_value==null) ? 'true' : ''
  };
}

function _buildErrorPredictionRow_(ev, runId, err) {
  var createdTs = new Date().toISOString();
  var predictionId = _uuidFromString_(((ev && ev.event_id) || 'unknown') + '|runner_error');
  return {
    object:'ai_prediction', run_id:runId, prediction_id:predictionId, schema_version:CFG.SCHEMA_VERSION, created_ts:createdTs,
    event_id: ev && ev.event_id || '', batch_id: ev && ev.batch_id || '', type: ev && ev.type || '',
    ai_name:'runner', ai_version:'', ai_model:'', model_version:'',
    consensus_value: ev && typeof ev.consensus_value==='number' ? ev.consensus_value : '',
    prev_revision:   ev && typeof ev.prev_revision==='number'   ? ev.prev_revision   : '',
    source_cal: ev && ev.source_cal || '', genre: ev && (ev.genre || _inferGenreFromName_(ev.indicator_name||'')) || '',
    fx_pair: ev && (ev.fx_pair || CFG.DEFAULT_FX) || CFG.DEFAULT_FX,
    ai_forecast_value:'', qualitative_result:'', expected_move_dir:'',
    expected_move_pips_min:'', expected_move_pips_max:'', expected_holding_minutes:'',
    rationale_short:'', rationale:'',
    prompt_tokens:'', completion_tokens:'', latency_ms:'', raw_output:'',
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

  var valsToWrite = _rowObjToRow_(rowObj, headers);
  if (foundRow > -1) {
    if (!CFG.DRY_RUN_PREDICT) sheet.getRange(foundRow, 1, 1, headers.length).setValues([valsToWrite]);
    return 'updated';
  } else {
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

/** =========================
 *  Synthetic batch summary
 *  ========================= */
function _ensureSyntheticBatchRow_(predSheet, ev, runId, idx) {
  var headers = getHeaderNames(predSheet);
  var i = idx || _getPredHeaderIndex_(headers);

  var eventCol = i['event_id'], typeCol=i['type'];
  var last = predSheet.getLastRow();
  var exists = false;
  if (last>=2) {
    var vals = predSheet.getRange(2,1,last-1,headers.length).getValues();
    for (var r=0; r<vals.length; r++) {
      if (String(vals[r][eventCol]) === String(ev.batch_id) && String(vals[r][typeCol]).toLowerCase()==='batch') { exists = true; break; }
    }
  }
  if (exists) return;

  var band = CFG.PIPS_BY_IMPORTANCE[(ev.importance||'medium').toLowerCase()] || CFG.PIPS_BY_IMPORTANCE.medium;

  var _ruleVer = String(CFG.RULE_VERSION || CFG.SCHEMA_VERSION || '1.0');

  var row = {
    object:'ai_prediction',
    run_id: runId,
    prediction_id: _uuidFromString_(ev.batch_id+'|BatchSynth'),
    schema_version: CFG.SCHEMA_VERSION,
    created_ts: new Date().toISOString(),

    event_id: ev.batch_id,
    batch_id: '',
    type: 'batch',

    ai_name: 'BatchSynth',
    ai_version: 'batch-synth-' + _ruleVer,   // e.g., "batch-synth-1.3"
    ai_model: 'BatchAggregator',             // instead of "batch_synth"
    model_version: _ruleVer,


    consensus_value: '',
    prev_revision: '',
    source_cal: ev.source_cal || '',
    genre: ev.genre || _inferGenreFromName_(ev.indicator_name||''),
    importance: (ev.importance != null && ev.importance !== '') ? String(ev.importance) : '',
    fx_pair: ev.fx_pair || CFG.DEFAULT_FX,

    ai_forecast_value: '',
    qualitative_result: 'inline',
    expected_move_dir: 'flat',
    expected_move_pips_min: band[0],
    expected_move_pips_max: band[1],
    expected_holding_minutes: 60,
    rationale_short: 'Synthetic batch summary',
    rationale: 'Aggregated batch summary row (v1.3).',

    prompt_tokens: '',
    completion_tokens: '',
    latency_ms: '',
    raw_output: '',
    status: 'ok',
    error_message: '',

    qualitative_only: 'true'
  };

  var vals = _rowObjToRow_(row, headers);
  if (!CFG.DRY_RUN_PREDICT) predSheet.appendRow(vals);
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



