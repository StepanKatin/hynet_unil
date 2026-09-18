from __future__ import annotations

import base64
import json

VLESS_VISION = (
    "vless://e0b6e984-4938-4012-a954-999f7063a63d@84.32.100.250:8444"
    "?security=reality&type=tcp&flow=xtls-rprx-vision"
    "&sni=iv.okcdn.ru&fp=chrome"
    "&pbk=rG0zJ5VDYOfcvHBnrU8GZJV_1L_-8tVMS3TgLPF-Dj8&sid=ff48391ffceb6947"
    "#%F0%9F%87%A9%F0%9F%87%AA%20VLESS%C2%B3%20-%20%D0%93%D0%B5%D1%80%D0%BC%D0%B0%D0%BD%D0%B8%D1%8F"
)

VLESS_GRPC = (
    "vless://e0b6e984-4938-4012-a954-999f7063a63d@84.32.100.250:2053"
    "?security=reality&type=grpc&serviceName=xyz&mode=gun"
    "&sni=web.max.ru&fp=chrome"
    "&pbk=rG0zJ5VDYOfcvHBnrU8GZJV_1L_-8tVMS3TgLPF-Dj8&sid=ff48391ffceb6947"
    "#DE-grpc"
)

TROJAN = (
    "trojan://SdQUm62YpW-rTeJ1cYMUaw@84.32.100.250:2058"
    "?security=tls&type=ws&path=%2F&sni=multy-d.hynet-connect.com"
    "#%F0%9F%87%A9%F0%9F%87%AA%20TROJAN%20-%20%D0%93%D0%B5%D1%80%D0%BC%D0%B0%D0%BD%D0%B8%D1%8F"
)

SS = (
    "ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNTo4RkpwZl9UZl9pX3M3X1Z1Mm0wX05B"
    "@84.32.100.250:2060#%F0%9F%87%A9%F0%9F%87%AA%20SHADOWSOCKS%20-%20%D0%93%D0%B5%D1%80%D0%BC%D0%B0%D0%BD%D0%B8%D1%8F"
)


def vmess_uri() -> str:
    payload = {
        "add": "1.2.3.4",
        "port": 8081,
        "id": "e183554a-2a4b-4018-8ecb-58d1f2b54141",
        "aid": "0",
        "net": "tcp",
        "type": "http",
        "host": "vkvideo.ru",
        "path": "/",
        "tls": "none",
        "ps": "VMess - Test",
        "v": "2",
        "scy": "auto",
    }
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"vmess://{raw}"
