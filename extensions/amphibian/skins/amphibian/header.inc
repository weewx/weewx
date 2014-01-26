## amphibian for weewx - Copyright 2012-2013 Matthew Wall
## $Id$

<div class='wide bordered line cell'>
  <div class='leftCell'>
$station.location ($station.latitude[0]&deg; $station.latitude[1]' $station.latitude[2] $station.longitude[0]&deg; $station.longitude[1]' $station.longitude[2] $station.altitude)
  </div>
  <div class='rightCell'>
$current.dateTime
  </div>
</div>

<div style='width: 100%'>
  <div class='bordered header' style='clear: both'>
    <div class='headerContent'>
      <span class='bigger'><span class='value'>$current.outTemp.formatted</span>&deg;</span> $unit.label.outTemp<br/>
      Humidity <span class='value'>$current.outHumidity.formatted</span> $unit.label.outHumidity<br/>
      Pressure <span class='value'>$current.barometer.formatted</span> $unit.label.barometer<br/>
    </div>
    <div class='leftCell leftpad rightAlign'>
      <span class='value'>$current.inTemp.formatted</span>$unit.label.outTemp<br/>
      <span class='value'>$current.inHumidity.formatted</span>$unit.label.outHumidity<br/>
      <span class='bigger'>
#if $varExists('trend')
#if $trend.barometer.raw is not None:
#if $trend.barometer.raw > 6
      &#8679;&#8679;&#8679;
#elif $trend.barometer.raw > 3
      &#8679;&#8679;
#elif $trend.barometer.raw > 0.5
      &#8679;
#elif $trend.barometer.raw < -6
      &#8681;&#8681;&#8681;
#elif $trend.barometer.raw < -3
      &#8681;&#8681;
#elif $trend.barometer.raw < 0.5
      &#8681;
#end if
#end if
#end if
      </span><br/>
    </div>
  </div>
  <div class='bordered headerNoPad'>
    <div class='leftCell'>rose</div>
    <div class='leftCell smallpad'>
      Wind <span class='value'>$current.windSpeed.formatted</span> $unit.label.windSpeed<br/>
      Gust <span class='value'>$current.windGust.formatted</span> $unit.label.windSpeed<br/>
      Rain <span class='value'>$current.rainRate.formatted</span> $unit.label.rainRate<br/>
    </div>
  </div>
  <div class='bordered headerNoPad'>
    <div class='leftCell smallpad'>
#if $almanac.hasExtras
      Sunrise <span class='value'>$almanac.sun.rise</span><br/>
      Sunset <span class='value'>$almanac.sun.set</span><br/>
      Moonrise <span class='value'>$almanac.moon.rise</span><br/>
      Moonset <span class='value'>$almanac.moon.set</span><br/>
#else
      Sunrise <span class='value'>$almanac.sunrise</span><br/>
      Sunset <span class='value'>$almanac.sunset</span><br/>
#end if
      Phase <span class='value'>$almanac.moon_phase $almanac.moon_fullness% full</span><br/>
    </div>
  </div>
</div>


<div class='tabPane'>
  <div class='leftCell' style='width:10px'>&nbsp;</div>
  <div id='hour' class='tab'><a id='hour-link' href='.'>Hour</a></div>
  <div id='day' class='tab'><a id='day-link' href='.'>Day</a></div>
  <div id='week' class='tab'><a id='week-link' href='.'>Week</a></div>
  <div id='month' class='tab'><a id='month-link' href='.'>Month</a></div>
  <div id='year' class='tab'><a id='year-link' href='.'>Year</a></div>
  <div id='almanac' class='tab'><a href='almanac.html'>Almanac</a></div>
  <div style='float:right; width:10px;'>&nbsp;</div>
  <div id='button-tables' class='rightTab'><a id='button-tables-link' href='.'>Tables</a></div>
  <div id='button-charts' class='rightTab'><a id='button-charts-link' href='.'>Charts</a></div>
</div>
