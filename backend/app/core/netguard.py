import ipaddress
import socket
import threading
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

BLOCKED_MESSAGE = "connection to a non-public address is blocked"


class BlockedAddressError(ConnectionRefusedError):
    def __init__(self, address: str) -> None:
        super().__init__(f"{BLOCKED_MESSAGE}: {address}")


def parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def is_public(address: str) -> bool:
    ip = parse_ip(address)
    return ip is not None and ip.is_global and not ip.is_multicast


def is_blocked(exc: BaseException | None) -> bool:
    seen: set[int] = set()
    stack = [exc]
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, BlockedAddressError) or BLOCKED_MESSAGE in str(current):
            return True
        if isinstance(current, BaseExceptionGroup):
            stack.extend(current.exceptions)
        stack.extend((current.__cause__, current.__context__))
    return False


_original_getaddrinfo = socket.getaddrinfo
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex


def _resolve(host: str) -> set[str]:
    try:
        infos = _original_getaddrinfo(host, None)
    except OSError:
        return set()
    return {str(info[4][0]) for info in infos}


Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_networks(value: str) -> list[Network]:
    return [
        ipaddress.ip_network(item.strip(), strict=False)
        for item in value.split(",")
        if item.strip()
    ]


class Allowlist:
    def __init__(
        self,
        hosts: Iterable[str],
        networks: Iterable[Network] = (),
        *,
        refresh_sec: float = 60.0,
        retry_sec: float = 5.0,
    ) -> None:
        self._hosts = frozenset(host for host in hosts if host)
        self._networks = tuple(networks)
        self._refresh_sec = refresh_sec
        self._retry_sec = retry_sec
        self._lock = threading.Lock()
        self._addresses: frozenset[str] = frozenset()
        self._resolved_at = float("-inf")

    @property
    def hosts(self) -> frozenset[str]:
        return self._hosts

    def allows(self, address: str) -> bool:
        ip = parse_ip(address)
        if ip is not None and any(ip in network for network in self._networks):
            return True
        if self._age() > self._refresh_sec:
            self._refresh()
        if address in self._addresses:
            return True
        # Containers get new IPs on restart, so a miss may just mean the cache is outdated.
        if self._age() > self._retry_sec:
            self._refresh()
            return address in self._addresses
        return False

    def _age(self) -> float:
        return time.monotonic() - self._resolved_at

    def _refresh(self) -> None:
        with self._lock:
            addresses: set[str] = set()
            for host in self._hosts:
                addresses |= _resolve(host)
            self._addresses = frozenset(addresses)
            self._resolved_at = time.monotonic()


_untrusted: ContextVar[bool] = ContextVar("netguard_untrusted", default=False)


@contextmanager
def untrusted() -> Iterator[None]:
    """Mark connections opened inside the block as following a user-supplied URL.

    Our own services (Redis, cobalt) stay reachable for our code but not for those.
    The flag is a context variable, so it follows asyncio.to_thread into yt-dlp.
    """
    token = _untrusted.set(True)
    try:
        yield
    finally:
        _untrusted.reset(token)


class Policy:
    def __init__(self, internal: Allowlist, egress: Allowlist) -> None:
        self.internal = internal
        self.egress = egress

    def _allows(self, ip: str) -> bool:
        if is_public(ip) or self.egress.allows(ip):
            return True
        return not _untrusted.get() and self.internal.allows(ip)

    def check(self, host: str) -> None:
        if parse_ip(host) is None:
            trusted_name = not _untrusted.get() and host in self.internal.hosts
            if trusted_name or host in self.egress.hosts:
                return
            resolved = _resolve(host)
            if resolved and all(self._allows(ip) for ip in resolved):
                return
            raise BlockedAddressError(host)
        if not self._allows(host):
            raise BlockedAddressError(host)


_policy: Policy | None = None


def _check(sock: socket.socket, address: object) -> None:
    if _policy is None or sock.family not in (socket.AF_INET, socket.AF_INET6):
        return
    if isinstance(address, tuple) and address:
        _policy.check(str(address[0]))


def _guarded_connect(self: socket.socket, address: object) -> None:
    _check(self, address)
    return _original_connect(self, address)


def _guarded_connect_ex(self: socket.socket, address: object) -> int:
    _check(self, address)
    return _original_connect_ex(self, address)


def install(
    internal_hosts: Iterable[str],
    egress_hosts: Iterable[str] = (),
    egress_networks: Iterable[Network] = (),
) -> None:
    """Refuse outbound connections to private, loopback and link-local addresses.

    Workers fetch user-supplied URLs, so without this anyone could make them read internal
    services (Redis, cobalt) or the cloud metadata endpoint. Checking at connect() time
    covers every Python HTTP stack in the process (httpx, urllib, requests inside yt-dlp),
    every redirect hop and DNS rebinding. ffmpeg runs as a subprocess and is not covered.

    egress_hosts and egress_networks are reachable even from untrusted() blocks: the
    outbound proxy, and networks of a resolver that hands out fake IPs (Clash or sing-box
    in fake-ip mode answer from 198.18.0.0/15, so every site looks private).
    """
    global _policy
    _policy = Policy(Allowlist(internal_hosts), Allowlist(egress_hosts, egress_networks))
    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]


def uninstall() -> None:
    global _policy
    _policy = None
    socket.socket.connect = _original_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _original_connect_ex  # type: ignore[method-assign]
