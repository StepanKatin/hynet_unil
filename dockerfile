FROM python:3.12-slim

ARG SING_BOX_VERSION=1.11.7
ARG TARGETARCH=amd64

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Map Docker arch → sing-box release arch
RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) SB_ARCH=amd64 ;; \
      arm64) SB_ARCH=arm64 ;; \
      *) echo "Unsupported arch: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
      "https://github.com/SagerNet/sing-box/releases/download/v${SING_BOX_VERSION}/sing-box-${SING_BOX_VERSION}-linux-${SB_ARCH}.tar.gz" \
      -o /tmp/sing-box.tgz; \
    tar -xzf /tmp/sing-box.tgz -C /tmp; \
    mv /tmp/sing-box-${SING_BOX_VERSION}-linux-${SB_ARCH}/sing-box /usr/local/bin/sing-box; \
    chmod +x /usr/local/bin/sing-box; \
    rm -rf /tmp/sing-box.tgz /tmp/sing-box-${SING_BOX_VERSION}-linux-${SB_ARCH}; \
    sing-box version

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY control_panel ./control_panel

RUN mkdir -p /data

ENV PYTHONUNBUFFERED=1 \
    SINGBOX_BIN=/usr/local/bin/sing-box \
    CONFIG_PATH=/data/config.json \
    STATE_DIR=/data \
    SOCKS_HOST=0.0.0.0 \
    SOCKS_PORT=1080

EXPOSE 1080
VOLUME ["/data"]

CMD ["python", "-u", "main.py"]
