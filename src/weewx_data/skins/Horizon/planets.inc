## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The planets panel: for each body in 'planets', its altitude now and its rise and
## set times. Any body that pyephem knows can be named. A planet below the horizon
## keeps its row. 'data-up' is 1 for a planet above the horizon and 0 for one below.
#if $almanac.hasExtras
  #set $bodies = $to_list($DisplayOptions.get('planets',
                          ['mercury', 'venus', 'mars', 'jupiter', 'saturn']))
<section class="panel" data-live-panel="planets">
  <div class="panel-head">
    <h2><a href="celestial.html">$gettext("Planets")</a></h2>
  </div>
  <div class="panel-body flush">

    <table class="planets">
      <thead>
        <tr>
          <th scope="col">$gettext("Planet")</th>
          <th scope="col" class="num">$pgettext("Astronomical", "Altitude")</th>
          <th scope="col" class="num">$gettext("Rises")</th>
          <th scope="col" class="num">$gettext("Sets")</th>
        </tr>
      </thead>
      <tbody>
  #for $body in $bodies
    #set $b = $getVar('almanac.%s' % $body, None)
    #if $b is not None
      #set $up = $b.alt > 0 and '1' or '0'
      #set $label = $gettext($body.capitalize())
      #set $alt = '%.0f' % $b.alt
        <tr>
          <th scope="row"><span class="planet-mark" data-up="$up" aria-hidden="true"></span>$label</th>
          <td class="num">$alt&deg;</td>
          <td class="num">$b.rise</td>
          <td class="num">$b.set</td>
        </tr>
    #end if
  #end for
      </tbody>
    </table>

  </div>
</section>
#end if
