# installer for the 'basic' skin
# Copyright 2014-2021 Matthew Wall

from weecfg.extension import ExtensionInstaller


def loader():
    return BasicInstaller()


class BasicInstaller(ExtensionInstaller):
    def __init__(self):
        super(BasicInstaller, self).__init__(
            version="0.3",
            name='basic',
            description='Very basic skin for weewx.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config={
                'StdReport': {
                    'basic': {
                        'skin': 'basic',
                        'HTML_ROOT': 'basic',
                        'lang': 'en',
                        'units': 'US'
                    }
                }
            },
            files=[
                ('skins/basic',
                 ['skins/basic/basic.css',
                  'skins/basic/current.inc',
                  'skins/basic/favicon.ico',
                  'skins/basic/hilo.inc',
                  'skins/basic/index.html.tmpl',
                  'skins/basic/skin.conf']),
                ('skins/basic/lang',
                 ['skins/basic/lang/en.conf',
                  'skins/basic/lang/fr.conf'])
            ]
        )
