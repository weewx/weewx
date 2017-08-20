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

function set_cookie(name, value, dur) {
    if(dur===null || dur===0) dur=30;
    var today = new Date();
    var expire = new Date();
    expire.setTime(today.getTime() + 24*3600000*dur);
    document.cookie = name+"="+encodeURIComponent(value)+";expires="+expire.toUTCString();
}

function get_cookie(name) {
    if(name==="") return "";
    var cookie = " "+document.cookie;
    var i = cookie.indexOf(" "+name+"=");
    if(i<0) i = cookie.indexOf(";"+name+"=");
    if(i<0) return "";
    var j = cookie.indexOf(";", i+1);
    if(j<0) j = cookie.length;
    return decodeURIComponent(cookie.substring(i + name.length + 2, j));
}

function get_default_level() {
    var level = get_cookie("toc_level");
    if (level === "") { level = 2; }
    return level;
}

function create_toc_control(level) {
    var c = document.getElementById('toc_controls');
    if(c) {
        var txt = "<select id='toc_level' onChange='change_toc_level()'>";
        txt += "<option value='1'";
        if (level === 1) { txt += " selected"; }
        txt += ">Less Detail</option>";
        txt += "<option value='2'";
        if (level === 2) { txt += " selected"; }
        txt += ">Some Detail</option>";
        txt += "<option value='3'";
        if (level === 3) { txt += " selected"; }
        txt += ">More Detail</option>";
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
