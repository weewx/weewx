# $Id$
# Copyright 2013 Matthew Wall
"""weewx module that records process information.

Installation

Put this file in the bin/user directory.


Configuration

Add the following to weewx.conf:

[ProcessMonitor]
    data_binding = pmon_binding

[DataBindings]
    [[pmon_binding]]
        database = pmon_sqlite
        manager = weewx.manager.DaySummaryManager
        table_name = archive
        schema = user.pmon.schema

[Databases]
    [[pmon_sqlite]]
        root = %(WEEWX_ROOT)s
        database_name = archive/pmon.sdb
        driver = weedb.sqlite

[Engine]
    [[Services]]
        archive_services = ..., user.pmon.ProcessMonitor
"""

import os
import platform
import re
import syslog
import time
from subprocess import Popen, PIPE

import weewx
import weeutil.weeutil
from weewx.engine import StdService

VERSION = "0.2"

def logmsg(level, msg):
    syslog.syslog(level, 'pmon: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

schema = [
    ('dateTime', 'INTEGER NOT NULL PRIMARY KEY'),
    ('usUnits', 'INTEGER NOT NULL'),
    ('interval', 'INTEGER NOT NULL'),
    ('mem_vsz','INTEGER'),
    ('mem_rss','INTEGER'),
    ]


class ProcessMonitor(StdService):

    def __init__(self, engine, config_dict):
        super(ProcessMonitor, self).__init__(engine, config_dict)

        d = config_dict.get('ProcessMonitor', {})
        self.process = d.get('process', 'weewxd')
        self.max_age = weeutil.weeutil.to_int(d.get('max_age', 2592000))

        # get the database parameters we need to function
        binding = d.get('data_binding', 'pmon_binding')
        self.dbm = self.engine.db_binder.get_manager(data_binding=binding,
                                                     initialize=True)

        # be sure database matches the schema we have
        dbcol = self.dbm.connection.columnsOf(self.dbm.table_name)
        dbm_dict = weewx.manager.get_manager_dict(
            config_dict['DataBindings'], config_dict['Databases'], binding)
        memcol = [x[0] for x in dbm_dict['schema']]
        if dbcol != memcol:
            raise Exception('pmon schema mismatch: %s != %s' % (dbcol, memcol))

        self.last_ts = None
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

    def shutDown(self):
        try:
            self.dbm.close()
        except:
            pass

    def new_archive_record(self, event):
        """save data to database then prune old records as needed"""
        now = int(time.time() + 0.5)
        delta = now - event.record['dateTime']
        if delta > event.record['interval'] * 60:
            logdbg("Skipping record: time difference %s too big" % delta)
            return
        if self.last_ts is not None:
            self.save_data(self.get_data(now, self.last_ts))
        self.last_ts = now
        if self.max_age is not None:
            self.prune_data(now - self.max_age)

    def save_data(self, record):
        """save data to database"""
        self.dbm.addRecord(record)

    def prune_data(self, ts):
        """delete records with dateTime older than ts"""
        sql = "delete from %s where dateTime < %d" % (self.dbm.table_name, ts)
        self.dbm.getSql(sql)
        try:
            # sqlite databases need some help to stay small
            self.dbm.getSql('vacuum')
        except Exception, e:
            pass

    COLUMNS = re.compile('[\S]+\s+[\d]+\s+[\d.]+\s+[\d.]+\s+([\d]+)\s+([\d]+)')

    def get_data(self, now_ts, last_ts):
        record = {}
        record['dateTime'] = now_ts
        record['usUnits'] = weewx.METRIC
        record['interval'] = int((now_ts - last_ts) / 60)
        try:
            cmd = 'ps aux'
            p = Popen(cmd, shell=True, stdout=PIPE)
            o = p.communicate()[0]
            for line in o.split('\n'):
                if line.find(self.process) >= 0:
                    m = self.COLUMNS.search(line)
                    if m:
                        record['mem_vsz'] = int(m.group(1))
                        record['mem_rss'] = int(m.group(2))
        except (ValueError, IOError, KeyError), e:
            logerr('apcups_info failed: %s' % e)

        return record


# what follows is a basic unit test of this module.  to run the test:
#
# cd /home/weewx
# PYTHONPATH=bin python bin/user/pmon.py
#
if __name__=="__main__":
    from weewx.engine import StdEngine
    config = {
        'Station': {
            'station_type': 'Simulator',
            'altitude': [0,'foot'],
            'latitude': 0,
            'longitude': 0},
        'Simulator': {
            'driver': 'weewx.drivers.simulator',
            'mode': 'simulator'},
        'ProcessMonitor': {
            'data_binding': 'pmon_binding',
            'process': 'weewxd'},
        'DataBindings': {
            'pmon_binding': {
                'database': 'pmon_sqlite',
                'manager': 'weewx.manager.DaySummaryManager',
                'table_name': 'archive',
                'schema': 'user.pmon.schema'}},
        'Databases': {
            'pmon_sqlite': {
                'root': '/tmp',
                'database_name': 'pmon.sdb',
                'driver': 'weedb.sqlite'}},
        'Engines': {
            'Services': {
                'process_services': 'user.pmon.ProcessMonitor'}}}
    engine = StdEngine(config)
    svc = ProcessMonitor(engine, config)
    record = svc.get_data()
    print record

    time.sleep(5)
    record = svc.get_data()
    print record

    time.sleep(5)
    record = svc.get_data()
    print record

    os.remove('/tmp/pmon.sdb')
