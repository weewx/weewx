/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 */

/* weewx-json.js reads the files of the JSON generator (see "The JSON generator" in
   the Customization Guide, and "JSON files" in the Reference Guide). Any skin can
   load it, whatever draws its charts. The Horizon skin draws its charts with
   ECharts, but weewx-json.js knows nothing about ECharts or about Horizon.

   weewx-json.js adds one name to the page, WeeWXJSON. WeeWXJSON.create() returns a
   reader of the files in one data directory:

     var data = WeeWXJSON.create({ dataDir: 'data' });
     data.loadManifest().then(function () {
       return data.loadIndex();
     }).then(function () {
       // The last 27 hours of plot group 'tempdew'.
       var to = Math.floor(Date.now() / 1000);
       return data.plot('tempdew', to - 27 * 3600, to);
     }).then(function (plot) {
       // plot.series[0].time and plot.series[0].values, ...
     });

   The options of create() are

     dataDir     The directory of the JSON files, relative to the page. Default is
                 'data'.
     unitSystem  A function that returns the name of the unit system the reader
                 chose, e.g., 'METRIC', or '' for the unit system of the report.
                 Default is a function that returns ''.

   The methods of the reader are

     loadManifest()         Returns a promise of data/skin.json: `time_lengths` and
                            the unit table `units`.
     loadIndex()            Returns a promise of data/archive/index.json.
     index()                Returns data/archive/index.json where loadIndex() has
                            loaded it, or null.
     hasFiles(group, from, to)
                            Returns whether the archive files cover the time span
                            from `from` to `to`, both in seconds since the epoch.
                            Call it after loadIndex().
     plot(group, from, to)  Returns a promise of the plot data of plot group `group`
                            for the time span, or of null. The plot data joins the
                            archive files that the time span touches onto one grid
                            of times. It holds `unit`, `unit_label`, `yscale`,
                            `aggregate_interval` and `series`, and where the time
                            span is short enough `daynight`. Each series holds
                            `time` and `values`, and the other arrays and fields
                            of the file. Call it after loadManifest() and
                            loadIndex().
     reset()                Forgets what loadManifest(), loadIndex() and plot()
                            have read, so that the next call reads the files again.
                            Call it when the generator has written new files.
     unitTable()            Returns the unit table of data/skin.json, or null.
     inChosenUnit(plot)     Returns `plot` with its readings, y axis and unit label
                            in the unit system that unitSystem() names. The plot is
                            not changed.
     targetUnit(obsType, fromUnit)
                            Returns the unit in which a reading of `obsType` in
                            `fromUnit` is shown, or null where it stays as it is.
     convertReading(value, fromUnit, obsType)
                            Returns {value, unit, label} for one reading, or null
                            where it stays as it is.
     unitLabel(unit)        Returns the label of `unit`, e.g., '°C'.
     decimalsFor(unit, fallback)
                            Returns the number of decimals the report writes for
                            `unit`. */

(function (root) {
  'use strict';

  function create(options) {
    options = options || {};
    var dataDir = options.dataDir || 'data';
    var chosenSystem = options.unitSystem || function () { return ''; };

    /* `manifest` holds data/skin.json: the `time_length` of each time period in
       skin.conf (`time_lengths`) and the unit table (`units`). */
    var manifest = null;

    /* The archive files, in data/archive/, hold the readings of each plot group over
       the whole archive, in three tiers (see MAX_POINTS). data/archive/index.json
       lists the files that exist. A time span fetches only the files it touches, and
       archiveCache keeps each file until reset() empties the cache. */
    var archiveIndex = null;
    var archiveCache = new Map();           // file name -> file contents

    /* WeeWX writes the JSON files in the report unit system. data/skin.json also
       carries a unit table. With the unit table, the browser converts any reading to
       the unit system the reader chose, without fetching anything. The unit table,
       in part:

         groups:  {"outTemp": "group_temperature", ...}
         systems: {"METRIC": {"group_temperature": "degree_C", ...}, ...}
         report:  {"group_temperature": "degree_F", ...}
         convert: {"degree_F": {"degree_C": [0.5556, -17.7778]}, ...}
         labels:  {"degree_C": "°C", ...}
         formats: {"degree_C": "%.1f", ...}

       A conversion multiplies by the first number of a pair in 'convert' and adds the
       second. */

    /* `unitChoices` holds the unit table from data/skin.json. reset() empties
       `manifest`, so that data/skin.json is read again. `unitChoices` keeps the old
       unit table meanwhile, so the readings stay in the chosen unit system while
       data/skin.json loads. The unit table changes only when the station's
       configuration changes. */
    var unitChoices = null;

    function unitTable() {
      return unitChoices;
    }

    /* Returns the label of `unit`, e.g., '°C'. data/skin.json is the only place that
       holds it: the archive files name only the unit. */
    function unitLabel(unit) {
      var table = unitTable();
      return (table && table.labels && table.labels[unit]) || '';
    }

    /* Returns the unit in which a reading of `obsType` in `fromUnit` is shown, or null
       where the reading stays in `fromUnit`.

       Without a chosen unit system the target is the report unit system. A reading
       that WeeWX wrote is then already in the target unit. The forecast, however,
       arrives from Open-Meteo in degree_C and km_per_hour, and is converted to match
       the rest of the page. */
    function targetUnit(obsType, fromUnit) {
      var table = unitTable();
      var system = chosenSystem();
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

    /* Returns the plot data `meta` with its readings, y axis and unit label in the unit
       system the reader chose. A conversion goes into a copy, and `meta` itself stays in
       the unit it was written in. If `meta` were converted in place, the next unit
       change would convert its readings a second time. */
    function inChosenUnit(meta) {
      var table = unitTable();
      if (!table || !meta || !meta.series || !meta.series.length) return meta;

      var to = targetUnit(meta.series[0].obs_type, meta.unit);
      if (!to) return meta;
      var steps = table.convert[meta.unit][to];
      var factor = steps[0], offset = steps[1];
      var apply = function (v) {
        return v === null || v === undefined ? null : v * factor + offset;
      };

      var out = shallow(meta);
      out.unit = to;
      out.unit_label = unitLabel(to);

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


    function loadArchiveIndex() {
      if (archiveIndex) return Promise.resolve(archiveIndex);
      return fetch(dataDir + '/archive/index.json', { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) { archiveIndex = j || { groups: [] }; return archiveIndex; })
        .catch(function () { archiveIndex = { groups: [] }; return archiveIndex; });
    }

    function loadArchiveFile(name) {
      if (archiveCache.has(name)) return Promise.resolve(archiveCache.get(name));
      return fetch(dataDir + '/archive/' + name + '.json', { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) { archiveCache.set(name, j); return j; })
        .catch(function () { archiveCache.set(name, null); return null; });
    }

    /* The archive files come in three tiers, which overlap in time. The day tier holds
       the station's own readings, one file per day. The month tier holds readings at a
       longer interval, one file per month. The year tier holds readings at a still
       longer interval, which grows with age, one file per calendar year. A file is
       named after its plot group and the day, month or year it covers, e.g.,
       'tempdew-2026-07'. TIER_KEYS lists the tiers finest first, with the keys of
       data/archive/index.json that list each tier's files (`named`) and their
       intervals (`grids`).

       filesFor takes the finest tier that covers the whole time span. A tier covers a
       time span where data/archive/index.json names a file for every part of the
       time span, and the time span comes to no more than MAX_POINTS readings. At a
       one-minute archive interval, a day of the day tier is 1440 readings. A year
       would be half a million, far more than a chart 1000 px wide can show. */
    var MAX_POINTS = 20000;

    var TIER_KEYS = [
      { named: 'days', grids: 'day_intervals', unit: 'day' },
      { named: 'months', grids: 'month_intervals', unit: 'month' },
      { named: 'years', grids: 'year_intervals', unit: 'year' }
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
        var keys = stampsIn(from, to, tier.unit);
        if (!keys.length) continue;

        var grids = entry[tier.grids] || {};
        var ok = true;
        var interval = 0;
        var present = [];
        for (var i = 0; i < keys.length; i++) {
          if (!(keys[i] in have)) {
            /* A key that data/archive/index.json does not name is harmless where the
               archive has no readings for that time. Otherwise the tier does not
               reach back far enough, and filesFor tries the next tier. A whole week
               from the month tier is better than half a week from the day tier. */
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
          names: present.map(function (k) { return group + '-' + k; })
        };
      }
      return null;
    }

    var daynightCache = new Map();

    function loadDayNight(year) {
      if (daynightCache.has(year)) return Promise.resolve(daynightCache.get(year));
      /* loadDayNight requests no file for a year before the first archive record. */
      if (archiveIndex && archiveIndex.first
          && year < new Date(archiveIndex.first * 1000).getFullYear()) {
        daynightCache.set(year, null);
        return Promise.resolve(null);
      }
      return fetch(dataDir + '/archive/daynight-' + year + '.json', { cache: 'no-cache' })
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
             whose average hides the extremes. The arrays named in EXTRA are joined
             like `values`. */
          var EXTRA = ['vector_x', 'vector_y', 'directions', 'min', 'max'];

          var template = present[0];
          var series = template.series.map(function (s) {
            var out = {
              obs_type: s.obs_type,
              label: s.label,
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
             the step of the first file that has one. `== null` also catches a value
             that is missing, e.g., the step of a yscale with two values. */
          var yscale = null;
          present.forEach(function (file) {
            if (!file.yscale) return;
            if (!yscale) { yscale = file.yscale.slice(); return; }
            if (file.yscale[0] != null && (yscale[0] == null || file.yscale[0] < yscale[0])) {
              yscale[0] = file.yscale[0];
            }
            if (file.yscale[1] != null && (yscale[1] == null || file.yscale[1] > yscale[1])) {
              yscale[1] = file.yscale[1];
            }
            if (yscale[2] == null) yscale[2] = file.yscale[2];
          });

          var out = {
            name: group,
            start: start,
            stop: start + slots * interval,
            unit: template.unit,
            unit_label: unitLabel(template.unit),
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
      return fetch(dataDir + '/skin.json', { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (json) {
          manifest = json || {};
          if (manifest.units) unitChoices = manifest.units;
          return manifest;
        })
        .catch(function () { manifest = {}; return manifest; });
    }

    function reset() {
      archiveCache.clear();
      archiveIndex = null;
      manifest = null;
    }

    return {
      loadManifest: loadManifest,
      loadIndex: loadArchiveIndex,
      index: function () { return archiveIndex; },
      hasFiles: function (group, from, to) { return !!filesFor(group, from, to); },
      plot: windowFromArchive,
      reset: reset,
      unitTable: unitTable,
      inChosenUnit: inChosenUnit,
      targetUnit: targetUnit,
      convertReading: convertReading,
      unitLabel: unitLabel,
      decimalsFor: decimalsFor
    };
  }

  root.WeeWXJSON = { create: create };
})(window);
