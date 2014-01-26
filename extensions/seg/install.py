# $Id$
# installer for seg
# Copyright 2014 Matthew Wall

from setup import ExtensionInstaller

def loader():
    return SEGInstaller()

class SEGInstaller(ExtensionInstaller):
    def __init__(self):
        super(SEGInstaller, self).__init__(
            version="0.1",
            name='seg',
            description='Upload weather data to SmartEnergyGroups.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            restful_services='user.seg.SEG',
            config={
                'StdRESTful' : {
                    'SmartEnergyGroups': {
                        'token': 'INSERT_TOKEN_HERE',
                        'station': 'INSERT_STATION_IDENTIFIER_HERE'}}},
            files=[('bin/user', ['bin/user/seg.py'])]
            )
