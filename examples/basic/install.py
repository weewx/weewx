# installer for the 'basic' skin
# Copyright 2014-2023 Matthew Wall

import os.path
from io import StringIO

import configobj

from weecfg.extension import ExtensionInstaller


def loader():
    return BasicInstaller()


# By creating the configuration dictionary from a StringIO, we can preserve any comments
BASIC_CONFIG = """
[StdReport]

    [[BasicReport]]
        skin = Basic
        enable = True
        # Language to use:
        lang = en
        # Unit system to use:
        unit_system = US
        # Where to put the results:
        HTML_ROOT = basic
"""

basic_dict = configobj.ConfigObj(StringIO(BASIC_CONFIG))


class BasicInstaller(ExtensionInstaller):
    def __init__(self):
        super(BasicInstaller, self).__init__(
            version="0.5",
            name='basic',
            description='Very basic skin for WeeWX.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config=basic_dict,
            files=[
                ('skins/Basic',
                 ['skins/Basic/basic.css',
                  'skins/Basic/current.inc',
                  'skins/Basic/favicon.ico',
                  'skins/Basic/hilo.inc',
                  'skins/Basic/index.html.tmpl',
                  'skins/Basic/skin.conf',
                  'skins/Basic/lang/en.conf',
                  'skins/Basic/lang/fr.conf',
                  ]),
            ]
        )

    def configure(self, engine):
        """Customized configuration that sets a language code"""
        # TODO: Set a units code as well
        my_skin_path = os.path.join(os.path.dirname(__file__), 'skins/Basic')
        code = engine.get_lang_code(my_skin_path, 'en')
        self['config']['StdReport']['BasicReport']['lang'] = code
        return True
