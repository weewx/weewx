#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Test module weewx.listener"""

import http.client
import queue
import time

import pytest

from weewx.listener import HTTPListener, Request

ECOWITT_BODY = ("PASSKEY=ABC&stationtype=GW1000B_V1.5.5&dateutc=2026-08-25+11:29:50"
                "&tempinf=67.1&humidityin=39&baromrelin=30.138")


@pytest.fixture
def make_listener():
    """Hand out listeners on a free port, and close them afterwards."""
    made = []

    def _make(**kwargs):
        kwargs.setdefault('port', 0)
        kwargs.setdefault('address', '127.0.0.1')
        listener = HTTPListener(**kwargs)
        made.append(listener)
        return listener

    yield _make

    for listener in made:
        listener.close()


def send(listener, method='POST', path='/', body=None, headers=None):
    """Send one request. Returns (status, response body)."""
    conn = http.client.HTTPConnection('127.0.0.1', listener.port, timeout=5)
    try:
        conn.request(method, path, body, headers or {})
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def test_post_arrives(make_listener):
    listener = make_listener()
    status, _ = send(listener, body=ECOWITT_BODY)
    assert status == 200

    request = listener.get(timeout=5)
    assert request is not None
    assert request.method == 'POST'
    assert request.path == '/'
    assert request.body == ECOWITT_BODY.encode('utf-8')
    assert request.text == ECOWITT_BODY
    assert request.client_address == '127.0.0.1'


def test_get_carries_the_query(make_listener):
    """A Weather Underground client uses GET, and the data are in the query."""
    listener = make_listener()
    status, _ = send(listener, method='GET',
                     path='/weatherstation/updateweatherstation.php?tempf=61.0&humidity=82')
    assert status == 200

    request = listener.get(timeout=5)
    assert request.method == 'GET'
    assert request.path == '/weatherstation/updateweatherstation.php'
    assert request.query == 'tempf=61.0&humidity=82'
    # 'text' falls back to the query, so a parser can use it for either protocol.
    assert request.text == 'tempf=61.0&humidity=82'


def test_iteration(make_listener):
    listener = make_listener()
    send(listener, body='first')
    send(listener, body='second')

    collected = []
    for request in listener:
        collected.append(request.text)
        if len(collected) == 2:
            break
    assert collected == ['first', 'second']


def test_iteration_stops_when_closed(make_listener):
    listener = make_listener()
    listener.close()
    assert list(listener) == []


def test_static_response(make_listener):
    listener = make_listener(response='{"errcode":"0","errmsg":"ok"}',
                             content_type='application/json')
    status, body = send(listener, body=ECOWITT_BODY)
    assert status == 200
    assert body == b'{"errcode":"0","errmsg":"ok"}'


def test_callable_response(make_listener):
    listener = make_listener(response=lambda request: "saw %d bytes" % len(request.body))
    _, body = send(listener, body='12345')
    assert body == b'saw 5 bytes'


def test_response_error_does_not_kill_the_request(make_listener):
    """A driver that raises while building a response still gets its data."""

    def explode(_request):
        raise ValueError("no response for you")

    listener = make_listener(response=explode)
    status, body = send(listener, body=ECOWITT_BODY)
    assert status == 200
    assert body == b''
    assert listener.get(timeout=5).text == ECOWITT_BODY


def test_path_filter(make_listener):
    listener = make_listener(path='/data/report/')

    status, _ = send(listener, path='/somewhere/else', body=ECOWITT_BODY)
    assert status == 404

    status, _ = send(listener, path='/data/report/', body=ECOWITT_BODY)
    assert status == 200
    # A trailing slash is not a difference worth a 404.
    status, _ = send(listener, path='/data/report', body=ECOWITT_BODY)
    assert status == 200

    assert listener.queue.qsize() == 2


def test_body_over_the_limit_is_refused(make_listener):
    listener = make_listener(max_body=64)
    status, _ = send(listener, body='x' * 65)
    assert status == 413
    assert listener.get(timeout=0.5) is None


def test_bad_content_length(make_listener):
    listener = make_listener()
    status, _ = send(listener, body=ECOWITT_BODY, headers={'Content-Length': 'garbage'})
    assert status == 400


def test_allowed_hosts(make_listener):
    listener = make_listener(allowed_hosts='192.168.1.5')
    status, _ = send(listener, body=ECOWITT_BODY)
    assert status == 403
    assert listener.get(timeout=0.5) is None


def test_allowed_hosts_as_a_list(make_listener):
    """configobj hands over a list when the option holds a comma."""
    listener = make_listener(allowed_hosts=['192.168.1.5', '127.0.0.1'])
    status, _ = send(listener, body=ECOWITT_BODY)
    assert status == 200


def test_token_in_the_query(make_listener):
    listener = make_listener(token='s3cret')
    status, _ = send(listener, path='/?token=s3cret', body=ECOWITT_BODY)
    assert status == 200
    assert listener.get(timeout=5) is not None


def test_token_in_a_header(make_listener):
    listener = make_listener(token='s3cret')
    status, _ = send(listener, body=ECOWITT_BODY, headers={'X-Auth-Token': 's3cret'})
    assert status == 200


def test_token_as_a_bearer(make_listener):
    listener = make_listener(token='s3cret')
    status, _ = send(listener, body=ECOWITT_BODY,
                     headers={'Authorization': 'Bearer s3cret'})
    assert status == 200


def test_wrong_token(make_listener):
    listener = make_listener(token='s3cret')
    status, _ = send(listener, path='/?token=wrong', body=ECOWITT_BODY)
    assert status == 403
    assert listener.get(timeout=0.5) is None


def test_missing_token(make_listener):
    listener = make_listener(token='s3cret')
    status, _ = send(listener, body=ECOWITT_BODY)
    assert status == 403


def test_no_token_required(make_listener):
    listener = make_listener()
    status, _ = send(listener, body=ECOWITT_BODY, headers={'X-Auth-Token': 'anything'})
    assert status == 200


def test_token_with_non_ascii(make_listener):
    """A token outside ASCII must not crash the comparison."""
    listener = make_listener(token='grün')
    status, _ = send(listener, body=ECOWITT_BODY, headers={'X-Auth-Token': 'grün'})
    assert status == 200
    status, _ = send(listener, body=ECOWITT_BODY, headers={'X-Auth-Token': 'blau'})
    assert status == 403


def test_token_in_the_path(make_listener):
    """A device that can only be given a URL carries its token in the path."""
    listener = make_listener(path='/a8f3c1/report')
    status, _ = send(listener, path='/a8f3c1/report', body=ECOWITT_BODY)
    assert status == 200
    status, _ = send(listener, path='/report', body=ECOWITT_BODY)
    assert status == 404


def test_trust_proxy(make_listener):
    listener = make_listener(trust_proxy=True)
    send(listener, body=ECOWITT_BODY, headers={'X-Forwarded-For': '10.0.0.9, 10.0.0.1'})
    assert listener.get(timeout=5).client_address == '10.0.0.9'


def test_proxy_header_ignored_unless_trusted(make_listener):
    listener = make_listener()
    send(listener, body=ECOWITT_BODY, headers={'X-Forwarded-For': '10.0.0.9'})
    assert listener.get(timeout=5).client_address == '127.0.0.1'


def test_options_may_be_strings(make_listener):
    """A driver hands over its configuration stanza, where everything is a string."""
    listener = make_listener(max_body='64', queue_size='3', trust_proxy='true',
                             log_raw='false', socket_timeout='5')
    assert listener.max_body == 64
    assert listener.queue_size == 3
    assert listener.trust_proxy is True
    assert listener.log_raw is False

    status, _ = send(listener, body='x' * 65)
    assert status == 413


def test_full_queue_drops_the_oldest(make_listener):
    listener = make_listener(queue_size=2)
    for i in range(4):
        send(listener, body=str(i))

    # Wait for the last one to be queued before looking.
    deadline = time.time() + 5
    while listener.dropped < 2 and time.time() < deadline:
        time.sleep(0.05)

    assert listener.dropped == 2
    assert [listener.get(timeout=1).text for _ in range(2)] == ['2', '3']


def test_get_returns_none_on_timeout(make_listener):
    listener = make_listener()
    start = time.time()
    assert listener.get(timeout=0.2) is None
    assert time.time() - start < 5


def test_close_releases_the_port(make_listener):
    listener = make_listener()
    port = listener.port
    listener.close()
    # Closing twice is not an error.
    listener.close()

    with pytest.raises(OSError):
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
        conn.request('POST', '/', ECOWITT_BODY)
        conn.getresponse()


def test_context_manager():
    with HTTPListener(port=0, address='127.0.0.1') as listener:
        assert listener.port != 0
        port = listener.port
    with pytest.raises(OSError):
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
        conn.request('POST', '/', ECOWITT_BODY)
        conn.getresponse()


def test_port_in_use():
    """A port that is already taken is reported where the driver is built."""
    first = HTTPListener(port=0, address='127.0.0.1')
    try:
        with pytest.raises(OSError):
            HTTPListener(port=first.port, address='127.0.0.1')
    finally:
        first.close()


def test_request_str():
    request = Request('POST', '/data/report/', '', b'abc', {}, '10.0.0.9')
    assert str(request) == "POST /data/report/ from 10.0.0.9, 3 bytes"


def test_queue_is_not_unbounded(make_listener):
    listener = make_listener(queue_size=1)
    assert isinstance(listener.queue, queue.Queue)
    assert listener.queue.maxsize == 1
