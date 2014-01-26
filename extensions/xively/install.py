# $Id$
# installer for Xively
# Copyright 2014 Matthew Wall

from setup import ExtensionInstaller

def loader():
    return XivelyInstaller()

class XivelyInstaller(ExtensionInstaller):
    def __init__(self):
        super(XivelyInstaller, self).__init__(
            version="0.1",
            name='xively',
            description='Upload weather data to Xively.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            restful_services='user.xively.Xively',
            config={
                'StdRESTful': {
                    'Xively': {
                        'token': 'INSERT_TOKEN_HERE',
                        'feed': 'INSERT_FEED_HERE',
                        'station_name': 'INSERT_STATION_NAME_HERE'}}},
            files=[('bin/user', ['bin/user/xively.py'])]
            )
