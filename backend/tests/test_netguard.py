import json
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


def test_internal_hosts_are_reachable_only_outside_untrusted_blocks():
    policy = netguard.Policy(netguard.Allowlist(["localhost"]), netguard.Allowlist([]))
    policy.check("localhost")
    policy.check("127.0.0.1")
    with pytest.raises(netguard.BlockedAddressError):
        policy.check("10.1.2.3")
    with netguard.untrusted():
        for host in ("localhost", "127.0.0.1"):
            with pytest.raises(netguard.BlockedAddressError):
                policy.check(host)
    policy.check("127.0.0.1")


def test_egress_allowlist_applies_inside_untrusted_blocks():
    egress = netguard.Allowlist(
        ["localhost"], netguard.parse_networks("198.18.0.0/15, 10.9.0.0/16")
    )
    policy = netguard.Policy(netguard.Allowlist([]), egress)
    with netguard.untrusted():
        for host in ("198.18.0.127", "10.9.1.1", "localhost", "127.0.0.1", "1.1.1.1"):
            policy.check(host)
        with pytest.raises(netguard.BlockedAddressError):
            policy.check("10.8.1.1")


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

    def do_POST(self):
        # Answers like cobalt does for a redirect: hands the requested URL back to download.
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        body = json.dumps({"status": "redirect", "url": request["url"]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

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
    # localhost counts as one of our services here: user URLs must still not reach it.
    netguard.install(["localhost"])
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
        with netguard.untrusted(), pytest.raises(httpx.ConnectError) as info:
            await client.get(local_server)
    assert netguard.is_blocked(info.value)


def test_guard_keeps_internal_hosts_reachable_for_our_code_only(local_server):
    netguard.install(["localhost"])
    try:
        assert httpx.get(local_server).text == "secret"
        with netguard.untrusted(), pytest.raises(httpx.ConnectError):
            httpx.get(local_server)
    finally:
        netguard.uninstall()


def test_ytdlp_errors_from_blocked_connections_map_to_forbidden():
    from app.engines.ytdlp import map_ytdlp_error

    exc = Exception(
        f"ERROR: Unable to download webpage: <urlopen error {netguard.BLOCKED_MESSAGE}: 10.0.0.1>"
    )
    error = map_ytdlp_error(exc)
    assert error.code is ErrorCode.FORBIDDEN
    assert error.message == netguard.BLOCKED_MESSAGE


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


def _cobalt_on(local_server):
    from app.engines.cobalt import CobaltEngine

    port = local_server.rsplit(":", 1)[1].strip("/")
    return CobaltEngine(f"http://localhost:{port}"), port


def _options(tmp_path):
    from app.engines.base import DownloadOptions
    from app.models import Preset

    return DownloadOptions(Preset.BEST, tmp_path, max_duration_sec=100, max_filesize_bytes=1000)


@needs_selector_loop
async def test_cobalt_downloads_its_own_tunnels(local_server, async_guard, tmp_path):
    engine, port = _cobalt_on(local_server)
    [path] = await engine.download(
        f"http://localhost:{port}/tunnel", _options(tmp_path), lambda p: None
    )
    assert path.read_bytes() == b"secret"


@needs_selector_loop
async def test_cobalt_redirects_to_internal_addresses_fail_as_forbidden(
    local_server, async_guard, tmp_path
):
    from app.core.errors import EngineError

    engine, port = _cobalt_on(local_server)
    with pytest.raises(EngineError) as info:
        await engine.download(f"http://127.0.0.1:{port}/file", _options(tmp_path), lambda p: None)
    assert info.value.code is ErrorCode.FORBIDDEN
