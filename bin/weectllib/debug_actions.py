#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
"""Debug command actions"""
import contextlib
import os
import platform
import sys
from io import BytesIO

import weecfg
import weecfg.extension
import weectllib
import weedb
import weeutil.config
import weewx
import weewx.manager
from weeutil.weeutil import timestamp_to_string, TimeSpan

# keys/setting names to obfuscate in weewx.conf, key value will be obfuscated
# if the key starts any element in the list. Can add additional string elements
# to list if required
OBFUSCATE_MAP = {
    "obfuscate": [
        "apiKey", "api_key", "app_key", "archive_security_key", "id", "key",
        "oauth_token", "password", "raw_security_key", "token", "user",
        "server_url", "station"],
    "do_not_obfuscate": [
        "station_type"]
}


def debug(config_path, output=None):
    """Generate information about the user's WeeWX environment

    Args:
        config_path (str): Path to the configuration file
        output (str|None): Path to where the output will be put. Default is stdout.
    """
    config_path, config_dict, database_name = weectllib.prepare(config_path,
                                                                'wx_binding',
                                                                dry_run=False)

    if output:
        # If a file path has been specified, then open it up and use the resultant "file-like
        # object" as the file descriptor
        sink = open(output, 'wt')
    else:
        # Otherwise, use stdout. It's already open, so use a null context, so that
        # we don't open it again
        sink = contextlib.nullcontext(sys.stdout)

    with sink as fd:
        # system/OS info
        generate_sys_info(fd)
        # WeeWX info
        generate_weewx_info(fd)
        # info about extensions
        generate_extension_info(config_path, config_dict, fd)
        # info about the archive database
        generate_archive_info(config_dict, fd)
        # generate our obfuscated weewx.conf
        generate_debug_conf(config_path, config_dict, fd)


def generate_sys_info(fd):
    """
    Generate general information about the system
    Args:
        fd (typing.TextIO): An open file-like object.
    """

    print("\nSystem info", file=fd)

    print("  Platform:       " + platform.platform(), file=fd)
    print("  Python Version: " + platform.python_version(), file=fd)

    # load info
    try:
        loadavg = '%.2f %.2f %.2f' % os.getloadavg()
        (load1, load5, load15) = loadavg.split(" ")

        print("\nLoad Information", file=fd)
        print(f"   1 minute load average:  {load1:8}", file=fd)
        print(f"   5 minute load average:  {load5:8}", file=fd)
        print(f"  15 minute load average:  {load15:8}", file=fd)
    except OSError:
        print("Sorry, the load average not available on this platform", file=fd)


def generate_weewx_info(fd):
    """
    Generate information about WeeWX, such as the version.
    Args:
        fd (typing.TextIO): An open file-like object.
    """
    # weewx version info
    print("\nGeneral Weewx info", file=fd)
    print(f"  Weewx version {weewx.__version__} detected.", file=fd)


def generate_extension_info(config_path, config_dict, fd):
    """
    Generate information about any installed extensions
    Args:
        config_path(str): The path toe the configuration dictionary
        config_dict(dict): The configuration dictionary.
        fd (typing.TextIO): An open file-like object.
    """
    # installed extensions info
    print("\nCurrently installed extensions", file=fd)
    ext = weecfg.extension.ExtensionEngine(config_path=config_path,
                                           config_dict=config_dict,
                                           logger=weecfg.extension.Logger(fd=fd))
    ext.enumerate_extensions()


def generate_archive_info(config_dict, fd):
    """
    Information about the archive database
    Args:
        config_dict(dict): The configuration dictionary.
        fd (typing.TextIO): An open file-like object.
    """
    # weewx archive info
    print("\nArchive info", file=fd)

    db_binding_wx = get_binding(config_dict)
    try:
        manager_info_dict = get_manager_info(config_dict, db_binding_wx)
    except weedb.CannotConnect as e:
        print("Unable to connect to database:", e, file=fd)
        print()
    except weedb.OperationalError as e:
        print("Error hitting database. It may not be properly initialized:", file=fd)
        print(e, file=fd)
        print(file=fd)
    else:
        units_nickname = weewx.units.unit_nicknames.get(manager_info_dict['units'],
                                                        "Unknown unit constant")
        print("  Database name:        %s" % manager_info_dict['db_name'], file=fd)
        print("  Table name:           %s" % manager_info_dict['table_name'], file=fd)
        print("  Version               %s" % manager_info_dict['version'], file=fd)
        print("  Unit system:          %s (%s)" % (manager_info_dict['units'],
                                                   units_nickname), file=fd)
        print("  First good timestamp: %s" % timestamp_to_string(manager_info_dict['first_ts']),
              file=fd)
        print("  Last good timestamp:  %s" % timestamp_to_string(manager_info_dict['last_ts']),
              file=fd)
        if manager_info_dict['ts_count']:
            print("  Number of records:    %s" % manager_info_dict['ts_count'].value, file=fd)
        else:
            print("  Number of records:    %s (no archive records found)"
                  % manager_info_dict['ts_count'], file=fd)
        # if we have a database and a table but no start or stop ts and no records
        # inform the user that the database/table exists but appears empty
        if (manager_info_dict['db_name'] and manager_info_dict['table_name']) \
                and not (manager_info_dict['ts_count']
                         or manager_info_dict['units']
                         or manager_info_dict['first_ts']
                         or manager_info_dict['last_ts']):
            print("                        It is likely that the database (%s) archive table (%s)"
                  % (manager_info_dict['db_name'], manager_info_dict['table_name']), file=fd)
            print("                        exists but contains no data.", file=fd)
        print("  weewx (weewx.conf) is set to use an archive interval of %s seconds."
              % config_dict['StdArchive']['archive_interval'], file=fd)
        print("  The station hardware was not interrogated to determine the archive interval.",
              file=fd)
        print(file=fd)

    # weewx database info
    print("Databases configured in weewx.conf:", file=fd)
    for db_keys in config_dict['Databases']:
        database_dict = weewx.manager.get_database_dict_from_config(config_dict,
                                                                    db_keys)
        print(f"    {db_keys}:", file=fd)
        for k in database_dict:
            print(f"{k:>20s} {database_dict[k]:<20s}", file=fd)
        print(file=fd)

    # sqlkeys/obskeys info
    print("Supported SQL keys", file=fd)
    format_list_cols(manager_info_dict['sqlkeys'], 3, fd)


def generate_debug_conf(config_path, config_dict, fd):
    """
    Generate a parsed and obfuscated weewx.conf and write to the open file descriptor 'fd'.
    Args:
        config_path(str): The path toe the configuration dictionary
        config_dict(dict): The configuration dictionary.
        fd (typing.TextIO): An open file-like object.
    """

    # Make a deep copy first, as we may be altering values.
    config_dict_copy = weeutil.config.deep_copy(config_dict)

    # Turn off interpolation on the copy, so it doesn't interfere with faithful representation of
    # the values
    config_dict_copy.interpolation = False

    # Now obfuscate any sensitive keys
    obfuscate_dict(config_dict_copy,
                   OBFUSCATE_MAP['obfuscate'],
                   OBFUSCATE_MAP['do_not_obfuscate'])

    print(f"\nConfiguration file {config_path}:", file=fd)

    # put obfuscated config_dict into weewx.conf form.
    with BytesIO() as buf:
        # First write it to a bytes buffer...
        config_dict_copy.write(buf)
        # ... rewind the buffer ...
        buf.seek(0)
        # ... then print it out line, by line, converting to strings as we go. Each line does
        # not need a '\n' because that was already done by the write above.
        for l in buf:
            print(l.decode('utf-8'), file=fd, end='')


def obfuscate_dict(src_dict, obfuscate_list, retain_list):
    """ Obfuscate any dictionary items whose key is contained in passed list. """

    # We need a function to be passed on to the 'walk()' function.
    def obfuscate_value(section, key):
        # Check to see if the key is in the obfuscation list. If so, then obfuscate it.
        if any(key.startswith(k) for k in obfuscate_list) and key not in retain_list:
            section[key] = "XXX obfuscated by wee_debug XXX"

    # Now walk the configuration dictionary, using the function
    src_dict.walk(obfuscate_value)


def get_binding(config_dict):
    """ Get db_binding for the weewx database """

    # Extract our binding from the StdArchive section of the config file. If
    # it's missing, return None.
    if 'StdArchive' in config_dict:
        db_binding_wx = config_dict['StdArchive'].get('data_binding', 'wx_binding')
    else:
        db_binding_wx = None

    return db_binding_wx


def get_manager_info(config_dict, db_binding_wx):
    """ Get info from the manager of a weewx archive for inclusion in debug
        report
    Args:
        config_dict(dict): The configuration dictionary
        db_binding_wx(str): The binding to use.
    """

    with weewx.manager.open_manager_with_config(config_dict, db_binding_wx) as dbmanager_wx:
        info = {
            'db_name': dbmanager_wx.database_name,
            'table_name': dbmanager_wx.table_name,
            'version': getattr(dbmanager_wx, 'version', 'unknown'),
            'units': dbmanager_wx.std_unit_system,
            'first_ts': dbmanager_wx.first_timestamp,
            'last_ts': dbmanager_wx.last_timestamp,
            'sqlkeys': dbmanager_wx.sqlkeys,
            'obskeys': dbmanager_wx.obskeys
        }
        # do we have any records in our archive?
        if info['first_ts'] and info['last_ts']:
            # We have some records so proceed to count them.
            # Since we are (more than likely) using archive field 'dateTime' for
            # our record count we need to call the getAggregate() method from our
            # parent class. Note that if we change to some other field the 'count'
            # might take a while longer depending on the archive size.
            info['ts_count'] = super(weewx.manager.DaySummaryManager, dbmanager_wx).getAggregate(
                TimeSpan(info['first_ts'], info['last_ts']),
                'dateTime',
                'count')
        else:
            info['ts_count'] = None
    return info


def format_list_cols(the_list, cols, fd):
    """ Format a list of strings into a given number of columns respecting the
        width of the largest list entry
    """

    max_width = max([len(x) for x in the_list])
    justifyList = [x.ljust(max_width) for x in the_list]
    lines = (' '.join(justifyList[i:i + cols])
             for i in range(0, len(justifyList), cols))
    for line in lines:
        print(" ", line, file=fd)
