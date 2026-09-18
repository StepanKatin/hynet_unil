from __future__ import annotations

from pathlib import Path

import pytest

from control_panel.models import ProxyServer
from control_panel.singbox import build_singbox_config, server_to_outbound, write_config


@pytest.mark.unit
def test_vless_vision_outbound(vless_vision_server: ProxyServer):
    outbound = server_to_outbound(vless_vision_server)
    assert outbound["type"] == "vless"
    assert outbound["flow"] == "xtls-rprx-vision"
    assert outbound["packet_encoding"] == "xudp"
    assert outbound["tls"]["reality"]["enabled"] is True
    assert "transport" not in outbound


@pytest.mark.unit
def test_vless_grpc_does_not_keep_vision_flow():
    server = ProxyServer(
        protocol="vless",
        name="grpc",
        host="1.2.3.4",
        port=2053,
        uuid="u",
        flow="xtls-rprx-vision",
        network="grpc",
        service_name="xyz",
        security="reality",
        sni="web.max.ru",
        public_key="pk",
        short_id="sid",
        fingerprint="chrome",
    )
    outbound = server_to_outbound(server)
    assert "flow" not in outbound
    assert outbound["transport"]["type"] == "grpc"
    assert outbound["transport"]["service_name"] == "xyz"


@pytest.mark.unit
def test_trojan_ws_outbound(trojan_server: ProxyServer):
    outbound = server_to_outbound(trojan_server)
    assert outbound["type"] == "trojan"
    assert outbound["tls"]["enabled"] is True
    assert outbound["transport"]["type"] == "ws"
    assert outbound["transport"]["path"] == "/"


@pytest.mark.unit
def test_ss_outbound():
    server = ProxyServer(
        protocol="ss",
        name="ss",
        host="1.1.1.1",
        port=2060,
        method="chacha20-ietf-poly1305",
        password="x",
    )
    outbound = server_to_outbound(server)
    assert outbound == {
        "type": "shadowsocks",
        "tag": "proxy",
        "server": "1.1.1.1",
        "server_port": 2060,
        "method": "chacha20-ietf-poly1305",
        "password": "x",
    }


@pytest.mark.unit
def test_build_and_write_config(trojan_server: ProxyServer, tmp_path: Path):
    cfg = build_singbox_config(
        trojan_server,
        socks_host="0.0.0.0",
        socks_port=1080,
        log_level="warn",
    )
    assert cfg["inbounds"][0]["listen_port"] == 1080
    assert cfg["route"]["final"] == "proxy"
    assert cfg["outbounds"][0]["type"] == "trojan"
    assert {o["tag"] for o in cfg["outbounds"]} == {"proxy", "direct"}

    path = write_config(tmp_path / "config.json", cfg)
    assert path.exists()
    assert "trojan" in path.read_text(encoding="utf-8")
