from __future__ import annotations

from control_panel.models import ProxyServer


def mark_preferred(servers: list[ProxyServer], tokens: list[str]) -> list[ProxyServer]:
    for server in servers:
        server.preferred = server.matches_preferred(tokens)
    return servers


def rank_servers(
    servers: list[ProxyServer],
    *,
    protocol_priority: list[str] | None = None,
) -> list[ProxyServer]:
    """
    Сортировка:
    1) preferred
    2) tcp_ok
    3) приоритет протокола (порядок из ALLOWED_PROTOCOLS)
    4) latency
    """
    priority = {name: idx for idx, name in enumerate(protocol_priority or [])}

    def key(server: ProxyServer) -> tuple:
        latency = server.latency_ms if server.latency_ms is not None else 1e12
        tcp_penalty = 0 if server.tcp_ok is not False else 1
        proto_rank = priority.get(server.protocol, 100)
        # grpc Reality на практике часто «порт открыт, туннель мёртв»
        transport_penalty = 1 if (server.network or "").lower() == "grpc" else 0
        return (
            0 if server.preferred else 1,
            tcp_penalty,
            proto_rank,
            transport_penalty,
            latency,
            server.name,
        )

    return sorted(servers, key=key)


def pick_best(
    servers: list[ProxyServer],
    *,
    protocol_priority: list[str] | None = None,
) -> ProxyServer | None:
    ranked = rank_servers(
        [s for s in servers if s.tcp_ok is not False],
        protocol_priority=protocol_priority,
    )
    for server in ranked:
        if server.latency_ms is not None:
            return server
    return ranked[0] if ranked else None


def alive_ratio(servers: list[ProxyServer]) -> float:
    if not servers:
        return 0.0
    alive = sum(1 for s in servers if s.tcp_ok)
    return alive / len(servers)
