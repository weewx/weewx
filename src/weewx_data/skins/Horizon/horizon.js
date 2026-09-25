/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 */

/* horizon.js draws the charts of the history panel, switches the time span of the
   charts and of the current conditions, converts units, runs the live update, and
   handles the menu, theme and back-to-top buttons. The charts are drawn from the
   archive files of the JSON generator (see "The JSON generator" in the
   Customization Guide). */

(function () {
  'use strict';

  var CFG = window.HORIZON || {};
  var DATA_DIR = CFG.dataDir || 'data';
  var STORE = 'weewx.horizon.';

  /* ------------------------------------------------------------- storage */

  /* remember() and recall() keep the reader's theme, units and time span in
     localStorage. If localStorage fails, the page uses the defaults.

     remember() and recall() catch every exception on purpose. localStorage throws
     in normal use: SecurityError when site data is blocked or the page has no
     origin (e.g., file://), QuotaExceededError when the quota is zero, as in some
     private modes, and TypeError when localStorage is missing. JavaScript cannot
     catch by type. A rethrown TypeError would stop horizon.js, and the page would
     lose its charts. */

  function remember(key, value) {
    try { localStorage.setItem(STORE + key, value); } catch (e) { /* see above */ }
  }

  function recall(key, fallback) {
    try {
      var v = localStorage.getItem(STORE + key);
      return v === null ? fallback : v;
    } catch (e) { return fallback; }
  }

  /* --------------------------------------------------------------- theme */

  function resolvedTheme() {
    var explicit = document.documentElement.getAttribute('data-theme');
    if (explicit) return explicit;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function themeColors() {
    var s = getComputedStyle(document.documentElement);
    return {
      grid: s.getPropertyValue('--chart-grid').trim() || '#e3eaf1',
      axis: s.getPropertyValue('--chart-axis').trim() || '#8397a7',
      night: s.getPropertyValue('--chart-night').trim() || '#eaeef3',
      ink: s.getPropertyValue('--ink').trim() || '#16222e',
      /* The tooltip takes its background and border from the stylesheet, so that
         the tooltip is not a white box in the dark theme. */
      surface: s.getPropertyValue('--surface').trim() || '#ffffff',
      border: s.getPropertyValue('--border').trim()
              || s.getPropertyValue('--chart-grid').trim() || '#e3eaf1',
      muted: s.getPropertyValue('--ink-muted').trim() || '#5c7183'
    };
  }

  /* ------------------------------------------------------------ page shell */

  /* The menu button opens the navigation over the page, as a menu, and closes it
     again. horizon.css shows the button only at 60rem and narrower, so this
     function does not check the width. */
  function setupNavToggle() {
    var button = document.getElementById('nav-toggle');
    var nav = document.getElementById('site-nav');
    if (!button || !nav) return;

    var isOpen = function () { return nav.dataset.open !== undefined; };
    var close = function () {
      delete nav.dataset.open;
      button.setAttribute('aria-expanded', 'false');
    };

    button.addEventListener('click', function () {
      if (isOpen()) {
        close();
      } else {
        nav.dataset.open = '';
        button.setAttribute('aria-expanded', 'true');
        /* horizon.css limits the menu's height by --menu-top (see .site-nav). */
        nav.style.setProperty('--menu-top', Math.round(nav.getBoundingClientRect().top) + 'px');
      }
    });

    /* A click outside the menu, or Escape, closes the menu. A click inside does
       not, so that the reader can choose a unit and then a language. */
    document.addEventListener('click', function (e) {
      if (isOpen() && !nav.contains(e.target) && !button.contains(e.target)) close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen()) {
        close();
        button.focus();
      }
    });

    /* The menu also closes when the focus moves to an element outside the menu and
       the button, e.g., with Tab past the last link, because the open menu would
       cover that element. A focusout with no element receiving the focus
       (relatedTarget null), as after a click on plain text, is left to the click
       handler. */
    var leaving = function (e) {
      var to = e.relatedTarget;
      if (isOpen() && to && !nav.contains(to) && !button.contains(to)) close();
    };
    nav.addEventListener('focusout', leaving);
    button.addEventListener('focusout', leaving);

    /* On the front page a time span link is a bare hash, so following the link
       loads no page, and the menu would stay open over the charts. A click on any
       link closes the menu and puts the focus back on the button, because the link
       that had the focus is hidden with the menu. */
    nav.addEventListener('click', function (e) {
      if (isOpen() && e.target.closest('a')) {
        close();
        button.focus();
      }
    });
  }

  function setupThemeToggle() {
    var button = document.getElementById('theme-toggle');
    if (!button) return;

    var saved = recall('theme', null);
    if (saved === 'dark' || saved === 'light') {
      document.documentElement.setAttribute('data-theme', saved);
    }
    syncLabel();

    button.addEventListener('click', function () {
      var next = resolvedTheme() === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      remember('theme', next);
      syncLabel();
      redrawAll();
    });

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      if (!document.documentElement.getAttribute('data-theme')) {
        syncLabel();
        redrawAll();
      }
    });

    function syncLabel() {
      var dark = resolvedTheme() === 'dark';
      button.setAttribute('aria-label',
        dark ? (CFG.text.toLight || 'Switch to light theme')
             : (CFG.text.toDark || 'Switch to dark theme'));
    }
  }

  /* Shows the back-to-top button of top.inc, by setting `data-show`, while the
     page is scrolled down. horizon.css hides the button until then, from the tab
     order too, so without JavaScript the button is neither seen nor reached. */
  function setupToTop() {
    var button = document.getElementById('to-top');
    if (!button) return;

    var shown = false;
    var queued = false;

    /* Scroll events fire more often than the browser paints, so check() runs at
       most once per animation frame. */
    function check() {
      queued = false;
      /* The button appears once the page is scrolled by more than one viewport
         height. A shorter way back up is as quick to scroll by hand. */
      var want = (window.pageYOffset || document.documentElement.scrollTop || 0)
                 > window.innerHeight;
      if (want === shown) return;
      shown = want;
      if (want) button.dataset.show = '';
      else delete button.dataset.show;
    }

    window.addEventListener('scroll', function () {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(check);
    }, { passive: true });
    window.addEventListener('resize', check);

    button.addEventListener('click', function () {
      var still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.scrollTo({ top: 0, behavior: still ? 'auto' : 'smooth' });
      /* At the top of the page the button hides itself, and the focus would fall to
         <body>. The focus goes to the page's heading instead, so that the keyboard
         and a screen reader continue from the top. */
      var heading = document.querySelector('.masthead h1');
      if (heading) {
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
      }
    });

    /* A page opened at an anchor, or with the back button, starts scrolled. */
    check();
  }

  /* ----------------------------------------------------------- formatting */

  var LOCALE = document.documentElement.lang || undefined;

  function fmtNumber(v, digits) {
    if (v === null || v === undefined || !isFinite(v)) return '–';
    return v.toLocaleString(LOCALE, {
      minimumFractionDigits: digits, maximumFractionDigits: digits
    });
  }

  /* Returns the number of decimals for a chart's axis labels, tooltip and data
     table, from the spread of its readings. */
  function digitsFor(series) {
    var span = 0;
    series.forEach(function (s) {
      var vals = s.values.filter(function (v) { return v !== null; });
      if (!vals.length) return;
      span = Math.max(span, Math.max.apply(null, vals) - Math.min.apply(null, vals));
    });
    if (span === 0) return 1;
    if (span < 1) return 2;
    if (span < 50) return 1;
    return 0;
  }

  function fmtTime(ts, period) {
    var d = new Date(ts * 1000);
    var opts = period === 'day'
      ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }
      : period === 'week'
        ? { weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }
        : { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' };
    return d.toLocaleString(LOCALE, opts);
  }

  /* Returns the label of one x axis tick. ECharts writes month names in English
     whatever the page's language. fmtTick writes the names of months and days in
     the page's language, and keeps the labels short enough not to overlap. */
  function fmtTick(ts, period, splits) {
    var d = new Date(ts * 1000);
    /* The form of the label depends on the seconds between ticks, not on the
       time span: on the Year chart of a station three weeks old, all ticks fall in
       one month, and every label would read "Aug". */
    var step = (splits && splits.length > 1) ? (splits[1] - splits[0]) : null;
    if (period === 'day') {
      return d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    }
    if (period === 'week') {
      return d.getHours() === 0
        ? d.toLocaleDateString(LOCALE, { weekday: 'short' })
        : d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    }
    /* Ticks less than a day apart get a clock time, as on the Month chart of a
       station three days old, where a date alone would repeat on every label. */
    if (step !== null && step < 86400) {
      return d.getHours() === 0 && d.getMinutes() === 0
        ? d.toLocaleDateString(LOCALE, { day: '2-digit', month: 'short' })
        : d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit',
                                         hourCycle: 'h23' });
    }
    if (period === 'month') {
      return d.toLocaleDateString(LOCALE, { day: '2-digit', month: '2-digit' });
    }
    if (step !== null && step < 25 * 86400) {
      return d.toLocaleDateString(LOCALE, { day: '2-digit', month: 'short' });
    }
    return d.toLocaleDateString(LOCALE, { month: 'short' });
  }

  /* ---------------------------------------------------------------- units */

  /* WeeWX writes the JSON files in the report unit system. data/index.json also
     carries a unit table, from which the browser converts any reading to the unit
     system the reader chose, without fetching anything. The unit table, in part:

       groups:  {"outTemp": "group_temperature", ...}
       systems: {"METRIC": {"group_temperature": "degree_C", ...}, ...}
       report:  {"group_temperature": "degree_F", ...}
       convert: {"degree_F": {"degree_C": [0.5556, -17.7778]}, ...}
       labels:  {"degree_C": "°C", ...}
       formats: {"degree_C": "%.1f", ...}

     A conversion multiplies by the first number of a pair in 'convert' and adds the
     second. */

  /* `unitChoices` holds the unit table from data/index.json. refreshCharts empties
     `manifest` on each new archive record, so that data/index.json is read again.
     `unitChoices` survives that, so the readings stay in the chosen unit system
     while data/index.json loads. The unit table changes only when the station's
     configuration changes. */
  var unitChoices = null;

  function unitTable() {
    return unitChoices;
  }

  /* Returns the unit in which a reading of `obsType` in `fromUnit` is shown, or null
     where the reading stays in `fromUnit`.

     Without a chosen unit system the target is the report unit system. A reading
     that WeeWX wrote is then already in the target unit. The forecast, however,
     arrives from Open-Meteo in degree_C and km_per_hour, and is converted to match
     the rest of the page. */
  function targetUnit(obsType, fromUnit) {
    var table = unitTable();
    var system = recall('units', '');
    if (!table || !fromUnit) return null;
    var group = table.groups && table.groups[obsType];
    var wanted = group && (system
      ? (table.systems && table.systems[system] && table.systems[system][group])
      : (table.report && table.report[group]));
    if (!wanted || wanted === fromUnit) return null;
    if (!table.convert || !table.convert[fromUnit]
        || !table.convert[fromUnit][wanted]) return null;
    return wanted;
  }

  /* Returns a copy of the plot data `meta` with its readings, y axis and unit label
     in the unit system the reader chose. `meta` itself stays in the unit it was
     written in. If `meta` were converted in place, the next unit change would
     convert its readings a second time. */
  function inChosenUnit(meta) {
    var table = unitTable();
    if (!table || !meta || !meta.series || !meta.series.length) return shallow(meta);

    var to = targetUnit(meta.series[0].obs_type, meta.unit);
    /* Return a copy even here: returning `meta` itself would make entry.meta and
       entry.raw one object, and updateChart would then write converted data into
       entry.raw. */
    if (!to) return shallow(meta);
    var steps = table.convert[meta.unit][to];
    var factor = steps[0], offset = steps[1];
    var apply = function (v) {
      return v === null || v === undefined ? null : v * factor + offset;
    };

    var out = shallow(meta);
    out.unit = to;
    out.unit_label = (table.labels && table.labels[to]) || '';

    /* The step of the y axis is a difference, so the step takes the factor but not
       the offset: a step of 5 degree_C is 9 degree_F, not 41. */
    if (meta.yscale) {
      out.yscale = [apply(meta.yscale[0]), apply(meta.yscale[1]),
                    meta.yscale[2] * Math.abs(factor)];
    }

    out.series = meta.series.map(function (s) {
      var copy = {};
      Object.keys(s).forEach(function (k) { copy[k] = s[k]; });
      copy.unit = to;
      copy.unit_label = out.unit_label;
      copy.values = s.values.map(apply);
      /* `min` and `max` are readings, so they take the offset as well. */
      ['min', 'max'].forEach(function (k) {
        if (s[k]) copy[k] = s[k].map(apply);
      });
      /* The wind vector components are lengths, so they take the factor alone. */
      ['vector_x', 'vector_y'].forEach(function (k) {
        if (s[k]) copy[k] = s[k].map(function (v) {
          return v === null ? null : v * factor;
        });
      });
      return copy;
    });
    return out;
  }

  /* Returns a copy of `obj` one level deep. The callers replace whole properties of
     the copy and change nothing inside one. */
  function shallow(obj) {
    if (!obj) return obj;
    var out = {};
    Object.keys(obj).forEach(function (k) { out[k] = obj[k]; });
    return out;
  }

  /* Returns the number of decimals the report writes for `unit`, from its format in
     the unit table: "%.1f" gives 1. Without decimalsFor, 63.9 degree_F converted to
     degree_C would be written as 17.72222222222222. */
  function decimalsFor(unit, fallback) {
    var table = unitTable();
    var fmt = table && table.formats && table.formats[unit];
    var m = fmt && /%\.(\d+)f/.exec(fmt);
    return m ? parseInt(m[1], 10) : (fallback === undefined ? 1 : fallback);
  }

  /* Converts one reading to the unit system the reader chose. Returns {value, unit,
     label}, or null where the reading stays as it is. */
  function convertReading(value, fromUnit, obsType) {
    if (value === null || value === undefined || isNaN(value)) return null;
    var to = targetUnit(obsType, fromUnit);
    if (!to) return null;
    var table = unitTable();
    var steps = table.convert[fromUnit][to];
    return {
      value: value * steps[0] + steps[1],
      unit: to,
      label: table.labels[to] || ''
    };
  }

  /* Returns the unit label `now`, with a space in front if the label `was` had one.
     The skin writes some unit labels with a space in front and some without, and
     the labels in the unit table have none, so a converted label copies the
     spacing of the label it replaces. */
  function respace(was, now) {
    if (!now) return now;
    var lead = was && /^\s/.test(was) ? ' ' : '';
    return lead + now.replace(/^\s+/, '');
  }

  /* Converts the readings WeeWX wrote into the page, within `root` or the whole
     document, to the unit system the reader chose. Each reading carries its number
     in `data-value` and its unit in `data-unit`. The text WeeWX wrote is kept in
     `data-as-written`, and shown again when no unit system is chosen. */
  function applyUnitsToPanels(root) {
    var scope = root || document;

    /* An element with `data-unit` but no `data-value`, such as a column heading,
       has a unit label and no number. Converting 1 gives the target unit's label. */
    scope.querySelectorAll('[data-unit]:not([data-value])').forEach(function (el) {
      var label = el.querySelector('[data-unit-label]');
      if (!label) return;
      if (label.dataset.asWritten === undefined) {
        label.dataset.asWritten = label.textContent;
      }
      var out = convertReading(1, el.dataset.unit, el.dataset.obs || el.dataset.live);
      label.textContent = out
        ? respace(label.dataset.asWritten, out.label)
        : label.dataset.asWritten;
    });

    scope.querySelectorAll('[data-unit][data-value]').forEach(function (el) {
      /* `data-obs` names the observation type, `data-live` the field in
         current.json. The two differ where a field is derived, e.g., 'rainToday' from
         'rain', and only the observation type is in the unit table. */
      var obs = el.dataset.obs || el.dataset.live;
      var out = convertReading(parseFloat(el.dataset.value), el.dataset.unit, obs);
      var target = el.querySelector('[data-unit-value]') || el;
      var label = el.querySelector('[data-unit-label]')
        || (el.parentNode && el.parentNode.querySelector('[data-unit-label]'));

      if (!out) {
        /* No conversion: show the text WeeWX wrote. */
        if (el.dataset.asWritten !== undefined) target.textContent = el.dataset.asWritten;
        if (label && label.dataset.asWritten !== undefined) {
          label.textContent = label.dataset.asWritten;
        }
        return;
      }
      if (el.dataset.asWritten === undefined) {
        el.dataset.asWritten = (target.textContent || '').trim();
      }
      if (label && label.dataset.asWritten === undefined) {
        label.dataset.asWritten = label.textContent;
      }
      target.textContent = fmtNumber(out.value, decimalsFor(out.unit));
      if (label) label.textContent = respace(label.dataset.asWritten, out.label);
    });
  }

  /* The unit conversion for climate.js and forecast.js, which draw readings that
     are not in the JSON files. Only these four functions are shared, so that the
     unit table and the reader's choice exist once on the page. */
  CFG.units = {
    /* target(obsType, fromUnit) returns the unit to show, or null. */
    target: targetUnit,
    /* convert(value, fromUnit, obsType) returns {value, unit, label}, or null. */
    convert: convertReading,
    /* decimals(unit, fallback) returns the number of decimals for `unit`. */
    decimals: decimalsFor,
    /* chosen() returns the unit system the reader chose, or ''. */
    chosen: function () { return recall('units', ''); }
  };

  /* tempColour(celsius) returns the CSS colour for a temperature in degree_C, from
     the palette of the tiles (see WARM_AT). climate.js colours its heat map with
     CFG.tempColour. */
  CFG.tempColour = function (celsius) {
    return tempColour(celsius, warmStops());
  };

  /* Returns the names of the unit systems in the unit table, e.g., ['US', 'METRIC',
     'METRICWX'], or [] where data/index.json has no unit table. */
  function availableSystems() {
    var table = unitTable();
    if (!table || !table.systems) return [];
    return Object.keys(table.systems).filter(function (name) {
      return Object.keys(table.systems[name]).length;
    });
  }

  /* Fills the unit picker in the navigation with the unit systems of the unit table,
     and shows the picker where there are at least two. The unit picker converts
     every reading on the page, the tiles as well as the charts. */
  function setupUnitPicker() {
    var picker = document.getElementById('unit-picker');
    if (!picker) return;

    var chosen = recall('units', '');
    if (chosen) applyUnitsAll();

    loadManifest().then(function () {
      var systems = availableSystems();
      if (systems.length < 2) return;
      picker.innerHTML = ['<option value="">'
                          + escapeHtml(CFG.text.asConfigured || 'Default')
                          + '</option>']
        .concat(systems.map(function (name) {
          return '<option value="' + name + '"'
            + (name === recall('units', '') ? ' selected' : '') + '>' + name + '</option>';
        })).join('');
      /* nav.inc writes the `.nav-field` hidden, label included, so the field is
         shown and not the select alone. */
      (picker.closest('.nav-field') || picker).hidden = false;
      if (recall('units', '')) applyUnitsAll();
    });

    picker.addEventListener('change', function () {
      remember('units', picker.value);
      applyUnitsAll();
    });
  }

  /* Converts every reading on the page to the unit system the reader chose,
     without fetching anything: the panels, the charts, and, through the event
     'horizon:units', whatever climate.js and forecast.js drew. */
  function applyUnitsAll() {
    applyUnitsToPanels();
    charts.forEach(function (entry) {
      if (entry.raw) updateChart(entry, entry.raw);
    });
    document.dispatchEvent(new CustomEvent('horizon:units'));
  }

  /* -------------------------------------------------------------- shaping */

  /* Returns the columns of the data table: [times, values of series 1, values of
     series 2, ...]. The series of one plot usually share their times. Where the
     times differ, `times` is the union of all of them, and a series has null at a
     time it has no reading for. */
  function align(series) {
    var first = series[0].time;
    var same = series.every(function (s) {
      return s.time.length === first.length && s.time[0] === first[0]
        && s.time[s.time.length - 1] === first[first.length - 1];
    });
    if (same) {
      return [first].concat(series.map(function (s) { return s.values; }));
    }

    var set = new Set();
    series.forEach(function (s) { s.time.forEach(function (t) { set.add(t); }); });
    var xs = Array.from(set).sort(function (a, b) { return a - b; });
    var index = new Map();
    xs.forEach(function (t, i) { index.set(t, i); });

    var out = [xs];
    series.forEach(function (s) {
      var col = new Array(xs.length).fill(null);
      s.time.forEach(function (t, i) {
        var at = index.get(t);
        if (at !== undefined) col[at] = s.values[i];
      });
      out.push(col);
    });
    return out;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ----------------------------------------------------------- chart pieces */

  /* Every chart drawn on the page, as {plot, host, meta, raw, period}: the ECharts
     instance, its element, the plot data in the chosen unit system, the plot data
     as fetched, and the time span. A new archive record, a theme change and a unit
     change update these instances in place.

     A chart card is the `section.chart-card` that showPeriod makes for each plot
     group: the chart's title, the chart and its data table. */
  var charts = [];

  /* Returns the nights of `meta.daynight` as bands for the chart's markArea. The
     JSON generator writes `daynight` beside the readings, e.g.

       {"first": "night", "transitions": [1230824814, 1230856303, ...],
        "twilight": [{"dir": "dawn", "from": 1230822770, "to": 1230824814}, ...]}

     where `transitions` holds the times of sunrise and sunset, and `first` says
     whether the chart starts at night. */
  function nightAreas(meta) {
    var dn = meta.daynight;
    if (!dn || !dn.transitions || !dn.transitions.length) return [];

    /* The bands fade in over the length of a dusk and out over the length of a
       dawn, both from `twilight`, or over 1800 seconds where the file has no
       twilight. The last dusk and dawn in `twilight` serve for every band, since
       the length of a twilight changes only slowly over the year. */
    var fade = {};
    (dn.twilight || []).forEach(function (b) {
      if (b && b.from && b.to) fade[b.dir === 'dawn' ? 'dawn' : 'dusk'] = b.to - b.from;
    });
    var dawn = fade.dawn || 1800;
    var dusk = fade.dusk || 1800;

    var out = [];
    var night = dn.first === 'night';
    var from = meta.start;
    var push = function (a, b) {
      /* The band starts half of `dusk` before sunset and ends half of `dawn` after
         sunrise, so that each fade is centred on sunset or sunrise. */
      var lo = a - dusk / 2, hi = b + dawn / 2;
      var span = hi - lo;
      if (span <= 0) return;
      out.push({
        span: span,
        /* The band is fully dark between the fractions in1 and in2 of its width. */
        in1: Math.min(0.5, dusk / span),
        in2: Math.max(0.5, 1 - dawn / span),
        pair: [{ xAxis: lo * 1000 }, { xAxis: hi * 1000 }]
      });
    };

    dn.transitions.forEach(function (ts) {
      if (night) push(from, ts);
      night = !night;
      from = ts;
    });
    if (night) push(from, meta.stop || from);
    return out;
  }

  /* Returns the markArea entry for one band of nightAreas, in `colour` with a
     gradient that fades in and out at the ends. */
  function nightBand(band, colour) {
    /* The ends fade to `colour` at zero opacity. Fading to 'transparent', which is
       black at zero opacity, would put a grey cast in the middle of each fade. */
    var clear = /^#[0-9a-f]{6}$/i.test(colour) ? colour + '00'
      : colour.replace(/^rgb\(/i, 'rgba(').replace(/\)$/, ', 0)');
    var stops = [
      { offset: 0, color: clear },
      { offset: band.in1, color: colour },
      { offset: band.in2, color: colour },
      { offset: 1, color: clear }
    ];
    var pair = band.pair.slice();
    pair[0] = { xAxis: pair[0].xAxis,
                itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, stops) } };
    return pair;
  }

  /* Returns the width of a bar in pixels: the time the bar totals, as a share of
     the time span, times the chart's width, less 15% for the gap between bars.
     ECharts would size a bar from the smallest gap between two points. For hourly
     totals on a finer interval, e.g., rain in an archive file, every bar would then
     be as narrow as that finer interval. */
  function barWidthPx(meta, s, hostWidth) {
    var covered = s.aggregate_interval || meta.aggregate_interval;
    var span = (meta.stop || 0) - (meta.start || 0);
    if (!covered || !span || !hostWidth) return undefined;
    return Math.max(1, Math.floor((covered / span) * hostWidth * 0.85));
  }

  /* Returns the renderItem of an ECharts custom series, for the plot type 'vector'.
     Each reading is a line from the zero line, as long as the wind speed on the y
     axis, in the direction of `vector_x` and `vector_y` turned by `vector_rotate`
     degrees. */
  function vectorRenderItem(s, meta) {
    var rotate = (s.vector_rotate || 0) * Math.PI / 180;
    return function (params, api) {
      var i = params.dataIndex;
      var x = s.vector_x && s.vector_x[i];
      var y = s.vector_y && s.vector_y[i];
      if (x === null || x === undefined || y === null || y === undefined) return;

      var base = api.coord([api.value(0), 0]);
      var tip = api.coord([api.value(0), Math.sqrt(x * x + y * y)]);
      var len = base[1] - tip[1];
      if (!len) return;

      var mag = Math.sqrt(x * x + y * y) || 1;
      var ux = (x / mag), uy = (y / mag);
      var ca = Math.cos(rotate), sa = Math.sin(rotate);
      var dx = ux * ca - uy * sa, dy = ux * sa + uy * ca;
      var ex = base[0] + dx * len, ey = base[1] - dy * len;

      return {
        type: 'line',
        shape: { x1: base[0], y1: base[1], x2: ex, y2: ey },
        style: { stroke: s.color || themeColors().ink, lineWidth: 1 }
      };
    };
  }

  /* --------------------------------------------------------------- charting */

  /* The first digits of a step between gridlines that reads as round, at any power
     of ten. 4.5 is in the list for 45 degrees, an eighth of the compass. A step that
     a conversion produces, e.g., 1.27 mm from 0.05 inch, is not round. */
  var ROUND_STEPS = [1, 1.5, 2, 2.5, 3, 4, 4.5, 5, 6, 7.5, 9];

  function isRound(v) {
    if (!v) return false;
    var mag = Math.pow(10, Math.floor(Math.log(Math.abs(v)) / Math.LN10));
    var lead = Math.abs(v) / mag;
    return ROUND_STEPS.some(function (m) { return Math.abs(lead - m) < 1e-9; });
  }

  /* Returns whether both ends of the y axis, `lo` and `hi`, are whole multiples of
     `step`. The `yscale` that the JSON generator works out passes, but after a
     conversion with an offset it can fail: a step of 5 degree_C becomes 9 degree_F,
     which ROUND_STEPS accepts, while ends of 0 and 40 degree_C become 32 and 104
     degree_F, which are not multiples of 9. */
  function divides(lo, hi, step) {
    if (!step) return false;
    var whole = function (v) {
      var n = v / step;
      return Math.abs(n - Math.round(n)) < 1e-6;
    };
    return whole(lo) && whole(hi);
  }

  /* Returns the step between the y axis gridlines of a chart `height` pixels high,
     or null to let ECharts choose. The step of `meta.yscale` is kept where the step
     is round, divides the axis, and leaves room between the labels. */
  function gridStep(meta, height) {
    if (!meta.yscale || !meta.yscale[2]) return null;
    var step = meta.yscale[2];
    var span = meta.yscale[1] - meta.yscale[0];
    if (!(span > 0)) return step;

    /* The labels are 12 px high, and a gridline every 24 px leaves as much space
       again between them. */
    var room = Math.max(2, Math.floor((height - 40) / 24));

    if (span / step <= room && isRound(step)
        && divides(meta.yscale[0], meta.yscale[1], step)) {
      return step;
    }

    /* Otherwise take the smallest of 1, 2, 2.5 and 5 times a power of ten that
       needs no more than `room` gridlines. */
    var least = span / room;
    var mag = Math.pow(10, Math.floor(Math.log(least) / Math.LN10));
    var nice = [1, 2, 2.5, 5, 10, 20].map(function (m) { return m * mag; })
      .filter(function (v) { return v >= least; })[0];
    return nice || step;
  }

  /* Returns the lower or upper end of the y axis (`which` is 'min' or 'max'), moved
     outward to a whole multiple of `step`, so that no reading falls outside the
     axis. After a conversion the ends of `meta.yscale` are seldom multiples, e.g.
     29.0 inHg is 982.05 mbar, and ECharts would put the gridlines at 982.05,
     992.05, and so on. */
  function axisEnd(meta, step, which) {
    if (!meta.yscale) return null;
    var v = meta.yscale[which === 'min' ? 0 : 1];
    if (v === null || v === undefined || !step) return v === undefined ? null : v;
    var snapped = which === 'min' ? Math.floor(v / step) * step
                                  : Math.ceil(v / step) * step;
    /* Remove floating-point error, e.g., 0.30000000000000004, from the label. */
    return Math.round(snapped * 1e6) / 1e6;
  }

  function chartHeight(width) {
    /* A chart is 0.32 times as high as it is wide, and between 270 px and 360 px
       high. A lower chart has room for too few gridlines, e.g., for four labels on
       a pressure axis at 180 px. horizon.css gives `.chart-skeleton` the same
       270 px. */
    return Math.max(270, Math.min(360, Math.round(width * 0.32)));
  }

  /* Saves the chart as a PNG, with the chart title and the end of the time span
     above the chart, so that the picture says what it shows when it is posted
     elsewhere. */
  function exportChart(entry, card) {
    var url = entry.plot.getDataURL({
      pixelRatio: window.devicePixelRatio || 2,
      backgroundColor: getComputedStyle(document.documentElement)
        .getPropertyValue('--surface').trim() || '#ffffff'
    });
    var img = new Image();
    img.onload = function () {
      var ratio = window.devicePixelRatio || 2;
      var pad = Math.round(12 * ratio);
      var titleHeight = Math.round(30 * ratio);
      var out = document.createElement('canvas');
      out.width = img.width + pad * 2;
      out.height = img.height + titleHeight + pad;
      var ctx = out.getContext('2d');

      var styles = getComputedStyle(document.documentElement);
      ctx.fillStyle = styles.getPropertyValue('--surface').trim() || '#ffffff';
      ctx.fillRect(0, 0, out.width, out.height);

      var family = getComputedStyle(document.body).fontFamily;
      ctx.textBaseline = 'top';
      ctx.fillStyle = styles.getPropertyValue('--ink').trim() || '#000000';
      ctx.font = '600 ' + Math.round(13 * ratio) + 'px ' + family;
      var title = (card.querySelector('.chart-title') || {}).textContent || '';
      ctx.fillText(title, pad, Math.round(4 * ratio));

      ctx.fillStyle = styles.getPropertyValue('--ink-faint').trim() || '#888888';
      ctx.font = Math.round(10 * ratio) + 'px ' + family;
      var when = card.dataset.from
        ? fmtTime(+card.dataset.to, card.dataset.period) : '';
      ctx.fillText((CFG.stationName || '') + (when ? ' · ' + when : ''),
                   pad, Math.round(19 * ratio));

      ctx.drawImage(img, pad, titleHeight);
      var link = document.createElement('a');
      link.download = (entry.meta.name || 'chart') + '.png';
      link.href = out.toDataURL('image/png');
      link.click();
    };
    img.src = url;
  }

  /* Returns the ECharts options for one chart. The options are built again on each
     change of readings, unit or theme, and passed to setOption() of the existing
     instance. */
  function chartOptions(meta, period, hostWidth) {
    var colors = themeColors();
    var family = getComputedStyle(document.body).fontFamily;
    var digits = digitsFor(meta.series);
    var isBar = meta.series.some(function (s) { return s.plot_type === 'bar'; });
    var step = gridStep(meta, chartHeight(hostWidth));
    var areas = isBar ? [] : nightAreas(meta);

    var series = meta.series.map(function (s, i) {
      var points = (s.time || []).map(function (t, j) {
        return [t * 1000, s.values[j]];
      });

      if (s.plot_type === 'vector') {
        return {
          name: s.label, type: 'custom', data: points,
          renderItem: vectorRenderItem(s, meta),
          encode: { x: 0, y: 1 },
          animation: false, silent: false
        };
      }

      var out = {
        name: s.label,
        type: s.plot_type === 'bar' ? 'bar' : 'line',
        data: points,
        animation: false,
        symbol: 'none',
        connectNulls: false,
        /* A day of one-minute readings is 1440 points and a year of hourly ones
           8760, more than a chart has pixels across. 'lttb' draws the points that
           keep the shape of the line. */
        sampling: 'lttb',
        large: true
      };
      if (s.plot_type === 'bar') {
        out.itemStyle = { color: s.fill_color || s.color || colors.ink };
        var w = barWidthPx(meta, s, hostWidth);
        if (w) out.barWidth = w;
        out.barGap = '-100%';
      } else {
        out.lineStyle = { color: s.color || colors.ink, width: 1.2 };
        out.itemStyle = { color: s.color || colors.ink };
      }
      /* The night shading goes on the first series, at z -1: in front of the
         gridlines the shading would hide them and the zero line. */
      if (i === 0 && areas.length) {
        var night = colors.night || 'rgba(0,0,0,0.05)';
        out.markArea = {
          silent: true,
          z: -1,
          emphasis: { disabled: true },
          data: areas.map(function (b) { return nightBand(b, night); })
        };
      }
      return out;
    });

    return {
      animation: false,
      grid: { left: 52, right: 10, top: 24, bottom: 28, containLabel: false },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: colors.axis, width: 1,
                                                  type: [4, 3] } },
        /* The tooltip stays in the top corner on the side away from the pointer.
           A tooltip that follows the pointer covers the readings being compared,
           and jumps to the other side at the edge of the chart. */
        position: function (point, params, dom, rect, size) {
          var wide = size.viewSize[0];
          var box = size.contentSize[0];
          var pointerRight = point[0] > wide / 2;
          return [pointerRight ? 10 : Math.max(10, wide - box - 10), 8];
        },
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderWidth: 1,
        padding: [6, 9],
        extraCssText: 'box-shadow: 0 2px 10px rgba(0,0,0,0.14); border-radius: 6px;',
        textStyle: { color: colors.ink, fontFamily: family, fontSize: 12 },
        formatter: function (params) {
          if (!params.length) return '';
          var when = fmtTime(Math.round(params[0].value[0] / 1000), period);
          var rows = params.map(function (p) {
            var s = meta.series[p.seriesIndex];
            var extra = '';
            /* A wind series carries `directions`, shown after the speed. */
            if (s && s.directions) {
              var d = s.directions[p.dataIndex];
              if (d !== null && d !== undefined) extra = ' · ' + fmtNumber(d, 0) + '°';
            }
            /* Where the series carries `min` and `max`, the tooltip shows them after
               the average: an hour with an average wind of 10 mph can have a
               maximum of 20. */
            if (s && s.max) {
              var lo = s.min && s.min[p.dataIndex], hi = s.max[p.dataIndex];
              if (hi !== null && hi !== undefined) {
                extra += ' <span style="color:' + colors.muted + '">('
                  + (lo === null || lo === undefined ? '' : fmtNumber(lo, digits) + '…')
                  + fmtNumber(hi, digits) + ')</span>';
              }
            }
            return '<span style="color:' + p.color + '">●</span> '
              + escapeHtml(p.seriesName) + ': <b>'
              + fmtNumber(p.value[1], digits) + '</b>'
              + (meta.unit_label ? ' ' + escapeHtml(meta.unit_label) : '') + extra;
          });
          return '<span style="color:' + colors.muted + '">' + escapeHtml(when)
            + '</span><br>' + rows.join('<br>');
        }
      },
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: colors.axis } },
        axisTick: { lineStyle: { color: colors.grid } },
        splitLine: { show: true, lineStyle: { color: colors.grid } },
        axisLabel: {
          /* --ink-muted rather than --chart-axis: the axis line may be faint, but
             its labels must be readable. */
          color: colors.muted, fontFamily: family, fontSize: 12,
          formatter: function (value) { return fmtTick(value / 1000, period, null); },
          hideOverlap: true
        }
      },
      yAxis: {
        type: 'value',
        name: meta.unit_label || '',
        nameLocation: 'end',
        nameGap: 12,
        nameTextStyle: {
          color: colors.muted, fontFamily: family, fontSize: 12, align: 'left'
        },
        /* `meta.yscale` comes from the JSON generator, which scales the y axis as
           the ImageGenerator does. Left to itself, ECharts runs a wind direction
           axis to 400 degrees, or a wind speed axis to 5 m/s for wind that never
           passed 2.3. */
        min: axisEnd(meta, step, 'min'),
        max: axisEnd(meta, step, 'max'),
        interval: step,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: colors.grid } },
        axisLabel: {
          color: colors.muted, fontFamily: family, fontSize: 12,
          formatter: function (v) { return fmtNumber(v, digits); }
        }
      },
      series: series
    };
  }

  function buildChart(host, meta, period) {
    meta._period = period;
    var hostWidth = host.clientWidth || 600;
    host.style.height = chartHeight(hostWidth) + 'px';
    var plot = echarts.init(host, null, { renderer: 'canvas' });
    plot.setOption(chartOptions(meta, period, hostWidth));
    return { plot: plot, meta: meta, host: host, period: period };
  }

  /* unitLabel writes the date between the arrows (#range-label) in a short form
     below 34rem and in a long form above. Crossing 34rem, e.g., by turning a phone,
     calls showPeriod to write the date again. */
  window.matchMedia('(min-width: 34rem)').addEventListener('change', function () {
    if (currentPeriod) showPeriod(currentPeriod);
  });

  function redrawAll() {
    /* chartOptions reads the colours from the stylesheet, so a theme change
       builds the options again. */
    charts.forEach(function (c) {
      c.plot.setOption(chartOptions(c.meta, c.period, c.host.clientWidth || 600));
    });
  }

  /* One ResizeObserver for all charts. At a new width a chart gets a new height and
     new series, because barWidthPx gives the width of a bar in pixels. */
  var resizeObserver = new ResizeObserver(function (entries) {
    entries.forEach(function (entry) {
      var c = charts.find(function (x) { return x.host === entry.target; });
      if (!c) return;
      var w = Math.round(entry.contentRect.width);
      if (w <= 0) return;
      c.host.style.height = chartHeight(w) + 'px';
      c.plot.resize({ width: w, height: chartHeight(w) });
      c.plot.setOption({ series: chartOptions(c.meta, c.period, w).series });
    });
  });

  /* ------------------------------------------------------------- rendering */

  function renderTable(meta, digits) {
    var head = '<tr><th>' + escapeHtml(CFG.text.time || 'Time') + '</th>'
      + meta.series.map(function (s) { return '<th>' + escapeHtml(s.label) + '</th>'; }).join('')
      + '</tr>';
    var data = align(meta.series);
    var rows = [];
    /* At most LIMIT rows. Above LIMIT readings the table shows every nth reading,
       and a note above the table says so. Only a long time span of raw readings
       has more than LIMIT. */
    var LIMIT = 1500;
    var total = data[0].length;
    var step = total > LIMIT ? Math.ceil(total / LIMIT) : 1;

    for (var i = 0; i < total; i += step) {
      var cells = '';
      for (var j = 1; j < data.length; j++) {
        cells += '<td>' + fmtNumber(data[j][i], digits) + '</td>';
      }
      rows.push('<tr><td class="metric">' + escapeHtml(fmtTime(data[0][i], meta._period))
        + '</td>' + cells + '</tr>');
    }

    var note = step > 1
      ? '<p class="table-note">' + escapeHtml((CFG.text.thinned || 'Showing every {n}th of {total} readings.')
          .replace('{n}', step).replace('{total}', total)) + '</p>'
      : '';

    return note + '<div class="scroller"><table class="data-table"><thead>' + head
      + '</thead><tbody>' + rows.join('') + '</tbody></table></div>';
  }

  function renderChart(card, raw, period) {
    /* entry.raw keeps the plot data as fetched, so that a unit change converts
       from entry.raw and not from converted data. */
    var meta = inChosenUnit(raw);
    var host = card.querySelector('.chart-host');
    var legend = card.querySelector('.chart-title');
    var details = card.querySelector('.chart-data');

    host.innerHTML = '';

    if (!meta.series.length) {
      host.innerHTML = '<p class="chart-empty">' + escapeHtml(CFG.text.noData || 'No data') + '</p>';
      return;
    }

    /* The chart title is the legend: each series name in the colour of its line.
       An ECharts legend would take a line of the chart's height on a phone. */
    legend.innerHTML = meta.series.map(function (s) {
      return '<span style="color:' + (s.color || 'currentColor') + '"><i></i>'
        + '<span class="series-name">' + escapeHtml(s.label) + '</span></span>';
    }).join('');

    var entry = buildChart(host, meta, period);
    entry.raw = raw;
    charts.push(entry);
    resizeObserver.observe(host);

    var actions = card.querySelector('.chart-actions');
    if (actions) {
      var save = document.createElement('button');
      save.type = 'button';
      save.className = 'chart-action';
      save.textContent = CFG.text.saveImage || 'Save image';
      save.addEventListener('click', function () { exportChart(entry, card); });
      actions.appendChild(save);
    }

    if (details) {
      var digits = digitsFor(meta.series);
      details.querySelector('.scroller-host').innerHTML = renderTable(meta, digits);
    }
  }

  /* Updates a drawn chart with the plot data `raw`, after a new archive record or a
     unit change. setOption() on the existing instance moves the x axis and adds the
     new reading without clearing the chart. A new instance would draw the chart
     from scratch, and the chart would flicker on every new archive record.

     Returns false where the number of series has changed, e.g., when a series gets
     its first reading. The caller then draws the chart again. */
  function updateChart(entry, raw) {
    var plot = entry.plot;
    var fresh = inChosenUnit(raw);
    if (!fresh.series || fresh.series.length !== entry.meta.series.length) return false;

    /* The new data is copied into entry.meta rather than replacing the object,
       because renderTable reads `_period`, which buildChart set on entry.meta. */
    Object.keys(fresh).forEach(function (key) { entry.meta[key] = fresh[key]; });
    entry.raw = raw;
    plot.setOption(chartOptions(entry.meta, entry.period,
                                entry.host.clientWidth || 600));

    /* An open data table is built again now. A closed data table gets
       `data-stale`, and is built when the reader opens it (see setupPeriods). */
    var card = entry.host.closest('.chart-card');
    var details = card && card.querySelector('.chart-data');
    if (details) {
      if (details.open) {
        details.querySelector('.scroller-host').innerHTML =
          renderTable(entry.meta, digitsFor(entry.meta.series));
        delete details.dataset.stale;
      } else {
        details.dataset.stale = '1';
      }
    }
    return true;
  }

  /* Returns a promise of the plot data for one chart card, or of null. */
  function chartSource(card) {
    return windowFromArchive(card.dataset.group, +card.dataset.from, +card.dataset.to);
  }

  /* Updates the charts to the newest archive record. Only the live view changes;
     a time span in the past stays as it is. */
  function refreshCharts() {
    if (anchor !== null) return;
    archiveCache.clear();
    archiveIndex = null;
    manifest = null;

    /* The live view ends at the newest archive record, so each chart card gets a
       new start and end. */
    var win = currentWindow(currentPeriod);

    loadArchiveIndex().then(function () {
      charts.forEach(function (entry) {
        var card = entry.host.closest('.chart-card');
        if (!card || !card.dataset.group) return;
        card.dataset.from = win.from;
        card.dataset.to = win.to;
        chartSource(card).then(function (fresh) {
          if (!fresh || !fresh.series || !fresh.series.length) return;
          if (updateChart(entry, fresh)) return;
          /* The number of series changed: draw the chart card again. */
          resizeObserver.unobserve(entry.host);
          entry.plot.dispose();
          charts = charts.filter(function (c) { return c !== entry; });
          renderChart(card, fresh, card.dataset.period);
        });
      });
    });

    /* A chart card that was fetched but had no readings to draw fetches again,
       since the new archive record may bring some. A chart card not yet scrolled
       into view fetches when the reader scrolls to it, from the emptied cache. */
    document.querySelectorAll('#charts .chart-card').forEach(function (card) {
      var drawn = charts.some(function (c) { return c.host === card.querySelector('.chart-host'); });
      if (!drawn && card.dataset.loaded) {
        delete card.dataset.loaded;
        hydrate(card);
      }
    });
  }

  function clearCharts() {
    charts.forEach(function (c) {
      resizeObserver.unobserve(c.host);
      c.plot.dispose();
    });
    charts = [];
    document.querySelectorAll('#charts .chart-card').forEach(function (card) {
      lazyObserver.unobserve(card);
    });
  }

  /* ------------------------------------------------------------ index.json */

  /* `manifest` holds data/index.json: the length of each time span (`spans`) and
     the unit table (`units`). */
  var manifest = null;

  /* --------------------------------------------------------- archive files */

  /* The archive files, in data/archive/, hold the readings of each plot group over
     the whole archive, in three tiers (see MAX_POINTS). data/archive/index.json
     lists the files that exist. A time span fetches only the files it touches, and
     archiveCache keeps each file until refreshCharts empties the cache. */

  var archiveIndex = null;
  var archiveCache = new Map();           // file name -> file contents

  /* A timestamp inside the calendar unit on screen, i.e., the day, week, month or
     year of the calendar that the charts show. null means the live view, which
     moves with each new archive record. Any other time span stays fixed, so a link
     to it shows the same days tomorrow. */
  var anchor = null;

  /* The length of the live view of each time span, in seconds. The live view ends
     at the newest archive record and reaches back this far, so that shortly after
     midnight the Day chart still shows the evening before. A time span reached with
     the arrows or the calendar is a calendar unit instead, e.g., Tuesday, week 33,
     July or 2025.

     These values are defaults. adoptSpans replaces them with the `time_length` of
     [[day_images]], [[week_images]] and so on in skin.conf, which data/index.json
     carries as `spans`. */
  var PERIOD_SECONDS = { day: 27 * 3600, week: 7 * 86400, month: 30 * 86400, year: 365 * 86400 };

  function adoptSpans(manifest) {
    if (!manifest || !manifest.spans) return;
    Object.keys(manifest.spans).forEach(function (group) {
      /* data/index.json names a time span by its section in skin.conf, e.g.
         'day_images', and the page names it 'day'. */
      var period = group.replace(/_images$/, '');
      var seconds = parseInt(manifest.spans[group], 10);
      if (seconds > 0) PERIOD_SECONDS[period] = seconds;
    });
  }

  /* There are two current times here, and using one where the other belongs moves
     the calendar by a day.

     dataTs() is the time of the newest archive record in the report
     (`window.HORIZON.generated`). The live view ends at that time, and the arrows
     step from the calendar unit that holds it.

     nowTs() is the browser's clock, and decides only whether the live view is
     labelled "Now" (see liveLabel). The two times differ when the station was off
     overnight, when the page has been open past midnight, or when a cache serves an
     older copy of the page. */
  function nowTs() {
    return Math.floor(Date.now() / 1000);
  }

  function dataTs() {
    return CFG.generated || nowTs();
  }

  /* Returns {from, to}, the start and end of the calendar unit of `period` that
     holds `ts`. */
  function calendarWindow(period, ts) {
    var d = new Date(ts * 1000);
    var y = d.getFullYear(), m = d.getMonth(), day = d.getDate();
    var from, to;

    if (period === 'day') {
      from = new Date(y, m, day);
      to = new Date(y, m, day + 1);
    } else if (period === 'week') {
      /* week_start comes from weewx.conf: 0 is Monday, 6 is Sunday. */
      var startDow = (CFG.weekStart === undefined ? 0 : +CFG.weekStart);
      var jsStart = (startDow + 1) % 7;            // JS counts Sunday as 0
      var back = (d.getDay() - jsStart + 7) % 7;
      from = new Date(y, m, day - back);
      to = new Date(from.getFullYear(), from.getMonth(), from.getDate() + 7);
    } else if (period === 'month') {
      from = new Date(y, m, 1);
      to = new Date(y, m + 1, 1);
    } else {
      from = new Date(y, 0, 1);
      to = new Date(y + 1, 0, 1);
    }
    return { from: Math.floor(from.getTime() / 1000), to: Math.floor(to.getTime() / 1000) };
  }

  /* Returns the time span on screen as {from, to, live}. */
  function currentWindow(period) {
    if (anchor === null) {
      var to = dataTs();
      return { from: to - (PERIOD_SECONDS[period] || PERIOD_SECONDS.day), to: to, live: true };
    }
    var w = calendarWindow(period, anchor);
    w.live = false;
    return w;
  }

  function loadArchiveIndex() {
    if (archiveIndex) return Promise.resolve(archiveIndex);
    return fetch(DATA_DIR + '/archive/index.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { archiveIndex = j || { groups: [] }; return archiveIndex; })
      .catch(function () { archiveIndex = { groups: [] }; return archiveIndex; });
  }

  function loadArchiveFile(name) {
    if (archiveCache.has(name)) return Promise.resolve(archiveCache.get(name));
    return fetch(DATA_DIR + '/archive/' + name + '.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { archiveCache.set(name, j); return j; })
      .catch(function () { archiveCache.set(name, null); return null; });
  }

  /* The archive files come in three tiers, which overlap in time. The raw tier holds
     the station's own readings, one file per day. The fine tier holds readings at a
     longer interval, one file per month. The year tier holds readings at a still
     longer interval, which grows with age, one file per calendar year. TIER_KEYS
     lists the tiers finest first, with the keys of data/archive/index.json that list
     each tier's files (`named`) and their intervals (`grids`).

     filesFor takes the finest tier that covers the whole time span. A tier covers a
     time span where data/archive/index.json names a file for every part of it, and
     where the time span comes to no more than MAX_POINTS readings. At a one-minute
     archive interval, a day of the raw tier is 1440 readings, and a year would be
     half a million, far more than a chart 1000 px wide can show. */
  var MAX_POINTS = 20000;

  var TIER_KEYS = [
    { kind: 'raw', named: 'raw', grids: 'raw_intervals',
      name: function (group, key) { return group + '-raw-' + key; },
      keys: function (from, to) { return stampsIn(from, to, 'day'); } },
    { kind: 'fine', named: 'fine', grids: 'fine_intervals',
      name: function (group, key) { return group + '-fine-' + key; },
      keys: function (from, to) { return stampsIn(from, to, 'month'); } },
    { kind: 'year', named: 'covered', grids: 'intervals',
      name: function (group, key) { return group + '-' + key; },
      keys: function (from, to) { return stampsIn(from, to, 'year'); } }
  ];

  /* Returns the keys of the files that the time span from `from` to `to` touches,
     as data/archive/index.json writes them: '2026-07-13' for `unit` 'day',
     '2026-07' for 'month' and '2026' for 'year'. */
  function stampsIn(from, to, unit) {
    var out = [];
    var cursor = new Date(from * 1000);
    cursor.setHours(0, 0, 0, 0);
    if (unit !== 'day') cursor.setDate(1);
    if (unit === 'year') cursor.setMonth(0);
    while (cursor.getTime() / 1000 < to) {
      var y = cursor.getFullYear();
      var m = cursor.getMonth() + 1;
      var d = cursor.getDate();
      var pad = function (n) { return (n < 10 ? '0' : '') + n; };
      if (unit === 'day') { out.push(y + '-' + pad(m) + '-' + pad(d)); cursor.setDate(d + 1); }
      else if (unit === 'month') { out.push(y + '-' + pad(m)); cursor.setMonth(m); }
      else { out.push(String(y)); cursor.setFullYear(y + 1); }
      if (out.length > 400) break;
    }
    return out;
  }

  /* Returns whether the year, month or day that `key` names ('2026', '2026-07' or
     '2026-07-13') overlaps the archive, from `first` to `last` in
     data/archive/index.json. Returns true where the index has no `first` and
     `last`. */
  function touchesRecord(key) {
    if (!archiveIndex || !archiveIndex.first || !archiveIndex.last) return true;
    var parts = key.split('-').map(Number);
    var start = new Date(parts[0], (parts[1] || 1) - 1, parts[2] || 1);
    var stop = new Date(start);
    if (parts.length === 1) stop.setFullYear(start.getFullYear() + 1);
    else if (parts.length === 2) stop.setMonth(start.getMonth() + 1);
    else stop.setDate(start.getDate() + 1);
    return stop.getTime() / 1000 > archiveIndex.first
      && start.getTime() / 1000 < archiveIndex.last;
  }

  /* Returns {interval, names}, the archive files to draw a time span from, taken
     from the finest tier that covers the time span, or null where no tier does. */
  function filesFor(group, from, to) {
    var entry = ((archiveIndex && archiveIndex.groups) || []).filter(function (g) {
      return g.name === group;
    })[0];
    if (!entry) return null;

    for (var t = 0; t < TIER_KEYS.length; t++) {
      var tier = TIER_KEYS[t];
      var have = entry[tier.named];
      if (!have) continue;
      var keys = tier.keys(from, to);
      if (!keys.length) continue;

      var grids = entry[tier.grids] || {};
      var ok = true;
      var interval = 0;
      var present = [];
      for (var i = 0; i < keys.length; i++) {
        if (!(keys[i] in have)) {
          /* A key that the index does not name is harmless where the archive has
             no readings for that time. Otherwise the tier does not reach back far
             enough, and the next tier is tried: a whole week from the fine tier is
             better than half a week from the raw tier. */
          if (touchesRecord(keys[i])) { ok = false; break; }
          continue;
        }
        var g = grids[keys[i]];
        /* The files must share one interval: a chart joined from two intervals
           changes its detail abruptly where they meet. */
        if (g && interval && g !== interval) { ok = false; break; }
        if (g) interval = g;
        present.push(keys[i]);
      }
      if (!ok || !present.length) continue;
      if (interval && (to - from) / interval > MAX_POINTS) continue;

      return {
        interval: interval,
        names: present.map(function (k) { return tier.name(group, k); })
      };
    }
    return null;
  }

  var daynightCache = new Map();

  function loadDayNight(year) {
    if (daynightCache.has(year)) return Promise.resolve(daynightCache.get(year));
    /* No request for a year before the first archive record. */
    if (archiveIndex && archiveIndex.first
        && year < new Date(archiveIndex.first * 1000).getFullYear()) {
      daynightCache.set(year, null);
      return Promise.resolve(null);
    }
    return fetch(DATA_DIR + '/archive/daynight-' + year + '.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { daynightCache.set(year, j); return j; })
      .catch(function () { daynightCache.set(year, null); return null; });
  }

  /* Returns a promise of the `daynight` data (see nightAreas) for a time span of up
     to 9 days, from the daynight files of `years`, or of null. On a longer time span
     a night is one or two pixels wide and the shading blurs into grey. Seasons draws
     no night shading on its month and year images either. */
  function nightForWindow(from, to, years) {
    if ((to - from) > 9 * 86400) return Promise.resolve(null);
    return Promise.all(years.map(loadDayNight)).then(function (files) {
      var all = [];
      var bands = [];
      var first = null;
      files.filter(Boolean).forEach(function (f) {
        if (first === null) {
          /* Day and night alternate, so the number of transitions before `from`
             says whether `from` is in the day or in the night. */
          var before = f.transitions.filter(function (t) { return t <= from; }).length;
          var startState = f.first === 'day' ? 'day' : 'night';
          first = (before % 2 === 0) ? startState : (startState === 'day' ? 'night' : 'day');
        }
        all = all.concat(f.transitions.filter(function (t) { return t > from && t < to; }));
        /* The twilight times go with the transitions, so that the nights fade over
           the real length of a twilight and not over the default of 1800 seconds. */
        bands = bands.concat((f.twilight || []).filter(function (b) {
          return b.to > from && b.from < to;
        }));
      });
      if (!all.length) return null;
      all.sort(function (a, b) { return a - b; });
      bands.sort(function (a, b) { return a.from - b.from; });
      return { first: first, transitions: all, twilight: bands };
    });
  }

  /* Returns a promise of the plot data for one time span of plot group `group`,
     joined from the archive files that the time span touches, or of null. */
  function windowFromArchive(group, from, to) {
    var pick = filesFor(group, from, to);
    if (!pick) return Promise.resolve(null);

    var years = [];
    for (var y = new Date(from * 1000).getFullYear();
         y <= new Date(to * 1000).getFullYear(); y++) years.push(y);

    return Promise.all([
      Promise.all(pick.names.map(loadArchiveFile)),
      nightForWindow(from, to, years)
    ]).then(function (both) {
      var files = both[0];
      var daynight = both[1];
      return (function () {
        var present = files.filter(Boolean);
        if (!present.length) return null;

        var interval = present[0].interval;
        var start = Math.floor(from / interval) * interval;
        var slots = Math.ceil((to - start) / interval);
        if (slots < 2) return null;

        /* Besides `values`, a series can carry arrays of the same length: the wind
           vector components, the wind directions, and `min` and `max` for the types
           whose average hides the extremes. The extra arrays are joined like
           `values`. */
        var EXTRA = ['vector_x', 'vector_y', 'directions', 'min', 'max'];

        var template = present[0];
        var series = template.series.map(function (s) {
          var out = {
            obs_type: s.obs_type,
            label: s.label,
            color: s.color,
            plot_type: s.plot_type || 'line',
            time: [],
            values: new Array(slots).fill(null)
          };
          if (s.vector_rotate !== undefined) out.vector_rotate = s.vector_rotate;
          /* barWidthPx needs `aggregate_interval` for a bar that totals more than
             one interval. */
          if (s.aggregate_interval) out.aggregate_interval = s.aggregate_interval;
          EXTRA.forEach(function (key) {
            if (s[key]) out[key] = new Array(slots).fill(null);
          });
          return out;
        });

        present.forEach(function (file) {
          file.series.forEach(function (s, si) {
            if (si >= series.length) return;
            for (var i = 0; i < s.values.length; i++) {
              var ts = file.start + i * file.interval;
              var slot = Math.round((ts - start) / interval);
              if (slot < 0 || slot >= slots) continue;
              if (s.values[i] !== null) series[si].values[slot] = s.values[i];
              for (var e = 0; e < EXTRA.length; e++) {
                var key = EXTRA[e];
                if (s[key] && series[si][key] && s[key][i] !== null
                    && s[key][i] !== undefined) {
                  series[si][key][slot] = s[key][i];
                }
              }
            }
          });
        });

        var times = new Array(slots);
        for (var k = 0; k < slots; k++) times[k] = start + k * interval;
        series.forEach(function (s) { s.time = times; });

        /* The joined y axis covers the widest range of the files' axes, and takes
           the step of the first file that has one. */
        var yscale = null;
        present.forEach(function (file) {
          if (!file.yscale) return;
          if (!yscale) { yscale = file.yscale.slice(); return; }
          if (file.yscale[0] !== null && (yscale[0] === null || file.yscale[0] < yscale[0])) {
            yscale[0] = file.yscale[0];
          }
          if (file.yscale[1] !== null && (yscale[1] === null || file.yscale[1] > yscale[1])) {
            yscale[1] = file.yscale[1];
          }
          if (yscale[2] === null) yscale[2] = file.yscale[2];
        });

        var out = {
          name: group,
          start: start,
          stop: start + slots * interval,
          unit: template.unit,
          unit_label: template.unit_label,
          aggregate_interval: interval,
          series: series
        };
        if (yscale) out.yscale = yscale;
        if (daynight) out.daynight = daynight;
        return out;
      })();
    });
  }

  function loadManifest() {
    if (manifest) return Promise.resolve(manifest);
    return fetch(DATA_DIR + '/index.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (json) {
        manifest = json || {};
        adoptSpans(manifest);
        if (manifest.units) unitChoices = manifest.units;
        return manifest;
      })
      .catch(function () { manifest = {}; return manifest; });
  }

  /* A chart card fetches and draws its chart when the chart card comes within
     300 px of the viewport. On a phone the page then fetches one or two files on
     load instead of twenty. */
  var lazyObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var card = entry.target;
      lazyObserver.unobserve(card);
      hydrate(card);
    });
  }, { rootMargin: '300px 0px' });

  function hydrate(card) {
    if (card.dataset.loaded) return;
    card.dataset.loaded = '1';

    var period = card.dataset.period;
    var empty = '<p class="chart-empty">' + escapeHtml(CFG.text.noData || 'No data') + '</p>';

    chartSource(card).then(function (meta) {
      if (!meta || !meta.series || !meta.series.length) {
        card.querySelector('.chart-host').innerHTML = empty;
        return;
      }
      var any = meta.series.some(function (s) {
        return s.values.some(function (v) { return v !== null; });
      });
      if (!any) {
        card.querySelector('.chart-host').innerHTML = empty;
        return;
      }
      renderChart(card, meta, period);
    });
  }

  var currentPeriod = null;

  /* ------------------------------------------------------------ shared links */

  /* Writes the view into the URL hash, e.g., #week for the live view or
     #month/2026-07 for July 2026, so that the Share button can copy a link to the
     view. A chart drawn in the browser has no file of its own to link to. The hash
     names a calendar unit rather than an offset such as three weeks back, so that
     the link shows the same days next week. */
  function writeLocation(period) {
    var hash = '#' + period;
    if (anchor !== null) {
      /* Name the calendar unit, not an instant inside it: #month/2026-07, not
         #month/2026-07-13. */
      var d = new Date(calendarWindow(period, anchor).from * 1000);
      var y = d.getFullYear();
      var mm = String(d.getMonth() + 1).padStart(2, '0');
      var dd = String(d.getDate()).padStart(2, '0');
      hash += '/' + (period === 'year' ? y
        : period === 'month' ? y + '-' + mm
        : y + '-' + mm + '-' + dd);
    }
    if (window.location.hash !== hash) {
      history.replaceState(null, '', window.location.pathname + window.location.search + hash);
    }
  }

  function readLocation() {
    var hash = window.location.hash.replace(/^#/, '');
    if (!hash) return null;
    var parts = hash.split('/');
    var period = parts[0];
    if ((CFG.periods || []).indexOf(period) < 0) return null;

    if (!parts[1]) return { period: period, anchor: null };

    /* 2026, 2026-07 and 2026-07-13 are accepted for any time span, and select the
       calendar unit that holds the date, so that a link typed by hand works too. */
    var m = parts[1].match(/^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?(?:T\d{1,2})?$/);
    if (!m) {
      /* #week/-3 means three weeks back from the newest archive record. */
      var n = parseInt(parts[1].replace(/^-/, ''), 10);
      if (!isNaN(n) && n > 0) {
        var span = PERIOD_SECONDS[period] || PERIOD_SECONDS.day;
        return { period: period, anchor: dataTs() - n * span };
      }
      return { period: period, anchor: null };
    }

    var d = new Date(+m[1], m[2] ? +m[2] - 1 : 0, m[3] ? +m[3] : 1, 12, 0, 0);
    var ts = Math.floor(d.getTime() / 1000);
    /* A calendar unit that has not ended yet is the live view. */
    var unit = calendarWindow(period, ts);
    return { period: period, anchor: unit.to > dataTs() ? null : ts };
  }

  /* After a change of time span, scrolls the page up to the first chart if the
     reader had scrolled past the first chart, because all charts have been
     replaced. A reader above the first chart is not moved. showPeriod calls
     backToFirstChart once the chart cards are in place; before that, the page is
     too short to scroll. The head of the history panel (`.history-head`) is sticky,
     so the first chart goes just below the head. */
  function backToFirstChart(container) {
    var head = document.querySelector('.history-head');
    var stuck = head ? head.offsetHeight : 0;
    var top = window.scrollY + container.getBoundingClientRect().top - stuck - 8;
    if (window.scrollY > top + 4) {
      window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
    }
  }

  function showPeriod(period, newAnchor) {
    var container = document.getElementById('charts');
    if (!container) return;

    if (newAnchor !== undefined) anchor = newAnchor;
    if (period !== currentPeriod && newAnchor === undefined) {
      anchor = null;                               // live view of the new time span
    }
    currentPeriod = period;

    clearCharts();
    container.setAttribute('aria-busy', 'true');

    Promise.all([loadManifest(), loadArchiveIndex()]).then(function (res) {
      var ai = res[1];
      var groups = CFG.plotGroups || [];
      /* The time span on screen is measured once data/index.json has loaded,
         because adoptSpans then replaces the defaults in PERIOD_SECONDS with the
         `time_length` of skin.conf. Measured earlier, the first Year chart after a
         page load would take the default of 365 days instead of the 365.25 days of
         '1y'. */
      var win = currentWindow(period);
      var from = win.from, to = win.to;

      /* The chart cards follow the order of `plot_groups` in skin.conf, not the
         order of data/index.json. */
      var wanted = groups.map(function (g) {
        var archived = (ai.groups || []).find(function (p) { return p.name === g; });
        /* data/archive/index.json lists every group with readings anywhere in the
           archive. A sensor that stopped three years ago is still listed, and its
           chart would be empty on every time span since. So a chart card is made
           only where filesFor finds files for this time span. */
        if (!archived || !filesFor(g, from, to)) return null;
        return { group: g, title: archived.title };
      }).filter(Boolean);

      container.innerHTML = '';
      updateRange(period, from, to, ai);

      if (!wanted.length) {
        container.innerHTML = '<p class="chart-empty">'
          + escapeHtml(CFG.text.noData || 'No data') + '</p>';
        container.setAttribute('aria-busy', 'false');
        return;
      }

      wanted.forEach(function (entry) {
        var card = document.createElement('section');
        card.className = 'chart-card';
        card.dataset.group = entry.group;
        card.dataset.period = period;
        card.dataset.from = from;
        card.dataset.to = to;
        card.innerHTML =
          '<div class="chart-head">'
          + '<h3 class="chart-title chart-legend">' + escapeHtml(entry.title) + '</h3>'
          + '<div class="chart-actions"></div>'
          + '</div>'
          + '<div class="chart-host"><div class="chart-skeleton"></div></div>'
          + '<details class="chart-data"><summary>'
          + escapeHtml(CFG.text.showData || 'Show data')
          + '</summary><div class="scroller-host"></div></details>';
        container.appendChild(card);
        lazyObserver.observe(card);
      });

      container.setAttribute('aria-busy', 'false');
      backToFirstChart(container);
    });

    /* Only links to this page's own charts are marked. On any other page than the
       front page, the navigation's time span links go to 'index.html#week' and the
       like, i.e., to the charts of the front page. */
    document.querySelectorAll('a[data-period][href^="#"]').forEach(function (a) {
      if (a.dataset.period === period) a.setAttribute('aria-current', 'true');
      else a.removeAttribute('aria-current');
    });

    remember('period', period);
    writeLocation(period);
    showSpanOnCards(period);
  }

  /* Shows the current conditions for the time span `period`. On Day each tile shows
     the current reading, with the day's low and high. On Week, Month and Year a tile
     shows the mean over that time span with its low and high, or the total for a
     type that is summed, such as rain.

     The time span is always the calendar unit that holds the newest archive record,
     even when the charts have been stepped back, because current.inc writes figures
     only for that calendar unit, into `data-spans`. current.inc describes the format
     of `data-spans`. */
  function showSpanOnCards(period) {
    var panel = document.querySelector('[data-live-panel="current"]');
    if (!panel) return;
    var daily = period === 'day' || !period;
    panel.dataset.span = period || 'day';
    /* `data-anchored` says that the charts show a time span in the past, which the
       tiles do not follow, and horizon.css then hides the Live badges. */
    if (anchor === null) delete panel.dataset.anchored;
    else panel.dataset.anchored = '';

    panel.querySelectorAll('[data-spans]').forEach(function (el) {
      var held;
      try {
        held = JSON.parse(el.dataset.spans || '{}');
      } catch (e) {
        return;
      }

      /* Where `data-spans` has no entry for this time span, the tile shows the
         day's figures. */
      var found = daily ? null : (held[period] || null);
      keepDay(el);
      if (found) setSpanValue(el, found.v, found.t);
      else setSpanValue(el, el.dataset.dayValue, el.dataset.dayText);

      /* "Rain Today" is wrong over any other time span, so the rain tile carries
         both headings, in `data-label-day` and `data-label-span`. */
      var tile = el.closest('.tile');
      var heading = tile && tile.querySelector('[data-label-span]');
      if (heading) {
        heading.textContent = daily
          ? heading.dataset.labelDay
          : heading.dataset.labelSpan;
      }

      /* Over a longer time span the wind tile shows the compass point of the
         vector averaged direction. */
      var vane = tile && tile.querySelector('.wind-dir');
      if (vane) {
        if (vane.dataset.asWritten === undefined) {
          vane.dataset.asWritten = vane.textContent;
        }
        vane.textContent = (found && found.dir) || vane.dataset.asWritten;
      }

      /* Where the entry has no `lo` and `hi`, as for a total, the low and high
         under the reading (.tile-range) are hidden: the day's low and high would be
         wrong beside that total. */
      var range = tile ? tile.querySelector('.tile-range') : null;
      if (!range) return;
      var ends = !found || (found.lo !== undefined && found.hi !== undefined);
      range.hidden = !ends;
      if (!ends) return;
      [['lo', 'lot'], ['hi', 'hit']].forEach(function (end) {
        var cell = range.querySelector('[data-range="' + end[0] + '"]');
        if (!cell) return;
        keepDay(cell);
        if (found) setSpanValue(cell, found[end[0]], found[end[1]]);
        else setSpanValue(cell, cell.dataset.dayValue, cell.dataset.dayText);
      });
    });

    applyUnitsToPanels(panel);
  }

  /* Stores the day's figure of `el` in `data-day-value` and `data-day-text`, once,
     for showSpanOnCards to show again on Day. From then on the live update keeps
     both current. The text comes from `data-as-written` where present, because an
     element whose reading is converted shows another unit. */
  function keepDay(el) {
    if (el.dataset.dayValue === undefined) {
      el.dataset.dayValue = el.dataset.value || '';
    }
    if (el.dataset.dayText === undefined) {
      var shown = el.querySelector('[data-unit-value]') || el;
      el.dataset.dayText = el.dataset.asWritten !== undefined
        ? el.dataset.asWritten : shown.textContent.trim();
    }
  }

  /* Shows one figure in `el`: `text` as the report formatted it, and `value`, the
     number for the unit conversion. `data-as-written` gets `text` as well, because
     applyUnitsToPanels shows `data-as-written` when the reader chooses Default
     again. A stale `data-as-written` would bring back another time span's figure. */
  function setSpanValue(el, value, text) {
    el.dataset.value = value;
    el.dataset.asWritten = text;
    (el.querySelector('[data-unit-value]') || el).textContent = text;
  }

  /* Returns the name of the calendar unit on screen, e.g., "Tuesday, 18 August 2026"
     for a day, the first and last date for a week, "July 2026" for a month and
     "2025" for a year. */
  function unitLabel(period, from, to) {
    var start = new Date(from * 1000);
    var end = new Date((to - 1) * 1000);

    /* Below 34rem the long form, e.g., "Sunday, 23 August 2026", is wider than the
       date button between the arrows, whose width horizon.css fixes: at 390px the
       button is 148px wide, and the long form needs 181px. */
    var roomy = window.matchMedia('(min-width: 34rem)').matches;

    if (period === 'day') {
      return start.toLocaleDateString(LOCALE, roomy
        ? { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }
        : { weekday: 'short', day: 'numeric', month: 'short' });
    }
    if (period === 'week') {
      var opts = roomy ? { day: 'numeric', month: 'short', year: 'numeric' }
                       : { day: 'numeric', month: 'short' };
      /* formatRange() writes a range of dates the way the page's language does.
         Two dates joined with a dash, the fallback below, have the wrong
         punctuation in most languages. */
      try {
        return new Intl.DateTimeFormat(LOCALE, opts).formatRange(start, end);
      } catch (e) {
        return start.toLocaleDateString(LOCALE, opts) + ' – '
          + end.toLocaleDateString(LOCALE, opts);
      }
    }
    if (period === 'month') {
      return start.toLocaleDateString(LOCALE,
        roomy ? { month: 'long', year: 'numeric' } : { month: 'short', year: 'numeric' });
    }
    return String(start.getFullYear());
  }

  /* The live view is labelled "Now" only while the newest archive record falls in
     the same calendar unit as the browser's clock. Otherwise, e.g., on a Monday with
     the newest archive record from Sunday, "Now" would stand for Sunday, and a step
     back to Saturday would look like a skipped day. The label then names the
     calendar unit. */
  function liveLabel(period) {
    var d = calendarWindow(period, dataTs());
    return d.from === calendarWindow(period, nowTs()).from
      ? (CFG.text.now || 'Now')
      : unitLabel(period, d.from, d.to);
  }

  /* Labels the time span on screen, and disables an arrow that would leave the
     archive. */
  function updateRange(period, from, to, ai) {
    var label = document.getElementById('range-label');
    var back = document.getElementById('range-back');
    var fwd = document.getElementById('range-fwd');
    var now = document.getElementById('range-now');
    if (!label) return;

    label.textContent = anchor === null
      ? liveLabel(period)
      : unitLabel(period, from, to);

    if (fwd) fwd.disabled = anchor === null;
    if (now) now.hidden = anchor === null;

    if (back && ai && ai.first) {
      back.disabled = from <= ai.first;
    }

    /* An open calendar is drawn again for the new time span. */
    drawCalendar();
  }

  /* Returns the date of `ts` as YYYY-MM-DD in the browser's time zone.
     toISOString() would give the date in UTC, which in any other time zone is a
     different date for part of every day. */
  function isoDate(ts) {
    var d = new Date(ts * 1000);
    return d.getFullYear()
      + '-' + String(d.getMonth() + 1).padStart(2, '0')
      + '-' + String(d.getDate()).padStart(2, '0');
  }

  /* Steps the charts one calendar unit back (`direction` < 0) or forward. Back from
     the live view goes to the last calendar unit that has ended. Forward into the
     calendar unit that holds the newest archive record returns to the live view. */
  function step(direction) {
    var here = calendarWindow(currentPeriod, anchor === null ? dataTs() : anchor);
    var target = direction < 0 ? here.from - 1 : here.to + 1;
    /* Test the end of the target's calendar unit against dataTs(), as readLocation
       does, and not the target itself. Testing the target would stop a step forward
       on the running calendar unit as a fixed time span, and a second step would be
       needed to reach the live view. */
    var unit = calendarWindow(currentPeriod, target);
    showPeriod(currentPeriod, unit.to > dataTs() ? null : target);
  }

  /* ------------------------------------------------------------- calendar */

  /* The calendar opens from the date between the arrows (#range-label) and jumps to
     any date, while the arrows move one calendar unit at a time. The calendar is
     drawn here rather than with <input type="date">, whose drop-down cannot be
     styled and shows as a white box in the browser's own fonts on a dark page. The
     drop-down also offers every date, while this calendar disables the dates before
     the first archive record and after the newest one. */

  var calShown = null;                       // the first day of the month shown

  function setupCalendar() {
    var button = document.getElementById('range-label');
    var panel = document.getElementById('range-cal');
    if (!button || !panel) return;

    button.addEventListener('click', function (e) {
      e.stopPropagation();
      if (panel.hidden) openCalendar(); else closeCalendar();
    });

    panel.addEventListener('click', function (e) {
      e.stopPropagation();
      var step = e.target.closest('[data-cal-step]');
      if (step) {
        calShown = new Date(calShown.getFullYear(),
                            calShown.getMonth() + Number(step.dataset.calStep), 1);
        drawCalendar();
        return;
      }
      var day = e.target.closest('[data-cal-day]');
      if (!day || day.disabled) return;
      /* Take midday of the chosen date, not midnight: midnight moved back by the
         hour of daylight saving time falls on the day before. */
      var parts = day.dataset.calDay.split('-').map(Number);
      var ts = Math.floor(new Date(parts[0], parts[1] - 1, parts[2], 12).getTime() / 1000);
      var unit = calendarWindow(currentPeriod, ts);
      closeCalendar();
      showPeriod(currentPeriod, unit.to > dataTs() ? null : ts);
    });

    /* A click outside the calendar, or Escape, closes the calendar. */
    document.addEventListener('click', function () {
      if (!panel.hidden) closeCalendar();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) { closeCalendar(); button.focus(); }
    });
  }

  function openCalendar() {
    var panel = document.getElementById('range-cal');
    var at = new Date((anchor === null ? dataTs() : anchor) * 1000);
    calShown = new Date(at.getFullYear(), at.getMonth(), 1);
    panel.hidden = false;
    document.getElementById('range-label').setAttribute('aria-expanded', 'true');
    drawCalendar();
  }

  function closeCalendar() {
    var panel = document.getElementById('range-cal');
    if (!panel) return;
    panel.hidden = true;
    document.getElementById('range-label').setAttribute('aria-expanded', 'false');
  }

  /* Draws the month `calShown` into the calendar. The week starts on `week_start`
     of weewx.conf, and the names of the days are in the page's language. */
  function drawCalendar() {
    var panel = document.getElementById('range-cal');
    if (!panel || panel.hidden) return;

    var ai = archiveIndex || {};
    var first = ai.first ? new Date(ai.first * 1000) : null;
    var last = new Date(dataTs() * 1000);
    var selected = anchor === null ? null : isoDate(anchor);
    var today = isoDate(dataTs());

    var year = calShown.getFullYear(), month = calShown.getMonth();
    var startDow = (CFG.weekStart === undefined ? 0 : +CFG.weekStart);
    var jsStart = (startDow + 1) % 7;                    // JS counts Sunday as 0

    /* 7 January 2024 was a Sunday, so the dates from there give the names of the
       days in order, in the page's language. */
    var names = [];
    for (var i = 0; i < 7; i++) {
      var d = new Date(2024, 0, 7 + ((jsStart + i) % 7));
      names.push(d.toLocaleDateString(LOCALE, { weekday: 'short' }));
    }

    var firstOfMonth = new Date(year, month, 1);
    var lead = (firstOfMonth.getDay() - jsStart + 7) % 7;
    var cells = [];
    for (var n = 0; n < 42; n++) {
      var day = new Date(year, month, 1 - lead + n);
      var iso = isoDate(Math.floor(day.getTime() / 1000) + 43200);
      var outside = day.getMonth() !== month;
      var tooEarly = first && day < new Date(first.getFullYear(), first.getMonth(), first.getDate());
      var tooLate = day > new Date(last.getFullYear(), last.getMonth(), last.getDate());
      var classes = ['cal-day'];
      if (outside) classes.push('cal-other');
      if (iso === selected) classes.push('cal-selected');
      if (iso === today) classes.push('cal-today');
      cells.push('<button type="button" class="' + classes.join(' ') + '"'
        + ' data-cal-day="' + iso + '"'
        + (tooEarly || tooLate ? ' disabled' : '')
        + (iso === selected ? ' aria-current="date"' : '')
        + '>' + day.getDate() + '</button>');
      /* Stop after the week that holds the last day of the month. */
      if (n % 7 === 6 && new Date(year, month, 1 - lead + n + 1).getMonth() !== month) break;
    }

    var title = calShown.toLocaleDateString(LOCALE, { month: 'long', year: 'numeric' });
    panel.innerHTML =
      '<div class="cal-head">'
      + '<button type="button" class="cal-step" data-cal-step="-1"'
      + ' aria-label="' + escapeHtml(CFG.text.earlier || 'Earlier') + '">'
      + '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg></button>'
      + '<span class="cal-title">' + escapeHtml(title) + '</span>'
      + '<button type="button" class="cal-step" data-cal-step="1"'
      + ' aria-label="' + escapeHtml(CFG.text.later || 'Later') + '">'
      + '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg></button>'
      + '</div>'
      + '<div class="cal-grid">'
      + names.map(function (x) { return '<span class="cal-dow">' + escapeHtml(x) + '</span>'; }).join('')
      + cells.join('')
      + '</div>';
  }

  function setupRangeNav() {
    var back = document.getElementById('range-back');
    var fwd = document.getElementById('range-fwd');
    var now = document.getElementById('range-now');
    if (back) back.addEventListener('click', function () { step(-1); });
    if (fwd) fwd.addEventListener('click', function () {
      if (anchor !== null) step(1);
    });
    if (now) now.addEventListener('click', function () { showPeriod(currentPeriod, null); });

    setupCalendar();

    var share = document.getElementById('range-share');
    if (share) {
      share.addEventListener('click', function () {
        var url = window.location.href;
        var done = function () {
          var was = share.textContent;
          share.textContent = CFG.text.linkCopied || 'Link copied';
          setTimeout(function () { share.textContent = was; }, 1800);
        };
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(url).then(done, function () { prompt(url); });
        } else {
          /* The clipboard API needs a secure context, i.e., HTTPS or localhost, and
             many stations are served over plain HTTP, so the link is shown for the
             reader to copy. */
          window.prompt(CFG.text.copyLink || 'Copy this link:', url);
        }
      });
    }

    /* With `#charts` focused, the left and right arrow keys step back and forward. */
    var container = document.getElementById('charts');
    if (container) {
      container.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft') { step(-1); e.preventDefault(); }
        if (e.key === 'ArrowRight' && anchor !== null) { step(1); e.preventDefault(); }
      });
    }
  }

  function setupPeriods() {
    var container = document.getElementById('charts');
    if (!container) return;

    /* Opening a data table builds the table where it is missing or stale. */
    container.addEventListener('toggle', function (e) {
      if (!e.target.matches('details.chart-data') || !e.target.open) return;
      var card = e.target.closest('.chart-card');
      if (!card) return;
      /* A chart card not yet scrolled into view has no chart and no table yet. */
      if (!card.dataset.loaded) {
        hydrate(card);
        return;
      }
      /* updateChart sets `data-stale` where new data or another unit arrived while
         the table was closed. */
      if (e.target.dataset.stale) {
        var entry = charts.find(function (c) {
          return c.host === card.querySelector('.chart-host');
        });
        if (entry) {
          e.target.querySelector('.scroller-host').innerHTML =
            renderTable(entry.meta, digitsFor(entry.meta.series));
        }
        delete e.target.dataset.stale;
      }
    }, true);
    setupRangeNav();

    /* A time span in the URL hash takes precedence over the one in localStorage. */
    var linked = readLocation();
    if (linked) {
      currentPeriod = linked.period;
      showPeriod(linked.period, linked.anchor);
    } else {
      var start = recall('period', (CFG.periods || ['day'])[0]);
      if ((CFG.periods || []).indexOf(start) < 0) start = (CFG.periods || ['day'])[0];
      showPeriod(start, null);
    }

    /* The time span links are bare hashes such as '#week', written by nav.inc on
       the front page and by history.inc on the other pages with charts, so
       following one fires hashchange. The browser's back and forward buttons fire
       hashchange too, as does a link pasted into the tab. */
    window.addEventListener('hashchange', function () {
      var loc = readLocation();
      if (loc && (loc.period !== currentPeriod || loc.anchor !== anchor)) {
        currentPeriod = loc.period;
        showPeriod(loc.period, loc.anchor);
      }
    });
  }

  /* ------------------------------------------------------- temperature colour */

  /* horizon.css defines nine colours, --warm-0 to --warm-8, one per temperature
     band, and current.inc sets the band edges. WARM_AT holds the middle of each band
     in degree_C, where the band's colour applies exactly. The colours are read from
     the stylesheet, so that the page has one palette. */
  var WARM_AT = [-15, -5, 2.5, 8.5, 15, 20.5, 25.5, 30.5, 36];

  function warmStops() {
    var css = getComputedStyle(document.documentElement);
    return WARM_AT.map(function (c, i) {
      return { c: c, rgb: parseColour(css.getPropertyValue('--warm-' + i).trim()) };
    }).filter(function (s) { return s.rgb; });
  }

  function parseColour(text) {
    if (!text) return null;
    var hex = /^#([0-9a-f]{6})$/i.exec(text);
    if (hex) {
      var n = parseInt(hex[1], 16);
      return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    }
    var rgb = /rgba?\(([^)]+)\)/.exec(text);
    if (rgb) {
      var parts = rgb[1].split(/[,\s/]+/).map(parseFloat);
      return [parts[0], parts[1], parts[2]];
    }
    return null;
  }

  /* Returns the colour of the temperature `celsius`, mixed from the colours of the
     two band middles it falls between. Two readings a degree apart then differ by a
     shade, not by a whole band. */
  function tempColour(celsius, stops) {
    if (!stops.length) return null;
    if (celsius <= stops[0].c) return rgbText(stops[0].rgb);
    for (var i = 1; i < stops.length; i++) {
      if (celsius <= stops[i].c) {
        var a = stops[i - 1], b = stops[i];
        var t = (celsius - a.c) / (b.c - a.c);
        return rgbText([0, 1, 2].map(function (k) {
          return Math.round(a.rgb[k] + (b.rgb[k] - a.rgb[k]) * t);
        }));
      }
    }
    return rgbText(stops[stops.length - 1].rgb);
  }

  function rgbText(rgb) {
    return 'rgb(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ')';
  }

  /* --------------------------------------------------------- panel refresh */

  /* On a new archive record, fetches the page again and replaces each element with
     `data-live-panel` by its new version. current.json carries only the current
     readings. Without the page fetch, the day's low and high, the trend arrows, the
     almanac, the statistics and the uptime would keep the values of the first page
     load, and a tile could show a reading above the day's high.

     An element whose content must survive a new archive record has no
     `data-live-panel`: the history panel with its charts, the imagery panels with
     the Google Maps object, and the report panel with the report the reader picked.
     Each of these is updated by its own code: refreshCharts, refreshImages and the
     script of the reports page. The climate panels do have `data-live-panel`, and
     climate.js draws their charts again on 'horizon:panels'. */
  var pageFetch = false;

  function refreshPanels() {
    var slots = document.querySelectorAll('[data-live-panel]');
    if (!slots.length || pageFetch) return;
    pageFetch = true;

    fetch(location.pathname + location.search, { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        pageFetch = false;
        if (!html) return;
        var fresh = new DOMParser().parseFromString(html, 'text/html');
        var touched = false;
        slots.forEach(function (old) {
          if (!old.parentNode) return;
          var next = fresh.querySelector('[data-live-panel="'
                                         + old.dataset.livePanel + '"]');
          if (!next || next.outerHTML === old.outerHTML) return;
          var fit = document.importNode(next, true);
          old.parentNode.replaceChild(fit, old);
          carryOver(old, fit);
          touched = true;
        });
        if (touched) {
          /* WeeWX wrote the new elements for Day and in the report unit system, so
             the time span and the chosen unit system are applied again. */
          showSpanOnCards(currentPeriod || 'day');
          applyUnitsToPanels();
          /* 'horizon:panels' tells other scripts, e.g., climate.js, that the new
             elements are in the document: a drawing in a replaced panel is gone, and
             so is any listener on an element inside one. 'horizon:update' fires
             earlier, when the new archive record arrives. */
          document.dispatchEvent(new CustomEvent('horizon:panels'));
        }
      })
      .catch(function () { pageFetch = false; });
  }

  /* Copies the sideways scroll position of each `.table-scroll` from the panel `old`
     to its replacement `fit`. refreshPanels calls carryOver after the swap, since an
     element outside the document cannot be scrolled. */
  function carryOver(old, fit) {
    var was = old.querySelectorAll('.table-scroll');
    var now = fit.querySelectorAll('.table-scroll');
    for (var i = 0; i < was.length && i < now.length; i++) {
      now[i].scrollLeft = was[i].scrollLeft;
    }
  }

  /* Images with `data-live-src`, e.g., radar and satellite images from other sites,
     have cache headers of their own, and the browser may show the morning's image
     all afternoon. A new query string on each archive record makes the browser
     fetch each image again. */
  function refreshImages(version) {
    document.querySelectorAll('img[data-live-src]').forEach(function (img) {
      var base = img.dataset.liveSrc;
      img.src = base + (base.indexOf('?') < 0 ? '?' : '&') + 'v=' + version;
    });
  }

  /* ------------------------------------------------------------ live update */

  function setupLiveUpdate() {
    var seconds = parseInt(CFG.refreshInterval, 10);
    if (!seconds || seconds < 5) return;

    var stamp = document.querySelector('[data-live="dateTime"]');
    var seen = String((stamp && stamp.dataset.raw) || CFG.generated || '');
    /* The current conditions and the time in the masthead are marked stale
       (`is-stale`) when no new archive record has come for 2.5 archive intervals.
       The wait is counted in live updates, not read from the clock, so that a
       station whose clock is a few minutes off is not marked stale. current.json
       gives the archive interval in minutes as `interval`; until the first answer,
       600 seconds is assumed. */
    var quiet = 0;
    var patience = Math.ceil(600 / seconds);
    var busy = false;

    function tick() {
      if (busy) return;
      busy = true;
      fetch('current.json', { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          busy = false;
          if (!data) return;

          var minutes = parseFloat(data.interval);
          if (minutes > 0) {
            patience = Math.max(3, Math.ceil(minutes * 60 * 2.5 / seconds));
          }

          /* On every live update, each element with `data-live` shows its field
             from current.json. current.json carries each reading as text, number
             and unit (see current.json.tmpl), and the number and unit go on the
             element for applyUnitsToPanels. */
          document.querySelectorAll('[data-live]').forEach(function (el) {
            var key = el.dataset.live;
            if (data[key] === undefined || data[key] === null) return;
            var text = String(data[key]);
            var value = data[key + '_v'];
            var known = value !== undefined && value !== null;

            /* On Week, Month or Year the tile shows that time span's figure, and the
               new reading is only stored, for showSpanOnCards to show on Day. */
            if (el.dataset.spans !== undefined) {
              el.dataset.dayText = text;
              if (known) el.dataset.dayValue = value;
              var tiles = el.closest('[data-span]');
              if (tiles && tiles.dataset.span !== 'day') return;
            }

            (el.querySelector('[data-unit-value]') || el).textContent = text;
            delete el.dataset.asWritten;
            if (known) {
              el.dataset.value = value;
              if (data[key + '_u']) el.dataset.unit = data[key + '_u'];
            }
          });

          /* The new text is in the report unit system. */
          applyUnitsToPanels();

          if (!data.dateTime_raw || String(data.dateTime_raw) === seen) {
            if (++quiet >= patience) markStale(true);
            return;
          }

          /* A changed `dateTime_raw` means a new archive record. [[[current_json]]]
             comes last in [[ToDate]] in skin.conf, so the Cheetah generator has
             already written the new pages, and refreshPanels finds the new panels.
             The JSON generator runs after the Cheetah generator, so refreshCharts
             may still get the JSON files of the previous archive record. */
          quiet = 0;
          markStale(false);
          seen = String(data.dateTime_raw);
          if (stamp) stamp.dataset.raw = data.dateTime_raw;
          refreshPanels();
          refreshImages(seen);
          refreshCharts();

          /* 'horizon:update' tells other scripts, e.g., the one on the reports page,
             that there is a new archive record. */
          document.dispatchEvent(new CustomEvent('horizon:update', {
            detail: { dateTime: data.dateTime_raw }
          }));
        })
        .catch(function () {
          busy = false;
          if (++quiet >= patience) markStale(true);
        });
    }

    function markStale(stale) {
      var tiles = document.querySelector('[data-live-panel="current"]');
      if (tiles) tiles.classList.toggle('is-stale', stale);
      if (stamp) stamp.classList.toggle('is-stale', stale);
    }

    /* `data-polling` on <html> makes horizon.css show the Live badges. A page
       without live updates, or without JavaScript, shows the readings WeeWX wrote,
       and no badge. */
    document.documentElement.dataset.polling = '';
    setInterval(tick, seconds * 1000);

    /* Browsers slow down timers in a background tab, so a tab brought back to the
       front runs a live update at once instead of showing old readings. */
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) tick();
    });
  }

  /* ----------------------------------------------------------------- start */

  function init() {
    CFG.text = CFG.text || {};
    setupNavToggle();
    setupThemeToggle();
    setupToTop();
    setupUnitPicker();
    setupPeriods();
    setupLiveUpdate();
  }

  /* init() runs at once, not on DOMContentLoaded: scripts.inc loads horizon.js at
     the end of <body>, after all markup, and a script named in `custom_js`, loaded
     after horizon.js, finds the page set up. */
  init();
})();
