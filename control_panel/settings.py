from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    subscription_url: str = Field(default="", alias="SUBSCRIPTION_URL")
    preferred_servers: str = Field(default="", alias="PREFERRED_SERVERS")
    # Порядок = приоритет при равной latency (слева выше)
    allowed_protocols: str = Field(default="trojan,ss,vless", alias="ALLOWED_PROTOCOLS")
    require_reality: bool = Field(default=False, alias="REQUIRE_REALITY")
    singbox_log_level: str = Field(default="warn", alias="SINGBOX_LOG_LEVEL")

    socks_host: str = Field(default="0.0.0.0", alias="SOCKS_HOST")
    socks_port: int = Field(default=1080, alias="SOCKS_PORT")

    singbox_bin: str = Field(default="sing-box", alias="SINGBOX_BIN")
    config_path: str = Field(default="/data/config.json", alias="CONFIG_PATH")
    state_dir: str = Field(default="/data", alias="STATE_DIR")

    health_interval_sec: int = Field(default=60, alias="HEALTH_INTERVAL_SEC")
    probe_timeout_sec: float = Field(default=8.0, alias="PROBE_TIMEOUT_SEC")
    refresh_interval_sec: int = Field(default=1800, alias="REFRESH_INTERVAL_SEC")
    tcp_connect_timeout_sec: float = Field(default=3.0, alias="TCP_CONNECT_TIMEOUT_SEC")
    min_alive_ratio: float = Field(default=0.5, alias="MIN_ALIVE_RATIO")
    max_health_failures: int = Field(default=3, alias="MAX_HEALTH_FAILURES")
    probe_url: str = Field(default="https://api.telegram.org", alias="PROBE_URL")

    def preferred_tokens(self) -> list[str]:
        return [p.strip() for p in self.preferred_servers.split(",") if p.strip()]

    def protocol_allowlist(self) -> set[str]:
        return set(self.protocol_priority())

    def protocol_priority(self) -> list[str]:
        return [p.strip().lower() for p in self.allowed_protocols.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
