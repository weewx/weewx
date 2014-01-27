# $Id$
# installer for amphibian
# Copyright 2014 Matthew Wall

from setup import ExtensionInstaller

def loader():
    return AmphibianInstaller()

class AmphibianInstaller(ExtensionInstaller):
    def __init__(self):
        super(AmphibianInstaller, self).__init__(
            version="0.8",
            name='amphibian',
            description='Skin that looks a bit like a wet frog.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config={
                'StdReport': {
                    'amphibian': {
                        'skin':'amphibian',
                        'HTML_ROOT':'amphibian',
                        'Extras': {
                            'footer':'%(WEEWX_ROOT)s%(SKIN_ROOT)s/amphibian/footer.inc',
                            'header':'%(WEEWX_ROOT)s%(SKIN_ROOT)s/amphibian/header.inc',
                            'charts':'%(WEEWX_ROOT)s%(SKIN_ROOT)s/amphibian/charts.inc'}}}},
            files=[('skins/amphibian',
                    ['skins/amphibian/almanac.html.tmpl',
                     'skins/amphibian/amphibian.css',
                     'skins/amphibian/amphibian.js',
                     'skins/amphibian/charts.inc',
                     'skins/amphibian/day.html.tmpl',
                     'skins/amphibian/favicon.ico',
                     'skins/amphibian/footer.inc',
                     'skins/amphibian/header.inc',
                     'skins/amphibian/index.html.tmpl',
                     'skins/amphibian/month-table.html.tmpl',
                     'skins/amphibian/month.html.tmpl',
                     'skins/amphibian/skin.conf',
                     'skins/amphibian/week-table.html.tmpl',
                     'skins/amphibian/week.html.tmpl',
                     'skins/amphibian/weewx_rss.xml.tmpl',
                     'skins/amphibian/year-table.html.tmpl',
                     'skins/amphibian/year.html.tmpl']),
                   ]
            )
