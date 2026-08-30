## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The charts, and the controls that pick which span they show. Empty in the page
## as rendered: horizon.js fills '#charts' from the JSON files, so the span the
## reader lands on is the one the browser remembers rather than one baked in here.
##
## Only one of these belongs on a page. The tab strip and the range bar address
## their controls by id, and horizon.js looks each of them up once.

#set $periods = $to_list($DisplayOptions.get('periods', ['day', 'week', 'month', 'year']))

<section class="panel">
  <div class="panel-head">
    <h2>$gettext("History")</h2>
    <div class="tabs" id="period-tabs" role="tablist" aria-label="$gettext('Time span')">
#for $period in $periods
      <button type="button" role="tab" data-period="$period"
              aria-selected="#if $period == $periods[0] then 'true' else 'false'#"
              aria-controls="charts">$gettext($period.capitalize())</button>
#end for
    </div>
  </div>
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

  <div class="panel-body flush">
    <div id="charts" class="charts" role="tabpanel" tabindex="-1"
         aria-live="polite" aria-busy="true">
      <p class="chart-empty">$gettext("Loading charts")&hellip;</p>
    </div>
    <noscript>
      <p class="chart-empty">$gettext("Charts need JavaScript. The statistics below work without it.")</p>
    </noscript>
  </div>
</section>
