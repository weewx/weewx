/*    Copyright (c) 2026 Manuel Hilgert
 *    Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 *
 * Fills the forecast panel. The forecast comes from data/forecast.json where the
 * station writes that file. Otherwise the browser asks Open-Meteo, if
 * `browser_fetch` is true. forecast-fetch.py documents the format of the file. See
 * "Customizing the Horizon skin" in the Customization Guide for the choice between
 * the two sources.
 */

(function () {
  'use strict';

  var CFG = window.HORIZON || {};
  var OPTS = CFG.forecast || {};
  var STORE = 'weewx.horizon.forecast';
  var HOUR = 3600 * 1000;

  /* The icon for each WMO 4677 code, as a file name in icons/forecast/. The text
     for a code comes from CFG.forecast.sky, which scripts.inc translates. */
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

  /* The night icons, which show the moon, for the three icons that show the sun. */
  var NIGHT = {
    clear: 'clear-night', 'mostly-clear': 'mostly-clear-night',
    'partly-cloudy': 'partly-cloudy-night'
  };

  /* Returns the text and the icon for a WMO code, e.g., { text: 'Light rain',
     symbol: 'rain' } for 61. With `dark` true, a sun icon becomes its night icon. */
  function described(code, dark) {
    var said = (OPTS.sky || {})[code] || '';
    var symbol = SYMBOLS[code];
    if (!symbol) {
      /* A code missing from SYMBOLS takes the icon of the lowest listed code in the
         same group of ten, e.g., 62 takes the icon of 61. Where CFG.forecast.sky has
         no text for the missing code, the text of that listed code is used. */
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
    /* Where the station does not write data/forecast.json, the request ends in a
       404. fromFile() then returns null, and start() asks Open-Meteo instead. */
    return fetch((CFG.dataDir || 'data') + '/forecast.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  /* Asks Open-Meteo and returns the answer in the format of data/forecast.json (see
     to_horizon() in forecast-fetch.py), so that draw() handles both sources alike.
     Returns null where `browser_fetch` is false or the request fails. */
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

  /* Returns the forecast that keep() stored less than an hour ago, or null. A reader
     who opens the front page several times within the hour causes one request, not
     one per visit. */
  function cached() {
    try {
      var held = JSON.parse(localStorage.getItem(STORE) || 'null');
      if (held && Date.now() - held.at < HOUR) return held.data;
    } catch (e) { /* Storage is blocked, or the stored text is not JSON. */ }
    return null;
  }

  function keep(data) {
    try {
      localStorage.setItem(STORE, JSON.stringify({ at: Date.now(), data: data }));
    } catch (e) { /* Without storage, every page view fetches the forecast. */ }
  }

  /* ------------------------------------------------------------- rendering */

  function icon(symbol) {
    var span = document.createElement('span');
    span.className = 'forecast-icon';
    span.setAttribute('aria-hidden', 'true');
    /* horizon.css colours the icon by its data-symbol. */
    span.dataset.symbol = symbol;
    span.style.setProperty('--icon', 'url(icons/forecast/' + symbol + '.svg)');
    return span;
  }

  function number(value, digits) {
    if (value === null || value === undefined) return '';
    return Number(value).toLocaleString(lang(),
      { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  /* Returns { text, label } for a value in `fromUnit`, written in the unit system the
     reader chose or, without a choice, in the report unit system, e.g.,
     { text: '68.0', label: '°F' }. The callers pass every forecast temperature as
     degree_C and every wind speed as km_per_hour. */
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

  /* The labels of degree_C and km_per_hour, the units the forecast arrives in.
     reading() uses DEFAULT_LABELS where CFG.units converts nothing, i.e., where the
     page shows the same units or horizon.js has not loaded data/index.json yet. */
  var DEFAULT_LABELS = { degree_C: '°C', km_per_hour: 'km/h' };

  /* Appends to `into` a `tag` element that holds the value and, in a <small>, its
     unit label, e.g., <b>20.6<small>°C</small></b>. Returns the new element. */
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
    /* The day is a button, because a click on the day makes the row below show the
       hours of that day, and the keyboard can reach and press a button. */
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

    /* A chance of rain of 0 % is left out, because the icon already shows a dry
       day. */
    if (day.rain) part(card, 'forecast-rain', number(day.rain, 0) + '%');
    if (day.wind !== null && day.wind !== undefined) {
      withUnit(part(card, 'forecast-wind'), day.wind, 'km_per_hour', 'windSpeed', 1);
    }
    return card;
  }

  /* Shows the hours of `date`, one every three hours, up to OPTS.hours of them.
     Today's hours start at the current hour, because an hour already past is not a
     forecast. Any other day starts at midnight. */
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

    /* When the reader chooses another unit system, the forecast already fetched is
       drawn again in the new units. */
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

  /* start() runs at once. scripts.inc loads this file after the page's markup and
     after horizon.js, which provides CFG.units. */
  start();
})();
