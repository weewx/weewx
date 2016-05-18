<div id="plots" class="widget">
  <img src="${period}tempdew.png" alt="$obs.label.outTemp" />
  #if $archive.inTemp.has_data
  <img src="${period}inside.png" alt="$obs.label.inTemp" />
  #end if
  <img src="${period}tempchill.png" alt="$obs.label.windchill" />
  <img src="${period}barometer.png" alt="$obs.label.barometer"/>
  <img src="${period}rain.png" alt="$obs.label.rain" />
  <img src="${period}wind.png" alt="$obs.label.windSpeed" />
  <img src="${period}winddir.png" alt="$obs.label.windDir" />
  <img src="${period}windvec.png" alt="$obs.label.windvec" />
  #if $archive.radiation.has_data
  <img src="${period}radiation.png" alt="$obs.label.radiation" />
  #end if
  #if $archive.extraTemp1.has_data
  <img src="${period}extratemp1.png" alt="$obs.label.extraTemp1" />
  #end if
  #if $archive.rxCheckPercent.has_data
  <img src="${period}rx.png" alt="$obs.label.rxCheckPercent"/>
  #end if
</div>
