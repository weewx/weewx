# $Id$
# installer for amphibian
# Copyright 2014 Matthew Wall

from setup import Installer

def loader():
    return AmphibianInstaller()

class AmphibianInstaller(Installer):
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
                        'HTML_ROOT':'amphibian' }}},
            files=[('skins/amphibian',
                    ['skins/amphibian/almanac.html.tmpl',
                     'skins/ambhibian/amphibian.css',
                     'skins/ambhibian/amphibian.js',
                     'skins/ambhibian/charts.inc',
                     'skins/ambhibian/day.html.tmpl',
                     'skins/ambhibian/favicon.ico',
                     'skins/ambhibian/footer.inc',
                     'skins/ambhibian/header.inc',
                     'skins/ambhibian/index.html.tmpl',
                     'skins/ambhibian/month-table.html.tmpl',
                     'skins/ambhibian/month.html.tmpl',
                     'skins/ambhibian/skin.conf',
                     'skins/ambhibian/week-table.html.tmpl',
                     'skins/ambhibian/week.html.tmpl',
                     'skins/ambhibian/weewx_rss.xml.tmpl',
                     'skins/ambhibian/year-table.html.tmpl',
                     'skins/amphibian/year.html.tmpl']),
                   ('skins/amphibian/NOAA',
                    ['skins/amphibian/NOAA/NOAA-YYYY-MM.txt.tmpl',
                     'skins/amphibian/NOAA/NOAA-YYYY.txt.tmpl']),
                   ]
            )
