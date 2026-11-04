#
#    Copyright (c) 2009-2026 Tom Keffer <tkeffer@gmail.com>
#    Copyright (c) 2026 Manuel Hilgert <hilman2@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test tag notation for template generation.

Use pytest to run the tests.
"""

import locale
import logging
import os
import os.path
import shutil
import sys
import time

import pytest

import parameters
import weeutil.config
import weeutil.logger
import weeutil.weeutil
import weewx
import weewx.accum
import weewx.manager
import weewx.reportengine
import weewx.station
import weewx.units
import weewx.wxxtypes
import weewx.xtypes

# Do not delete the following line. The module is used by an underlying xtype
import misc

weewx.debug = 1

log = logging.getLogger(__name__)

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()

@pytest.fixture(autouse=True)
def isolate_locale():
    """Explicitly set LANG and LC_ALL to US locale for template tests, restoring afterwards."""
    orig_lc = locale.setlocale(locale.LC_ALL)
    orig_lang = os.environ.get('LANG')
    try:
        os.environ['LANG'] = "en_US.UTF-8"
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except locale.Error:
            pass
        yield
    finally:
        if orig_lang is not None:
            os.environ['LANG'] = orig_lang
        else:
            os.environ.pop('LANG', None)
        try:
            locale.setlocale(locale.LC_ALL, orig_lc)
        except locale.Error:
            locale.setlocale(locale.LC_ALL, 'C')

# The expected results of the German report hold the abbreviations used by glibc. The C library
# on macOS uses different ones. For example, it writes "Nov." for "Nov", "Juni" for "Jun", and
# "Mo." for "Mo". The fixture `german_abbreviations` supplies glibc's spelling
# on every platform.
GERMAN_ABBREVIATED_MONTHS = ('Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
                             'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez')
GERMAN_ABBREVIATED_DAYS = ('Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So')


@pytest.fixture(autouse=True)
def german_abbreviations(monkeypatch):
    """Expand %b and %a from the tables above whenever the German locale is active."""
    original_strftime = time.strftime

    def strftime(format_string, time_tuple=None):
        if time_tuple is None:
            time_tuple = time.localtime()
        # The report engine changes the locale from report to report, so check on every call.
        if locale.getlocale(locale.LC_TIME)[0] == 'de_DE':
            month_name = GERMAN_ABBREVIATED_MONTHS[time_tuple[1] - 1]
            day_name = GERMAN_ABBREVIATED_DAYS[time_tuple[6]]
            format_string = format_string.replace('%b', month_name).replace('%a', day_name)
        return original_strftime(format_string, time_tuple)

    monkeypatch.setattr(time, 'strftime', strftime)

# These tests also test the examples in the 'example' subdirectory.
# Patch PYTHONPATH to find them.
import weewx_data

example_dir = os.path.normpath(os.path.join(os.path.dirname(weewx_data.__file__),
                                            './examples'))
sys.path.append(os.path.join(example_dir, './colorize'))
sys.path.append(os.path.join(example_dir, './xstats/bin/user'))

import colorize_1
import colorize_2
import colorize_3

# Monkey patch to create SLEs with unambiguous names. We will test using these names.
colorize_1.Colorize.colorize_1 = colorize_1.Colorize.colorize
colorize_2.Colorize.colorize_2 = colorize_2.Colorize.colorize
colorize_3.Colorize.colorize_3 = colorize_3.Colorize.colorize


# We will be testing the ability to extend the unit system, so set that up first:
class ExtraUnits:
    def __getitem__(self, obs_type):
        if obs_type.endswith('Temp'):
            # Anything that ends with "Temp" is assumed to be in group_temperature
            return "group_temperature"
        elif obs_type.startswith('current'):
            # Anything that starts with "current" is in group_amperage:
            return "group_amperage"
        else:
            raise KeyError(obs_type)

    def __contains__(self, obs_type):
        return obs_type.endswith('Temp') or obs_type.startswith('current')


extra_units = ExtraUnits()
weewx.units.obs_group_dict.extend(extra_units)

# Add the new group group_amperage to the standard unit systems:
weewx.units.USUnits["group_amperage"] = "amp"
weewx.units.MetricUnits["group_amperage"] = "amp"
weewx.units.MetricWXUnits["group_amperage"] = "amp"

weewx.units.default_unit_format_dict["amp"] = "%.1f"
weewx.units.default_unit_label_dict["amp"] = " A"


def test_report_engine(config_dict):
    stn_info, testtime_ts = prepare_report_engine(config_dict)

    # First run the engine without a current record.
    run_engine(config_dict, stn_info, None, testtime_ts)

    # Now run the engine again, but this time with a current record:
    with weewx.manager.open_manager_with_config(config_dict, 'wx_binding') as manager:
        record = manager.getRecord(testtime_ts)
    run_engine(config_dict, stn_info, record, testtime_ts)


def test_noaa_wide_month_abbreviation(config_dict, monkeypatch):
    """A four character month abbreviation must not shift the columns of a yearly NOAA report."""
    # The real abbreviation depends on the locale and the C library, so force a wide one.
    original_strftime = time.strftime

    def strftime(format_string, *args):
        return original_strftime(format_string.replace('%b', 'Juli'), *args)

    monkeypatch.setattr(time, 'strftime', strftime)

    stn_info, testtime_ts = prepare_report_engine(config_dict)
    test_html_dir = generate_reports(config_dict, stn_info, None, testtime_ts)

    filename_rel = os.path.join('StandardTest', 'NOAA', 'NOAA-2010.txt')
    with open(os.path.join(test_html_dir, filename_rel), 'r') as actual:
        actual_lines = actual.readlines()
    with open(os.path.join(os.path.dirname(__file__), 'expected', filename_rel), 'r') as expected:
        expected_lines = expected.readlines()
    # Only the month names differ from the expected results, so the widths must all match.
    assert 'Juli' in ''.join(actual_lines)
    assert [len(line) for line in actual_lines] == [len(line) for line in expected_lines]


def prepare_report_engine(config_dict):
    """Remove any old results and initialize what the report engine depends on.

    Args:
        config_dict (dict): The configuration dictionary.

    Returns:
        tuple[weewx.station.StationInfo, int]: A two-way tuple (stn_info, testtime_ts).
    """
    # Set up logging:
    weeutil.logger.setup('weetest_templates', config_dict)
    # Remove the old directory:
    try:
        test_html_dir = os.path.join(config_dict['WEEWX_ROOT'],
                                     config_dict['StdReport']['HTML_ROOT'])
        shutil.rmtree(test_html_dir)
    except OSError as e:
        if os.path.exists(test_html_dir):
            print("\nUnable to remove old test directory %s", test_html_dir, file=sys.stderr)
            print("Reason:", e, file=sys.stderr)
            print("Aborting", file=sys.stderr)
            exit(1)

    altitude_vt = weewx.units.ValueTuple(float(config_dict['Station']['altitude'][0]),
                                         config_dict['Station']['altitude'][1],
                                         'group_altitude')
    latitude = float(config_dict['Station']['latitude'])
    longitude = float(config_dict['Station']['longitude'])
    # Initialize the xtypes system for derived weather types:
    weewx.xtypes.xtypes.append(weewx.wxxtypes.WXXTypes(altitude_vt, latitude, longitude))

    # We test accumulator configurations as well, so initialize the Accumulator dictionary:
    weewx.accum.initialize(config_dict)

    # The generation time should be the same as the last record in the test database:
    testtime_ts = parameters.synthetic_dict['stop_ts']
    print("\ntest time is %s" % weeutil.weeutil.timestamp_to_string(testtime_ts))

    stn_info = weewx.station.StationInfo(**config_dict['Station'])
    return stn_info, testtime_ts


def generate_reports(config_dict, stn_info, record, testtime_ts):
    """Run the test skins through the report engine.

    Args:
        config_dict (dict): The configuration dictionary.
        stn_info (weewx.station.StationInfo): The station information.
        record (dict|None): The current record, if any.
        testtime_ts (int): The time of the reports.

    Returns:
        str: The directory that holds the generated files.
    """
    t = weewx.reportengine.StdReportEngine(config_dict, stn_info, record, testtime_ts)

    # Find the test skins and then have SKIN_ROOT in the report engine point to it:
    test_dir = os.path.dirname(__file__)
    t.config_dict['StdReport']['SKIN_ROOT'] = os.path.join(test_dir, 'test_skins')

    # Although the report engine inherits from Thread, we can just run it in the main thread:
    print("Starting report engine test")
    t.run()
    print("Done.")

    return os.path.join(t.config_dict['WEEWX_ROOT'], t.config_dict['StdReport']['HTML_ROOT'])


def run_engine(config_dict, stn_info, record, testtime_ts):
    test_html_dir = generate_reports(config_dict, stn_info, record, testtime_ts)
    expected_dir = os.path.join(os.path.dirname(__file__), 'expected')

    # Walk the directory of expected results to discover all the generated files we should
    # be checking
    for dirpath, _, dirfilenames in os.walk(expected_dir):
        for dirfilename in dirfilenames:
            expected_filename_abs = os.path.join(dirpath, dirfilename)
            # Get the file path relative to the directory of expected results
            filename_rel = os.path.relpath(expected_filename_abs, expected_dir)
            # Use that to figure out where the actual results ended up
            actual_filename_abs = os.path.join(test_html_dir, filename_rel)

            # Read in the actual lines...
            with open(actual_filename_abs, 'r') as actual:
                actual_lines = actual.readlines()
            # ... then the expected lines...
            with open(expected_filename_abs, 'r') as expected:
                expected_lines = expected.readlines()
            # ... then compare them.
            assert actual_lines == expected_lines, \
                f"File mismatch: {actual_filename_abs} vs {expected_filename_abs}"
