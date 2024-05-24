#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""User extensions module

This module is imported from the main executable, so anything put here will be
executed before anything else happens. This makes it a good place to put user
extensions.
"""

import locale

# This sets the locale for all categories to the user’s default setting (typically specified in the
# LANG environment variable). See: https://docs.python.org/3/library/locale.html#locale.setlocale
locale.setlocale(locale.LC_ALL, '')
