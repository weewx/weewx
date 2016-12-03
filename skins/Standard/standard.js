/* javascript for weewx standard report */

var cookie_prefix = "weewx.standard.";
var widgets = ['current', 'celestial', 'hilo', 'about', 'radar', 'satellite'];

function setup() {
  var id = get_cookie('history', 'day');
  choose_history(id);
  id = get_cookie('celestial', 'summary');
  choose_celestial(id);
  var hilo_periods = ['week', 'month', 'year'];
  for(var i=0; i<hilo_periods.length; i++) {
    var showing = get_cookie('hilo.' + hilo_periods[i], 'false');
    toggle('hilo', hilo_periods[i], showing);
  }
  for(var i=0; i<widgets.length; i++) {
    var state = get_cookie(widgets[i]+'.state', 'expanded');
    toggle_widget(widgets[i], state);
  }
}

function choose_history(id) {
  choose_div('history', id, ['day', 'week', 'month', 'year']);
}

function choose_celestial(id) {
  choose_div('celestial', id, ['summary', 'details']);
}

function toggle_widget(id, state) {
  var c = document.getElementById(id+'_widget');
  if(c) {
    for(var i=0; i<c.childNodes.length; i++) {
      if(c.childNodes[i].className == 'widget_contents') {
        if(state === undefined) {
          // make it the opposite of the current state
          state = c.childNodes[i].style.display == 'block' ? 'collapsed' : 'expanded';
        }
        c.childNodes[i].style.display = (state == 'expanded') ? 'block' : 'none';
      }
    }
    set_cookie(id+'.state', state);
  }
}

// if showing is specified, set state to match.  if not, then toggle state
// based on current state.
function toggle(group, id, showing) { 
  if(showing === undefined) {
    showing = 'false';
  }
  var c = document.getElementById('button_' + group + '_' + id);
  if(c) {
    var cl = ' ' + c.className + ' ';
    if(cl.indexOf(' button ') >= 0) {
      showing = 'true';
    }
    c.className = (showing == 'true') ? 'button_selected' : 'button';
  }
  var items = document.getElementsByClassName(group + '_' + id);
  if(items) {
    for(var i=0; i<items.length; i++) {
      if(showing == 'true') {
        items[i].style.display = '';
      } else {
        items[i].style.display = 'none';
      }
    }
  }
  set_cookie(group + '.' + id, showing);
}

function choose_div(group, selected_id, all_ids) {
  for(var i=0; i<all_ids.length; i++) {
    var c = document.getElementById('button_' + group + '_' + all_ids[i]);
    if(c) c.className = (all_ids[i] == selected_id) ? 'button_selected' : 'button';
    var g = document.getElementById(group + '_' + all_ids[i]);
    if(g) g.style.display = (all_ids[i] == selected_id) ? 'block' : 'none';
  }
  set_cookie(group, selected_id);
}

function set_cookie(name, value, dur) {
  if(dur==null || dur==0) dur=30;
  var today = new Date();
  var expire = new Date();
  expire.setTime(today.getTime() + 24*3600000*dur);
  document.cookie = cookie_prefix+name+"="+escape(value)+";expires="+expire.toGMTString();
}

function get_cookie(name, default_value) {
  if(name=="") return default_value;
  var full_name = cookie_prefix+name;
  var cookie = " "+document.cookie;
  var i = cookie.indexOf(" "+full_name+"=");
  if(i<0) i = cookie.indexOf(";"+full_name+"=");
  if(i<0) return default_value;
  var j = cookie.indexOf(";", i+1);
  if(j<0) j = cookie.length;
  return unescape(cookie.substring(i + full_name.length + 2, j));
}

function openNOAAFile(date) {
  window.location = "NOAA/NOAA-" + date + ".txt";
}
