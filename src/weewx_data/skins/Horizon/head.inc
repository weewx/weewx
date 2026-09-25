## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The title of a page is '$page_title' and the station's location. The front page
## sets no '$page_title' and gets the location alone.
##
## A page passes '$page_title', '$page_units' and '$climate_year' to the includes
## with '#set global'. An include cannot read a name that the page sets with a plain
## '#set'.
#set $title = $getVar('page_title', '')
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light dark">
#if $title
    <title>$title &ndash; $station.location</title>
#else
    <title>$station.location</title>
#end if
    <link rel="icon" href="favicon.ico" sizes="any">
    <link rel="stylesheet" href="horizon.css">
## The stylesheets named in 'custom_css' load after horizon.css, so that their rules
## take precedence.
#for $css in $to_list($DisplayOptions.get('custom_css', []))
  #if $css
    <link rel="stylesheet" href="$css">
  #end if
#end for
#if $station.station_url
    <link rel="canonical" href="$station.station_url/$filename">
#end if
    <script>
      /* This script runs before the browser draws the page. The script applies the
         theme saved in localStorage, so that the page never shows the other theme
         first. The script also adds the class 'js' to <html>. Only with 'js' does
         horizon.css hide the navigation behind the menu button on a narrow screen.
         Without scripts the menu button cannot open the navigation. */
      (function () {
        var root = document.documentElement;
        root.classList.add('js');
        try {
          var t = localStorage.getItem('weewx.horizon.theme');
          if (t === 'dark' || t === 'light') root.setAttribute('data-theme', t);
        } catch (e) {}
      })();
    </script>
    #include "analytics.inc"
