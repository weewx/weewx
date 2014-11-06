/*
 *  Copyright (c) 2014 Tom Keffer <tkeffer@gmail.com>
 * 
 *  See the file LICENSE.txt for your full rights.
 *
 *  $Id$
 */

function wee_gen_id(text, element) {
	// Given an element, extracts a suitable ID tag, for use in
	// links.
    hv = element[0].getAttribute('id');
    if (hv == null) {
      // prettify the text
      hv = text.toLowerCase().replace(/\s/g, "-");
      // fix double hyphens
      while (hv.indexOf("--") > -1) {
        hv = hv.replace(/--/g, "-");
      }
      // fix colon-space instances
      while (hv.indexOf(":-") > -1) {
        hv = hv.replace(/:-/g, "-");
      }
    }
    return hv;
}
