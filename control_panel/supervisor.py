from __future__ import annotations

import asyncio
import logging
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path

from control_panel import probe, ranking, singbox, subscription
from control_panel.models import ProxyServer
from control_panel.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class RuntimeState:
    servers: list[ProxyServer] = field(default_factory=list)
    active: ProxyServer | None = None
    last_refresh_at: float = 0.0
    health_failures: int = 0
    singbox_proc: asyncio.subprocess.Process | None = None


class Supervisor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state = RuntimeState()
        self._stop = asyncio.Event()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                pass

        Path(self.settings.state_dir).mkdir(parents=True, exist_ok=True)
        await self.refresh_subscription(force=True)
        await self.select_and_apply()

        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.settings.health_interval_sec)
                break
            except asyncio.TimeoutError:
                await self.tick()

        await self.stop_singbox()
        logger.info("Supervisor stopped")

    async def tick(self) -> None:
        now = time.time()
        need_refresh = (now - self.state.last_refresh_at) >= self.settings.refresh_interval_sec
        if need_refresh:
            await self.refresh_subscription(force=True)

        ok, latency = await probe.http_probe_via_socks(
            socks_host=self.settings.socks_host,
            socks_port=self.settings.socks_port,
            url=self.settings.probe_url,
            timeout=self.settings.probe_timeout_sec,
        )
        if ok:
            self.state.health_failures = 0
            if self.state.active is not None and latency is not None:
                self.state.active.latency_ms = latency
            logger.info(
                "Health OK via %s (%.0f ms)",
                self.state.active.summary() if self.state.active else "?",
                latency or -1,
            )
            return

        self.state.health_failures += 1
        logger.warning(
            "Health FAIL (%s/%s) active=%s",
            self.state.health_failures,
            self.settings.max_health_failures,
            self.state.active.summary() if self.state.active else None,
        )

        if self.state.health_failures >= self.settings.max_health_failures:
            ratio = ranking.alive_ratio(self.state.servers)
            if ratio < self.settings.min_alive_ratio:
                logger.warning(
                    "Alive ratio %.0f%% < %.0f%% — refreshing subscription",
                    ratio * 100,
                    self.settings.min_alive_ratio * 100,
                )
                await self.refresh_subscription(force=True)
            await self.select_and_apply(exclude_active=True)
            self.state.health_failures = 0

    async def refresh_subscription(self, *, force: bool = False) -> None:
        logger.info("Fetching subscription…")
        body = await subscription.fetch_subscription(self.settings.subscription_url)
        servers = subscription.parse_subscription(
            body,
            allowed_protocols=self.settings.protocol_allowlist(),
            require_reality=self.settings.require_reality,
        )
        ranking.mark_preferred(servers, self.settings.preferred_tokens())
        await probe.probe_tcp_batch(
            servers,
            timeout=self.settings.tcp_connect_timeout_sec,
        )
        self.state.servers = servers
        self.state.last_refresh_at = time.time()
        preferred = sum(1 for s in servers if s.preferred)
        logger.info(
            "Subscription loaded: %s servers (%s preferred, %.0f%% tcp-alive)",
            len(servers),
            preferred,
            ranking.alive_ratio(servers) * 100,
        )
        if force and not servers:
            raise RuntimeError("No servers left after filters — check SUBSCRIPTION_URL / ALLOWED_PROTOCOLS")

    async def select_and_apply(self, *, exclude_active: bool = False) -> None:
        candidates = list(self.state.servers)
        if exclude_active and self.state.active is not None:
            active_key = (self.state.active.host, self.state.active.port, self.state.active.network)
            candidates = [
                s
                for s in candidates
                if (s.host, s.port, s.network) != active_key
            ]
            if not candidates:
                candidates = list(self.state.servers)

        best = ranking.pick_best(
            candidates,
            protocol_priority=self.settings.protocol_priority(),
        )
        if best is None:
            raise RuntimeError("No candidate servers available")

        if (
            self.state.active
            and self.state.active.host == best.host
            and self.state.active.port == best.port
            and self.state.active.network == best.network
            and self.state.singbox_proc
            and self.state.singbox_proc.returncode is None
        ):
            logger.info("Keep current server: %s", best.summary())
            return

        await self.apply_server(best)

    async def apply_server(self, server: ProxyServer, *, _depth: int = 0) -> None:
        if _depth > 8:
            logger.error(
                "Exhausted failover attempts — keeping last config and will retry on health loop"
            )
            return

        logger.info("Switching to %s", server.summary())
        config = singbox.build_singbox_config(
            server,
            socks_host=self.settings.socks_host,
            socks_port=self.settings.socks_port,
            log_level=self.settings.singbox_log_level,
        )
        singbox.write_config(self.settings.config_path, config)
        await self.restart_singbox()
        self.state.active = server

        # короткая пауза на bind + проверка
        await asyncio.sleep(1.5)
        ok, latency = await probe.http_probe_via_socks(
            socks_host=self.settings.socks_host,
            socks_port=self.settings.socks_port,
            url=self.settings.probe_url,
            timeout=self.settings.probe_timeout_sec,
        )
        if ok:
            server.latency_ms = latency
            logger.info("Active server ready: %s", server.summary())
            return

        logger.warning("New server failed first probe: %s", server.summary())
        server.tcp_ok = False
        nxt = ranking.pick_best(
            [
                s
                for s in self.state.servers
                if not (
                    s.host == server.host
                    and s.port == server.port
                    and s.network == server.network
                )
                and s.tcp_ok is not False
            ],
            protocol_priority=self.settings.protocol_priority(),
        )
        if nxt is None:
            logger.error("No working outbound found after probe failures")
            return
        await self.apply_server(nxt, _depth=_depth + 1)

    async def restart_singbox(self) -> None:
        await self.stop_singbox()
        cmd = [
            self.settings.singbox_bin,
            "run",
            "-c",
            self.settings.config_path,
        ]
        logger.info("Starting: %s", " ".join(cmd))
        self.state.singbox_proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        asyncio.create_task(self._pump_singbox_logs(self.state.singbox_proc))

    async def stop_singbox(self) -> None:
        proc = self.state.singbox_proc
        if proc is None:
            return
        if proc.returncode is not None:
            self.state.singbox_proc = None
            return
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        self.state.singbox_proc = None

    async def _pump_singbox_logs(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            logger.info("[sing-box] %s", line.decode("utf-8", errors="replace").rstrip())
