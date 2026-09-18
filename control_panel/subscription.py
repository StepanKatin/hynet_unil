from __future__ import annotations

import base64
import json
import logging
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from control_panel.models import ProxyServer

logger = logging.getLogger(__name__)


def _b64decode_padded(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _decode_subscription_body(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    if "://" in text:
        return text
    try:
        decoded = _b64decode_padded(text.replace("\n", "").replace("\r", "")).decode(
            "utf-8", errors="replace"
        )
        if "://" in decoded:
            return decoded
    except Exception:
        pass
    return text


async def fetch_subscription(url: str, timeout: float = 30.0) -> str:
    if not url:
        raise ValueError("SUBSCRIPTION_URL is empty")
    headers = {
        "User-Agent": "hynet-util/0.1",
        "Accept": "*/*",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return _decode_subscription_body(response.content)


def _first(qs: dict[str, list[str]], *keys: str, default: str | None = None) -> str | None:
    for key in keys:
        values = qs.get(key)
        if values and values[0] != "":
            return values[0]
    return default


def parse_vless(uri: str) -> ProxyServer | None:
    parsed = urlparse(uri)
    if parsed.scheme != "vless" or not parsed.hostname or not parsed.port:
        return None
    qs = parse_qs(parsed.query)
    name = unquote(parsed.fragment) if parsed.fragment else f"{parsed.hostname}:{parsed.port}"
    network = (_first(qs, "type", "net") or "tcp").lower()
    security = (_first(qs, "security") or "none").lower()
    return ProxyServer(
        protocol="vless",
        name=name,
        host=parsed.hostname,
        port=parsed.port,
        raw_uri=uri,
        uuid=unquote(parsed.username or ""),
        flow=_first(qs, "flow") or None,
        encryption=_first(qs, "encryption") or "none",
        network=network,
        path=unquote(_first(qs, "path") or "") or None,
        host_header=_first(qs, "host") or None,
        service_name=_first(qs, "serviceName", "service_name") or None,
        grpc_mode=_first(qs, "mode") or None,
        security=security if security != "none" else None,
        sni=_first(qs, "sni", "serverName", "server_name") or None,
        fingerprint=_first(qs, "fp", "fingerprint") or None,
        public_key=_first(qs, "pbk", "publicKey", "public_key") or None,
        short_id=_first(qs, "sid", "shortId", "short_id") or None,
    )


def parse_trojan(uri: str) -> ProxyServer | None:
    parsed = urlparse(uri)
    if parsed.scheme != "trojan" or not parsed.hostname or not parsed.port:
        return None
    qs = parse_qs(parsed.query)
    name = unquote(parsed.fragment) if parsed.fragment else f"{parsed.hostname}:{parsed.port}"
    network = (_first(qs, "type", "net") or "tcp").lower()
    security = (_first(qs, "security") or "tls").lower()
    return ProxyServer(
        protocol="trojan",
        name=name,
        host=parsed.hostname,
        port=parsed.port,
        raw_uri=uri,
        password=unquote(parsed.username or ""),
        network=network,
        path=unquote(_first(qs, "path") or "") or None,
        host_header=_first(qs, "host") or None,
        security=security if security != "none" else None,
        sni=_first(qs, "sni", "peer") or None,
        fingerprint=_first(qs, "fp", "fingerprint") or None,
    )


def parse_ss(uri: str) -> ProxyServer | None:
    # ss://base64(method:password)@host:port#name  OR ss://base64(method:password@host:port)#name
    if not uri.startswith("ss://"):
        return None
    rest = uri[5:]
    name = ""
    if "#" in rest:
        rest, frag = rest.split("#", 1)
        name = unquote(frag)

    method: str | None = None
    password: str | None = None
    host: str | None = None
    port: int | None = None

    if "@" in rest:
        userinfo, hostport = rest.rsplit("@", 1)
        try:
            decoded = _b64decode_padded(userinfo).decode("utf-8")
            method, password = decoded.split(":", 1)
        except Exception:
            method, password = unquote(userinfo).split(":", 1)
        host_part, port_s = hostport.rsplit(":", 1)
        host, port = host_part, int(port_s)
    else:
        decoded = _b64decode_padded(rest).decode("utf-8")
        # method:password@host:port
        userinfo, hostport = decoded.rsplit("@", 1)
        method, password = userinfo.split(":", 1)
        host_part, port_s = hostport.rsplit(":", 1)
        host, port = host_part, int(port_s)

    if not host or not port:
        return None
    return ProxyServer(
        protocol="ss",
        name=name or f"{host}:{port}",
        host=host,
        port=port,
        raw_uri=uri,
        method=method,
        password=password,
        security=None,
    )


def parse_vmess(uri: str) -> ProxyServer | None:
    if not uri.startswith("vmess://"):
        return None
    payload = uri[8:]
    try:
        data = json.loads(_b64decode_padded(payload).decode("utf-8"))
    except Exception:
        logger.debug("Failed to decode vmess uri", exc_info=True)
        return None
    host = data.get("add") or data.get("host")
    port = int(data.get("port") or 0)
    if not host or not port:
        return None
    network = str(data.get("net") or "tcp").lower()
    tls = str(data.get("tls") or "").lower()
    security = "tls" if tls and tls != "none" else None
    return ProxyServer(
        protocol="vmess",
        name=str(data.get("ps") or f"{host}:{port}"),
        host=str(host),
        port=port,
        raw_uri=uri,
        uuid=str(data.get("id") or ""),
        network=network,
        path=str(data.get("path") or "/") if data.get("path") else None,
        host_header=str(data.get("host")) if data.get("host") else None,
        security=security,
        sni=str(data.get("sni") or data.get("host") or "") or None,
        fingerprint=str(data.get("fp") or "") or None,
    )


_PARSERS = {
    "vless": parse_vless,
    "trojan": parse_trojan,
    "ss": parse_ss,
    "vmess": parse_vmess,
}


def parse_subscription(
    body: str,
    *,
    allowed_protocols: set[str] | None = None,
    require_reality: bool = False,
) -> list[ProxyServer]:
    servers: list[ProxyServer] = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        scheme = line.split("://", 1)[0].lower()
        parser = _PARSERS.get(scheme)
        if parser is None:
            continue
        if allowed_protocols and scheme not in allowed_protocols:
            continue
        try:
            server = parser(line)
        except Exception:
            logger.warning("Skip broken URI (%s)", scheme, exc_info=True)
            continue
        if server is None:
            continue
        if require_reality and not server.is_reality:
            continue
        servers.append(server)

    # de-dup by host:port:protocol:network
    unique: dict[tuple, ProxyServer] = {}
    for server in servers:
        key = (server.protocol, server.host, server.port, server.network, server.flow)
        unique[key] = server
    return list(unique.values())
