# $Id$
# Copyright 2013 Matthew Wall

#==============================================================================
# AWEKAS
#==============================================================================
# Upload data to AWEKAS - Automatisches WEtterKArten System
# http://www.awekas.at
#
# Installation:
# 1) put this file in bin/user
# 2) add the following configuration stanza to weewx.conf
# 3) restart weewx
#
# [AWEKAS]
#     username = AWEKAS_USERNAME
#     password = AWEKAS_PASSWORD

import Queue
import hashlib
import sys
import syslog
import time
import urllib2

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool

def logmsg(level, msg):
    syslog.syslog(level, 'awekas: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class AWEKAS(weewx.restx.StdRESTbase):
    """Upload using the AWEKAS protocol.

    The AWEKAS server expects a single string of values delimited by
    semicolons.  The position of each value matters, for example position 1
    is the awekas username and position 2 is the awekas password.

    Positions 1-25 are defined for the basic API:

    Pos1: user (awekas username)
    Pos2: password (awekas password MD5 Hash)
    Pos3: date (dd.mm.yyyy) (varchar)
    Pos4: time (hh:mm) (varchar)
    Pos5: temperature (C) (float)
    Pos6: humidity (%) (int)
    Pos7: air pressure (hPa) (float)
    Pos8: precipitation (rain at this day) (float)
    Pos9: wind speed (km/h) float)
    Pos10: wind direction (degree) (int)
    Pos11: weather condition (int)
            0=clear warning
            1=clear
            2=sunny sky
            3=partly cloudy
            4=cloudy
            5=heavy cloundy
            6=overcast sky
            7=fog
            8=rain showers
            9=heavy rain showers
           10=light rain
           11=rain
           12=heavy rain
           13=light snow
           14=snow
           15=light snow showers
           16=snow showers
           17=sleet
           18=hail
           19=thunderstorm
           20=storm
           21=freezing rain
           22=warning
           23=drizzle
           24=heavy snow
           25=heavy snow showers
    Pos12: warning text (varchar)
    Pos13: snow high (cm) (int) if no snow leave blank
    Pos14: language (varchar)
           de=german; en=english; it=italian; fr=french; nl=dutch
    Pos15: tendency (int)
           -2 = high falling
           -1 = falling
            0 = steady
            1 = rising
            2 = high rising
    Pos16. wind gust (km/h) (float)
    Pos17: solar radiation (W/m^2) (float) 
    Pos18: UV Index (float)
    Pos19: brightness (LUX) (int)
    Pos20: sunshine hours today (float)
    Pos21: soil temperature (degree C) (float)
    Pos22: rain rate (mm/h) (float)
    Pos23: software flag NNNN_X.Y, for example, WLIP_2.15
    Pos24: longitude (float)
    Pos25: latitude (float)

    positions 26-111 are defined for API2
        """

    def __init__(self, engine, config_dict):
        """Initialize for posting data to AWEKAS.

        Required parameters:

        username: AWEKAS user name

        password: AWEKAS password

        language: Possible values include de, en, it, fr, nl
        Default is de

        latitude: Station latitude in decimal degrees
        Default is station latitude

        longitude: Station longitude in decimal degrees
        Default is station longitude

        Optional parameters:
        
        station: station identifier
        Default is None.

        server_url: URL of the server
        Default is the AWEKAS site
        
        log_success: If True, log a successful post in the system log.
        Default is True.

        log_failure: If True, log an unsuccessful post in the system log.
        Default is True.

        max_backlog: How many records are allowed to accumulate in the queue
        before the queue is trimmed.
        Default is sys.maxint (essentially, allow any number).

        max_tries: How many times to try the post before giving up.
        Default is 3

        stale: How old a record can be and still considered useful.
        Default is None (never becomes too old).

        post_interval: The interval in seconds between posts.
        AWEKAS requests that uploads happen no more often than 5 minutes, so
        this should be set to no less than 300.
        Default is 300

        timeout: How long to wait for the server to respond before giving up.
        Default is 60 seconds

        skip_upload: debugging option to display data but do not upload
        Default is False
        """
        super(AWEKAS, self).__init__(engine, config_dict)
        try:
            site_dict = dict(config_dict['StdRESTful']['AWEKAS'])
            site_dict['username']
            site_dict['password']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        site_dict.setdefault('latitude', engine.stn_info.latitude_f)
        site_dict.setdefault('longitude', engine.stn_info.longitude_f)
        site_dict.setdefault('language', 'de')
        site_dict.setdefault('database_dict', config_dict['Databases'][config_dict['StdArchive']['archive_database']])

        self.archive_queue = Queue.Queue()
        self.archive_thread = AWEKASThread(self.archive_queue, **site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        loginf("Data will be uploaded to AWEKAS")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)

class AWEKASThread(weewx.restx.RESTThread):

    _SERVER_URL = 'http://data.awekas.at/eingabe_pruefung.php'
    _FORMATS = {'barometer'   : '%.3f',
                'outTemp'     : '%.1f',
                'outHumidity' : '%.0f',
                'windSpeed'   : '%.1f',
                'windDir'     : '%.0f',
                'windGust'    : '%.1f',
                'dewpoint'    : '%.1f',
                'hourRain'    : '%.2f',
                'dayRain'     : '%.2f',
                'radiation'   : '%.2f',
                'UV'          : '%.2f',
                'rainRate'    : '%.2f'}

    def __init__(self, queue, username, password, latitude, longitude,
                 database_dict,
                 language='de', server_url=_SERVER_URL, skip_upload=False,
                 log_success=True, log_failure=True, max_backlog=sys.maxint,
                 stale=None, max_tries=3, post_interval=300, timeout=60):
        super(AWEKASThread, self).__init__(queue,
                                           protocol_name='AWEKAS',
                                           database_dict=database_dict,
                                           log_success=log_success,
                                           log_failure=log_failure,
                                           max_backlog=max_backlog,
                                           stale=stale,
                                           max_tries=max_tries,
                                           post_interval=post_interval,
                                           timeout=timeout)
        self.username = username
        self.password = password
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.language = language
        self.server_url = server_url
        self.skip_upload = to_bool(skip_upload)

    def get_record(self, record, archive):
        """Add rainRate to the record."""
        r = super(AWEKASThread, self).get_record(record, archive)
        # FIXME: for some reason this returns an array of 10 items instead
        # of a single record.  why?
        rr = archive.getSql('select rainRate from archive where dateTime=?',
                            (r['dateTime'],))
        datadict = dict(zip(['rainRate'], rr))
        if datadict.has_key('rainRate'):
            r['rainRate'] = datadict['rainRate']
        return r

    def process_record(self, record, archive):
        r = self.get_record(record, archive)
        url = self.get_url(r)
        if self.skip_upload:
            logdbg("skipping upload")
            return
        req = urllib2.Request(url)
        self.post_with_retries(req)

    def check_response(self, response):
        for line in response:
            if not line.startswith('OK'):
                raise weewx.restx.FailedPost("server returned '%s'" % line)

    def get_url(self, record):
        # put everything into the right units and scaling
        if record['usUnits'] != weewx.METRIC:
            converter = weewx.units.StdUnitConverters[weewx.METRIC]
            record = converter.convertDict(record)
        if record.has_key('dayRain') and record['dayRain'] is not None:
            record['dayRain'] = record['dayRain'] * 10
        if record.has_key('rainRate') and record['rainRate'] is not None:
            record['rainRate'] = record['rainRate'] * 10

        # assemble an array of values in the proper order
        values = [self.username]
        m = hashlib.md5()
        m.update(self.password)
        values.append(m.hexdigest())
        time_tt = time.gmtime(record['dateTime'])
        values.append(time.strftime("%d.%m.%Y", time_tt))
        values.append(time.strftime("%H:%M", time_tt))
        values.append(self._format(record, 'outTemp')) # C
        values.append(self._format(record, 'outHumidity')) # %
        values.append(self._format(record, 'barometer')) # mbar
        values.append(self._format(record, 'dayRain')) # mm?
        values.append(self._format(record, 'windSpeed')) # km/h
        values.append(self._format(record, 'windDir'))
        values.append('') # weather condition
        values.append('') # warning text
        values.append('') # snow high
        values.append(self.language)
        values.append('') # tendency
        values.append(self._format(record, 'windGust')) # km/h
        values.append(self._format(record, 'radiation')) # W/m^2
        values.append(self._format(record, 'UV')) # uv index
        values.append('') # brightness in lux
        values.append('') # sunshine hours
        values.append('') # soil temperature
        values.append(self._format(record, 'rainRate')) # mm/h
        values.append('weewx_%s' % weewx.__version__)
        values.append(str(self.longitude))
        values.append(str(self.latitude))

        valstr = ';'.join(values)
        url = self.server_url + '?val=' + valstr
        logdbg('url: %s' % url)
        return url

    def _format(self, record, label):
        if record.has_key(label) and record[label] is not None:
            if self._FORMATS.has_key(label):
                return self._FORMATS[label] % record[label]
            return str(record[label])
        return ''
