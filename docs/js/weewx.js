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
