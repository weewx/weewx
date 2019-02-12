/*  Javascript for the weewx documentation
 *
 *  Copyright (c) 2015 Tom Keffer <tkeffer@gmail.com>
 * 
 *  See the file LICENSE.txt for your rights.
 */

function wee_gen_id(text, element) {
        // If the element has an explicit id, use that.
	// Otherwise, use the same generator function as the
	// old Samaxes TOC library
	var hv = element[0].getAttribute('id');
    if (!hv) {
	    hv = text.replace(/[ <>#\/\\?&\n]/g, '_');
    }
    return hv
}

function set_cookie(name, value, days) {
    // Default duration of 30 days
    if (!days) days = 30;
    var expire = new Date(Date.now() + 24 * 3600000 * days);
    document.cookie = name + "=" + value + ";path=/;expires=" + expire.toUTCString();
}

function get_cookie(name) {
    if (!name) return "";
    var v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
    return v ? v[2] : null;
}

function get_default_level() {
    var level = get_cookie("toc_level");
    if (!level) {
        level = 3;
    }
    return level;
}

function create_toc_control(level) {
    var c = document.getElementById('toc_controls');
    if (c) {
        var txt = "<select id='toc_level' onChange='change_toc_level()'>";

        txt += "<option value='1'";
        if (level == 1) {
            txt += " selected";
        }
        txt += ">Less detail</option>";

        txt += "<option value='2'";
        if (level == 2) {
            txt += " selected";
        }
        txt += ">Some detail</option>";

        txt += "<option value='3'";
        if (level == 3) {
            txt += " selected";
        }
        txt += ">More detail</option>";

        txt += "<option value='4'";
        if (level == 4) {
            txt += " selected";
        }
        txt += ">Very detailed</option>";

        txt += "</select>";
        c.innerHTML = txt;
    }
}

function change_toc_level() {
    var field = document.getElementById('toc_level');
    if(field) {
        set_cookie("toc_level", field.value);
        $("#toc").remove();
        $("#toc_parent").append("<div id='toc'></div>");
        generate_toc(field.value);
    }
}

function generate_toc(level) {
    var sstr = "h1";
    for (var i=2; i<=level; i++) {
        sstr += ",h"+i;
    }
    $("#toc").tocify({
      context : "#technical_content",
      showAndHide : false,
      theme : "jqueryui",
      ignoreSelector : ".title",
      hashGenerator : wee_gen_id,
      selectors : sstr
      }).data("toc-tocify");
}
