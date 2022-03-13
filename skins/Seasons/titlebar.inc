## titlebar for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

#set $show_rss = $to_bool($DisplayOptions.get('show_rss', True))
#set $show_reports = $to_bool($DisplayOptions.get('show_reports', True))

<div id="title_bar">
  <div id="title">
    <h1 class="page_title">$station.location</h1>
    <p class="lastupdate">$current.dateTime</p>
  </div>
#if $show_rss
  <div id="rss_link"><a href="rss.xml">RSS</a></div>
#end if
#if $show_reports
  <div id="reports">
    $gettext("Monthly Reports"):
    <select name="reports" onchange="openTabularFile(value)">
      #for $monthYear in $SummaryByMonth
      <option value="$monthYear">$monthYear</option>
      #end for
      <option selected>- $gettext("select month") -</option>
    </select>
    <br/>
    $gettext("Yearly Reports"):
    <select name="reports" onchange="openTabularFile(value)">
      #for $yr in $SummaryByYear
      <option value="$yr">$yr</option>
      #end for
      <option selected>- $gettext("select year") -</option>
    </select>
    <br/>
  </div>
#end if
</div>
