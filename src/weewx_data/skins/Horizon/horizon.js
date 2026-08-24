/* Copyright (c) 2026 Manuel Hilgert
 * Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 */

(function () {
  'use strict';

  var CFG = window.HORIZON || {};
  var DATA_DIR = CFG.dataDir || 'data';
  var STORE = 'weewx.horizon.';

  /* ------------------------------------------------------------- storage */

  function remember(key, value) {
    try { localStorage.setItem(STORE + key, value); } catch (e) { /* private mode */ }
  }

  function recall(key, fallback) {
    try {
      var v = localStorage.getItem(STORE + key);
      return v === null ? fallback : v;
    } catch (e) { return fallback; }
  }

  /* --------------------------------------------------------------- theme */

  function resolvedTheme() {
    var explicit = document.documentElement.getAttribute('data-theme');
    if (explicit) return explicit;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function themeColors() {
    var s = getComputedStyle(document.documentElement);
    return {
      grid: s.getPropertyValue('--chart-grid').trim() || '#e3eaf1',
      axis: s.getPropertyValue('--chart-axis').trim() || '#8397a7',
      night: s.getPropertyValue('--chart-night').trim() || '#eaeef3',
      ink: s.getPropertyValue('--ink').trim() || '#16222e'
    };
  }

  function setupThemeToggle() {
    var button = document.getElementById('theme-toggle');
    if (!button) return;

    var saved = recall('theme', null);
    if (saved === 'dark' || saved === 'light') {
      document.documentElement.setAttribute('data-theme', saved);
    }
    syncLabel();

    button.addEventListener('click', function () {
      var next = resolvedTheme() === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      remember('theme', next);
      syncLabel();
      redrawAll();
    });

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      if (!document.documentElement.getAttribute('data-theme')) { syncLabel(); redrawAll(); }
    });

    function syncLabel() {
      var dark = resolvedTheme() === 'dark';
      button.setAttribute('aria-label',
        dark ? (CFG.text.toLight || 'Switch to light theme')
             : (CFG.text.toDark || 'Switch to dark theme'));
    }
  }

  /* ----------------------------------------------------------- formatting */

  var LOCALE = document.documentElement.lang || undefined;

  function fmtNumber(v, digits) {
    if (v === null || v === undefined || !isFinite(v)) return '–';
    return v.toLocaleString(LOCALE, {
      minimumFractionDigits: digits, maximumFractionDigits: digits
    });
  }

  /* Pick a sensible number of decimals from the spread of the data. */
  function digitsFor(series) {
    var span = 0;
    series.forEach(function (s) {
      var vals = s.values.filter(function (v) { return v !== null; });
      if (!vals.length) return;
      span = Math.max(span, Math.max.apply(null, vals) - Math.min.apply(null, vals));
    });
    if (span === 0) return 1;
    if (span < 1) return 2;
    if (span < 50) return 1;
    return 0;
  }

  function fmtTime(ts, period) {
    var d = new Date(ts * 1000);
    var opts = period === 'day'
      ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }
      : period === 'week'
        ? { weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }
        : { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' };
    return d.toLocaleString(LOCALE, opts);
  }

  /* Axis ticks. uPlot's built-in date formatter is English and 12-hour; use the
     viewer's locale instead, and keep the labels short enough not to collide. */
  function fmtTick(ts, period) {
    var d = new Date(ts * 1000);
    if (period === 'day') {
      return d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    }
    if (period === 'week') {
      return d.getHours() === 0
        ? d.toLocaleDateString(LOCALE, { weekday: 'short' })
        : d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    }
    if (period === 'month') {
      return d.toLocaleDateString(LOCALE, { day: '2-digit', month: '2-digit' });
    }
    return d.toLocaleDateString(LOCALE, { month: 'short' });
  }

  /* -------------------------------------------------------------- shaping */

  /* uPlot wants one shared x axis. Series usually share timestamps already;
     when they do not, fall back to a union and index each series into it. */
  function align(series) {
    var first = series[0].time;
    var same = series.every(function (s) {
      return s.time.length === first.length && s.time[0] === first[0]
        && s.time[s.time.length - 1] === first[first.length - 1];
    });
    if (same) {
      return [first].concat(series.map(function (s) { return s.values; }));
    }

    var set = new Set();
    series.forEach(function (s) { s.time.forEach(function (t) { set.add(t); }); });
    var xs = Array.from(set).sort(function (a, b) { return a - b; });
    var index = new Map();
    xs.forEach(function (t, i) { index.set(t, i); });

    var out = [xs];
    series.forEach(function (s) {
      var col = new Array(xs.length).fill(null);
      s.time.forEach(function (t, i) {
        var at = index.get(t);
        if (at !== undefined) col[at] = s.values[i];
      });
      out.push(col);
    });
    return out;
  }

  /* A gradient stop of 'transparent' is rgba(0,0,0,0), so fading a colour out
     through it runs the middle of the ramp through black. Fade to the same colour
     at zero alpha instead. */
  function fadeOut(color) {
    var c = color.trim();
    var m = c.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
    if (m) {
      var h = m[1];
      if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
      return 'rgba(' + parseInt(h.slice(0, 2), 16) + ','
        + parseInt(h.slice(2, 4), 16) + ','
        + parseInt(h.slice(4, 6), 16) + ',0)';
    }
    m = c.match(/^rgba?\(([^)]+)\)$/i);
    if (m) {
      var parts = m[1].split(',').slice(0, 3).map(function (x) { return x.trim(); });
      return 'rgba(' + parts.join(',') + ',0)';
    }
    return 'rgba(0,0,0,0)';
  }

  /* --------------------------------------------------------------- plugins */

  /* Shade the hours between sunset and sunrise, the way the PNGs do. */
  function nightPlugin(daynight) {
    if (!daynight || !daynight.transitions || !daynight.transitions.length) return null;
    return {
      hooks: {
        drawClear: function (u) {
          var ctx = u.ctx;
          var colors = themeColors();
          var left = u.bbox.left, right = u.bbox.left + u.bbox.width;
          var top = u.bbox.top, height = u.bbox.height;
          var xmin = u.scales.x.min, xmax = u.scales.x.max;

          var bands = (daynight.twilight || []).filter(function (b) {
            return b.to > xmin && b.from < xmax;
          });

          /* Work out the stretches of full night. Counting crossings does not work
             here: the end of dusk and the start of dawn are both "night boundaries"
             but they are not alternating events in the same list. Walk the bands and
             open and close a night instead. */
          var nights = [];
          var openedAt = null;

          if (bands.length) {
            /* If the first thing ahead is dawn, the window opened during the night. */
            if (bands[0].dir === 'dawn') openedAt = xmin;
          } else if (daynight.first === 'night') {
            openedAt = xmin;
          }

          bands.forEach(function (b) {
            if (b.dir === 'dawn') {
              if (openedAt !== null) { nights.push([openedAt, b.from]); openedAt = null; }
            } else {
              openedAt = b.to;              // night proper begins when dusk ends
            }
          });
          if (openedAt !== null) nights.push([openedAt, xmax]);

          /* No twilight data at all: fall back to the horizon crossings. */
          if (!bands.length && daynight.transitions.length) {
            nights = [];
            var isNight = daynight.first === 'night';
            var edges = [xmin].concat(daynight.transitions, [xmax]);
            for (var i = 0; i < edges.length - 1; i++) {
              if (isNight) nights.push([edges[i], edges[i + 1]]);
              isNight = !isNight;
            }
          }

          ctx.save();
          ctx.fillStyle = colors.night;
          nights.forEach(function (n) {
            var x0 = Math.max(u.valToPos(n[0], 'x', true), left);
            var x1 = Math.min(u.valToPos(n[1], 'x', true), right);
            if (x1 > x0) ctx.fillRect(x0, top, x1 - x0, height);
          });

          /* Now the fade across the real civil twilight -- half an hour here, hours
             in a northern summer -- instead of a fixed number of pixels that means
             something different at every time scale. */
          bands.forEach(function (b) {
            var a = u.valToPos(b.from, 'x', true);
            var z = u.valToPos(b.to, 'x', true);
            var x0 = Math.max(Math.min(a, z), left);
            var x1 = Math.min(Math.max(a, z), right);
            if (x1 - x0 < 0.5) return;

            var grad = ctx.createLinearGradient(a, 0, z, 0);
            var clear = fadeOut(colors.night);
            /* Dawn starts dark and clears; dusk does the reverse. */
            grad.addColorStop(0, b.dir === 'dawn' ? colors.night : clear);
            grad.addColorStop(1, b.dir === 'dawn' ? clear : colors.night);

            ctx.fillStyle = grad;
            ctx.fillRect(x0, top, x1 - x0, height);
          });
          ctx.restore();
        }
      }
    };
  }

  /* A wind vector plot is not a line. Each reading is an arrow from the zero line whose
     direction is the wind and whose length is the speed -- the "progressive vector"
     plot WeeWX has always drawn. The arithmetic below is weeplot's, so the canvas and
     the PNG agree:

         scaled = vector * yscale          (both components scaled by the y axis)
         scaled *= e^(i·rotate)            (vector_rotate, 90 degrees by default)
         xEnd = xStart - scaled.real       (x grows right, y grows down)
         yEnd = yStart + scaled.imag
  */
  function vectorPlugin(series) {
    var vectors = series.filter(function (s) {
      return s.plot_type === 'vector' && s.vector_x && s.vector_y;
    });
    if (!vectors.length) return null;

    return {
      hooks: {
        draw: function (u) {
          var ctx = u.ctx;
          var y0 = u.valToPos(0, 'y', true);
          /* Pixels per unit on the y axis. Negative, because canvas y grows downward
             while values grow upward -- the same sign weeplot's yscale carries. */
          var yScale = u.valToPos(1, 'y', true) - y0;

          ctx.save();
          ctx.beginPath();
          ctx.rect(u.bbox.left, u.bbox.top, u.bbox.width, u.bbox.height);
          ctx.clip();

          vectors.forEach(function (s) {
            var rot = (s.vector_rotate || 0) * Math.PI / 180;
            var cos = Math.cos(rot), sin = Math.sin(rot);

            ctx.strokeStyle = s.color || 'currentColor';
            ctx.lineWidth = Math.max(1, Math.round(devicePixelRatio || 1));
            ctx.beginPath();

            for (var i = 0; i < s.time.length; i++) {
              var vx = s.vector_x[i], vy = s.vector_y[i];
              if (vx === null || vy === null) continue;
              var ts = s.time[i];
              if (ts < u.scales.x.min || ts > u.scales.x.max) continue;

              var sx = vx * yScale, sy = vy * yScale;
              if (rot) {
                var rx = sx * cos - sy * sin;
                sy = sx * sin + sy * cos;
                sx = rx;
              }

              var xPix = u.valToPos(ts, 'x', true);
              ctx.moveTo(xPix, y0);
              ctx.lineTo(xPix - sx, y0 + sy);
            }
            ctx.stroke();
          });

          vectors.forEach(function (s) { drawRose(u, s); });

          /* The zero line the arrows hang from. */
          ctx.strokeStyle = themeColors().axis;
          ctx.lineWidth = 1;
          ctx.globalAlpha = 0.5;
          ctx.beginPath();
          ctx.moveTo(u.bbox.left, y0);
          ctx.lineTo(u.bbox.left + u.bbox.width, y0);
          ctx.stroke();

          ctx.restore();
        }
      }
    };
  }

  /* The compass rose the PNGs put in the lower left corner: an arrow to north,
     turned by the same 'vector_rotate' as the arrows themselves, with the label
     upright in the middle. Without it nothing says which way the wind is measured
     from. Shape and proportions follow genplot._renderRose(). */
  function drawRose(u, s) {
    var dpr = devicePixelRatio || 1;
    var ctx = u.ctx;
    var size = 26 * dpr, barb = 4 * dpr, radius = 8 * dpr;
    var cx = u.bbox.left + 10 * dpr + size / 2;
    var cy = u.bbox.top + u.bbox.height - 8 * dpr - size / 2;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.strokeStyle = s.color || themeColors().ink;
    ctx.lineWidth = Math.max(1, Math.round(dpr));
    ctx.globalAlpha = 0.85;

    ctx.save();
    /* PIL turns the image anticlockwise, the canvas turns the other way. */
    ctx.rotate(-(s.vector_rotate || 0) * Math.PI / 180);
    ctx.beginPath();
    /* The shaft stops at the circle rather than running through it, so the label
       inside stays readable. The PNG draws it straight through. */
    ctx.moveTo(0, -size / 2);
    ctx.lineTo(0, -radius);
    ctx.moveTo(0, radius);
    ctx.lineTo(0, size / 2);
    ctx.moveTo(-barb, -size / 2 + barb);
    ctx.lineTo(0, -size / 2);
    ctx.lineTo(barb, -size / 2 + barb);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.restore();

    /* Drawn after the rotation, so it stays the right way up. */
    ctx.globalAlpha = 1;
    ctx.fillStyle = themeColors().axis;
    ctx.font = Math.round(10 * dpr) + 'px ' + getComputedStyle(document.body).fontFamily;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(s.rose_label || 'N', 0, 0.5 * dpr);
    ctx.restore();
  }

  /* The unit, over the y axis. The PNGs put it in the upper left corner, and a
     chart without it says 21.4 and leaves the reader to guess at what. */
  function unitPlugin(label) {
    if (!label) return null;
    return {
      hooks: {
        draw: function (u) {
          var dpr = devicePixelRatio || 1;
          var ctx = u.ctx;
          ctx.save();
          ctx.font = Math.round(11 * dpr) + 'px ' + getComputedStyle(document.body).fontFamily;
          ctx.fillStyle = themeColors().axis;
          ctx.textAlign = 'left';
          ctx.textBaseline = 'bottom';
          /* Clear of the topmost tick, which uPlot centres on the axis top. */
          ctx.fillText(label, 2 * dpr, u.bbox.top - 8 * dpr);
          ctx.restore();
        }
      }
    };
  }

  function tooltipPlugin(meta, digits) {
    var el;
    return {
      hooks: {
        init: function (u) {
          el = document.createElement('div');
          el.className = 'u-tooltip';
          el.style.opacity = '0';
          u.over.appendChild(el);
          u.over.addEventListener('mouseleave', function () { el.style.opacity = '0'; });

          /* Touch has no hover, so a finger dragged across the chart moves the
             cursor instead. Which gesture it is only becomes clear after a few
             pixels: mostly sideways reads the chart, mostly up and down scrolls
             the page, and until then neither is claimed. */
          var startX = 0, startY = 0, reading = null;

          u.over.addEventListener('touchstart', function (e) {
            var t = e.touches[0];
            startX = t.clientX;
            startY = t.clientY;
            reading = null;
          }, { passive: true });

          u.over.addEventListener('touchmove', function (e) {
            var t = e.touches[0];
            if (reading === null) {
              var dx = Math.abs(t.clientX - startX), dy = Math.abs(t.clientY - startY);
              if (dx + dy < 8) return;
              reading = dx > dy;
            }
            if (!reading) return;
            /* Ours now, so the page must not scroll under it. */
            if (e.cancelable) e.preventDefault();
            var box = u.over.getBoundingClientRect();
            u.setCursor({ left: t.clientX - box.left, top: t.clientY - box.top });
          }, { passive: false });

          u.over.addEventListener('touchend', function () {
            reading = null;
            el.style.opacity = '0';
            u.setCursor({ left: -10, top: -10 });
          }, { passive: true });
        },
        setCursor: function (u) {
          var idx = u.cursor.idx;
          if (idx === null || idx === undefined || u.cursor.left < 0) {
            el.style.opacity = '0';
            return;
          }
          var ts = u.data[0][idx];
          var rows = '';
          var any = false;
          for (var i = 1; i < u.data.length; i++) {
            var v = u.data[i][idx];
            if (v === null || v === undefined) continue;
            any = true;
            var s = meta.series[i - 1];
            var extra = '';
            if (s.directions && s.directions[idx] !== null && s.directions[idx] !== undefined) {
              extra = ' · ' + fmtNumber(s.directions[idx], 0) + '°';
            }
            rows += '<div class="t-row" style="color:' + (s.color || 'currentColor') + '">'
              + '<i></i><span style="color:var(--ink)">' + escapeHtml(s.label) + '</span>'
              + '<b style="color:var(--ink)">' + fmtNumber(v, digits) + (meta.unit_label || '')
              + escapeHtml(extra) + '</b></div>';
          }
          if (!any) { el.style.opacity = '0'; return; }

          el.innerHTML = '<div class="t-time">' + escapeHtml(fmtTime(ts, meta._period)) + '</div>' + rows;
          el.style.opacity = '1';

          /* Keep the tooltip inside the plot. */
          var w = el.offsetWidth, h = el.offsetHeight;
          var left = u.cursor.left + 14;
          if (left + w > u.bbox.width / devicePixelRatio) left = u.cursor.left - w - 14;
          var top = u.cursor.top - h - 10;
          if (top < 0) top = u.cursor.top + 16;
          el.style.left = left + 'px';
          el.style.top = top + 'px';
        }
      }
    };
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ---------------------------------------------------------- image export */

  /* The server still writes the classic PNGs, and those remain the right thing to
     link to. This covers what they cannot: the window actually on screen, including
     a zoomed or historical one that was never rendered to a file. */
  function exportChart(entry, card) {
    var src = entry.plot.ctx.canvas;
    var ratio = window.devicePixelRatio || 1;
    var pad = Math.round(12 * ratio);
    var titleHeight = Math.round(30 * ratio);

    var out = document.createElement('canvas');
    out.width = src.width + pad * 2;
    out.height = src.height + titleHeight + pad;
    var ctx = out.getContext('2d');

    var styles = getComputedStyle(document.documentElement);
    var surface = styles.getPropertyValue('--surface').trim() || '#ffffff';
    var ink = styles.getPropertyValue('--ink').trim() || '#000000';
    var faint = styles.getPropertyValue('--ink-faint').trim() || '#888888';

    ctx.fillStyle = surface;
    ctx.fillRect(0, 0, out.width, out.height);

    var family = getComputedStyle(document.body).fontFamily;
    ctx.textBaseline = 'top';

    ctx.fillStyle = ink;
    ctx.font = '600 ' + Math.round(13 * ratio) + 'px ' + family;
    var title = card.querySelector('.chart-title').textContent.trim();
    ctx.fillText(title, pad, Math.round(6 * ratio));

    ctx.fillStyle = faint;
    ctx.font = Math.round(10 * ratio) + 'px ' + family;
    var stamp = (CFG.station || '') + ' · '
      + fmtTime(entry.meta.start, entry.meta._period) + ' – '
      + fmtTime(entry.meta.stop, entry.meta._period);
    ctx.fillText(stamp, pad, Math.round(20 * ratio));

    ctx.drawImage(src, pad, titleHeight);

    var name = entry.meta.name + '-'
      + new Date(entry.meta.stop * 1000).toISOString().slice(0, 10) + '.png';

    out.toBlob(function (blob) {
      if (!blob) return;
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }, 'image/png');
  }

  /* ---------------------------------------------------------------- charts */

  var charts = [];   // {plot, meta, host}

  function buildChart(host, meta, period) {
    meta._period = period;
    var colors = themeColors();
    var data = align(meta.series);
    var digits = digitsFor(meta.series);
    var isBar = meta.series.some(function (s) { return s.plot_type === 'bar'; });
    var ys = meta.yscale;

    var opts = {
      title: '',
      width: host.clientWidth || 600,
      height: Math.max(150, Math.min(260, Math.round((host.clientWidth || 600) * 0.34))),
      padding: [22, 8, 0, 0],     // room for the unit above the y axis
      legend: { show: false },
      cursor: {
        drag: { x: true, y: false, setScale: true },
        points: { size: 6, width: 2 },
        focus: { prox: 24 }
      },
      scales: {
        x: { time: true },
        /* 'yscale' is the axis the ImageGenerator would draw, worked out by the
           generator so that the chart and the PNG of the same plot agree. It is
           null only when a plot has no data to scale. */
        y: ys ? {
          range: function () { return [ys[0], ys[1]]; }
        } : {}
      },
      /* Colors are read at draw time, so switching theme only needs a redraw. */
      axes: [
        {
          stroke: function () { return themeColors().axis; },
          grid: { stroke: function () { return themeColors().grid; }, width: 1 },
          ticks: { stroke: function () { return themeColors().grid; }, width: 1, size: 5 },
          font: '11px ' + getComputedStyle(document.body).fontFamily,
          space: 60,
          values: function (u, splits) {
            return splits.map(function (ts) { return fmtTick(ts, period); });
          }
        },
        {
          stroke: function () { return themeColors().axis; },
          grid: { stroke: function () { return themeColors().grid; }, width: 1 },
          ticks: { show: false },
          font: '11px ' + getComputedStyle(document.body).fontFamily,
          size: 46,
          /* Gridlines where the PNG puts them, but not closer than they can be
             read: on a phone the same increment that suits a 500 pixel image
             stacks the labels on top of each other. Double it until they fit. */
          space: 34,
          splits: ys && ys[2] ? function (u, ai, min, max) {
            var step = ys[2];
            while ((max - min) / step > Math.max(2, u.bbox.height / (34 * (devicePixelRatio || 1)))) {
              step *= 2;
            }
            var out = [];
            for (var v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) {
              /* Round the value, not the value over the step. Dividing here turned
                 a tick at 800 into one at 8, and every label piled up at the
                 bottom of the axis. */
              out.push(Math.round(v * 1e6) / 1e6);
            }
            return out;
          } : null,
          values: function (u, splits) {
            return splits.map(function (v) { return fmtNumber(v, digits); });
          }
        }
      ],
      series: [{ label: 'time' }].concat(meta.series.map(function (s) {
        var base = {
          label: s.label,
          stroke: s.color || colors.ink,
          width: 1.6,
          spanGaps: false,
          points: { show: false }
        };
        if (s.plot_type === 'bar') {
          base.paths = uPlot.paths.bars({ size: [0.85, 24], align: 0 });
          base.fill = s.fill_color || s.color || colors.ink;
          base.stroke = s.fill_color || s.color || colors.ink;
          base.width = 0;
        } else if (s.plot_type === 'vector') {
          /* Drawn by vectorPlugin, from the components. A line through the
             magnitudes would say nothing about direction. The series still has to
             count as shown: uPlot works out a scale's range from its visible series
             only, and a hidden one leaves the y axis on its 0..1 default. */
          base.paths = function () { return null; };
          base.points = { show: false };
        }
        return base;
      })),
      plugins: [tooltipPlugin(meta, digits), vectorPlugin(meta.series),
                unitPlugin(meta.unit_label)].concat(
        isBar ? [] : [nightPlugin(meta.daynight)]
      ).filter(Boolean)
    };

    var plot = new uPlot(opts, data, host);
    return { plot: plot, meta: meta, host: host };
  }

  function redrawAll() {
    /* Axis colors and the night shading resolve themselves at draw time, so a
       plain redraw is enough. The first argument is rebuildPaths: it must stay
       true, or the canvas is cleared and nothing is drawn back onto it. */
    charts.forEach(function (c) { c.plot.redraw(true, true); });
  }

  /* Resize charts to their container. One observer for all of them. */
  var resizeObserver = new ResizeObserver(function (entries) {
    entries.forEach(function (entry) {
      var c = charts.find(function (x) { return x.host === entry.target; });
      if (!c) return;
      var w = Math.round(entry.contentRect.width);
      if (w > 0 && w !== c.plot.width) {
        c.plot.setSize({ width: w, height: Math.max(150, Math.min(260, Math.round(w * 0.34))) });
      }
    });
  });

  /* ------------------------------------------------------------- rendering */

  function renderTable(meta, digits) {
    var head = '<tr><th>' + escapeHtml(CFG.text.time || 'Time') + '</th>'
      + meta.series.map(function (s) { return '<th>' + escapeHtml(s.label) + '</th>'; }).join('')
      + '</tr>';
    var data = align(meta.series);
    var rows = [];
    /* Show every sample. An aggregated plot is a few hundred rows at most; only
       an unaggregated long span needs thinning, and then we say so. */
    var LIMIT = 1500;
    var total = data[0].length;
    var step = total > LIMIT ? Math.ceil(total / LIMIT) : 1;

    for (var i = 0; i < total; i += step) {
      var cells = '';
      for (var j = 1; j < data.length; j++) {
        cells += '<td>' + fmtNumber(data[j][i], digits) + '</td>';
      }
      rows.push('<tr><td class="metric">' + escapeHtml(fmtTime(data[0][i], meta._period))
        + '</td>' + cells + '</tr>');
    }

    var note = step > 1
      ? '<p class="table-note">' + escapeHtml((CFG.text.thinned || 'Showing every {n}th of {total} readings.')
          .replace('{n}', step).replace('{total}', total)) + '</p>'
      : '';

    return note + '<div class="scroller"><table class="data-table"><thead>' + head
      + '</thead><tbody>' + rows.join('') + '</tbody></table></div>';
  }

  function renderChart(card, meta, period) {
    var host = card.querySelector('.chart-host');
    var legend = card.querySelector('.chart-title');
    var details = card.querySelector('.chart-data');

    host.innerHTML = '';

    if (!meta.series.length) {
      host.innerHTML = '<p class="chart-empty">' + escapeHtml(CFG.text.noData || 'No data') + '</p>';
      return;
    }

    /* The title doubles as the legend: each series name in its own colour. Saying
       it twice wastes a line, which matters on a phone. */
    legend.innerHTML = meta.series.map(function (s) {
      return '<span style="color:' + (s.color || 'currentColor') + '"><i></i>'
        + '<span class="series-name">' + escapeHtml(s.label) + '</span></span>';
    }).join('');

    var entry = buildChart(host, meta, period);
    charts.push(entry);
    resizeObserver.observe(host);

    /* Two ways out of the chart: the file the server rendered (a stable URL, good
       for linking) and the view on screen (good for anything else). */
    var actions = card.querySelector('.chart-actions');
    if (actions) {
      var save = document.createElement('button');
      save.type = 'button';
      save.className = 'chart-action';
      save.textContent = CFG.text.saveImage || 'Save image';
      save.addEventListener('click', function () { exportChart(entry, card); });
      actions.appendChild(save);

      /* The rendered PNG only exists for the four standard windows. */
      if (anchor === null && CFG.hasImages && meta.name) {
        var link = document.createElement('a');
        link.className = 'chart-action';
        link.href = meta.name + '.png';
        link.textContent = CFG.text.imageLink || 'PNG';
        link.title = CFG.text.imageLinkTitle || 'Permanent link to the rendered image';
        actions.appendChild(link);
      }
    }

    if (details) {
      var digits = digitsFor(meta.series);
      details.querySelector('.scroller-host').innerHTML = renderTable(meta, digits);
    }
  }

  function clearCharts() {
    charts.forEach(function (c) {
      resizeObserver.unobserve(c.host);
      c.plot.destroy();
    });
    charts = [];
    document.querySelectorAll('#charts .chart-card').forEach(function (card) {
      lazyObserver.unobserve(card);
    });
  }

  /* --------------------------------------------------------------- periods */

  var cache = new Map();
  var manifest = null;

  /* ------------------------------------------------------- history archive */

  /* The four period files are snapshots of "now". To look further back, the archive
     is used instead: one file per plot group and calendar year, on a fixed grid.
     Only the years a window actually touches are fetched, and each is kept once. */

  var archiveIndex = null;
  var archiveCache = new Map();           // "group-year" -> payload

  /* The end of the window on screen, as a timestamp. null means "now", which is the
     only view that follows the clock. Everything else is pinned to a moment in time,
     so that a link keeps showing the same days tomorrow as it does today. */
  var anchor = null;

  /* Only used for the live view, which slides: at half past midnight you want to see
     last evening, not an empty "today". Everything you page back to is a whole
     calendar unit instead -- Tuesday, week 33, July, 2025 -- which is what people
     mean when they click "back".

     These are fallbacks. The real lengths come from the manifest, which reads them
     from 'time_length' in skin.conf -- so changing the configuration moves the charts
     and the PNGs together, instead of only the PNGs. */
  var PERIOD_SECONDS = { day: 27 * 3600, week: 7 * 86400, month: 30 * 86400, year: 365 * 86400 };

  function adoptSpans(manifest) {
    if (!manifest || !manifest.spans) return;
    Object.keys(manifest.spans).forEach(function (group) {
      /* The manifest names the section ('day_images'); the page names the period. */
      var period = group.replace(/_images$/, '');
      var seconds = parseInt(manifest.spans[group], 10);
      if (seconds > 0) PERIOD_SECONDS[period] = seconds;
    });
  }

  /* Two different "nows", and mixing them up moves the calendar.

     dataTs() is the last reading in the report, and everything the arrows do is
     measured from it. The live view ends there, so the unit it falls in is the unit
     on screen, and "back" means the one before that.

     nowTs() is the reader's clock. It only decides whether the live view can still
     be called "now": the two part company when a station was off overnight, when a
     page has been open past midnight, or when a site is served from a cache. */
  function nowTs() {
    return Math.floor(Date.now() / 1000);
  }

  function dataTs() {
    return CFG.generated || nowTs();
  }

  /* The calendar unit of `period` that contains `ts`. */
  function calendarWindow(period, ts) {
    var d = new Date(ts * 1000);
    var y = d.getFullYear(), m = d.getMonth(), day = d.getDate();
    var from, to;

    if (period === 'day') {
      from = new Date(y, m, day);
      to = new Date(y, m, day + 1);
    } else if (period === 'week') {
      /* week_start comes from the station config: 0 = Monday, 6 = Sunday. */
      var startDow = (CFG.weekStart === undefined ? 0 : +CFG.weekStart);
      var jsStart = (startDow + 1) % 7;            // JS counts Sunday as 0
      var back = (d.getDay() - jsStart + 7) % 7;
      from = new Date(y, m, day - back);
      to = new Date(from.getFullYear(), from.getMonth(), from.getDate() + 7);
    } else if (period === 'month') {
      from = new Date(y, m, 1);
      to = new Date(y, m + 1, 1);
    } else {
      from = new Date(y, 0, 1);
      to = new Date(y + 1, 0, 1);
    }
    return { from: Math.floor(from.getTime() / 1000), to: Math.floor(to.getTime() / 1000) };
  }

  /* The window currently on screen. */
  function currentWindow(period) {
    if (anchor === null) {
      var to = dataTs();
      return { from: to - (PERIOD_SECONDS[period] || PERIOD_SECONDS.day), to: to, live: true };
    }
    var w = calendarWindow(period, anchor);
    w.live = false;
    return w;
  }

  function loadArchiveIndex() {
    if (archiveIndex) return Promise.resolve(archiveIndex);
    return fetch(DATA_DIR + '/archive/index.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { archiveIndex = j || { groups: [] }; return archiveIndex; })
      .catch(function () { archiveIndex = { groups: [] }; return archiveIndex; });
  }

  function loadArchiveYear(group, year) {
    var key = group + '-' + year;
    if (archiveCache.has(key)) return Promise.resolve(archiveCache.get(key));
    return fetch(DATA_DIR + '/archive/' + key + '.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { archiveCache.set(key, j); return j; })
      .catch(function () { archiveCache.set(key, null); return null; });
  }

  var daynightCache = new Map();

  function loadDayNight(year) {
    if (daynightCache.has(year)) return Promise.resolve(daynightCache.get(year));
    /* Only years the archive actually covers. */
    if (archiveIndex && archiveIndex.first
        && year < new Date(archiveIndex.first * 1000).getFullYear()) {
      daynightCache.set(year, null);
      return Promise.resolve(null);
    }
    return fetch(DATA_DIR + '/archive/daynight-' + year + '.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { daynightCache.set(year, j); return j; })
      .catch(function () { daynightCache.set(year, null); return null; });
  }

  /* Night bands only say something on a window short enough to show individual days;
     on a month or a year they turn into a grey smear, which is why the PNGs switch
     them off there too. */
  function nightForWindow(from, to, years) {
    if ((to - from) > 9 * 86400) return Promise.resolve(null);
    return Promise.all(years.map(loadDayNight)).then(function (files) {
      var all = [];
      var bands = [];
      var first = null;
      files.filter(Boolean).forEach(function (f) {
        if (first === null) {
          /* Work out the state at `from` by counting the transitions before it. */
          var before = f.transitions.filter(function (t) { return t <= from; }).length;
          var startState = f.first === 'day' ? 'day' : 'night';
          first = (before % 2 === 0) ? startState : (startState === 'day' ? 'night' : 'day');
        }
        all = all.concat(f.transitions.filter(function (t) { return t > from && t < to; }));
        /* The twilight bands travel with the transitions. Dropping them here left
           the archive with hard edges where the live view fades. */
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

  /* Assemble one window from however many year files it spans. */
  function windowFromArchive(group, from, to) {
    /* The index knows which years exist for this group. Asking for the others would
       only produce 404s in the console of every visitor. */
    var known = null;
    if (archiveIndex && archiveIndex.groups) {
      var entry = archiveIndex.groups.find(function (g) { return g.name === group; });
      if (entry && entry.years) known = entry.years;
    }

    var years = [];
    for (var y = new Date(from * 1000).getFullYear(); y <= new Date(to * 1000).getFullYear(); y++) {
      if (!known || known.indexOf(y) >= 0) years.push(y);
    }
    if (!years.length) return Promise.resolve(null);

    return Promise.all([
      Promise.all(years.map(function (y) { return loadArchiveYear(group, y); })),
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

        var template = present[0];
        var series = template.series.map(function (s) {
          return {
            obs_type: s.obs_type,
            label: s.label,
            color: s.color,
            plot_type: s.plot_type || 'line',
            time: [],
            values: new Array(slots).fill(null)
          };
        });

        present.forEach(function (file) {
          file.series.forEach(function (s, si) {
            if (si >= series.length) return;
            for (var i = 0; i < s.values.length; i++) {
              var ts = file.start + i * file.interval;
              var slot = Math.round((ts - start) / interval);
              if (slot >= 0 && slot < slots && s.values[i] !== null) {
                series[si].values[slot] = s.values[i];
              }
            }
          });
        });

        var times = new Array(slots);
        for (var k = 0; k < slots; k++) times[k] = start + k * interval;
        series.forEach(function (s) { s.time = times; });

        var out = {
          name: group,
          start: start,
          stop: start + slots * interval,
          unit: template.unit,
          unit_label: template.unit_label,
          aggregate_interval: interval,
          series: series
        };
        if (daynight) out.daynight = daynight;
        return out;
      })();
    });
  }

  function loadManifest() {
    if (manifest) return Promise.resolve(manifest);
    return fetch(DATA_DIR + '/index.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (json) {
        manifest = json || { plots: [] };
        adoptSpans(manifest);
        return manifest;
      })
      .catch(function () { manifest = { plots: [] }; return manifest; });
  }

  function loadPlot(name) {
    if (cache.has(name)) return Promise.resolve(cache.get(name));
    return fetch(DATA_DIR + '/' + name + '.json', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (json) { cache.set(name, json); return json; })
      .catch(function () { cache.set(name, null); return null; });
  }

  /* Draw a card's chart the first time it comes near the viewport. On a phone that
     means one or two fetches on load instead of twenty. */
  var lazyObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      var card = entry.target;
      lazyObserver.unobserve(card);
      hydrate(card);
    });
  }, { rootMargin: '300px 0px' });

  function hydrate(card) {
    if (card.dataset.loaded) return;
    card.dataset.loaded = '1';

    var period = card.dataset.period;
    var empty = '<p class="chart-empty">' + escapeHtml(CFG.text.noData || 'No data') + '</p>';

    /* The live window uses the ready-made snapshot: full resolution, with the
       day/night bands. Anything pinned to the past comes from the archive. */
    var source = anchor === null
      ? loadPlot(card.dataset.plot)
      : windowFromArchive(card.dataset.group, +card.dataset.from, +card.dataset.to);

    source.then(function (meta) {
      if (!meta || !meta.series || !meta.series.length) {
        card.querySelector('.chart-host').innerHTML = empty;
        return;
      }
      var any = meta.series.some(function (s) {
        return s.values.some(function (v) { return v !== null; });
      });
      if (!any) {
        card.querySelector('.chart-host').innerHTML = empty;
        return;
      }
      renderChart(card, meta, period);
    });
  }

  var currentPeriod = null;

  /* ------------------------------------------------------------ shared links */

  /* A rendered PNG can be linked because a web server hands it out as a file. The
     canvas export cannot: it exists only in the browser that made it. What *can* be
     shared is the view itself, which is usually what someone means anyway -- and it
     arrives current, in the reader's language and theme. */

  /* The link carries a date, not an offset. "Three weeks back" would point somewhere
     else next week; "the week ending 2 August 2026" does not move. */
  function writeLocation(period) {
    var hash = '#' + period;
    if (anchor !== null) {
      /* Name the unit, not an arbitrary instant inside it: #month/2026-07 rather
         than #month/2026-07-13. */
      var d = new Date(calendarWindow(period, anchor).from * 1000);
      var y = d.getFullYear();
      var mm = String(d.getMonth() + 1).padStart(2, '0');
      var dd = String(d.getDate()).padStart(2, '0');
      hash += '/' + (period === 'year' ? y
        : period === 'month' ? y + '-' + mm
        : y + '-' + mm + '-' + dd);
    }
    if (window.location.hash !== hash) {
      history.replaceState(null, '', window.location.pathname + window.location.search + hash);
    }
  }

  function readLocation() {
    var hash = window.location.hash.replace(/^#/, '');
    if (!hash) return null;
    var parts = hash.split('/');
    var period = parts[0];
    if ((CFG.periods || []).indexOf(period) < 0) return null;

    if (!parts[1]) return { period: period, anchor: null };

    /* Accepts 2026, 2026-07 and 2026-07-13, whichever suits the period. Anything
       inside the unit resolves to the unit, so a hand-typed date still works. */
    var m = parts[1].match(/^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?(?:T\d{1,2})?$/);
    if (!m) {
      /* Tolerate the older "-3" form rather than dropping the reader at "now". */
      var n = parseInt(parts[1].replace(/^-/, ''), 10);
      if (!isNaN(n) && n > 0) {
        var span = PERIOD_SECONDS[period] || PERIOD_SECONDS.day;
        return { period: period, anchor: dataTs() - n * span };
      }
      return { period: period, anchor: null };
    }

    var d = new Date(+m[1], m[2] ? +m[2] - 1 : 0, m[3] ? +m[3] : 1, 12, 0, 0);
    var ts = Math.floor(d.getTime() / 1000);
    /* A unit that is still running is the live view. */
    var unit = calendarWindow(period, ts);
    return { period: period, anchor: unit.to > dataTs() ? null : ts };
  }

  function showPeriod(period, newAnchor) {
    var container = document.getElementById('charts');
    if (!container) return;

    if (newAnchor !== undefined) anchor = newAnchor;
    if (period !== currentPeriod && newAnchor === undefined) {
      anchor = null;                               // switching span returns to now
    }
    currentPeriod = period;

    clearCharts();
    container.setAttribute('aria-busy', 'true');

    var win = currentWindow(period);
    var from = win.from, to = win.to, live = win.live;

    Promise.all([loadManifest(), loadArchiveIndex()]).then(function (res) {
      var mf = res[0], ai = res[1];
      var groups = CFG.plotGroups || [];

      /* Keep the order the skin configured, not the order the files were written. */
      var wanted = groups.map(function (g) {
        var snapshot = mf.plots.find(function (p) { return p.name === period + g; });
        var archived = (ai.groups || []).find(function (p) { return p.name === g; });
        if (live) {
          return snapshot ? { group: g, name: snapshot.name, title: snapshot.title } : null;
        }
        return archived ? { group: g, name: g, title: archived.title } : null;
      }).filter(Boolean);

      container.innerHTML = '';
      updateRange(period, from, to, ai);

      if (!wanted.length) {
        container.innerHTML = '<p class="chart-empty">'
          + escapeHtml(CFG.text.noData || 'No data') + '</p>';
        container.setAttribute('aria-busy', 'false');
        return;
      }

      wanted.forEach(function (entry) {
        var card = document.createElement('section');
        card.className = 'chart-card';
        card.dataset.plot = entry.name;
        card.dataset.group = entry.group;
        card.dataset.period = period;
        card.dataset.from = from;
        card.dataset.to = to;
        card.innerHTML =
          '<div class="chart-head">'
          + '<h3 class="chart-title chart-legend">' + escapeHtml(entry.title) + '</h3>'
          + '<div class="chart-actions"></div>'
          + '</div>'
          + '<div class="chart-host"><div class="chart-skeleton"></div></div>'
          + '<details class="chart-data"><summary>'
          + escapeHtml(CFG.text.showData || 'Show data')
          + '</summary><div class="scroller-host"></div></details>';
        container.appendChild(card);
        lazyObserver.observe(card);
      });

      container.setAttribute('aria-busy', 'false');
    });

    document.querySelectorAll('#period-tabs button').forEach(function (b) {
      b.setAttribute('aria-selected', String(b.dataset.period === period));
    });
    remember('period', period);
    writeLocation(period);
  }

  /* Name the calendar unit on screen: "Tuesday, 18 August 2026", "11–17 Aug 2026",
     "July 2026", "2025". */
  function unitLabel(period, from, to) {
    var start = new Date(from * 1000);
    var end = new Date((to - 1) * 1000);

    if (period === 'day') {
      return start.toLocaleDateString(LOCALE,
        { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
    if (period === 'week') {
      var opts = { day: 'numeric', month: 'short', year: 'numeric' };
      /* formatRange knows how each language shortens a span -- "10.–16. Aug. 2026"
         in German, "10 – 16 Aug 2026" in English. Hand-joining two formatted dates
         gets the punctuation wrong in most of them. */
      try {
        return new Intl.DateTimeFormat(LOCALE, opts).formatRange(start, end);
      } catch (e) {
        return start.toLocaleDateString(LOCALE, opts) + ' – '
          + end.toLocaleDateString(LOCALE, opts);
      }
    }
    if (period === 'month') {
      return start.toLocaleDateString(LOCALE, { month: 'long', year: 'numeric' });
    }
    return String(start.getFullYear());
  }

  /* "Now" is only honest while the last reading falls in the unit the clock is in.
     Older than that, the live view is showing Sunday and calling it now, and the
     step back to Saturday looks as if it skipped a day. Name the unit instead. */
  function liveLabel(period) {
    var d = calendarWindow(period, dataTs());
    return d.from === calendarWindow(period, nowTs()).from
      ? (CFG.text.now || 'Now')
      : unitLabel(period, d.from, d.to);
  }

  /* Label the window being shown, and disable the arrows at the ends of the record. */
  function updateRange(period, from, to, ai) {
    var label = document.getElementById('range-label');
    var back = document.getElementById('range-back');
    var fwd = document.getElementById('range-fwd');
    var now = document.getElementById('range-now');
    if (!label) return;

    label.textContent = anchor === null
      ? liveLabel(period)
      : unitLabel(period, from, to);

    if (fwd) fwd.disabled = anchor === null;
    if (now) now.hidden = anchor === null;

    /* Do not walk off the start of the record. */
    if (back && ai && ai.first) {
      back.disabled = from <= ai.first;
    }
  }

  /* Move one whole calendar unit. From the live view, "back" lands on the last
     complete unit; stepping forward into the unit still running returns to following
     the clock. */
  function step(direction) {
    var here = calendarWindow(currentPeriod, anchor === null ? dataTs() : anchor);
    var target = direction < 0 ? here.from - 1 : here.to + 1;
    /* The unit the data end in is the live view, the same rule readLocation()
       applies to a pasted link. Testing the instant instead of the unit it falls in
       left "forward" one short: it landed on the current unit as an archive window,
       so it took two steps to get back. */
    var unit = calendarWindow(currentPeriod, target);
    showPeriod(currentPeriod, unit.to > dataTs() ? null : target);
  }

  function setupRangeNav() {
    var back = document.getElementById('range-back');
    var fwd = document.getElementById('range-fwd');
    var now = document.getElementById('range-now');
    if (back) back.addEventListener('click', function () { step(-1); });
    if (fwd) fwd.addEventListener('click', function () {
      if (anchor !== null) step(1);
    });
    if (now) now.addEventListener('click', function () { showPeriod(currentPeriod, null); });

    var share = document.getElementById('range-share');
    if (share) {
      share.addEventListener('click', function () {
        var url = window.location.href;
        var done = function () {
          var was = share.textContent;
          share.textContent = CFG.text.linkCopied || 'Link copied';
          setTimeout(function () { share.textContent = was; }, 1800);
        };
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(url).then(done, function () { prompt(url); });
        } else {
          /* Plain http, which most stations serve: no clipboard API available. */
          window.prompt(CFG.text.copyLink || 'Copy this link:', url);
        }
      });
    }

    /* Arrow keys move through time when the chart area has focus. */
    var container = document.getElementById('charts');
    if (container) {
      container.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft') { step(-1); e.preventDefault(); }
        if (e.key === 'ArrowRight' && anchor !== null) { step(1); e.preventDefault(); }
      });
    }
  }

  function setupPeriods() {
    var tabs = document.getElementById('period-tabs');
    if (!tabs) return;
    tabs.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-period]');
      if (b) showPeriod(b.dataset.period);
    });

    /* Opening the data table on a card that has not been drawn yet must still
       produce a table. */
    var container = document.getElementById('charts');
    if (container) {
      container.addEventListener('toggle', function (e) {
        if (e.target.matches('details.chart-data') && e.target.open) {
          var card = e.target.closest('.chart-card');
          if (card) hydrate(card);
        }
      }, true);
    }
    setupRangeNav();

    /* A link wins over what this browser last looked at. */
    var linked = readLocation();
    if (linked) {
      currentPeriod = linked.period;
      showPeriod(linked.period, linked.anchor);
    } else {
      var start = recall('period', (CFG.periods || ['day'])[0]);
      if ((CFG.periods || []).indexOf(start) < 0) start = (CFG.periods || ['day'])[0];
      showPeriod(start, null);
    }

    /* Back and forward buttons, and links pasted into the same tab. */
    window.addEventListener('hashchange', function () {
      var loc = readLocation();
      if (loc && (loc.period !== currentPeriod || loc.anchor !== anchor)) {
        currentPeriod = loc.period;
        showPeriod(loc.period, loc.anchor);
      }
    });
  }

  /* ------------------------------------------------------------ live update */

  function setupLiveUpdate() {
    var seconds = parseInt(CFG.refreshInterval, 10);
    if (!seconds || seconds < 5) return;

    var stamp = document.querySelector('[data-live="dateTime"]');

    setInterval(function () {
      fetch('current.json', { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data) return;
          document.querySelectorAll('[data-live]').forEach(function (el) {
            var key = el.dataset.live;
            if (data[key] !== undefined && data[key] !== null) {
              el.textContent = data[key];
              el.classList.remove('is-stale');
            }
          });
          /* New archive record: the plots are stale too. */
          if (stamp && data.dateTime_raw && stamp.dataset.raw
              && String(data.dateTime_raw) !== String(stamp.dataset.raw)) {
            stamp.dataset.raw = data.dateTime_raw;
            cache.clear();
            manifest = null;
            var active = document.querySelector('#period-tabs button[aria-selected="true"]');
            if (active) showPeriod(active.dataset.period);
          }
        })
        .catch(function () { /* offline; try again next tick */ });
    }, seconds * 1000);
  }

  /* ----------------------------------------------------------------- start */

  function init() {
    CFG.text = CFG.text || {};
    setupThemeToggle();
    setupPeriods();
    setupLiveUpdate();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
