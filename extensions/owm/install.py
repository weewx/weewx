# $Id$
# installer for OpenWeatherMap
# Copyright 2014 Matthew Wall

from setup import Installer

def loader():
    return OWMInstaller()

class OWMInstaller(Installer):
    def __init__(self):
        super(OWMInstaller, self).__init__(
            version="0.1",
            name='owm',
            description='Upload weather data to OpenWeatherMap.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            restful_services='user.owm.OpenWeatherMap',
            config={
                'StdRESTful': {
                    'OpenWeatherMap': {
                        'username': 'INSERT_USERNAME_HERE',
                        'password': 'INSERT_PASSWORD_HERE',
                        'station_name': 'INSERT_STATION_NAME_HERE'}}},
            files=[('bin/user', ['bin/user/owm.py'])]
            )
