#
#    Copyright (c) 2009-2020 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Publish weather data to RESTful sites such as the Weather Underground.

                            GENERAL ARCHITECTURE

Each protocol uses two classes:

 o A weewx service, that runs in the main thread. Call this the
    "controlling object"
 o A separate "threading" class that runs in its own thread. Call this the
    "posting object".
 
Communication between the two is via an instance of queue.Queue. New loop
packets or archive records are put into the queue by the controlling object
and received by the posting object. Details below.
 
The controlling object should inherit from StdRESTful. The controlling object
is responsible for unpacking any configuration information from weewx.conf, and
supplying any defaults. It sets up the queue. It arranges for any new LOOP or
archive records to be put in the queue. It then launches the thread for the
posting object.
 
When a new LOOP or record arrives, the controlling object puts it in the queue,
to be received by the posting object. The controlling object can tell the
posting object to terminate by putting a 'None' in the queue.
 
The posting object should inherit from class RESTThread. It monitors the queue
and blocks until a new record arrives.

The base class RESTThread has a lot of functionality, so specializing classes
should only have to implement a few functions. In particular, 

 - format_url(self, record). This function takes a record dictionary as an
   argument. It is responsible for formatting it as an appropriate URL. 
   For example, the station registry's version emits strings such as
     http://weewx.com/register/register.cgi?weewx_info=2.6.0a5&python_info= ...
   
 - skip_this_post(self, time_ts). If this function returns True, then the
   post will be skipped. Otherwise, it is done. The default version does two
   checks. First, it sees how old the record is. If it is older than the value
   'stale', then the post is skipped. Second, it will not allow posts more
   often than 'post_interval'. Both of these can be set in the constructor of
   RESTThread.

 - post_request(self, request, data). This function takes a urllib.request.Request object
   and is responsible for performing the HTTP GET or POST. The default version
   simply uses urllib.request.urlopen(request) and returns the result. If the post
   could raise an unusual exception, override this function and catch the
   exception. See the WOWThread implementation for an example.
   
 - check_response(self, response). After an HTTP request gets posted, the webserver sends
   back a "response." This response may contain clues as to whether the post
   worked.  By overriding check_response() you can look for these clues. For
   example, the station registry checks all lines in the response, looking for
   any that start with the string "FAIL". If it finds one, it raises a
   FailedPost exception, signaling that the post did not work.
   
In unusual cases, you might also have to implement the following:
  
 - get_request(self, url). The default version of this function creates
   an urllib.request.Request object from the url, adds a 'User-Agent' header,
   then returns it. You may need to override this function if you need to add
   other headers, such as "Authorization" header.

 - get_post_body(self, record). Override this function if you want to do an HTTP
   POST (instead of GET). It should return a tuple. First element is the body
   of the POST, the second element is the type of the body. An example would
   be (json.dumps({'city' : 'Sacramento'}), 'application/json').

 - process_record(self, record, dbmanager). The default version is designed
   to handle HTTP GET and POST. However, if your uploader uses some other
   protocol, you may need to override this function. See the CWOP version,
   CWOPThread.process_record(), for an example that uses sockets.

See the file restful.md in the "tests" subdirectory for known behaviors
of various RESTful services.

"""

from __future__ import absolute_import

import datetime
import logging
import platform
import re
import socket
import ssl
import threading
import time

# Python 2/3 compatiblity shims
import six
from six.moves import http_client
from six.moves import queue
from six.moves import urllib

import weedb
import weeutil.logger
import weeutil.weeutil
import weewx.engine
import weewx.manager
import weewx.units
from weeutil.config import search_up, accumulateLeaves
from weeutil.weeutil import to_int, to_float, to_bool, timestamp_to_string, to_sorted_string

log = logging.getLogger(__name__)


class FailedPost(IOError):
    """Raised when a post fails, and is unlikely to succeed if retried."""


class AbortedPost(Exception):
    """Raised when a post is aborted by the client."""


class BadLogin(Exception):
    """Raised when login information is bad or missing."""


class ConnectError(IOError):
    """Raised when unable to get a socket connection."""


class SendError(IOError):
    """Raised when unable to send through a socket."""


# ==============================================================================
#                    Abstract base classes
# ==============================================================================

class StdRESTful(weewx.engine.StdService):
    """Abstract base class for RESTful weewx services.
    
    Offers a few common bits of functionality."""

    def shutDown(self):
        """Shut down any threads"""
        if hasattr(self, 'loop_queue') and hasattr(self, 'loop_thread'):
            StdRESTful.shutDown_thread(self.loop_queue, self.loop_thread)
        if hasattr(self, 'archive_queue') and hasattr(self, 'archive_thread'):
            StdRESTful.shutDown_thread(self.archive_queue, self.archive_thread)

    @staticmethod
    def shutDown_thread(q, t):
        """Function to shut down a thread."""
        if q and t.is_alive():
            # Put a None in the queue to signal the thread to shutdown
            q.put(None)
            # Wait up to 20 seconds for the thread to exit:
            t.join(20.0)
            if t.is_alive():
                log.error("Unable to shut down %s thread", t.name)
            else:
                log.debug("Shut down %s thread.", t.name)


# For backwards compatibility with early v2.6 alphas. In particular, the WeatherCloud uploader depends on it.
StdRESTbase = StdRESTful


class RESTThread(threading.Thread):
    """Abstract base class for RESTful protocol threads.
    
    Offers a few bits of common functionality."""

    def __init__(self, q, protocol_name,
                 essentials={},
                 manager_dict=None,
                 post_interval=None,
                 max_backlog=six.MAXSIZE,
                 stale=None,
                 log_success=True,
                 log_failure=True,
                 timeout=10,
                 max_tries=3,
                 retry_wait=5,
                 retry_login=3600,
                 retry_ssl=3600,
                 softwaretype="weewx-%s" % weewx.__version__,
                 skip_upload=False):
        """Initializer for the class RESTThread
        Required parameters:

          q: An instance of queue.Queue where the records will appear.

          protocol_name: A string holding the name of the protocol.
          
        Optional parameters:

          essentials: A dictionary that holds observation types that must
          not be None for the post to go ahead.

          manager_dict: A manager dictionary, to be used to open up a
          database manager. Default is None.
        
          post_interval: How long to wait between posts.
          Default is None (post every record).
          
          max_backlog: How many records are allowed to accumulate in the queue
          before the queue is trimmed.
          Default is six.MAXSIZE (essentially, allow any number).
          
          stale: How old a record can be and still considered useful.
          Default is None (never becomes too old).
          
          log_success: If True, log a successful post in the system log.
          Default is True.
          
          log_failure: If True, log an unsuccessful post in the system log.
          Default is True.
          
          timeout: How long to wait for the server to respond before giving up.
          Default is 10 seconds.

          max_tries: How many times to try the post before giving up.
          Default is 3
          
          retry_wait: How long to wait between retries when failures.
          Default is 5 seconds.
          
          retry_login: How long to wait before retrying a login. Default
          is 3600 seconds (one hour).
          
          retry_ssl: How long to wait before retrying after an SSL error. Default
          is 3600 seconds (one hour).

          softwaretype: Sent as field "softwaretype in the Ambient post.
          Default is "weewx-x.y.z where x.y.z is the weewx version.

          skip_upload: Do all record processing, but do not upload the result.
          Useful for diagnostic purposes when local debugging should not
          interfere with the downstream data service.  Default is False.
          """
        # Initialize my superclass:
        threading.Thread.__init__(self, name=protocol_name)
        self.daemon = True

        self.queue = q
        self.protocol_name = protocol_name
        self.essentials = essentials
        self.manager_dict = manager_dict
        self.log_success = to_bool(log_success)
        self.log_failure = to_bool(log_failure)
        self.max_backlog = to_int(max_backlog)
        self.max_tries = to_int(max_tries)
        self.stale = to_int(stale)
        self.post_interval = to_int(post_interval)
        self.timeout = to_int(timeout)
        self.retry_wait = to_int(retry_wait)
        self.retry_login = to_int(retry_login)
        self.retry_ssl = to_int(retry_ssl)
        self.softwaretype = softwaretype
        self.lastpost = 0
        self.skip_upload = to_bool(skip_upload)

    def get_record(self, record, dbmanager):
        """Augment record data with additional data from the archive.
        Should return results in the same units as the record and the database.
        
        This is a general version that works for:
          - WeatherUnderground
          - PWSweather
          - WOW
          - CWOP
        It can be overridden and specialized for additional protocols.

        returns: A dictionary of weather values"""

        if dbmanager is None:
            # If we don't have a database, we can't do anything
            if self.log_failure and weewx.debug >= 2:
                log.debug("No database specified. Augmentation from database skipped.")
            return record

        _time_ts = record['dateTime']
        _sod_ts = weeutil.weeutil.startOfDay(_time_ts)

        # Make a copy of the record, then start adding to it:
        _datadict = dict(record)

        # If the type 'rain' does not appear in the archive schema,
        # or the database is locked, an exception will be raised. Be prepared
        # to catch it.
        try:
            if 'hourRain' not in _datadict:
                # CWOP says rain should be "rain that fell in the past hour".
                # WU says it should be "the accumulated rainfall in the past
                # 60 min". Presumably, this is exclusive of the archive record
                # 60 minutes before, so the SQL statement is exclusive on the
                # left, inclusive on the right.
                _result = dbmanager.getSql(
                    "SELECT SUM(rain), MIN(usUnits), MAX(usUnits) FROM %s "
                    "WHERE dateTime>? AND dateTime<=?"
                    % dbmanager.table_name, (_time_ts - 3600.0, _time_ts))
                if _result is not None and _result[0] is not None:
                    if not _result[1] == _result[2] == record['usUnits']:
                        raise ValueError(
                            "Inconsistent units (%s vs %s vs %s) when querying for hourRain"
                            % (_result[1], _result[2], record['usUnits']))
                    _datadict['hourRain'] = _result[0]
                else:
                    _datadict['hourRain'] = None

            if 'rain24' not in _datadict:
                # Similar issue, except for last 24 hours:
                _result = dbmanager.getSql(
                    "SELECT SUM(rain), MIN(usUnits), MAX(usUnits) FROM %s "
                    "WHERE dateTime>? AND dateTime<=?"
                    % dbmanager.table_name, (_time_ts - 24 * 3600.0, _time_ts))
                if _result is not None and _result[0] is not None:
                    if not _result[1] == _result[2] == record['usUnits']:
                        raise ValueError(
                            "Inconsistent units (%s vs %s vs %s) when querying for rain24"
                            % (_result[1], _result[2], record['usUnits']))
                    _datadict['rain24'] = _result[0]
                else:
                    _datadict['rain24'] = None

            if 'dayRain' not in _datadict:
                # NB: The WU considers the archive with time stamp 00:00
                # (midnight) as (wrongly) belonging to the current day
                # (instead of the previous day). But, it's their site,
                # so we'll do it their way.  That means the SELECT statement
                # is inclusive on both time ends:
                _result = dbmanager.getSql(
                    "SELECT SUM(rain), MIN(usUnits), MAX(usUnits) FROM %s "
                    "WHERE dateTime>=? AND dateTime<=?"
                    % dbmanager.table_name, (_sod_ts, _time_ts))
                if _result is not None and _result[0] is not None:
                    if not _result[1] == _result[2] == record['usUnits']:
                        raise ValueError(
                            "Inconsistent units (%s vs %s vs %s) when querying for dayRain"
                            % (_result[1], _result[2], record['usUnits']))
                    _datadict['dayRain'] = _result[0]
                else:
                    _datadict['dayRain'] = None

        except weedb.OperationalError as e:
            log.debug("%s: Database OperationalError '%s'", self.protocol_name, e)

        return _datadict

    def run(self):
        """If there is a database specified, open the database, then call
        run_loop() with the database.  If no database is specified, simply
        call run_loop()."""

        # Open up the archive. Use a 'with' statement. This will automatically
        # close the archive in the case of an exception:
        if self.manager_dict is not None:
            with weewx.manager.open_manager(self.manager_dict) as _manager:
                self.run_loop(_manager)
        else:
            self.run_loop()

    def run_loop(self, dbmanager=None):
        """Runs a continuous loop, waiting for records to appear in the queue,
        then processing them.
        """

        while True:
            while True:
                # This will block until something appears in the queue:
                _record = self.queue.get()
                # A None record is our signal to exit:
                if _record is None:
                    return
                # If packets have backed up in the queue, trim it until it's
                # no bigger than the max allowed backlog:
                if self.queue.qsize() <= self.max_backlog:
                    break

            if self.skip_this_post(_record['dateTime']):
                continue

            try:
                # Process the record, using whatever method the specializing
                # class provides
                self.process_record(_record, dbmanager)
            except AbortedPost as e:
                if self.log_success:
                    _time_str = timestamp_to_string(_record['dateTime'])
                    log.info("%s: Skipped record %s: %s", self.protocol_name, _time_str, e)
            except BadLogin:
                if self.retry_login:
                    log.error("%s: Bad login; waiting %s minutes then retrying",
                              self.protocol_name, self.retry_login / 60.0)
                    time.sleep(self.retry_login)
                else:
                    log.error("%s: Bad login; no retry specified. Terminating", self.protocol_name)
                    raise
            except FailedPost as e:
                if self.log_failure:
                    _time_str = timestamp_to_string(_record['dateTime'])
                    log.error("%s: Failed to publish record %s: %s"
                              % (self.protocol_name, _time_str, e))
            except ssl.SSLError as e:
                if self.retry_ssl:
                    log.error("%s: SSL error (%s); waiting %s minutes then retrying",
                              self.protocol_name, e, self.retry_ssl / 60.0)
                    time.sleep(self.retry_ssl)
                else:
                    log.error("%s: SSL error (%s); no retry specified. Terminating",
                              self.protocol_name, e)
                    raise
            except Exception as e:
                # Some unknown exception occurred. This is probably a serious
                # problem. Exit.
                log.error("%s: Unexpected exception of type %s", self.protocol_name, type(e))
                weeutil.logger.log_traceback(log.error, '*** ')
                log.critical("%s: Thread terminating. Reason: %s", self.protocol_name, e)
                raise
            else:
                if self.log_success:
                    _time_str = timestamp_to_string(_record['dateTime'])
                    log.info("%s: Published record %s" % (self.protocol_name, _time_str))

    def process_record(self, record, dbmanager):
        """Default version of process_record.
        
        This version uses HTTP GETs to do the post, which should work for many
        protocols, but it can always be replaced by a specializing class."""

        # Get the full record by querying the database ...
        _full_record = self.get_record(record, dbmanager)
        # ... check it ...
        self.check_this_record(_full_record)
        # ... format the URL, using the relevant protocol ...
        _url = self.format_url(_full_record)
        # ... get the Request to go with it...
        _request = self.get_request(_url)
        #  ... get any POST payload...
        _payload = self.get_post_body(_full_record)
        # ... add a proper Content-Type if needed...
        if _payload:
            _request.add_header('Content-Type', _payload[1])
            data = _payload[0]
        else:
            data = None
        # ... check to see if this is just a drill...            
        if self.skip_upload:
            raise AbortedPost("Skip post")

        # ... then, finally, post it
        self.post_with_retries(_request, data)

    def get_request(self, url):
        """Get a request object. This can be overridden to add any special headers."""
        _request = urllib.request.Request(url)
        _request.add_header("User-Agent", "weewx/%s" % weewx.__version__)
        return _request

    def post_with_retries(self, request, data=None):
        """Post a request, retrying if necessary
        
        Attempts to post the request object up to max_tries times. 
        Catches a set of generic exceptions.
        
        request: An instance of urllib.request.Request
        
        data: The body of the POST. If not given, the request will be done as a GET.
        """

        # Retry up to max_tries times:
        for _count in range(self.max_tries):
            try:
                if _count:
                    # If this is not the first time through, sleep a bit before retrying
                    time.sleep(self.retry_wait)

                # Do a single post. The function post_request() can be
                # specialized by a RESTful service to catch any unusual
                # exceptions.
                _response = self.post_request(request, data)

                if 200 <= _response.code <= 299:
                    # No exception thrown and we got a good response code, but
                    # we're still not done.  Some protocols encode a bad
                    # station ID or password in the return message.
                    # Give any interested protocols a chance to examine it.
                    # This must also be inside the try block because some
                    # implementations defer hitting the socket until the
                    # response is used.
                    self.check_response(_response)
                    # Does not seem to be an error. We're done.
                    return
                # We got a bad response code. By default, log it and try again.
                # Provide method for derived classes to behave otherwise if
                # necessary.
                self.handle_code(_response.code, _count + 1)
            except (urllib.error.URLError, socket.error, http_client.HTTPException) as e:
                # An exception was thrown. By default, log it and try again.
                # Provide method for derived classes to behave otherwise if
                # necessary.
                self.handle_exception(e, _count + 1)
        else:
            # This is executed only if the loop terminates normally, meaning
            # the upload failed max_tries times. Raise an exception. Caller
            # can decide what to do with it.
            raise FailedPost("Failed upload after %d tries" % self.max_tries)

    def check_this_record(self, record):
        """Raises exception AbortedPost if the record should not be posted.
        Otherwise, does nothing"""
        for obs_type in self.essentials:
            if to_bool(self.essentials[obs_type]) and record.get(obs_type) is None:
                raise AbortedPost("Observation type %s missing" % obs_type)

    def check_response(self, response):
        """Check the response from a HTTP post. This version does nothing."""
        pass

    def handle_code(self, code, count):
        """Check code from HTTP post.  This simply logs the response."""
        log.debug("%s: Failed upload attempt %d: Code %s"
                  % (self.protocol_name, count, code))

    def handle_exception(self, e, count):
        """Check exception from HTTP post.  This simply logs the exception."""
        log.debug("%s: Failed upload attempt %d: %s" % (self.protocol_name, count, e))

    def post_request(self, request, data=None):
        """Post a request object. This version does not catch any HTTP
        exceptions.
        
        Specializing versions can can catch any unusual exceptions that might
        get raised by their protocol.
        
        request: An instance of urllib.request.Request
        
        data: If given, the request will be done as a POST. Otherwise, 
        as a GET. [optional]
        """
        # Data might be a unicode string. Encode it first.
        data_bytes = six.ensure_binary(data) if data is not None else None
        _response = urllib.request.urlopen(request, data=data_bytes, timeout=self.timeout)
        return _response

    def skip_this_post(self, time_ts):
        """Check whether the post is current"""
        # Don't post if this record is too old
        if self.stale is not None:
            _how_old = time.time() - time_ts
            if _how_old > self.stale:
                log.debug("%s: record %s is stale (%d > %d).",
                          self.protocol_name, timestamp_to_string(time_ts), _how_old, self.stale)
                return True

        if self.post_interval is not None:
            # We don't want to post more often than the post interval
            _how_long = time_ts - self.lastpost
            if _how_long < self.post_interval:
                log.debug("%s: wait interval (%d < %d) has not passed for record %s",
                          self.protocol_name, _how_long,
                          self.post_interval, timestamp_to_string(time_ts))
                return True

        self.lastpost = time_ts
        return False

    def get_post_body(self, record):  # @UnusedVariable
        """Return any POST payload.
        
        The returned value should be a 2-way tuple. First element is the Python
        object to be included as the payload. Second element is the MIME type it 
        is in (such as "application/json").
        
        Return a simple 'None' if there is no POST payload. This is the default.
        """
        # Maintain backwards compatibility with the old format_data() function.
        body = self.format_data(record)
        if body:
            return body, 'application/x-www-form-urlencoded'
        return None

    def format_data(self, _):
        """Return a POST payload as an urlencoded object.
        
        DEPRECATED. Use get_post_body() instead.
        """
        return None

    def format_url(self, _):
        raise NotImplementedError


# ==============================================================================
#                    Ambient protocols
# ==============================================================================

class StdWunderground(StdRESTful):
    """Specialized version of the Ambient protocol for the Weather Underground.
    """

    # the rapidfire URL:
    rf_url = "https://rtupdate.wunderground.com/weatherstation/updateweatherstation.php"
    # the personal weather station URL:
    pws_url = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"

    def __init__(self, engine, config_dict):

        super(StdWunderground, self).__init__(engine, config_dict)

        _ambient_dict = get_site_dict(
            config_dict, 'Wunderground', 'station', 'password')
        if _ambient_dict is None:
            return

        _essentials_dict = search_up(config_dict['StdRESTful']['Wunderground'], 'Essentials', {})

        log.debug("WU essentials: %s", _essentials_dict)

        # Get the manager dictionary:
        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        # The default is to not do an archive post if a rapidfire post
        # has been specified, but this can be overridden
        do_rapidfire_post = to_bool(_ambient_dict.pop('rapidfire', False))
        do_archive_post = to_bool(_ambient_dict.pop('archive_post',
                                                    not do_rapidfire_post))

        if do_archive_post:
            _ambient_dict.setdefault('server_url', StdWunderground.pws_url)
            self.archive_queue = queue.Queue()
            self.archive_thread = AmbientThread(
                self.archive_queue,
                _manager_dict,
                protocol_name="Wunderground-PWS",
                essentials=_essentials_dict,
                **_ambient_dict)
            self.archive_thread.start()
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
            log.info("Wunderground-PWS: Data for station %s will be posted",
                     _ambient_dict['station'])

        if do_rapidfire_post:
            _ambient_dict.setdefault('server_url', StdWunderground.rf_url)
            _ambient_dict.setdefault('log_success', False)
            _ambient_dict.setdefault('log_failure', False)
            _ambient_dict.setdefault('max_backlog', 0)
            _ambient_dict.setdefault('max_tries', 1)
            _ambient_dict.setdefault('rtfreq', 2.5)
            self.cached_values = CachedValues()
            self.loop_queue = queue.Queue()
            self.loop_thread = AmbientLoopThread(
                self.loop_queue,
                _manager_dict,
                protocol_name="Wunderground-RF",
                essentials=_essentials_dict,
                **_ambient_dict)
            self.loop_thread.start()
            self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
            log.info("Wunderground-RF: Data for station %s will be posted",
                     _ambient_dict['station'])

    def new_loop_packet(self, event):
        """Puts new LOOP packets in the loop queue"""
        if weewx.debug >= 3:
            log.debug("Raw packet: %s", to_sorted_string(event.packet))
        self.cached_values.update(event.packet, event.packet['dateTime'])
        if weewx.debug >= 3:
            log.debug("Cached packet: %s",
                      to_sorted_string(self.cached_values.get_packet(event.packet['dateTime'])))
        self.loop_queue.put(
            self.cached_values.get_packet(event.packet['dateTime']))

    def new_archive_record(self, event):
        """Puts new archive records in the archive queue"""
        self.archive_queue.put(event.record)


class CachedValues(object):
    """Dictionary of value-timestamp pairs.  Each timestamp indicates when the
    corresponding value was last updated."""

    def __init__(self):
        self.unit_system = None
        self.values = dict()

    def update(self, packet, ts):
        # update the cache with values from the specified packet, using the
        # specified timestamp.
        for k in packet:
            if k is None:
                # well-formed packets do not have None as key, but just in case
                continue
            elif k == 'dateTime':
                # do not cache the timestamp
                continue
            elif k == 'usUnits':
                # assume unit system of first packet, then enforce consistency
                if self.unit_system is None:
                    self.unit_system = packet['usUnits']
                elif packet['usUnits'] != self.unit_system:
                    raise ValueError("Mixed units encountered in cache. %s vs %s"
                                     % (self.unit_system, packet['usUnits']))
            else:
                # cache each value, associating it with the it was cached
                self.values[k] = {'value': packet[k], 'ts': ts}

    def get_value(self, k, ts, stale_age):
        # get the value for the specified key.  if the value is older than
        # stale_age (seconds) then return None.
        if k in self.values and ts - self.values[k]['ts'] < stale_age:
            return self.values[k]['value']
        return None

    def get_packet(self, ts=None, stale_age=960):
        if ts is None:
            ts = int(time.time() + 0.5)
        pkt = {'dateTime': ts, 'usUnits': self.unit_system}
        for k in self.values:
            pkt[k] = self.get_value(k, ts, stale_age)
        return pkt


class StdPWSWeather(StdRESTful):
    """Specialized version of the Ambient protocol for PWSWeather"""

    # The URL used by PWSWeather:
    archive_url = "https://www.pwsweather.com/pwsupdate/pwsupdate.php"

    def __init__(self, engine, config_dict):
        super(StdPWSWeather, self).__init__(engine, config_dict)

        _ambient_dict = get_site_dict(
            config_dict, 'PWSweather', 'station', 'password')
        if _ambient_dict is None:
            return

        # Get the manager dictionary:
        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        _ambient_dict.setdefault('server_url', StdPWSWeather.archive_url)
        self.archive_queue = queue.Queue()
        self.archive_thread = AmbientThread(self.archive_queue, _manager_dict,
                                            protocol_name="PWSWeather",
                                            **_ambient_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        log.info("PWSWeather: Data for station %s will be posted", _ambient_dict['station'])

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)


# For backwards compatibility with early alpha versions:
StdPWSweather = StdPWSWeather


class StdWOW(StdRESTful):
    """Upload using the UK Met Office's WOW protocol.
    
    For details of the WOW upload protocol, see 
    http://wow.metoffice.gov.uk/support/dataformats#dataFileUpload
    """

    # The URL used by WOW:
    archive_url = "https://wow.metoffice.gov.uk/automaticreading"

    def __init__(self, engine, config_dict):
        super(StdWOW, self).__init__(engine, config_dict)

        _ambient_dict = get_site_dict(
            config_dict, 'WOW', 'station', 'password')
        if _ambient_dict is None:
            return

        # Get the manager dictionary:
        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        _ambient_dict.setdefault('server_url', StdWOW.archive_url)
        self.archive_queue = queue.Queue()
        self.archive_thread = WOWThread(self.archive_queue, _manager_dict,
                                        protocol_name="WOW",
                                        **_ambient_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        log.info("WOW: Data for station %s will be posted", _ambient_dict['station'])

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)


class AmbientThread(RESTThread):
    """Concrete class for threads posting from the archive queue,
       using the Ambient PWS protocol.
       """

    def __init__(self,
                 q,
                 manager_dict,
                 station,
                 password,
                 server_url,
                 post_indoor_observations=False,
                 api_key=None,  # Not used.
                 protocol_name="Unknown-Ambient",
                 essentials={},
                 post_interval=None,
                 max_backlog=six.MAXSIZE,
                 stale=None,
                 log_success=True,
                 log_failure=True,
                 timeout=10,
                 max_tries=3,
                 retry_wait=5,
                 retry_login=3600,
                 retry_ssl=3600,
                 softwaretype="weewx-%s" % weewx.__version__,
                 skip_upload=False,
                 force_direction=False):

        """
        Initializer for the AmbientThread class.

        Parameters specific to this class:
          
          station: The name of the station. For example, for the WU, this
          would be something like "KORHOODR3".
          
          password: Password used for the station.
          
          server_url: An url where the server for this protocol can be found.
        """
        super(AmbientThread, self).__init__(q,
                                            protocol_name,
                                            essentials=essentials,
                                            manager_dict=manager_dict,
                                            post_interval=post_interval,
                                            max_backlog=max_backlog,
                                            stale=stale,
                                            log_success=log_success,
                                            log_failure=log_failure,
                                            timeout=timeout,
                                            max_tries=max_tries,
                                            retry_wait=retry_wait,
                                            retry_login=retry_login,
                                            retry_ssl=retry_ssl,
                                            softwaretype=softwaretype,
                                            skip_upload=skip_upload)
        self.station = station
        self.password = password
        self.server_url = server_url
        self.formats = dict(AmbientThread._FORMATS)
        if to_bool(post_indoor_observations):
            self.formats.update(AmbientThread._INDOOR_FORMATS)
        self.force_direction = to_bool(force_direction)
        self.last_direction = 0

    # Types and formats of the data to be published.
    # See https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US
    # for definitions.
    _FORMATS = {
        'barometer': 'baromin=%.3f',
        'co': 'AqCO=%f',
        'dateTime': 'dateutc=%s',
        'dayRain': 'dailyrainin=%.2f',
        'dewpoint': 'dewptf=%.1f',
        'hourRain': 'rainin=%.2f',
        'leafWet1': "leafwetness=%03.0f",
        'leafWet2': "leafwetness2=%03.0f",
        'no2': 'AqNO2=%f',
        'o3': 'AqOZONE=%f',
        'outHumidity': 'humidity=%03.0f',
        'outTemp': 'tempf=%.1f',
        'pm10_0': 'AqPM10=%.1f',
        'pm2_5': 'AqPM2.5=%.1f',
        'radiation': 'solarradiation=%.2f',
        'realtime': 'realtime=%d',
        'rtfreq': 'rtfreq=%.1f',
        'so2': 'AqSO2=%f',
        'soilMoist1': "soilmoisture=%03.0f",
        'soilMoist2': "soilmoisture2=%03.0f",
        'soilMoist3': "soilmoisture3=%03.0f",
        'soilMoist4': "soilmoisture4=%03.0f",
        'soilTemp1': "soiltempf=%.1f",
        'soilTemp2': "soiltemp2f=%.1f",
        'soilTemp3': "soiltemp3f=%.1f",
        'soilTemp4': "soiltemp4f=%.1f",
        'UV': 'UV=%.2f',
        'windDir': 'winddir=%03.0f',
        'windGust': 'windgustmph=%03.1f',
        'windGust10': 'windgustmph_10m=%03.1f',
        'windGustDir10': 'windgustdir_10m=%03.0f',
        'windSpeed': 'windspeedmph=%03.1f',
        'windSpeed2': 'windspdmph_avg2m=%03.1f',
        # The following four formats have been commented out until the WU
        # fixes the bug that causes them to be displayed as soil moisture.
        # 'extraTemp1' : "temp2f=%.1f",
        # 'extraTemp2' : "temp3f=%.1f",
        # 'extraTemp3' : "temp4f=%.1f",
        # 'extraTemp4' : "temp5f=%.1f",
    }

    _INDOOR_FORMATS = {
        'inTemp': 'indoortempf=%.1f',
        'inHumidity': 'indoorhumidity=%.0f'}

    def format_url(self, incoming_record):
        """Return an URL for posting using the Ambient protocol."""

        record = weewx.units.to_US(incoming_record)

        _liststr = ["action=updateraw",
                    "ID=%s" % self.station,
                    "PASSWORD=%s" % urllib.parse.quote(self.password),
                    "softwaretype=%s" % self.softwaretype]

        # Go through each of the supported types, formatting it, then adding
        # to _liststr:
        for _key in self.formats:
            _v = record.get(_key)
            # WU claims a station is "offline" if it sends a null wind direction, even when wind
            # speed is zero. If option 'force_direction' is set, cache the last non-null wind
            # direction and use it instead.
            if _key == 'windDir' and self.force_direction:
                if _v is None:
                    _v = self.last_direction
                else:
                    self.last_direction = _v
            # Check to make sure the type is not null
            if _v is not None:
                if _key == 'dateTime':
                    # Convert from timestamp to string. The results will look something
                    # like '2020-10-19%2021%3A43%3A18'
                    _v = urllib.parse.quote(str(datetime.datetime.utcfromtimestamp(_v)))
                # Format the value, and accumulate in _liststr:
                _liststr.append(self.formats[_key] % _v)
        # Now stick all the pieces together with an ampersand between them:
        _urlquery = '&'.join(_liststr)
        # This will be the complete URL for the HTTP GET:
        _url = "%s?%s" % (self.server_url, _urlquery)
        # show the url in the logs for debug, but mask any password
        if weewx.debug >= 2:
            log.debug("Ambient: url: %s", re.sub(r"PASSWORD=[^\&]*", "PASSWORD=XXX", _url))
        return _url

    def check_response(self, response):
        """Check the HTTP response for an Ambient related error."""
        for line in response:
            # PWSweather signals a bad login with 'ERROR'
            if line.startswith(b'ERROR'):
                # Bad login. No reason to retry. Raise an exception.
                raise BadLogin(line)
            # PWS signals something garbled with a line that includes 'invalid'.
            elif line.find(b'invalid') != -1:
                # Again, no reason to retry. Raise an exception.
                raise FailedPost(line)


class AmbientLoopThread(AmbientThread):
    """Version used for the Rapidfire protocol."""

    def __init__(self,
                 q,
                 manager_dict,
                 station,
                 password,
                 server_url,
                 post_indoor_observations=False,
                 api_key=None,  # Not used
                 protocol_name="Unknown-Ambient",
                 essentials={},
                 post_interval=None,
                 max_backlog=six.MAXSIZE,
                 stale=None,
                 log_success=True,
                 log_failure=True,
                 timeout=10,
                 max_tries=3,
                 retry_wait=5,
                 retry_login=3600,
                 retry_ssl=3600,
                 softwaretype="weewx-%s" % weewx.__version__,
                 skip_upload=False,
                 force_direction=False,
                 rtfreq=2.5  # This is the only one added by AmbientLoopThread
                 ):
        """
        Initializer for the AmbientLoopThread class.

        Parameters specific to this class:
          
          rtfreq: Frequency of update in seconds for RapidFire
        """
        super(AmbientLoopThread, self).__init__(q,
                                                manager_dict=manager_dict,
                                                station=station,
                                                password=password,
                                                server_url=server_url,
                                                post_indoor_observations=post_indoor_observations,
                                                api_key=api_key,
                                                protocol_name=protocol_name,
                                                essentials=essentials,
                                                post_interval=post_interval,
                                                max_backlog=max_backlog,
                                                stale=stale,
                                                log_success=log_success,
                                                log_failure=log_failure,
                                                timeout=timeout,
                                                max_tries=max_tries,
                                                retry_wait=retry_wait,
                                                retry_login=retry_login,
                                                retry_ssl=retry_ssl,
                                                softwaretype=softwaretype,
                                                skip_upload=skip_upload,
                                                force_direction=force_direction)

        self.rtfreq = float(rtfreq)
        self.formats.update(AmbientLoopThread.WUONLY_FORMATS)

    # may also be used by non-rapidfire; this is the least invasive way to just fix rapidfire,
    # which i know supports windGustDir, while the Ambient class is used elsewhere
    WUONLY_FORMATS = {
        'windGustDir': 'windgustdir=%03.0f'
    }

    def get_record(self, record, dbmanager):
        """Prepare a record for the Rapidfire protocol."""

        # Call the regular Ambient PWS version
        _record = AmbientThread.get_record(self, record, dbmanager)
        # Add the Rapidfire-specific keywords:
        _record['realtime'] = 1
        _record['rtfreq'] = self.rtfreq

        return _record


class WOWThread(AmbientThread):
    """Class for posting to the WOW variant of the Ambient protocol."""

    # Types and formats of the data to be published:
    _FORMATS = {'dateTime': 'dateutc=%s',
                'barometer': 'baromin=%.3f',
                'outTemp': 'tempf=%.1f',
                'outHumidity': 'humidity=%.0f',
                'windSpeed': 'windspeedmph=%.0f',
                'windDir': 'winddir=%.0f',
                'windGust': 'windgustmph=%.0f',
                'windGustDir': 'windgustdir=%.0f',
                'dewpoint': 'dewptf=%.1f',
                'hourRain': 'rainin=%.2f',
                'dayRain': 'dailyrainin=%.3f'}

    def format_url(self, incoming_record):
        """Return an URL for posting using WOW's version of the Ambient
        protocol."""

        record = weewx.units.to_US(incoming_record)

        _liststr = ["action=updateraw",
                    "siteid=%s" % self.station,
                    "siteAuthenticationKey=%s" % self.password,
                    "softwaretype=weewx-%s" % weewx.__version__]

        # Go through each of the supported types, formatting it, then adding
        # to _liststr:
        for _key in WOWThread._FORMATS:
            _v = record.get(_key)
            # Check to make sure the type is not null
            if _v is not None:
                if _key == 'dateTime':
                    _v = urllib.parse.quote_plus(
                        datetime.datetime.utcfromtimestamp(_v).isoformat(' '))
                # Format the value, and accumulate in _liststr:
                _liststr.append(WOWThread._FORMATS[_key] % _v)
        # Now stick all the pieces together with an ampersand between them:
        _urlquery = '&'.join(_liststr)
        # This will be the complete URL for the HTTP GET:
        _url = "%s?%s" % (self.server_url, _urlquery)
        # show the url in the logs for debug, but mask any password
        if weewx.debug >= 2:
            log.debug("WOW: url: %s", re.sub(r"siteAuthenticationKey=[^\&]*",
                                             "siteAuthenticationKey=XXX", _url))
        return _url

    def post_request(self, request, data=None):  # @UnusedVariable
        """Version of post_request() for the WOW protocol, which
        uses a response error code to signal a bad login."""
        try:
            _response = urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            # WOW signals a bad login with a HTML Error 403 code:
            if e.code == 403:
                raise BadLogin(e)
            elif e.code >= 400:
                raise FailedPost(e)
            else:
                raise
        else:
            return _response


# ==============================================================================
#                    CWOP
# ==============================================================================

class StdCWOP(StdRESTful):
    """Weewx service for posting using the CWOP protocol.
    
    Manages a separate thread CWOPThread"""

    # Default list of CWOP servers to try:
    default_servers = ['cwop.aprs.net:14580', 'cwop.aprs.net:23']

    def __init__(self, engine, config_dict):
        super(StdCWOP, self).__init__(engine, config_dict)

        _cwop_dict = get_site_dict(config_dict, 'CWOP', 'station')
        if _cwop_dict is None:
            return

        if 'passcode' not in _cwop_dict or _cwop_dict['passcode'] == 'replace_me':
            _cwop_dict['passcode'] = '-1'
        _cwop_dict['station'] = _cwop_dict['station'].upper()
        _cwop_dict.setdefault('latitude', self.engine.stn_info.latitude_f)
        _cwop_dict.setdefault('longitude', self.engine.stn_info.longitude_f)
        _cwop_dict.setdefault('station_type', config_dict['Station'].get(
            'station_type', 'Unknown'))

        # Get the database manager dictionary:
        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        self.archive_queue = queue.Queue()
        self.archive_thread = CWOPThread(self.archive_queue, _manager_dict,
                                         **_cwop_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        log.info("CWOP: Data for station %s will be posted", _cwop_dict['station'])

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)


class CWOPThread(RESTThread):
    """Concrete class for threads posting from the archive queue, using the CWOP protocol. For
    details on the protocol, see http://www.wxqa.com/faq.html."""

    def __init__(self, q, manager_dict,
                 station, passcode, latitude, longitude, station_type,
                 server_list=StdCWOP.default_servers,
                 post_interval=600, max_backlog=six.MAXSIZE, stale=600,
                 log_success=True, log_failure=True,
                 timeout=10, max_tries=3, retry_wait=5, skip_upload=False):

        """
        Initializer for the CWOPThread class.
        
        Parameters specific to this class:
          
          station: The name of the station. Something like "DW1234".
          
          passcode: Some stations require a passcode.
          
          latitude: Latitude of the station in decimal degrees.
          
          longitude: Longitude of the station in decimal degrees.
          
          station_type: The type of station. Generally, this is the driver
          symbolic name, such as "Vantage".
        
          server_list: A list of strings holding the CWOP server name and
          port. Default is ['cwop.aprs.net:14580', 'cwop.aprs.net:23']

        Parameters customized for this class:
          
          post_interval: How long to wait between posts.
          Default is 600 (every 10 minutes).
          
          stale: How old a record can be and still considered useful.
          Default is 60 (one minute).
        """
        # Initialize my superclass
        super(CWOPThread, self).__init__(q,
                                         protocol_name="CWOP",
                                         manager_dict=manager_dict,
                                         post_interval=post_interval,
                                         max_backlog=max_backlog,
                                         stale=stale,
                                         log_success=log_success,
                                         log_failure=log_failure,
                                         timeout=timeout,
                                         max_tries=max_tries,
                                         retry_wait=retry_wait,
                                         skip_upload=skip_upload)
        self.station = station
        self.passcode = passcode
        # In case we have a single server that would likely appear as a string
        # not a list
        self.server_list = weeutil.weeutil.option_as_list(server_list)
        self.latitude = to_float(latitude)
        self.longitude = to_float(longitude)
        self.station_type = station_type

    def process_record(self, record, dbmanager):
        """Process a record in accordance with the CWOP protocol."""

        # Get the full record by querying the database ...
        _full_record = self.get_record(record, dbmanager)
        # ... convert to US if necessary ...
        _us_record = weewx.units.to_US(_full_record)
        # ... get the login and packet strings...
        _login = self.get_login_string()
        _tnc_packet = self.get_tnc_packet(_us_record)
        if self.skip_upload:
            raise AbortedPost("Skip post")
        # ... then post them:
        self.send_packet(_login, _tnc_packet)

    def get_login_string(self):
        _login = "user %s pass %s vers weewx %s\r\n" % (
            self.station, self.passcode, weewx.__version__)
        return _login

    def get_tnc_packet(self, record):
        """Form the TNC2 packet used by CWOP."""

        # Preamble to the TNC packet:
        _prefix = "%s>APRS,TCPIP*:" % self.station

        # Time:
        _time_tt = time.gmtime(record['dateTime'])
        _time_str = time.strftime("@%d%H%Mz", _time_tt)

        # Position:
        _lat_str = weeutil.weeutil.latlon_string(self.latitude,
                                                 ('N', 'S'), 'lat')
        _lon_str = weeutil.weeutil.latlon_string(self.longitude,
                                                 ('E', 'W'), 'lon')
        # noinspection PyStringFormat
        _latlon_str = '%s%s%s/%s%s%s' % (_lat_str + _lon_str)

        # Wind and temperature
        _wt_list = []
        for _obs_type in ['windDir', 'windSpeed', 'windGust', 'outTemp']:
            _v = record.get(_obs_type)
            _wt_list.append("%03d" % int(_v + 0.5) if _v is not None else '...')
        _wt_str = "_%s/%sg%st%s" % tuple(_wt_list)

        # Rain
        _rain_list = []
        for _obs_type in ['hourRain', 'rain24', 'dayRain']:
            _v = record.get(_obs_type)
            _rain_list.append("%03d" % int(_v * 100.0 + 0.5) if _v is not None else '...')
        _rain_str = "r%sp%sP%s" % tuple(_rain_list)

        # Barometer:
        _baro = record.get('altimeter')
        if _baro is None:
            _baro_str = "b....."
        else:
            # While everything else in the CWOP protocol is in US Customary,
            # they want the barometer in millibars.
            _baro_vt = weewx.units.convert((_baro, 'inHg', 'group_pressure'),
                                           'mbar')
            _baro_str = "b%05d" % int(_baro_vt[0] * 10.0 + 0.5)

        # Humidity:
        _humidity = record.get('outHumidity')
        if _humidity is None:
            _humid_str = "h.."
        else:
            _humid_str = ("h%02d" % int(_humidity + 0.5)) if _humidity < 99.5 else "h00"

        # Radiation:
        _radiation = record.get('radiation')
        if _radiation is None:
            _radiation_str = ""
        elif _radiation < 999.5:
            _radiation_str = "L%03d" % int(_radiation + 0.5)
        elif _radiation < 1999.5:
            _radiation_str = "l%03d" % int(_radiation - 1000 + 0.5)
        else:
            _radiation_str = ""

        # Station equipment
        _equipment_str = ".weewx-%s-%s" % (weewx.__version__, self.station_type)

        _tnc_packet = ''.join([_prefix, _time_str, _latlon_str, _wt_str,
                               _rain_str, _baro_str, _humid_str,
                               _radiation_str, _equipment_str, "\r\n"])

        # show the packet in the logs for debug
        if weewx.debug >= 2:
            log.debug("CWOP: packet: '%s'", _tnc_packet.rstrip('\r\n'))

        return _tnc_packet

    def send_packet(self, login, tnc_packet):

        # Go through the list of known server:ports, looking for
        # a connection that works:
        for _serv_addr_str in self.server_list:

            try:
                _server, _port_str = _serv_addr_str.split(":")
                _port = int(_port_str)
            except ValueError:
                log.error("%s: Bad server address: '%s'; ignored", self.protocol_name,
                          _serv_addr_str)
                continue

            # Try each combination up to max_tries times:
            for _count in range(self.max_tries):
                try:
                    # Get a socket connection:
                    _sock = self._get_connect(_server, _port)
                    log.debug("%s: Connected to server %s:%d", self.protocol_name, _server, _port)
                    try:
                        # Send the login ...
                        self._send(_sock, login, dbg_msg='login')
                        # ... and then the packet
                        response = self._send(_sock, tnc_packet, dbg_msg='tnc')
                        if weewx.debug >= 2:
                            log.debug("%s: Response to packet: '%s'", self.protocol_name, response)
                        return
                    finally:
                        _sock.close()
                except ConnectError as e:
                    log.debug("%s: Attempt %d to %s:%d. Connection error: %s",
                              self.protocol_name, _count + 1, _server, _port, e)
                except SendError as e:
                    log.debug("%s: Attempt %d to %s:%d. Socket send error: %s",
                              self.protocol_name, _count + 1, _server, _port, e)

        # If we get here, the loop terminated normally, meaning we failed
        # all tries
        raise FailedPost("Tried %d servers %d times each"
                         % (len(self.server_list), self.max_tries))

    def _get_connect(self, server, port):
        """Get a socket connection to a specific server and port."""

        _sock = None
        try:
            _sock = socket.socket()
            _sock.connect((server, port))
        except IOError as e:
            # Unsuccessful. Close it in case it was open:
            try:
                _sock.close()
            except (AttributeError, socket.error):
                pass
            raise ConnectError(e)

        return _sock

    def _send(self, sock, msg, dbg_msg):
        """Send a message to a specific socket."""

        # Convert from string to byte string
        msg_bytes = msg.encode('ascii')
        try:
            sock.send(msg_bytes)
        except IOError as e:
            # Unsuccessful. Log it and go around again for another try
            raise SendError("Packet %s; Error %s" % (dbg_msg, e))
        else:
            # Success. Look for response from the server.
            try:
                _resp = sock.recv(1024).decode('ascii')
                return _resp
            except IOError as e:
                log.debug("%s: Exception %s (%s) when looking for response to %s packet",
                          self.protocol_name, type(e), e, dbg_msg)
                return


# ==============================================================================
#                    Station Registry
# ==============================================================================

class StdStationRegistry(StdRESTful):
    """Class for phoning home to register a weewx station.

    To enable this module, add the following to weewx.conf:

    [StdRESTful]
        [[StationRegistry]]
            register_this_station = True

    This will periodically do a http GET with the following information:

        station_url      Should be world-accessible. Used as key.
        description      Brief synopsis of the station
        latitude         Station latitude in decimal
        longitude        Station longitude in decimal
        station_type     The driver name, for example Vantage, FineOffsetUSB
        station_model    The hardware_name property from the driver
        weewx_info       weewx version
        python_info
        platform_info

    The station_url is the unique key by which a station is identified.
    """

    archive_url = 'http://weewx.com/register/register.cgi'

    def __init__(self, engine, config_dict):

        super(StdStationRegistry, self).__init__(engine, config_dict)

        _registry_dict = get_site_dict(config_dict, 'StationRegistry', 'register_this_station')
        if _registry_dict is None:
            return

        # Should the service be run?
        if not to_bool(_registry_dict.pop('register_this_station', False)):
            log.info("StationRegistry: Registration not requested.")
            return

        # Registry requires a valid station url
        _registry_dict.setdefault('station_url',
                                  self.engine.stn_info.station_url)
        if _registry_dict['station_url'] is None:
            log.info("StationRegistry: Station will not be registered: no station_url specified.")
            return

        _registry_dict.setdefault('station_type',
                                  config_dict['Station'].get('station_type', 'Unknown'))
        _registry_dict.setdefault('description', self.engine.stn_info.location)
        _registry_dict.setdefault('latitude', self.engine.stn_info.latitude_f)
        _registry_dict.setdefault('longitude', self.engine.stn_info.longitude_f)
        _registry_dict.setdefault('station_model', self.engine.stn_info.hardware)

        self.archive_queue = queue.Queue()
        self.archive_thread = StationRegistryThread(self.archive_queue,
                                                    **_registry_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        log.info("StationRegistry: Station will be registered.")

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)


class StationRegistryThread(RESTThread):
    """Concrete threaded class for posting to the weewx station registry."""

    def __init__(self, q, station_url, latitude, longitude,
                 server_url=StdStationRegistry.archive_url,
                 description="Unknown",
                 station_type="Unknown", station_model="Unknown",
                 post_interval=604800, max_backlog=0, stale=None,
                 log_success=True, log_failure=True,
                 timeout=60, max_tries=3, retry_wait=5):
        """Initialize an instance of StationRegistryThread.
        
        Parameters specific to this class:

          station_url: An URL used to identify the station. This will be
          used as the unique key in the registry to identify each station.
          
          latitude: Latitude of the staion
          
          longitude: Longitude of the station
        
          server_url: The URL of the registry server. 
          Default is 'http://weewx.com/register/register.cgi'
          
          description: A brief description of the station. 
          Default is 'Unknown'
          
          station_type: The type of station. Generally, this is the name of
          the driver used by the station. 
          Default is 'Unknown'
          
          station_model: The hardware model, typically the hardware_name
          property provided by the driver.
          Default is 'Unknown'.

        Parameters customized for this class:
          
          post_interval: How long to wait between posts.
          Default is 604800 seconds (1 week).
        """

        super(StationRegistryThread, self).__init__(
            q,
            protocol_name='StationRegistry',
            post_interval=post_interval,
            max_backlog=max_backlog,
            stale=stale,
            log_success=log_success,
            log_failure=log_failure,
            timeout=timeout,
            max_tries=max_tries,
            retry_wait=retry_wait)
        self.station_url = station_url
        self.latitude = to_float(latitude)
        self.longitude = to_float(longitude)
        self.server_url = server_url
        self.description = weeutil.weeutil.list_as_string(description)
        self.station_type = station_type
        self.station_model = station_model

    def get_record(self, dummy_record, dummy_archive):
        _record = {
            'station_url': self.station_url,
            'description': self.description,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'station_type': self.station_type,
            'station_model': self.station_model,
            'python_info': platform.python_version(),
            'platform_info': platform.platform(),
            'weewx_info': weewx.__version__,
            'usUnits': weewx.US,
        }
        return _record

    _FORMATS = {'station_url': 'station_url=%s',
                'description': 'description=%s',
                'latitude': 'latitude=%.4f',
                'longitude': 'longitude=%.4f',
                'station_type': 'station_type=%s',
                'station_model': 'station_model=%s',
                'python_info': 'python_info=%s',
                'platform_info': 'platform_info=%s',
                'weewx_info': 'weewx_info=%s'}

    def format_url(self, record):
        """Return an URL for posting using the StationRegistry protocol."""

        _liststr = []
        for _key in StationRegistryThread._FORMATS:
            v = record[_key]
            if v is not None:
                # Under Python 2, quote_plus() can only accept strings (no unicode).
                # If necessary, convert.
                if isinstance(v, six.string_types):
                    v = six.ensure_str(v)
                _liststr.append(urllib.parse.quote_plus(StationRegistryThread._FORMATS[_key] % v,
                                                        '='))
        _urlquery = '&'.join(_liststr)
        _url = "%s?%s" % (self.server_url, _urlquery)
        return _url

    def check_response(self, response):
        """Check the response from a Station Registry post."""
        for line in response:
            # the server replies to a bad post with a line starting with "FAIL"
            if line.startswith(b'FAIL'):
                raise FailedPost(line)


# ==============================================================================
# AWEKAS
# ==============================================================================

class StdAWEKAS(StdRESTful):
    """Upload data to AWEKAS - Automatisches WEtterKArten System
    http://www.awekas.at

    To enable this module, add the following to weewx.conf:

    [StdRESTful]
        [[AWEKAS]]
            enable   = True
            username = AWEKAS_USERNAME
            password = AWEKAS_PASSWORD
    
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
    Pos7: air pressure (hPa) (float) [22dec15. This should be SLP. -tk personal communications]
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
        super(StdAWEKAS, self).__init__(engine, config_dict)

        site_dict = get_site_dict(config_dict, 'AWEKAS', 'username', 'password')
        if site_dict is None:
            return

        site_dict.setdefault('latitude', engine.stn_info.latitude_f)
        site_dict.setdefault('longitude', engine.stn_info.longitude_f)
        site_dict.setdefault('language', 'de')

        site_dict['manager_dict'] = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        self.archive_queue = queue.Queue()
        self.archive_thread = AWEKASThread(self.archive_queue, **site_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)
        log.info("AWEKAS: Data will be uploaded for user %s", site_dict['username'])

    def new_archive_record(self, event):
        self.archive_queue.put(event.record)


# For compatibility with some early alpha versions:
AWEKAS = StdAWEKAS


class AWEKASThread(RESTThread):
    _SERVER_URL = 'http://data.awekas.at/eingabe_pruefung.php'
    _FORMATS = {'barometer': '%.3f',
                'outTemp': '%.1f',
                'outHumidity': '%.0f',
                'windSpeed': '%.1f',
                'windDir': '%.0f',
                'windGust': '%.1f',
                'dewpoint': '%.1f',
                'hourRain': '%.2f',
                'dayRain': '%.2f',
                'radiation': '%.2f',
                'UV': '%.2f',
                'rainRate': '%.2f'}

    def __init__(self, q, username, password, latitude, longitude,
                 manager_dict,
                 language='de', server_url=_SERVER_URL,
                 post_interval=300, max_backlog=six.MAXSIZE, stale=None,
                 log_success=True, log_failure=True,
                 timeout=10, max_tries=3, retry_wait=5,
                 retry_login=3600, retry_ssl=3600, skip_upload=False):
        """Initialize an instances of AWEKASThread.

        Parameters specific to this class:

          username: AWEKAS user name

          password: AWEKAS password

          language: Possible values include de, en, it, fr, nl
          Default is de

          latitude: Station latitude in decimal degrees
          Default is station latitude

          longitude: Station longitude in decimal degrees
          Default is station longitude
        
          manager_dict: A dictionary holding the database manager
          information. It will be used to open a connection to the archive 
          database.
        
          server_url: URL of the server
          Default is the AWEKAS site

        Parameters customized for this class:

          post_interval: The interval in seconds between posts. AWEKAS requests
          that uploads happen no more often than 5 minutes, so this should be
          set to no less than 300. Default is 300
        """
        import hashlib
        super(AWEKASThread, self).__init__(q,
                                           protocol_name='AWEKAS',
                                           manager_dict=manager_dict,
                                           post_interval=post_interval,
                                           max_backlog=max_backlog,
                                           stale=stale,
                                           log_success=log_success,
                                           log_failure=log_failure,
                                           timeout=timeout,
                                           max_tries=max_tries,
                                           retry_wait=retry_wait,
                                           retry_login=retry_login,
                                           retry_ssl=retry_ssl,
                                           skip_upload=skip_upload)
        self.username = username
        # Calculate and save the password hash
        m = hashlib.md5()
        m.update(password.encode('utf-8'))
        self.password_hash = m.hexdigest()
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.language = language
        self.server_url = server_url

    def get_record(self, record, dbmanager):
        """Ensure that rainRate is in the record."""
        # Have my superclass process the record first.
        record = super(AWEKASThread, self).get_record(record, dbmanager)

        # No need to do anything if rainRate is already in the record
        if 'rainRate' in record:
            return record

        # If we don't have a database, we can't do anything
        if dbmanager is None:
            if self.log_failure:
                log.debug("AWEKAS: No database specified. Augmentation from database skipped.")
            return record

        # If the database does not have rainRate in its schema, an exception will be raised.
        # Be prepare to catch it.
        try:
            rr = dbmanager.getSql('select rainRate from %s where dateTime=?'
                                  % dbmanager.table_name, (record['dateTime'],))
        except weedb.OperationalError:
            pass
        else:
            # If there is no record with the timestamp, None will be returned.
            # In theory, this shouldn't happen, but check just in case:
            if rr:
                record['rainRate'] = rr[0]

        return record

    def format_url(self, in_record):
        """Specialized version of format_url() for the AWEKAS protocol."""

        # Convert to units required by awekas
        record = weewx.units.to_METRIC(in_record)
        if 'dayRain' in record and record['dayRain'] is not None:
            record['dayRain'] *= 10
        if 'rainRate' in record and record['rainRate'] is not None:
            record['rainRate'] *= 10

        time_tt = time.gmtime(record['dateTime'])
        # assemble an array of values in the proper order
        values = [
            self.username,
            self.password_hash,
            time.strftime("%d.%m.%Y", time_tt),
            time.strftime("%H:%M", time_tt),
            self._format(record, 'outTemp'),  # C
            self._format(record, 'outHumidity'),  # %
            self._format(record, 'barometer'),  # mbar
            self._format(record, 'dayRain'),  # mm
            self._format(record, 'windSpeed'),  # km/h
            self._format(record, 'windDir'),
            '',  # weather condition
            '',  # warning text
            '',  # snow high
            self.language,
            '',  # tendency
            self._format(record, 'windGust'),  # km/h
            self._format(record, 'radiation'),  # W/m^2
            self._format(record, 'UV'),  # uv index
            '',  # brightness in lux
            '',  # sunshine hours
            '',  # soil temperature
            self._format(record, 'rainRate'),  # mm/h
            'weewx_%s' % weewx.__version__,
            str(self.longitude),
            str(self.latitude),
        ]

        valstr = ';'.join(values)
        url = self.server_url + '?val=' + valstr

        if weewx.debug >= 2:
            # show the url in the logs for debug, but mask any credentials
            log.debug('AWEKAS: url: %s', url.replace(self.password_hash, 'XXX'))

        return url

    def _format(self, record, label):
        if label in record and record[label] is not None:
            if label in self._FORMATS:
                return self._FORMATS[label] % record[label]
            return str(record[label])
        return ''

    def check_response(self, response):
        """Specialized version of check_response()."""
        for line in response:
            # Skip blank lines:
            if not line.strip():
                continue
            if line.startswith(b'OK'):
                return
            elif line.startswith(b"Benutzer/Passwort Fehler"):
                raise BadLogin(line)
            else:
                raise FailedPost("Server returned '%s'" % six.ensure_text(line))


###############################################################################

def get_site_dict(config_dict, service, *args):
    """Obtain the site options, with defaults from the StdRESTful section.
    If the service is not enabled, or if one or more required parameters is
    not specified, then return None."""

    try:
        site_dict = accumulateLeaves(config_dict['StdRESTful'][service],
                                     max_level=1)
    except KeyError:
        log.info("%s: No config info. Skipped.", service)
        return None

    # If site_dict has the key 'enable' and it is False, then
    # the service is not enabled.
    try:
        if not to_bool(site_dict['enable']):
            log.info("%s: Posting not enabled.", service)
            return None
    except KeyError:
        pass

    # At this point, either the key 'enable' does not exist, or
    # it is set to True. Check to see whether all the needed
    # options exist, and none of them have been set to 'replace_me':
    try:
        for option in args:
            if site_dict[option] == 'replace_me':
                raise KeyError(option)
    except KeyError as e:
        log.debug("%s: Data will not be posted: Missing option %s", service, e)
        return None

    # If the site dictionary does not have a log_success or log_failure, get
    # them from the root dictionary
    site_dict.setdefault('log_success', to_bool(config_dict.get('log_success', True)))
    site_dict.setdefault('log_failure', to_bool(config_dict.get('log_failure', True)))

    # Get rid of the no longer needed key 'enable':
    site_dict.pop('enable', None)

    return site_dict


# For backward compatibility pre 3.6.0
check_enable = get_site_dict
