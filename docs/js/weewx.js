/*
 *  Copyright (c) 2014 Tom Keffer <tkeffer@gmail.com>
 * 
 *  See the file LICENSE.txt for your full rights.
 *
 *  $Id$
 */

function wee_gen_id(text, element) {
	// If the element has an explicit id, use that.
	// Otherwise, use the same generator function as the
	// old Samaxes TOC library
	hv = element[0].getAttribute('id');
    if (hv == null) {
	    hv = text.replace(/[ <>#\/\\?&\n]/g, '_');
    }
    return hv
}

function set_cookie(name, value, dur) {
    if(dur==null || dur==0) dur=30;
    var today = new Date();
    var expire = new Date();
    expire.setTime(today.getTime() + 24*3600000*dur);
    document.cookie = name+"="+escape(value)+";expires="+expire.toGMTString();
}

function get_cookie(name) {
    if(name=="") return;
    var cookie = " "+document.cookie;
    var i = cookie.indexOf(" "+name+"=");
    if(i<0) i = cookie.indexOf(";"+name+"=");
    if(i<0) return "";
    var j = cookie.indexOf(";", i+1);
    if(j<0) j = cookie.length;
    return unescape(cookie.substring(i + name.length + 2, j));
}
