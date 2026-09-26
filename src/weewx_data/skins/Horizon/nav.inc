## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## Every page has the same navigation; only the entry marked as current differs. On
## a narrow screen the menu button in the masthead opens the navigation over the page.
##
## The time span links switch the charts and the tiles on the front page. The links
## appear only when 'panels' includes 'history', because horizon.js switches the time
## span only where the page has charts. On the front page each link is a bare hash
## such as '#week'. horizon.js switches the charts on 'hashchange' and marks the link
## with 'aria-current'. A link to 'index.html#week' would reload the front page when
## the front page is served as '/'.
#set $periods = $to_list($DisplayOptions.get('periods', ['day', 'week', 'month', 'year']))
#set $has_charts = 'history' in $to_list($DisplayOptions.get('panels', ['history']))
#set $front = '' if $page == 'index' else 'index.html'
#set $period_icons = {'day': 'nav-today', 'week': 'nav-week', 'month': 'nav-month',
                      'year': 'nav-year'}
##
## The station's other pages. Each name is the page's section name in skin.conf,
## and the page's file is that name plus '.html'. On a climate year page
## ('climate_year') the Climate entry is marked as current.
#set $here = 'climate' if $page == 'climate_year' else $page
#set $pages = [('climate', 'nav-page', $gettext("Climate")),
               ('statistics', 'nav-statistics', $gettext("Statistics")),
               ('celestial', 'nav-celestial', $gettext("Celestial")),
               ('reports', 'nav-archive', $gettext("Reports")),
               ('telemetry', 'nav-monitor', $gettext("Telemetry"))]
#set $show_units = $to_bool($getVar('page_units', True))
#set $languages = $DisplayOptions.get('Languages', {})
      <nav class="site-nav" id="site-nav" aria-label="$gettext('Menu')">
#if $has_charts
        <section class="nav-group">
          <h2 class="nav-heading">$gettext("Conditions")</h2>
          <ul class="nav-list">
  #for $period in $periods
    #set $href = $front + '#' + $period
## A time span without an icon still gets an empty icon element, so that the labels
## line up.
    #set $icon = ''
    #if $period in $period_icons
      #set $icon = ' style="--icon:url(icons/%s.svg)"' % $period_icons[$period]
    #end if
            <li><a class="nav-item" href="$href" data-period="$period"><span class="nav-icon"$icon aria-hidden="true"></span>$gettext($period.capitalize())</a></li>
  #end for
          </ul>
        </section>
#end if
        <section class="nav-group">
          <h2 class="nav-heading">$gettext("Station")</h2>
          <ul class="nav-list">
#for $name, $icon, $label in $pages
  #set $mark = ' aria-current="page"' if $name == $here else ''
            <li><a class="nav-item" href="${name}.html"$mark><span class="nav-icon" style="--icon:url(icons/${icon}.svg)" aria-hidden="true"></span>$label</a></li>
#end for
          </ul>
        </section>
#if $show_units or len($languages) > 1
        <div class="nav-settings">
  #if $show_units
## Every page whose '$page_units' is not False gets the unit picker. horizon.js fills
## the list from 'data/skin.json' and unhides the field when skin.json offers at
## least two unit systems.
          <p class="nav-field" hidden>
            <label for="unit-picker">$gettext("Units")</label>
            <select id="unit-picker" class="select"></select>
          </p>
  #end if
  #if len($languages) > 1
## Each 'path' in [[Languages]] is relative to the top directory of the station's
## pages. 'lang_root' is the path from this report's HTML_ROOT back to that top
## directory, e.g., '..' for a report that writes to 'en'. The comment at the year
## picker in masthead.inc explains autocomplete="off".
    #set $lang_root = $DisplayOptions.get('lang_root', '.')
          <p class="nav-field">
            <label for="lang-picker">$gettext("Language")</label>
            <select id="lang-picker" class="select" autocomplete="off"
                    onchange="if (this.value) window.location = this.value;">
    #for $code in $languages
      #set $entry = $languages[$code]
      #set $path = $entry.get('path', $code)
      #set $parts = [$p for $p in [$lang_root, $path] if $p not in ('.', '')]
      #set $target = '/'.join($parts + ['index.html'])
              <option value="$target"#if $code == $lang or $lang.startswith($code + '_') then ' selected' else ''#>$entry.get('label', $code)</option>
    #end for
            </select>
          </p>
  #end if
        </div>
#end if
      </nav>
