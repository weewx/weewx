/*    Copyright (c) 2026 Manuel Hilgert
 *    Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 *
 * The two parts of the Deck flavour that a stylesheet cannot reach.
 *
 * Everything else about that look is in flavor-deck.css, which is where it
 * belongs. This file exists for the two places where the arrangement itself
 * differs rather than the paint:
 *
 *   The navigation moves into a column of its own, grouped under headings,
 *   instead of sitting in a row across the top.
 *
 * The readings need nothing here: the skin already wraps each <dt> and its <dd>
 * in a <div>, so the stylesheet has something to draw a tile around.
 *
 * Nothing is moved that the skin's own code holds a reference to by position.
 * The period buttons keep their listeners because they are the same elements,
 * only somewhere else in the document.
 *
 * To use it, add to skin.conf:
 *
 *     [DisplayOptions]
 *         custom_css = flavor-deck.css
 *
 * and put this file in 'copy_once' beside it, then reference it from the
 * templates, or load it from your own [[Extras]] script tag.
 */

(function () {
  'use strict';

  /* A glyph for each entry, by what the entry leads to. The time spans are known
     by the period they carry; the pages by the file they point at. Anything not
     listed simply gets none. */
  var NAV_ICONS = {
    day: 'nav-today', week: 'nav-week', month: 'nav-month', year: 'nav-year',
    'climate.html': 'nav-page', 'statistics.html': 'nav-statistics',
    'celestial.html': 'nav-celestial', 'reports.html': 'nav-archive',
    'telemetry.html': 'nav-monitor', 'sensor-status.html': 'nav-sensors'
  };

  function markIcon(el) {
    var key = el.dataset.period
      || (el.getAttribute('href') || '').split('/').pop();
    var icon = NAV_ICONS[key];
    if (!icon) return;
    var glyph = document.createElement('span');
    glyph.className = 'nav-icon';
    glyph.setAttribute('aria-hidden', 'true');
    glyph.style.setProperty('--icon', 'url(icons/' + icon + '.svg)');
    el.insertBefore(glyph, el.firstChild);
  }

  /* One <section> per group of links, with its heading, the way the flavour
     draws its navigation. */
  function group(title, nodes) {
    if (!nodes.length) return null;
    var section = document.createElement('section');
    section.className = 'deck-nav-group';
    var head = document.createElement('h2');
    head.textContent = title;
    section.appendChild(head);
    var list = document.createElement('div');
    list.className = 'deck-nav-list';
    nodes.forEach(function (n) { markIcon(n); list.appendChild(n); });
    section.appendChild(list);
    return section;
  }

  /* The heading a group gets. Taken from the page where the page has one, so a
     translated skin gets translated headings rather than English ones. */
  function labelled(name, fallback) {
    var el = document.querySelector('[data-deck-label="' + name + '"]');
    return (el && el.textContent.trim()) || fallback;
  }

  function buildSidebar() {
    var wrap = document.querySelector('.wrap');
    var masthead = wrap && wrap.querySelector('.masthead');
    if (!wrap || !masthead || document.querySelector('.deck-sidebar')) return;

    var aside = document.createElement('nav');
    aside.className = 'deck-sidebar';
    aside.setAttribute('aria-label', labelled('nav', 'Sections'));

    /* The time spans, which are buttons the skin already listens to. Moving the
       element keeps the listener; copying it would not. */
    var tabs = document.getElementById('period-tabs');
    if (tabs) {
      var spans = group(labelled('spans', 'Conditions'),
                        Array.prototype.slice.call(tabs.children));
      if (spans) {
        spans.querySelector('.deck-nav-list').id = 'period-tabs';
        spans.querySelector('.deck-nav-list').setAttribute('role', 'tablist');
        tabs.parentNode.removeChild(tabs);
        aside.appendChild(spans);
      }
    }

    /* The other pages of the skin. RSS is a feed rather than a page, so it stays
       in the masthead where it does not look like a section. */
    var links = Array.prototype.slice
      .call(masthead.querySelectorAll('.masthead-link'))
      .filter(function (a) { return !/\.xml$/.test(a.getAttribute('href') || ''); });
    var station = group(labelled('station', 'Station'), links);
    if (station) aside.appendChild(station);

    wrap.insertBefore(aside, masthead.nextSibling);
    document.documentElement.classList.add('deck-has-sidebar');
  }

  /* The station's particulars and the colophon, together at the foot of the page.

     Beside the readings the particulars take a column's width to say the altitude
     and the version number; at the bottom they say the same thing and cost
     nothing. The line about WeeWX is already down there, and one footer reads
     better than a panel with a paragraph after it.

     The heading stays for anyone listening rather than looking: on screen the
     placement says what this is, but a screen reader has only the words. */
  function buildFooter() {
    var wrap = document.querySelector('.wrap');
    if (!wrap || document.querySelector('footer.deck-footer')) return;
    var about = document.querySelector('[data-live-panel="about"]');
    var colophon = wrap.querySelector('p.footer');
    /* One of the two is enough: the other pages carry no station panel, and the
       line about WeeWX should still sit in a footer rather than loose under the
       last card. */
    if (!about && !colophon) return;

    var foot = document.createElement('footer');
    foot.className = 'deck-footer';

    var head = about && about.querySelector('.panel-head h2');
    if (head) {
      var quiet = document.createElement('h2');
      quiet.className = 'visually-hidden';
      quiet.textContent = head.textContent;
      foot.appendChild(quiet);
    }

    /* Each term with its value in a box of its own. Without one, a rule that puts
       labels on one row and values on the next has nothing to keep a pair
       together when the row wraps. */
    var list = about && about.querySelector('.readings');
    if (list) {
      var pairs = [];
      var pair = null;
      Array.prototype.slice.call(list.children).forEach(function (child) {
        if (child.tagName === 'DT') {
          pair = document.createElement('div');
          pairs.push(pair);
        }
        if (pair) pair.appendChild(child);
      });
      pairs.forEach(function (d) { list.appendChild(d); });
      foot.appendChild(list);
    }

    if (colophon) foot.appendChild(colophon);

    if (about) about.parentNode.removeChild(about);
    wrap.appendChild(foot);
  }

  /* On a narrow screen the navigation joins the masthead's own menu instead of
     opening a second panel beside it. One button, one panel, one place to look.
     The groups move rather than being copied, so the period buttons keep the
     listeners the skin attached to them. */
  function follow() {
    var aside = document.querySelector('.deck-sidebar');
    var tools = document.getElementById('masthead-tools');
    if (!aside || !tools || !window.matchMedia) return;
    var narrow = window.matchMedia('(max-width: 60rem)');

    var place = function () {
      var groups = Array.prototype.slice.call(
        document.querySelectorAll('.deck-nav-group'));
      if (narrow.matches) {
        groups.forEach(function (g) { tools.insertBefore(g, tools.firstChild); });
        document.documentElement.classList.add('deck-nav-in-menu');
      } else {
        groups.forEach(function (g) { aside.appendChild(g); });
        document.documentElement.classList.remove('deck-nav-in-menu');
      }
    };

    place();
    if (narrow.addEventListener) narrow.addEventListener('change', place);
    else narrow.addListener(place);
  }

  /* Choosing something puts the menu away.
     The skin's own handler closes it on a tap outside the tools, and the
     navigation is outside them, so a tap on a link would close it anyway; a tap
     on a time span would not, because those redraw the page in place. */
  function closeOnChoice() {
    var aside = document.querySelector('.deck-sidebar');
    var tools = document.getElementById('masthead-tools');
    var button = document.getElementById('nav-toggle');
    if (!aside || !tools || !button) return;
    [aside, tools].forEach(function (host) {
    host.addEventListener('click', function (e) {
      if (!e.target.closest('button, a')) return;
      delete tools.dataset.open;
      button.setAttribute('aria-expanded', 'false');
    });
    });
  }

  function start() {
    buildSidebar();
    buildFooter();
    follow();
    closeOnChoice();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
