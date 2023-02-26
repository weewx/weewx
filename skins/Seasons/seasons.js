/* javascript for the weewx Seasons skin
 * Copyright (c) Tom Keffer, Matthew Wall
 * Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
 */

const cookie_prefix = "weewx.seasons.";
let year_type = get_state('year_type', 'year');

function setup(widgets) {
    // set the state of the history widget
    const id = get_state('history', 'day');
    choose_history(id);
    // if we got a list of widget names, then use it.  otherwise, query the doc
    // for every object with an id of *_widget, and use that as the name list.
    if (!widgets) {
        widgets = [];
        const items = document.getElementsByClassName('widget');
        if (items) {
            for (let i = 0; i < items.length; i++) {
                if (items[i].id) {
                    const widget_name = items[i].id.replace('_widget', '');
                    if (widget_name) {
                        widgets.push(widget_name);
                    }
                }
            }
        }
    }
    // now set the toggle state for each widget based on what the cookies say
    for (let i = 0; i < widgets.length; i++) {
        const state = get_state(widgets[i] + '.state', 'expanded');
        toggle_widget(widgets[i], state);
    }
}

function choose_history(id) {
    choose_div('history', id, ['day', 'week', 'month', 'year']);
    choose_col('hilo', id, ['week', 'month', 'year', 'rainyear']);
    choose_col('totals', id, ['week', 'month', 'year', 'rainyear']);
    choose_rainyear(id);
}

function choose_rainyear(id) {
    if (id === 'year') {
        choose_col('hilo', year_type, ['year', 'rainyear']);
        choose_col('totals', year_type, ['year', 'rainyear']);
    }
}

function toggle_rainyear() {
    if (year_type === 'year') {
        year_type = 'rainyear';
    } else {
        year_type = 'year';
    }
    set_state('year_type', year_type);
    const id = get_active_div('history', ['day', 'week', 'month', 'year'], 'day');
    choose_rainyear(id);
}

function toggle_widget(id, state) {
    const id_elements = document.getElementById(id + '_widget');
    if (id_elements) {
        for (let i = 0; i < id_elements.childNodes.length; i++) {
            if (id_elements.childNodes[i].className === 'widget_contents') {
                if (state === undefined) {
                    // make it the opposite of the current state
                    state = id_elements.childNodes[i].style.display === 'block' ? 'collapsed' : 'expanded';
                }
                id_elements.childNodes[i].style.display = (state === 'expanded') ? 'block' : 'none';
            }
        }
        set_state(id + '.state', state);
    }
}

function choose_col(group, selected_id, all_ids) {
    for (let i = 0; i < all_ids.length; i++) {
        let elements = document.getElementsByClassName(group + '_' + all_ids[i]);
        if (elements) {
            const display = selected_id === all_ids[i] ? '' : 'none';
            for (let j = 0; j < elements.length; j++) {
                elements[j].style.display = display;
            }
        }
    }
}

function choose_div(group, selected_id, all_ids) {
    for (let i = 0; i < all_ids.length; i++) {
        const button = document.getElementById('button_' + group + '_' + all_ids[i]);
        if (button) {
            button.className = (all_ids[i] === selected_id) ? 'button_selected' : 'button';
        }
        const element = document.getElementById(group + '_' + all_ids[i]);
        if (element) {
            element.style.display = (all_ids[i] === selected_id) ? 'block' : 'none';
        }
    }
    set_state(group, selected_id);
}

/* if cookies are disabled, then we must look at page to get state */
function get_active_div(group, all_ids, default_value) {
    let id = default_value;
    for (let i = 0; i < all_ids.length; i++) {
        const button = document.getElementById('button_' + group + '_' + all_ids[i]);
        if (button && button.className === 'button_selected') {
            id = all_ids[i];
        }
    }
    return id;
}

function set_state(name, value, dur) {
    const full_name = cookie_prefix + name;
/*    set_cookie(full_name, value, dur); */
    window.localStorage.setItem(full_name, value);
}

function get_state(name, default_value) {
    const full_name = cookie_prefix + name;
/*    return get_cookie(name, default_value); */
    let value = window.localStorage.getItem(full_name);
    if (value === undefined || value == null) {
        value = default_value;
    }
    return value
}

function set_cookie(name, value, dur) {
    if (!dur) dur = 30;
    const today = new Date();
    let expire = new Date();
    expire.setTime(today.getTime() + 24 * 3600000 * dur);
    document.cookie = name + "=" + encodeURI(value) + ";expires=" + expire.toUTCString();
}

function get_cookie(name, default_value) {
    if (name === "") return default_value;
    const cookie = " " + document.cookie;
    let i = cookie.indexOf(" " + name + "=");
    if (i < 0) i = cookie.indexOf(";" + name + "=");
    if (i < 0) return default_value;
    let j = cookie.indexOf(";", i + 1);
    if (j < 0) j = cookie.length;
    return unescape(cookie.substring(i + name.length + 2, j));
}

function get_parameter(name) {
    const query = window.location.search.substring(1);
    if (query) {
        const vars = query.split("&");
        for (let i = 0; i < vars.length; i++) {
            const pair = vars[i].split("=");
            if (pair[0] === name) {
                return pair[1];
            }
        }
    }
    return false;
}

function load_file(div_id, var_name) {
    let content;
    const file = get_parameter(var_name);
    if (file) {
        content = "Loading " + file;
        let xhr = new XMLHttpRequest();
        xhr.onload = function () {
            let e = document.getElementById(div_id);
            if (e) {
                e.textContent = this.responseText;
            }
        };
        xhr.open('GET', file);
        xhr.send();
    } else {
        content = 'nothing specified';
    }
    let e = document.getElementById(div_id);
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
