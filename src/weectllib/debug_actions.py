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
import weedb
import weeutil.config
import weeutil.printer
import weewx
import weewx.manager
import weewx.units
import weewx.xtypes
from weeutil.weeutil import timestamp_to_string, TimeSpan, bcolors

# keys/setting names to obfuscate in weewx.conf, key value will be obfuscated
# if the key starts any element in the list. Can add additional string elements
# to list if required
OBFUSCATE_MAP = {
    "obfuscate": [
        "apiKey", "api_key", "app_key", "archive_security_key", "id", "key",
        "oauth_token", "password", "raw_security_key", "token", "user",
        "server_url", "station", "passcode", "server"],
    "do_not_obfuscate": [
        "station_type"]
}


def debug(config_dict, output=None):
    """Generate information about the user's WeeWX environment

    Args:
        config_dict (dict): Configuration dictionary.
        output (str|None): Path to where the output will be put. Default is stdout.
    """

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
        generate_extension_info(config_dict['config_path'], config_dict, fd)
        # info about the archive database
        generate_archive_info(config_dict, fd)
        # generate our obfuscated weewx.conf
        generate_debug_conf(config_dict['config_path'], config_dict, fd)


def generate_sys_info(fd):
    """Generate general information about the system

    Args:
        fd (typing.TextIO): An open file-like object.
    """

    print("\nSystem info", file=fd)

    print(f"  Platform:       {platform.platform()}", file=fd)
    print(f"  Python Version: {platform.python_version()}", file=fd)

    # load info
    try:
        loadavg = '%.2f %.2f %.2f' % os.getloadavg()
        (load1, load5, load15) = loadavg.split(" ")

        print("\nLoad Information", file=fd)
        print(f"   1 minute load average:  {load1:8}", file=fd)
        print(f"   5 minute load average:  {load5:8}", file=fd)
        print(f"  15 minute load average:  {load15:8}", file=fd)
    except OSError:
        print("  The load average is not available on this platform.", file=fd)


def generate_weewx_info(fd):
    """Generate information about WeeWX, such as the version.

    Args:
        fd (typing.TextIO): An open file-like object.
    """
    # weewx version info
    print("\nGeneral Weewx info", file=fd)
    print(f"  Weewx version {weewx.__version__} detected.", file=fd)


def generate_extension_info(config_path, config_dict, fd):
    """Generate information about any installed extensions

    Args:
        config_path(str): The path toe the configuration dictionary
        config_dict(dict): The configuration dictionary.
        fd (typing.TextIO): An open file-like object.
    """
    # installed extensions info
    print("\nCurrently installed extensions", file=fd)
    ext = weecfg.extension.ExtensionEngine(config_path=config_path,
                                           config_dict=config_dict,
                                           printer=weeutil.printer.Printer(fd=fd))
    ext.enumerate_extensions()


def generate_archive_info(config_dict, fd):
    """Information about the archive database

    Args:
        config_dict(dict): The configuration dictionary.
        fd (typing.TextIO): An open file-like object.
    """
    # weewx archive info
    print("\nArchive info", file=fd)

    try:
        manager_info_dict = get_manager_info(config_dict)
    except weedb.CannotConnect as e:
        print("  Unable to connect to database:", e, file=fd)
    except weedb.OperationalError as e:
        print("  Error hitting database. It may not be properly initialized:", file=fd)
        print(f"  {e}", file=fd)
    else:
        units_nickname = weewx.units.unit_nicknames.get(manager_info_dict['units'],
                                                        "Unknown unit constant")
        print(f"  Database name:        {manager_info_dict['db_name']}", file=fd)
        print(f"  Table name:           {manager_info_dict['table_name']}", file=fd)
        print(f"  Version               {manager_info_dict['version']}", file=fd)
        print(f"  Unit system:          {manager_info_dict['units']} ({units_nickname})", file=fd)
        print(f"  First good timestamp: {timestamp_to_string(manager_info_dict['first_ts'])}",
              file=fd)
        print(f"  Last good timestamp:  {timestamp_to_string(manager_info_dict['last_ts'])}",
              file=fd)
        if manager_info_dict['ts_count']:
            print(f"  Number of records:    {manager_info_dict['ts_count']}", file=fd)
        else:
            print("  (no archive records found)", file=fd)
        # if we have a database and a table but no start or stop ts and no records
        # inform the user that the database/table exists but appears empty
        if (manager_info_dict['db_name'] and manager_info_dict['table_name']) \
                and not (manager_info_dict['ts_count']
                         or manager_info_dict['units']
                         or manager_info_dict['first_ts']
                         or manager_info_dict['last_ts']):
            print(f"                        It is likely that the database "
                  f"({manager_info_dict['db_name']}) "
                  f"archive table ({manager_info_dict['table_name']})",
                  file=fd)
            print("                        exists but contains no data.", file=fd)
        print(f"  weewx (weewx.conf) is set to use an archive interval of "
              f"{config_dict['StdArchive']['archive_interval']} seconds.", file=fd)
        print("  The station hardware was not interrogated to determine the archive interval.",
              file=fd)

        # sqlkeys/obskeys info
        print("\nSupported SQL keys", file=fd)
        format_list_cols(manager_info_dict['sqlkeys'], 3, fd)


    # weewx database info
    print("\nDatabases configured in weewx.conf:", file=fd)
    for db_keys in config_dict['Databases']:
        database_dict = weewx.manager.get_database_dict_from_config(config_dict,
                                                                    db_keys)
        print(f"  {db_keys}:", file=fd)
        for k in database_dict:
            print(f"{k:>18s} {database_dict[k]:<20s}", file=fd)

def generate_debug_conf(config_path, config_dict, fd):
    """Generate a parsed and obfuscated weewx.conf and write to the open file descriptor 'fd'.

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

    print(f"\n--- Start configuration file {config_path} ---", file=fd)

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
    """Obfuscate any dictionary items whose key is contained in passed list.

    Args:
        src_dict (dict): The configuration dictionary to be obfuscated.
        obfuscate_list (list): A list of keys that should be obfuscated.
        retain_list(list): A list of keys that should not be obfuscated.
    """

    # We need a function to be passed on to the 'walk()' function.
    def obfuscate_value(section, key):
        # Check to see if the key is in the obfuscation list. If so, then obfuscate it.
        if any(key.startswith(k) for k in obfuscate_list) and key not in retain_list:
            section[key] = "XXXXXX"

    # Now walk the configuration dictionary, using the function
    src_dict.walk(obfuscate_value)


def get_manager_info(config_dict):
    """Get info from the manager of a weewx archive for inclusion in debug report.

    Args:
        config_dict(dict): The configuration dictionary
    """

    db_binding_wx = get_binding(config_dict)
    with weewx.manager.open_manager_with_config(config_dict, db_binding_wx) as dbmanager_wx:
        info = {
            'db_name': dbmanager_wx.database_name,
            'table_name': dbmanager_wx.table_name,
            'version': getattr(dbmanager_wx, 'version', 'unknown'),
            'units': dbmanager_wx.std_unit_system,
            'first_ts': dbmanager_wx.first_timestamp,
            'last_ts': dbmanager_wx.last_timestamp,
            'sqlkeys': dbmanager_wx.sqlkeys,
        }
        # do we have any records in our archive?
        if info['first_ts'] and info['last_ts']:
            # We have some records so count them.
            result = dbmanager_wx.getSql(f"SELECT COUNT(*) FROM {dbmanager_wx.table_name};")
            info['ts_count'] = result[0]
        else:
            info['ts_count'] = None
    return info


def get_binding(config_dict):
    """Get the data binding used by the weewx database.

    Args:
        config_dict (dict): The configuration dictionary.

    Returns:
        str: The binding used by the StdArchive database. Default is 'wx_binding'
    """

    # Extract our binding from the StdArchive section of the config file. If
    # it's missing, return 'wx_binding'.
    if 'StdArchive' in config_dict:
        db_binding_wx = config_dict['StdArchive'].get('data_binding', 'wx_binding')
    else:
        db_binding_wx = 'wx_binding'

    return db_binding_wx


def format_list_cols(the_list, cols, fd):
    """Format a list of strings into a given number of columns, respecting the
    width of the largest list entry

    Args:
        the_list (list): A list of strings
        cols (int): The number of columns to be used.
        fd (typing.TextIO): An open file-like object.
    """

    max_width = max([len(x) for x in the_list])
    justifyList = [x.ljust(max_width) for x in the_list]
    lines = (' '.join(justifyList[i:i + cols])
             for i in range(0, len(justifyList), cols))
    for line in lines:
        print(" ", line, file=fd)
