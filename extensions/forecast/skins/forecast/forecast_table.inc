## forecast display for weewx - Copyright 2012-2013 Matthew Wall
## $Id$
## Include this file to display forecast data.  This file uses icons from the
## forecast icon set.

## version = 0.1

#if $varExists('forecast')

## Which forecast should be displayed?  options are WU or NWS
#set $forecast_source = 'WU'

## How many forecast periods should be considered?
#set $num_periods = 40

## Which columns should be displayed?
#set $show_legend = 1
#set $show_hourly = 0
#set $show_date = 1
#set $show_outlook = 1
#set $show_temp = 1
#set $show_dewpoint = 0
#set $show_humidity = 0
#set $show_wind = 1
#set $show_tides = 0
#set $show_sun = 0
#set $show_moon = 0
#set $show_pop = 1
#set $show_precip = 1
#set $show_obvis = 1

#set $wlog = ''
#set $wts = ''

## These are the styles used by the forecast display.  Putting the styles
## like this works (in page, not in head), but it is not good practice.
<style>
.forecast {
  clear: both;
}
.forecast td {
  font-size: 80%;
  text-align: left;
}
.forecast table {
  table-layout: fixed;
}
.legend {
}
.legend tr {
  vertical-align: top;
}
.summary {
}
.summary tr {
  vertical-align: top;
}
.period {
}
.disclosure {
  width: 20px;
}
.col-outlook {
  width: 36px;
}
.col-date {
  width: 64px;
}
.col-temp {
  width: 30px;
}
.col-dewpoint {
  width: 30px;
}
.col-humidity {
  width: 30px;
}
.col-wind {
  width: 60px;
  height: 32px;
}
.col-pop {
  width: 40px;
}
.col-precip {
}
.col-obvis {
}
.col-tides {
  width: 80px;
}
.col-sun {
  width: 30px;
}
.col-moon {
  width: 30px;
}
.col-moonphase {
  width: 30px;
}
.units {
  color: #aaaaaa;
}
.day {
  font-size: 120%;
}
.hour {
  font-size: 80%;
}
.date {
  font-size: 80%;
}
.temphi {
  color: #ff4444;
}
.templo {
  color: #4444ff;
}
.windgust {
  color: #aaaaaa;
}
.winddir {
  color: #aaaaaa;
}
.winddir-img {
  width: 32px;
}
.outlook-img {
  width: 32px;
}
.legend-img {
  width: 15px;
}
.pop-img {
  width: 8px;
}
.precip-img {
  width: 32px;
}
.obvis-img {
  width: 32px;
}
.sources p {
  font-size: 8pt;
  font-style: italic;
  color: #aaaaaa;
}
</style>
<script type='text/javascript'>
function toggle(control, id) {
  elem = document.getElementById(id + '.hours');
  if(elem) {
    if(elem.style.display != 'none') {
      elem.style.display = 'none';
      control.src = 'icons/triangle-right.png'
    } else {
      elem.style.display = 'inline';
      control.src = 'icons/triangle-down.png'
    }
  }
}
</script>

<div class='forecast'>

## Get any tide predictions
#set $tides = $forecast.xtides

#if $show_legend
  <div class='legend'>
    <table>
      <tr>
#if $show_hourly
        <td class='disclosure'></td>
#end if
#if $show_date
        <td class='col-date'></td>
#end if
#if $show_outlook
        <td class='col-outlook'></td>
#end if
#if $show_temp
        <td class='col-temp'><img src='icons/thermometer-red.png' class='legend-img' alt='T' title='temperature' /><br/><span class='units'>$unit.label.outTemp</span></td>
#end if
#if $show_dewpoint
        <td class='col-dewpoint'><img src='icons/thermometer-dewpoint.png' class='legend-img' alt='D' title='dewpoint' /><br/><span class='units'>$unit.label.dewpoint</span></td>
#end if
#if $show_humidity
        <td class='col-humidity'><img src='icons/thermometer-blue.png' class='legend-img' alt='H' title='humidity' /><br/><span class='units'>$unit.label.outHumidity</span></td>
#end if
#if $show_wind
        <td class='col-wind' style='text-align:center'><img src='icons/flag.png' class='legend-img' alt='W' title='wind' /><br/><span class='units'>$unit.label.wind</span></td>
#end if
#if $show_tides and len($tides) > 0
        <td class='col-tides'><img src='icons/water.png' class='legend-img' alt='tide' title='tides' /><br/><span class='units'>$unit.label.altitude</span></td>
#end if
#if $show_sun
        <td class='col-sun'><img src='icons/sunriseset.png' class='legend-img' alt='S' title='sun' /><br/></td>
#end if
#if $show_moon
#if $almanac.hasExtras
        <td class='col-moon'><img src='icons/moonriseset.png' class='legend-img' alt='M' title='moon' /><br/></td>
#end if
        <td class='col-moonphase'><img src='icons/moonphase.png' class='legend-img' alt='MP' title='moon phase' /><br/></td>
#end if
#if $show_pop
        <td class='col-pop'><img src='icons/pop.png' class='legend-img' alt='PoP' title='probability of precipitation' /><br/><span class='units'>$unit.label.rain</span></td>
#end if
#if $show_precip
        <td class='col-precip'></td>
#end if
#if $show_obvis
        <td class='col-obvis'></td>
#end if
      </tr>
    </table>
  </div>
#end if ## show_legend


## Some forecasts return 16-points of the compass, but the icons support
## only 8-points.  This dictionary maps the 16 points to 8 points.
#set $wind_dir_dict = {'SSW':'SW','WSW':'SW','NNW':'NW','WNW':'NW','SSE':'SE','ESE':'SE','NNE':'NE','ENE':'NE'}

#set $lastday = None
#set $periods = $forecast.weather_periods($forecast_source, max_events=$num_periods)
#for $period in $periods
  #set $thisday = $period.event_ts.format('%d')
  #set $thisdate = $period.event_ts.format('%Y.%m.%d')
  #set $smryid = $forecast_source + '.' + $thisdate
  #set $hourid = $forecast_source + '.' + $thisdate + '.hours'
  #set $alm = $forecast.almanac(ts=$period.event_ts.raw)
  #set $nextday_ts = time.mktime(time.strptime($thisdate + ' 00:00', '%Y.%m.%d %H:%M')) + 24*3600
  #if $alm.hasExtras
    #set $sunrise_ts = $alm.sunrise.raw
    #set $sunset_ts = $alm.sunset.raw
    #set $moonrise_ts = $alm.moon.rise.raw
    #set $moonset_ts = $alm.moon.set.raw
  #else
    ## non-pyephem sunrise/sunset is not a ValueHelper so do conversions
    #set $sunrise_ts = time.mktime(time.strptime($thisdate + ' ' + $alm.sunrise, '%Y.%m.%d %H:%M'))
    #set $sunset_ts = time.mktime(time.strptime($thisdate + ' ' + $alm.sunset, '%Y.%m.%d %H:%M'))
  #end if
  #set $wts = $period.issued_ts

  #if $lastday != $thisday
#if $show_hourly
    #if $lastday is not None
    </table>
  </div>
    #end if
#end if
    #set $lastday = $thisday
    #set $summary = $forecast.weather_summary($forecast_source, $period.event_ts.raw, periods=$periods)
    #set $wloc = $summary.location

  <div id='$smryid' class='summary'>
    <table>
      <tr>
#if $show_hourly
        <td class='disclosure'><img src='icons/triangle-right.png' onclick="toggle(this, '$smryid')" /></td>
#end if
#if $show_date
        <td class='col-date'><span class='day'>$summary.event_ts.format('%a')</span><br/><span class='date'>$summary.event_ts.format('%d %b %Y')</span></td>
#end if
#if $show_outlook
        <td class='col-outlook'>
    #if $summary.clouds is not None
      #set $simg = 'icons/' + $summary.clouds + '.png'
          <img class='outlook-img' src='$simg' alt='$summary.clouds' title='$forecast.label('Weather', $summary.clouds)' />
    #end if
        </td>
#end if
#if $show_temp
        <td class='col-temp'><span class='temphi'>$summary.tempMax.nolabel('%.0f')</span><br/><span class='templo'>$summary.tempMin.nolabel('%.0f')</span></td>
#end if
#if $show_dewpoint
        <td class='col-dewpoint'>$summary.dewpointMax.nolabel('%.0f')<br/>$summary.dewpointMin.nolabel('%.0f')</td>
#end if
#if $show_humidity
        <td class='col-humidity'>$summary.humidityMax.nolabel('%.0f',' ')<br/>$summary.humidityMin.nolabel('%.0f',' ')</td>
#end if
#if $show_wind
        <td class='col-wind'
    #if $summary.windDirs is not None
            style='vertical-align:middle; text-align:center; background: url()
      #for $d in $summary.windDirs
        #set $winddir_img = 'icons/' + $wind_dir_dict.get($d,$d) + '.png'
            ,url($winddir_img)
      #end for
            ; background-repeat:no-repeat; background-position:center; background-size:32px;'
    #end if
            >
    #if $summary.windSpeedMin == $summary.windSpeedMax or $summary.windSpeedMin.raw == $summary.windSpeedMax.raw
          $summary.windSpeedMin.nolabel('%.0f',' ')
    #else
          $summary.windSpeedMin.nolabel('%.0f',' ')-$summary.windSpeedMax.nolabel('%.0f',' ')
    #end if
          <span class='windgust'>$summary.windGust.nolabel('%.0f',' ')</span>$summary.windChar
        </td>
#end if
#if $show_tides and len($tides) > 0
        <td class='col-tides'>
          <table cellspacing='0' cellpadding='0' width='100%'>
  #for $tide in $tides
    #if $summary.event_ts.raw <= $tide.event_ts.raw < $summary.event_ts.raw + $summary.duration
            <tr>
              <td style='font-size:100%'>$tide.event_ts.format('%H:%M')</td><td style='font-size:100%'>$tide.hilo</td><td style='font-size:100%; text-align:right;'>$tide.offset.nolabel('%.1f')</td>
            </tr>
    #end if
  #end for
          </table>
        </td>
#end if
#if $show_sun
        <td class='col-sun'>
  #if $alm.hasExtras
          $alm.sun.rise<br/>
          $alm.sun.set
  #else
          $alm.sunrise<br/>
          $alm.sunset
  #end if
        </td>
#end if
#if $show_moon
  #if $alm.hasExtras
        <td class='col-moon'>
          $alm.moon.rise<br/>
          $alm.moon.set
        </td>
  #end if
        <td class='col-moonphase'>
          $alm.moon_fullness%
        </td>
#end if
#if $show_pop
        <td class='col-pop'>
  #if $summary.pop.raw > 0
          $summary.pop.format('%.0f','')<br/>
    #if $summary.qpf.raw > 0
          $summary.qpf.nolabel('%.2f','') <img class='pop-img' src='icons/raindrop.png' /><br/>
    #end if
    #if $summary.qsf.raw > 0
          $summary.qsf.nolabel('%.2f','') <img class='pop-img' src='icons/snowflake.png' />
    #end if
  #end if
        </td>
#end if
#if $show_precip
        <td class='col-precip'>
  #for $k in $summary.precip
    #set $precip_img = 'icons/' + $k + '.png'
         <img class='precip-img' src='$precip_img' alt='$k' title='$forecast.label('Weather', $k)' />
  #end for
        </td>
#end if
#if $show_obvis
        <td class='col-obvis'>
  #for $k in $summary.obvis
    #set $obvis_img = 'icons/' + $k + '.png'
         <img class='obvis-img' src='$obvis_img' alt='$k' title='$forecast.label('Weather', $k)' />
  #end for
        </td>
#end if
      </tr>
    </table>
  </div>


#if $show_hourly
  <div id='$hourid' class='period' style='display:none'>
    <table>
#end if
  #end if ## lastday != thisday


#if $show_hourly
  #set $hour = $period.event_ts.format('%H:%M')
      <tr>
        <td class='disclosure'></td>
#if $show_date
        <td class='col-date'>$hour<br/></td>
#end if
#if $show_outlook
        <td class='col-outlook'>
  #if $period.clouds is not None
    #if $sunrise_ts < $period.event_ts.raw < $sunset_ts
      #set $outlook_img = 'icons/' + $period.clouds + '.png'
    #else
      #set $outlook_img = 'icons/' + $period.clouds + 'n.png'
    #end if
          <img class='outlook-img' src='$outlook_img' alt='$period.clouds' title='$forecast.label('Weather', $period.clouds)' />
  #end if
        </td>
#end if
#if $show_temp
        <td class='col-temp'>$period.temp.nolabel('%.0f')</td>
#end if
#if $show_dewpoint
        <td class='col-dewpoint'>$period.dewpoint.nolabel('%.0f')</td>
#end if
#if $show_humidity
        <td class='col-humidity'>$period.humidity.nolabel('%.0f',' ')</td>
#end if
#if $show_wind
        <td class='col-wind'
  #if $period.windDir is not None
    #set $winddir_img = 'icons/' + $wind_dir_dict.get($period.windDir,$period.windDir) + '.png'
          background='$winddir_img' style='text-align:center; background-repeat:no-repeat; background-position:center; background-size:32px;'
  #end if
            >
          $period.windSpeed.nolabel('%.0f',' ') <span class='windgust'>$period.windGust.nolabel('%.0f',' ')</span>$period.windChar<br/>
        </td>
#end if
#if $show_tides and len($tides) > 0
        <td class='col-tides'>
  #for $tide in $tides
    #if $period.event_ts.raw <= $tide.event_ts.raw < $period.event_ts.raw + $period.duration and $tide.event_ts.raw < $nextday_ts
           $tide.event_ts.format('%H:%M') $tide.hilo $tide.offset.nolabel('%.1f')
    #end if
  #end for
        </td>
#end if
#if $show_sun
        <td class='col-sun'>
  #if $period.event_ts.raw <= $sunrise_ts < $period.event_ts.raw + $period.duration
          $alm.sunrise
  #end if
  #if $period.event_ts.raw <= $sunset_ts < $period.event_ts.raw + $period.duration
          $alm.sunset
  #end if
        </td>
#end if
#if $show_moon
  #if $alm.hasExtras
        <td class='col-moon'>
  #if $period.event_ts.raw <= $moonrise_ts < $period.event_ts.raw + $period.duration
          $alm.moon.rise
  #end if
  #if $period.event_ts.raw <= $moonset_ts < $period.event_ts.raw + $period.duration
          $alm.moon.set
  #end if
        </td>
  #end if
        <td class='col-moonphase'></td>
#end if
#if $show_pop
        <td class='col-pop'>
  #if $period.pop.raw > 0
          $period.pop.format('%.0f',' ')<br/>
    #if $period.qpf.raw > 0
          $period.qpf.nolabel('%.2f',' ') <img class='pop-img' src='icons/raindrop.png' /><br/>
    #end if
    #if $period.qsf.raw > 0
          $period.qsf.nolabel('%.2f',' ') <img class='pop-img' src='icons/snowflake.png' />
    #end if
  #end if
        </td>
#end if
#if $show_precip
        <td class='col-precip'>
          <table width='100%'><tr>
  #for $k,$v in $period.precip.items()
          <td>
    #set $precip_img = 'icons/' + $k + '.png'
            <img class='precip-img' src='$precip_img' alt='$k' title='$forecast.label('Weather', $k)' />
            <br/>
    #if $v != ''
            $forecast.label('Weather', $v+'q')
    #else
            &nbsp;
    #end if
          </td>
  #end for
          </tr></table>
        </td>
#end if
#if $show_obvis
        <td class='col-obvis'>
  #if $period.obvis is not None
    #set $obvis_img = 'icons/' + $period.obvis + '.png'
          <img class='obvis-img' src='$obvis_img' alt='$period.obvis' title='$forecast.label('Weather', $period.obvis)' />
  #end if
        </td>
#end if
      </tr>
#end if  ## show_hourly
#end for ## period in periods

#if $show_hourly
    </table>
  </div>
#end if

  <div class='sources'>
    <p>
#if $show_tides and len($tides) > 0
      tides for $tides[0].location issued on $tides[0].issued_ts<br/>
#end if
      $forecast_source forecast
#if $wloc is not None and $wloc != ''
 for $wloc
#end if
#if $wts is not None and $wts != ''
 issued on $wts
#end if
    </p>
  </div>

</div>

#else

<!-- forecasting is not installed -->

#end if
