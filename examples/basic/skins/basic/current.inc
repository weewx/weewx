## basic for weewx - Copyright 2013 Matthew Wall

<!-- current readings in tabular form -->

<table class='metrics' width='100%'>
  <tr style='vertical-align:top'>
    <td class='metric_name'>$obs.label.outTemp</td>
    <td class='metric_large'><a href='dayouttemphilo.png' class='popup'>$current.outTemp.format(add_label=False)</a></td>
    <td class='metric_value'><a href='daytempchill.png' class='popup'><span class='heatindex'>$current.heatindex.format(add_label=False)</span><br/><span class='windchill'>$current.windchill.format(add_label=False)</span></a></td>
    <td class='metric_value'>
      $day.outTemp.max.format(add_label=False)<br/>
      $day.outTemp.min.format(add_label=False)</td>
    <td class='metric_units'>$unit.label.outTemp</td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>$obs.label.outHumidity</td>
    <td class='metric_large' colspan='2' >
      <a href='dayouthum.png' class='popup'>$current.outHumidity.format(add_label=False)</a>
    </td>
    <td class='metric_value'>
      $day.outHumidity.max.format(add_label=False)<br/>
      $day.outHumidity.min.format(add_label=False)</td>
    <td class='metric_units'>$unit.label.outHumidity</td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>$obs.label.dewpoint</td>
    <td class='metric_large' colspan='2' ><a href='dayouttempdew.png' class='popup'>$current.dewpoint.format(add_label=False)</a></td>
    <td class='metric_value'>
      $day.dewpoint.max.format(add_label=False)<br/>
      $day.dewpoint.min.format(add_label=False)</td>
    <td class='metric_units'>$unit.label.dewpoint</td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>$obs.label.barometer</td>
    <td class='metric_large' colspan='2' ><a href='daybarometer.png' class='popup'>$current.barometer.format(add_label=False)</a></td>
    <td class='metric_value'>
      $day.barometer.max.format(add_label=False)<br/>
      $day.barometer.min.format(add_label=False)</td>
    <td class='metric_units'>$unit.label.barometer<br/>
#if $varExists('trend')
    #set $mbar_trend = $trend.barometer.mbar.raw
    #if $mbar_trend is not None:
        ## Note: these thresholds are for millibar, not inHg
        #if $mbar_trend > 6
              &#8679;&#8679;&#8679;
        #elif $mbar_trend > 3
              &#8679;&#8679;
        #elif $mbar_trend > 0.5
              &#8679;
        #elif $mbar_trend < -6
              &#8681;&#8681;&#8681;
        #elif $mbar_trend < -3
              &#8681;&#8681;
        #elif $mbar_trend < 0.5
              &#8681;
        #end if
    #end if
#end if
    </td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>$obs.label.wind</td>
    <td class='metric_large' colspan='2' >
      <table cellspacing='0' cellpadding='0'><tr>
      <td><a href='daywind.png' class='popup'>$current.windSpeed.format(add_label=False)</a>
      </td>
      <td style='font-size:50%;padding-left:8px;'>
      <a href='daywinddir.png' class='popup'>$current.windDir.ordinal_compass<br/><span style='font-size:90%'>$current.windDir</span></a>
      </td>
      <td style='padding-left:8px;'>
      <a href='daywindvec.png' class='popup'>
#if $current.windDir.raw is None:
      -
#else
    #if $current.windDir.raw < 22.5
          &#8593;
    #elif $current.windDir.raw < 67.5
          &#8599;
    #elif $current.windDir.raw < 112.5
          &#8594;
    #elif $current.windDir.raw < 157.5
          &#8600;
    #elif $current.windDir.raw < 202.5
          &#8595;
    #elif $current.windDir.raw < 247.5
          &#8601;
    #elif $current.windDir.raw < 292.5
          &#8592;
    #elif $current.windDir.raw < 337.5
          &#8598;
    #else
          &#8593;
    #end if
#end if
      </a>
      </td>
      </tr></table>
    </td>
    <td>
      <span class='metric_value' title='maximum wind speed'>$day.wind.max.format(add_label=False)</span><br/>
      <span class='metric_value' title='average wind speed'>$day.wind.avg.format(add_label=False)</span> avg
    </td>
    <td class='metric_units'>$unit.label.windSpeed<br/>
#if $varExists('trend')
    #if $trend.windSpeed.raw is not None:
        #if $trend.windSpeed.raw > 0
              &#8679;
        #elif $trend.windSpeed.raw < 0
              &#8681;
        #end if
    #end if
#end if
    </td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>$gettext["Precipitation"]</td>
    <td class='metric_large' colspan='2' >
      <span title=$gettext['rainfall within the past few minutes']><a href='dayrain.png' class='popup'>$current.rain.format(add_label=False)</a></span>
    </td>
    <td class='metric_value'>
      <span title=$gettext['maximum rain rate this day']>$day.rainRate.max.format(add_label=False)</span><br/>
      <span title=$gettext['total rainfall this day']>$day.rain.sum.format(add_label=False)</span>
    </td>
    <td class='metric_units'>
      $unit.label.rainRate<br/>
      $unit.label.rain
    </td>
  </tr>

#if $day.UV.has_data
  <tr style='vertical-align:top'>
    <td class='metric_name'>$obs.label.UV</td>
    <td class='metric_large' colspan='2' >
      <span title=$gettext['UV Index']><a href='dayuv.png' class='popup'>$current.UV.format(add_label=False)</a></span>
    </td>
    <td class='metric_value'>
      <span title=$gettext['maximum UV this day']>$day.UV.max.format(add_label=False)</span><br/>
      <span title=$gettext['minimum UV this day']>$day.UV.min.format(add_label=False)</span>
    </td>
    <td></td>
  </tr>
#end if

  <tr style='vertical-align:top'>
    <td class='metric_name'>$obs.label.outTemp<br/>$gettext["Inside"]</td>
    <td class='metric_large' colspan='2' >
      <a href='dayintemphilo.png' class='popup'>$current.inTemp.format(add_label=False)</a>
    </td>
    <td class='metric_value'>
      $day.inTemp.max.format(add_label=False)<br/>
      $day.inTemp.min.format(add_label=False)
    </td>
    <td class='metric_units'>$unit.label.outTemp</td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>$obs.label.outHumidity<br/>$gettext["Inside"]</td>
    <td class='metric_large' colspan='2' >
      <a href='dayinhum.png' class='popup'>$current.inHumidity.format(add_label=False)</a>
    </td>
    <td class='metric_value'>
      $day.inHumidity.max.format(add_label=False)<br/>
      $day.inHumidity.min.format(add_label=False)
    </td>
    <td class='metric_units'>$unit.label.outHumidity</td>
  </tr>
</table>
