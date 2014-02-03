# $Id$
# installer for the 'basic' skin
# Copyright 2014 Matthew Wall

from setup import ExtensionInstaller

def loader():
    return BasicInstaller()

class BasicInstaller(ExtensionInstaller):
    def __init__(self):
        super(BasicInstaller, self).__init__(
            version="0.1",
            name='basic',
            description='Very basic skin for weewx.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config={
                'StdReport': {
                    'basic': {
                        'skin':'basic',
                        'HTML_ROOT':'basic',
                        'Extras': {
                            'current':'SKIN_DIR/basic/current.inc',
                            'hilo':'SKIN_DIR/basic/hilo.inc'}}}},
            files=[('skins/basic',
                    ['skins/basic/basic.css',
                     'skins/basic/current.inc',
                     'skins/basic/favicon.ico',
                     'skins/basic/hilo.inc',
                     'skins/basic/index.html.tmpl',
                     'skins/basic/skin.conf']),
                   ]
            )
