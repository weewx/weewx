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

  var node = document.getElementById('climate-data');
  if (!node) return;

  var DATA;
  try {
    DATA = JSON.parse(node.textContent);
  } catch (e) {
    return;
  }

  var LOCALE = document.documentElement.lang || undefined;

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
  function drawDiagram() {
    var host = document.getElementById('climate-diagram');
    if (!host || !window.uPlot) return;
    if (!DATA.temp && !DATA.rain) return;

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
    var backT = DATA.tempBack || [1, 0];
    var backR = DATA.rainBack || [1, 0];
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
          label: DATA.tempLabel,
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
          label: DATA.rainLabel,
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
      series: series
    };

    var plot = new uPlot(opts, data, host);
    new ResizeObserver(function () {
      plot.setSize({ width: host.clientWidth, height: 300 });
    }).observe(host);
  }

  /* --------------------------------------------------------------- day by day */

  /* One square per day, in the shape a calendar has: a column per week, a row per
     weekday. Drawn as elements rather than as a canvas so that each day keeps its
     own tooltip and its own place in the page for a screen reader. */
  function drawHeatmap() {
    var host = document.getElementById('climate-heatmap');
    if (!host || !DATA.dayStart || !DATA.dayStart.length) return;

    /* Two lists of the same length: when each day began, and what fell on it. */
    var byDay = {};
    var most = 0;
    DATA.dayStart.forEach(function (start, i) {
      var value = DATA.dayRain[i];
      if (value === null || value === undefined) return;
      byDay[isoDay(new Date(start * 1000))] = value;
      if (value > most) most = value;
    });
    if (!most) {
      host.innerHTML = '<p class="chart-empty">'
        + escapeHtml(DATA.noRain || '') + '</p>';
      return;
    }

    var startDow = DATA.weekStart === undefined ? 0 : Number(DATA.weekStart);
    var jsStart = (startDow + 1) % 7;

    var first = new Date(DATA.year, 0, 1);
    var last = new Date(DATA.year, 11, 31);
    /* Back up to the start of the week the year begins in, so every column is a whole
       week and the rows line up with the weekday names. */
    var cursor = new Date(first);
    cursor.setDate(cursor.getDate() - ((first.getDay() - jsStart + 7) % 7));

    var names = [];
    for (var i = 0; i < 7; i++) {
      names.push(new Date(2024, 0, 7 + ((jsStart + i) % 7))
        .toLocaleDateString(LOCALE, { weekday: 'short' }));
    }

    var cells = [];
    var monthMarks = [];
    var column = 0;
    while (cursor <= last) {
      for (var row = 0; row < 7; row++) {
        var inYear = cursor.getFullYear() === DATA.year;
        var iso = isoDay(cursor);
        var value = byDay[iso];
        if (!inYear) {
          cells.push('<span class="hm-cell hm-outside" style="grid-column:'
            + (column + 2) + ';grid-row:' + (row + 1) + '"></span>');
        } else {
          /* The scale is the fourth root of the share of the wettest day. A linear
             scale on rainfall leaves almost every day in the palest step, because
             most rain falls on few days. */
          var share = value ? Math.pow(value / most, 0.25) : 0;
          var title = cursor.toLocaleDateString(LOCALE, {
            weekday: 'long', day: 'numeric', month: 'long'
          }) + (value ? ': ' + fmt(value) + ' ' + DATA.rainLabel : '');
          cells.push('<span class="hm-cell" style="grid-column:' + (column + 2)
            + ';grid-row:' + (row + 1)
            + ';--hm: ' + share.toFixed(3) + '"'
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

    host.innerHTML =
      '<div class="hm-months" style="grid-template-columns: 2.2rem repeat('
      + column + ', 1fr)">' + monthMarks.join('') + '</div>'
      + '<div class="hm-grid" style="grid-template-columns: 2.2rem repeat('
      + column + ', 1fr)">' + labels.join('') + cells.join('') + '</div>'
      + '<div class="hm-key"><span>' + escapeHtml(fmt(0)) + '</span>'
      + '<span class="hm-ramp"></span><span>'
      + escapeHtml(fmt(most) + ' ' + DATA.rainLabel) + '</span></div>';
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

  /* Four tables of the same shape, one showing at a time. All four are in the page
     already, so the switch shows and hides rather than fetching or rebuilding. */
  function setupRecordTabs() {
    var tabs = document.getElementById('record-tabs');
    if (!tabs) return;
    tabs.addEventListener('click', function (e) {
      var button = e.target.closest('button[data-record]');
      if (!button) return;
      var wanted = button.dataset.record;
      tabs.querySelectorAll('button[data-record]').forEach(function (b) {
        b.setAttribute('aria-selected', String(b.dataset.record === wanted));
      });
      document.querySelectorAll('[data-record-panel]').forEach(function (panel) {
        panel.hidden = panel.dataset.recordPanel !== wanted;
      });
    });
  }

  function start() {
    drawDiagram();
    drawHeatmap();
    setupRecordTabs();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
