/*    Copyright (c) 2026 Manuel Hilgert
 *    Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 *
 * The forecast panel. Two sources, tried in this order:
 *
 *   'data/forecast.json', if something on the station writes one. Nothing
 *   leaves the reader's browser, the model is fetched once for the station
 *   rather than once per visitor, and the source can be anything: Open-Meteo,
 *   DWD MOSMIX through weewx-dwd, weewx-forecast, a script of your own. See
 *   'forecast-fetch.py' beside this file for one that writes the format.
 *
 *   Open-Meteo, fetched by the page. No key, nothing to install, works
 *   anywhere. The cost is that every reader's browser asks Open-Meteo, so their
 *   address reaches a third party. On a station published to the world that is
 *   worth a thought, and 'browser_fetch = false' in skin.conf turns it off.
 *
 * The answer is kept for an hour. Models run three-hourly at best, so asking
 * again on each page view returns the same numbers at somebody else's expense.
 *
 * The panel stays hidden until there is something in it, so a station with no
 * forecast has no empty box on it.
 */

(function () {
  'use strict';

  var CFG = window.HORIZON || {};
  var OPTS = CFG.forecast || {};
  var STORE = 'weewx.horizon.forecast';
  var HOUR = 3600 * 1000;

  /* Which picture goes with which WMO 4677 code.

     Only the picture: what the code is called comes from the page, in the
     station's own language, because the skin's language files are where its
     words belong. A code that reaches here without a word simply shows the
     picture, which is still most of the message. */
  var SYMBOLS = {
    0: 'clear', 1: 'mostly-clear', 2: 'partly-cloudy', 3: 'overcast',
    45: 'fog', 48: 'fog',
    51: 'drizzle', 53: 'drizzle', 55: 'drizzle', 56: 'sleet', 57: 'sleet',
    61: 'rain', 63: 'rain', 65: 'rain', 66: 'sleet', 67: 'sleet',
    71: 'snow', 73: 'snow', 75: 'snow', 77: 'snow',
    80: 'showers', 81: 'showers', 82: 'showers',
    85: 'snow-showers', 86: 'snow-showers',
    95: 'thunderstorm', 96: 'thunderstorm-hail', 99: 'thunderstorm-hail'
  };

  /* A clear night is not a sun. Drawing one looks broken rather than wrong. */
  var NIGHT = {
    clear: 'clear-night', 'mostly-clear': 'mostly-clear-night',
    'partly-cloudy': 'partly-cloudy-night'
  };

  function described(code, dark) {
    var said = (OPTS.sky || {})[code] || '';
    var symbol = SYMBOLS[code];
    if (!symbol) {
      /* Codes not listed fall back to the nearest ten: 62 is rain like 61. */
      var near = Math.floor(code / 10) * 10;
      for (var i = 0; i < 10 && !symbol; i++) {
        symbol = SYMBOLS[near + i];
        if (symbol && !said) said = (OPTS.sky || {})[near + i] || '';
      }
    }
    if (!symbol) return { text: said, symbol: 'cloudy' };
    return { text: said, symbol: (dark && NIGHT[symbol]) || symbol };
  }

  var lang = function () { return document.documentElement.lang || undefined; };

  /* -------------------------------------------------------------- fetching */

  function fromFile() {
    /* Only where something writes the file. Asking for it regardless puts a 404
       in every reader's console on every station that has no such script, which
       is most of them. */
    if (!OPTS.file) return Promise.resolve(null);
    return fetch((CFG.dataDir || 'data') + '/forecast.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  /* Open-Meteo's fields, turned into the shape the file has, so everything below
     works the same whichever source answered. */
  function fromOpenMeteo() {
    if (!OPTS.fetch || CFG.latitude === undefined) return Promise.resolve(null);

    var url = 'https://api.open-meteo.com/v1/forecast'
      + '?latitude=' + encodeURIComponent(CFG.latitude)
      + '&longitude=' + encodeURIComponent(CFG.longitude)
      + '&daily=weather_code,temperature_2m_max,temperature_2m_min,'
      + 'precipitation_probability_max,wind_speed_10m_max'
      + '&hourly=weather_code,temperature_2m,precipitation_probability'
      + '&timezone=auto&forecast_days=' + (OPTS.days || 7);

    return fetch(url, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.daily) return null;
        var d = j.daily;
        var h = j.hourly || { time: [] };
        var du = j.daily_units || {};
        return {
          source: 'open-meteo',
          run: null,
          units: {
            temperature: du.temperature_2m_max || '°C',
            wind: du.wind_speed_10m_max || 'km/h'
          },
          days: d.time.map(function (t, i) {
            return {
              date: t, code: d.weather_code[i],
              high: d.temperature_2m_max[i], low: d.temperature_2m_min[i],
              rain: d.precipitation_probability_max[i],
              wind: d.wind_speed_10m_max[i]
            };
          }),
          hours: h.time.map(function (t, i) {
            return {
              time: t, code: h.weather_code[i],
              temperature: h.temperature_2m[i],
              rain: (h.precipitation_probability || [])[i]
            };
          })
        };
      })
      .catch(function () { return null; });
  }

  /* Kept for an hour: a reader who opens four pages should cost one request. */
  function cached() {
    try {
      var held = JSON.parse(localStorage.getItem(STORE) || 'null');
      if (held && Date.now() - held.at < HOUR) return held.data;
    } catch (e) { /* private mode, or nothing there */ }
    return null;
  }

  function keep(data) {
    try {
      localStorage.setItem(STORE, JSON.stringify({ at: Date.now(), data: data }));
    } catch (e) { /* not worth failing over */ }
  }

  /* ------------------------------------------------------------- rendering */

  function icon(symbol) {
    var span = document.createElement('span');
    span.className = 'forecast-icon';
    span.setAttribute('aria-hidden', 'true');
    /* Named, so the stylesheet can give a sky its own colour: a sun is not the
       same grey as a cloud, and a page that draws it so reads as switched off. */
    span.dataset.symbol = symbol;
    span.style.setProperty('--icon', 'url(icons/forecast/' + symbol + '.svg)');
    return span;
  }

  function number(value, digits) {
    if (value === null || value === undefined) return '';
    return Number(value).toLocaleString(lang(),
      { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  /* A reading in whatever unit the reader has asked the page for.

     The forecast arrives in Celsius and km/h whichever source answered, and the
     rest of the page may be showing Fahrenheit. Putting the two side by side
     without saying which is which is worse than either on its own, so the same
     conversion the charts use is applied here, through the skin's own table.

     Returns the number and the label, both already written out. */
  function reading(value, fromUnit, obsType, digits) {
    if (value === null || value === undefined) return { text: '', label: '' };
    var units = (window.HORIZON || {}).units;
    var shown = units && units.convert ? units.convert(value, fromUnit, obsType) : null;
    if (!shown) {
      return { text: number(value, digits), label: DEFAULT_LABELS[fromUnit] || '' };
    }
    var places = units.decimals ? units.decimals(shown.unit) : digits;
    return {
      text: number(shown.value, places === undefined ? digits : places),
      label: shown.label || DEFAULT_LABELS[shown.unit] || ''
    };
  }

  /* What to call the units the forecast comes in, where the page has no opinion
     because the reader has not chosen a system. */
  var DEFAULT_LABELS = { degree_C: '°C', km_per_hour: 'km/h' };

  /* Number and unit together, the unit smaller: '20.6 °C' reads as one thing. */
  function withUnit(into, value, fromUnit, obsType, digits, tag) {
    var said = reading(value, fromUnit, obsType, digits);
    var host = document.createElement(tag || 'span');
    host.textContent = said.text;
    if (said.label) {
      var unit = document.createElement('small');
      unit.textContent = said.label;
      host.appendChild(unit);
    }
    into.appendChild(host);
    return host;
  }

  function part(parent, cls, text) {
    var el = document.createElement('div');
    el.className = cls;
    if (text !== undefined) el.textContent = text;
    parent.appendChild(el);
    return el;
  }

  function dayCard(day, index, units) {
    /* A button, because it does something: it decides which day the row of hours
       below is showing. Keyboard and screen reader get that for free. */
    var card = document.createElement('button');
    card.type = 'button';
    card.className = 'forecast-day';
    card.dataset.date = day.date;
    card.setAttribute('aria-pressed', index === 0 ? 'true' : 'false');
    var said = described(day.code, false);

    var name = index === 0
      ? ((CFG.text && CFG.text.today) || 'Today')
      : new Date(day.date + 'T12:00:00').toLocaleDateString(lang(), { weekday: 'short' });
    part(card, 'forecast-when', name);
    card.appendChild(icon(said.symbol));
    part(card, 'forecast-what', said.text);

    var temps = part(card, 'forecast-temps');
    withUnit(temps, day.high, 'degree_C', 'outTemp', 1, 'b');
    withUnit(temps, day.low, 'degree_C', 'outTemp', 1, 'span');

    /* A zero says nothing that the picture has not already said, and a column of
       them reads as data where there is none. */
    if (day.rain) part(card, 'forecast-rain', number(day.rain, 0) + '%');
    if (day.wind !== null && day.wind !== undefined) {
      withUnit(part(card, 'forecast-wind'), day.wind, 'km_per_hour', 'windSpeed', 1);
    }
    return card;
  }

  /* The hours of one day, every third one. Twenty-four in a row is a wall of
     numbers, and three hours is as fine as the models resolve anyway.

     Today starts from the hour we are in rather than from midnight: the hours
     already past are not a forecast. Any other day is shown whole. */
  function hourCards(hours, into, date) {
    var now = Date.now();
    var today = new Date().toISOString().slice(0, 10);
    var ahead = hours.filter(function (h) {
      if (date && h.time.slice(0, 10) !== date) return false;
      if (date && date !== today) return true;
      return new Date(h.time).getTime() >= now - HOUR;
    });
    var wanted = OPTS.hours || 8;
    for (var i = 0; i < ahead.length && into.children.length < wanted; i += 3) {
      var h = ahead[i];
      var when = new Date(h.time);
      var dark = when.getHours() < 6 || when.getHours() >= 20;
      var said = described(h.code, dark);

      var card = document.createElement('div');
      card.className = 'forecast-hour';
      if (into.children.length === 0 && (!date || date === today)) card.dataset.now = '';
      part(card, 'forecast-when', ('0' + when.getHours()).slice(-2));
      card.appendChild(icon(said.symbol));
      withUnit(part(card, 'forecast-temps'), h.temperature,
               'degree_C', 'outTemp', 1, 'b');
      if (h.rain) part(card, 'forecast-rain', number(h.rain, 0) + '%');
      into.appendChild(card);
    }
  }

  function draw(data) {
    var panel = document.getElementById('forecast-panel');
    if (!panel || !data || !data.days || !data.days.length) return;
    var units = data.units || {};

    var days = panel.querySelector('.forecast-days');
    days.textContent = '';
    data.days.forEach(function (d, i) { days.appendChild(dayCard(d, i, units)); });

    var hours = panel.querySelector('.forecast-hours');
    var show = function (date) {
      hours.textContent = '';
      if (data.hours && data.hours.length) hourCards(data.hours, hours, date);
      days.querySelectorAll('.forecast-day').forEach(function (b) {
        b.setAttribute('aria-pressed', String(b.dataset.date === date));
      });
    };
    show(data.days[0].date);

    days.addEventListener('click', function (e) {
      var day = e.target.closest('.forecast-day');
      if (day && day.dataset.date) show(day.dataset.date);
    });

    var run = panel.querySelector('.forecast-run');
    if (run && data.run) {
      run.textContent = new Date(data.run).toLocaleString(lang(),
        { weekday: 'short', hour: '2-digit', minute: '2-digit' });
    }
    panel.hidden = false;
  }

  function start() {
    if (!document.getElementById('forecast-panel')) return;

    /* Drawn again when the reader picks another unit. The numbers do not change,
       only what they are written in, so the answer already fetched is enough. */
    var last = null;
    var show = function (data) { last = data; draw(data); };
    document.addEventListener('horizon:units', function () {
      if (last) draw(last);
    });

    var held = cached();
    if (held) { show(held); return; }
    fromFile()
      .then(function (data) { return data || fromOpenMeteo(); })
      .then(function (data) {
        if (!data) return;
        keep(data);
        show(data);
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
