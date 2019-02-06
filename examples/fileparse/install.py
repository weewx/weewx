# installer for the fileparse driver
# Copyright 2014 Matthew Wall

from weecfg.extension import ExtensionInstaller


def loader():
    return FileParseInstaller()


class FileParseInstaller(ExtensionInstaller):
    def __init__(self):
        super(FileParseInstaller, self).__init__(
            version="0.6",
            name='fileparse',
            description='File parsing driver for weewx.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config={
                'Station': {
                    'station_type': 'FileParse'},
                'FileParse': {
                    'poll_interval': '10',
                    'path': '/var/tmp/datafile',
                    'driver': 'user.fileparse'}},
            files=[('bin/user', ['bin/user/fileparse.py'])]
        )
