# $Id$
# installer for the forecast extension
# Copyright 2014 Matthew Wall

from setup import ExtensionInstaller

def loader():
    return ForecastInstaller()

class ForecastInstaller(ExtensionInstaller):
    def __init__(self):
        super(ForecastInstaller, self).__init__(
            version="0.3",
            name='forecast',
            description='Generate and display weather and tide forecasts.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            process_services=['user.forecast.ZambrettiForecast',
                              'user.forecast.WUForecast'],
            config={
                'Forecast': {
                    'database': 'forecast_sqlite',
                    'XTide': {
                        'location': 'Boston'},
                    'Zambretti': {
                        'hemisphere': 'NORTH'},
                    'NWS': {
                        'lid': 'MAZ014',
                        'foid': 'BOX'},
                    'WU': {
                        'api_key': 'INSERT_WU_API_KEY_HERE'}},
                'Databases': {
                    'forecast_sqlite': {
                        'database': 'forecast.sdb',
                        'driver': 'weedb.sqlite'}},
                'StdReport': {
                    'forecast': {
                        'skin':'forecast',
                        'HTML_ROOT':'forecast',
                        'Extras': {
                            'forecast_table':'%(WEEWX_ROOT)s%(SKIN_ROOT)s/forecast/forecast_table.inc'}}}},
            files=[('bin/user',
                    ['bin/user/forecast.py']),
                   ('skins/forecast',
                    ['skins/forecast/skin.conf',
                     'skins/forecast/forecast.inc',
                     'skins/forecast/index.html.tmpl']),
                   ('skins/forecast/icons',
                    ['skins/forecast/icons/AF.png',
                     'skins/forecast/icons/B1.png',
                     'skins/forecast/icons/B1n.png',
                     'skins/forecast/icons/B2.png',
                     'skins/forecast/icons/B2n.png',
                     'skins/forecast/icons/BD.png',
                     'skins/forecast/icons/BK.png',
                     'skins/forecast/icons/BKn.png',
                     'skins/forecast/icons/BS.png',
                     'skins/forecast/icons/CL.png',
                     'skins/forecast/icons/CLn.png',
                     'skins/forecast/icons/E.png',
                     'skins/forecast/icons/F+.png',
                     'skins/forecast/icons/F.png',
                     'skins/forecast/icons/FW.png',
                     'skins/forecast/icons/FWn.png',
                     'skins/forecast/icons/H.png',
                     'skins/forecast/icons/K.png',
                     'skins/forecast/icons/N.png',
                     'skins/forecast/icons/NE.png',
                     'skins/forecast/icons/NW.png',
                     'skins/forecast/icons/OV.png',
                     'skins/forecast/icons/OVn.png',
                     'skins/forecast/icons/PF+.png',
                     'skins/forecast/icons/PF.png',
                     'skins/forecast/icons/S.png',
                     'skins/forecast/icons/SC.png',
                     'skins/forecast/icons/SCn.png',
                     'skins/forecast/icons/SE.png',
                     'skins/forecast/icons/SW.png',
                     'skins/forecast/icons/W.png',
                     'skins/forecast/icons/blizzard.png',
                     'skins/forecast/icons/drizzle.png',
                     'skins/forecast/icons/flag-yellow.png',
                     'skins/forecast/icons/flag.png',
                     'skins/forecast/icons/flurries.png',
                     'skins/forecast/icons/frzngdrzl.png',
                     'skins/forecast/icons/moon.png',
                     'skins/forecast/icons/moonphase.png',
                     'skins/forecast/icons/moonriseset.png',
                     'skins/forecast/icons/pop.png',
                     'skins/forecast/icons/rain.png',
                     'skins/forecast/icons/raindrop.png',
                     'skins/forecast/icons/rainshwrs.png',
                     'skins/forecast/icons/raintorrent.png',
                     'skins/forecast/icons/sleet.png',
                     'skins/forecast/icons/snow.png',
                     'skins/forecast/icons/snowflake.png',
                     'skins/forecast/icons/snowshwrs.png',
                     'skins/forecast/icons/sprinkles.png',
                     'skins/forecast/icons/sun.png',
                     'skins/forecast/icons/sunmoon.png',
                     'skins/forecast/icons/sunriseset.png',
                     'skins/forecast/icons/thermometer-blue.png',
                     'skins/forecast/icons/thermometer-dewpoint.png',
                     'skins/forecast/icons/thermometer-red.png',
                     'skins/forecast/icons/thermometer.png',
                     'skins/forecast/icons/triangle-down.png',
                     'skins/forecast/icons/triangle-right.png',
                     'skins/forecast/icons/tstms.png',
                     'skins/forecast/icons/water.png']),
                   ]
            )
