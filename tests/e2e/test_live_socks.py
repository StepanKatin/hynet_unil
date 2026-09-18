"""Optional live smoke — запускать только при поднятом tg-proxy.

  RUN_E2E=1 pytest -m e2e
"""

from __future__ import annotations

import os

import httpx
import pytest


pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_live_socks_reaches_telegram():
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("Set RUN_E2E=1 and start tg-proxy on :1080")

    async with httpx.AsyncClient(
        proxy="socks5://127.0.0.1:1080",
        timeout=20.0,
        follow_redirects=True,
    ) as client:
        response = await client.get("https://api.telegram.org")
    assert response.status_code < 500
