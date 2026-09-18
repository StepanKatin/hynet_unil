from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from control_panel.models import ProxyServer
from control_panel.probe import http_probe_via_socks, probe_target_host, probe_tcp_batch, tcp_ping


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_ping_localhost():
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        ok, ms = await tcp_ping("127.0.0.1", port, timeout=1.0)
        assert ok is True
        assert ms is not None and ms >= 0
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tcp_ping_closed_port():
    ok, ms = await tcp_ping("127.0.0.1", 1, timeout=0.3)
    assert ok is False
    assert ms is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_probe_tcp_batch_marks_servers():
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        nodes = [
            ProxyServer(protocol="ss", name="up", host="127.0.0.1", port=port),
            ProxyServer(protocol="ss", name="down", host="127.0.0.1", port=1),
        ]
        await probe_tcp_batch(nodes, timeout=0.5)
        assert nodes[0].tcp_ok is True
        assert nodes[0].latency_ms is not None
        assert nodes[1].tcp_ok is False
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.unit
def test_probe_target_host():
    assert probe_target_host("https://api.telegram.org/bot") == "api.telegram.org"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_http_probe_via_socks_success_mocked():
    response = MagicMock()
    response.status_code = 302

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.return_value = response

    with patch("control_panel.probe.httpx.AsyncClient", return_value=mock_client):
        ok, ms = await http_probe_via_socks(
            socks_host="0.0.0.0",
            socks_port=1080,
            url="https://api.telegram.org",
            timeout=2.0,
        )
    assert ok is True
    assert ms is not None
    mock_client.get.assert_awaited()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_http_probe_via_socks_treats_5xx_as_fail():
    response = MagicMock()
    response.status_code = 502

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.return_value = response

    with patch("control_panel.probe.httpx.AsyncClient", return_value=mock_client):
        ok, ms = await http_probe_via_socks(
            socks_host="127.0.0.1",
            socks_port=1080,
            url="https://api.telegram.org",
            timeout=2.0,
        )
    assert ok is False
    assert ms is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_http_probe_via_socks_exception():
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.side_effect = httpx.ConnectError("boom")

    with patch("control_panel.probe.httpx.AsyncClient", return_value=mock_client):
        ok, ms = await http_probe_via_socks(
            socks_host="127.0.0.1",
            socks_port=1080,
            url="https://api.telegram.org",
            timeout=2.0,
        )
    assert ok is False
    assert ms is None
