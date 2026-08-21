from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import httpx

from core.config.settings import Settings, get_settings


class OutboundRequestError(RuntimeError):
    pass


class DisallowedOutboundHost(OutboundRequestError):
    pass


class DownloadTooLargeError(OutboundRequestError):
    def __init__(self, url: str, limit: int) -> None:
        super().__init__(f"Download from {url} exceeds {limit} bytes")
        self.limit = limit


_PRIVATE_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("fc00::/7"),
)

# These destinations are unsafe even when an operator explicitly allows a
# private Paperless host.  In particular, cloud metadata endpoints must never
# become reachable through the generic private-host escape hatch.
_NEVER_ALLOWED_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.100.100.200/32"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fd00:ec2::254/128"),
    ipaddress.ip_network("ff00::/8"),
)


def resolve_hosts(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise DisallowedOutboundHost(f"DNS resolution failed for {host}: {exc}") from exc
    return sorted({str(info[4][0]) for info in infos})


def is_private_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip in net for net in _PRIVATE_NETWORKS)


def is_never_allowed_address(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip in net for net in _NEVER_ALLOWED_NETWORKS)


def _allowed_hosts_from_settings(settings: Settings) -> set[str]:
    hosts: set[str] = set(host.lower() for host in settings.outbound_allowed_hosts)
    for url in (settings.paperless_base_url, settings.ollama_base_url):
        parsed = urlparse(url)
        if parsed.hostname:
            hosts.add(parsed.hostname.lower())
    return hosts


def _matches_allowlist(hostname: str, allowlist: Iterable[str]) -> bool:
    host = hostname.lower()
    for entry in allowlist:
        entry_l = entry.lower()
        if entry_l.startswith("."):
            if host.endswith(entry_l):
                return True
        elif host == entry_l:
            return True
    return False


def validate_outbound_url(
    url: str,
    *,
    extra_allowed_hosts: Iterable[str] | None = None,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise DisallowedOutboundHost(f"Unsupported URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise DisallowedOutboundHost("Missing hostname in URL")
    if parsed.username is not None or parsed.password is not None:
        raise DisallowedOutboundHost("Credentials in outbound URLs are not allowed")

    allowlist = _allowed_hosts_from_settings(settings)
    if extra_allowed_hosts:
        allowlist.update(host.lower() for host in extra_allowed_hosts if host)
    if not _matches_allowlist(parsed.hostname, allowlist):
        raise DisallowedOutboundHost(
            f"Outbound host '{parsed.hostname}' is not in the allowed list"
        )
    if parsed.hostname in {"localhost"}:
        raise DisallowedOutboundHost("Requests to localhost are blocked")

    try:
        literal_address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal_address = None

    if literal_address is not None:
        # Address literals must always pass the forbidden/private-network
        # checks. In particular, IPv6 literals contain no dot and must not be
        # mistaken for Kubernetes single-label service names.
        addresses = [str(literal_address)]
        private_service_name = False
    else:
        # Single-label Kubernetes service names may resolve to a private
        # ClusterIP, but DNS is still inspected so aliases cannot hide a
        # forbidden loopback/link-local destination.
        private_service_name = "." not in parsed.hostname
        addresses = resolve_hosts(parsed.hostname)

    private_allowlist = settings.outbound_private_allowed_hosts
    for address in addresses:
        if is_never_allowed_address(address):
            raise DisallowedOutboundHost(
                f"Host {parsed.hostname} resolves to forbidden address {address}"
            )
        if (
            settings.outbound_block_private_networks
            and is_private_address(address)
            and not private_service_name
            and not _matches_allowlist(parsed.hostname, private_allowlist)
        ):
            raise DisallowedOutboundHost(
                f"Host {parsed.hostname} resolves to private address {address}"
            )


async def stream_capped(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_bytes: int,
    **kwargs: Any,
) -> tuple[httpx.Response, bytes]:
    """Perform an HTTP request and stream the body into memory with a hard cap.

    Raises ``DownloadTooLargeError`` as soon as the cap is exceeded, without
    reading further from the wire. Content-Length is honoured up front when
    the server sends it.
    """
    async with client.stream(method, url, **kwargs) as response:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = 0
            if declared > max_bytes:
                await response.aclose()
                raise DownloadTooLargeError(url, max_bytes)
        buffer = bytearray()
        async for chunk in response.aiter_bytes():
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                await response.aclose()
                raise DownloadTooLargeError(url, max_bytes)
        body = bytes(buffer)
        buffered_response = httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=body,
            request=response.request,
            extensions=response.extensions,
        )
        return buffered_response, body
