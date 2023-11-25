#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Actions related to running and managing reports"""

import logging
import socket
import time

import weecfg
import weectllib
import weeutil.logger
import weewx
import weewx.engine
import weewx.manager
import weewx.reportengine
import weewx.station
from weeutil.weeutil import bcolors, timestamp_to_string, to_bool

log = logging.getLogger(__name__)


def list_reports(config_path):
    # Read the configuration file
    config_path, config_dict = weecfg.read_config(config_path)
    print(f"Using configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC}")

    # Customize the logging with user settings.
    weeutil.logger.setup('weectl', config_dict)

    print(
        f"\n{bcolors.BOLD}{'Report' : >20}  {'Skin':<12} {'Enabled':^8} {'Units':^8} {'Language':^8}{bcolors.ENDC}")
    for report in config_dict['StdReport'].sections:
        if report == 'Defaults':
            continue
        enabled = to_bool(config_dict['StdReport'][report].get('enable', True))
        # Fetch and build the skin_dict:
        try:
            skin_dict = weewx.reportengine.build_skin_dict(config_dict, report)
        except SyntaxError as e:
            unit_system = "N/A"
            lang = "N/A"
            skin = "N/A"
        else:
            unit_system = skin_dict["unit_system"].upper()
            lang = skin_dict["lang"].upper()
            skin = skin_dict['skin']

        print(f"{report : >20}  {skin:<12} {'Y' if enabled else 'N':^8} "
              f"{unit_system:^8} {lang:^8}")


def run_reports(config_path,
                epoch=None,
                report_date=None, report_time=None):
    # If the user specified a time, retrieve it. Otherwise, set to None
    if epoch:
        gen_ts = int(epoch)
    elif report_date:
        gen_ts = get_epoch_time(report_date, report_time)
    else:
        gen_ts = None

    if gen_ts:
        print(f"Generating for requested time {timestamp_to_string(gen_ts)}")
    else:
        print("Generating as of last timestamp in the database.")

    # Read the configuration file
    config_path, config_dict = weecfg.read_config(config_path)
    print(f"The configuration file {bcolors.BOLD}{config_path}{bcolors.ENDC} will be used.")

    weewx.initialize(config_dict, 'weectl')

    # We want to generate all reports irrespective of any report_timing settings that may exist.
    # The easiest way to do this is walk the config dict, resetting any report_timing settings
    # found.
    config_dict.walk(disable_timing)

    socket.setdefaulttimeout(10)

    # Instantiate the dummy engine. This will cause services to get loaded, which will make
    # the type extensions (xtypes) system available.
    engine = weewx.engine.DummyEngine(config_dict)

    stn_info = weewx.station.StationInfo(**config_dict['Station'])

    try:
        binding = config_dict['StdArchive']['data_binding']
    except KeyError:
        binding = 'wx_binding'

    # Retrieve the appropriate record from the database
    with weewx.manager.DBBinder(config_dict) as db_binder:
        db_manager = db_binder.get_manager(binding)
        ts = gen_ts or db_manager.lastGoodStamp()
        record = db_manager.getRecord(ts)

    # Instantiate the report engine with the retrieved record and required timestamp
    t = weewx.reportengine.StdReportEngine(config_dict, stn_info, record=record, gen_ts=ts)

    # Although the report engine inherits from Thread, we can just run it in the main thread:
    t.run()

    # Shut down any running services,
    engine.shutDown()


def get_epoch_time(d_tt, t_tt):
    tt = (d_tt.tm_year, d_tt.tm_mon, d_tt.tm_mday,
          t_tt.tm_hour, t_tt.tm_min, 0, 0, 0, -1)
    return time.mktime(tt)


def disable_timing(section, key):
    """Function to effectively disable report_timing option"""
    if key == 'report_timing':
        section['report_timing'] = "* * * * *"
