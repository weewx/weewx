#
#    Copyright (c) 2019-2026 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test restx services"""

import configobj
import http.client
import os
import queue
import time
import urllib.parse
from unittest import mock

import pytest

import weewx
import weewx.restx

os.environ['TZ'] = 'America/Los_Angeles'
time.tzset()


class MatchRequest:
    """Allows equality testing between Request objects"""

    def __init__(self, url, user_agent):
        # This is what I'm expecting:
        self.url = url
        self.user_agent = user_agent

    def __eq__(self, req):
        """Check for equality between myself and a Request object"""

        other_split = urllib.parse.urlsplit(req.get_full_url())
        other_query = urllib.parse.parse_qs(other_split.query)
        my_split = urllib.parse.urlsplit(self.url)
        my_query = urllib.parse.parse_qs(my_split.query)

        # In what follows, we could just return 'False', but raising the AssertionError directly
        # gives more useful error messages.

        if other_split.hostname != my_split.hostname:
            raise AssertionError(
                "Mismatched hostnames: \nActual:'%s'\nExpect:'%s' " % (other_split.hostname, my_split.hostname))
        if other_query != my_query:
            raise AssertionError("Mismatched queries: \nActual:'%s'\nExpect:'%s' " % (other_query, my_query))
        if req.headers.get('User-agent') != self.user_agent:
            raise AssertionError("Mismatched user-agent: \nActual:'%s'\nExpect:'%s'"
                                 % (req.headers.get('User-agent'), self.user_agent))
        return True


def get_record():
    """Get a record that is to be posted to the RESTful service."""
    ts = time.mktime(time.strptime("2018-03-22", "%Y-%m-%d"))
    record = {'dateTime': ts,
              'usUnits': weewx.US,
              'interval': 5,
              'outTemp': 20.0,
              'inTemp': 70.0,
              'barometer': 30.1
              }
    return record


class TestAmbient:
    """Test the Ambient RESTful protocol"""

    # These don't really matter. We'll be testing that the URL we end up with is
    # the one we were expecting.
    station = 'KBZABCDEF3'
    password = 'somepassword'
    server_url = 'http://www.testserver.com/testapi'
    protocol_name = 'Test-Ambient'

    @pytest.fixture(autouse=True)
    def setup_method(self):
        self.patchers = []

    def teardown_method(self):
        for patcher in self.patchers:
            patcher.stop()

    def get_openurl_patcher(self, code=200, response_body=None, side_effect=None):
        """Get a patch object for a post to urllib.request.urlopen

        code: The response code that should be returned by the mock urlopen().

        response_body: The response body that should be returned by the mock urlopen().
        Should be an iterable.

        side_effect: Any side effect to be done. Set to an exception class to have
        an exception raised by the mock urlopen().
        """
        if response_body is None:
            response_body = []
        # Mock up the urlopen
        patcher = mock.patch('weewx.restx.urllib.request.urlopen')
        mock_urlopen = patcher.start()
        # Set up its return value. It will be a MagicMock object.
        mock_urlopen.return_value = mock.MagicMock()
        # Add a return code
        mock_urlopen.return_value.code = code
        # And something we can iterate over for the response body
        mock_urlopen.return_value.__iter__.return_value = iter(response_body)
        if side_effect:
            mock_urlopen.side_effect = side_effect
        # This will insure that patcher.stop() method will get called after a test
        self.patchers.append(patcher)
        return mock_urlopen

    def test_request(self):
        """Test of a normal GET post to an Ambient uploading service"""

        # Get the mock urlopen()
        mock_urlopen = self.get_openurl_patcher()
        q = queue.Queue()
        obj = weewx.restx.AmbientThread(q,
                                        manager_dict=None,
                                        station=TestAmbient.station,
                                        password=TestAmbient.password,
                                        server_url=TestAmbient.server_url,
                                        protocol_name=TestAmbient.protocol_name,
                                        max_tries=1,
                                        log_success=True,
                                        log_failure=True,
                                        )
        record = get_record()
        q.put(record)
        q.put(None)
        # Set up mocks of log.debug() and log.info(). Then we'll check that they got called as we expected
        with mock.patch('weewx.restx.log.debug') as mock_logdbg:
            with mock.patch('weewx.restx.log.info') as mock_loginf:
                obj.run()
                mock_logdbg.assert_not_called()
                # loginf() should have been called once with the success
                mock_loginf.assert_called_once_with('Test-Ambient: Published record '
                                                    '2018-03-22 00:00:00 PDT (1521702000)')

        # Now check that our mock urlopen() was called with the parameters we expected.
        matcher = TestAmbient.get_matcher(TestAmbient.server_url, TestAmbient.station, TestAmbient.password)
        mock_urlopen.assert_called_once_with(matcher, data=None, timeout=10)

    def test_request_with_indoor(self):
        """Test of a normal GET post to an Ambient uploading service, but include indoor temperature"""

        mock_urlopen = self.get_openurl_patcher()
        q = queue.Queue()
        obj = weewx.restx.AmbientThread(q,
                                        manager_dict=None,
                                        station=TestAmbient.station,
                                        password=TestAmbient.password,
                                        server_url=TestAmbient.server_url,
                                        protocol_name=TestAmbient.protocol_name,
                                        max_tries=1,
                                        log_success=True,
                                        log_failure=True,
                                        post_indoor_observations=True   # Set to True this time!
                                        )
        record = get_record()
        q.put(record)
        q.put(None)
        # Set up mocks of log.debug() and log.info(). Then we'll check that they got called as we expected
        with mock.patch('weewx.restx.log.debug') as mock_logdbg:
            with mock.patch('weewx.restx.log.info') as mock_loginf:
                obj.run()
                mock_logdbg.assert_not_called()
                # loginf() should have been called once with the success
                mock_loginf.assert_called_once_with('Test-Ambient: Published record '
                                                    '2018-03-22 00:00:00 PDT (1521702000)')

        # Now check that our mock urlopen() was called with the parameters we expected.
        matcher = TestAmbient.get_matcher(TestAmbient.server_url, TestAmbient.station, TestAmbient.password,
                                          include_indoor=True)
        mock_urlopen.assert_called_once_with(matcher, data=None, timeout=10)

    def test_bad_response_request(self):
        """Test response to a bad request"""

        # This will get a mocked version of urlopen, which will return a 401 code
        mock_urlopen = self.get_openurl_patcher(code=401, response_body=['unauthorized'])
        q = queue.Queue()
        obj = weewx.restx.AmbientThread(q,
                                        manager_dict=None,
                                        station=TestAmbient.station,
                                        password=TestAmbient.password,
                                        server_url=TestAmbient.server_url,
                                        protocol_name=TestAmbient.protocol_name,
                                        max_tries=1,
                                        log_success=True,
                                        log_failure=True,
                                        )
        record = get_record()
        q.put(record)
        q.put(None)
        # Set up mocks of log.debug() and log.error(). Then we'll check that they got called as we expected
        with mock.patch('weewx.restx.log.debug') as mock_logdbg:
            with mock.patch('weewx.restx.log.error') as mock_logerr:
                obj.run()
                # log.debug() should have been called twice...
                mock_logdbg.assert_called_once_with('Test-Ambient: Failed upload attempt 1: Code 401')
                # ... and log.error() once with the failed post.
                mock_logerr.assert_called_once_with('Test-Ambient: Failed to publish record '
                                                    '2018-03-22 00:00:00 PDT (1521702000): '
                                                    'Failed upload after 1 tries')

        # Now check that our mock urlopen() was called with the parameters we expected.
        matcher = TestAmbient.get_matcher(TestAmbient.server_url, TestAmbient.station, TestAmbient.password)
        mock_urlopen.assert_called_once_with(matcher, data=None, timeout=10)

    def test_bad_http_request(self):
        """Test response to raising an exception during a post"""

        # Get a mock version of urlopen(), but with the side effect of having an exception of
        # type http.client.HTTPException raised when it's called
        mock_urlopen = self.get_openurl_patcher(side_effect=http.client.HTTPException("oops"))

        q = queue.Queue()
        obj = weewx.restx.AmbientThread(q,
                                        manager_dict=None,
                                        station=TestAmbient.station,
                                        password=TestAmbient.password,
                                        server_url=TestAmbient.server_url,
                                        protocol_name=TestAmbient.protocol_name,
                                        max_tries=1,
                                        log_success=True,
                                        log_failure=True,
                                        )
        record = get_record()
        q.put(record)
        q.put(None)
        # Set up mocks of log.debug() and log.error(). Then we'll check that they got called as we expected
        with mock.patch('weewx.restx.log.debug') as mock_logdbg:
            with mock.patch('weewx.restx.log.error') as mock_logerr:
                obj.run()
                # log.debug() should have been called twice...
                mock_logdbg.assert_called_once_with('Test-Ambient: Failed upload attempt 1: oops')
                # ... and log.error() once with the failed post.
                mock_logerr.assert_called_once_with('Test-Ambient: Failed to publish record '
                                                    '2018-03-22 00:00:00 PDT (1521702000): '
                                                    'Failed upload after 1 tries')

        # Now check that our mock urlopen() was called with the parameters we expected.
        matcher = TestAmbient.get_matcher(TestAmbient.server_url, TestAmbient.station, TestAmbient.password)
        mock_urlopen.assert_called_once_with(matcher, data=None, timeout=10)

    @staticmethod
    def get_matcher(server_url, station, password, include_indoor=False):
        """Return a MatchRequest object that will test against what we expected"""
        url = '%s?action=updateraw&ID=%s&PASSWORD=%s&softwaretype=weewx-%s' \
              '&dateutc=2018-03-22%%2007%%3A00%%3A00' \
              '&baromin=30.100&tempf=20.0' \
              % (server_url, station, password, weewx.__version__)
        if include_indoor:
            url += "&indoortempf=70.0"
        matcher = MatchRequest(url, 'weewx/%s' % weewx.__version__)
        return matcher


class TestWunderground:
    """Test the StdWunderground service setup. Regression test for PR #1145"""

    station = 'KBZABCDEF3'
    password = 'somepassword'

    @staticmethod
    def get_config_dict(wunderground_options):
        """Build a configuration dictionary with a Wunderground section"""
        config_dict = configobj.ConfigObj()
        config_dict['StdRESTful'] = {}
        config_dict['StdRESTful']['Wunderground'] = {'enable': True,
                                                     'station': TestWunderground.station,
                                                     'password': TestWunderground.password}
        config_dict['StdRESTful']['Wunderground'].update(wunderground_options)
        return config_dict

    @staticmethod
    def get_service(wunderground_options):
        """Construct a StdWunderground service with thread starts and manager mocked"""
        config_dict = TestWunderground.get_config_dict(wunderground_options)
        engine = mock.Mock()
        with mock.patch('weewx.manager.get_manager_dict_from_config',
                        return_value=None):
            with mock.patch.object(weewx.restx.AmbientThread, 'start') as archive_start:
                with mock.patch.object(weewx.restx.AmbientLoopThread, 'start') as loop_start:
                    service = weewx.restx.StdWunderground(engine, config_dict)
        return service, archive_start, loop_start

    def test_both_modes_with_rtfreq(self):
        """Both modes with an explicit rtfreq: each thread gets its own endpoint"""
        service, archive_start, loop_start = TestWunderground.get_service(
            {'rapidfire': True, 'archive_post': True, 'rtfreq': 9})

        assert service.archive_thread.server_url == weewx.restx.StdWunderground.pws_url
        assert service.loop_thread.server_url == weewx.restx.StdWunderground.rf_url
        assert service.loop_thread.rtfreq == 9.0
        # The archive thread cannot accept rtfreq, so it must not have it set
        assert not hasattr(service.archive_thread, 'rtfreq')
        archive_start.assert_called_once()
        loop_start.assert_called_once()

    def test_rapidfire_only_with_rtfreq(self):
        """Rapidfire-only remains the working configuration, with rtfreq honored"""
        service, archive_start, loop_start = TestWunderground.get_service(
            {'rapidfire': True, 'archive_post': False, 'rtfreq': 9})

        assert not hasattr(service, 'archive_thread')
        assert service.loop_thread.server_url == weewx.restx.StdWunderground.rf_url
        assert service.loop_thread.rtfreq == 9.0
        archive_start.assert_not_called()
        loop_start.assert_called_once()

    def test_both_modes_no_rtfreq(self):
        """Both modes with no rtfreq: the rapidfire thread still gets rf_url"""
        service, _archive_start, _loop_start = TestWunderground.get_service(
            {'rapidfire': True, 'archive_post': True})

        assert service.archive_thread.server_url == weewx.restx.StdWunderground.pws_url
        assert service.loop_thread.server_url == weewx.restx.StdWunderground.rf_url

    def test_archive_only(self):
        """Archive-only posts to the PWS endpoint and ignores rtfreq"""
        service, archive_start, loop_start = TestWunderground.get_service(
            {'rapidfire': False, 'archive_post': True, 'rtfreq': 9})

        assert not hasattr(service, 'loop_thread')
        assert service.archive_thread.server_url == weewx.restx.StdWunderground.pws_url
        assert not hasattr(service.archive_thread, 'rtfreq')
        archive_start.assert_called_once()
        loop_start.assert_not_called()

    def test_user_server_url_is_respected(self):
        """An explicit server_url overrides the default endpoint for both modes"""
        custom_url = 'https://custom.example.com/updateweatherstation.php'
        service, _archive_start, _loop_start = TestWunderground.get_service(
            {'rapidfire': True, 'archive_post': True,
             'server_url': custom_url, 'rtfreq': 9})

        assert service.archive_thread.server_url == custom_url
        assert service.loop_thread.server_url == custom_url
