# installer for xstats
# Copyright 2014 Matthew Wall

from setup import ExtensionInstaller

def loader():
    return XStatsInstaller()

class XStatsInstaller(ExtensionInstaller):
    def __init__(self):
        super(XStatsInstaller, self).__init__(
            version="0.2",
            name='xstats',
            description='Extended statistics for weewx reports',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config={
                'StdReport': {
                    'xstats': {
                        'skin': 'xstats',
                        'HTML_ROOT': 'xstats'}}},
            files=[('bin/user', ['bin/user/xstats.py']),
                   ('skins/xstats', ['skins/xstats/skin.conf',
                                     'skins/xstats/index.html.tmpl'])]
            )
