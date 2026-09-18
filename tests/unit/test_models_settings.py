from __future__ import annotations

import pytest

from control_panel.models import ProxyServer
from control_panel.settings import Settings, get_settings


@pytest.mark.unit
def test_proxy_server_matches_preferred():
    server = ProxyServer(
        protocol="trojan",
        name="TROJAN - Литва",
        host="188.214.135.206",
        port=2058,
    )
    assert server.matches_preferred(["Литва"]) is True
    assert server.matches_preferred(["188.214.135.206"]) is True
    assert server.matches_preferred(["США"]) is False


@pytest.mark.unit
def test_settings_helpers(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SUBSCRIPTION_URL", "https://example.test/s")
    monkeypatch.setenv("PREFERRED_SERVERS", "США, Нидерланды")
    monkeypatch.setenv("ALLOWED_PROTOCOLS", "trojan, ss, vless")
    settings = Settings(_env_file=None)
    assert settings.preferred_tokens() == ["США", "Нидерланды"]
    assert settings.protocol_priority() == ["trojan", "ss", "vless"]
    assert settings.protocol_allowlist() == {"trojan", "ss", "vless"}
    get_settings.cache_clear()
