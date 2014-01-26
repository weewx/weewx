# $Id$
# installer for awekas
# Copyright 2014 Matthew Wall

from setup import ExtensionInstaller

def loader():
    return AWEKASInstaller()

class AWEKASInstaller(ExtensionInstaller):
    def __init__(self):
        super(AWEKASInstaller, self).__init__(
            version="0.1",
            name='awekas',
            description='Upload weather data to AWEKAS.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            restful_services='user.awekas.AWEKAS',
            config={
                'StdRESTful': {
                    'AWEKAS': {
                        'username': 'INSERT_USERNAME_HERE',
                        'password': 'INSERT_PASSWORD_HERE'}}},
            files=[('bin/user', ['bin/user/awekas.py'])]
            )
