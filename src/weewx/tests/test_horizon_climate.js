/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3. See LICENSE.txt for your rights.
 * Run with node --test src/weewx/tests/test_horizon_climate.js.
 */

'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname,
  '../../weewx_data/skins/Horizon/climate.js'), 'utf8');

function chart(data, units) {
  const charts = {};
  const listeners = {};
  const hosts = { 'climate-diagram': { style: {} }, 'climate-water': { style: {} } };
  vm.runInNewContext(source, {
    document: {
      documentElement: { lang: 'en-US' }, body: {},
      getElementById: function (id) {
        return id === 'climate-data' ? { textContent: JSON.stringify(data) } : hosts[id];
      },
      querySelectorAll: function () { return []; },
      addEventListener: function (name, callback) { listeners[name] = callback; }
    },
    window: { HORIZON: { units: units }, echarts: {} },
    echarts: {
      init: function (host) {
        const id = Object.keys(hosts).find(function (key) { return hosts[key] === host; });
        return {
          setOption: function (option) { charts[id] = option; },
          dispose: function () { delete charts[id]; }, resize: function () {}
        };
      }
    },
    getComputedStyle: function () {
      return { fontFamily: 'sans-serif', getPropertyValue: function () { return ''; } };
    },
    ResizeObserver: function () { this.observe = function () {}; }
  });
  return { charts: charts, redraw: listeners['horizon:units'] };
}

function labels(axis) {
  return Array.from({ length: 6 }, function (_, i) {
    return Number(axis.axisLabel.formatter(axis.min + i * axis.interval));
  });
}

const sample = {
  months: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'],
  temp: [2, 4, 8, 10, 15, 17, 21, 21, 15, 15],
  rain: [60, 120, 165, 40, 50, 20, 0, 0, 15, null],
  tempBack: [1, 0], rainBack: [1, 0], tempUnit: 'degree_C', rainUnit: 'mm'
};

for (const spec of [
  { name: 'metric', tempBack: [1, 0], rainBack: [1, 0], tempLimit: 40 },
  { name: 'US', tempBack: [1.8, 32], rainBack: [1 / 25.4, 0], tempLimit: 100 },
  { name: 'Kelvin/cm', tempBack: [1, 273.15], rainBack: [0.1, 0], tempLimit: 323.15 }
]) {
  test(spec.name + ' axes have round, evenly spaced labels on matching gridlines', function () {
    const data = Object.assign({}, sample, spec);
    const axes = chart(data).charts['climate-diagram'].yAxis;
    axes.forEach(function (axis) {
      const ticks = labels(axis);
      const step = ticks[1] - ticks[0];
      const power = Math.pow(10, Math.floor(Math.log10(step)));
      assert.ok([1, 2, 5, 10].some(function (n) { return Math.abs(step / power - n) < 1e-8; }),
        'the displayed step must be round');
      ticks.forEach(function (tick, i) {
        assert.ok(Math.abs(tick - ticks[0] - i * step) < 1e-8,
          'equally spaced ticks must have equal numeric increments');
      });
      assert.ok(Math.abs((axis.max - axis.min) / axis.interval - 5) < 1e-5,
        'both axes must have five intervals');
    });
    assert.ok(labels(axes[0])[5] <= spec.tempLimit, 'rainfall must not inflate temperature');
    for (const [i, back, values] of [[0, spec.tempBack, data.temp], [1, spec.rainBack, data.rain]]) {
      for (const value of values.filter(function (v) { return v !== null; })) {
        assert.ok(axes[i].min <= value && value <= axes[i].max, 'all data must fit');
      }
      assert.ok(Math.abs(labels(axes[i])[0] - (axes[i].min * back[0] + back[1])) < 1e-8);
    }
  });
}

test('temperature limits do not depend on rainfall extremes', function () {
  const dry = chart(Object.assign({}, sample, { rain: [0] })).charts['climate-diagram'];
  const wet = chart(Object.assign({}, sample, { rain: [2000] })).charts['climate-diagram'];
  assert.equal(dry.yAxis[0].min, wet.yAxis[0].min);
  assert.equal(dry.yAxis[0].max, wet.yAxis[0].max);
});

test('US rainfall labels advance by the same amount at every gridline', function () {
  const data = Object.assign({}, sample, { tempBack: [1.8, 32], rainBack: [1 / 25.4, 0] });
  const ticks = labels(chart(data).charts['climate-diagram'].yAxis[1]);
  const step = ticks[1] - ticks[0];
  for (let i = 2; i < ticks.length; i++) {
    assert.ok(Math.abs(ticks[i] - ticks[i - 1] - step) < 1e-8,
      'US rainfall labels have uneven increments: ' + ticks.join(', '));
  }
});

test('freezing temperatures and all-zero or missing months keep finite axes', function () {
  for (const temps of [[-20, -5, 0, null], [0, 0], [null, null]]) {
    const option = chart(Object.assign({}, sample, { temp: temps, rain: [0, null] }))
      .charts['climate-diagram'];
    option.yAxis.forEach(function (axis) {
      assert.ok(Number.isFinite(axis.min) && Number.isFinite(axis.max) && axis.interval > 0);
    });
    temps.filter(function (v) { return v !== null; }).forEach(function (v) {
      assert.ok(option.yAxis[0].min <= v && v <= option.yAxis[0].max);
    });
    assert.equal(option.yAxis[1].min, 0);
  }
});

test('dry shading keeps the metric criterion, including zero rain and missing data', function () {
  const data = Object.assign({}, sample, {
    temp: [10, 10, 10, 0, -5, null, 10], rain: [0, 19, 20, 0, 0, 0, null]
  });
  const option = chart(data).charts['climate-diagram'];
  const area = option.series.find(function (s) { return s.type === 'bar'; }).markArea;
  assert.equal(JSON.stringify(area.data), JSON.stringify([
    [{ xAxis: 0 }, { xAxis: 0 }], [{ xAxis: 1 }, { xAxis: 1 }]
  ]));
});

test('single observation types are drawn without classifying dry months', function () {
  for (const obs of ['temp', 'rain']) {
    const data = Object.assign({}, sample, { [obs]: null });
    const option = chart(data).charts['climate-diagram'];
    assert.equal(option.series.length, 1);
    if (obs === 'temp') assert.equal(option.series[0].markArea.data.length, 0);
  }
  assert.equal(chart({}).charts['climate-diagram'], undefined);
});

test('unit changes redraw axes and preserve raw tooltip readings and water balance', function () {
  let chosen = false;
  const units = {
    chosen: function () { return chosen; },
    target: function (obs) { return chosen ? (obs === 'outTemp' ? 'degree_F' : 'inch') : null; },
    convert: function (v, unit, obs) {
      return { value: obs === 'outTemp' ? v * 1.8 + 32 : v / 25.4,
               label: obs === 'outTemp' ? '°F' : 'in' };
    }
  };
  const data = Object.assign({}, sample, { et: sample.rain.map(function () { return 10; }) });
  const result = chart(data, units);
  assert.equal(labels(result.charts['climate-diagram'].yAxis[0])[0], 0);
  chosen = true;
  result.redraw();
  const option = result.charts['climate-diagram'];
  assert.equal(labels(option.yAxis[0])[0], 30);
  assert.equal(labels(option.yAxis[1])[1], 2);
  assert.equal(JSON.stringify(option.series[0].data), JSON.stringify(data.rain));
  assert.match(option.tooltip.formatter([
    { seriesType: 'bar', value: 165, seriesName: 'Rainfall', color: 'blue', axisValueLabel: 'Mar' }
  ]), /6\.5 in/);
  assert.equal(result.charts['climate-water'].series[2].data[2], 155);
  data.tempBack = [1.8, 32];
  data.rainBack = [1 / 25.4, 0];
  units.target = function () { return null; };
  result.redraw();
  assert.equal(labels(result.charts['climate-diagram'].yAxis[0])[0], 0);
});
