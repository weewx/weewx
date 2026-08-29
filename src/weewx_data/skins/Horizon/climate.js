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

  /* From Celsius and millimetres to whatever is on screen, as a factor and an
     offset. Without a choice by the reader that is the report's own unit, which the
     template worked out and sent along. With one it is theirs.

     Measured at 0 and at 1. Where the answer is null the target is the metric unit
     itself, and the conversion is the identity: a reader who asks for Celsius on a
     page rendered in Fahrenheit must not be given the page's factor, and a reader who
     asks for millimetres on a page rendered in inches must not be given the page's. */
  function backOf(metricUnit, obs, asRendered) {
    if (!CFG.units || !CFG.units.chosen()) return asRendered || [1, 0];
    var target = CFG.units.target(obs, metricUnit);
    if (!target) return [1, 0];
    var at0 = CFG.units.convert(0, metricUnit, obs);
    var at1 = CFG.units.convert(1, metricUnit, obs);
    return (at0 && at1) ? [at1.value - at0.value, at0.value] : [1, 0];
  }

  /* Millimetres are read as whole numbers, inches are not. Where the unit on screen
     is a small fraction of the metric one, a tick without a decimal reads zero. */
  function digitsFor(back) {
    return back[0] < 0.5 ? 1 : 0;
  }

  /* One reading, written in the unit on screen. */
  function scaled(back, digits) {
    return function (v) {
      return (v * back[0] + back[1]).toLocaleString(LOCALE, {
        minimumFractionDigits: digits, maximumFractionDigits: digits
      });
    };
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
  var diagram = null;

  function drawDiagram() {
    var host = document.getElementById('climate-diagram');
    if (!host || !window.echarts) return;
    if (!DATA.temp && !DATA.rain) return;
    /* Called again after a unit change, on the element that still holds the last
       one. Take it down first, or the two are drawn on top of each other. */
    if (diagram) {
      diagram.dispose();
      diagram = null;
    }

    var temps = (DATA.temp || []).slice();
    var rains = (DATA.rain || []).slice();

    /* The values are in Celsius and millimetres. The rainfall axis runs at exactly
       twice the temperature axis, which is the convention, so a bar that falls below
       the line marks a dry month wherever the reader lives. */
    var real = function (list) { return list.filter(function (v) { return v !== null; }); };
    var tMax = Math.max.apply(null, real(temps).concat([0]));
    var tMin = Math.min.apply(null, real(temps).concat([0]));
    var rMax = Math.max.apply(null, real(rains).concat([0]));
    var top = Math.max(tMax, rMax / 2) * 1.1 || 1;
    var bottom = Math.min(tMin, 0) * 1.1;

    var backT = backOf('degree_C', 'outTemp', DATA.tempBack);
    var backR = backOf('mm', 'rain', DATA.rainBack);
    var tempUnit = unitLabel(DATA.tempUnit, 'outTemp', DATA.tempLabel);
    var rainUnit = unitLabel(DATA.rainUnit, 'rain', DATA.rainLabel);

    var family = getComputedStyle(document.body).fontFamily;
    var axisColor = themeColor('--chart-axis', '#8397a7');
    var gridColor = themeColor('--chart-grid', '#e3eaf1');
    var tempColor = themeColor('--hi', '#b2503c');
    var rainColor = themeColor('--lo', '#2f6f9e');

    var series = [];
    if (DATA.rain) {
      series.push({
        name: DATA.rainText || 'Rainfall',
        type: 'bar', yAxisIndex: 1, data: rains,
        itemStyle: { color: rainColor }, barMaxWidth: 40, animation: false
      });
    }
    if (DATA.temp) {
      series.push({
        name: DATA.meanText || 'Mean temperature',
        type: 'line', yAxisIndex: 0, data: temps,
        lineStyle: { color: tempColor, width: 1.5 },
        itemStyle: { color: tempColor }, symbolSize: 5, animation: false
      });
    }

    diagram = echarts.init(host, null, { renderer: 'canvas' });
    diagram.setOption({
      animation: false,
      grid: { left: 58, right: 58, top: 30, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: themeColor('--surface', '#fff'),
        borderColor: themeColor('--border', '#e3eaf1'),
        borderWidth: 1,
        padding: [6, 9],
        extraCssText: 'box-shadow: 0 2px 10px rgba(0,0,0,0.14); border-radius: 6px;',
        textStyle: { color: themeColor('--ink', '#16222e'), fontFamily: family,
                     fontSize: 12 },
        formatter: function (params) {
          var rows = params.map(function (p) {
            var bar = p.seriesType === 'bar';
            var back = bar ? backR : backT;
            var unit = bar ? rainUnit : tempUnit;
            return '<span style="color:' + p.color + '">●</span> ' + p.seriesName
              + ': ' + scaled(back, 1)(p.value) + (unit ? ' ' + unit : '');
          });
          return params[0].axisValueLabel + '<br>' + rows.join('<br>');
        }
      },
      xAxis: {
        type: 'category', data: DATA.months, boundaryGap: true,
        axisLine: { lineStyle: { color: axisColor } },
        axisTick: { show: false }, splitLine: { show: false },
        axisLabel: { color: themeColor('--ink-muted', '#5c7183'), fontFamily: family, fontSize: 12 }
      },
      yAxis: [
        {
          type: 'value', min: bottom, max: top,
          name: tempUnit,
          nameTextStyle: { color: tempColor, fontFamily: family, fontSize: 12 },
          axisLine: { show: false }, axisTick: { show: false },
          splitLine: { lineStyle: { color: gridColor } },
          axisLabel: { color: tempColor, fontFamily: family, fontSize: 12,
                       formatter: scaled(backT, digitsFor(backT)) }
        },
        {
          /* Exactly twice the temperature axis. That is the whole point of the
             diagram: where the rain bar drops below the temperature line, the month
             is dry. */
          type: 'value', min: bottom * 2, max: top * 2,
          name: rainUnit,
          nameTextStyle: { color: rainColor, fontFamily: family, fontSize: 12 },
          axisLine: { show: false }, axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { color: rainColor, fontFamily: family, fontSize: 12,
                       formatter: scaled(backR, digitsFor(backR)) }
        }
      ],
      series: series
    });

    host.style.height = '300px';
    new ResizeObserver(function () {
      if (diagram) diagram.resize();
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
    if (!host || !window.echarts) return;
    if (!DATA.rain || !DATA.et) return;
    if (water) {
      water.dispose();
      water = null;
    }

    var rain = DATA.rain.slice();
    var lost = DATA.et.map(function (v) { return v === null ? null : -v; });
    var kept = rain.map(function (v, i) {
      var e = DATA.et[i];
      return (v === null || e === null) ? null : v - e;
    });

    var backR = backOf('mm', 'rain', DATA.rainBack);
    var rainUnit = unitLabel(DATA.rainUnit, 'rain', DATA.rainLabel);
    var label = scaled(backR, digitsFor(backR));

    var family = getComputedStyle(document.body).fontFamily;
    var axisColor = themeColor('--chart-axis', '#8397a7');
    var gridColor = themeColor('--chart-grid', '#e3eaf1');

    water = echarts.init(host, null, { renderer: 'canvas' });
    water.setOption({
      animation: false,
      grid: { left: 58, right: 12, top: 26, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: themeColor('--surface', '#fff'),
        borderColor: themeColor('--border', '#e3eaf1'),
        borderWidth: 1,
        padding: [6, 9],
        extraCssText: 'box-shadow: 0 2px 10px rgba(0,0,0,0.14); border-radius: 6px;',
        textStyle: { color: themeColor('--ink', '#16222e'), fontFamily: family,
                     fontSize: 12 },
        formatter: function (params) {
          var rows = params.map(function (p) {
            return '<span style="color:' + p.color + '">●</span> ' + p.seriesName
              + ': ' + label(Math.abs(p.value)) + (rainUnit ? ' ' + rainUnit : '');
          });
          return params[0].axisValueLabel + '<br>' + rows.join('<br>');
        }
      },
      xAxis: {
        type: 'category', data: DATA.months, boundaryGap: true,
        axisLine: { lineStyle: { color: axisColor } },
        axisTick: { show: false }, splitLine: { show: false },
        axisLabel: { color: themeColor('--ink-muted', '#5c7183'), fontFamily: family, fontSize: 12 }
      },
      yAxis: {
        type: 'value',
        name: rainUnit,
        nameTextStyle: { color: axisColor, fontFamily: family, fontSize: 12 },
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: gridColor } },
        axisLabel: { color: themeColor('--ink-muted', '#5c7183'), fontFamily: family,
                     fontSize: 12, formatter: label }
      },
      series: [
        { name: DATA.rainText || 'Rainfall',
          type: 'bar', data: rain, barMaxWidth: 30,
          itemStyle: { color: themeColor('--lo', '#2f6f9e') }, animation: false },
        { name: DATA.etText || 'Evapotranspiration',
          type: 'bar', data: lost, barMaxWidth: 30,
          barGap: '-100%',
          itemStyle: { color: themeColor('--sun', '#a8761c') }, animation: false },
        { name: DATA.keptText || 'Water balance',
          type: 'line', data: kept, symbolSize: 5,
          lineStyle: { color: themeColor('--ink', '#16222e'), width: 1.5 },
          itemStyle: { color: themeColor('--ink', '#16222e') }, animation: false }
      ]
    });

    host.style.height = '260px';
    new ResizeObserver(function () {
      if (water) water.resize();
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
