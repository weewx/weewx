/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 */

/* weewx-json.js reads the files of the JSON generator (see "The JSON generator" in
   the Customization Guide, and "JSON files" in the Reference Guide) and the file
   display.json of a skin, and hands the caller descriptions of charts that are ready
   to draw. Any skin can load it, whatever draws its charts. The Horizon skin draws its
   charts with ECharts, but weewx-json.js knows nothing about ECharts or about Horizon.

   The files it reads are

     data/meta.json          What a JavaScript needs to convert a reading to another
                             unit. The JSON generator writes it.
     data/archive/           The readings. The JSON generator writes them, in the
                             unit system of the report. They say what was measured and
                             nothing about how to show it.
     display.json            How to show the readings: the labels, the type of each
                             chart, the length of each time span and how to write a
                             unit. The skin writes it, e.g., Horizon from
                             [DisplayOptions] with the template display.json.tmpl.
                             Without display.json, every plot group in the archive is
                             a line chart, and a series is labelled with the name of
                             its observation type.

   weewx-json.js adds one name to the page, WeeWXJSON. WeeWXJSON.create() returns a
   reader of the files in one data directory:

     var data = WeeWXJSON.create({ dataDir: 'data' });
     data.load().then(function () {
       // The last 27 hours of plot group 'tempdew'.
       var to = Math.floor(Date.now() / 1000);
       return data.chart('tempdew', to - 27 * 3600, to);
     }).then(function (chart) {
       // chart.series[0].label, chart.series[0].time, chart.series[0].values, ...
       // data.yAxis(chart, 8) is [min, max, step] for the y axis.
     });

   The options of create() are

     dataDir      The directory of the JSON files, relative to the page. Default is
                  'data'.
     displayFile  The address of display.json, relative to the page. Default is
                  'display.json'.
     unitSystem   A function that returns the name of the unit system the reader
                  chose, e.g., 'METRIC', or '' for the unit system of the report.
                  Default is a function that returns ''.

   The methods of the reader are

     load()                 Returns a promise that is kept when meta.json,
                            display.json and data/archive/index.json have loaded. A
                            file that is missing is read as empty.
     display()              Returns display.json where load() has loaded it, or {}.
                            It holds `periods`, `time_lengths` (seconds), `plot_groups`
                            and `telemetry_plot_groups`, `charts`, `labels` and
                            `units`.
     index()                Returns data/archive/index.json where load() has loaded
                            it, or null.
     hasFiles(group, from, to)
                            Returns whether the archive files cover the time span
                            from `from` to `to`, both in seconds since the epoch.
                            Call it after load().
     chart(group, from, to) Returns a promise of the chart description of plot group
                            `group` for the time span, or of null. The description
                            joins the archive files that the time span touches onto
                            one grid of times. It holds `title`, `unit`, `unit_label`,
                            `yscale`, `aggregate_interval` and `series`, and where the
                            time span is short enough `daynight`. `yscale` holds the
                            minimum, the maximum and the step that display.json sets,
                            where each can be null. Each series holds `label`, `type`
                            ('line', 'bar' or 'vector'), `time` and `values`, and the
                            other arrays and fields of the file. A 'vector' series has
                            `vector_x`, `vector_y` and `vector_rotate`, the angle in
                            degrees that display.json sets. Call it after load().
     yAxis(chart, steps)    Returns [minimum, maximum, step] for the y axis of
                            `chart`, a number that is round at 1, 2 and 5 times a power
                            of ten. See scale(). `steps` is the number of gridlines the
                            axis has room for.
     reset()                Forgets what load() and chart() have read, except
                            meta.json, so that the next call reads the other files
                            again. Call it when the generator has written new files.
     unitTable()            Returns the unit table, or null. It joins the unit table of
                            meta.json with `units` of display.json.
     inChosenUnit(chart)    Returns `chart` with its readings, y axis and unit label
                            in the unit system that unitSystem() names. The chart is
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
                            `unit`.

   WeeWXJSON.scale(min, max, prescale, steps) is the function that yAxis() calls. */

(function (root) {
  'use strict';

  /* Returns a number without the digits that floating point adds, e.g., 0.30000000000000004
     as 0.3. */
  function clean(v) {
    return parseFloat(v.toPrecision(12));
  }

  /* Returns [minimum, maximum, step] for an axis that has to hold the readings from
     `dataMin` to `dataMax`, with the zero on a step. It does what scale() of
     weeplot/utilities.py does for the image of the ImageGenerator, so that a chart
     here has the axis that the image of the same plot would have.

     `prescale` is [minimum, maximum, step], where each can be null. A minimum or a
     maximum that is not null is kept. A step that is not null is the smallest the axis
     may have. `steps` is the number of steps wanted, 10 if not given. */
  function scale(dataMin, dataMax, prescale, steps) {
    var pre = prescale || [null, null, null];
    var minScale = pre[0], maxScale = pre[1], minInterval = pre[2];
    var wanted = steps || 10;

    /* Everything is fixed, so there is nothing to work out. */
    if (minScale !== null && maxScale !== null && minInterval !== null) {
      return [minScale, maxScale, minInterval];
    }

    var lo = dataMin, hi = dataMax;
    /* Readings outside a fixed end do not move the axis. */
    if (maxScale !== null) {
      hi = Math.min(hi, maxScale);
      if (hi < lo) lo = hi;
    }
    if (minScale !== null) {
      lo = Math.max(lo, minScale);
      if (hi < lo) hi = lo;
    }

    /* All readings equal: the axis needs a range, and gets one by moving an end that
       is not fixed. */
    if (Math.abs(lo - hi) <= 1e-7 * Math.max(Math.abs(lo), Math.abs(hi))) {
      var out = minInterval !== null ? minInterval * wanted
        : (hi ? 0.01 * (Math.round(Math.abs(hi) * 100) / 100) : 0.1);
      if (maxScale !== null) {
        lo = hi - out;
      } else if (minScale !== null) {
        hi = lo + out;
      } else if (lo === 0) {
        hi = 1;
      } else {
        hi = lo + out;
      }
    }

    var range;
    if (minScale !== null && maxScale !== null) range = maxScale - minScale;
    else if (minScale !== null) range = hi - minScale;
    else if (maxScale !== null) range = maxScale - lo;
    else range = hi - lo;

    var nominal = range / wanted;
    var power = Math.pow(10, Math.floor(Math.log(nominal) / Math.LN10));
    var lead = Math.floor(nominal / power + 0.5);
    /* The step is 2, 5 or 10 times a power of ten, whichever is nearest to the
       nominal step. weeplot has no step of 1 times a power of ten. */
    var interval = (lead > 5 ? 10 : lead > 2 ? 5 : 2) * power;

    if (minInterval === null || interval >= minInterval) {
      if (minScale === null) minScale = interval * Math.floor(lo / interval);
      if (maxScale === null) maxScale = interval * Math.ceil(hi / interval);
    } else {
      /* The step that was asked for is wider than the one that fits. The axis then
         has few steps, so its ends are moved to make a chart that is not empty. */
      interval = minInterval;
      if (minScale === null) {
        if (maxScale === null) {
          minScale = interval * Math.floor(lo / interval);
          maxScale = minScale + interval * wanted;
        } else {
          minScale = maxScale - interval * wanted;
        }
      } else if (maxScale === null) {
        maxScale = minScale + interval * wanted;
      }
    }
    return [clean(minScale), clean(maxScale), clean(interval)];
  }

  function create(options) {
    options = options || {};
    var dataDir = options.dataDir || 'data';
    var displayFile = options.displayFile || 'display.json';
    var chosenSystem = options.unitSystem || function () { return ''; };

    /* `metaFile` holds data/meta.json, which the JSON generator writes: the unit table
       that converts a reading to another unit. `shown` holds display.json, which the
       skin writes. The unit table changes only when the station's configuration does,
       so reset() leaves `metaFile` alone and a page reads it once. reset() empties
       `shown`, so that load() reads display.json again, and a page that stays open
       for days shows a label that its owner has changed. */
    var metaFile = null;
    var shown = null;

    /* The archive files, in data/archive/, hold the readings of each plot group over
       the whole archive, in three tiers (see MAX_POINTS). data/archive/index.json
       lists the files that exist. A time span fetches only the files it touches, and
       archiveCache keeps each file until reset() empties the cache. */
    var archiveIndex = null;
    var archiveCache = new Map();           // file name -> file contents

    /* WeeWX writes the JSON files in the report unit system. With the unit table, the
       browser converts any reading to the unit system the reader chose, without
       fetching anything. The unit table comes in two files. data/meta.json says how to
       convert, because that depends on the units and on nothing else:

         groups:  {"outTemp": "group_temperature", ...}
         systems: {"METRIC": {"group_temperature": "degree_C", ...}, ...}
         convert: {"degree_F": {"degree_C": [0.5556, -17.7778]}, ...}

       A conversion multiplies by the first number of a pair in 'convert' and adds the
       second. display.json says how to write a unit, because that depends on the
       language of the report:

         report:  {"group_temperature": "degree_F", ...}
         labels:  {"degree_C": "°C", ...}
         formats: {"degree_C": "%.1f", ...} */

    /* `unitChoices` holds the unit table, from the two files. reset() empties
       `metaFile` and `shown`, so that both files are read again. `unitChoices` keeps
       the old unit table meanwhile, so the readings stay in the chosen unit system
       while the files load. The unit table changes only when the station's
       configuration changes. */
    var unitChoices = null;

    function unitTable() {
      return unitChoices;
    }

    /* Returns the label of `unit`, e.g., '°C'. display.json is the only place that
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

    /* Returns the chart `chart` with its readings, y axis and unit label in the unit
       system the reader chose. A conversion goes into a copy, and `chart` itself stays
       in the unit it was written in. If `chart` were converted in place, the next unit
       change would convert its readings a second time. */
    function inChosenUnit(chart) {
      var table = unitTable();
      if (!table || !chart || !chart.series || !chart.series.length) return chart;

      var to = targetUnit(chart.series[0].obs_type, chart.unit);
      if (!to) return chart;
      var steps = table.convert[chart.unit][to];
      var factor = steps[0], offset = steps[1];
      var apply = function (v) {
        return v === null || v === undefined ? null : v * factor + offset;
      };

      var out = shallow(chart);
      out.unit = to;
      out.unit_label = unitLabel(to);

      /* The step of the y axis is a difference, so the step takes the factor but not
         the offset: a step of 5 degree_C is 9 degree_F, not 41. `converted` tells
         yAxis() that the ends are no longer the ones that were set: 0 and 40 degree_C
         are 32 and 104 degree_F, which are not round. */
      if (chart.yscale) {
        out.yscale = [apply(chart.yscale[0]), apply(chart.yscale[1]),
                      chart.yscale[2] === null ? null : chart.yscale[2] * Math.abs(factor)];
        out.converted = true;
      }

      out.series = chart.series.map(function (s) {
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


    /* Returns [minimum, maximum, step] for the y axis of `chart`, worked out from the
       readings that `chart` holds, at the unit system the chart is in. The ends and
       the step that display.json sets are kept, as scale() keeps them, and `steps` is
       the number of steps the axis has room for. */
    function yAxis(chart, steps) {
      var fixed = (chart.yscale || [null, null, null]).slice();
      var lo = null, hi = null, bars = false;

      chart.series.forEach(function (s) {
        var top = null, bottom = null;
        for (var i = 0; i < s.values.length; i++) {
          var v = s.values[i];
          if (v === null || v === undefined) continue;
          /* A vector is as long as the speed on the axis, in both directions from
             zero, as weeplot draws it. */
          var a = s.type === 'vector' ? -Math.abs(v) : v;
          var b = s.type === 'vector' ? Math.abs(v) : v;
          if (bottom === null || a < bottom) bottom = a;
          if (top === null || b > top) top = b;
        }
        if (top === null) return;
        if (s.type === 'vector') {
          bottom = -Math.max(top, -bottom);
          top = -bottom;
        }
        if (s.type === 'bar') bars = true;
        lo = lo === null ? bottom : Math.min(lo, bottom);
        hi = hi === null ? top : Math.max(hi, top);
      });
      if (lo === null) return [0, 1, 0.2];

      /* A bar starts at zero. An axis that starts higher makes a small total look
         like a big one. */
      if (bars) {
        lo = Math.min(lo, 0);
        hi = Math.max(hi, 0);
      }

      /* After a conversion, the ends that display.json sets are no longer round, e.g.,
         32 and 104 degree_F. They then only widen the readings, and scale() rounds. */
      if (chart.converted) {
        if (fixed[0] !== null) lo = Math.min(lo, fixed[0]);
        if (fixed[1] !== null) hi = Math.max(hi, fixed[1]);
        fixed[0] = fixed[1] = null;
      }
      return scale(lo, hi, fixed, steps);
    }

    function loadIndex() {
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
          var look = chartLook(group);
          var series = template.series.map(function (s) {
            var own = look.series[s.obs_type] || {};
            var type = own.plot_type || look.plot_type;
            /* A vector needs the components that the file holds for a wind vector. A
               file without them gets a line of the speeds instead, e.g., for a type
               of a station that has no wind direction. */
            if (type === 'vector' && !s.vector_x) type = 'line';
            var out = {
              obs_type: s.obs_type,
              label: own.label || labelOf(s.obs_type),
              type: type,
              time: [],
              values: new Array(slots).fill(null)
            };
            if (type === 'vector') {
              out.vector_rotate = own.vector_rotate !== undefined
                ? own.vector_rotate : look.vector_rotate;
            }
            /* A series that totals more than one interval, e.g., hourly rain in a
               file of five minutes, needs `aggregate_interval` to say how many
               intervals each of its readings covers. */
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

          var out = {
            name: group,
            title: series.map(function (s) { return s.label; }).join(', '),
            start: start,
            stop: start + slots * interval,
            unit: template.unit,
            unit_label: unitLabel(template.unit),
            aggregate_interval: interval,
            /* The ends and the step of the y axis that display.json sets, where
               each can be null. yAxis() works out the others from the readings. */
            yscale: look.yscale.slice(),
            series: series
          };
          if (daynight) out.daynight = daynight;
          return out;
        })();
      });
    }


    /* Reads a JSON file, and returns a promise of its contents, or of `empty` where
       the file is missing or is not JSON. A skin without display.json still draws its
       charts, from the defaults. */
    function fetchJSON(url, empty) {
      return fetch(url, { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : empty; })
        .catch(function () { return empty; });
    }

    function loadMeta() {
      if (metaFile) return Promise.resolve(metaFile);
      return fetchJSON(dataDir + '/meta.json', {}).then(function (json) {
        metaFile = json;
        return json;
      });
    }

    function loadDisplay() {
      if (shown) return Promise.resolve(shown);
      return fetchJSON(displayFile, {}).then(function (json) {
        shown = json;
        return json;
      });
    }

    /* `loading` is the promise of a load() that is under way. The page calls load()
       from more than one place at start-up, and the files should be fetched once. */
    var loading = null;

    /* Reads meta.json, display.json and data/archive/index.json, and puts the unit
       table together from the first two. */
    function load() {
      if (loading) return loading;
      loading = Promise.all([loadMeta(), loadDisplay(), loadIndex()]).then(function (all) {
        if (all[0].units || all[1].units) {
          unitChoices = Object.assign({}, all[0].units, all[1].units);
        }
        /* Without display.json, every plot group in the archive is a chart. */
        if (!all[1].plot_groups) {
          all[1].plot_groups = (all[2].groups || []).map(function (g) { return g.name; });
        }
      });
      return loading;
    }

    /* Returns what display.json says about plot group `group`: the type of its
       chart, the ends and step of its y axis, the angle of its vector arrows, and in
       `series` what it says about a series, by observation type. A plot group that
       display.json does not list is a line chart. */
    function chartLook(group) {
      var listed = ((shown && shown.charts) || {})[group] || {};
      return {
        plot_type: listed.plot_type || 'line',
        yscale: listed.yscale || [null, null, null],
        vector_rotate: listed.vector_rotate || 0,
        series: listed.overrides || {}
      };
    }

    /* Returns the label of the observation type `obsType` in the language of the
       report, or the type itself where display.json has none. */
    function labelOf(obsType) {
      var labels = (shown && shown.labels) || {};
      return labels[obsType] || obsType;
    }

    function reset() {
      archiveCache.clear();
      archiveIndex = null;
      shown = null;
      loading = null;
    }

    return {
      load: load,
      display: function () { return shown || {}; },
      index: function () { return archiveIndex; },
      hasFiles: function (group, from, to) { return !!filesFor(group, from, to); },
      chart: windowFromArchive,
      yAxis: yAxis,
      reset: reset,
      unitTable: unitTable,
      inChosenUnit: inChosenUnit,
      targetUnit: targetUnit,
      convertReading: convertReading,
      unitLabel: unitLabel,
      decimalsFor: decimalsFor
    };
  }

  root.WeeWXJSON = { create: create, scale: scale };
})(window);
