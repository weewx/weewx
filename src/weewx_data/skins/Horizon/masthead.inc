## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The masthead, and with it the way to every other page. One file rather than one
## copy per template: a menu that differs from page to page is a menu the reader has
## to read again on each of them.
##
## What a page sets before including this. All of it optional, and all of it with
## '#set global', because an include is compiled on its own and a plain '#set' does
## not reach it:
##
##   $page_root   the way back to the directory the report was written to, for a page
##                that sits in a subdirectory of it. Defaults to '.'.
##   $page_title  the heading. Without one the station's location is the heading and
##                there is no way back to it, which is what the front page wants.
##   $page_units  False on a page that holds nothing the unit picker could convert.
##
## Which page this is. $page is WeeWX's own: the section name in skin.conf where
## the template is listed. That is the page's identity already, so nothing here
## has to repeat it. The years of the climate archive are listed under their own
## section and count as the climate page.
#set $here = $getVar('page', '')
#if $here == 'climate_year'
#set $here = 'climate'
#end if
#set $root = $getVar('page_root', '.')
#set $prefix = '' if $root in ('.', '') else $root + '/'
#set $title = $getVar('page_title', '')
#set $show_units = $to_bool($getVar('page_units', True))
##
## Every page the skin writes, in the order the menu shows them. Three are optional,
## and a station that has switched one off should not be offered a link to a page
## that was never written.
#set $nav = []
#if $to_bool($DisplayOptions.get('show_climate', True))
#silent $nav.append({'page': 'climate', 'href': 'climate.html', 'label': $gettext("Climate")})
#end if
#silent $nav.append({'page': 'statistics', 'href': 'statistics.html', 'label': $gettext("Statistics")})
#silent $nav.append({'page': 'celestial', 'href': 'celestial.html', 'label': $gettext("Celestial")})
#if $to_bool($DisplayOptions.get('show_reports', True))
#silent $nav.append({'page': 'reports', 'href': 'reports.html', 'label': $gettext("Reports")})
#end if
#silent $nav.append({'page': 'telemetry', 'href': 'telemetry.html', 'label': $gettext("Telemetry")})
#if $to_bool($DisplayOptions.get('show_rss', True))
#silent $nav.append({'page': 'rss', 'href': 'rss.xml', 'label': $gettext("RSS")})
#end if
##
      <header class="masthead">
        <div>
#if $title
          <h1>$title</h1>
          <p class="updated"><a href="${prefix}index.html">&larr; $station.location</a> &middot;
            <span class="visually-hidden">$gettext("Last update")</span>
            <span data-live="dateTime" data-raw="$current.dateTime.raw">$current.dateTime</span></p>
#else
          <h1>$station.location</h1>
          <p class="updated">
            <span class="visually-hidden">$gettext("Last update")</span>
            <span data-live="dateTime" data-raw="$current.dateTime.raw">$current.dateTime</span>
          </p>
#end if
        </div>

## The theme switch stays outside the menu, because it is the one control a reader
## reaches for without wanting anything else. On a phone it sits beside the menu
## button rather than inside it.
          <button type="button" id="theme-toggle" class="icon-button theme-toggle"
                  aria-label="$gettext('Switch theme')">
            <svg class="glyph-light" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.5 1.5m11.2 11.2l1.5 1.5M19.1 4.9l-1.5 1.5M6.4 17.6l-1.5 1.5"/></svg>
            <svg class="glyph-dark" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z"/></svg>
          </button>
## On a phone the controls below do not fit across the page, and a masthead that
## reaches past the edge is a page that scrolls sideways. The button folds them into
## a menu; the stylesheet shows it only where they would not fit.
          <button type="button" id="nav-toggle" class="icon-button nav-toggle"
                  aria-expanded="false" aria-controls="masthead-tools"
                  aria-label="$gettext('Menu')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
          </button>
        <div class="masthead-tools" id="masthead-tools">
#if $show_units
## Which unit the readings are shown in. Filled by the script, and hidden where the
## station has nothing to offer besides the unit the report was rendered in.
          <label class="visually-hidden" for="unit-picker">$gettext("Units")</label>
          <select id="unit-picker" class="unit-select" hidden></select>
#end if
#set $languages = $DisplayOptions.get('Languages', {})
#if len($languages) > 1
## Paths in [[Languages]] are relative to the station's top directory. 'lang_root' is
## the way from this rendering back up to it, and $prefix the way out of a
## subdirectory, so a page in one and a page at the top both link correctly.
  #set $lang_root = $DisplayOptions.get('lang_root', '.')
          <label class="visually-hidden" for="lang-picker">$gettext("Language")</label>
          <select id="lang-picker" class="lang-select"
                  onchange="if(this.value) window.location = this.value;">
  #for $code in $languages
    #set $entry = $languages[$code]
    #set $path = $entry.get('path', $code)
    #set $parts = [$p for $p in [$root, $lang_root, $path] if $p not in ('.', '')]
    #set $target = '/'.join($parts + ['index.html'])
            <option value="$target"#if $code == $lang or $lang.startswith($code + '_') then ' selected' else ''#>$entry.get('label', $code)</option>
  #end for
          </select>
#end if
#if $here == 'climate'
## Each year is its own page, written once when the year ended. The picker fetches
## the one that is wanted and puts its panels in place of these, rather than loading
## it: a year is about six kilobytes over the wire, and holding all of them in every
## page would be a quarter of a megabyte on a station with a long record.
## First year of the record to last, which is exactly the set of pages the generator
## writes: it runs a year template over every span between the two, whether or not
## the year holds anything.
##
## Not $SummaryByYear, which holds the years this run has written so far. A page for
## 2009 sees 2009 and nothing after it, so every year but the last was left without a
## picker. Not $alltime.years either: it ends at the report time, and on a page for a
## year that has ended, that is the end of the year.
  #set $climate_years = []
  #for $y in range($int($alltime.start.format("%Y")), $int($latest.dateTime.format("%Y")) + 1)
    #silent $climate_years.append($str($y))
  #end for
  #if $climate_year not in $climate_years
    #silent $climate_years.append($climate_year)
  #end if
  #if len($climate_years) > 1
## The value is the page to fetch. A reader without JavaScript still gets a working
## control, because the script only takes over if it is there.
          <label class="visually-hidden" for="climate-year">$gettext("Year")</label>
          <select id="climate-year" class="lang-select">
    #for $y in reversed($climate_years)
      #if $y == $current.dateTime.format("%Y")
            <option value="${prefix}climate.html"#if $y == $climate_year then ' selected' else ''#>$y</option>
      #else
            <option value="${prefix}climate/climate-${y}.html"#if $y == $climate_year then ' selected' else ''#>$y</option>
      #end if
    #end for
          </select>
          <noscript>
            <a class="masthead-link" href="${prefix}climate.html">$gettext("Year")</a>
          </noscript>
  #end if
#end if
#for $item in $nav
  #set $mark = ' aria-current="page"' if $item['page'] == $here else ''
          <a class="masthead-link" href="${prefix}$item['href']"$mark>$item['label']</a>
#end for
        </div>
      </header>
