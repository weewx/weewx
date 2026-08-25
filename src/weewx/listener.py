#
#    Copyright (c) 2026 Manuel Hilgert
#
#    See the file LICENSE.txt for your full rights.
#
"""Listeners for hardware that pushes its data to WeeWX.

Most drivers poll: they ask the hardware for data and wait for an answer. Some hardware
never answers a request. It posts on its own schedule, and the driver has to be a server.

This module provides that server, so a driver does not have to write one. A driver
creates a listener, then iterates over it:

    from weewx.listener import HTTPListener

    class MyDriver(weewx.drivers.AbstractDevice):

        def __init__(self, **stn_dict):
            self.listener = HTTPListener(**stn_dict)

        def genLoopPackets(self):
            for request in self.listener:
                packet = self.parse(request.body)
                if packet:
                    yield packet

        def closePort(self):
            self.listener.close()

What the listener owns: the socket, the thread, the queue and the shutdown. What it does
not own: the protocol. Parsing the body, mapping fields and assigning units are all the
driver's business, i.e. the parts that differ from one device to the next.

The response is part of the protocol, so it comes from the driver. Many devices treat an
upload as failed until they have read one, e.g. an Ecowitt gateway expects JSON:

    HTTPListener(port=8000, response='{"errcode":"0","errmsg":"ok"}',
                 content_type='application/json')

Hardware that broadcasts instead of posting uses `UDPListener` the same way. Same queue,
same iteration, no response to send.

Options may be passed as strings, so a driver can hand over its configuration stanza
unchanged.
"""

import hmac
import logging
import queue
import socket
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import weewx
from weeutil.weeutil import to_bool, to_int

log = logging.getLogger(__name__)

# How long an idle client may hold a connection open, in seconds.
DEFAULT_SOCKET_TIMEOUT = 20
# Largest request body accepted, in bytes. Weather uploads are a few hundred bytes.
DEFAULT_MAX_BODY = 65536
# How many requests may wait to be picked up before the oldest is dropped.
DEFAULT_QUEUE_SIZE = 10
# How often a blocked iterator looks up to see whether the listener has been closed.
POLL_INTERVAL = 1.0


class Request:
    """A single request, as handed to the driver.

    Attributes:
        method (str): The HTTP method, e.g. 'POST'.
        path (str): The path, without the query, e.g. '/data/report/'.
        query (str): The query string, without the leading '?'. Empty if there was none.
        body (bytes): The request body. Empty for a GET.
        headers (dict): The request headers, with lowercased keys.
        client_address (str): Where the request came from. Taken from 'X-Forwarded-For'
            if the listener was told to trust a proxy, otherwise the peer address.
    """

    __slots__ = ('method', 'path', 'query', 'body', 'headers', 'client_address')

    def __init__(self, method, path, query, body, headers, client_address):
        self.method = method
        self.path = path
        self.query = query
        self.body = body
        self.headers = headers
        self.client_address = client_address

    @property
    def text(self):
        """The body decoded as UTF-8, falling back to the query for a GET.

        Devices split over two protocols here. Ecowitt POSTs a form body, Weather
        Underground clients GET a query string. Both end up in the same place.
        """
        if self.body:
            return self.body.decode('utf-8', 'replace')
        return self.query

    def __str__(self):
        return "%s %s from %s, %d bytes" % (self.method, self.path,
                                            self.client_address, len(self.body))


class Listener:
    """Base class for listeners. Holds the queue and the iteration protocol."""

    def __init__(self, **kwargs):
        # At least one, because a Queue of size zero is an unbounded one, which is
        # the thing this is here to avoid.
        self.queue_size = max(1, to_int(kwargs.get('queue_size', DEFAULT_QUEUE_SIZE)))
        self.queue = queue.Queue(maxsize=self.queue_size)
        self.closed = threading.Event()
        # Number of requests dropped because nobody picked them up in time.
        self.dropped = 0

    def put(self, request):
        """Hand a request to whoever is iterating over this listener.

        If the queue is full, the oldest request is dropped. Current weather beats
        stale weather, and an unbounded queue would grow without limit if the consumer
        ever stalled.
        """
        while True:
            try:
                self.queue.put_nowait(request)
                return
            except queue.Full:
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    # Drained by the consumer in the meantime. Try again.
                    continue
                self.dropped += 1
                log.warning("Queue full. Dropped the oldest request (%d so far).",
                            self.dropped)

    def get(self, timeout=None):
        """Return the next request, or None if none arrived in time.

        Returns None once the listener has been closed. Raises weewx.WeeWxIOError if
        the thread doing the listening has stopped, because from here that is
        indistinguishable from a station that went quiet, and the two need very
        different handling.
        """
        deadline = None if timeout is None else max(0.0, float(timeout))
        while not self.closed.is_set():
            wait = POLL_INTERVAL if deadline is None else min(POLL_INTERVAL, deadline)
            try:
                return self.queue.get(timeout=max(wait, 0.001))
            except queue.Empty:
                self._still_listening()
                if deadline is not None:
                    deadline -= wait
                    if deadline <= 0:
                        return None
        return None

    def _listening(self):
        """Whether this listener is still able to receive anything.

        Subclasses that run a thread say so here.
        """
        return True

    def _still_listening(self):
        """Raise if nothing is filling the queue any more.

        Nothing restarts a listener that has stopped, and a driver waiting on an
        empty queue would wait for good. Better to say so and let the engine decide.
        """
        if not self.closed.is_set() and not self._listening():
            raise weewx.WeeWxIOError("The listener on port %s has stopped"
                                     % getattr(self, 'port', '?'))

    def __iter__(self):
        return self

    def __next__(self):
        request = self.get()
        if request is None:
            raise StopIteration
        return request

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Stop listening. Safe to call more than once."""
        self.closed.set()


class HTTPListener(Listener):
    """Listen for HTTP requests and queue them for a driver.

    The socket is bound in the constructor, so a port that is already in use is reported
    where the driver is created, not later and out of sight in a thread.

    Args:
        port (int): The port to listen on. Default is 80, which needs root.
        address (str): The address to bind to. Default is '', i.e. every interface. Use
            'localhost' when a reverse proxy sits in front.
        path (str): Accept requests for this path only, e.g. '/data/report/'. Anything
            else is answered with a 404. Default is None, i.e. accept every path.
        response (str|bytes|callable): What to send back. A callable is passed the
            Request and returns the body. Default is an empty 200.
        content_type (str): The content type of the response. Default 'text/plain'.
        max_body (int): Largest body accepted, in bytes. Larger requests get a 413.
        socket_timeout (int): How long an idle client may hold a connection.
        allowed_hosts (list): Accept requests from these addresses only. Default is
            empty, i.e. accept from anywhere.
        token (str): Accept a request only if it presents this token, either as query
            parameter 'token', or in header 'X-Auth-Token', or as a bearer token in
            header 'Authorization'. Anything else gets a 403. Default is None, i.e. no
            token is required. A device that cannot set a header or a query parameter
            can carry the token in 'path' instead.
        trust_proxy (bool): Take the client address from 'X-Forwarded-For'. Only set
            this when a proxy you control sets that header. Default False.
        log_raw (bool): Log every request body at debug level. This is what you turn on
            when a sensor is missing from the data.
        queue_size (int): How many requests may wait to be picked up.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.port = to_int(kwargs.get('port', 80))
        self.address = kwargs.get('address', '')
        self.path = kwargs.get('path')
        self.response = kwargs.get('response', '')
        self.content_type = kwargs.get('content_type', 'text/plain')
        self.max_body = to_int(kwargs.get('max_body', DEFAULT_MAX_BODY))
        self.socket_timeout = to_int(kwargs.get('socket_timeout', DEFAULT_SOCKET_TIMEOUT))
        self.allowed_hosts = _as_list(kwargs.get('allowed_hosts'))
        self.token = kwargs.get('token')
        self.trust_proxy = to_bool(kwargs.get('trust_proxy', False))
        self.log_raw = to_bool(kwargs.get('log_raw', False))

        try:
            self.server = _Server(self, self.address, self.port)
        except OSError as e:
            # Almost always a port that something else already holds, e.g. a web server
            # on 80, or a second WeeWX instance. Say so, then let it stop the startup.
            log.error("Cannot listen on %s:%s: %s", self.address or '*', self.port, e)
            raise
        # Report the port the socket actually got. They differ when the caller asked for
        # port 0, i.e. "any free port".
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       name='WeeWX-listener')
        self.thread.daemon = True
        self.thread.start()
        log.info("Listening for HTTP requests on %s:%d", self.address or '*', self.port)

    def _listening(self):
        return self.thread is not None and self.thread.is_alive()

    def get_response(self, request):
        """The body to send back. Override this, or pass 'response' to the constructor."""
        if callable(self.response):
            return self.response(request)
        return self.response

    def close(self):
        """Stop the server and release the port."""
        super().close()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(POLL_INTERVAL * 2)
            self.thread = None
        log.info("Stopped listening on port %d", self.port)


class UDPListener(Listener):
    """Listen for UDP datagrams and queue them for a driver.

    Hardware that broadcasts rather than posts, e.g. WeatherFlow on port 50222 or a
    Davis WeatherLink Live on 22222, ends up here. There is no response to send: a
    datagram is sent once and nobody waits for an answer.

    Args:
        port (int): The port to listen on. Required.
        address (str): The address to bind to. Default is '', i.e. every interface,
            which is what receiving a broadcast usually needs.
        max_body (int): Largest datagram accepted, in bytes.
        allowed_hosts (list): Accept datagrams from these addresses only. Default is
            empty, i.e. accept from anywhere.
        reuse_address (bool): Let other programs on this machine read the same
            broadcasts. Default True, because that is nearly always wanted.
        log_raw (bool): Log every datagram at debug level.
        queue_size (int): How many datagrams may wait to be picked up.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.port = to_int(kwargs.get('port', 0))
        self.address = kwargs.get('address', '')
        self.max_body = to_int(kwargs.get('max_body', DEFAULT_MAX_BODY))
        self.allowed_hosts = _as_list(kwargs.get('allowed_hosts'))
        self.reuse_address = to_bool(kwargs.get('reuse_address', True))
        self.log_raw = to_bool(kwargs.get('log_raw', False))

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((self.address, self.port))
        except OSError as e:
            log.error("Cannot listen on %s:%s: %s", self.address or '*', self.port, e)
            self.socket.close()
            raise
        # So the reading loop comes up for air often enough to notice a close().
        self.socket.settimeout(POLL_INTERVAL)
        self.port = self.socket.getsockname()[1]

        self.thread = threading.Thread(target=self._run, name='WeeWX-listener')
        self.thread.daemon = True
        self.thread.start()
        log.info("Listening for UDP datagrams on %s:%d", self.address or '*', self.port)

    def _listening(self):
        return self.thread is not None and self.thread.is_alive()

    def _run(self):
        while not self.closed.is_set():
            try:
                datagram, sender = self.socket.recvfrom(self.max_body)
            except socket.timeout:
                continue
            except (OSError, AttributeError):
                # The socket was closed under us, and may already be gone. Either way
                # that is how this loop ends.
                return
            if self.allowed_hosts and sender[0] not in self.allowed_hosts:
                log.warning("Rejected a datagram from %s", sender[0])
                continue
            request = Request(method='UDP', path='', query='', body=datagram,
                              headers={}, client_address=sender[0])
            if self.log_raw:
                log.debug("Raw datagram: %s", request.text)
            self.put(request)

    def close(self):
        """Stop listening and release the port."""
        super().close()
        if self.socket is not None:
            # Closing wakes the reading thread. Wait for it before dropping the
            # reference, or it can find self.socket gone mid-call.
            self.socket.close()
            if self.thread is not None:
                self.thread.join(POLL_INTERVAL * 2)
                self.thread = None
            self.socket = None
        log.info("Stopped listening on port %d", self.port)


def _as_list(option):
    """Return an option as a list of strings. configobj may hand over either."""
    if not option:
        return []
    if isinstance(option, str):
        return [x.strip() for x in option.split(',') if x.strip()]
    return [str(x).strip() for x in option]


class _Server(ThreadingHTTPServer):
    """The HTTP server. Knows which listener to hand its requests to."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, listener, address, port):
        self.listener = listener
        # Pick the address family from the address itself, so that an IPv6 address
        # works without any further configuration.
        self.address_family = _address_family(address, port)
        super().__init__((address, port), _Handler)

    def handle_error(self, request, client_address):
        """Log the error rather than printing a traceback to stderr."""
        log.error("Error while handling a request from %s", client_address, exc_info=True)


def _address_family(address, port):
    """Return the address family to use for an address."""
    if not address:
        return socket.AF_INET
    try:
        info = socket.getaddrinfo(address, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return socket.AF_INET
    return info[0][0] if info else socket.AF_INET


class _Handler(BaseHTTPRequestHandler):
    """Turn a request into a Request object and queue it."""

    # HTTP/1.0, so a connection is closed after every response. Devices upload and go.
    protocol_version = 'HTTP/1.0'

    @property
    def timeout(self):
        return self.server.listener.socket_timeout

    def do_GET(self):
        self._handle(b'')

    def do_POST(self):
        listener = self.server.listener
        try:
            length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            self.send_error(400, "Bad Content-Length")
            return
        if length > listener.max_body:
            log.warning("Request from %s is %d bytes, over the limit of %d",
                        self._client_address(), length, listener.max_body)
            self.send_error(413, "Request body too large")
            return
        self._handle(self.rfile.read(length) if length else b'')

    def _handle(self, body):
        listener = self.server.listener
        client = self._client_address()

        if listener.allowed_hosts and client not in listener.allowed_hosts:
            log.warning("Rejected a request from %s", client)
            self.send_error(403, "Forbidden")
            return

        parts = urllib.parse.urlsplit(self.path)
        if listener.path is not None and parts.path.rstrip('/') != listener.path.rstrip('/'):
            self.send_error(404, "Not Found")
            return

        if not self._token_ok(listener, parts.query):
            log.warning("Rejected a request from %s: bad or missing token", client)
            self.send_error(403, "Forbidden")
            return

        request = Request(method=self.command,
                          path=parts.path,
                          query=parts.query,
                          body=body,
                          headers={k.lower(): v for k, v in self.headers.items()},
                          client_address=client)

        if listener.log_raw:
            log.debug("Raw request: %s", request.text)

        # Answer first, then queue. Some devices treat an upload as failed if the
        # response is slow, and a full queue must not hold up the reply.
        try:
            response = listener.get_response(request)
        except Exception as e:
            log.error("Error while building a response: %s", e)
            response = ''
        self._respond(response, listener.content_type)

        listener.put(request)

    def _respond(self, response, content_type):
        if isinstance(response, str):
            response = response.encode('utf-8')
        elif response is None:
            response = b''
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        if response:
            self.wfile.write(response)

    def _token_ok(self, listener, query):
        """Check the token, if one is required.

        Devices differ in what they can send, so look in the three places one can end
        up: a query parameter, our own header, and a bearer token.
        """
        if not listener.token:
            return True
        presented = self.headers.get('X-Auth-Token', '')
        if not presented:
            authorization = self.headers.get('Authorization', '')
            if authorization.startswith('Bearer '):
                presented = authorization[len('Bearer '):].strip()
        if not presented:
            presented = urllib.parse.parse_qs(query).get('token', [''])[0]
        # Constant time, so that a wrong token cannot be found one character at a time.
        return hmac.compare_digest(presented.encode('utf-8'),
                                   str(listener.token).encode('utf-8'))

    def _client_address(self):
        if self.server.listener.trust_proxy:
            forwarded = self.headers.get('X-Forwarded-For')
            if forwarded:
                return forwarded.split(',')[0].strip()
        return self.client_address[0]

    def log_message(self, fmt, *args):
        """Send the server's own chatter to the log instead of stderr."""
        log.debug("%s %s", self.client_address[0], fmt % args)
