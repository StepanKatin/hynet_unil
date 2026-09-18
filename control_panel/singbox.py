from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from control_panel.models import ProxyServer

logger = logging.getLogger(__name__)


def _tls_block(server: ProxyServer) -> dict[str, Any] | None:
    security = (server.security or "").lower()
    if security not in {"tls", "reality"}:
        return None
    tls: dict[str, Any] = {
        "enabled": True,
        "server_name": server.sni or server.host,
    }
    if server.fingerprint:
        tls["utls"] = {"enabled": True, "fingerprint": server.fingerprint}
    if server.alpn:
        tls["alpn"] = server.alpn
    if security == "reality":
        tls["reality"] = {
            "enabled": True,
            "public_key": server.public_key or "",
            "short_id": server.short_id or "",
        }
    return tls


def _transport_block(server: ProxyServer) -> dict[str, Any] | None:
    network = (server.network or "tcp").lower()
    if network in {"tcp", "raw"}:
        return None
    if network == "ws":
        transport: dict[str, Any] = {"type": "ws"}
        if server.path:
            transport["path"] = server.path
        if server.host_header:
            transport["headers"] = {"Host": server.host_header}
        return transport
    if network == "grpc":
        transport = {"type": "grpc"}
        if server.service_name:
            transport["service_name"] = server.service_name
        return transport
    if network == "http":
        transport = {"type": "http"}
        if server.path:
            transport["path"] = [server.path]
        if server.host_header:
            transport["host"] = [server.host_header]
        return transport
    logger.warning("Unsupported transport %s for %s, using tcp", network, server.name)
    return None


def server_to_outbound(server: ProxyServer, tag: str = "proxy") -> dict[str, Any]:
    if server.protocol == "vless":
        outbound: dict[str, Any] = {
            "type": "vless",
            "tag": tag,
            "server": server.host,
            "server_port": server.port,
            "uuid": server.uuid or "",
            "packet_encoding": "xudp",
        }
        # vision flow только с tcp; на grpc/ws ломает хендшейк
        if server.flow and (server.network or "tcp").lower() in {"tcp", "raw"}:
            outbound["flow"] = server.flow
        tls = _tls_block(server)
        if tls:
            outbound["tls"] = tls
        transport = _transport_block(server)
        if transport:
            outbound["transport"] = transport
        return outbound

    if server.protocol == "trojan":
        outbound = {
            "type": "trojan",
            "tag": tag,
            "server": server.host,
            "server_port": server.port,
            "password": server.password or "",
        }
        tls = _tls_block(server)
        if tls:
            outbound["tls"] = tls
        transport = _transport_block(server)
        if transport:
            outbound["transport"] = transport
        return outbound

    if server.protocol == "ss":
        return {
            "type": "shadowsocks",
            "tag": tag,
            "server": server.host,
            "server_port": server.port,
            "method": server.method or "aes-256-gcm",
            "password": server.password or "",
        }

    if server.protocol == "vmess":
        outbound = {
            "type": "vmess",
            "tag": tag,
            "server": server.host,
            "server_port": server.port,
            "uuid": server.uuid or "",
            "security": "auto",
        }
        tls = _tls_block(server)
        if tls:
            outbound["tls"] = tls
        transport = _transport_block(server)
        if transport:
            outbound["transport"] = transport
        return outbound

    raise ValueError(f"Unsupported protocol: {server.protocol}")


def build_singbox_config(
    server: ProxyServer,
    *,
    socks_host: str,
    socks_port: int,
    log_level: str = "warn",
) -> dict[str, Any]:
    return {
        "log": {"level": log_level, "timestamp": True},
        "inbounds": [
            {
                "type": "socks",
                "tag": "socks-in",
                "listen": socks_host,
                "listen_port": socks_port,
                "sniff": True,
            }
        ],
        "outbounds": [
            server_to_outbound(server, tag="proxy"),
            {"type": "direct", "tag": "direct"},
        ],
        "route": {
            "final": "proxy",
            "auto_detect_interface": True,
        },
    }


def write_config(path: str | Path, config: dict[str, Any]) -> Path:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote sing-box config to %s", config_path)
    return config_path
