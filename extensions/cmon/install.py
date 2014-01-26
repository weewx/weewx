# $Id$
# installer for cmon
# Copyright 2014 Matthew Wall

from setup import Installer

def loader():
    return ComputerMonitorInstaller()

class ComputerMonitorInstaller(Installer):
    def __init__(self):
        super(ComputerMonitorInstaller, self).__init__(
            version="0.1",
            name='cmon',
            description='Collect and display computer health indicators.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            process_services='user.cmon.ComputerMonitor',
            config={
                'ComputerMonitor': {
                    'database': 'computer_sqlite',
                    'max_age': '2592000'},
                'Databases': {
                    'computer_sqlite': {
                        'root': '%(SQLITE_ROOT)s',
                        'database': 'computer.sdb',
                        'driver': 'weedb.sqlite'}},
                'StdReport': {
                    'cmon': {
                        'skin':'cmon',
                        'HTML_ROOT':'cmon' }}},
            files=[('bin/user',
                    ['bin/user/cmon.py']),
                   ('skins/cmon',
                    ['skins/cmon/skin.conf',
                     'skins/cmon/index.html.tmpl']),
                   ]
            )
