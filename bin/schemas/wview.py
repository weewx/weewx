#
#    Copyright (c) 2009-2015 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""The wview schema, which is also used by weewx."""

# =============================================================================
# This is a list containing the default schema of the archive database.  It is
# identical to what is used by wview. It is only used for initialization ---
# afterwards, the schema is obtained dynamically from the database.  Although a
# type may be listed here, it may not necessarily be supported by your weather
# station hardware.
#
# You may trim this list of any unused types if you wish, but it will not
# result in saving as much space as you may think --- most of the space is
# taken up by the primary key indexes (type "dateTime").
# =============================================================================
schema = [('dateTime',             'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
          ('usUnits',              'INTEGER NOT NULL'),
          ('interval',             'INTEGER NOT NULL'),
          ('barometer',            'REAL'),
          ('pressure',             'REAL'),
          ('altimeter',            'REAL'),
          ('inTemp',               'REAL'),
          ('outTemp',              'REAL'),
          ('inHumidity',           'REAL'),
          ('outHumidity',          'REAL'),
          ('windSpeed',            'REAL'),
          ('windDir',              'REAL'),
          ('windGust',             'REAL'),
          ('windGustDir',          'REAL'),
          ('rainRate',             'REAL'),
          ('rain',                 'REAL'),
          ('dewpoint',             'REAL'),
          ('windchill',            'REAL'),
          ('heatindex',            'REAL'),
          ('ET',                   'REAL'),
          ('radiation',            'REAL'),
          ('UV',                   'REAL'),
          ('extraTemp1',           'REAL'),
          ('extraTemp2',           'REAL'),
          ('extraTemp3',           'REAL'),
          ('soilTemp1',            'REAL'),
          ('soilTemp2',            'REAL'),
          ('soilTemp3',            'REAL'),
          ('soilTemp4',            'REAL'),
          ('leafTemp1',            'REAL'),
          ('leafTemp2',            'REAL'),
          ('extraHumid1',          'REAL'),
          ('extraHumid2',          'REAL'),
          ('soilMoist1',           'REAL'),
          ('soilMoist2',           'REAL'),
          ('soilMoist3',           'REAL'),
          ('soilMoist4',           'REAL'),
          ('leafWet1',             'REAL'),
          ('leafWet2',             'REAL'),
          ('rxCheckPercent',       'REAL'),
          ('txBatteryStatus',      'REAL'),
          ('consBatteryVoltage',   'REAL'),
          ('hail',                 'REAL'),
          ('hailRate',             'REAL'),
          ('heatingTemp',          'REAL'),
          ('heatingVoltage',       'REAL'),
          ('supplyVoltage',        'REAL'),
          ('referenceVoltage',     'REAL'),
          ('windBatteryStatus',    'REAL'),
          ('rainBatteryStatus',    'REAL'),
          ('outTempBatteryStatus', 'REAL'),
          ('inTempBatteryStatus',  'REAL')]
