"""FeedHandler must not hang on a server that accepts but never answers."""

import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from util import feedhandler
from util.feedhandler import FeedHandler

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>
<item><title>A</title><link>https://example.com/a</link>
<pubDate>Wed, 23 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>B</title><link>https://example.com/b</link>
<pubDate>Thu, 24 Sep 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


@pytest.fixture
def silent_server():
    """Accepts TCP connections and never sends a byte."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    conns = []
    stop = threading.Event()

    def accept():
        sock.settimeout(0.1)
        while not stop.is_set():
            try:
                conns.append(sock.accept()[0])
            except socket.timeout:
                pass

    t = threading.Thread(target=accept, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{sock.getsockname()[1]}/feed"
    stop.set()
    t.join()
    for c in conns:
        c.close()
    sock.close()


@pytest.fixture
def rss_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml")
            self.end_headers()
            self.wfile.write(RSS)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{server.server_port}/feed"
    server.shutdown()
    server.server_close()


async def test_parse_feed_times_out_on_silent_server(silent_server):
    with patch.object(feedhandler, "FEED_TIMEOUT_SECONDS", 0.5):
        start = time.monotonic()
        entries = await FeedHandler.parse_feed(silent_server, entries=4)
    assert entries == []
    assert time.monotonic() - start < 3


async def test_is_parsable_times_out_on_silent_server(silent_server):
    with patch.object(feedhandler, "FEED_TIMEOUT_SECONDS", 0.5):
        start = time.monotonic()
        assert await FeedHandler.is_parsable(silent_server) is False
    assert time.monotonic() - start < 3


async def test_parse_feed_reads_rss(rss_server):
    entries = await FeedHandler.parse_feed(rss_server, entries=4)
    assert [e["link"] for e in entries] == ["https://example.com/b", "https://example.com/a"]
    assert await FeedHandler.is_parsable(rss_server) is True


@pytest.fixture
def http_server():
    """Serves a fixed (status, body) set by the test."""
    reply = {"status": 200, "body": RSS}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(reply["status"])
            self.send_header("Content-Type", "application/rss+xml")
            self.end_headers()
            self.wfile.write(reply["body"])

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{server.server_port}/feed", reply
    server.shutdown()
    server.server_close()


async def test_status_ok(http_server):
    url, _ = http_server
    entries, error = await FeedHandler.parse_feed_with_status(url)
    assert error is None
    assert len(entries) == 2


async def test_status_http_error(http_server):
    url, reply = http_server
    reply["status"], reply["body"] = 404, b"not found"
    assert await FeedHandler.parse_feed_with_status(url) == ([], "HTTP 404")


async def test_status_empty_feed(http_server):
    url, reply = http_server
    reply["body"] = b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'
    assert await FeedHandler.parse_feed_with_status(url) == ([], "vazio")


async def test_status_timeout(silent_server):
    with patch.object(feedhandler, "FEED_TIMEOUT_SECONDS", 0.5):
        assert await FeedHandler.parse_feed_with_status(silent_server) == ([], "timeout")


async def test_status_connection_refused():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()  # nothing listening on this port now
    entries, error = await FeedHandler.parse_feed_with_status(f"http://127.0.0.1:{port}/feed")
    assert (entries, error) == ([], "erro de conexão")
