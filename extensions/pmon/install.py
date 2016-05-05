# installer for pmon
# Copyright 2014 Matthew Wall

from setup import ExtensionInstaller

def loader():
    return ProcessMonitorInstaller()

class ProcessMonitorInstaller(ExtensionInstaller):
    def __init__(self):
        super(ProcessMonitorInstaller, self).__init__(
            version="0.4",
            name='pmon',
            description='Collect and display process memory usage.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            process_services='user.pmon.ProcessMonitor',
            config={
                'ProcessMonitor': {
                    'data_binding': 'pmon_binding',
                    'process': 'weewxd'},
                'DataBindings': {
                    'pmon_binding': {
                        'database': 'pmon_sqlite',
                        'table_name': 'archive',
                        'manager': 'weewx.manager.DaySummaryManager',
                        'schema': 'user.pmon.schema'}},
                'Databases': {
                    'pmon_sqlite': {
                        'database_name': 'pmon.sdb',
                        'driver': 'weedb.sqlite'}},
                'StdReport': {
                    'pmon': {
                        'skin': 'pmon',
                        'HTML_ROOT': 'pmon'}}},
            files=[('bin/user', ['bin/user/pmon.py']),
                   ('skins/pmon', ['skins/pmon/skin.conf',
                                   'skins/pmon/index.html.tmpl'])]
            )
