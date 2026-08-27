/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 *
 * The two pictures on the climate page, and the switch between the tables under them.
 *
 * The data are in the page, in a script tag the server filled in. Nothing is fetched:
 * a year is twelve months and three hundred and sixty-five days, which the template
 * had already read in order to draw the tables.
 */

(function () {
  'use strict';

  var LOCALE = document.documentElement.lang || undefined;
  var CFG = window.HORIZON || {};
  var DATA = null;

  /* Read again rather than once. The live update replaces the script tag along with
     the panels, so what was parsed at load is last cycle's numbers. */
  function readData() {
    var node = document.getElementById('climate-data');
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (e) {
      return null;
    }
  }

  /* Which of the four the calendar is showing. Kept here rather than read off the
     buttons, so it survives the buttons being replaced. */
  var heatKind = null;

  /* One reading in the unit the reader chose, or unchanged where they chose none.
     The conversion lives in horizon.js, which owns the table and the choice. */
  function inReaderUnit(value, unit, obsType) {
    if (value === null || value === undefined) return value;
    if (!CFG.units || !unit) return value;
    var out = CFG.units.convert(value, unit, obsType);
    return out ? out.value : value;
  }

  function readerUnit(unit, obsType) {
    if (!CFG.units || !unit) return unit;
    return CFG.units.target(obsType, unit) || unit;
  }

  /* The label to write beside a reading. Where the reader has chosen a unit, it is
     that unit's; otherwise it is the one the server rendered the page in, which the
     template sent along. */
  function unitLabel(unit, obsType, asRendered) {
    if (CFG.units && unit) {
      var out = CFG.units.convert(1, unit, obsType);
      if (out) return out.label;
    }
    return asRendered || '';
  }

  function themeColor(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  /* ------------------------------------------------------------ the year's shape */

  /* A climate diagram, after Walter and Lieth: the month's mean temperature as a
     line, the month's rainfall as bars behind it, and the rainfall axis running at
     twice the temperature axis. Where the bars fall below the line, the month is dry.
     That crossing is why the two are drawn together rather than side by side.

     The 2:1 ratio is the convention, and it is stated in degrees Celsius: 10 degrees
     against 20 mm. On a page in Fahrenheit and inches the same ratio would put the
     crossing somewhere else, so the axes are scaled from the data instead, and the
     rule is applied to the axis rather than to the numbers. */
  /* What a tooltip shows for one month. 'rows' is [label, value, unit, colour], and a
     null value is left out rather than written as a gap.

     The box and the touch handling come from horizon.js, so reading these charts with
     a finger works the same way as reading the ones on the front page. */
  function monthTip(rows) {
    return function (u, idx) {
      var written = rows(idx).filter(function (r) {
        return r[1] !== null && r[1] !== undefined && !isNaN(r[1]);
      });
      if (!written.length) return null;
      var digits = function (v) {
        return Math.abs(v) >= 100 ? 0 : 1;
      };
      return '<div class="t-time">' + escapeHtml(DATA.months[idx] || '') + '</div>'
        + written.map(function (r) {
          return '<div class="t-row" style="color:' + r[3] + '">'
            + '<i></i><span style="color:var(--ink)">' + escapeHtml(r[0]) + '</span>'
            + '<b style="color:var(--ink)">'
            + r[1].toLocaleString(LOCALE, {
                minimumFractionDigits: digits(r[1]), maximumFractionDigits: digits(r[1])
              })
            + (r[2] ? ' ' + escapeHtml(r[2]) : '') + '</b></div>';
        }).join('');
    };
  }

  var diagram = null;

  function drawDiagram() {
    var host = document.getElementById('climate-diagram');
    if (!host || !window.uPlot) return;
    if (!DATA.temp && !DATA.rain) return;
    /* Called again after a unit change, on the element that still holds the last
       one. Take it down first, or the two are drawn on top of each other. */
    if (diagram) {
      diagram.destroy();
      diagram = null;
    }
    host.innerHTML = '';

    var n = DATA.months.length;
    var x = [];
    for (var i = 0; i < n; i++) x.push(i);

    var temps = (DATA.temp || []).map(function (v) { return v === null ? null : v; });
    var rains = (DATA.rain || []).map(function (v) { return v === null ? null : v; });

    /* The values are in Celsius and millimetres. The rainfall axis runs at exactly
       twice the temperature axis, which is the convention, so a bar that falls below
       the line marks a dry month wherever the reader lives. */
    var real = function (list) { return list.filter(function (v) { return v !== null; }); };
    var tMax = Math.max.apply(null, real(temps).concat([0]));
    var tMin = Math.min.apply(null, real(temps).concat([0]));
    var rMax = Math.max.apply(null, real(rains).concat([0]));
    var top = Math.max(tMax, rMax / 2) * 1.1 || 1;
    var bottom = Math.min(tMin, 0) * 1.1;

    /* Back to the unit the page reads in, for the labels only. The plot itself stays
       metric, because that is what the 2:1 rule is stated in. */
    /* From Celsius and millimetres to whatever is on screen, as a factor and an
       offset. Without a choice by the reader that is the report's own unit, which the
       template worked out and sent along. With one it is theirs.

       Measured at 0 and at 1. Where the answer is null the target is the metric unit
       itself, and the conversion is the identity: a reader who asks for Celsius on a
       page rendered in Fahrenheit must not be given the page's factor. */
    var backOf = function (metricUnit, obs, asRendered) {
      if (!CFG.units || !CFG.units.chosen()) return asRendered || [1, 0];
      var target = CFG.units.target(obs, metricUnit);
      if (!target) return [1, 0];
      var at0 = CFG.units.convert(0, metricUnit, obs);
      var at1 = CFG.units.convert(1, metricUnit, obs);
      return (at0 && at1) ? [at1.value - at0.value, at0.value] : [1, 0];
    };
    var backT = backOf('degree_C', 'outTemp', DATA.tempBack);
    var backR = backOf('mm', 'rain', DATA.rainBack);
    var label = function (back, digits) {
      return function (u, splits) {
        return splits.map(function (v) {
          return (v * back[0] + back[1]).toLocaleString(LOCALE, {
            minimumFractionDigits: digits, maximumFractionDigits: digits
          });
        });
      };
    };

    var series = [{}];
    var data = [x];
    if (DATA.rain) {
      series.push({
        label: DATA.rainLabel,
        scale: 'r',
        paths: uPlot.paths.bars({ size: [0.62, 40] }),
        fill: function () { return themeColor('--lo', '#2f6f9e'); },
        stroke: function () { return themeColor('--lo', '#2f6f9e'); },
        width: 0,
        points: { show: false }
      });
      data.push(rains);
    }
    if (DATA.temp) {
      series.push({
        label: DATA.tempLabel,
        scale: 't',
        stroke: function () { return themeColor('--hi', '#b2503c'); },
        width: 2,
        points: { show: true, size: 5 }
      });
      data.push(temps);
    }

    var opts = {
      width: host.clientWidth || 600,
      height: 300,
      padding: [16, 8, 0, 0],
      legend: { show: false },
      cursor: { drag: { x: false, y: false } },
      scales: {
        x: { time: false, range: [-0.6, n - 0.4] },
        t: { range: function () { return [bottom, top]; } },
        r: { range: function () { return [bottom * 2, top * 2]; } }
      },
      axes: [
        {
          stroke: function () { return themeColor('--chart-axis', '#8397a7'); },
          grid: { show: false },
          ticks: { show: false },
          font: '11px ' + getComputedStyle(document.body).fontFamily,
          splits: function () { return x; },
          values: function () { return DATA.months; }
        },
        {
          scale: 't',
          label: unitLabel(DATA.tempUnit, 'outTemp', DATA.tempLabel),
          labelSize: 22,
          labelFont: '11px ' + getComputedStyle(document.body).fontFamily,
          stroke: function () { return themeColor('--hi', '#b2503c'); },
          grid: {
            stroke: function () { return themeColor('--chart-grid', '#e3eaf1'); },
            width: 1
          },
          ticks: { show: false },
          font: '11px ' + getComputedStyle(document.body).fontFamily,
          size: 50,
          values: label(backT, 0)
        },
        {
          scale: 'r',
          side: 1,
          label: unitLabel(DATA.rainUnit, 'rain', DATA.rainLabel),
          labelSize: 22,
          labelFont: '11px ' + getComputedStyle(document.body).fontFamily,
          stroke: function () { return themeColor('--lo', '#2f6f9e'); },
          grid: { show: false },
          ticks: { show: false },
          font: '11px ' + getComputedStyle(document.body).fontFamily,
          size: 50,
          values: label(backR, backR[0] < 0.5 ? 1 : 0)
        }
      ],
      series: series,
      plugins: CFG.tooltip ? [CFG.tooltip(monthTip(function (idx) {
        var tLabel = unitLabel(DATA.tempUnit, 'outTemp', DATA.tempLabel);
        var rLabel = unitLabel(DATA.rainUnit, 'rain', DATA.rainLabel);
        var out = [];
        if (DATA.temp && DATA.temp[idx] !== null) {
          out.push([DATA.meanText || 'Mean temperature',
                    DATA.temp[idx] * backT[0] + backT[1], tLabel,
                    themeColor('--hi', '#b2503c')]);
        }
        if (DATA.rain && DATA.rain[idx] !== null) {
          out.push([DATA.rainText || 'Rainfall',
                    DATA.rain[idx] * backR[0] + backR[1], rLabel,
                    themeColor('--lo', '#2f6f9e')]);
        }
        return out;
      }))] : []
    };

    diagram = new uPlot(opts, data, host);
    new ResizeObserver(function () {
      if (diagram) diagram.setSize({ width: host.clientWidth, height: 300 });
    }).observe(host);
  }

  /* ------------------------------------------------------------ water balance */

  /* What fell against what left again, month by month. Rain stands above the line,
     evapotranspiration below it, and the line between them is what the ground kept.

     Two bars and a line rather than one bar of the difference: a dry month and a
     month where a lot fell and a lot evaporated both come out near zero, and they are
     not the same month. */
  var water = null;

  function drawWater() {
    var host = document.getElementById('climate-water');
    if (!host || !window.uPlot) return;
    if (!DATA.rain || !DATA.et) return;
    if (water) {
      water.destroy();
      water = null;
    }
    host.innerHTML = '';

    var n = DATA.months.length;
    var x = [];
    for (var i = 0; i < n; i++) x.push(i);

    var rain = DATA.rain.map(function (v) { return v === null ? null : v; });
    var lost = DATA.et.map(function (v) { return v === null ? null : -v; });
    var kept = rain.map(function (v, i) {
      var e = DATA.et[i];
      return (v === null || e === null) ? null : v - e;
    });

    var real = function (list) { return list.filter(function (v) { return v !== null; }); };
    var top = Math.max.apply(null, real(rain).concat(real(kept)).concat([0])) * 1.1 || 1;
    var bottom = Math.min.apply(null, real(lost).concat(real(kept)).concat([0])) * 1.1;

    /* Millimetres in, the reader's unit on the axis. Same rule as the diagram above. */
    var back = [1, 0];
    if (CFG.units && CFG.units.chosen() && CFG.units.target('rain', 'mm')) {
      var a = CFG.units.convert(0, 'mm', 'rain');
      var b = CFG.units.convert(1, 'mm', 'rain');
      if (a && b) back = [b.value - a.value, a.value];
    } else if (!CFG.units || !CFG.units.chosen()) {
      back = DATA.rainBack || [1, 0];
    }

    var opts = {
      width: host.clientWidth || 600,
      height: 260,
      padding: [16, 8, 0, 0],
      legend: { show: false },
      cursor: { drag: { x: false, y: false } },
      scales: { x: { time: false, range: [-0.6, n - 0.4] },
                y: { range: function () { return [bottom, top]; } } },
      axes: [
        {
          stroke: function () { return themeColor('--chart-axis', '#8397a7'); },
          grid: { show: false },
          ticks: { show: false },
          font: '11px ' + getComputedStyle(document.body).fontFamily,
          splits: function () { return x; },
          values: function () { return DATA.months; }
        },
        {
          label: unitLabel(DATA.rainUnit, 'rain', DATA.rainLabel),
          labelSize: 22,
          labelFont: '11px ' + getComputedStyle(document.body).fontFamily,
          stroke: function () { return themeColor('--chart-axis', '#8397a7'); },
          grid: {
            stroke: function () { return themeColor('--chart-grid', '#e3eaf1'); },
            width: 1
          },
          ticks: { show: false },
          font: '11px ' + getComputedStyle(document.body).fontFamily,
          size: 50,
          values: function (u, splits) {
            return splits.map(function (v) {
              return (v * back[0] + back[1]).toLocaleString(LOCALE, {
                minimumFractionDigits: back[0] < 0.5 ? 1 : 0,
                maximumFractionDigits: back[0] < 0.5 ? 1 : 0
              });
            });
          }
        }
      ],
      plugins: CFG.tooltip ? [CFG.tooltip(monthTip(function (idx) {
        var label = unitLabel(DATA.rainUnit, 'rain', DATA.rainLabel);
        var scaled = function (v) { return v === null ? null : v * back[0] + back[1]; };
        return [
          [DATA.rainText || 'Rainfall', scaled(rain[idx]), label,
           themeColor('--lo', '#2f6f9e')],
          [DATA.etText || 'Evapotranspiration',
           DATA.et[idx] === null ? null : scaled(DATA.et[idx]), label,
           themeColor('--sun', '#a8761c')],
          [DATA.keptText || 'Water balance', scaled(kept[idx]), label,
           themeColor('--ink', '#16222e')]
        ];
      }))] : [],
      series: [
        {},
        {
          paths: uPlot.paths.bars({ size: [0.5, 30] }),
          fill: function () { return themeColor('--lo', '#2f6f9e'); },
          stroke: function () { return themeColor('--lo', '#2f6f9e'); },
          width: 0,
          points: { show: false }
        },
        {
          paths: uPlot.paths.bars({ size: [0.5, 30] }),
          fill: function () { return themeColor('--sun', '#a8761c'); },
          stroke: function () { return themeColor('--sun', '#a8761c'); },
          width: 0,
          points: { show: false }
        },
        {
          stroke: function () { return themeColor('--ink', '#16222e'); },
          width: 2,
          points: { show: true, size: 5 }
        }
      ]
    };

    water = new uPlot(opts, [x, rain, lost, kept], host);
    new ResizeObserver(function () {
      if (water) water.setSize({ width: host.clientWidth, height: 260 });
    }).observe(host);
  }

  /* --------------------------------------------------------------- day by day */

  /* One square per day, in the shape a calendar has: a column per week, a row per
     weekday. Drawn as elements rather than onto a canvas, so each day keeps its own
     tooltip and its own place in the page for a screen reader.

     Four things can be shown in it. Rain runs from the page's dry colour to its wet
     one. The three temperatures use the same nine steps as the reading at the top of
     the front page, so a warm day is the same colour wherever it appears. */
  var HEAT = {
    rain: { list: 'dayRain', unit: 'rainUnit', obs: 'rain', kind: 'rain' },
    temp: { list: 'dayTemp', unit: 'tempUnit', obs: 'outTemp', kind: 'temp' },
    tmin: { list: 'dayMin', unit: 'tempUnit', obs: 'outTemp', kind: 'temp' },
    tmax: { list: 'dayMax', unit: 'tempUnit', obs: 'outTemp', kind: 'temp' }
  };

  function availableHeat() {
    return Object.keys(HEAT).filter(function (key) {
      var list = DATA[HEAT[key].list];
      return list && list.some(function (v) { return v !== null; });
    });
  }

  function drawHeatmap() {
    var host = document.getElementById('climate-heatmap');
    if (!host || !DATA || !DATA.dayStart || !DATA.dayStart.length) return;

    var kinds = availableHeat();
    if (!kinds.length) return;
    if (kinds.indexOf(heatKind) < 0) heatKind = kinds[0];
    var spec = HEAT[heatKind];
    var values = DATA[spec.list] || [];
    var unit = DATA[spec.unit];
    var shown = readerUnit(unit, spec.obs);
    var label = unitLabel(unit, spec.obs,
                          spec.kind === 'rain' ? DATA.rainLabel : DATA.tempLabel);

    /* Each day twice: as the reader sees it, and as the data hold it. The colour
       scale for temperature is defined in Celsius, and converting back from what is
       on screen would go through two conversions to arrive where it started. */
    var byDay = {};
    var lo = null, hi = null;
    DATA.dayStart.forEach(function (start, i) {
      var raw = values[i];
      if (raw === null || raw === undefined) return;
      var v = inReaderUnit(raw, unit, spec.obs);
      byDay[isoDay(new Date(start * 1000))] = { shown: v, raw: raw };
      if (lo === null || v < lo) lo = v;
      if (hi === null || v > hi) hi = v;
    });
    if (lo === null) return;
    /* Rain is measured from nothing, not from the driest day of the year. */
    if (spec.kind === 'rain') lo = 0;

    var toCelsius = function (v) {
      if (unit === 'degree_F') return (v - 32) / 1.8;
      if (unit === 'degree_K') return v - 273.15;
      return v;
    };

    var startDow = DATA.weekStart === undefined ? 0 : Number(DATA.weekStart);
    var jsStart = (startDow + 1) % 7;

    var first = new Date(DATA.year, 0, 1);
    var last = new Date(DATA.year, 11, 31);
    /* Back to the start of the week the year begins in, so every column is a whole
       week and the rows line up with the weekday names. */
    var cursor = new Date(first);
    cursor.setDate(cursor.getDate() - ((first.getDay() - jsStart + 7) % 7));

    var names = [];
    for (var i = 0; i < 7; i++) {
      names.push(new Date(2024, 0, 7 + ((jsStart + i) % 7))
        .toLocaleDateString(LOCALE, { weekday: 'short' }));
    }

    var digits = (CFG.units && CFG.units.decimals(shown, 1)) || 1;
    var write = function (v) {
      return v.toLocaleString(LOCALE, {
        minimumFractionDigits: digits, maximumFractionDigits: digits
      });
    };

    var cells = [];
    var monthMarks = [];
    var column = 0;
    var span = (hi - lo) || 1;
    while (cursor <= last) {
      for (var row = 0; row < 7; row++) {
        var inYear = cursor.getFullYear() === DATA.year;
        var iso = isoDay(cursor);
        var value = byDay[iso];
        if (!inYear) {
          cells.push('<span class="hm-cell hm-outside" style="grid-column:'
            + (column + 2) + ';grid-row:' + (row + 1) + '"></span>');
        } else if (value === undefined) {
          cells.push('<span class="hm-cell hm-empty" style="grid-column:'
            + (column + 2) + ';grid-row:' + (row + 1) + '"></span>');
        } else {
          var style = 'grid-column:' + (column + 2) + ';grid-row:' + (row + 1);
          if (spec.kind === 'temp' && CFG.tempColour) {
            style += ';background:' + CFG.tempColour(toCelsius(value.raw));
          } else {
            /* The fourth root of the share of the range. On a linear scale nearly
               every wet day lands in the palest step, because most of a year's rain
               falls on few of its days. */
            style += ';--hm: '
              + Math.pow(Math.max(0, value.shown - lo) / span, 0.25).toFixed(3);
          }
          var title = cursor.toLocaleDateString(LOCALE, {
            weekday: 'long', day: 'numeric', month: 'long'
          }) + ': ' + write(value.shown) + (label ? ' ' + label : '');
          cells.push('<span class="hm-cell" style="' + style + '"'
            + ' title="' + escapeHtml(title) + '"></span>');
          if (cursor.getDate() === 1) {
            monthMarks.push('<span class="hm-month" style="grid-column:' + (column + 2)
              + '">' + escapeHtml(cursor.toLocaleDateString(LOCALE, { month: 'short' }))
              + '</span>');
          }
        }
        cursor.setDate(cursor.getDate() + 1);
      }
      column++;
    }

    var labels = names.map(function (name, i) {
      /* Every other one. Seven labels in the height of seven squares do not fit. */
      return '<span class="hm-dow" style="grid-row:' + (i + 1) + '">'
        + (i % 2 === 0 ? escapeHtml(name) : '') + '</span>';
    });

    var ramp = spec.kind === 'temp' ? 'hm-ramp hm-ramp--temp' : 'hm-ramp';
    host.innerHTML =
      '<div class="hm-months" style="grid-template-columns: 2.2rem repeat('
      + column + ', 1fr)">' + monthMarks.join('') + '</div>'
      + '<div class="hm-grid" style="grid-template-columns: 2.2rem repeat('
      + column + ', 1fr)">' + labels.join('') + cells.join('') + '</div>'
      + '<div class="hm-key"><span>' + escapeHtml(write(lo)) + '</span>'
      + '<span class="' + ramp + '"></span><span>'
      + escapeHtml(write(hi) + (label ? ' ' + label : '')) + '</span></div>';
  }

  function isoDay(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
      + '-' + String(d.getDate()).padStart(2, '0');
  }

  function fmt(v) {
    return v.toLocaleString(LOCALE, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ------------------------------------------------------------- the record */

  /* ------------------------------------------------------------- switching */

  /* Both sets of tabs are bound to the document rather than to the tab strip. The
     live update replaces whole panels, and a listener bound to an element inside one
     goes with it: the tabs would still be drawn and no longer do anything. */
  document.addEventListener('click', function (e) {
    var record = e.target.closest('#record-tabs button[data-record]');
    if (record) {
      var wanted = record.dataset.record;
      document.querySelectorAll('#record-tabs button[data-record]').forEach(function (b) {
        b.setAttribute('aria-selected', String(b.dataset.record === wanted));
      });
      document.querySelectorAll('[data-record-panel]').forEach(function (panel) {
        panel.hidden = panel.dataset.recordPanel !== wanted;
      });
      return;
    }
    var heat = e.target.closest('#heat-tabs button[data-heat]');
    if (heat) {
      heatKind = heat.dataset.heat;
      markHeatTabs();
      drawHeatmap();
    }
  });

  function markHeatTabs() {
    document.querySelectorAll('#heat-tabs button[data-heat]').forEach(function (b) {
      b.setAttribute('aria-selected', String(b.dataset.heat === heatKind));
    });
  }

  /* ---------------------------------------------------------------- years */

  /* Stepping back through the record. Each year is its own page, written once when
     the year ended, so the picker fetches the wanted one and puts its panels in place
     of these rather than loading it. What the reader has open stays open: the tabs,
     the unit, the scroll position.

     A year is around six kilobytes over the wire. Holding every year in every page
     would be a quarter of a megabyte on a station with fourteen years of record, and
     the page is rendered again on every report cycle. */
  var loading = false;

  function setupYearPicker() {
    var picker = document.getElementById('climate-year');
    if (!picker) return;
    picker.addEventListener('change', function () {
      if (!picker.value || loading) return;
      showYear(picker.value, true);
    });

    /* Back and forward, once a year has been fetched. */
    window.addEventListener('popstate', function (e) {
      if (e.state && e.state.climateYear) showYear(e.state.climateYear, false);
    });
  }

  function showYear(url, push) {
    loading = true;
    var body = document.querySelector('.wrap');
    if (body) body.setAttribute('aria-busy', 'true');

    fetch(url, { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        loading = false;
        if (body) body.removeAttribute('aria-busy');
        if (!html) return;
        var fresh = new DOMParser().parseFromString(html, 'text/html');

        /* The panels, and the data block that feeds the pictures. Same mechanism the
           live update uses, so a panel that gains a 'data-live-panel' tomorrow is
           carried across here without anything being added. */
        document.querySelectorAll('[data-live-panel]').forEach(function (old) {
          var next = fresh.querySelector('[data-live-panel="' + old.dataset.livePanel + '"]');
          if (next && old.parentNode) {
            old.parentNode.replaceChild(document.importNode(next, true), old);
          }
        });

        /* The heading says which year is on screen. */
        var head = document.querySelector('.masthead h1');
        var freshHead = fresh.querySelector('.masthead h1');
        if (head && freshHead) head.textContent = freshHead.textContent;
        document.title = fresh.title || document.title;

        if (push) {
          history.pushState({ climateYear: url }, '', url);
        }
        draw();
      })
      .catch(function () {
        loading = false;
        if (body) body.removeAttribute('aria-busy');
        /* The page is still there and still readable. Fall back to loading it. */
        window.location = url;
      });
  }

  /* ------------------------------------------------------------------ start */

  function draw() {
    DATA = readData();
    if (!DATA) return;
    markHeatTabs();
    drawDiagram();
    drawWater();
    drawHeatmap();
  }

  /* The panels have been replaced, taking the pictures with them. Draw them again,
     from the data that arrived with them. */
  document.addEventListener('horizon:panels', draw);

  /* The reader has changed unit. Nothing has to be fetched; the same numbers are
     shown in another one. */
  document.addEventListener('horizon:units', draw);

  function start() {
    setupYearPicker();
    draw();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
