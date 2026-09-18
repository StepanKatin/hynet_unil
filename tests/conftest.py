from __future__ import annotations

import pytest

from control_panel.models import ProxyServer
from tests.fixtures_data import SS, TROJAN, VLESS_GRPC, VLESS_VISION, vmess_uri


@pytest.fixture
def sample_subscription_body() -> str:
    return "\n".join(
        [
            "# comment",
            VLESS_VISION,
            VLESS_GRPC,
            TROJAN,
            SS,
            vmess_uri(),
            "",
            VLESS_VISION,
        ]
    )


@pytest.fixture
def trojan_server() -> ProxyServer:
    return ProxyServer(
        protocol="trojan",
        name="TROJAN - Германия",
        host="84.32.100.250",
        port=2058,
        password="secret",
        network="ws",
        path="/",
        security="tls",
        sni="multy-d.hynet-connect.com",
        preferred=True,
        tcp_ok=True,
        latency_ms=12.0,
    )


@pytest.fixture
def vless_vision_server() -> ProxyServer:
    return ProxyServer(
        protocol="vless",
        name="VLESS³ - Германия",
        host="84.32.100.250",
        port=8444,
        uuid="e0b6e984-4938-4012-a954-999f7063a63d",
        flow="xtls-rprx-vision",
        network="tcp",
        security="reality",
        sni="iv.okcdn.ru",
        fingerprint="chrome",
        public_key="rG0zJ5VDYOfcvHBnrU8GZJV_1L_-8tVMS3TgLPF-Dj8",
        short_id="ff48391ffceb6947",
        preferred=True,
        tcp_ok=True,
        latency_ms=5.0,
    )
