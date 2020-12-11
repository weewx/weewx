#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your rights.
#
"""A very small wview schema."""

# =============================================================================
# This is a very severely restricted schema that includes only the basics. It
# is useful for testing, and for very small installations. Like other WeeWX
# schemas, it is used only for initialization --- afterwards, the schema is obtained
# dynamically from the database.  Although a type may be listed here, it may
# not necessarily be supported by your weather station hardware.
# =============================================================================
# NB: This schema is specified using the WeeWX V4 "new-style" schema.
# =============================================================================
table = [('dateTime',             'INTEGER NOT NULL UNIQUE PRIMARY KEY'),
         ('usUnits',              'INTEGER NOT NULL'),
         ('interval',             'INTEGER NOT NULL'),
         ('altimeter',            'REAL'),
         ('barometer',            'REAL'),
         ('dewpoint',             'REAL'),
         ('ET',                   'REAL'),
         ('heatindex',            'REAL'),
         ('inHumidity',           'REAL'),
         ('inTemp',               'REAL'),
         ('outHumidity',          'REAL'),
         ('outTemp',              'REAL'),
         ('pressure',             'REAL'),
         ('radiation',            'REAL'),
         ('rain',                 'REAL'),
         ('rainRate',             'REAL'),
         ('rxCheckPercent',       'REAL'),
         ('UV',                   'REAL'),
         ('windchill',            'REAL'),
         ('windDir',              'REAL'),
         ('windGust',             'REAL'),
         ('windGustDir',          'REAL'),
         ('windSpeed',            'REAL'),
         ]

day_summaries = [(e[0], 'scalar') for e in table
                 if e[0] not in ('dateTime', 'usUnits', 'interval')] + [('wind', 'VECTOR')]

schema = {
    'table': table,
    'day_summaries' : day_summaries
}
