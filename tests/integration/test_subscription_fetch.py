from __future__ import annotations

import base64

import httpx
import pytest
import respx

from control_panel.subscription import fetch_subscription
from tests.fixtures_data import TROJAN


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_subscription_empty_url():
    with pytest.raises(ValueError, match="SUBSCRIPTION_URL"):
        await fetch_subscription("")


@pytest.mark.integration
@pytest.mark.asyncio
@respx.mock
async def test_fetch_subscription_plain_body():
    route = respx.get("https://example.test/sub").mock(
        return_value=httpx.Response(200, text=f"{TROJAN}\n")
    )
    body = await fetch_subscription("https://example.test/sub")
    assert "trojan://" in body
    assert route.called


@pytest.mark.integration
@pytest.mark.asyncio
@respx.mock
async def test_fetch_subscription_base64_body():
    raw = f"{TROJAN}\n".encode()
    encoded = base64.b64encode(raw).decode()
    respx.get("https://example.test/b64").mock(return_value=httpx.Response(200, text=encoded))
    body = await fetch_subscription("https://example.test/b64")
    assert "trojan://" in body


@pytest.mark.integration
@pytest.mark.asyncio
@respx.mock
async def test_fetch_subscription_http_error():
    respx.get("https://example.test/fail").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_subscription("https://example.test/fail")
