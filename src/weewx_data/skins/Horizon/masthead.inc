## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The masthead holds the heading and the time of the latest archive record. At the
## right are the year picker (climate.html only), the theme toggle and the menu
## button.
##
## On a page that sets '$page_title', the title is the heading, and the line under it
## starts with a link to the front page. The front page sets no '$page_title', so its
## heading is the station's location.
#set $title = $getVar('page_title', '')
## A climate year page shows no time of update (see climate-%Y.html.tmpl).
#set $archived = $page == 'climate_year'
      <header class="masthead">
        <div class="masthead-title">
          <h1>#if $title then $title else $station.location#</h1>
          <p class="updated">
#if $title and not $archived
            <a href="index.html">&larr; $station.location</a> &middot;
#elif $title
            <a href="index.html">&larr; $station.location</a>
#end if
#if not $archived
            <span class="visually-hidden">$gettext("Last update")</span>
            <span data-live="dateTime" data-raw="$current.dateTime.raw">$current.dateTime</span>
#end if
          </p>
        </div>
        <div class="masthead-tools">
#if $page == 'climate'
## The year picker lists every year from the first archive record to the latest one.
## WeeWX writes a climate year page for each year in that range, with or without
## data.
##
## Only climate.html has the picker. climate.html is written on every report cycle,
## so its list always includes the newest year. A list on a climate year page would
## end at the year in which WeeWX last wrote that page.
  #set $climate_years = []
  #for $y in range($int($alltime.start.format("%Y")), $int($latest.dateTime.format("%Y")) + 1)
    #silent $climate_years.append($str($y))
  #end for
  #if $climate_year not in $climate_years
    #silent $climate_years.append($climate_year)
  #end if
  #if len($climate_years) > 1
## autocomplete="off" keeps the browser from restoring the reader's last choice when
## the reader comes back with the Back button. The picker would then name another
## year than the page on screen, and choosing that year again would fire no
## 'change'.
          <label class="visually-hidden" for="climate-year">$gettext("Year")</label>
          <select id="climate-year" class="select" autocomplete="off"
                  onchange="if (this.value) window.location = this.value;">
    #for $y in reversed($climate_years)
      #if $y == $climate_year
            <option value="climate.html" selected>$y</option>
      #else
            <option value="climate-${y}.html">$y</option>
      #end if
    #end for
          </select>
  #end if
#end if
## The theme toggle sits in the masthead, so that it stays reachable on a narrow
## screen with the menu closed.
          <button type="button" id="theme-toggle" class="icon-button"
                  aria-label="$gettext('Switch theme')">
            <svg class="glyph-light" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.5 1.5m11.2 11.2l1.5 1.5M19.1 4.9l-1.5 1.5M6.4 17.6l-1.5 1.5"/></svg>
            <svg class="glyph-dark" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z"/></svg>
          </button>
## horizon.css shows the menu button only on a narrow screen and only where scripts
## run. The button opens the navigation over the page.
          <button type="button" id="nav-toggle" class="icon-button nav-toggle"
                  aria-expanded="false" aria-controls="site-nav"
                  aria-label="$gettext('Menu')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
          </button>
        </div>
      </header>
