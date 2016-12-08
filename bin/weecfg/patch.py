#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Classes to support patching of weewx data."""

# standard python imports
import sys
import syslog

# weewx imports
import weewx

from weeutil.weeutil import tobool
from weewx import require_weewx_version


# ============================================================================
#                            class DatabasePatch
# ============================================================================

class DatabasePatch(object):
    """Base class for applying patches to the weewx database."""

    def __init__(self, config_dict, patch_config_dict, log):
        """A generic initialisation."""

        # give our patch object some logging abilities
        self.plog = log
        # save our weewx config dict
        self.config_dict = config_dict
        # save our patch config dict
        self.patch_config_dict = patch_config_dict
        # get our name
        self.name = patch_config_dict['name']
        # is this a dry run
        self.dry_run = tobool(patch_config_dict.get('dry_run', True)) == True
        if self.dry_run:
            self.plog.printlog(syslog.LOG_INFO, "A dry run has been requested.")
        # check if we have the required weewx version
        _min_weewx = patch_config_dict.get('required_weewx', '3.6.0')
        require_weewx_version('patch', _min_weewx)

    def run(self):
        raise NotImplementedError("Method 'run' not implemented")

    @staticmethod
    def progress(percent):
        """Generic progress function.

        Generic progress function. Patches that have different requirements
        should override this method in their class definition.
        """

        print >>sys.stdout, "%d% complete..." % (percent, ),
        sys.stdout.flush()


# ============================================================================
#                           class WeewxPatchLog
# ============================================================================


class DatabasePatchLog(object):
    """Class to handle patch logging.

    This class provides a wrapper around the python syslog module to handle
    patch logging requirements.
    """

    def __init__(self, patch_config_dict):
        """Initialise our log environment."""

        # first check if we are turning off log to file or not
        try:
            log_bool = patch_config_dict.get('log_results', True) == True
        except KeyError:
            log_bool = True
        # Flag to indicate whether we are logging to file or not. Log to file
        # every time except when logging is explicitly turned off on the
        # command line or its a dry run.
        try:
            _dry_run = patch_config_dict.get('dry_run', True) == True
        except KeyError:
            _dry_run = True
        self.log = not _dry_run and log_bool
        # if we are logging then setup our syslog environment
        # if --verbose we log up to syslog.LOG_DEBUG
        # otherwise just log up to syslog.LOG_INFO
        try:
            self.verbose = patch_config_dict.get('verbose', False) == True
        except KeyError:
            self.verbose = False
        if self.log:
            syslog.openlog(ident='weewx_dbpatch', logoption=syslog.LOG_PID | syslog.LOG_CONS)
            if self.verbose:
                syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))
            else:
                syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
        # logging by other modules (eg WxCalculate) does not use WeeImportLog
        # but we can disable most logging by raising the log priority if its a
        # dry run
        if _dry_run:
            syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_CRIT))
        # set the preamble used for each log line
        self.preamble = "".join(patch_config_dict['name'].split())

    def logonly(self, level, message):
        """Log to file only."""

        # are we logging ?
        if self.log:
            # add a little preamble to say this is wee_import
            _message = self.preamble.strip() + ': ' + message
            syslog.syslog(level, _message)

    def printlog(self, level, message):
        """Print to screen and log to file."""

        print message
        self.logonly(level, message)

    def verboselog(self, level, message):
        """Print to screen if --verbose and log to file always."""

        if self.verbose:
            print message
            self.logonly(level, message)