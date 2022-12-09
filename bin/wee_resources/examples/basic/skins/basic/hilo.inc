## basic for weewx - Copyright 2013 Matthew Wall

<!-- hi/lo readings in tabular form -->

<table class='metrics'>
  <tr>
    <td></td>
    <td class="metric_title">$gettext["Today"]</td>
    <td class="metric_title">$gettext["Month"]</td>
    <td class="metric_title">$gettext["Year"]</td>
    <td></td>
  </tr>

  <!-- outside -->

  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Temperature"]:</td>
    <td><span class="metric_value">$day.outTemp.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.outTemp.maxtime</span></td>
    <td><span class="metric_value">$month.outTemp.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.outTemp.maxtime</span></td>
    <td><span class="metric_value">$year.outTemp.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.outTemp.maxtime</span></td>
    <td class="metric_units">$unit.label.outTemp</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Minimum Temperature"]:</td>
    <td><span class="metric_value">$day.outTemp.min.format(add_label=False)</span><br>
      <span class="hilo_time">$day.outTemp.mintime</span></td>
    <td><span class="metric_value">$month.outTemp.min.format(add_label=False)</span><br>
      <span class="hilo_time">$month.outTemp.mintime</span></td>
    <td><span class="metric_value">$year.outTemp.min.format(add_label=False)</span><br>
      <span class="hilo_time">$year.outTemp.mintime</span></td>
    <td class="metric_units">$unit.label.outTemp</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Humidity"]:</td>
    <td><span class="metric_value">$day.outHumidity.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.outHumidity.maxtime</span></td>
    <td><span class="metric_value">$month.outHumidity.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.outHumidity.maxtime</span></td>
    <td><span class="metric_value">$year.outHumidity.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.outHumidity.maxtime</span></td>
    <td class="metric_units">$unit.label.outHumidity</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Minimum Humidity"]:</td>
    <td><span class="metric_value">$day.outHumidity.min.format(add_label=False)</span><br>
      <span class="hilo_time">$day.outHumidity.mintime</span></td>
    <td><span class="metric_value">$month.outHumidity.min.format(add_label=False)</span><br>
      <span class="hilo_time">$month.outHumidity.mintime</span></td>
    <td><span class="metric_value">$year.outHumidity.min.format(add_label=False)</span><br>
      <span class="hilo_time">$year.outHumidity.mintime</span></td>
    <td class="metric_units">$unit.label.outHumidity</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Dewpoint"]:</td>
    <td><span class="metric_value">$day.dewpoint.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.dewpoint.maxtime</span></td>
    <td><span class="metric_value">$month.dewpoint.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.dewpoint.maxtime</span></td>
    <td><span class="metric_value">$year.dewpoint.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.dewpoint.maxtime</span></td>
    <td class="metric_units">$unit.label.dewpoint</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Minimum Dewpoint"]:</td>
    <td><span class="metric_value">$day.dewpoint.min.format(add_label=False)</span><br>
      <span class="hilo_time">$day.dewpoint.mintime</span></td>
    <td><span class="metric_value">$month.dewpoint.min.format(add_label=False)</span><br>
      <span class="hilo_time">$month.dewpoint.mintime</span></td>
    <td><span class="metric_value">$year.dewpoint.min.format(add_label=False)</span><br>
      <span class="hilo_time">$year.dewpoint.mintime</span></td>
    <td class="metric_units">$unit.label.dewpoint</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Barometer"]:</td>
    <td><span class="metric_value">$day.barometer.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.barometer.maxtime</span></td>
    <td><span class="metric_value">$month.barometer.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.barometer.maxtime</span></td>
    <td><span class="metric_value">$year.barometer.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.barometer.maxtime</span></td>
    <td class="metric_units">$unit.label.barometer</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Minimum Barometer"]:</td>
    <td><span class="metric_value">$day.barometer.min.format(add_label=False)</span><br>
      <span class="hilo_time">$day.barometer.mintime</span></td>
    <td><span class="metric_value">$month.barometer.min.format(add_label=False)</span><br>
      <span class="hilo_time">$month.barometer.mintime</span></td>
    <td><span class="metric_value">$year.barometer.min.format(add_label=False)</span><br>
      <span class="hilo_time">$year.barometer.mintime</span></td>
    <td class="metric_units">$unit.label.barometer</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Heat Index"]:</td>
    <td><span class="metric_value">$day.heatindex.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.heatindex.maxtime</span></td>
    <td><span class="metric_value">$month.heatindex.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.heatindex.maxtime</span></td>
    <td><span class="metric_value">$year.heatindex.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.heatindex.maxtime</span></td>
    <td class="metric_units">$unit.label.heatindex</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Minimum Wind Chill"]:</td>
    <td><span class="metric_value">$day.windchill.min.format(add_label=False)</span><br>
      <span class="hilo_time">$day.windchill.mintime</span></td>
    <td><span class="metric_value">$month.windchill.min.format(add_label=False)</span><br>
      <span class="hilo_time">$month.windchill.mintime</span></td>
    <td><span class="metric_value">$year.windchill.min.format(add_label=False)</span><br>
      <span class="hilo_time">$year.windchill.mintime</span></td>
    <td class="metric_units">$unit.label.windchill</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Wind Speed"]:</td>
    <td><span class="metric_value">$day.wind.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.wind.maxtime</span></td>
    <td><span class="metric_value">$month.wind.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.wind.maxtime</span></td>
    <td><span class="metric_value">$year.wind.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.wind.maxtime</span></td>
    <td class="metric_units">$unit.label.wind</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Average Wind Speed"]:</td>
    <td><span class="metric_value">$day.wind.avg.format(add_label=False)</span></td>
    <td><span class="metric_value">$month.wind.avg.format(add_label=False)</span></td>
    <td><span class="metric_value">$year.wind.avg.format(add_label=False)</span></td>
    <td class="metric_units">$unit.label.wind</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Rain Rate"]:</td>
    <td><span class="metric_value">$day.rainRate.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.rainRate.maxtime</span></td>
    <td><span class="metric_value">$month.rainRate.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.rainRate.maxtime</span></td>
    <td><span class="metric_value">$year.rainRate.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.rainRate.maxtime</span></td>
    <td class="metric_units">$unit.label.rainRate</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Rain Total"]:</td>
    <td><span class="metric_value">$day.rain.sum.format(add_label=False)</span><br></td>
    <td><span class="metric_value">$month.rain.sum.format(add_label=False)</span></td>
    <td><span class="metric_value">$year.rain.sum.format(add_label=False)</span></td>
    <td class="metric_units">$unit.label.rain</td>
  </tr>

  <!-- inside -->

  <tr><td>&nbsp;</td></tr>
  <tr><td colspan='4' class='metric_name'>$gettext["Inside"]</td></tr>

  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Temperature"]:</td>
    <td><span class="metric_value">$day.inTemp.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.inTemp.maxtime</span></td>
    <td><span class="metric_value">$month.inTemp.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.inTemp.maxtime</span></td>
    <td><span class="metric_value">$year.inTemp.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.inTemp.maxtime</span></td>
    <td class="metric_units">$unit.label.inTemp</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Minimum Temperature"]:</td>
    <td><span class="metric_value">$day.inTemp.min.format(add_label=False)</span><br>
      <span class="hilo_time">$day.inTemp.mintime</span></td>
    <td><span class="metric_value">$month.inTemp.min.format(add_label=False)</span><br>
      <span class="hilo_time">$month.inTemp.mintime</span></td>
    <td><span class="metric_value">$year.inTemp.min.format(add_label=False)</span><br>
      <span class="hilo_time">$year.inTemp.mintime</span></td>
    <td class="metric_units">$unit.label.inTemp</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Maximum Humidity"]:</td>
    <td><span class="metric_value">$day.inHumidity.max.format(add_label=False)</span><br>
      <span class="hilo_time">$day.inHumidity.maxtime</span></td>
    <td><span class="metric_value">$month.inHumidity.max.format(add_label=False)</span><br>
      <span class="hilo_time">$month.inHumidity.maxtime</span></td>
    <td><span class="metric_value">$year.inHumidity.max.format(add_label=False)</span><br>
      <span class="hilo_time">$year.inHumidity.maxtime</span></td>
    <td class="metric_units">$unit.label.inHumidity</td>
  </tr>
  <tr style='vertical-align:top'>
    <td class="metric_name">$gettext["Minimum Humidity"]:</td>
    <td><span class="metric_value">$day.inHumidity.min.format(add_label=False)</span><br>
      <span class="hilo_time">$day.inHumidity.mintime</span></td>
    <td><span class="metric_value">$month.inHumidity.min.format(add_label=False)</span><br>
      <span class="hilo_time">$month.inHumidity.mintime</span></td>
    <td><span class="metric_value">$year.inHumidity.min.format(add_label=False)</span><br>
      <span class="hilo_time">$year.inHumidity.mintime</span></td>
    <td class="metric_units">$unit.label.inHumidity</td>
  </tr>

</table>
