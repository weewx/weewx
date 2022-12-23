#
#    Copyright (c) 2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""The 'weectl' package."""
import sys

if sys.platform == 'darwin':
    default_config_path = '/Users/Shared/weewx/weewx.conf'
else:
    default_config_path = '/home/weewx/weewx.conf'
