/* javascript for weewx Seasons report */

var cookie_prefix = "weewx.seasons.";

function setup(widgets) {
  // set the state of the history widget
  var id = get_cookie('history', 'day');
  choose_history(id);
  // if we got a list of widget names, then use it.  otherwise, query the doc
  // for every object with an id of *_widget, and use that as the name list.
  if(! widgets) {
    widgets = [];
    var items = document.getElementsByClassName('widget');
    if(items) {
      for(var i=0; i<items.length; i++) {
        if(items[i].id) {
          var widget_name = items[i].id.replace('_widget', '');
          if(widget_name) {
            widgets.push(widget_name);
          }
        }
      }
    }
  }
  // now set the toggle state for each widget based on what the cookies say
  for(var i=0; i<widgets.length; i++) {
    var state = get_cookie(widgets[i]+'.state', 'expanded');
    toggle_widget(widgets[i], state);
  }
}

function choose_history(id) {
  choose_div('history', id, ['day', 'week', 'month', 'year']);
  choose_col('hilo', id, ['week', 'month', 'year']);
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

function get_parameter(name) {
  var query = window.location.search.substring(1);
  if (query) {
    var vars = query.split("&");
    for (var i=0; i<vars.length; i++) {
      var pair = vars[i].split("=");
      if (pair[0] == name) {
        return pair[1];
      }
    }
  }
  return false;
}

function load_file(div_id, var_name) {
  var content = '';
  var file = get_parameter(var_name);
  if (file) {
    content = "Loading " + file;
    var xhr = new XMLHttpRequest();
    xhr.onload = function() {
      var e = document.getElementById(div_id);
      if (e) {
        e.textContent = this.responseText;
      }
    };
    xhr.open('GET', file);
    xhr.send();
  } else {
    content = 'nothing specified';
  }
  var e = document.getElementById(div_id);
  if (e) {
    e.innerHTML = content;
  }
}

function openNOAAFile(date) {
  if (date.match(/^\d\d\d\d/)) {
    window.location = "NOAA/NOAA-" + date + ".txt";
  }
}

function openTabularFile(date) {
  if (date.match(/^\d\d\d\d/)) {
    window.location = "tabular.html?report=NOAA/NOAA-" + date + ".txt";
  }
}
