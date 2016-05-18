<!DOCTYPE html>
<html>
  <head>
    <title>$station.location : $page_title</title>
    <link rel="stylesheet" type="text/css" href="weewx.css"/>
    <link rel="icon" type="image/png" href="favicon.ico" />
    #include "ga.inc"
  </head>
  <body>

#include "header.inc"

<div class="content">
  <div class="sidebar">
    #include "radar.inc"
    #include "current_conditions.inc"
    #include "historical_summary.inc"
    #include "celestial.inc"
    #include "station_info.inc"
  </div>

  <div class="main">
    #include "plots.inc"
  </div>
</div>

  </body>
</html>
