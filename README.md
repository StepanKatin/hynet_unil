# hynet_util

Docker-sidecar для Telegram-ботов на серверах в РФ: поднимает локальный **SOCKS5**, гоняет трафик через ноды из subscription-подписки (Hynet и совместимые), сам выбирает рабочий сервер и обновляет список при деградации.

Под капотом: **sing-box** (data plane) + небольшой **Python-оркестратор** (подписка, ranking, health/failover).

## Зачем это нужно

Telegram с многих серверов в РФ недоступен напрямую. Вместо системного VPN на всю машину бот ходит только в API Telegram через `socks5://tg-proxy:1080`. Остальной трафик сервера не затрагивается.

## Как это работает

1. Скачивает subscription URL.
2. Парсит URI (`trojan` / `ss` / `vless` / …), фильтрует по `ALLOWED_PROTOCOLS`.
3. Помечает preferred-ноды (`PREFERRED_SERVERS`).
4. Делает TCP-probe, выбирает лучший outbound (с учётом приоритета протоколов).
5. Пишет конфиг sing-box и слушает SOCKS на `1080`.
6. Периодически проверяет доступность `PROBE_URL` (по умолчанию `https://api.telegram.org`).
7. При фейлах — failover на другую ноду; если мало живых — обновляет подписку.

## Быстрый старт (этот репозиторий)

```bash
git clone <repo> && cd hynet_util
cp .env.example .env
# обязателен SUBSCRIPTION_URL=
```

Сборка и запуск образа:

```bash
docker build -f dockerfile -t hynet-util .
docker run --rm -it --env-file .env -p 1080:1080 -v hynet-data:/data hynet-util
```

Проверка с хоста:

```bash
# через прокси — должно ответить (часто 302)
curl -x socks5h://127.0.0.1:1080 -I --max-time 20 https://api.telegram.org

# напрямую с РФ-сервера — часто timeout; это нормально
curl -I --max-time 10 -o /dev/null -w "direct %{http_code}\n" https://api.telegram.org
```

> `docker-compose.yml` в git **не коммитится** (локальный стенд). В проде и в чужих проектах используйте **`dockerfile`** / готовый image как сервис.

## Подключение бота в Docker Compose

Рекомендуемый вариант: **sidecar в compose бота** — один `docker compose up` поднимает и прокси, и бота.

### Вариант A — build из соседнего репозитория

Структура на диске:

```text
projects/
  hynet_util/          # этот репозиторий (dockerfile)
  my_tg_bot/
    docker-compose.yml
    .env.hynet         # секреты прокси (не в git)
```

`my_tg_bot/docker-compose.yml`:

```yaml
services:
  tg-proxy:
    build:
      context: ../hynet_util
      dockerfile: dockerfile
    env_file:
      - .env.hynet
    restart: unless-stopped
    volumes:
      - tg-proxy-data:/data
    # ports не нужны, если бот в той же сети compose
    # ports:
    #   - "1080:1080"   # только если нужен curl с хоста

  bot:
    build: .
    depends_on:
      - tg-proxy
    environment:
      TELEGRAM_PROXY: socks5://tg-proxy:1080
      # BOT_TOKEN: ...
    restart: unless-stopped

volumes:
  tg-proxy-data:
```

`.env.hynet` (пример):

```env
SUBSCRIPTION_URL=https://hynet.click/s/xxxx
PREFERRED_SERVERS=США,Нидерланды,Германия,Швеция,Литва
ALLOWED_PROTOCOLS=trojan,ss,vless
REQUIRE_REALITY=false
```

В коде бота используйте `TELEGRAM_PROXY` (название на ваш вкус) как SOCKS5 для HTTP-клиента Telegram.

### Вариант B — готовый image

```yaml
services:
  tg-proxy:
    image: registry.example.com/hynet-util:latest
    env_file: .env.hynet
    restart: unless-stopped
    volumes:
      - tg-proxy-data:/data

  bot:
    image: registry.example.com/my-bot:latest
    depends_on: [tg-proxy]
    environment:
      TELEGRAM_PROXY: socks5://tg-proxy:1080
```

### Вариант C — один общий прокси на несколько ботов

Создайте общую сеть один раз:

```bash
docker network create tg-proxy-net
```

Стек прокси (отдельный compose или `docker run`) подключается к `tg-proxy-net`.  
Каждый бот в своём compose добавляет:

```yaml
services:
  bot:
    environment:
      TELEGRAM_PROXY: socks5://tg-proxy:1080
    networks: [tg-proxy-net]

networks:
  tg-proxy-net:
    external: true
```

Имя сервиса/контейнера прокси должно быть резолвимо как `tg-proxy` (или поправьте URL).

## Примеры в коде бота

### httpx / aiogram 3

```python
import os
import httpx
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

proxy = os.environ["TELEGRAM_PROXY"]  # socks5://tg-proxy:1080

# httpx
client = httpx.AsyncClient(proxy=proxy, timeout=30.0)

# aiogram (через aiohttp session с proxy — зависит от версии;
# часто достаточно передать proxy в session)
session = AiohttpSession(proxy=proxy)
bot = Bot(token=os.environ["BOT_TOKEN"], session=session)
```

### python-telegram-bot

```python
from telegram.ext import Application
import os

app = (
    Application.builder()
    .token(os.environ["BOT_TOKEN"])
    .proxy(os.environ["TELEGRAM_PROXY"])
    .get_updates_proxy(os.environ["TELEGRAM_PROXY"])
    .build()
)
```

Точный API зависит от версии библиотеки — суть одна: **весь Telegram HTTP трафик через SOCKS**.

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `SUBSCRIPTION_URL` | URL подписки (**обязателен**) | — |
| `PREFERRED_SERVERS` | Имена/IP preferred-нод через запятую | пусто |
| `ALLOWED_PROTOCOLS` | Протоколы в порядке приоритета | `trojan,ss,vless` |
| `REQUIRE_REALITY` | Только Reality (для VLESS) | `false` |
| `SOCKS_HOST` / `SOCKS_PORT` | Listen SOCKS | `0.0.0.0` / `1080` |
| `HEALTH_INTERVAL_SEC` | Интервал healthcheck | `60` |
| `REFRESH_INTERVAL_SEC` | Период обновления подписки | `1800` |
| `MIN_ALIVE_RATIO` | Ниже порога → форс-refresh | `0.5` |
| `MAX_HEALTH_FAILURES` | Фейлов подряд до failover | `3` |
| `PROBE_URL` | Цель проверки канала | `https://api.telegram.org` |
| `SINGBOX_LOG_LEVEL` | `warn` / `info` / `debug` | `warn` |

Полный список — в `.env.example`.

## Локальная разработка без Docker

Нужен бинарь [sing-box](https://github.com/SagerNet/sing-box/releases) в `PATH`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить SUBSCRIPTION_URL
# для локального запуска удобно:
# CONFIG_PATH=./data/config.json STATE_DIR=./data SOCKS_HOST=127.0.0.1
python main.py
```

## Тесты

```bash
pip install -r requirements-dev.txt
pytest -m "not e2e"
```

Живой smoke (прокси уже слушает `:1080`):

```bash
RUN_E2E=1 pytest -m e2e
```

Пирамида:

- **unit** — парсеры, ranking, генерация конфига sing-box;
- **integration** — TCP probe, fetch подписки (mock), supervisor на моках;
- **e2e** — опционально, реальный SOCKS → Telegram.

## Структура проекта

```text
main.py                 # точка входа
control_panel/
  settings.py           # env / Settings
  subscription.py       # fetch + parse URI
  ranking.py            # preferred / protocol priority
  probe.py              # TCP + HTTP via SOCKS
  singbox.py            # генерация конфига
  supervisor.py         # цикл health / failover / refresh
dockerfile              # контракт для sidecar в других проектах
.env.example
tests/
```

## Замечания по эксплуатации

- Не коммитьте `.env` и URL подписки.
- На машине «за хостовым VPN» Reality может вести себя иначе, чем на чистом VPS в РФ — ориентируйтесь на проверку с целевого сервера.
- `EXPOSE 1080` в Docker не публикует порт наружу; публикация — только через `ports` в compose/`-p` в `docker run`, либо доступ по имени сервиса внутри сети.
- Healthcheck Docker «порт открыт» ≠ «Telegram доступен»; смотрите логи: строка `Active server ready` / `Health OK`.

## Лицензия / внутреннее использование

Утилита для внутренних сервисов перевозчика: проксирование легитимного трафика собственных Telegram-ботов.
