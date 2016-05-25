<div id="header" class="page_heading">
  <div class="title_left">
    <div class="station_title">$station.location</div>
    <div class="page_title">$page_title</div>
  </div>
  <div class="title_right">
    <div class="logo">
      <a href="http://weewx.com/"><img src="weewx.png" /></a>
    </div>
    <div class="station_location">
      $current.dateTime<br/>
      $station.latitude[0]&deg; $station.latitude[1]' $station.latitude[2]
      $station.longitude[0]&deg; $station.longitude[1]' $station.longitude[2]<br/>
      $station.altitude
    </div>
  </div>
  <div class="nav">
    <div class="navitem $btn.get('day', 'button')">
      <a href="index.html">Day</a></div>
    <div class="navitem $btn.get('week', 'button')">
      <a href="week.html">Week</a></div>
    <div class="navitem $btn.get('month', 'button')">
      <a href="month.html">Month</a></div>
    <div class="navitem $btn.get('year', 'button')">
      <a href="year.html">Year</a></div>
    <div class="navitem $btn.get('archive', 'button')">
      <a href="archive.html">Archive</a></div>
    <div class="rss"><a href="rss.xml"><img src="rss.png" /></a></div>
  </div>
</div>

<div style="clear:both"></div>

