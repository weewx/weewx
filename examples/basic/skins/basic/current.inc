## basic for weewx - Copyright 2013 Matthew Wall

<!-- current readings in tabular form -->

<table class='metrics' width='100%'>
  <tr style='vertical-align:top'>
    <td class='metric_name'>Temperature</td>
    <td class='metric_large'><a href='dayouttemphilo.png' class='popup'>$current.outTemp.formatted</a></td>
    <td class='metric_value'><a href='daytempchill.png' class='popup'><span class='heatindex'>$current.heatindex.formatted</span><br/><span class='windchill'>$current.windchill.formatted</span></a></td>
    <td class='metric_value'>
      $day.outTemp.max.formatted<br/>
      $day.outTemp.min.formatted</td>
    <td class='metric_units'>$unit.label.outTemp</td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>Humidity</td>
    <td class='metric_large' colspan='2' >
      <a href='dayouthum.png' class='popup'>$current.outHumidity.formatted</a>
    </td>
    <td class='metric_value'>
      $day.outHumidity.max.formatted<br/>
      $day.outHumidity.min.formatted</td>
    <td class='metric_units'>$unit.label.outHumidity</td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>Dewpoint</td>
    <td class='metric_large' colspan='2' ><a href='dayouttempdew.png' class='popup'>$current.dewpoint.formatted</a></td>
    <td class='metric_value'>
      $day.dewpoint.max.formatted<br/>
      $day.dewpoint.min.formatted</td>
    <td class='metric_units'>$unit.label.dewpoint</td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>Barometer</td>
    <td class='metric_large' colspan='2' ><a href='daybarometer.png' class='popup'>$current.barometer.formatted</a></td>
    <td class='metric_value'>
      $day.barometer.max.formatted<br/>
      $day.barometer.min.formatted</td>
    <td class='metric_units'>$unit.label.barometer<br/>
<!-- note: these thresholds are for millibar, not inHg -->
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
    </td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>Wind</td>
    <td class='metric_large' colspan='2' >
      <table cellspacing='0' cellpadding='0'><tr>
      <td><a href='daywind.png' class='popup'>$current.windSpeed.formatted</a>
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
      <span class='metric_value' title='maximum wind speed'>$day.wind.max.formatted</span><br/>
      <span class='metric_value' title='average wind speed'>$day.wind.avg.formatted</span> avg
    </td>
    <td class='metric_units'>$unit.label.windSpeed<br/>
#if $varExists('trend')
#if $trend.windSpeed.raw is not None:
#if $trend.windSpeed.formatted > 0
      &#8679;
#elif $trend.windSpeed.formatted < 0
      &#8681;
#end if
#end if
#end if
    </td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>Precipitation</td>
    <td class='metric_large' colspan='2' >
      <span title='rainfall within the past few minutes'><a href='dayrain.png' class='popup'>$current.rain.formatted</a></span>
    </td>
    <td class='metric_value'>
      <span title='maximum rain rate this day'>$day.rainRate.max.formatted</span><br/>
      <span title='total rainfall this day'>$day.rain.sum.formatted</span>
    </td>
    <td class='metric_units'>
      $unit.label.rainRate<br/>
      $unit.label.rain
    </td>
  </tr>

#if $day.UV.has_data
  <tr style='vertical-align:top'>
    <td class='metric_name'>UV</td>
    <td class='metric_large' colspan='2' >
      <span title='UV Index'><a href='dayuv.png' class='popup'>$current.UV.formatted</a></span>
    </td>
    <td class='metric_value'>
      <span title='maximum UV this day'>$day.UV.max.formatted</span><br/>
      <span title='minimum UV this day'>$day.UV.min.formatted</span>
    </td>
    <td></td>
  </tr>
#end if

  <tr style='vertical-align:top'>
    <td class='metric_name'>Temperature<br/>Inside</td>
    <td class='metric_large' colspan='2' >
      <a href='dayintemphilo.png' class='popup'>$current.inTemp.formatted</a>
    </td>
    <td class='metric_value'>
      $day.inTemp.max.formatted<br/>
      $day.inTemp.min.formatted
    </td>
    <td class='metric_units'>$unit.label.outTemp</td>
  </tr>

  <tr style='vertical-align:top'>
    <td class='metric_name'>Humidity<br/>Inside</td>
    <td class='metric_large' colspan='2' >
      <a href='dayinhum.png' class='popup'>$current.inHumidity.formatted</a>
    </td>
    <td class='metric_value'>
      $day.inHumidity.max.formatted<br/>
      $day.inHumidity.min.formatted
    </td>
    <td class='metric_units'>$unit.label.outHumidity</td>
  </tr>
</table>
