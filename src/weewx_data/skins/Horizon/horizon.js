/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 */

(function () {
  'use strict';

  var CFG = window.HORIZON || {};
  var DATA_DIR = CFG.dataDir || 'data';
  var STORE = 'weewx.horizon.';

  /* ------------------------------------------------------------- storage */

  function remember(key, value) {
    try { localStorage.setItem(STORE + key, value); } catch (e) { /* private mode */ }
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
      /* The tooltip is a panel over the page, so it takes the page's own panel
         colours. Hard-coded white here is a white box on a dark page. */
      surface: s.getPropertyValue('--surface').trim() || '#ffffff',
      border: s.getPropertyValue('--border').trim()
              || s.getPropertyValue('--chart-grid').trim() || '#e3eaf1',
      muted: s.getPropertyValue('--ink-muted').trim() || '#5c7183'
    };
  }

  /* The menu the masthead controls fold into on a phone. The stylesheet decides
     whether there is a button at all; this only opens and closes it. */
  function setupNavToggle() {
    var button = document.getElementById('nav-toggle');
    var tools = document.getElementById('masthead-tools');
    if (!button || !tools) return;

    var close = function () {
      delete tools.dataset.open;
      button.setAttribute('aria-expanded', 'false');
    };

    button.addEventListener('click', function (e) {
      e.stopPropagation();
      if (tools.dataset.open === undefined) {
        tools.dataset.open = '';
        button.setAttribute('aria-expanded', 'true');
      } else {
        close();
      }
    });

    /* A tap anywhere else, or Escape, puts it away. Not a tap inside it: choosing a
       unit there should leave it open to choose something else. */
    document.addEventListener('click', function (e) {
      if (tools.dataset.open !== undefined && !tools.contains(e.target)) close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && tools.dataset.open !== undefined) {
        close();
        button.focus();
      }
    });

    /* Following a link leaves the page anyway, and leaving it open would have it
       flash back into view on the way out. */
    tools.addEventListener('click', function (e) {
      if (e.target.closest('a')) close();
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
      paintSpan();
    });

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      if (!document.documentElement.getAttribute('data-theme')) {
        syncLabel();
        redrawAll();
        paintSpan();
      }
    });

    function syncLabel() {
      var dark = resolvedTheme() === 'dark';
      button.setAttribute('aria-label',
        dark ? (CFG.text.toLight || 'Switch to light theme')
             : (CFG.text.toDark || 'Switch to dark theme'));
    }
  }

  /* The way back to the top of a long page. The stylesheet keeps the button out of
     sight until this shows it, which is why it is safe to write it on every page:
     without a script there is nothing to see and nothing to tab to. */
  function setupToTop() {
    var button = document.getElementById('to-top');
    if (!button) return;

    var shown = false;
    var queued = false;

    /* A scroll event fires far more often than the page can paint, and all this has
       to decide is whether one attribute is set. One look per frame is enough. */
    function check() {
      queued = false;
      /* A screen of page behind the reader. Less than that and the button would be
         offering a trip that a flick of the thumb already makes. */
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
    });

    /* A page opened at an anchor, or returned to, is already scrolled. */
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

  /* Pick a sensible number of decimals from the spread of the data. */
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

  /* One label for one tick on the x axis. A chart library's own date formatter
     writes English
     and a 12-hour clock. This one writes the reader's locale, and keeps the labels
     short enough that they do not run into each other. */
  function fmtTick(ts, period, splits) {
    var d = new Date(ts * 1000);
    /* Seconds between ticks, which is what the label has to suit. The name of the
       period does not say it. A year view of a station three weeks old has every tick
       inside one month, where twelve labels reading "Aug" say nothing. */
    var step = (splits && splits.length > 1) ? (splits[1] - splits[0]) : null;
    if (period === 'day') {
      return d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    }
    if (period === 'week') {
      return d.getHours() === 0
        ? d.toLocaleDateString(LOCALE, { weekday: 'short' })
        : d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    }
    /* Ticks less than a day apart need a clock time on them, whatever the period is
       called. A month or a year view of a station running for three days has all its
       ticks inside those days. Without the time, every label reads the same. */
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

  /* The plot files hold readings already converted, into whichever unit the skin was
     configured for. That is one unit, decided on the server, and a reader who thinks
     in the other one is stuck with it.

     index.json carries what it takes to change that: the unit group each observation
     belongs to, the unit each unit system uses for that group, and the factor and
     offset between any two units. So the page can redraw the same readings in
     Fahrenheit or in Celsius without fetching anything.

     Only the charts. The panels are rendered by the server, in the report's own unit,
     and moving those would mean rebuilding WeeWX's formatting in JavaScript. So the
     control sits on the history panel, next to the span it applies to, rather than in
     the masthead where it would look like it governed the page. */

  /* Kept apart from the manifest, and not cleared with it. A new record empties the
     manifest so that a plot added since is noticed, and the conversions would go with
     it: the reader's choice of unit would fall back to the server's for as long as it
     took the index to arrive again. The table itself changes only when the station is
     reconfigured. */
  var unitChoices = null;

  function unitTable() {
    return unitChoices;
  }

  /* The unit this series should be shown in, or null to leave it as it came.

     With no system chosen the report's own units apply. That matters for readings
     the page fetches rather than renders: the forecast comes from Open-Meteo in
     Celsius and km/h whatever the station is set to, and showing it in metric
     beside a page of Fahrenheit is worse than either on its own. Everything the
     server wrote is already in these units, so for those this converts nothing. */
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

  /* Rewrite a plot's readings, axis and labels in the reader's chosen unit.

     Done to a copy, never to what came off the wire: the cached file has to stay in
     the unit it was written in, or switching back and forth would convert a converted
     reading. */
  function inChosenUnit(meta) {
    var table = unitTable();
    if (!table || !meta || !meta.series || !meta.series.length) return shallow(meta);

    var to = targetUnit(meta.series[0].obs_type, meta.unit);
    /* A copy even when there is nothing to convert. Returning the argument would make
       entry.meta and entry.raw the same object, and the next conversion would write
       its result into the file it was meant to convert from. Switching unit twice
       would then convert an already converted reading. */
    if (!to) return shallow(meta);
    var steps = table.convert[meta.unit][to];
    var factor = steps[0], offset = steps[1];
    var apply = function (v) {
      return v === null || v === undefined ? null : v * factor + offset;
    };

    var out = shallow(meta);
    out.unit = to;
    out.unit_label = (table.labels && table.labels[to]) || '';

    /* The axis moves with the readings. Its step is a distance, not a reading, so it
       takes the factor and not the offset: 5 degrees Celsius of spacing is 9 degrees
       Fahrenheit of spacing, not 41. */
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
      /* The extremes are readings on the same axis, so they take the offset too. */
      ['min', 'max'].forEach(function (k) {
        if (s[k]) copy[k] = s[k].map(apply);
      });
      /* Wind arrows are drawn from these, and they are lengths, not readings: a
         length of five degrees Celsius is nine of Fahrenheit, not forty-one. */
      ['vector_x', 'vector_y'].forEach(function (k) {
        if (s[k]) copy[k] = s[k].map(function (v) {
          return v === null ? null : v * factor;
        });
      });
      return copy;
    });
    return out;
  }

  /* A copy one level deep. Enough here: what gets replaced is always a whole property,
     never something inside one. */
  function shallow(obj) {
    if (!obj) return obj;
    var out = {};
    Object.keys(obj).forEach(function (k) { out[k] = obj[k]; });
    return out;
  }

  /* How many decimals to write, taken from the format string the skin uses for that
     unit: "%.1f" means one. Without it, a temperature converted to Celsius comes out
     as 17.72222222222222. */
  function decimalsFor(unit, fallback) {
    var table = unitTable();
    var fmt = table && table.formats && table.formats[unit];
    var m = fmt && /%\.(\d+)f/.exec(fmt);
    return m ? parseInt(m[1], 10) : (fallback === undefined ? 1 : fallback);
  }

  /* One reading, in the unit the reader asked for. Returns the number as it should be
     shown and the label to put beside it, or null where nothing has to change. */
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

  /* A label spaced the way the one it replaces was spaced. */
  function respace(was, now) {
    if (!now) return now;
    var lead = was && /^\s/.test(was) ? ' ' : '';
    return lead + now.replace(/^\s+/, '');
  }

  /* Rewrite the readings the server put on the page.

     Each of them carries the number as the database holds it and the unit that number
     is in, so the page can show it in another unit without asking for it again. The
     text stays as the server wrote it until a reader chooses otherwise, which is what
     a reader without JavaScript sees, and what everyone sees first. */
  function applyUnitsToPanels(root) {
    var scope = root || document;

    /* A column heading that names the unit for the column under it, and carries no
       reading of its own. Only the label moves; there is no number here to convert. */
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
      /* 'data-obs' first: it names the observation type, while 'data-live' names the
         field in current.json. They differ where one is derived from the other, as
         'rainToday' is from 'rain', and only the type is in the unit table. */
      var obs = el.dataset.obs || el.dataset.live;
      var out = convertReading(parseFloat(el.dataset.value), el.dataset.unit, obs);
      var target = el.querySelector('[data-unit-value]') || el;
      var label = el.querySelector('[data-unit-label]')
        || (el.parentNode && el.parentNode.querySelector('[data-unit-label]'));

      if (!out) {
        /* Back to what the server wrote. Kept on the element for exactly this. */
        if (el.dataset.asWritten !== undefined) setLive(target, el.dataset.asWritten);
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
      setLive(target, fmtNumber(out.value, decimalsFor(out.unit)));
      /* The skin writes some labels with a leading space and some without, and the
         unit table strips them all. Put back whatever the server had used here, so a
         converted reading is spaced like the one it replaced. */
      if (label) label.textContent = respace(label.dataset.asWritten, out.label);
    });
  }

  /* What another script on the page needs in order to show its own numbers in the
     reader's unit. Four functions and nothing else: the tables and the reader's
     choice stay in here, so there is one of each on the page.

     Used by climate.js, which draws from data the server put in the page rather than
     from the plot files, and so cannot go through the chart path above. */
  CFG.units = {
    /* The unit this reading should be shown in, or null to leave it alone. */
    target: targetUnit,
    /* {value, unit, label} in that unit, or null where nothing has to change. */
    convert: convertReading,
    /* How many decimals the skin writes for that unit. */
    decimals: decimalsFor,
    /* Whether a reader has chosen a unit system at all. */
    chosen: function () { return recall('units', ''); }
  };

  /* The colour this skin gives a temperature, so that the same reading is the same
     colour wherever it appears. Celsius in, CSS colour out. */
  CFG.tempColour = function (celsius) {
    return tempColour(celsius, warmStops());
  };

  /* Which systems this station's readings can be shown in. Empty where the station
     publishes no unit table, which is any skin whose generator predates it. */
  function availableSystems() {
    var table = unitTable();
    if (!table || !table.systems) return [];
    return Object.keys(table.systems).filter(function (name) {
      return Object.keys(table.systems[name]).length;
    });
  }

  /* The control, in the masthead beside the language picker and the theme toggle.

     It belongs there rather than on the history panel: it governs every reading on
     the page, the card at the top as much as the charts. A control over the charts
     alone would leave the card saying 63.9 while the chart under it said 17.7. */
  function setupUnitPicker() {
    var picker = document.getElementById('unit-picker');
    if (!picker) return;

    var chosen = recall('units', '');
    /* Convert whatever is already on the page, before the manifest arrives. The
       readings carry their own units, so this does not wait for anything. */
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
      picker.hidden = false;
      if (recall('units', '')) applyUnitsAll();
    });

    picker.addEventListener('change', function () {
      remember('units', picker.value);
      applyUnitsAll();
    });
  }

  /* Everything on the page that carries a reading. Nothing is fetched: the numbers
     are already here, and only the arithmetic on them changes. */
  function applyUnitsAll() {
    applyUnitsToPanels();
    charts.forEach(function (entry) {
      if (entry.raw) updateChart(entry, entry.raw);
    });
    /* For anything on the page that holds numbers of its own. */
    document.dispatchEvent(new CustomEvent('horizon:units'));
  }

  /* -------------------------------------------------------------- shaping */

  /* The data table draws every series against one array of timestamps. The series
     in a plot
     usually already carry the same ones. Where they do not, build the union of all
     their timestamps and put each series' values at the right positions in it. */
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

  /* The CSS keyword 'transparent' means rgba(0,0,0,0), which is black. A gradient
     that fades a colour out through it therefore passes through grey on the way.
     Return the same colour at zero alpha, which fades without changing hue. */
  function fadeOut(color) {
    var c = color.trim();
    var m = c.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
    if (m) {
      var h = m[1];
      if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
      return 'rgba(' + parseInt(h.slice(0, 2), 16) + ','
        + parseInt(h.slice(2, 4), 16) + ','
        + parseInt(h.slice(4, 6), 16) + ',0)';
    }
    m = c.match(/^rgba?\(([^)]+)\)$/i);
    if (m) {
      var parts = m[1].split(',').slice(0, 3).map(function (x) { return x.trim(); });
      return 'rgba(' + parts.join(',') + ',0)';
    }
    return 'rgba(0,0,0,0)';
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ----------------------------------------------------------- chart pieces */

  /* Every chart on the page, as {plot, host, meta, raw, period}. Kept so that a new
     record, a theme change or a unit change can be put into the instances that are
     already drawn rather than building them again. */
  var charts = [];

  /* The stretches of darkness, as areas the chart can shade.

     Worked out from the sunrise and sunset times the generator wrote beside the
     readings, so the shading follows the real day rather than a fixed hour. Read
     fresh on every build: a record arriving at the turn of a day brings new times
     with it. */
  function nightAreas(meta) {
    var dn = meta.daynight;
    if (!dn || !dn.transitions || !dn.transitions.length) return [];

    /* How long the light takes to go, at this latitude and this time of year. The
       generator writes the civil twilight either side of each sunrise and sunset, so
       the shading can fade over the time the sky actually took rather than over a
       fixed number of minutes. Half the fade sits either side of the boundary, which
       is where the eye puts it. */
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
      /* Grown by half a twilight at each end, so the gradient below can reach full
         darkness at the boundary itself. */
      var lo = a - dusk / 2, hi = b + dawn / 2;
      var span = hi - lo;
      if (span <= 0) return;
      out.push({
        span: span,
        /* Where in the band the sky is fully dark. */
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

  /* One shaded band, faded in and out across its own twilight. */
  function nightBand(band, colour) {
    /* The same colour at zero opacity, not a transparent black: fading to black
       puts a grey cast in the middle of the gradient. */
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

  /* How wide to draw a bar, in pixels.

     A bar totalled over an hour sits on the grid every nth slot, and a chart library
     sizes bars from the closest pair of points it can see. Left alone that makes an
     hour's rain a hairline. The width is therefore worked out from the span the bar
     stands for against the span on screen. */
  function barWidthPx(meta, s, hostWidth) {
    var covered = s.aggregate_interval || meta.aggregate_interval;
    var span = (meta.stop || 0) - (meta.start || 0);
    if (!covered || !span || !hostWidth) return undefined;
    return Math.max(1, Math.floor((covered / span) * hostWidth * 0.85));
  }

  /* One wind arrow per reading, drawn from the two components.

     A line through the speeds would say nothing about direction, which is the whole
     point of the plot. Each arrow starts on the zero line and points where the wind
     came from, scaled so the longest reaches the top of the axis. */
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

      /* The components give the direction; the axis gives how long to draw it. */
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

  /* The gaps a person picks when dividing an axis by hand, whatever the decimal
     point does. Four and a half is here for the eighths of a compass; 1.27, which is
     what a twentieth of an inch of rain comes to in millimetres, is not. */
  var ROUND_STEPS = [1, 1.5, 2, 2.5, 3, 4, 4.5, 5, 6, 7.5, 9];

  function isRound(v) {
    if (!v) return false;
    var mag = Math.pow(10, Math.floor(Math.log(Math.abs(v)) / Math.LN10));
    var lead = Math.abs(v) / mag;
    return ROUND_STEPS.some(function (m) { return Math.abs(lead - m) < 1e-9; });
  }

  /* Whether the generator's own step still divides its own axis.

     It always does as it leaves the generator. A conversion into the reader's unit
     can break it: multiplying a fifth of an inch of mercury gives 6.77 hectopascals
     against ends of 989.49 and 1030.13, and Fahrenheit adds an offset on top, so
     ten degrees Celsius becomes a step of eighteen starting at minus four. Where the
     ends are still whole multiples the step was meant, however unusual it looks:
     forty-five degrees is an eighth of the compass. */
  function divides(lo, hi, step) {
    if (!step) return false;
    var whole = function (v) {
      var n = v / step;
      return Math.abs(n - Math.round(n)) < 1e-6;
    };
    return whole(lo) && whole(hi);
  }

  /* The gap between gridlines. Null where there is nothing to scale, which leaves the
     choice to the chart. */
  function gridStep(meta, height) {
    if (!meta.yscale || !meta.yscale[2]) return null;
    var step = meta.yscale[2];
    var span = meta.yscale[1] - meta.yscale[0];
    if (!(span > 0)) return step;

    /* A label is one line of twelve pixel type. Twenty-four leaves it as much air
       again, which is enough to read a column of numbers down an axis. */
    var room = Math.max(2, Math.floor((height - 40) / 24));

    if (span / step <= room && isRound(step)
        && divides(meta.yscale[0], meta.yscale[1], step)) {
      return step;
    }

    /* Otherwise the smallest step a person would have picked that still fits. */
    var least = span / room;
    var mag = Math.pow(10, Math.floor(Math.log(least) / Math.LN10));
    var nice = [1, 2, 2.5, 5, 10, 20].map(function (m) { return m * mag; })
      .filter(function (v) { return v >= least; })[0];
    return nice || step;
  }

  /* One end of the y axis, on a whole step. Widened, never narrowed: a reading must
     not fall outside the axis drawn for it. */
  function axisEnd(meta, step, which) {
    if (!meta.yscale) return null;
    var v = meta.yscale[which === 'min' ? 0 : 1];
    if (v === null || v === undefined || !step) return v === undefined ? null : v;
    var snapped = which === 'min' ? Math.floor(v / step) * step
                                  : Math.ceil(v / step) * step;
    /* Away from floating point dust: 0.30000000000000004 is not a tick label. */
    return Math.round(snapped * 1e6) / 1e6;
  }

  function chartHeight(width) {
    /* The floor is what a chart in a narrow column gets, and it decides how many
       gridlines fit: at 180 a pressure axis had room for four labels. */
    return Math.max(270, Math.min(360, Math.round(width * 0.32)));
  }

  /* Save the chart as a picture, with its title and the station's name on it.

     A chart pasted into a forum post has to say what it is without the page around
     it. */
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

  /* The options one chart is drawn from.

     Rebuilt whenever the readings or the theme change, and handed to the instance
     with setOption(), which keeps the reader's zoom and their place in the data. */
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
        /* A day of one minute readings is 1440 points, a year of hourly ones 8760.
           Drawing every one of them says nothing a screen can show. */
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
      /* The shading goes on the first series that can carry it. Behind everything:
         it is the backdrop, and drawn on top it hides the zero line and the grid. */
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
        /* Parked in a top corner rather than following the cursor: a box that moves
           with the pointer covers the very readings being compared, and jumps from
           one side to the other as it runs out of room. It sits opposite the hand,
           so it never hides what is being pointed at. */
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
            /* A wind reading is a speed and a bearing. The speed alone is half of it. */
            if (s && s.directions) {
              var d = s.directions[p.dataIndex];
              if (d !== null && d !== undefined) extra = ' · ' + fmtNumber(d, 0) + '°';
            }
            /* Where the series carries the extremes of its slot, they belong here:
               an average of an hour with a gust of twice it in the middle is not the
               hour the reader thinks it was. */
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
          /* The muted ink rather than the axis colour: an axis line may fade into
             the background, but the numbers on it are meant to be read. */
          color: colors.muted, fontFamily: family, fontSize: 12,
          formatter: function (value) { return fmtTick(value / 1000, period, null); },
          hideOverlap: true
        }
      },
      yAxis: {
        type: 'value',
        /* The unit, above the axis it belongs to. A column of numbers says nothing
           on its own, and the reader can change what they mean. */
        name: meta.unit_label || '',
        nameLocation: 'end',
        nameGap: 12,
        nameTextStyle: {
          color: colors.muted, fontFamily: family, fontSize: 12, align: 'left'
        },
        /* Worked out by the generator with the function the ImageGenerator uses.
           Left to choose, a chart library gives axes that reach 400 degrees of wind
           direction, or 5 m/s for wind that never passed 2.3.

           The ends are widened to whole steps. In the reader's unit the generator's
           are no longer round: 29.2 inches of mercury is 989.49 hectopascals, and an
           axis starting there is labelled 989.5, 1009.5, 1029.5. */
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

  /* The range label is written short or long depending on how much room there is.
     Turning a phone sideways has to rewrite it, or the short form stays. */
  window.matchMedia('(min-width: 34rem)').addEventListener('change', function () {
    if (currentPeriod) showPeriod(currentPeriod);
  });

  function redrawAll() {
    /* The colours are read when the options are built, so a theme change means
       building them again. Everything else about the chart stays as it is. */
    charts.forEach(function (c) {
      c.plot.setOption(chartOptions(c.meta, c.period, c.host.clientWidth || 600));
    });
  }

  /* Resize a chart when the element holding it changes size. One observer watches
     every chart, rather than one observer each. A bar's width is worked out in
     pixels, so it has to be worked out again at the new width. */
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
    /* One row per reading. An aggregated plot has a few hundred readings at most.
       Only a long span of raw readings runs past the limit, and the table says so
       in its caption when it does. */
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
    /* Convert here, and keep 'raw' on the entry below. Switching unit reruns the
       conversion from the file as it was written, never from a converted copy. */
    var meta = inChosenUnit(raw);
    var host = card.querySelector('.chart-host');
    var legend = card.querySelector('.chart-title');
    var details = card.querySelector('.chart-data');

    host.innerHTML = '';

    if (!meta.series.length) {
      host.innerHTML = '<p class="chart-empty">' + escapeHtml(CFG.text.noData || 'No data') + '</p>';
      return;
    }

    /* The card's title is also its legend: each series name in the colour of its
       line. A separate legend would repeat those names on a second line, and on a
       phone that line is one the chart could have had. */
    legend.innerHTML = meta.series.map(function (s) {
      return '<span style="color:' + (s.color || 'currentColor') + '"><i></i>'
        + '<span class="series-name">' + escapeHtml(s.label) + '</span></span>';
    }).join('');

    var entry = buildChart(host, meta, period);
    entry.raw = raw;
    charts.push(entry);
    resizeObserver.observe(host);

    /* Saving the chart. Where the skin also runs the ImageGenerator there is a
       second button, linking to the file it wrote, because a file on the server has
       a URL that can be pasted somewhere. */
    var actions = card.querySelector('.chart-actions');
    if (actions) {
      var save = document.createElement('button');
      save.type = 'button';
      save.className = 'chart-action';
      save.textContent = CFG.text.saveImage || 'Save image';
      save.addEventListener('click', function () { exportChart(entry, card); });
      actions.appendChild(save);

      /* Most stations run one skin, and this one does not draw PNGs unless asked.
         So the link appears only where index.json says they are being written, or
         where 'show_image_links' says so outright. */
      var offerImage = CFG.hasImages === null || CFG.hasImages === undefined
        ? !!(manifest && manifest.images)
        : CFG.hasImages;
      if (anchor === null && offerImage && meta.name) {
        var link = document.createElement('a');
        link.className = 'chart-action';
        link.href = meta.name + '.png';
        link.textContent = CFG.text.imageLink || 'PNG';
        link.title = CFG.text.imageLinkTitle || 'Permanent link to the rendered image';
        actions.appendChild(link);
      }
    }

    if (details) {
      var digits = digitsFor(meta.series);
      details.querySelector('.scroller-host').innerHTML = renderTable(meta, digits);
    }
  }

  /* Put a new record into a chart that is already on screen.

     Rebuilding the chart instead would make a new instance, which clears the canvas,
     drops the reader's zoom and their place in the data table, and shows an empty
     plot for as long as the fetch takes. All of that once a minute. Handing the new
     options to the instance leaves it alone: the x axis moves to the left by one
     record and the new reading is drawn on the right.

     Returns false where the shape of the plot has changed. The caller rebuilds those.
     It happens when a series that has never had a reading gets its first one. */
  function updateChart(entry, raw) {
    var plot = entry.plot;
    var fresh = inChosenUnit(raw);
    if (!fresh.series || fresh.series.length !== entry.meta.series.length) return false;

    /* The options are built from entry.meta, so replacing its contents is what
       carries the new sunrise times, unit label and axis range into the redraw. */
    Object.keys(fresh).forEach(function (key) { entry.meta[key] = fresh[key]; });
    entry.raw = raw;
    plot.setOption(chartOptions(entry.meta, entry.period,
                                entry.host.clientWidth || 600));

    /* The table is built from the data, so it is rebuilt as well. A closed one is
       marked instead of rebuilt, and built again when the reader opens it: rebuilding
       eleven tables nobody is looking at, once a minute, is work for nothing. */
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

  /* Where one card's readings come from.

     The archive answers every span, live or stepped back: it holds the same readings
     on a grid chosen to suit the span, and today is its raw tier, written every
     report. The period files are the fallback, and only where a skin still writes
     them: asking for one that is turned off is a 404 per card, per reload, for
     everyone who opens the page. */
  function chartSource(card) {
    return windowFromArchive(card.dataset.group, +card.dataset.from, +card.dataset.to)
      .then(function (meta) {
        if (meta) return meta;
        var hasPeriods = manifest && manifest.plots && manifest.plots.length;
        return anchor === null && hasPeriods ? loadPlot(card.dataset.plot) : null;
      });
  }

  /* Bring every chart on screen up to the newest record.

     A span in the past cannot have changed, so there is nothing to do for one. Only
     the live view follows the clock. */
  function refreshCharts() {
    if (anchor !== null) return;
    cache.clear();
    /* The archive answers the live view too, so its files and the index naming them
       are what has just gone stale. */
    archiveCache.clear();
    archiveIndex = null;
    manifest = null;
    indexRefetched = false;

    /* The live window slides with the clock: at half past midnight "today" is not
       the day it was when these cards were built. */
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
          /* The plot has a series it did not have before. Draw the card again. */
          resizeObserver.unobserve(entry.host);
          entry.plot.dispose();
          charts = charts.filter(function (c) { return c !== entry; });
          renderChart(card, fresh, card.dataset.period);
        });
      });
    });

    /* Cards further down the page have no chart yet, and cards whose plot had no
       readings were left empty. Both have to look again, because the file behind them
       has changed. Those still waiting to be scrolled into view do so on their own,
       out of the cache that was just emptied. */
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

  /* --------------------------------------------------------------- periods */

  var cache = new Map();
  var manifest = null;

  /* ------------------------------------------------------- history archive */

  /* The day, week, month and year files all end at the last reading, so none of them
     reaches further back than a year. Spans before that come from the archive files
     instead: one per plot group and calendar year, with readings evenly spaced in
     time. Only the years a span touches are fetched, and each is kept after that. */

  var archiveIndex = null;
  var archiveCache = new Map();           // "group-year" -> the file's contents

  /* The end of the span on screen, as a timestamp. null means the live view, which is
     the only one that follows the clock. Every other span is fixed to a moment, so a
     link to one still shows the same days tomorrow. */
  var anchor = null;

  /* How many seconds each span covers. Used for the live view alone, because the live
     view slides: at half past midnight the reader wants last evening, not an empty
     "today". Every span reached by the arrows is a whole calendar unit instead, such
     as Tuesday, week 33, July or 2025, which is what "back" means to a reader.

     These four are fallbacks. The real lengths arrive in index.json, which takes them
     from 'time_length' in skin.conf, so that option reaches the chart and not only
     the PNGs of a skin that draws them. */
  var PERIOD_SECONDS = { day: 27 * 3600, week: 7 * 86400, month: 30 * 86400, year: 365 * 86400 };

  function adoptSpans(manifest) {
    if (!manifest || !manifest.spans) return;
    Object.keys(manifest.spans).forEach(function (group) {
      /* index.json uses the skin.conf section name, 'day_images'. The page uses the
         period name, 'day'. */
      var period = group.replace(/_images$/, '');
      var seconds = parseInt(manifest.spans[group], 10);
      if (seconds > 0) PERIOD_SECONDS[period] = seconds;
    });
  }

  /* There are two "nows" here, and using one where the other belongs moves the
     calendar by a day.

     dataTs() is the time of the last reading in the report. The arrows measure from
     it. The live view ends there, so the calendar unit holding that reading is the
     unit on screen, and "back" means the unit before it.

     nowTs() is the reader's own clock. It decides one thing only: whether the live
     view can still be labelled "Now". The two times differ when the station was off
     overnight, when the page has been open past midnight, or when a cache is serving
     an older copy of the site. */
  function nowTs() {
    return Math.floor(Date.now() / 1000);
  }

  function dataTs() {
    return CFG.generated || nowTs();
  }

  /* The start and end of the calendar unit of `period` that holds `ts`. */
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

  /* The span currently on screen, as a start, an end, and whether it is live. */
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

  /* The archive is written on three grids: the station's own readings per day, a
     closer grid per month, and one per calendar year that coarsens with age. They
     overlap on purpose, so a span can be drawn from whichever of them suits it.

     Finest first, and the first one that can cover the whole span wins. "Can" is two
     things: the index has to name a file for every part of the span, since joining
     two grids in one chart would draw a step where the spacing changes, and the
     result has to be a sane number of points. A day from the raw tier is 1440 of
     them; a year would be half a million, which is a download nobody wants for a
     chart a thousand pixels wide. */
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

  /* The keys of the files a span touches, as the index writes them. */
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

  /* Does the stretch a key stands for overlap the readings the station has at all?
     'YYYY', 'YYYY-MM' and 'YYYY-MM-DD' all say where they start and how far they run. */
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

  /* Which files to draw a span from, finest grid that fits. */
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
          /* A key the index does not name is either a stretch the station has no
             readings for, which is nothing to hold against the tier, or a gap in what
             this tier reaches back to, which disqualifies it: half a week drawn from
             the day files and the rest missing is worse than the whole week drawn
             from the month files. */
          if (touchesRecord(keys[i])) { ok = false; break; }
          continue;
        }
        var g = grids[keys[i]];
        /* Two spacings in one chart would draw a step where they meet. */
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
    /* Only the years the archive holds. */
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

  /* Night shading is readable only on a span short enough to show single days. Over a
     month or a year the bands are a pixel or two wide and read as grey haze. The PNGs
     leave the shading off on those spans for the same reason. */
  function nightForWindow(from, to, years) {
    if ((to - from) > 9 * 86400) return Promise.resolve(null);
    return Promise.all(years.map(loadDayNight)).then(function (files) {
      var all = [];
      var bands = [];
      var first = null;
      files.filter(Boolean).forEach(function (f) {
        if (first === null) {
          /* Whether `from` falls in daylight or darkness. Day and night alternate,
             so counting the crossings before it settles which. */
          var before = f.transitions.filter(function (t) { return t <= from; }).length;
          var startState = f.first === 'day' ? 'day' : 'night';
          first = (before % 2 === 0) ? startState : (startState === 'day' ? 'night' : 'day');
        }
        all = all.concat(f.transitions.filter(function (t) { return t > from && t < to; }));
        /* The twilight times have to be carried across with the crossings. Without
           them the archive view steps from day to night where the live view fades. */
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

  /* Build one span's series by joining the archive files it reaches across. */
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

        /* Beside 'values' a series can carry more arrays of the same length: the two
           components of a wind vector, and the extremes of a slot for the types where
           an average hides what mattered. They are joined exactly as values are. */
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
          /* A bar totalled over more than one slot has to be drawn that wide. */
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

        /* The y axis comes from the files, not from the chart library. The generator
           works it out
           with the same function the ImageGenerator uses, which knows that a wind
           vector is drawn about zero and that a direction runs 0 to 360. Left to
           choose, a chart library gets both wrong. Joining several files takes the
           widest of their axes, and the step from the first that states one. */
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
        manifest = json || { plots: [] };
        adoptSpans(manifest);
        if (manifest.units) unitChoices = manifest.units;
        return manifest;
      })
      .catch(function () { manifest = { plots: [] }; return manifest; });
  }

  /* index.json lists the plot files that existed when the report last ran, and it can
     end up naming one that is not there. A file deleted by hand does it. So does a
     publish over FTP or rsync that carries index.json across before the file it names,
     which leaves a window of a few seconds on every cycle.

     There is no way for the page to prevent that, so it recovers from it instead. A
     404 on a file the index names means the index is the thing that is wrong, so fetch
     it again. Once, until the next record arrives: a station that really is missing a
     file would otherwise re-read the index for every card on the page, every time. */
  var indexRefetched = false;

  function loadPlot(name) {
    if (cache.has(name)) return Promise.resolve(cache.get(name));
    return fetch(DATA_DIR + '/' + name + '.json', { cache: 'no-cache' })
      .then(function (r) {
        if (r.ok) return r.json();
        if (r.status === 404 && !indexRefetched) {
          indexRefetched = true;
          manifest = null;
          return loadManifest().then(function () { return null; });
        }
        return null;
      })
      .then(function (json) { cache.set(name, json); return json; })
      .catch(function () { cache.set(name, null); return null; });
  }

  /* Draw a card's chart when the card first comes near the screen. On a phone that
     is one or two files fetched on load, rather than twenty. */
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

    /* Every span comes from the archive, live or stepped back. It holds the same
       readings on a grid chosen to suit the span, so there is nothing the four period
       files could add: today is the raw tier, and it is written every report.

       They are still the fallback. A skin can leave 'periods' on, and a station whose
       archive is still building has spans it cannot answer yet. */
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

  /* A PNG on the server can be linked to, because the web server hands it out as a
     file. A chart saved from the canvas cannot: it exists only in the browser that
     made it. What can be shared is the view, as a link that reopens it. That is
     usually what is meant anyway, and it arrives current, in the reader's own
     language and theme.

     The link names a date rather than an offset. "Three weeks back" points somewhere
     else next week. "The week ending 2 August 2026" does not move. */
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

    /* Accepts 2026, 2026-07 and 2026-07-13, whichever suits the period. Any date
       inside a unit selects that unit, so a link typed by hand still works. */
    var m = parts[1].match(/^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?(?:T\d{1,2})?$/);
    if (!m) {
      /* An older form of the link counted units back, as "-3". Read it rather than
         dropping the reader at the live view. */
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

  /* The range bar sticks to the window under the panel head, so it has to be told how
     tall that head is. A fixed value in the stylesheet holds for one font size and one
     row of tabs. At any other size the two overlap. */
  function measureStickyHead() {
    var panels = document.querySelectorAll('.panel');
    for (var i = 0; i < panels.length; i++) {
      var head = panels[i].querySelector('.panel-head');
      var bar = panels[i].querySelector('.range-bar');
      if (head && bar) {
        panels[i].style.setProperty('--head-height', head.offsetHeight + 'px');
      }
    }
  }

  /* Scroll back to the first chart after the span changed. Changing it from halfway
     down the page leaves the reader among charts that have just been replaced, at a
     scroll position that no longer means anything. Only scroll if they were past the
     first chart: at the top of the page, nothing should move. Called once the cards
     are in place, because until then the page is too short to scroll. */
  function backToFirstChart(container) {
    var panel = container.closest('.panel');
    if (!panel) return;
    var head = panel.querySelector('.panel-head');
    var bar = panel.querySelector('.range-bar');
    var stuck = (head ? head.offsetHeight : 0) + (bar ? bar.offsetHeight : 0);
    var top = window.scrollY + container.getBoundingClientRect().top - stuck - 8;
    if (window.scrollY > top + 4) {
      window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
    }
  }

  function showPeriod(period, newAnchor, keepPlace) {
    var container = document.getElementById('charts');
    if (!container) return;

    if (newAnchor !== undefined) anchor = newAnchor;
    if (period !== currentPeriod && newAnchor === undefined) {
      anchor = null;                               // switching span returns to now
    }
    currentPeriod = period;

    clearCharts();
    container.setAttribute('aria-busy', 'true');

    var win = currentWindow(period);
    var from = win.from, to = win.to, live = win.live;

    Promise.all([loadManifest(), loadArchiveIndex()]).then(function (res) {
      var mf = res[0], ai = res[1];
      var groups = CFG.plotGroups || [];

      /* Order the cards as 'plot_groups' in skin.conf lists them, not as the files
         happen to appear in index.json. */
      var wanted = groups.map(function (g) {
        var snapshot = (mf.plots || []).find(function (p) { return p.name === period + g; });
        var archived = (ai.groups || []).find(function (p) { return p.name === g; });
        /* The period files are optional. Where they are not written the archive is
           the only source, live or not, and it is the one that names the group. */
        if (live && snapshot) {
          return { group: g, name: snapshot.name, title: snapshot.title };
        }
        /* Being named in the index means the group has readings somewhere, not
           that it has any in the span on screen. A sensor that stopped reporting
           three years ago stays named, because the years it did report are still
           in the archive, and its card would be drawn empty on every span since.
           Ask instead for the files this span would actually be drawn from. */
        if (!archived || !filesFor(g, from, to)) return null;
        return { group: g, name: period + g, title: archived.title };
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
        card.dataset.plot = entry.name;
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
      if (!keepPlace) backToFirstChart(container);
    });

    document.querySelectorAll('#period-tabs button').forEach(function (b) {
      b.setAttribute('aria-selected', String(b.dataset.period === period));
    });

    remember('period', period);
    writeLocation(period);
    showSpanOnCards(period);
  }

  /* The cards, for the span on screen.

     A card shows the reading as it stands and what it did today. Over a week or a
     year the reading as it stands says nothing about the span: it is one instant
     out of thousands. So for those the card shows the mean instead, with the two
     ends of the span under it -- which is what the numbers mean when the span is
     longer than a day.

     The figures are already in the page: the template wrote them into
     'data-spans' when it rendered the card. Nothing is fetched, and the unit
     conversion is the skin's own, run again over the values just swapped in. */
  function showSpanOnCards(period) {
    var panel = document.querySelector('[data-live-panel="current"]');
    if (!panel) return;
    var daily = period === 'day' || !period;
    panel.dataset.span = period || 'day';

    panel.querySelectorAll('[data-spans]').forEach(function (el) {
      var held;
      try {
        held = JSON.parse(el.dataset.spans || '{}');
      } catch (e) {
        return;
      }

      /* What the server wrote is the day, and it is what we come back to. */
      if (el.dataset.dayValue === undefined) {
        el.dataset.dayValue = el.dataset.value || '';
      }
      var found = daily ? null : held[period];
      if (!daily && !found) {
        /* No figures for this span -- a sensor fitted yesterday, say. Leave the
           card on the day rather than emptying it. */
        found = null;
      }
      setSpanValue(el, found ? found.v : el.dataset.dayValue);

      /* A heading that names the day cannot stand over a year. Rain is the one
         that does: "Rain Today" is right for a day and wrong for everything
         else, so the card carries both and the span picks. */
      var tile = el.closest('div');
      var heading = tile && tile.querySelector('[data-label-span]');
      if (heading) {
        heading.textContent = daily
          ? heading.dataset.labelDay
          : heading.dataset.labelSpan;
      }

      /* Where the wind mostly came from, in place of where the vane points now. */
      var vane = tile && tile.querySelector('.wind-now');
      if (vane) {
        if (vane.dataset.asWritten === undefined) {
          vane.dataset.asWritten = vane.textContent;
        }
        vane.textContent = (found && found.dir) || vane.dataset.asWritten;
      }

      /* The two ends belong to the same card and move with it. */
      var range = tile ? tile.querySelector('.tile-range') : null;
      if (!range) return;
      ['lo', 'hi'].forEach(function (end) {
        var cell = range.querySelector('[data-range="' + end + '"]');
        if (!cell) return;
        if (cell.dataset.dayValue === undefined) {
          cell.dataset.dayValue = cell.dataset.value || '';
        }
        setSpanValue(cell, found ? found[end] : cell.dataset.dayValue);
      });
    });

    applyUnitsToPanels(panel);
  }

  /* One figure swapped in, written as the server would have written it so that
     the unit conversion has something to work from. */
  function setSpanValue(el, value) {
    if (value === null || value === undefined || value === '') {
      el.removeAttribute('data-value');
      return;
    }
    el.dataset.value = value;
    /* 'as-written' is what the conversion falls back to, so it has to move too. */
    var target = el.querySelector('[data-unit-value]') || el;
    var digits = decimalsFor(el.dataset.unit);
    var written = Number(value).toFixed(digits === undefined ? 1 : digits);
    el.dataset.asWritten = written;
    target.textContent = written;
  }

  /* The name of the calendar unit on screen: "Tuesday, 18 August 2026" for a day,
     "11–17 Aug 2026" for a week, "July 2026" for a month, "2025" for a year. */
  function unitLabel(period, from, to) {
    var start = new Date(from * 1000);
    var end = new Date((to - 1) * 1000);

    /* "Sunday, 23 August 2026" does not fit between the two arrows on a phone. It
       pushed the Now button underneath the forward arrow. The long form is kept on a
       wide screen, where there is room for it. */
    var roomy = window.matchMedia('(min-width: 34rem)').matches;

    if (period === 'day') {
      return start.toLocaleDateString(LOCALE, roomy
        ? { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }
        : { weekday: 'short', day: 'numeric', month: 'short' });
    }
    if (period === 'week') {
      var opts = roomy ? { day: 'numeric', month: 'short', year: 'numeric' }
                       : { day: 'numeric', month: 'short' };
      /* formatRange() knows how each language writes a span of dates: "10.–16. Aug.
         2026" in German, "10 – 16 Aug 2026" in English. Formatting both dates and
         joining them with a dash gets the punctuation wrong in most languages. */
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

  /* The word "Now" holds only while the last reading falls in the calendar unit the
     reader's clock is in. Where it does not, the live view shows Sunday and calls it
     now, and stepping back to Saturday looks as though it skipped a day. So label it
     with the name of the unit instead. */
  function liveLabel(period) {
    var d = calendarWindow(period, dataTs());
    return d.from === calendarWindow(period, nowTs()).from
      ? (CFG.text.now || 'Now')
      : unitLabel(period, d.from, d.to);
  }

  /* Label the span on screen, and grey out an arrow that would leave the record. */
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

    /* There is nothing before the first reading in the database. */
    if (back && ai && ai.first) {
      back.disabled = from <= ai.first;
    }

    /* An open calendar follows the span it was opened from. */
    drawCalendar();
  }

  /* A timestamp as YYYY-MM-DD in local time, which is the only form a date input
     takes. toISOString() would give the date in UTC, which is the day before for
     anyone west of Greenwich for part of every day. */
  function isoDate(ts) {
    var d = new Date(ts * 1000);
    return d.getFullYear()
      + '-' + String(d.getMonth() + 1).padStart(2, '0')
      + '-' + String(d.getDate()).padStart(2, '0');
  }

  /* Move one whole calendar unit. From the live view, "back" lands on the last unit
     that has ended. Stepping forward into the unit still running returns to the live
     view, which follows the clock. */
  function step(direction) {
    var here = calendarWindow(currentPeriod, anchor === null ? dataTs() : anchor);
    var target = direction < 0 ? here.from - 1 : here.to + 1;
    /* The unit the readings end in is the live view. readLocation() applies the same
       rule to a pasted link. Test the unit, not the instant: testing the instant
       leaves "forward" one step short, landing on the current unit as a fixed span,
       from where it takes a second press to reach the live view. */
    var unit = calendarWindow(currentPeriod, target);
    showPeriod(currentPeriod, unit.to > dataTs() ? null : target);
  }

  /* ------------------------------------------------------------- calendar */

  /* Reaching a date. The arrows step one calendar unit at a time, which is a long way
     back to last March.

     Drawn here rather than handed to <input type="date">. The panel a browser drops
     out of that input cannot be styled at all, so on a themed page it arrives as a
     white box with its own fonts and its own blue. It also knows nothing about this
     station: it offers every date since the calendar began, including the years
     before the station was built. This one greys those out, and it marks the day the
     readings end. */

  var calShown = null;                       // first of the month on display

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
      /* Midday, not midnight. A date taken as local midnight and then moved by an
         hour of summer time lands on the day before. */
      var parts = day.dataset.calDay.split('-').map(Number);
      var ts = Math.floor(new Date(parts[0], parts[1] - 1, parts[2], 12).getTime() / 1000);
      var unit = calendarWindow(currentPeriod, ts);
      closeCalendar();
      showPeriod(currentPeriod, unit.to > dataTs() ? null : ts);
    });

    /* A click anywhere else, or Escape, closes it. */
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

  /* One month. The week starts on the day the station's configuration says, which is
     not Monday everywhere, and the day names come from the reader's locale. */
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

    /* Day names, in the reader's language, from a week that is known to begin on a
       Sunday. Reading them out of Intl rather than listing them keeps this working in
       every language the skin is translated into. */
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
      /* Stop after a whole week that has left the month behind. */
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
          /* The clipboard API needs a secure context, and most stations are served
             over plain http. Show the link for the reader to copy. */
          window.prompt(CFG.text.copyLink || 'Copy this link:', url);
        }
      });
    }

    /* With the chart area focused, the left and right arrow keys step through time. */
    var container = document.getElementById('charts');
    if (container) {
      container.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft') { step(-1); e.preventDefault(); }
        if (e.key === 'ArrowRight' && anchor !== null) { step(1); e.preventDefault(); }
      });
    }
  }

  function setupPeriods() {
    var tabs = document.getElementById('period-tabs');
    if (!tabs) return;
    tabs.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-period]');
      if (b) showPeriod(b.dataset.period);
    });

    /* Opening the table on a card whose chart has not been drawn yet has to produce
       a table all the same. */
    var container = document.getElementById('charts');
    if (container) {
      container.addEventListener('toggle', function (e) {
        if (!e.target.matches('details.chart-data') || !e.target.open) return;
        var card = e.target.closest('.chart-card');
        if (!card) return;
        /* Never drawn: fetch and draw it, table and all. */
        if (!card.dataset.loaded) {
          hydrate(card);
          return;
        }
        /* Drawn, but the data or the unit moved on while this was closed. */
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
    }
    setupRangeNav();

    /* A span named in the link beats the one this browser last looked at. */
    var linked = readLocation();
    if (linked) {
      currentPeriod = linked.period;
      showPeriod(linked.period, linked.anchor);
    } else {
      var start = recall('period', (CFG.periods || ['day'])[0]);
      if ((CFG.periods || []).indexOf(start) < 0) start = (CFG.periods || ['day'])[0];
      showPeriod(start, null);
    }

    /* The browser's back and forward buttons, and a link pasted into this tab. */
    window.addEventListener('hashchange', function () {
      var loc = readLocation();
      if (loc && (loc.period !== currentPeriod || loc.anchor !== anchor)) {
        currentPeriod = loc.period;
        showPeriod(loc.period, loc.anchor);
      }
    });
  }

  /* ------------------------------------------------------------ live update */

  /* Write one live value into one element. The headline is set in two sizes, with the
     decimals smaller than the whole units, so its number arrives as one string and has
     to be split again here. Every other element takes the string as it is. */
  function setLive(el, text) {
    if (!el.classList.contains('lead-value')) {
      el.textContent = text;
      return;
    }
    var match = /^\s*([-+]?[\d.,]+)/.exec(text);
    var number = match ? match[1] : text.trim();
    var point = number.search(/[.,]/);
    if (point < 0) {
      el.textContent = number;
      return;
    }
    var decimals = el.querySelector('.lead-dec');
    if (!decimals) {
      decimals = document.createElement('span');
      decimals.className = 'lead-dec';
    }
    decimals.textContent = number.slice(point);
    el.textContent = number.slice(0, point);
    el.appendChild(decimals);
  }

  /* ------------------------------------------------------- temperature colour */

  /* The stylesheet defines nine colours, --warm-0 to --warm-8, one per temperature
     band. BAND_EDGES holds the temperatures where one band ends and the next begins,
     in degrees Celsius. WARM_AT holds the temperature at the middle of each band,
     which is where that colour is exact. Reading the colours from the stylesheet
     rather than repeating them here keeps one palette for the page, and moves the
     bar and the headline together when the theme changes. */
  var WARM_AT = [-15, -5, 2.5, 8.5, 15, 20.5, 25.5, 30.5, 36];
  var BAND_EDGES = [-10, 0, 5, 12, 18, 23, 28, 33];

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

  /* The colour for one temperature, mixed from the two band colours it falls between.
     Mixed rather than rounded to the nearer band, so that the mark on the bar and the
     headline both take the colour the bar is actually showing at that point. */
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

  /* Colour the bar under the headline by the temperatures it spans. Its ends take the
     colours of the day's lowest and highest readings. Every band edge between them
     gets a gradient stop at the position that temperature occupies on the bar. A day
     from 13 to 14 degrees comes out one colour. A day from 2 to 30 runs through all
     nine. */
  function paintSpan() {
    var track = document.querySelector('.span-track[data-lo]');
    if (!track) return;
    var lo = parseFloat(track.dataset.lo);
    var hi = parseFloat(track.dataset.hi);
    if (isNaN(lo) || isNaN(hi) || hi <= lo) return;

    var stops = warmStops();
    if (!stops.length) return;

    var parts = [tempColour(lo, stops) + ' 0%'];
    BAND_EDGES.forEach(function (edge) {
      if (edge > lo && edge < hi) {
        parts.push(tempColour(edge, stops)
                   + ' ' + ((edge - lo) / (hi - lo) * 100).toFixed(1) + '%');
      }
    });
    parts.push(tempColour(hi, stops) + ' 100%');

    var fill = track.querySelector('.span-fill');
    if (fill) fill.style.background = 'linear-gradient(90deg, ' + parts.join(', ') + ')';

    var now = parseFloat(track.dataset.now);
    if (isNaN(now)) return;
    var colour = tempColour(now, stops);
    var mark = track.querySelector('.span-now');
    if (mark) mark.style.setProperty('--span-at', colour);
    /* The headline shows the same temperature as the mark, so it takes its colour. */
    var lead = document.querySelector('.lead-value[data-band]');
    if (lead) lead.style.color = colour;
  }

  /* --------------------------------------------------------- panel refresh */

  /* Bring every panel forward when a new record arrives, by fetching the page again
     and putting each freshly rendered section in place of the one on screen.

     Only elements carrying 'data-live' used to be updated, which meant the readings
     and nothing else. The day's high and low, the times they were reached, the mark
     showing where the reading sits between them, the trend arrows, the almanac and
     the statistics all stood as the template first rendered them. Left open for an
     afternoon, the card contradicted itself: a reading well above a day that, by the
     line under it, never got that warm.

     A section is swapped if it carries 'data-live-panel'. A section that holds
     something the templates cannot render says so by not carrying the attribute: the
     charts hold chart instances, the map holds a Google Maps object, and the report
     picker holds the reader's choice of month. Each of those is brought forward its
     own way instead. */
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
          paintSpan();
          measureStickyHead();
          /* The sections just swapped in were rendered by the server, in the report's
             own unit. */
          applyUnitsToPanels();
          /* Anything that drew into a panel has just had its drawing thrown away,
             along with any listener it had bound to an element inside one. This says
             the swap is finished and the new elements are in the document. The event
             on the live update announces the record; this one announces the DOM. */
          document.dispatchEvent(new CustomEvent('horizon:panels'));
        }
      })
      .catch(function () { pageFetch = false; });
  }

  /* What the viewer did inside the panel that its freshly rendered twin cannot
     know about. One thing so far: how far a table too wide for its column has been
     pushed sideways. Set after the swap, since until then there is no layout to
     scroll. */
  function carryOver(old, fit) {
    var was = old.querySelectorAll('.table-scroll');
    var now = fit.querySelectorAll('.table-scroll');
    for (var i = 0; i < was.length && i < now.length; i++) {
      now[i].scrollLeft = was[i].scrollLeft;
    }
  }

  /* Radar and satellite pictures come from somewhere else and carry cache headers
     of their own, so on a page left open all afternoon the picture is still the
     morning's. Asking again under a new query string gets the current one. */
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
    /* A reading that has stopped arriving should look like one, rather than sit
       there being read as current. Counted in polls since the last new record and
       not from the clock, so a station whose clock is a few minutes out is not
       declared dead on the strength of it.

       How long to wait comes from the station: current.json says how far apart its
       records are, and two records' worth of silence is a fault. Guessing that
       would mean calling a ten-minute archive interval a fault every time. Ten
       minutes stands in until the first record says otherwise. */
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

          /* The readings that have an element of their own. Cheap, and on its own
             enough for a station whose current.json is written between records.

             Each arrives twice: as the string the server formatted, and as the number
             behind it. The number goes onto the element, so that a reader who has
             chosen another unit keeps it through the update. */
          document.querySelectorAll('[data-live]').forEach(function (el) {
            var key = el.dataset.live;
            if (data[key] === undefined || data[key] === null) return;
            var target = el.querySelector('[data-unit-value]') || el;
            setLive(target, String(data[key]));
            delete el.dataset.asWritten;
            if (data[key + '_v'] !== undefined && data[key + '_v'] !== null) {
              el.dataset.value = data[key + '_v'];
              if (data[key + '_u']) el.dataset.unit = data[key + '_u'];
            }
          });

          /* The day's high and low, and the times they were reached. They sit either
             side of the bar under the headline and move with it. */
          if (data.day_unit) {
            [['span-end', 'min'], ['span-end--right', 'max']].forEach(function (pair) {
              var el = document.querySelector('.' + pair[0]);
              if (!el || data['day_' + pair[1]] === undefined) return;
              var value = el.querySelector('[data-unit-value]');
              var when = el.querySelector('.faint');
              if (value) value.textContent = data['day_' + pair[1]];
              if (when && data['day_' + pair[1] + 'time']) {
                when.textContent = data['day_' + pair[1] + 'time'];
              }
              delete el.dataset.asWritten;
              el.dataset.value = data['day_' + pair[1] + '_v'];
              el.dataset.unit = data.day_unit;
            });
          }

          /* Back into the reader's unit, since the strings just written are in the
             report's. Returns at once where they have not chosen one. */
          applyUnitsToPanels();
          if (data.outTemp_c !== undefined && data.outTemp_c !== null) {
            var track = document.querySelector('.span-track[data-lo]');
            if (track) track.dataset.now = data.outTemp_c;
            paintSpan();
          }

          if (!data.dateTime_raw || String(data.dateTime_raw) === seen) {
            if (++quiet >= patience) markStale(true);
            return;
          }

          /* A new archive record. The page was re-rendered before current.json was
             written, so everything on it can be brought forward, not just the
             readings. */
          quiet = 0;
          markStale(false);
          seen = String(data.dateTime_raw);
          if (stamp) stamp.dataset.raw = data.dateTime_raw;
          refreshPanels();
          refreshImages(seen);
          refreshCharts();

          /* Anything else on the page keeping state of its own, and wanting to
             know that there is something new to fetch. */
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
      var card = document.querySelector('.panel.headline');
      if (card) card.classList.toggle('is-stale', stale);
      if (stamp) stamp.classList.toggle('is-stale', stale);
    }

    setInterval(tick, seconds * 1000);

    /* A tab in the background has its timers throttled, so what it shows is as old
       as the last time the browser felt like running one. Ask once on the way back
       rather than leaving yesterday's weather up while the viewer reads it. */
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
    measureStickyHead();
    window.addEventListener('resize', measureStickyHead);
    paintSpan();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
