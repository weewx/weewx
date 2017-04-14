"""
Upload data to Previmeteo
  http://previmeteo.com

[StdRESTful]
    [[Previmeteo]]
        station = STATION_ID
        password = PASSWORD
"""

import Queue
import syslog

import weewx
import weewx.restx
import weewx.units

VERSION = "0.1"

if weewx.__version__ < "3":
    raise weewx.UnsupportedFeature("weewx 3 is required, found %s" %
                                   weewx.__version__)
def logmsg(level, msg):
    syslog.syslog(level, 'restx: Previmeteo: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class StdPrevimeteo(weewx.restx.StdRESTful):
    """Specialized version of the Ambient protocol for Previmeteo"""

    archive_url = "http://www.previmeteo.com/scripts/stations/updateweatherstation.php"

    def __init__(self, engine, config_dict):

        super(StdPrevimeteo, self).__init__(engine, config_dict)

        _ambient_dict = get_site_dict(
            config_dict, 'Previmeteo', 'station', 'password')
        if _ambient_dict is None:
            return

        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        _ambient_dict.setdefault('server_url', StdPrevimeteo.archive_url)
        self.archive_queue = Queue.Queue()
        self.archive_thread = weewx.restx.AmbientThread(self.archive_queue, _manager_dict,
                                            protocol_name="Previmeteo",
                                            **_ambient_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        syslog.syslog(syslog.LOG_INFO, "restx: Previmeteo: "
                                       "Data for station %s will be posted" %
                      _ambient_dict['station'])

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)
