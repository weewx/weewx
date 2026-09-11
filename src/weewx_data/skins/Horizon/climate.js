/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 *
 * Draws the three charts of the climate page (the climate diagram, the water
 * balance and the day-by-day heat map) and switches the tabs above the heat map
 * (#heat-tabs) and above the whole-archive tables (#record-tabs).
 * climate.inc writes the data into the page, in the script element #climate-data.
 */

(function () {
  'use strict';

  var LOCALE = document.documentElement.lang || undefined;
  var CFG = window.HORIZON || {};
  var DATA = null;

  /* Returns the data in #climate-data, or null. The data are parsed again on every
     draw, because horizon.js replaces #climate-data on each new archive record. */
  function readData() {
    var node = document.getElementById('climate-data');
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (e) {
      return null;
    }
  }

  /* The key of the HEAT entry that the heat map shows. The choice is kept in this
     variable and not read from the tabs, because horizon.js replaces the tabs on
     each new archive record, and the new tabs mark the first entry as selected.
     draw() marks the chosen tab again through markHeatTabs(). */
  var heatKind = null;

  /* Returns `value`, which is in `unit`, converted to the unit shown. Here and below,
     'the unit shown' is the unit the page shows for `obsType`: from the unit system
     the reader chose or, where the reader chose none, from the report unit system. */
  function inReaderUnit(value, unit, obsType) {
    if (value === null || value === undefined) return value;
    if (!CFG.units || !unit) return value;
    var out = CFG.units.convert(value, unit, obsType);
    return out ? out.value : value;
  }

  /* Returns the unit shown for a value in `unit`. */
  function readerUnit(unit, obsType) {
    if (!CFG.units || !unit) return unit;
    return CFG.units.target(obsType, unit) || unit;
  }

  /* Returns the label of the unit shown for a value in `unit`. Where no conversion
     applies, the label is `asRendered`, which climate.inc wrote for the report unit
     system. */
  function unitLabel(unit, obsType, asRendered) {
    if (CFG.units && unit) {
      var out = CFG.units.convert(1, unit, obsType);
      if (out) return out.label;
    }
    return asRendered || '';
  }

  /* Returns [factor, offset] that convert a value in `metricUnit`, degree_C or mm,
     into the unit shown. Where the reader has chosen no unit system, the answer is
     `asRendered`, which climate.inc computed for the report unit system. Otherwise
     the answer is measured with CFG.units at 0 and at 1, which is exact because every
     conversion between these units is linear.

     CFG.units.target() returns null where the unit system the reader chose uses
     `metricUnit` itself. The answer is then [1, 0], not `asRendered`: a reader who
     chooses METRICWX on a page in US units must see degree_C and mm. */
  function backOf(metricUnit, obs, asRendered) {
    if (!CFG.units || !CFG.units.chosen()) return asRendered || [1, 0];
    var target = CFG.units.target(obs, metricUnit);
    if (!target) return [1, 0];
    var at0 = CFG.units.convert(0, metricUnit, obs);
    var at1 = CFG.units.convert(1, metricUnit, obs);
    return (at0 && at1) ? [at1.value - at0.value, at0.value] : [1, 0];
  }

  /* Returns the number of decimals for the axis labels: one where a metric unit is
     less than half of the unit shown, as a millimetre is of an inch, and none
     otherwise. Without a decimal, axis labels 10 mm apart would read 0, 0, 1, 1 in
     inches. */
  function digitsFor(back) {
    return back[0] < 0.5 ? 1 : 0;
  }

  /* Returns a function that writes a metric value in the unit shown, with `digits`
     decimals. */
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

  /* -------------------------------------------------------- climate diagram */

  /* The climate diagram of Walter and Lieth (see climate.inc). Both axes are laid
     out in degree_C and mm, the units in which climate.inc writes the lists. Only
     the axis labels and the tooltip are converted to the unit shown, through
     backOf(). */
  var diagram = null;

  function drawDiagram() {
    var host = document.getElementById('climate-diagram');
    if (!host || !window.echarts) return;
    if (!DATA.temp && !DATA.rain) return;
    /* After a unit change, #climate-diagram still holds the previous chart.
       echarts.init() would return that chart, and setOption() would merge the new
       option into the previous one, keeping a series the new option leaves out. */
    if (diagram) {
      diagram.dispose();
      diagram = null;
    }

    var temps = (DATA.temp || []).slice();
    var rains = (DATA.rain || []).slice();

    /* The temperature axis reaches up to the warmest month's mean or to half the
       wettest month's rainfall, whichever is higher, because the rainfall axis at
       twice the scale must hold the wettest month's bar. */
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
          /* The rainfall axis, at twice the scale of the temperature axis. */
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

  /* The water balance, month by month: rainfall as a bar above zero,
     evapotranspiration as a bar below zero, and their difference as a line. One bar
     of the difference alone would put a dry month and a month with much rain and
     much evapotranspiration both near zero. */
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
          /* In the same column as the rainfall bar, below zero. */
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

  /* --------------------------------------------------------------- heat map */

  /* The heat map: one square per day, a column per week and a row per weekday. Each
     square is an element with its own title, which the browser shows as a tooltip;
     a canvas would have no title per day.

     Each HEAT entry names the list in DATA, the key in DATA of that list's unit, the
     observation type, and whether the list is coloured as rain or as temperature.
     A temperature takes its colour from CFG.tempColour, which mixes the colours
     --warm-0 to --warm-8 that also tint the outside temperature tile. */
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

    /* Each day keeps two values: `shown` in the unit shown, for the title and the
       legend, and `raw` in the report unit system, for the colour. toCelsius()
       below turns `raw` into the degree_C that CFG.tempColour takes, which saves a
       conversion back from the unit shown. */
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
    /* The rain scale starts at 0, not at the smallest daily total. */
    if (spec.kind === 'rain') lo = 0;

    var toCelsius = function (v) {
      if (unit === 'degree_F') return (v - 32) / 1.8;
      if (unit === 'degree_K') return v - 273.15;
      return v;
    };

    /* WeeWX numbers the weekdays from Monday = 0, JavaScript from Sunday = 0. */
    var startDow = DATA.weekStart === undefined ? 0 : Number(DATA.weekStart);
    var jsStart = (startDow + 1) % 7;

    var first = new Date(DATA.year, 0, 1);
    var last = new Date(DATA.year, 11, 31);
    /* The heat map starts on the first day of the week that holds 1 January, so that
       every column is a whole week and every row is one weekday. */
    var cursor = new Date(first);
    cursor.setDate(cursor.getDate() - ((first.getDay() - jsStart + 7) % 7));

    /* 7 January 2024 was a Sunday, so day 7 + n of that month is weekday n in
       JavaScript's numbering. */
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
            /* `--hm` is the fourth root of the day's share of the range, because most
               of a year's rain falls on a few days. On a linear scale nearly every
               rainy day would get the palest colour. */
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
      /* Only every other weekday gets a label, because seven labels do not fit in
         the height of seven squares. */
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

  /* ------------------------------------------------------------------- tabs */

  /* One click listener on the document serves both sets of tabs. horizon.js
     replaces the panels that hold the tabs on each new archive record, and a
     listener on an element inside a replaced panel is lost with that element. */
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

  /* ------------------------------------------------------------------ start */

  function draw() {
    DATA = readData();
    if (!DATA) return;
    markHeatTabs();
    drawDiagram();
    drawWater();
    drawHeatmap();
  }

  /* horizon.js has replaced the panels and #climate-data after a new archive
     record, and the new chart elements are empty. */
  document.addEventListener('horizon:panels', draw);

  /* The reader has chosen another unit system. */
  document.addEventListener('horizon:units', draw);

  /* draw() runs at once. scripts.inc loads this file after the page's markup and
     after horizon.js, which provides CFG.units and CFG.tempColour. */
  draw();
})();
