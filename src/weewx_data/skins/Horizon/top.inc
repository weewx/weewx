## Copyright (c) 2026 Manuel Hilgert
## Distributed under terms of GPLv3.  See LICENSE.txt for your rights.
#errorCatcher Echo
#encoding UTF-8
##
## The way back to the top of a long page. Every page carries it, and the script
## decides when it can be seen: it is out of sight until there is enough page behind
## the reader to make the trip worth a button, and it never appears at all where
## there is no JavaScript to notice the scrolling.
    <button type="button" id="to-top" class="icon-button to-top"
            aria-label="$gettext('Back to top')">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m-7 7l7-7 7 7"/></svg>
    </button>
