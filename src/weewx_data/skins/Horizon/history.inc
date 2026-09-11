## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The history panel: the charts, and the range bar that moves them back and forth in
## time. horizon.js draws the charts into '#charts' from the JSON files. A page has at
## most one history panel, because horizon.js finds the range bar's controls by id.
#set $periods = $to_list($DisplayOptions.get('periods', ['day', 'week', 'month', 'year']))
<section class="panel wide history">
  <div class="panel-head history-head">
    <h2>$gettext("History")</h2>
## On the front page the time span links are in the navigation. The navigation's
## links always open the front page's charts, so any other page with a history panel
## (i.e., telemetry) has its own links here, in the panel head.
#if $page != 'index'
    <div class="tabs" role="group" aria-label="$gettext('Time span')">
  #for $period in $periods
    #set $href = '#' + $period
      <a href="$href" data-period="$period">$gettext($period.capitalize())</a>
  #end for
    </div>
#end if
    <div class="range-bar">
      <div class="range-nav">
        <button type="button" id="range-back" class="range-button"
                aria-label="$gettext('Earlier')">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>
        </button>
        <div class="range-label-wrap">
          <button type="button" id="range-label" class="range-label"
                  aria-haspopup="dialog" aria-expanded="false"
                  title="$gettext('Jump to a date')">$gettext("Now")</button>
          <div id="range-cal" class="range-cal" role="dialog" hidden
               aria-label="$gettext('Jump to a date')"></div>
        </div>
        <button type="button" id="range-fwd" class="range-button"
                aria-label="$gettext('Later')" disabled>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>
        </button>
      </div>
      <div class="range-extra">
        <button type="button" id="range-now" class="range-now" hidden>$gettext("Now")</button>
        <button type="button" id="range-share" class="range-now"
                title="$gettext('Link to this view')">$gettext("Share")</button>
      </div>
    </div>
  </div>
  <div class="panel-body flush">
    <div id="charts" class="charts" tabindex="-1" aria-live="polite" aria-busy="true">
      <p class="chart-empty">$gettext("Loading charts")&hellip;</p>
    </div>
## The notice mentions the statistics below the charts, i.e., the 'hilo' panel, which
## only the front page has.
#if $page == 'index'
    <noscript>
      <p class="chart-empty">$gettext("Charts need JavaScript. The statistics below work without it.")</p>
    </noscript>
#end if
  </div>
</section>
