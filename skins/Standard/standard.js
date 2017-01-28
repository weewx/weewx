/* javascript for weewx standard report */

var cookie_prefix = "weewx.standard.";

function setup(widgets) {
  var id = get_cookie('history', 'day');
  choose_history(id);
  id = get_cookie('celestial', 'summary');
  choose_celestial(id);
  if(widgets) {
    for(var i=0; i<widgets.length; i++) {
      var state = get_cookie(widgets[i]+'.state', 'expanded');
      toggle_widget(widgets[i], state);
    }
  }
}

function choose_history(id) {
  choose_div('history', id, ['day', 'week', 'month', 'year']);
  choose_col('hilo', id, ['week', 'month', 'year']);
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

function choose_col(group, selected_id, all_ids) { 
  for(var i=0; i<all_ids.length; i++) {
    var items = document.getElementsByClassName(group + '_' + all_ids[i]);
    if(items) {
      var display = selected_id == all_ids[i] ? '' : 'none';
      for(var j=0; j<items.length; j++) {
        items[j].style.display = display;
      }
    }
  }
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
