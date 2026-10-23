import socket
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from app.core import netguard
from app.core.errors import ErrorCode
from app.engines.http_download import transport_error

needs_selector_loop = pytest.mark.skipif(
    sys.platform == "win32", reason="the proactor loop connects without socket.connect"
)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.5",
        "172.18.0.3",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "::1",
        "fe80::1",
        "fd00::1",
        "::ffff:10.0.0.1",
        "224.0.0.1",
        "not-an-ip",
    ],
)
def test_non_public_addresses_are_rejected(address):
    assert not netguard.is_public(address)


@pytest.mark.parametrize("address", ["1.1.1.1", "142.250.74.14", "2606:4700:4700::1111"])
def test_public_addresses_are_accepted(address):
    assert netguard.is_public(address)


def test_allowlist_permits_resolved_internal_hosts():
    allowlist = netguard.Allowlist(["localhost"])
    netguard.check_address("localhost", allowlist)
    netguard.check_address("127.0.0.1", allowlist)
    with pytest.raises(netguard.BlockedAddressError):
        netguard.check_address("10.1.2.3", allowlist)


def test_is_blocked_walks_causes_and_groups():
    inner = netguard.BlockedAddressError("10.0.0.1")
    try:
        try:
            raise ExceptionGroup("attempts", [OSError("other"), inner])
        except ExceptionGroup as group:
            raise OSError("All connection attempts failed") from group
    except OSError as outer:
        assert netguard.is_blocked(outer)
    assert not netguard.is_blocked(OSError("refused"))


def test_transport_error_maps_blocked_connections_to_forbidden():
    blocked = httpx.ConnectError("x")
    blocked.__cause__ = netguard.BlockedAddressError("10.0.0.1")
    assert transport_error(blocked).code is ErrorCode.FORBIDDEN
    assert transport_error(httpx.ConnectError("refused")).code is ErrorCode.NETWORK


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"secret")

    def log_message(self, *args):
        pass


@pytest.fixture
def local_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


@pytest.fixture
def guard():
    netguard.install([])
    yield
    netguard.uninstall()


@pytest.fixture
async def async_guard():
    # Windows builds the event loop's self-pipe over loopback TCP, so install after it exists.
    netguard.install([])
    yield
    netguard.uninstall()


def test_local_server_is_reachable_without_guard(local_server):
    assert httpx.get(local_server).text == "secret"


def test_guard_blocks_httpx(local_server, guard):
    with pytest.raises(httpx.ConnectError) as info:
        httpx.get(local_server)
    assert netguard.is_blocked(info.value)


def test_guard_blocks_urllib_used_by_ytdlp(local_server, guard):
    with pytest.raises(urllib.error.URLError) as info:
        urllib.request.urlopen(local_server, timeout=5)
    assert netguard.is_blocked(info.value)


def test_guard_blocks_hostnames_resolving_to_private_addresses(local_server, guard):
    with pytest.raises(OSError) as info:
        socket.create_connection(("localhost", int(local_server.rsplit(":", 1)[1].strip("/"))))
    assert netguard.is_blocked(info.value)


@needs_selector_loop
async def test_guard_blocks_async_httpx(local_server, async_guard):
    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.ConnectError) as info:
            await client.get(local_server)
    assert netguard.is_blocked(info.value)


def test_guard_keeps_allowlisted_hosts_reachable(local_server):
    netguard.install(["localhost"])
    try:
        assert httpx.get(local_server).text == "secret"
    finally:
        netguard.uninstall()


def test_ytdlp_errors_from_blocked_connections_map_to_forbidden():
    from app.engines.ytdlp import map_ytdlp_error

    exc = Exception(
        f"ERROR: Unable to download webpage: <urlopen error {netguard.BLOCKED_MESSAGE}: 10.0.0.1>"
    )
    assert map_ytdlp_error(exc).code is ErrorCode.FORBIDDEN


async def test_ytdlp_probe_of_internal_url_fails_as_forbidden(local_server, async_guard):
    from app.core.errors import EngineError
    from app.engines.ytdlp import YtDlpEngine

    with pytest.raises(EngineError) as info:
        await YtDlpEngine().probe(local_server)
    assert info.value.code is ErrorCode.FORBIDDEN


@needs_selector_loop
async def test_direct_probe_of_internal_url_fails_as_forbidden(local_server, async_guard):
    from app.core.errors import EngineError
    from app.engines.direct import DirectEngine

    with pytest.raises(EngineError) as info:
        await DirectEngine().probe(local_server)
    assert info.value.code is ErrorCode.FORBIDDEN
