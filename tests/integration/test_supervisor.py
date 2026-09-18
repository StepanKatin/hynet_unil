from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from control_panel.models import ProxyServer
from control_panel.settings import Settings
from control_panel.supervisor import Supervisor


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        subscription_url="https://example.test/s",
        allowed_protocols="trojan,ss,vless",
        preferred_servers="Германия",
        config_path=str(tmp_path / "config.json"),
        state_dir=str(tmp_path),
        socks_host="127.0.0.1",
        socks_port=1080,
        max_health_failures=2,
        min_alive_ratio=0.5,
        health_interval_sec=1,
        probe_timeout_sec=1,
    )


def _node(**kwargs) -> ProxyServer:
    data = dict(
        protocol="trojan",
        name="TROJAN - Германия",
        host="10.0.0.1",
        port=2058,
        password="x",
        network="ws",
        path="/",
        security="tls",
        sni="example.com",
        preferred=True,
        tcp_ok=True,
        latency_ms=10.0,
    )
    data.update(kwargs)
    return ProxyServer(**data)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_server_success(tmp_path: Path, trojan_server: ProxyServer):
    supervisor = Supervisor(_settings(tmp_path))
    supervisor.state.servers = [trojan_server]

    with (
        patch.object(supervisor, "restart_singbox", new=AsyncMock()) as restart,
        patch(
            "control_panel.supervisor.probe.http_probe_via_socks",
            new=AsyncMock(return_value=(True, 123.0)),
        ),
    ):
        await supervisor.apply_server(trojan_server)

    restart.assert_awaited()
    assert supervisor.state.active is trojan_server
    assert trojan_server.latency_ms == 123.0
    assert (tmp_path / "config.json").exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_server_failover_then_ok(tmp_path: Path):
    bad = _node(name="bad", host="10.0.0.1", port=1, latency_ms=1)
    good = _node(name="good", host="10.0.0.2", port=2, latency_ms=5)
    supervisor = Supervisor(_settings(tmp_path))
    supervisor.state.servers = [bad, good]

    probe = AsyncMock(side_effect=[(False, None), (True, 50.0)])
    with (
        patch.object(supervisor, "restart_singbox", new=AsyncMock()),
        patch("control_panel.supervisor.probe.http_probe_via_socks", new=probe),
    ):
        await supervisor.apply_server(bad)

    assert supervisor.state.active is good
    assert bad.tcp_ok is False
    assert probe.await_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tick_health_ok_resets_failures(tmp_path: Path, trojan_server: ProxyServer):
    supervisor = Supervisor(_settings(tmp_path))
    supervisor.state.active = trojan_server
    supervisor.state.servers = [trojan_server]
    supervisor.state.health_failures = 2
    supervisor.state.last_refresh_at = 10**12  # far future → no refresh

    with patch(
        "control_panel.supervisor.probe.http_probe_via_socks",
        new=AsyncMock(return_value=(True, 40.0)),
    ):
        await supervisor.tick()

    assert supervisor.state.health_failures == 0
    assert trojan_server.latency_ms == 40.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tick_triggers_failover_after_max_failures(tmp_path: Path):
    active = _node(name="active", host="10.0.0.1")
    other = _node(name="other", host="10.0.0.2", latency_ms=20)
    supervisor = Supervisor(_settings(tmp_path))
    supervisor.state.active = active
    supervisor.state.servers = [active, other]
    supervisor.state.health_failures = 1  # next fail → reaches max=2
    supervisor.state.last_refresh_at = 10**12

    with (
        patch(
            "control_panel.supervisor.probe.http_probe_via_socks",
            new=AsyncMock(return_value=(False, None)),
        ),
        patch.object(supervisor, "select_and_apply", new=AsyncMock()) as select,
        patch.object(supervisor, "refresh_subscription", new=AsyncMock()) as refresh,
    ):
        await supervisor.tick()

    select.assert_awaited_once_with(exclude_active=True)
    # alive ratio 100% → no forced refresh
    refresh.assert_not_awaited()
    assert supervisor.state.health_failures == 0
