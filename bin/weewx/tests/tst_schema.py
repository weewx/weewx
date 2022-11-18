#
#      Copyright (c) 2019-2022 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#
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
         ('sunshineDur',          'REAL'),
         ('UV',                   'REAL'),
         ('windchill',            'REAL'),
         ('windDir',              'REAL'),
         ('windGust',             'REAL'),
         ('windGustDir',          'REAL'),
         ('windSpeed',            'REAL'),
         ('stringData',           'VARCHAR(30)')
         ]

day_types = [e[0] for e in table if e[0] not in {'dateTime', 'usUnits', 'interval', 'stringData'}]
day_summaries = [(day_type, 'scalar') for day_type in day_types] + [('wind', 'VECTOR')]

schema = {
    'table': table,
    'day_summaries' : day_summaries
}
