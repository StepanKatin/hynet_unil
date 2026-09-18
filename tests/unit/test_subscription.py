from __future__ import annotations

import base64

import pytest

from control_panel.subscription import (
    _decode_subscription_body,
    parse_ss,
    parse_subscription,
    parse_trojan,
    parse_vless,
    parse_vmess,
)
from tests.fixtures_data import SS, TROJAN, VLESS_GRPC, VLESS_VISION


@pytest.mark.unit
def test_parse_vless_vision():
    server = parse_vless(VLESS_VISION)
    assert server is not None
    assert server.protocol == "vless"
    assert server.host == "84.32.100.250"
    assert server.port == 8444
    assert server.flow == "xtls-rprx-vision"
    assert server.is_reality
    assert server.sni == "iv.okcdn.ru"
    assert "Германия" in server.name


@pytest.mark.unit
def test_parse_vless_grpc():
    server = parse_vless(VLESS_GRPC)
    assert server is not None
    assert server.network == "grpc"
    assert server.service_name == "xyz"
    assert server.flow is None


@pytest.mark.unit
def test_parse_trojan_ws():
    server = parse_trojan(TROJAN)
    assert server is not None
    assert server.protocol == "trojan"
    assert server.network == "ws"
    assert server.password == "SdQUm62YpW-rTeJ1cYMUaw"
    assert server.sni == "multy-d.hynet-connect.com"


@pytest.mark.unit
def test_parse_ss_userinfo():
    server = parse_ss(SS)
    assert server is not None
    assert server.protocol == "ss"
    assert server.method == "chacha20-ietf-poly1305"
    assert server.password == "8FJpf_Tf_i_s7_Vu2m0_NA"
    assert server.port == 2060


@pytest.mark.unit
def test_parse_ss_fully_encoded():
    inner = "chacha20-ietf-poly1305:pass@9.9.9.9:8388"
    encoded = base64.urlsafe_b64encode(inner.encode()).decode().rstrip("=")
    server = parse_ss(f"ss://{encoded}#node")
    assert server is not None
    assert server.host == "9.9.9.9"
    assert server.port == 8388
    assert server.password == "pass"


@pytest.mark.unit
def test_parse_vmess(sample_subscription_body: str):
    line = next(line for line in sample_subscription_body.splitlines() if line.startswith("vmess://"))
    server = parse_vmess(line)
    assert server is not None
    assert server.host == "1.2.3.4"
    assert server.port == 8081
    assert server.uuid


@pytest.mark.unit
def test_parse_subscription_filters_and_dedup(sample_subscription_body: str):
    servers = parse_subscription(
        sample_subscription_body,
        allowed_protocols={"vless", "trojan", "ss"},
        require_reality=False,
    )
    # vision + grpc + trojan + ss (vmess filtered, vision deduped)
    assert len(servers) == 4
    protocols = {s.protocol for s in servers}
    assert protocols == {"vless", "trojan", "ss"}


@pytest.mark.unit
def test_parse_subscription_require_reality(sample_subscription_body: str):
    servers = parse_subscription(
        sample_subscription_body,
        allowed_protocols={"vless", "trojan", "ss"},
        require_reality=True,
    )
    assert servers
    assert all(s.is_reality for s in servers)
    assert all(s.protocol == "vless" for s in servers)


@pytest.mark.unit
def test_decode_plain_and_base64_subscription():
    plain = f"{TROJAN}\n"
    assert TROJAN in _decode_subscription_body(plain.encode())

    b64 = base64.b64encode(plain.encode()).decode()
    decoded = _decode_subscription_body(b64.encode())
    assert "trojan://" in decoded
