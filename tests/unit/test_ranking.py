from __future__ import annotations

import pytest

from control_panel.models import ProxyServer
from control_panel.ranking import alive_ratio, mark_preferred, pick_best, rank_servers


def _srv(**kwargs) -> ProxyServer:
    base = dict(
        protocol="trojan",
        name="node",
        host="1.1.1.1",
        port=443,
        tcp_ok=True,
        latency_ms=50.0,
    )
    base.update(kwargs)
    return ProxyServer(**base)


@pytest.mark.unit
def test_mark_preferred_by_name_and_ip():
    servers = [
        _srv(name="TROJAN - США", host="8.8.8.8"),
        _srv(name="other", host="9.9.9.9"),
    ]
    mark_preferred(servers, ["США", "9.9.9.9"])
    assert servers[0].preferred is True
    assert servers[1].preferred is True


@pytest.mark.unit
def test_rank_prefers_preferred_and_protocol_order():
    servers = [
        _srv(protocol="vless", name="v", preferred=True, latency_ms=1, network="tcp"),
        _srv(protocol="trojan", name="t", preferred=True, latency_ms=20, network="ws"),
        _srv(protocol="ss", name="s", preferred=False, latency_ms=2, network="tcp"),
    ]
    ranked = rank_servers(servers, protocol_priority=["trojan", "ss", "vless"])
    assert ranked[0].protocol == "trojan"
    assert ranked[1].protocol == "vless"
    assert ranked[2].protocol == "ss"


@pytest.mark.unit
def test_rank_penalizes_grpc():
    a = _srv(protocol="vless", name="tcp", network="tcp", preferred=True, latency_ms=10)
    b = _srv(protocol="vless", name="grpc", network="grpc", preferred=True, latency_ms=1)
    ranked = rank_servers([b, a], protocol_priority=["vless"])
    assert ranked[0].network == "tcp"


@pytest.mark.unit
def test_pick_best_skips_tcp_dead():
    dead = _srv(name="dead", tcp_ok=False, preferred=True, latency_ms=1)
    live = _srv(name="live", tcp_ok=True, preferred=False, latency_ms=100)
    assert pick_best([dead, live]).name == "live"


@pytest.mark.unit
def test_alive_ratio():
    servers = [_srv(tcp_ok=True), _srv(tcp_ok=False), _srv(tcp_ok=True)]
    assert alive_ratio(servers) == pytest.approx(2 / 3)
    assert alive_ratio([]) == 0.0
