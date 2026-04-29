# Deployment Guide

## Требования к серверу

- Linux VPS, x86_64.
- **2 vCPU и 1.9–2 ГиБ RAM** — минимум, при условии что включён swap (см. шаг 0). Стек выверен под этот размер: `mem_limit` стоит на каждом сервисе. Без swap или с меньшей памятью сборка фронтенда и пиковая нагрузка транскрибации вытолкнут api OOM-killer'ом.
- **4+ ГиБ RAM** — рекомендуется для комфортной работы под нагрузкой.
- 30+ ГиБ SSD. Под Docker уйдёт ~10 ГиБ (образы + слои), плюс БД растёт на ~10 МиБ/день.
- Публичный IPv4, открытые 80/443, **закрытые 5432/6379/8000** (это внутренние).
- DNS A-запись `bot.example.com` → IP. Если используете публичный веб-сайт — заодно `sb.example.com` (admin) или то, что в `DOMAIN`.
- Docker 24+ и Docker Compose v2.

```bash
# Ubuntu/Debian:
apt update && apt install -y docker.io docker-compose-plugin git curl
```

---

## Шаг 0. Swap (для VPS с 2 ГиБ RAM)

Без swap у вас при первом же `docker compose up` (admin_panel/web_panel запускают npm build, node жжёт ~12 ГиБ виртуала) либо при пиковой транскрибации сработает глобальный OOM-killer и снесёт случайный процесс — обычно api или uvicorn. С 2 ГиБ swap kernel сначала свопит холодные страницы.

```bash
sudo sh scripts/enable_swap.sh        # создаёт /swapfile, vm.swappiness=10, прописывает в /etc/fstab
free -h && swapon --show              # проверить
```

Скрипт идемпотентный — повторный запуск ничего не ломает.

---

## Шаг 1. Клонирование и .env

```bash
cd /srv
git clone https://github.com/Psayha/bukvatrans.git
cd bukvatrans
cp .env.example .env
chmod 600 .env
```

### 1.1. Логин в GHCR (один раз)

Compose тянет образ `ghcr.io/psayha/bukvatrans:latest`, и Watchtower следит за обновлениями. Для приватного образа нужен `docker login`:

```bash
echo "$YOUR_PAT_WITH_READ_PACKAGES" | docker login ghcr.io -u <github_username> --password-stdin
```

Это создаёт `~/.docker/config.json`, который Watchtower монтирует read-only внутрь контейнера. PAT с scope `read:packages`.

### 1.2. Заполнить `.env`

Минимум:

```ini
DOMAIN=bot.example.com
DB_PASSWORD=<длинный случайный>
BOT_TOKEN=<из @BotFather>
WEBHOOK_HOST=https://bot.example.com   # см. шаг "Прокси для Telegram"
WEBHOOK_SECRET=<64 случайных символа>

GROQ_API_KEY=<groq.com>
GROQ_API_BASE=https://api.groq.com     # см. шаг "Прокси для Groq"
OPENROUTER_API_KEY=<openrouter.ai>
YUKASSA_SHOP_ID=...
YUKASSA_SECRET_KEY=...

ADMIN_IDS=111111,222222     # ≥ 2 для 2FA admin-команд
ENV=production
SENTRY_DSN=https://...@sentry.io/...
SUPPORT_EMAIL=ops@example.com

COMPANY_NAME="ИП Иванов И.И."
COMPANY_INN=...
COMPANY_OGRN=...
COMPANY_ADDRESS="г. Москва"
```

Кириллические значения с пробелами обязательно в кавычках, иначе при `source .env` в bash он попытается выполнить вторую часть как команду (compose читает корректно — это спасает только ручной `source`).

---

## Шаг 2. Прокси для гео-блокированных сервисов {#proxies}

Из РФ обычно недоступны: `api.telegram.org`, `api.groq.com`, иногда Instagram. Каждый случай решается своим прокси.

### 2.1. Telegram webhook (Telegram → ваш сервер)

Telegram сам не блокирует входящий трафик к вам, **но если api.telegram.org недоступен с сервера, бот не сможет вызвать `set_webhook` при старте**. Решение — поднять Cloudflare Worker / Deno Deploy, который:

1. Принимает Telegram-webhook на свой публичный URL.
2. Форвардит его на `https://<ваш-домен>/webhooks/telegram` с тем же body и заголовком `X-Telegram-Bot-Api-Secret-Token`.
3. Заодно служит исходящим прокси для bot API-вызовов.

Шаблон: `scripts/telegram_webhook_proxy_worker.js`. Деплой на Deno Deploy за 5 минут (New Playground → вставить → Save & Deploy → получить `https://<project>.<acc>.deno.net`).

В `.env`:
```
WEBHOOK_HOST=https://<deno-proxy-host>
```

### 2.2. Groq Whisper (api.groq.com)

Groq геоблочит RU/CN. Деплой того же типа прокси через Cloudflare Worker (предпочтительно — ослабленнее лимиты по body) или Deno Deploy.

Шаблоны: `scripts/groq_proxy_worker.js` (CF), `scripts/groq_proxy_deno.js` (Deno).

⚠️ **Cloudflare Worker предпочтительнее**:
- CF: 100 МБ body, 30s wall-clock, 100k req/day free.
- Deno Deploy free tier тимит на больших файлах → периодические 500.

В `.env`:
```
GROQ_API_BASE=https://<your-groq-proxy-host>
```

### 2.3. Скачивание yt-dlp (опционально)

Для большинства поддерживаемых платформ (YouTube, VK, RuTube, TikTok) RU-egress работает напрямую — прокси не нужен. Если когда-нибудь потребуется (Instagram, новые блокировки) — есть `YDL_PROXY` для SOCKS5/HTTP:

```
YDL_PROXY=socks5h://host:port
```

⚠️ Применяется ко **всем** загрузкам! Если поставите ради одного домена — пострадают все остальные. Если нужен прокси только под один сервис — лучше не включать YDL_PROXY, а отключить сервис в whitelist (`src/utils/validators.py`).

WARP (Cloudflare) даёт бесплатный SOCKS5, но требует socat-форвардера для проброса в docker bridge. Подробности в `docs/RUNBOOK.md` → «Включить WARP-прокси для yt-dlp».

---

## Шаг 3. Первичный TLS-сертификат

`nginx` в основном конфиге ссылается на TLS-файлы, которых на чистом сервере ещё нет. Прямой `docker compose up -d` на первом деплое **не запустится**. Используйте бутстрап:

```bash
DOMAIN=bot.example.com \
CERTBOT_EMAIL=ops@example.com \
    ./nginx/init-letsencrypt.sh
```

Скрипт делает:
1. Поднимает временный nginx с `nginx.bootstrap.conf` (HTTP-only на :80) — обслуживает ACME-challenge.
2. Запускает certbot, получает боевой сертификат в volume `letsencrypt_certs`.
3. Останавливает временный nginx.
4. Запускает весь стек с TLS.

При отладке: `CERTBOT_STAGING=1` — staging-сертификат (не валиден в браузере, но rate-limit мягче).

---

## Шаг 4. Запуск и проверка

```bash
docker compose ps                       # все healthy
docker compose logs -f bot              # должен быть webhook_set + bot_idle_in_webhook_mode
```

Порядок старта:
1. `db` и `redis` — healthcheck.
2. `migrate` — alembic upgrade head, `service_completed_successfully`.
3. `bot`, `api`, `worker*`, `beat` — стартуют после `migrate`.
4. `nginx` — подставляет `${DOMAIN}` в конфиг (через envsubst), проксирует на api.
5. `admin_panel` и `web_panel` — npm build → копирование в shared volume → exit. **Идемпотентны** (skip если `index.html` уже есть). Чтобы пересобрать фронт — удалите `index.html` в томе.
6. `certbot` — раз в 12 часов пробует обновить.
7. `db_backup` — ждёт ближайшие `BACKUP_HOUR_UTC:00` UTC.

Проверки:

```bash
# 1. Health
curl -fsS https://bot.example.com/health
# ожидаем {"status":"ok","db":"ok","redis":"ok"}

# 2. Telegram webhook
. ./.env
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
# pending_update_count: 0
# url: ваш WEBHOOK_HOST/webhooks/telegram

# 3. Webhook end-to-end (через прокси, если используется)
curl -sk -X POST https://bot.example.com/webhooks/telegram \
  -H "X-Telegram-Bot-Api-Secret-Token: $WEBHOOK_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"update_id":1}' \
  -w '\nHTTP %{http_code}\n'
# ожидаем HTTP 200 {"ok":true}

# 4. Память — ничего не упирается в потолок
docker stats --no-stream
```

---

## Обновление

**Автоматически:** `git push origin main` → CI собирает образ и публикует в GHCR → Watchtower на VPS подтягивает за ≤300 секунд (раз в 5 минут) и graceful-restart'ит app-контейнеры. nginx, db, redis Watchtower не трогает.

**Вручную (если Watchtower выключен или нужно срочно):**
```bash
docker compose pull
docker compose up -d --wait
```

`--wait` дожидается healthcheck. Миграции применяются автоматически one-shot сервисом `migrate`.

**Применение compose-изменений (без перебилда образа):**
Изменения в `docker-compose.yml` (mem_limit, env, healthcheck) или в `nginx/nginx.conf` — это **файлы на хосте**, рестарта compose достаточно:
```bash
docker compose up -d                # переподнимет только то, что изменилось
docker compose restart nginx        # для правок в nginx.conf без обновления образа
```

---

## Откат

```bash
git log --oneline -20            # найти последний здоровый коммит
git checkout <hash>
docker compose build             # если правили src/
docker compose up -d --wait

# Если нужна обратная миграция:
docker compose exec api alembic downgrade -1
```

---

## Настройка ЮKassa webhook

ЛК ЮKassa → HTTP-уведомления:
- URL: `https://bot.example.com/webhooks/yukassa`
- События: `payment.succeeded`, `payment.canceled`.

HMAC-подпись включается в том же разделе (используется `YUKASSA_SECRET_KEY`). При отсутствии подписи fallback — IP-whitelist YuKassa в `src/api/webhooks.py`.

---

## Настройка Telegram webhook

Бот сам вызывает `set_webhook` при старте, если задан `WEBHOOK_HOST`. Ничего руками делать не надо. Но запомните:
- В webhook-режиме бот регистрирует endpoint и **спит** (`asyncio.Event().wait()`). Сам uvicorn не запускает.
- Доставку обеспечивает **api**-сервис (`src/api/main.py:/webhooks/telegram`), nginx → api.
- Если `set_webhook` не получается (api.telegram.org недоступен) — настройте `WEBHOOK_HOST` через прокси (см. шаг 2.1).

---

## Мониторинг

**UptimeRobot / Pingdom:** простой HTTP-check на `https://bot.example.com/health` → `"status":"ok"`.

**Prometheus / Grafana** (опционально): `https://internal-host/metrics` — доступен только из RFC1918-сетей (nginx блокирует внешние).

**Логи:** все JSON, structlog, доступны через `docker compose logs <service>`. Для длительной агрегации настройте Loki/Vector.

---

## Бэкапы

Автоматические ежедневные дампы в volume `db_backups`. Получить локальную копию:

```bash
docker run --rm -v bukvatrans_db_backups:/src -v $(pwd):/dst alpine \
    sh -c 'cp /src/transcribe_bot_*.sql.gz /dst/'
```

Восстановление — см. [`docs/RUNBOOK.md`](RUNBOOK.md#восстановление-бд-из-бэкапа-restore-from-backup).

---

## Регулярные операции

| Что | Когда | Как |
|---|---|---|
| Поверхностная очистка docker | каждый месяц | `docker system prune -af --volumes=false` |
| Перевыпуск TLS | автоматически | certbot раз в 12ч; cron не нужен |
| Ротация cert.docker config | ~раз в год | новый PAT в `~/.docker/config.json`, `docker compose restart watchtower` |
| Освобождение swap | при > 50% использования | `swapoff /swapfile && swapon /swapfile` (выгрузит холодные страницы) |
| Обновление yt-dlp | автоматически | `pip install -U yt-dlp` стоит в Dockerfile, перезапекается с каждым образом |
