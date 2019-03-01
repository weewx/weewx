#
#    Copyright (c) 2019 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
"""Test restx services"""

import time
import unittest
from unittest.mock import patch

from six.moves import queue

import weewx
import weewx.restx


class MatchRequest(object):
    """Allows equality testing against Request objects"""

    def __init__(self, url, user_agent):
        self.url = url
        self.user_agent = user_agent

    def __eq__(self, other):
        # In what follows, we could just return 'False', but raising the AssertionError directly
        # gives a more useful error message.
        if other.full_url != self.url:
            raise AssertionError("Mismatched urls: \nActual:'%s'\nExpect:'%s' " % (other.full_url, self.url))
        if other.headers.get('User-agent') != self.user_agent:
            raise AssertionError("Mismatched user-agent: \nActual:'%s'\nExpect:'%s'"
                                 % (other.headers.get('User-agent'), self.user_agent))
        return True


class TestAmbient(unittest.TestCase):
    """Test the Ambient RESTful protocol"""

    station = 'KBZABCDEF3'
    password = 'somepassword'
    server_url = 'http://www.testserver.com/testapi'

    @patch('weewx.restx.urllib.request.urlopen')
    def test_request(self, mock_urlopen):
        """Test that we are forming the right Request object"""
        q = queue.Queue()
        obj = weewx.restx.AmbientThread(q,
                                        manager_dict=None,
                                        station=TestAmbient.station,
                                        password=TestAmbient.password,
                                        server_url=TestAmbient.server_url,
                                        )
        ts = time.mktime(time.strptime("2018-03-22", "%Y-%m-%d"))
        record = {'dateTime': ts,
                  'usUnits': weewx.US,
                  'interval': 5,
                  'outTemp': 20.0,
                  'barometer': 30.1
                  }
        q.put(record)
        obj.run()

        matcher = MatchRequest('%s?action=updateraw&ID=%s&PASSWORD=%s&softwaretype=weewx-%s'
                               '&dateutc=2018-03-22%%2007%%3A00%%3A00'
                               '&baromin=30.100&tempf=20.0'
                               % (TestAmbient.server_url,
                                  TestAmbient.station,
                                  TestAmbient.password,
                                  weewx.__version__),
                               'weewx/%s' % weewx.__version__)

        mock_urlopen.assert_called_once_with(matcher, data=None, timeout=10)


if __name__ == '__main__':
    unittest.main()
