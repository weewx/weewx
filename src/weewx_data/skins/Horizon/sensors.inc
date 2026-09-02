## sensors module for weewx skins
## Copyright Tom Keffer, Matthew Wall
## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8

#set $connections = $to_list($DisplayOptions.get('sensor_connections', []))
#set $batteries = $to_list($DisplayOptions.get('sensor_batteries', []))
#set $voltages = $to_list($DisplayOptions.get('sensor_voltages', []))

## Only build the panel if at least one of these fields actually carries data.
#set $any_sensor = False
#for $x in $connections + $batteries + $voltages
  #if $getVar('day.%s.has_data' % $x, False)
    #set $any_sensor = True
    #break
  #end if
#end for

#if $any_sensor
<section class="panel" data-live-panel="sensors">
  <div class="panel-head">
    <h2>$gettext("Sensor Status")</h2>
  </div>
  <div class="panel-body">
    <dl class="readings">
  #for $x in $connections
    #if $getVar('day.%s.has_data' % $x, False)
      <dt>$obs.label[$x]</dt>
      <dd>$getVar('current.' + $x)</dd>
    #end if
  #end for
  #for $x in $batteries
    #if $getVar('day.%s.has_data' % $x, False)
      <dt>$obs.label[$x]</dt>
      <dd>
      #set $v = $getVar('current.%s.raw' % $x)
      #if $v is None
        <span class="status-dot status-unknown"></span>$gettext("UNKNOWN")
      #elif $v
        <span class="status-dot status-low"></span>$gettext("LOW")
      #else
        <span class="status-dot status-ok"></span>$gettext("OK")
      #end if
      </dd>
    #end if
  #end for
  #for $x in $voltages
    #if $getVar('day.%s.has_data' % $x, False)
      <dt>$obs.label[$x]</dt>
      <dd>$getVar('current.' + $x)</dd>
    #end if
  #end for
    </dl>
  </div>
</section>
#end if
