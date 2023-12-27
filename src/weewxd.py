#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Entry point to the weewx weather system."""

import argparse
import locale
import logging
import os
import os.path
import platform
import signal
import sys
import time

import configobj

import weecfg
import weedb
import weeutil.logger
import weeutil.startup
import weewx.engine
from weeutil.weeutil import to_bool, to_float
from weewx import daemon

description = """The main entry point for WeeWX. This program will gather data from your 
station, archive its data, then generate reports."""

usagestr = """%(prog)s --help
       %(prog)s --version
       %(prog)s [FILENAME|--config=FILENAME]
                 [--daemon]
                 [--pidfile=PIDFILE]
                 [--exit]
                 [--loop-on-init]
                 [--log-label=LABEL]
"""

epilog = "Specify either the positional argument FILENAME, " \
         "or the optional argument using --config, but not both."


# ===============================================================================
#                       Main entry point
# ===============================================================================

def main():
    parser = argparse.ArgumentParser(description=description, usage=usagestr, epilog=epilog)
    parser.add_argument("--config", dest="config_option", metavar="FILENAME",
                        help="Use configuration file FILENAME")
    parser.add_argument("-d", "--daemon", action="store_true", dest="daemon",
                        help="Run as a daemon")
    parser.add_argument("-p", "--pidfile", dest="pidfile", metavar="PIDFILE",
                        default="/var/run/weewx.pid",
                        help="Store the process ID in PIDFILE")
    parser.add_argument("-v", "--version", action="store_true", dest="version",
                        help="Display version number then exit")
    parser.add_argument("-x", "--exit", action="store_true", dest="exit",
                        help="Exit on I/O and database errors instead of restarting")
    parser.add_argument("-r", "--loop-on-init", action="store_true", dest="loop_on_init",
                        help="Retry forever if device is not ready on startup")
    parser.add_argument("-n", "--log-label", dest="log_label", metavar="LABEL", default="weewxd",
                        help="Label to use in syslog entries")
    parser.add_argument("config_arg", nargs='?', metavar="FILENAME")

    # Get the command line options and arguments:
    namespace = parser.parse_args()

    if namespace.version:
        print(weewx.__version__)
        sys.exit(0)

    # User can specify the config file as either a positional argument, or as
    # an option argument, but not both.
    if namespace.config_option and namespace.config_arg:
        print(epilog, file=sys.stderr)
        sys.exit(weewx.CMD_ERROR)

    # Read the configuration file
    try:
        config_path, config_dict = weecfg.read_config(namespace.config_arg,
                                                      [namespace.config_option])
    except (IOError, configobj.ConfigObjError) as e:
        print(f"Error parsing config file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(weewx.CONFIG_ERROR)

    # Customize the logging with user settings.
    try:
        weeutil.logger.setup(namespace.log_label, config_dict)
    except Exception as e:
        print(f"Unable to set up logger: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(weewx.CONFIG_ERROR)

    # Get a logger. This one will have the requested configuration.
    log = logging.getLogger(__name__)
    # Announce the startup
    log.info("Initializing weewxd version %s", weewx.__version__)
    log.info("Command line: %s", ' '.join(sys.argv))

    # Set up debug, add USER_ROOT to PYTHONPATH, read user.extensions:
    weewx_root, user_dir = weeutil.startup.initialize(config_dict)

    # Log key bits of information.
    log.info("Using Python %s", sys.version)
    log.info("Located at %s", sys.executable)
    log.info("Platform %s", platform.platform())
    log.info("Locale: '%s'", locale.setlocale(locale.LC_ALL))
    log.info("Entry path: %s", __file__)
    log.info("Configuration file: %s", config_path)
    log.info("WEEWX_ROOT: %s", weewx_root)
    log.info("User directory: %s", user_dir)
    log.info("Debug: %s", weewx.debug)

    # If no command line --loop-on-init was specified, look in the config file.
    if namespace.loop_on_init is None:
        loop_on_init = to_bool(config_dict.get('loop_on_init', False))
    else:
        loop_on_init = namespace.loop_on_init

    # Save the current working directory. A service might
    # change it. In case of a restart, we need to change it back.
    cwd = os.getcwd()

    # Make sure the system time is not out of date (a common problem with the Raspberry Pi).
    # Do this by making sure the system time is later than the creation time of this file.
    sane = os.stat(__file__).st_ctime
    n = 0
    while weewx.launchtime_ts < sane:
        # Log any problems every minute.
        if n % 10 == 0:
            log.info("Waiting for sane time. File time is %s; current time is %s",
                     weeutil.weeutil.timestamp_to_string(sane),
                     weeutil.weeutil.timestamp_to_string(weewx.launchtime_ts))
        n += 1
        time.sleep(0.5)
        weewx.launchtime_ts = time.time()

    # Set up a handler for a termination signal
    signal.signal(signal.SIGTERM, sigTERMhandler)

    if namespace.daemon:
        log.info("PID file is %s", namespace.pidfile)
        daemon.daemonize(pidfile=namespace.pidfile)

    # Main restart loop
    while True:

        os.chdir(cwd)

        try:
            log.debug("Initializing engine")

            # Create and initialize the engine
            engine = weewx.engine.StdEngine(config_dict)

            log.info("Starting up weewx version %s", weewx.__version__)

            # Start the engine. It should run forever unless an exception
            # occurs. Log it if the function returns.
            engine.run()
            log.critical("Unexpected exit from main loop. Program exiting.")

        # Catch any console initialization error:
        except weewx.engine.InitializationError as e:
            # Log it:
            log.critical("Unable to load driver: %s", e)
            # See if we should loop, waiting for the console to be ready.
            # Otherwise, just exit.
            if loop_on_init:
                wait_time = to_float(config_dict.get('retry_wait', 60.0))
                log.critical(f"    ****  Waiting {wait_time:.1f} seconds then retrying...")
                time.sleep(wait_time)
                log.info("retrying...")
            else:
                log.critical("    ****  Exiting...")
                sys.exit(weewx.IO_ERROR)

        # Catch any recoverable weewx I/O errors:
        except weewx.WeeWxIOError as e:
            # Caught an I/O error. Log it, wait 60 seconds, then try again
            log.critical("Caught WeeWxIOError: %s", e)
            if namespace.exit:
                log.critical("    ****  Exiting...")
                sys.exit(weewx.IO_ERROR)
            wait_time = to_float(config_dict.get('retry_wait', 60.0))
            log.critical(f"    ****  Waiting {wait_time:.1f} seconds then retrying...")
            time.sleep(wait_time)
            log.info("retrying...")

        # Catch any database connection errors:
        except (weedb.CannotConnectError, weedb.DisconnectError) as e:
            # No connection to the database server. Log it, wait 60 seconds, then try again
            log.critical("Database connection exception: %s", e)
            if namespace.exit:
                log.critical("    ****  Exiting...")
                sys.exit(weewx.DB_ERROR)
            log.critical("    ****  Waiting 60 seconds then retrying...")
            time.sleep(60)
            log.info("retrying...")

        except weedb.OperationalError as e:
            # Caught a database error. Log it, wait 120 seconds, then try again
            log.critical("Database OperationalError exception: %s", e)
            if namespace.exit:
                log.critical("    ****  Exiting...")
                sys.exit(weewx.DB_ERROR)
            log.critical("    ****  Waiting 2 minutes then retrying...")
            time.sleep(120)
            log.info("retrying...")

        except OSError as e:
            # Caught an OS error. Log it, wait 10 seconds, then try again
            log.critical("Caught OSError: %s", e)
            weeutil.logger.log_traceback(log.critical, "    ****  ")
            log.critical("    ****  Waiting 10 seconds then retrying...")
            time.sleep(10)
            log.info("retrying...")

        except Terminate:
            log.info("Terminating weewx version %s", weewx.__version__)
            weeutil.logger.log_traceback(log.debug, "    ****  ")
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            os.kill(0, signal.SIGTERM)

        # Catch any keyboard interrupts and log them
        except KeyboardInterrupt:
            log.critical("Keyboard interrupt.")
            # Reraise the exception (this should cause the program to exit)
            raise

        # Catch any non-recoverable errors. Log them, exit
        except Exception as ex:
            # Caught unrecoverable error. Log it, exit
            log.critical("Caught unrecoverable exception:")
            log.critical("    ****  %s" % ex)
            # Include a stack traceback in the log:
            weeutil.logger.log_traceback(log.critical, "    ****  ")
            log.critical("    ****  Exiting.")
            # Reraise the exception (this should cause the program to exit)
            raise


# ==============================================================================
#                       Signal handlers
# ==============================================================================

class Terminate(Exception):
    """Exception raised when terminating the engine."""


def sigTERMhandler(signum, _frame):
    log = logging.getLogger(__name__)
    log.info("Received signal TERM (%s).", signum)
    raise Terminate


if __name__ == "__main__":
    # Start up the program
    main()
