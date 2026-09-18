from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlparse

import httpx

from control_panel.models import ProxyServer

logger = logging.getLogger(__name__)


async def tcp_ping(host: str, port: int, timeout: float) -> tuple[bool, float | None]:
    started = time.perf_counter()
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, (time.perf_counter() - started) * 1000
    except Exception:
        return False, None


async def probe_tcp_batch(
    servers: list[ProxyServer],
    *,
    timeout: float,
    concurrency: int = 20,
) -> list[ProxyServer]:
    sem = asyncio.Semaphore(concurrency)

    async def one(server: ProxyServer) -> None:
        async with sem:
            ok, ms = await tcp_ping(server.host, server.port, timeout)
            server.tcp_ok = ok
            # предварительная оценка, пока нет HTTP-probe через outbound
            if ok and server.latency_ms is None:
                server.latency_ms = ms

    await asyncio.gather(*(one(s) for s in servers))
    alive = sum(1 for s in servers if s.tcp_ok)
    logger.info("TCP probe: %s/%s alive", alive, len(servers))
    return servers


async def http_probe_via_socks(
    *,
    socks_host: str,
    socks_port: int,
    url: str,
    timeout: float,
) -> tuple[bool, float | None]:
    """Проверка, что через локальный SOCKS реально ходит до Telegram."""
    # Из того же контейнера ходим на 127.0.0.1, даже если listen = 0.0.0.0
    listen_host = "127.0.0.1" if socks_host in {"0.0.0.0", "::"} else socks_host
    proxy = f"socks5://{listen_host}:{socks_port}"
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            proxy=proxy,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            # Telegram может ответить 302/200/401 — главное что TLS+маршрут живы
            if response.status_code >= 500:
                return False, None
            return True, (time.perf_counter() - started) * 1000
    except Exception as exc:
        logger.debug("HTTP probe via socks failed: %s", exc)
        return False, None


def probe_target_host(url: str) -> str:
    return urlparse(url).hostname or "api.telegram.org"
