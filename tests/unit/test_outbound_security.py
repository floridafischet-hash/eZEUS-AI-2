from unittest.mock import patch

import httpx
import pytest

from core.config.settings import Settings
from core.security.outbound import (
    DisallowedOutboundHost,
    DownloadTooLargeError,
    stream_capped,
    validate_outbound_url,
)


def _settings(**overrides: object) -> Settings:
    values = {
        "paperless_base_url": "https://paperless.example.test",
        "ollama_base_url": "http://ollama:11434",
        "outbound_allowed_hosts": ("paperless.example.test", "ollama"),
    }
    values.update(overrides)  # type: ignore[arg-type]
    return Settings(**values)  # type: ignore[arg-type]


def test_allows_host_from_settings() -> None:
    with patch("core.security.outbound.resolve_hosts", return_value=["203.0.113.10"]):
        validate_outbound_url("https://paperless.example.test/api", settings=_settings())


def test_rejects_unknown_host() -> None:
    with pytest.raises(DisallowedOutboundHost):
        validate_outbound_url("https://evil.example.com/x", settings=_settings())


def test_rejects_non_http_scheme() -> None:
    with pytest.raises(DisallowedOutboundHost):
        validate_outbound_url("file:///etc/passwd", settings=_settings())


def test_blocks_dns_rebind_to_private_ip() -> None:
    settings = _settings(outbound_allowed_hosts=("paperless.example.test",))
    with (
        patch(
            "core.security.outbound.resolve_hosts",
            return_value=["10.0.0.1"],
        ),
        pytest.raises(DisallowedOutboundHost),
    ):
        validate_outbound_url("https://paperless.example.test/", settings=settings)


def test_single_label_cluster_service_allows_private_cluster_ip() -> None:
    # Kubernetes service DNS names ("ollama", "postgres") resolve to private
    # cluster IPs and must not be blocked after DNS safety inspection.
    settings = _settings(outbound_allowed_hosts=("ollama",))
    with patch("core.security.outbound.resolve_hosts", return_value=["10.96.0.42"]):
        validate_outbound_url("http://ollama:11434/api/tags", settings=settings)


def test_single_label_alias_cannot_hide_loopback() -> None:
    settings = _settings(outbound_allowed_hosts=("ip6-localhost",))
    with (
        patch("core.security.outbound.resolve_hosts", return_value=["::1"]),
        pytest.raises(DisallowedOutboundHost, match="forbidden address"),
    ):
        validate_outbound_url("http://ip6-localhost/api", settings=settings)


@pytest.mark.parametrize("host", ["127.0.0.1", "[::1]", "[::ffff:127.0.0.1]"])
def test_address_literal_cannot_bypass_forbidden_networks(host: str) -> None:
    allowed_host = host.removeprefix("[").removesuffix("]")
    settings = _settings(
        paperless_base_url=f"http://{host}",
        outbound_allowed_hosts=(allowed_host,),
        outbound_private_allowed_hosts=(allowed_host,),
    )
    with pytest.raises(DisallowedOutboundHost, match="forbidden address"):
        validate_outbound_url(f"http://{host}/api", settings=settings)


def test_block_can_be_disabled() -> None:
    settings = _settings(
        outbound_allowed_hosts=("paperless.example.test",),
        outbound_block_private_networks=False,
    )
    with patch(
        "core.security.outbound.resolve_hosts",
        return_value=["10.0.0.1"],
    ):
        validate_outbound_url("https://paperless.example.test/", settings=settings)


def test_private_host_requires_operator_private_allowlist() -> None:
    settings = _settings(
        outbound_allowed_hosts=("paperless.internal.example",),
        outbound_private_allowed_hosts=("paperless.internal.example",),
    )
    with patch("core.security.outbound.resolve_hosts", return_value=["10.20.30.40"]):
        validate_outbound_url("https://paperless.internal.example/", settings=settings)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "169.254.169.254",
        "100.100.100.200",
        "::1",
        "fe80::1",
        "fd00:ec2::254",
        "::ffff:127.0.0.1",
    ],
)
def test_private_allowlist_never_allows_loopback_or_link_local(address: str) -> None:
    settings = _settings(
        outbound_allowed_hosts=("paperless.internal.example",),
        outbound_private_allowed_hosts=("paperless.internal.example",),
    )
    with (
        patch("core.security.outbound.resolve_hosts", return_value=[address]),
        pytest.raises(DisallowedOutboundHost, match="forbidden address"),
    ):
        validate_outbound_url("https://paperless.internal.example/", settings=settings)


@pytest.mark.asyncio
async def test_stream_capped_aborts_on_content_length() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-length": "9999"}, content=b"x" * 9999)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DownloadTooLargeError):
            await stream_capped(client, "GET", "https://x/a", max_bytes=100)


@pytest.mark.asyncio
async def test_stream_capped_aborts_when_body_exceeds_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 5000)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DownloadTooLargeError):
            await stream_capped(client, "GET", "https://x/a", max_bytes=1000)
