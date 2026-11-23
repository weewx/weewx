/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3. See LICENSE.txt for your rights.
 * Run with node --test src/weewx/tests/test_weewx_json.js.
 */

'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname,
  '../../weewx_data/skins/Horizon/weewx-json.js'), 'utf8');
const start = new Date(2026, 6, 13, 12).getTime() / 1000;
const interval = 3600;

async function readChart(charts, series) {
  const files = {
    'data/meta.json': {},
    'display.json': {
      charts: charts,
      labels: { outTemp: 'Outside Temperature', dewpoint: 'Dew Point' }
    },
    'data/archive/index.json': {
      first: start,
      last: start + 2 * interval,
      groups: [{ name: 'tempdew', years: { '2026': true },
        year_intervals: { '2026': interval } }]
    },
    'data/archive/tempdew-2026.json': {
      name: 'tempdew', start: start, interval: interval, unit: 'degree_F',
      series: series || [
        { obs_type: 'outTemp', values: [70, 72, 71] },
        { obs_type: 'dewpoint', values: [50, 51, 49] }
      ]
    }
  };
  const context = {
    window: {},
    fetch: async function (url) {
      return { ok: url in files, json: async function () { return files[url]; } };
    }
  };
  vm.runInNewContext(source, context);
  const reader = context.window.WeeWXJSON.create();
  await reader.load();
  return reader.chart('tempdew', start, start + 3 * interval);
}

test('series labels and yscale from display.json reach the chart', async function () {
  const chart = await readChart({ tempdew: {
    yscale: [10, 100, null],
    overrides: { outTemp: { label: 'Living room' }, dewpoint: { label: 'Dewpoint' } }
  } });

  assert.deepEqual(Array.from(chart.series, function (s) { return s.label; }),
    ['Living room', 'Dewpoint']);
  assert.equal(chart.title, 'Living room, Dewpoint');
  assert.deepEqual(Array.from(chart.yscale), [10, 100, null]);
});

test('a series without a label override keeps its generic label', async function () {
  const chart = await readChart({ tempdew: {
    plot_type: 'bar',
    overrides: { outTemp: { label: 'Living room', plot_type: 'line' } }
  } });

  assert.deepEqual(Array.from(chart.series, function (s) { return s.label; }),
    ['Living room', 'Dew Point']);
  assert.deepEqual(Array.from(chart.series, function (s) { return s.type; }),
    ['line', 'bar']);
});

test('series plot type and vector rotation override the chart defaults', async function () {
  const chart = await readChart({ tempdew: {
    plot_type: 'line', vector_rotate: 90,
    overrides: { windSpeed: { plot_type: 'bar' },
      windvec: { plot_type: 'vector', vector_rotate: 0 } }
  } }, [
    { obs_type: 'windSpeed', values: [1, 2, 3] },
    { obs_type: 'windvec', values: [3, 2, 1],
      vector_x: [1, 2, 3], vector_y: [3, 2, 1] }
  ]);

  assert.deepEqual(Array.from(chart.series, function (s) { return s.type; }),
    ['bar', 'vector']);
  assert.equal(chart.series[1].vector_rotate, 0);
});

test('a chart without display options uses generic labels and line series', async function () {
  const chart = await readChart({});

  assert.deepEqual(Array.from(chart.series, function (s) { return s.label; }),
    ['Outside Temperature', 'Dew Point']);
  assert.deepEqual(Array.from(chart.series, function (s) { return s.type; }),
    ['line', 'line']);
  assert.deepEqual(Array.from(chart.yscale), [null, null, null]);
});
