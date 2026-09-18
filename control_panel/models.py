from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ProtocolName = Literal["vless", "vmess", "trojan", "ss"]


class ProxyServer(BaseModel):
    """Один outbound из subscription-листа."""

    protocol: ProtocolName
    name: str
    host: str
    port: int
    raw_uri: str = ""

    # common / vless
    uuid: str | None = None
    flow: str | None = None
    encryption: str | None = None

    # transport
    network: str = "tcp"  # tcp | ws | grpc | http
    path: str | None = None
    host_header: str | None = None
    service_name: str | None = None
    grpc_mode: str | None = None

    # tls / reality
    security: str | None = None  # reality | tls | none
    sni: str | None = None
    fingerprint: str | None = None
    public_key: str | None = None
    short_id: str | None = None
    alpn: list[str] = Field(default_factory=list)

    # trojan / ss
    password: str | None = None
    method: str | None = None

    # ranking helpers (заполняются рантаймом)
    preferred: bool = False
    tcp_ok: bool | None = None
    latency_ms: float | None = None

    @property
    def tag(self) -> str:
        safe = "".join(c if c.isalnum() else "_" for c in self.name)[:48] or "node"
        return f"{self.protocol}_{self.host}_{self.port}_{safe}"

    @property
    def is_reality(self) -> bool:
        return (self.security or "").lower() == "reality"

    def matches_preferred(self, tokens: list[str]) -> bool:
        if not tokens:
            return False
        hay = f"{self.name} {self.host}".casefold()
        return any(token.casefold() in hay for token in tokens)

    def summary(self) -> str:
        flags = []
        if self.preferred:
            flags.append("preferred")
        if self.latency_ms is not None:
            flags.append(f"{self.latency_ms:.0f}ms")
        suffix = f" [{', '.join(flags)}]" if flags else ""
        return f"{self.protocol}://{self.host}:{self.port} ({self.name}){suffix}"

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "network": self.network,
            "security": self.security,
            "preferred": self.preferred,
            "latency_ms": self.latency_ms,
        }
