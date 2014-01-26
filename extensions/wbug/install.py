# $Id$
# installer for WeatherBug
# Copyright 2014 Matthew Wall

from setup import Installer

def loader():
    return WeatherBugInstaller()

class WeatherBugInstaller(Installer):
    def __init__(self):
        super(WeatherBugInstaller, self).__init__(
            version="0.1",
            name='wbug',
            description='Upload weather data to WeatherBug.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            restful_services='user.wbug.WeatherBug',
            config={
                'StdRESTful': {
                    'WeatherBug': {
                        'publisher_id': 'INSERT_PUBLISHER_ID_HERE',
                        'station_number': 'INSERT_STATION_NUMBER_HERE',
                        'password': 'INSERT_PASSWORD_HERE'}}},
            files=[('bin/user', ['bin/user/wbug.py'])]
            )
