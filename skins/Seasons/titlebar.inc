## titlebar for weewx skins
## Copyright Tom Keffer, Matthew Wall
## See LICENSE.txt for your rights
#errorCatcher Echo
#encoding UTF-8

<div id="title_bar">
  <div id="title">
    <h1 class="page_title">$station.location</h1>
    <p class="lastupdate">$current.dateTime</p>
  </div>
  <div id="rss_link"><a href="rss.xml">RSS</a></div>
  <div id="reports">
    $obs.label.monthly_reports:
    <select name="reports" onchange="openTabularFile(value)">
      #for $monthYear in $SummaryByMonth
      <option value="$monthYear">$monthYear</option>
      #end for
      <option selected>- $obs.label.select_month -</option>
    </select>
    <br/>
    $obs.label.yearly_reports:
    <select name="reports" onchange="openTabularFile(value)">
      #for $yr in $SummaryByYear
      <option value="$yr">$yr</option>
      #end for
      <option selected>- $obs.label.select_year -</option>
    </select>
    <br/>
  </div>
</div>
