## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The head of a climate page, shared by the year in progress and by the years that
## have ended. Those two sit in different directories, so every link here goes through
## $climate_root, which each template sets to the way back to the top.
##
## The year picker is a list of links rather than a control that fetches: each year is
## its own page, written once when the year ended.
#set $climate_years = []
#for $y in $SummaryByYear
#silent $climate_years.append($str($y))
#end for
#if $climate_year not in $climate_years
#silent $climate_years.append($climate_year)
#end if
##
      <header class="masthead">
        <div>
          <h1>$gettext("Climate") $climate_year</h1>
          <p class="updated"><a href="$climate_root/index.html">&larr; $station.location</a> &middot;
            <span class="visually-hidden">$gettext("Last update")</span>
            <span data-live="dateTime" data-raw="$current.dateTime.raw">$current.dateTime</span></p>
        </div>

        <div class="masthead-tools">
## The same control the front page carries, so a reader who set a unit there finds
## the same numbers here. Filled by the script, and hidden where there is nothing to
## choose between.
          <label class="visually-hidden" for="unit-picker">$gettext("Units")</label>
          <select id="unit-picker" class="unit-select" hidden></select>
#if len($climate_years) > 1
## Each year is its own page, written once when the year ended. The picker fetches
## the one that is wanted and puts its panels in place of these, rather than loading
## it: a year is about six kilobytes over the wire, and holding all of them in every
## page would be a quarter of a megabyte on a station with a long record.
##
## The value is the page to fetch. A reader without JavaScript still gets a working
## control, because the script only takes over if it is there.
          <label class="visually-hidden" for="climate-year">$gettext("Year")</label>
          <select id="climate-year" class="lang-select">
#for $y in reversed($climate_years)
#if $y == $current.dateTime.format("%Y")
            <option value="$climate_root/climate.html"#if $y == $climate_year then ' selected' else ''#>$y</option>
#else
            <option value="$climate_root/climate/climate-${y}.html"#if $y == $climate_year then ' selected' else ''#>$y</option>
#end if
#end for
          </select>
          <noscript>
            <a class="masthead-link" href="$climate_root/climate.html">$gettext("Year")</a>
          </noscript>
#end if
          <a class="masthead-link" href="$climate_root/statistics.html">$gettext("Statistics")</a>
          <a class="masthead-link" href="$climate_root/reports.html">$gettext("Reports")</a>
          <button type="button" id="theme-toggle" class="icon-button" aria-label="$gettext('Switch theme')">
            <svg class="glyph-light" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.5 1.5m11.2 11.2l1.5 1.5M19.1 4.9l-1.5 1.5M6.4 17.6l-1.5 1.5"/></svg>
            <svg class="glyph-dark" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z"/></svg>
          </button>
        </div>
      </header>
