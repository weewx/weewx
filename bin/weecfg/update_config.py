# coding: utf-8
#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""Utilities that update and merge ConfigObj objects"""

import os.path
import sys

import weecfg

import weeutil.config


def update_and_merge(config_dict, template_dict):
    """First update a configuration file, then merge it with the distribution template"""

    update_config(config_dict)
    merge_config(config_dict, template_dict)


def update_config(config_dict):
    """Update a (possibly old) configuration dictionary to the latest format.

    Raises exception of type ValueError if it cannot be done.
    """

    major, minor = weecfg.get_version_info(config_dict)

    # I don't know how to merge older, V1.X configuration files, only
    # newer V2.X ones.
    if major == '1':
        raise ValueError("Cannot update version V%s.%s. Too old" % (major, minor))

    update_to_v25(config_dict)

    update_to_v26(config_dict)

    update_to_v30(config_dict)

    update_to_v32(config_dict)

    update_to_v36(config_dict)

    update_to_v39(config_dict)

    update_to_v40(config_dict)

    update_to_v42(config_dict)

    update_to_v43(config_dict)


def merge_config(config_dict, template_dict):
    """Merge the template (distribution) dictionary into the user's dictionary.

    config_dict: An existing, older configuration dictionary.

    template_dict: A newer dictionary supplied by the installer.
    """

    # All we need to do is update the version number:
    config_dict['version'] = template_dict['version']


def update_to_v25(config_dict):
    """Major changes for V2.5:

    - Option webpath is now station_url
    - Drivers are now in their own package
    - Introduction of the station registry

    """
    major, minor = weecfg.get_version_info(config_dict)

    if major + minor >= '205':
        return

    try:
        # webpath is now station_url
        webpath = config_dict['Station'].get('webpath')
        station_url = config_dict['Station'].get('station_url')
        if webpath is not None and station_url is None:
            config_dict['Station']['station_url'] = webpath
        config_dict['Station'].pop('webpath', None)
    except KeyError:
        pass

    # Drivers are now in their own Python package. Change the names.

    # --- Davis Vantage series ---
    try:
        if config_dict['Vantage']['driver'].strip() == 'weewx.VantagePro':
            config_dict['Vantage']['driver'] = 'weewx.drivers.vantage'
    except KeyError:
        pass

    # --- Oregon Scientific WMR100 ---

    # The section name has changed from WMR-USB to WMR100
    if 'WMR-USB' in config_dict:
        if 'WMR100' in config_dict:
            sys.exit("\n*** Configuration file has both a 'WMR-USB' "
                     "section and a 'WMR100' section. Aborting ***\n\n")
        config_dict.rename('WMR-USB', 'WMR100')
    # If necessary, reflect the section name in the station type:
    try:
        if config_dict['Station']['station_type'].strip() == 'WMR-USB':
            config_dict['Station']['station_type'] = 'WMR100'
    except KeyError:
        pass
    # Finally, the name of the driver has been changed
    try:
        if config_dict['WMR100']['driver'].strip() == 'weewx.wmrx':
            config_dict['WMR100']['driver'] = 'weewx.drivers.wmr100'
    except KeyError:
        pass

    # --- Oregon Scientific WMR9x8 series ---

    # The section name has changed from WMR-918 to WMR9x8
    if 'WMR-918' in config_dict:
        if 'WMR9x8' in config_dict:
            sys.exit("\n*** Configuration file has both a 'WMR-918' "
                     "section and a 'WMR9x8' section. Aborting ***\n\n")
        config_dict.rename('WMR-918', 'WMR9x8')
    # If necessary, reflect the section name in the station type:
    try:
        if config_dict['Station']['station_type'].strip() == 'WMR-918':
            config_dict['Station']['station_type'] = 'WMR9x8'
    except KeyError:
        pass
    # Finally, the name of the driver has been changed
    try:
        if config_dict['WMR9x8']['driver'].strip() == 'weewx.WMR918':
            config_dict['WMR9x8']['driver'] = 'weewx.drivers.wmr9x8'
    except KeyError:
        pass

    # --- Fine Offset instruments ---

    try:
        if config_dict['FineOffsetUSB']['driver'].strip() == 'weewx.fousb':
            config_dict['FineOffsetUSB']['driver'] = 'weewx.drivers.fousb'
    except KeyError:
        pass

    # --- The weewx Simulator ---

    try:
        if config_dict['Simulator']['driver'].strip() == 'weewx.simulator':
            config_dict['Simulator']['driver'] = 'weewx.drivers.simulator'
    except KeyError:
        pass

    if 'StdArchive' in config_dict:
        # Option stats_types is no longer used. Get rid of it.
        config_dict['StdArchive'].pop('stats_types', None)

    try:
        # V2.5 saw the introduction of the station registry:
        if 'StationRegistry' not in config_dict['StdRESTful']:
            stnreg_dict = weeutil.config.config_from_str("""[StdRESTful]

        [[StationRegistry]]
            # Uncomment the following line to register this weather station.
            #register_this_station = True

            # Specify a station URL, otherwise the station_url from [Station]
            # will be used.
            #station_url = http://example.com/weather/

            # Specify a description of the station, otherwise the location from
            # [Station] will be used.
            #description = The greatest station on earth

            driver = weewx.restful.StationRegistry

    """)
            config_dict.merge(stnreg_dict)
    except KeyError:
        pass

    config_dict['version'] = '2.5.0'


def update_to_v26(config_dict):
    """Update a configuration diction to V2.6.

    Major changes:

    - Addition of "model" option for WMR100, WMR200, and WMR9x8
    - New option METRICWX
    - Engine service list now broken up into separate sublists
    - Introduction of 'log_success' and 'log_failure' options
    - Introduction of rapidfire
    - Support of uploaders for WOW and AWEKAS
    - CWOP option 'interval' changed to 'post_interval'
    - CWOP option 'server' changed to 'server_list' (and is not in default weewx.conf)
    """

    major, minor = weecfg.get_version_info(config_dict)

    if major + minor >= '206':
        return

    try:
        if 'model' not in config_dict['WMR100']:
            config_dict['WMR100']['model'] = 'WMR100'
            config_dict['WMR100'].comments['model'] = \
                ["", "    # The station model, e.g., WMR100, WMR100N, WMRS200"]
    except KeyError:
        pass

    try:
        if 'model' not in config_dict['WMR200']:
            config_dict['WMR200']['model'] = 'WMR200'
            config_dict['WMR200'].comments['model'] = \
                ["", "    # The station model, e.g., WMR200, WMR200A, Radio Shack W200"]
    except KeyError:
        pass

    try:
        if 'model' not in config_dict['WMR9x8']:
            config_dict['WMR9x8']['model'] = 'WMR968'
            config_dict['WMR9x8'].comments['model'] = \
                ["", "    # The station model, e.g., WMR918, Radio Shack 63-1016"]
    except KeyError:
        pass

    # Option METRICWX was introduced. Include it in the inline comment
    try:
        config_dict['StdConvert'].inline_comments[
            'target_unit'] = "# Options are 'US', 'METRICWX', or 'METRIC'"
    except KeyError:
        pass

    # New default values for inHumidity, rain, and windSpeed Quality Controls
    try:
        if 'inHumidity' not in config_dict['StdQC']['MinMax']:
            config_dict['StdQC']['MinMax']['inHumidity'] = [0, 100]
        if 'rain' not in config_dict['StdQC']['MinMax']:
            config_dict['StdQC']['MinMax']['rain'] = [0, 60, "inch"]
        if 'windSpeed' not in config_dict['StdQC']['MinMax']:
            config_dict['StdQC']['MinMax']['windSpeed'] = [0, 120, "mile_per_hour"]
        if 'inTemp' not in config_dict['StdQC']['MinMax']:
            config_dict['StdQC']['MinMax']['inTemp'] = [10, 20, "degree_F"]
    except KeyError:
        pass

    service_map_v2 = {'weewx.wxengine.StdTimeSynch': 'prep_services',
                      'weewx.wxengine.StdConvert': 'process_services',
                      'weewx.wxengine.StdCalibrate': 'process_services',
                      'weewx.wxengine.StdQC': 'process_services',
                      'weewx.wxengine.StdArchive': 'archive_services',
                      'weewx.wxengine.StdPrint': 'report_services',
                      'weewx.wxengine.StdReport': 'report_services'}

    # See if the engine configuration section has the old-style "service_list":
    if 'Engines' in config_dict and 'service_list' in config_dict['Engines']['WxEngine']:
        # It does. Break it up into five, smaller lists. If a service
        # does not appear in the dictionary "service_map_v2", meaning we
        # do not know what it is, then stick it in the last group we
        # have seen. This should get its position about right.
        last_group = 'prep_services'

        # Set up a bunch of empty groups in the right order. Option 'data_services' was actually introduced
        # in v3.0, but it can be included without harm here.
        for group in ['prep_services', 'data_services', 'process_services', 'archive_services',
                      'restful_services', 'report_services']:
            config_dict['Engines']['WxEngine'][group] = list()

        # Add a helpful comment
        config_dict['Engines']['WxEngine'].comments['prep_services'] = \
            ['', ' # The list of services the main weewx engine should run:']

        # Now map the old service names to the right group
        for _svc_name in config_dict['Engines']['WxEngine']['service_list']:
            svc_name = _svc_name.strip()
            # Skip the no longer needed StdRESTful service:
            if svc_name == 'weewx.wxengine.StdRESTful':
                continue
            # Do we know about this service?
            if svc_name in service_map_v2:
                # Yes. Get which group it belongs to, and put it there
                group = service_map_v2[svc_name]
                config_dict['Engines']['WxEngine'][group].append(svc_name)
                last_group = group
            else:
                # No. Put it in the last group.
                config_dict['Engines']['WxEngine'][last_group].append(svc_name)

        # Now add the restful services, using the old driver name to help us
        for section in config_dict['StdRESTful'].sections:
            svc = config_dict['StdRESTful'][section]['driver']
            # weewx.restful has changed to weewx.restx
            if svc.startswith('weewx.restful'):
                svc = 'weewx.restx.Std' + section
            # awekas is in weewx.restx since 2.6
            if svc.endswith('AWEKAS'):
                svc = 'weewx.restx.AWEKAS'
            config_dict['Engines']['WxEngine']['restful_services'].append(svc)

        # Depending on how old a version the user has, the station registry
        # may have to be included:
        if 'weewx.restx.StdStationRegistry' not in config_dict['Engines']['WxEngine'][
            'restful_services']:
            config_dict['Engines']['WxEngine']['restful_services'].append(
                'weewx.restx.StdStationRegistry')

        # Get rid of the no longer needed service_list:
        config_dict['Engines']['WxEngine'].pop('service_list', None)

    # V2.6 introduced "log_success" and "log_failure" options.
    # The "driver" option was removed.
    for section in config_dict['StdRESTful']:
        # Save comments before popping driver
        comments = config_dict['StdRESTful'][section].comments.get('driver', [])
        if 'log_success' not in config_dict['StdRESTful'][section]:
            config_dict['StdRESTful'][section]['log_success'] = True
        if 'log_failure' not in config_dict['StdRESTful'][section]:
            config_dict['StdRESTful'][section]['log_failure'] = True
        config_dict['StdRESTful'][section].comments['log_success'] = comments
        config_dict['StdRESTful'][section].pop('driver', None)

    # Option 'rapidfire' was new:
    try:
        if 'rapidfire' not in config_dict['StdRESTful']['Wunderground']:
            config_dict['StdRESTful']['Wunderground']['rapidfire'] = False
            config_dict['StdRESTful']['Wunderground'].comments['rapidfire'] = \
                ['',
                 '        # Set the following to True to have weewx use the WU "Rapidfire"',
                 '        # protocol']
    except KeyError:
        pass

    # Support for the WOW uploader was introduced
    try:
        if 'WOW' not in config_dict['StdRESTful']:
            config_dict.merge(weeutil.config.config_from_str("""[StdRESTful]

            [[WOW]]
                # This section is for configuring posts to WOW

                # If you wish to do this, uncomment the following station and password
                # lines and fill them with your station and password:
                #station = your WOW station ID
                #password = your WOW password

                log_success = True
                log_failure = True

        """))
            config_dict['StdRESTful'].comments['WOW'] = ['']
    except KeyError:
        pass

    # Support for the AWEKAS uploader was introduced
    try:
        if 'AWEKAS' not in config_dict['StdRESTful']:
            config_dict.merge(weeutil.config.config_from_str("""[StdRESTful]

            [[AWEKAS]]
                # This section is for configuring posts to AWEKAS

                # If you wish to do this, uncomment the following username and password
                # lines and fill them with your username and password:
                #username = your AWEKAS username
                #password = your AWEKAS password

                log_success = True
                log_failure = True

        """))
            config_dict['StdRESTful'].comments['AWEKAS'] = ['']
    except KeyError:
        pass

    # The CWOP option "interval" has changed to "post_interval"
    try:
        if 'interval' in config_dict['StdRESTful']['CWOP']:
            comment = config_dict['StdRESTful']['CWOP'].comments['interval']
            config_dict['StdRESTful']['CWOP']['post_interval'] = \
                config_dict['StdRESTful']['CWOP']['interval']
            config_dict['StdRESTful']['CWOP'].pop('interval')
            config_dict['StdRESTful']['CWOP'].comments['post_interval'] = comment
    except KeyError:
        pass

    try:
        if 'server' in config_dict['StdRESTful']['CWOP']:
            # Save the old comments, as they are useful for setting up CWOP
            comments = [c for c in config_dict['StdRESTful']['CWOP'].comments.get('server') if
                        'Comma' not in c]
            # Option "server" has become "server_list". It is also no longer
            # included in the default weewx.conf, so just pop it.
            config_dict['StdRESTful']['CWOP'].pop('server', None)
            # Put the saved comments in front of the first scalar.
            key = config_dict['StdRESTful']['CWOP'].scalars[0]
            config_dict['StdRESTful']['CWOP'].comments[key] = comments
    except KeyError:
        pass

    config_dict['version'] = '2.6.0'


def update_to_v30(config_dict):
    """Update a configuration file to V3.0

     - Introduction of the new database structure
     - Introduction of StdWXCalculate
    """

    major, minor = weecfg.get_version_info(config_dict)

    if major + minor >= '300':
        return

    old_database = None

    if 'StdReport' in config_dict:
        # The key "data_binding" is now used instead of these:
        config_dict['StdReport'].pop('archive_database', None)
        config_dict['StdReport'].pop('stats_database', None)
        if 'data_binding' not in config_dict['StdReport']:
            config_dict['StdReport']['data_binding'] = 'wx_binding'
            config_dict['StdReport'].comments['data_binding'] = \
                ['', "    # The database binding indicates which data should be used in reports"]

    if 'Databases' in config_dict:
        # The stats database no longer exists. Remove it from the [Databases]
        # section:
        config_dict['Databases'].pop('stats_sqlite', None)
        config_dict['Databases'].pop('stats_mysql', None)
        # The key "database" changed to "database_name"
        for stanza in config_dict['Databases']:
            if 'database' in config_dict['Databases'][stanza]:
                config_dict['Databases'][stanza].rename('database',
                                                        'database_name')

    if 'StdArchive' in config_dict:
        # Save the old database, if it exists
        old_database = config_dict['StdArchive'].pop('archive_database', None)
        # Get rid of the no longer needed options
        config_dict['StdArchive'].pop('stats_database', None)
        config_dict['StdArchive'].pop('archive_schema', None)
        config_dict['StdArchive'].pop('stats_schema', None)
        # Add the data_binding option
        if 'data_binding' not in config_dict['StdArchive']:
            config_dict['StdArchive']['data_binding'] = 'wx_binding'
            config_dict['StdArchive'].comments['data_binding'] = \
                ['', "    # The data binding to be used"]

    if 'DataBindings' not in config_dict:
        # Insert a [DataBindings] section. First create it
        c = weeutil.config.config_from_str("""[DataBindings]
            # This section binds a data store to a database

            [[wx_binding]]
                # The database must match one of the sections in [Databases]
                database = archive_sqlite
                # The name of the table within the database
                table_name = archive
                # The manager handles aggregation of data for historical summaries
                manager = weewx.manager.DaySummaryManager
                # The schema defines the structure of the database.
                # It is *only* used when the database is created.
                schema = schemas.wview.schema

        """)
        # Now merge it in:
        config_dict.merge(c)
        # For some reason, ConfigObj strips any leading comments. Put them back:
        config_dict.comments['DataBindings'] = weecfg.major_comment_block
        # Move the new section to just before [Databases]
        weecfg.reorder_sections(config_dict, 'DataBindings', 'Databases')
        # No comments between the [DataBindings] and [Databases] sections:
        config_dict.comments['Databases'] = [""]
        config_dict.inline_comments['Databases'] = []

        # If there was an old database, add it in the new, correct spot:
        if old_database:
            try:
                config_dict['DataBindings']['wx_binding']['database'] = old_database
            except KeyError:
                pass

    # StdWXCalculate is new
    if 'StdWXCalculate' not in config_dict:
        c = weeutil.config.config_from_str("""[StdWXCalculate]
    # Derived quantities are calculated by this service.  Possible values are:
    #  hardware        - use the value provided by hardware
    #  software        - use the value calculated by weewx
    #  prefer_hardware - use value provide by hardware if available,
    #                      otherwise use value calculated by weewx

    pressure = prefer_hardware
    barometer = prefer_hardware
    altimeter = prefer_hardware
    windchill = prefer_hardware
    heatindex = prefer_hardware
    dewpoint = prefer_hardware
    inDewpoint = prefer_hardware
    rainRate = prefer_hardware""")
        # Now merge it in:
        config_dict.merge(c)
        # For some reason, ConfigObj strips any leading comments. Put them back:
        config_dict.comments['StdWXCalculate'] = weecfg.major_comment_block
        # Move the new section to just before [StdArchive]
        weecfg.reorder_sections(config_dict, 'StdWXCalculate', 'StdArchive')

    # Section ['Engines'] got renamed to ['Engine']
    if 'Engine' not in config_dict and 'Engines' in config_dict:
        config_dict.rename('Engines', 'Engine')
        # Subsection [['WxEngine']] got renamed to [['Services']]
        if 'WxEngine' in config_dict['Engine']:
            config_dict['Engine'].rename('WxEngine', 'Services')

            # Finally, module "wxengine" got renamed to "engine". Go through
            # each of the service lists, making the change
            for list_name in config_dict['Engine']['Services']:
                service_list = config_dict['Engine']['Services'][list_name]
                # If service_list is not already a list (it could be just a
                # single name), then make it a list:
                if not isinstance(service_list, (tuple, list)):
                    service_list = [service_list]
                config_dict['Engine']['Services'][list_name] = \
                    [this_item.replace('wxengine', 'engine') for this_item in service_list]
        try:
            # Finally, make sure the new StdWXCalculate service is in the list:
            if 'weewx.wxservices.StdWXCalculate' not in config_dict['Engine']['Services'][
                'process_services']:
                config_dict['Engine']['Services']['process_services'].append(
                    'weewx.wxservices.StdWXCalculate')
        except KeyError:
            pass

    config_dict['version'] = '3.0.0'


def update_to_v32(config_dict):
    """Update a configuration file to V3.2

    - Introduction of section [DatabaseTypes]
    - New option in [Databases] points to DatabaseType
    """

    major, minor = weecfg.get_version_info(config_dict)

    if major + minor >= '302':
        return

    # For interpolation to work, it's critical that WEEWX_ROOT not end
    # with a trailing slash ('/'). Convert it to the normative form:
    config_dict['WEEWX_ROOT'] = os.path.normpath(config_dict['WEEWX_ROOT'])

    # Add a default database-specific top-level stanzas if necessary
    if 'DatabaseTypes' not in config_dict:
        # Do SQLite first. Start with a sanity check:
        try:
            assert (config_dict['Databases']['archive_sqlite']['driver'] == 'weedb.sqlite')
        except KeyError:
            pass
        # Set the default [[SQLite]] section. Turn off interpolation first, so the
        # symbol for WEEWX_ROOT does not get lost.
        save, config_dict.interpolation = config_dict.interpolation, False
        # The section must be built step by step so we get the order of the entries correct
        config_dict['DatabaseTypes'] = {}
        config_dict['DatabaseTypes']['SQLite'] = {}
        config_dict['DatabaseTypes']['SQLite']['driver'] = 'weedb.sqlite'
        config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] = '%(WEEWX_ROOT)s/archive'
        config_dict['DatabaseTypes'].comments['SQLite'] = \
            ['', '    # Defaults for SQLite databases']
        config_dict['DatabaseTypes']['SQLite'].comments['SQLITE_ROOT'] \
            = "        # Directory in which the database files are located"
        config_dict.interpolation = save
        try:
            root = config_dict['Databases']['archive_sqlite']['root']
            database_name = config_dict['Databases']['archive_sqlite']['database_name']
            fullpath = os.path.join(root, database_name)
            dirname = os.path.dirname(fullpath)
            # By testing to see if they end up resolving to the same thing,
            # we can keep the interpolation used to specify SQLITE_ROOT above.
            if dirname != config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT']:
                config_dict['DatabaseTypes']['SQLite']['SQLITE_ROOT'] = dirname
            config_dict['DatabaseTypes']['SQLite'].comments['SQLITE_ROOT'] = \
                ['        # Directory in which the database files are located']
            config_dict['Databases']['archive_sqlite']['database_name'] = os.path.basename(
                fullpath)
            config_dict['Databases']['archive_sqlite']['database_type'] = 'SQLite'
            config_dict['Databases']['archive_sqlite'].pop('root', None)
            config_dict['Databases']['archive_sqlite'].pop('driver', None)
        except KeyError:
            pass

        # Now do MySQL. Start with a sanity check:
        try:
            assert (config_dict['Databases']['archive_mysql']['driver'] == 'weedb.mysql')
        except KeyError:
            pass
        config_dict['DatabaseTypes']['MySQL'] = {}
        config_dict['DatabaseTypes'].comments['MySQL'] = ['', '    # Defaults for MySQL databases']
        try:
            config_dict['DatabaseTypes']['MySQL']['host'] = \
                config_dict['Databases']['archive_mysql'].get('host', 'localhost')
            config_dict['DatabaseTypes']['MySQL']['user'] = \
                config_dict['Databases']['archive_mysql'].get('user', 'weewx')
            config_dict['DatabaseTypes']['MySQL']['password'] = \
                config_dict['Databases']['archive_mysql'].get('password', 'weewx')
            config_dict['DatabaseTypes']['MySQL']['driver'] = 'weedb.mysql'
            config_dict['DatabaseTypes']['MySQL'].comments['host'] = [
                "        # The host where the database is located"]
            config_dict['DatabaseTypes']['MySQL'].comments['user'] = [
                "        # The user name for logging into the host"]
            config_dict['DatabaseTypes']['MySQL'].comments['password'] = [
                "        # The password for the user name"]
            config_dict['Databases']['archive_mysql'].pop('host', None)
            config_dict['Databases']['archive_mysql'].pop('user', None)
            config_dict['Databases']['archive_mysql'].pop('password', None)
            config_dict['Databases']['archive_mysql'].pop('driver', None)
            config_dict['Databases']['archive_mysql']['database_type'] = 'MySQL'
            config_dict['Databases'].comments['archive_mysql'] = ['']
        except KeyError:
            pass

        # Move the new section to just before [Engine]
        weecfg.reorder_sections(config_dict, 'DatabaseTypes', 'Engine')
        # Add a major comment deliminator:
        config_dict.comments['DatabaseTypes'] = \
            weecfg.major_comment_block + \
            ['#   This section defines defaults for the different types of databases', '']

    # Version 3.2 introduces the 'enable' keyword for RESTful protocols. Set
    # it appropriately
    def set_enable(c, service, keyword):
        # Check to see whether this config file has the service listed
        try:
            c['StdRESTful'][service]
        except KeyError:
            # It does not. Nothing to do.
            return

        # Now check to see whether it already has the option 'enable':
        if 'enable' in c['StdRESTful'][service]:
            # It does. No need to proceed
            return

        # The option 'enable' is not present. Add it,
        # and set based on whether the keyword is present:
        if keyword in c['StdRESTful'][service]:
            c['StdRESTful'][service]['enable'] = 'true'
        else:
            c['StdRESTful'][service]['enable'] = 'false'
        # Add a comment for it
        c['StdRESTful'][service].comments['enable'] = ['',
                                                       '    # Set to true to enable this uploader']

    set_enable(config_dict, 'AWEKAS', 'username')
    set_enable(config_dict, 'CWOP', 'station')
    set_enable(config_dict, 'PWSweather', 'station')
    set_enable(config_dict, 'WOW', 'station')
    set_enable(config_dict, 'Wunderground', 'station')

    config_dict['version'] = '3.2.0'


def update_to_v36(config_dict):
    """Update a configuration file to V3.6

    - New subsection [[Calculations]]
    """

    major, minor = weecfg.get_version_info(config_dict)

    if major + minor >= '306':
        return

    # Perform the following only if the dictionary has a StdWXCalculate section
    if 'StdWXCalculate' in config_dict:
        # No need to update if it already has a 'Calculations' section:
        if 'Calculations' not in config_dict['StdWXCalculate']:
            # Save the comment attached to the first scalar
            try:
                first = config_dict['StdWXCalculate'].scalars[0]
                comment = config_dict['StdWXCalculate'].comments[first]
                config_dict['StdWXCalculate'].comments[first] = ''
            except IndexError:
                comment = """    # Derived quantities are calculated by this service. Possible values are:
    #  hardware        - use the value provided by hardware
    #  software        - use the value calculated by weewx
    #  prefer_hardware - use value provide by hardware if available,
    #                      otherwise use value calculated by weewx"""
            # Create a new 'Calculations' section:
            config_dict['StdWXCalculate']['Calculations'] = {}
            # Now transfer over the options. Make a copy of them first: we will be
            # deleting some of them.
            scalars = list(config_dict['StdWXCalculate'].scalars)
            for scalar in scalars:
                # These scalars don't get moved:
                if not scalar in ['ignore_zero_wind', 'rain_period',
                                  'et_period', 'wind_height', 'atc',
                                  'nfac', 'max_delta_12h']:
                    config_dict['StdWXCalculate']['Calculations'][scalar] = \
                    config_dict['StdWXCalculate'][scalar]
                    config_dict['StdWXCalculate'].pop(scalar)
            # Insert the old comment at the top of the new stanza:
            try:
                first = config_dict['StdWXCalculate']['Calculations'].scalars[0]
                config_dict['StdWXCalculate']['Calculations'].comments[first] = comment
            except IndexError:
                pass

    config_dict['version'] = '3.6.0'


def update_to_v39(config_dict):
    """Update a configuration file to V3.9

    - New top-level options log_success and log_failure
    - New subsections [[SeasonsReport]], [[SmartphoneReport]], and [[MobileReport]]
    - New section [StdReport][[Defaults]]. Prior to V4.6, it had lots of entries. With the
      introduction of V4.6, it has been pared back to the minimum.
    """

    major, minor = weecfg.get_version_info(config_dict)

    if major + minor >= '309':
        return

    # Add top-level log_success and log_failure if missing
    if 'log_success' not in config_dict:
        config_dict['log_success'] = True
        config_dict.comments['log_success'] = ['', '# Whether to log successful operations']
        weecfg.reorder_scalars(config_dict.scalars, 'log_success', 'socket_timeout')
    if 'log_failure' not in config_dict:
        config_dict['log_failure'] = True
        config_dict.comments['log_failure'] = ['', '# Whether to log unsuccessful operations']
        weecfg.reorder_scalars(config_dict.scalars, 'log_failure', 'socket_timeout')

    if 'StdReport' in config_dict:

        #
        # The logic below will put the subsections in the following order:
        #
        #   [[StandardReport]]
        #   [[SeasonsReport]]
        #   [[SmartphoneReport]]
        #   [[MobileReport]]
        #   [[FTP]]
        #   [[RSYNC]
        #   [[Defaults]]
        #
        #  NB: For an upgrade, we want StandardReport first, because that's
        #  what the user is already using.
        #

        # Work around a ConfigObj limitation that can cause comments to be dropped.
        # Save the original comment, then restore it later.
        std_report_comment = config_dict.comments['StdReport']

        if 'Defaults' not in config_dict['StdReport']:
            defaults_dict = weeutil.config.config_from_str(DEFAULTS)
            weeutil.config.merge_config(config_dict, defaults_dict)
            weecfg.reorder_sections(config_dict['StdReport'], 'Defaults', 'RSYNC', after=True)

        if 'SeasonsReport' not in config_dict['StdReport']:
            seasons_options_dict = weeutil.config.config_from_str(SEASONS_REPORT)
            weeutil.config.merge_config(config_dict, seasons_options_dict)
            weecfg.reorder_sections(config_dict['StdReport'], 'SeasonsReport', 'FTP')

        if 'SmartphoneReport' not in config_dict['StdReport']:
            smartphone_options_dict = weeutil.config.config_from_str(SMARTPHONE_REPORT)
            weeutil.config.merge_config(config_dict, smartphone_options_dict)
            weecfg.reorder_sections(config_dict['StdReport'], 'SmartphoneReport', 'FTP')

        if 'MobileReport' not in config_dict['StdReport']:
            mobile_options_dict = weeutil.config.config_from_str(MOBILE_REPORT)
            weeutil.config.merge_config(config_dict, mobile_options_dict)
            weecfg.reorder_sections(config_dict['StdReport'], 'MobileReport', 'FTP')

        if 'StandardReport' in config_dict['StdReport'] \
                and 'enable' not in config_dict['StdReport']['StandardReport']:
            config_dict['StdReport']['StandardReport']['enable'] = True

    # Put the comment for [StdReport] back in
    config_dict.comments['StdReport'] = std_report_comment

    # Remove all comments before each report section
    for report in config_dict['StdReport'].sections:
        if report == 'Defaults':
            continue
        config_dict['StdReport'].comments[report] = ['']

    # Special comment for the first report section:
    first_section_name = config_dict['StdReport'].sections[0]
    config_dict['StdReport'].comments[first_section_name] \
        = ['',
           '####',
           '',
           '# Each of the following subsections defines a report that will be run.',
           '# See the customizing guide to change the units, plot types and line',
           '# colors, modify the fonts, display additional sensor data, and other',
           '# customizations. Many of those changes can be made here by overriding',
           '# parameters, or by modifying templates within the skin itself.',
           ''
           ]

    config_dict['version'] = '3.9.0'


def update_to_v40(config_dict):
    """Update a configuration file to V4.0

    - Add option loop_request for Vantage users.
    - Fix problems with DegreeDays and Trend in weewx.conf
    - Add new option growing_base
    - Add new option WU api_key
    - Add options to [StdWXCalculate] that were formerly defaults
    """

    # No need to check for the version of weewx for these changes.

    if 'Vantage' in config_dict \
            and 'loop_request' not in config_dict['Vantage']:
        config_dict['Vantage']['loop_request'] = 1
        config_dict['Vantage'].comments['loop_request'] = \
            ['', 'The type of LOOP packet to request: 1 = LOOP1; 2 = LOOP2; 3 = both']
        weecfg.reorder_scalars(config_dict['Vantage'].scalars, 'loop_request', 'iss_id')

    if 'StdReport' in config_dict \
            and 'Defaults' in config_dict['StdReport'] \
            and 'Units' in config_dict['StdReport']['Defaults']:

        # Both the DegreeDays and Trend subsections accidentally ended up
        # in the wrong section
        for key in ['DegreeDays', 'Trend']:

            # Proceed only if the key has not already been moved, and exists in the incorrect spot:
            if key not in config_dict['StdReport']['Defaults']['Units'] \
                    and 'Ordinates' in config_dict['StdReport']['Defaults']['Units'] \
                    and key in config_dict['StdReport']['Defaults']['Units']['Ordinates']:
                # Save the old comment
                old_comment = config_dict['StdReport']['Defaults']['Units']['Ordinates'].comments[
                    key]

                # Shallow copy the sub-section
                config_dict['StdReport']['Defaults']['Units'][key] = \
                    config_dict['StdReport']['Defaults']['Units']['Ordinates'][key]
                # Delete it in from its old location
                del config_dict['StdReport']['Defaults']['Units']['Ordinates'][key]

                # Unfortunately, ConfigObj can't fix these things when doing a shallow copy:
                config_dict['StdReport']['Defaults']['Units'][key].depth = \
                    config_dict['StdReport']['Defaults']['Units'].depth + 1
                config_dict['StdReport']['Defaults']['Units'][key].parent = \
                    config_dict['StdReport']['Defaults']['Units']
                config_dict['StdReport']['Defaults']['Units'].comments[key] = old_comment

    # Now add the option "growing_base" if it hasn't already been added:
    if 'StdReport' in config_dict \
            and 'Defaults' in config_dict['StdReport'] \
            and 'Units' in config_dict['StdReport']['Defaults'] \
            and 'DegreeDays' in config_dict['StdReport']['Defaults']['Units'] \
            and 'growing_base' not in config_dict['StdReport']['Defaults']['Units']['DegreeDays']:
        config_dict['StdReport']['Defaults']['Units']['DegreeDays']['growing_base'] = [50.0,
                                                                                       'degree_F']
        config_dict['StdReport']['Defaults']['Units']['DegreeDays'].comments['growing_base'] = \
            ["Base temperature for growing days, with unit:"]

    # Add the WU API key if it hasn't already been added
    if 'StdRESTful' in config_dict \
            and 'Wunderground' in config_dict['StdRESTful'] \
            and 'api_key' not in config_dict['StdRESTful']['Wunderground']:
        config_dict['StdRESTful']['Wunderground']['api_key'] = 'replace_me'
        config_dict['StdRESTful']['Wunderground'].comments['api_key'] = \
            ["", "If you plan on using wunderfixer, set the following", "to your API key:"]

    # The following types were never listed in weewx.conf and, instead, depended on defaults.
    if 'StdWXCalculate' in config_dict \
            and 'Calculations' in config_dict['StdWXCalculate']:
        config_dict['StdWXCalculate']['Calculations'].setdefault('maxSolarRad', 'prefer_hardware')
        config_dict['StdWXCalculate']['Calculations'].setdefault('cloudbase', 'prefer_hardware')
        config_dict['StdWXCalculate']['Calculations'].setdefault('humidex', 'prefer_hardware')
        config_dict['StdWXCalculate']['Calculations'].setdefault('appTemp', 'prefer_hardware')
        config_dict['StdWXCalculate']['Calculations'].setdefault('ET', 'prefer_hardware')
        config_dict['StdWXCalculate']['Calculations'].setdefault('windrun', 'prefer_hardware')

    # This section will inject a [Logging] section. Leave it commented out for now,
    # until we gain more experience with it.

    # if 'Logging' not in config_dict:
    #     logging_dict = configobj.ConfigObj(StringIO(weeutil.logger.LOGGING_STR), interpolation=False)
    #
    #     # Delete some not needed (and dangerous) entries
    #     try:
    #         del logging_dict['Logging']['version']
    #         del logging_dict['Logging']['disable_existing_loggers']
    #     except KeyError:
    #         pass
    #
    #     config_dict.merge(logging_dict)
    #
    #     # Move the new section to just before [Engine]
    #     reorder_sections(config_dict, 'Logging', 'Engine')
    #     config_dict.comments['Logging'] = \
    #         major_comment_block + \
    #         ['#   This section customizes logging', '']

    # Make sure the version number is at least 4.0
    major, minor = weecfg.get_version_info(config_dict)

    if major + minor < '400':
        config_dict['version'] = '4.0.0'


def update_to_v42(config_dict):
    """Update a configuration file to V4.2

    - Add new engine service group xtype_services
    """

    if 'Engine' in config_dict and 'Services' in config_dict['Engine']:
        # If it's not there already, inject 'xtype_services'
        if 'xtype_services' not in config_dict['Engine']['Services']:
            config_dict['Engine']['Services']['xtype_services'] = \
                ['weewx.wxxtypes.StdWXXTypes',
                 'weewx.wxxtypes.StdPressureCooker',
                 'weewx.wxxtypes.StdRainRater',
                 'weewx.wxxtypes.StdDelta']

        # V4.2.0 neglected to include StdDelta. If necessary, add it:
        if 'weewx.wxxtypes.StdDelta' not in config_dict['Engine']['Services']['xtype_services']:
            config_dict['Engine']['Services']['xtype_services'].append('weewx.wxxtypes.StdDelta')

        # Make sure xtype_services are located just before the 'archive_services'
        weecfg.reorder_scalars(config_dict['Engine']['Services'].scalars,
                               'xtype_services',
                               'archive_services')
        config_dict['Engine']['Services'].comments['prep_services'] = []
        config_dict['Engine']['Services'].comments['xtype_services'] = []
        config_dict['Engine'].comments['Services'] = ['The following section specifies which '
                                                      'services should be run and in what order.']
    config_dict['version'] = '4.2.0'


def update_to_v43(config_dict):
    """Update a configuration file to V4.3

    - Set [StdReport] / log_failure to True
    """
    if 'StdReport' in config_dict and 'log_failure' in config_dict['StdReport']:
        config_dict['StdReport']['log_failure'] = True

    config_dict['version'] = '4.3.0'


# ==============================================================================
#            Various config sections
# ==============================================================================


SEASONS_REPORT = """[StdReport]

    [[SeasonsReport]]
        # The SeasonsReport uses the 'Seasons' skin, which contains the
        # images, templates and plots for the report.
        skin = Seasons
        enable = false"""

SMARTPHONE_REPORT = """[StdReport]

    [[SmartphoneReport]]
        # The SmartphoneReport uses the 'Smartphone' skin, and the images and
        # files are placed in a dedicated subdirectory.
        skin = Smartphone
        enable = false
        HTML_ROOT = public_html/smartphone"""

MOBILE_REPORT = """[StdReport]

    [[MobileReport]]
        # The MobileReport uses the 'Mobile' skin, and the images and files
        # are placed in a dedicated subdirectory.
        skin = Mobile
        enable = false
        HTML_ROOT = public_html/mobile"""

DEFAULTS = """[StdReport]

    ####

    # Options in the [[Defaults]] section below will apply to all reports.
    # What follows are a few of the more popular options you may want to
    # uncomment, then change.
    [[Defaults]]

        # Which language to use for all reports. Not all skins support all languages.
        # You can override this for individual reports.
        lang = en

        # Which unit system to use for all reports. Choices are 'us', 'metric', or 'metricwx'.
        # You can override this for individual reports.
        unit_system = us

        [[[Units]]]
            # Option "unit_system" above sets the general unit system, but overriding specific unit
            # groups is possible. These are popular choices. Uncomment and set as appropriate.
            # NB: The unit is always in the singular. I.e., 'mile_per_hour',
            # NOT 'miles_per_hour'
            [[[[Groups]]]]
                # group_altitude     = meter              # Options are 'foot' or 'meter'
                # group_pressure     = mbar               # Options are 'inHg', 'mmHg', 'mbar', or 'hPa'
                # group_rain         = mm                 # Options are 'inch', 'cm', or 'mm'
                # group_rainrate     = mm_per_hour        # Options are 'inch_per_hour', 'cm_per_hour', or 'mm_per_hour'
                # The following line is used to keep the above lines indented properly.
                # It can be ignored.
                unused = unused

            # Uncommenting the following section frequently results in more
            # attractive formatting of times and dates, but may not work in
            # your locale.
            [[[[TimeFormats]]]]
                # day        = %H:%M
                # week       = %H:%M on %A
                # month      = %d-%b-%Y %H:%M
                # year       = %d-%b-%Y %H:%M
                # rainyear   = %d-%b-%Y %H:%M
                # current    = %d-%b-%Y %H:%M
                # ephem_day  = %H:%M
                # ephem_year = %d-%b-%Y %H:%M
                # The following line is used to keep the above lines indented properly.
                # It can be ignored.
                unused = unused

        [[[Labels]]]
            # Users frequently change the labels for these observation types
            [[[[Generic]]]]
                # inHumidity     = Inside Humidity
                # inTemp         = Inside Temperature
                # outHumidity    = Outside Humidity
                # outTemp        = Outside Temperature
                # extraTemp1     = Temperature1
                # extraTemp2     = Temperature2
                # extraTemp3     = Temperature3
                # The following line is used to keep the above lines indented properly.
                # It can be ignored.
                unused = unused

"""
