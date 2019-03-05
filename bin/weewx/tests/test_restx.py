#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test restx services"""

import time
import unittest

try:
    # Python 3 --- mock is included in unittest
    from unittest import mock
except ImportError:
    # Python 2 --- must have mock installed
    import mock

from six.moves import queue
from six.moves import urllib

import weewx
import weewx.restx


class MatchRequest(object):
    """Allows equality testing between Request objects"""

    def __init__(self, url, user_agent):
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


class TestAmbient(unittest.TestCase):
    """Test the Ambient RESTful protocol"""

    station = 'KBZABCDEF3'
    password = 'somepassword'
    server_url = 'http://www.testserver.com/testapi'

    def get_patcher(self, code=200, response_body=[]):
        """Get a patch object for a post to urllib.request.urlopen

        code: The response code that should be returned by the mock urlopen

        response_body: The response body that should be returned by the mock urlopen
        """
        # Mock up the urlopen
        patcher = mock.patch('weewx.restx.urllib.request.urlopen')
        mock_urlopen = patcher.start()
        # Set up its return value
        mock_urlopen.return_value = mock.MagicMock(name='urlopen return value')
        mock_urlopen.return_value.code = code
        mock_urlopen.return_value.__iter__.return_value = iter(response_body)
        # This will insure that patcher.stop() will get called
        self.addCleanup(patcher.stop)
        return mock_urlopen

    def test_request(self):
        """Test that we are forming the right Request object"""

        mock_urlopen = self.get_patcher()
        q = queue.Queue()
        obj = weewx.restx.AmbientThread(q,
                                        manager_dict=None,
                                        station=TestAmbient.station,
                                        password=TestAmbient.password,
                                        server_url=TestAmbient.server_url,
                                        )
        record = get_record()
        q.put(record)
        q.put(None)
        obj.run()

        matcher = TestAmbient.get_matcher(TestAmbient.server_url, TestAmbient.station, TestAmbient.password)
        mock_urlopen.assert_called_once_with(matcher, data=None, timeout=10)

    @staticmethod
    def get_matcher(server_url, station, password):
        matcher = MatchRequest('%s?action=updateraw&ID=%s&PASSWORD=%s&softwaretype=weewx-%s'
                               '&dateutc=2018-03-22%%2007%%3A00%%3A00'
                               '&baromin=30.100&tempf=20.0'
                               % (server_url, station, password, weewx.__version__),
                               'weewx/%s' % weewx.__version__)
        return matcher


if __name__ == '__main__':
    unittest.main()
