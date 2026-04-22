# Deployment Guide

## Требования к серверу

- Linux VPS с 2+ vCPU, 4+ ГБ RAM, 40+ ГБ SSD.
- Публичный IPv4, открытые порты 80 и 443, закрытые 5432/6379/8000.
- DNS A-запись с доменом на IP сервера.
- Docker 24+ и Docker Compose v2.

```bash
# Ubuntu/Debian:
apt update && apt install -y docker.io docker-compose-plugin git curl
```

---

## Шаг 1. Клонирование и .env

```bash
cd /srv
git clone https://github.com/Psayha/bukvatrans.git
cd bukvatrans
cp .env.example .env
chmod 600 .env
```

Отредактируйте `.env`. Минимум:

```ini
DOMAIN=bot.example.com
DB_PASSWORD=<длинный случайный>
BOT_TOKEN=<из @BotFather>
WEBHOOK_HOST=https://bot.example.com
WEBHOOK_SECRET=<64 случайных символа, будет проверяться на webhook>
WEBHOOK_HOST=https://bot.example.com

GROQ_API_KEY=<groq.com>
CLAUDE_API_KEY=<console.anthropic.com>
YUKASSA_SHOP_ID=<yookassa.ru личный кабинет>
YUKASSA_SECRET_KEY=<yookassa.ru личный кабинет>

ADMIN_IDS=111111,222222    # как минимум ДВА id для 2FA
ENV=production
SENTRY_DSN=https://...@sentry.io/...
SUPPORT_EMAIL=ops@example.com

# Юрлицо — для чеков 54-ФЗ и /privacy /terms
COMPANY_NAME="ИП Иванов И.И."
COMPANY_INN=...
COMPANY_OGRN=...
COMPANY_ADDRESS=...
```

---

## Шаг 2. Первичный выпуск TLS-сертификата

**Важно:** `nginx` в основном конфиге ссылается на TLS-файлы, которых на чистом сервере ещё нет. Поэтому прямой `docker compose up -d` на первом деплое **не запустится**. Используйте скрипт-бутстрап, он сам всё разрулит:

```bash
DOMAIN=bot.example.com \
CERTBOT_EMAIL=ops@example.com \
    ./nginx/init-letsencrypt.sh
```

Скрипт делает 4 шага:
1. Поднимает временный nginx с `nginx.bootstrap.conf` (HTTP-only на :80) — он обслуживает ACME-challenge от Let's Encrypt.
2. Запускает certbot, получает боевой сертификат в volume `letsencrypt_certs`.
3. Останавливает временный nginx.
4. Запускает весь стек (`docker compose up -d`) с основным конфигом и TLS.

При отладке можно добавить `CERTBOT_STAGING=1` — staging-серт (не валидный в браузере, но rate-limit мягче).

---

## Шаг 3. Проверка запуска

```bash
docker compose ps
docker compose logs -f bot
```

Порядок старта сервисов:
1. `db` и `redis` — базовые сервисы с healthcheck.
2. `migrate` — one-shot сервис: выполняет `alembic upgrade head` и выходит с кодом 0.
3. `bot`, `api`, `worker*`, `beat` — стартуют, когда `migrate` завершился успешно (`depends_on: condition: service_completed_successfully`). Никаких гонок за схемой.
4. `nginx` подставляет `${DOMAIN}` в конфиг и проксирует на `api`.
5. `certbot` раз в 12 часов пробует обновить серт.
6. `db_backup` ждёт ближайшие `BACKUP_HOUR_UTC:00` UTC (по умолчанию 03:00) и делает `pg_dump`.

---

## Шаг 4. Проверка

```bash
# health
curl -fsS https://bot.example.com/health
# should return {"status":"ok","db":"ok","redis":"ok"}

# webhook зарегистрирован в Telegram
docker compose exec bot python -c "
import asyncio, os
from aiogram import Bot
b = Bot(os.environ['BOT_TOKEN'])
print(asyncio.run(b.get_webhook_info()))
"
```

---

## Обновление

```bash
git pull
docker compose build
docker compose up -d --wait
```

`--wait` дожидается healthcheck всех сервисов. Миграции применяются автоматически.

## Откат

```bash
git log --oneline -20            # найти коммит до проблемного
git checkout <hash>
docker compose build
docker compose up -d --wait

# Если нужна обратная миграция:
docker compose exec api alembic downgrade -1
```

---

## Настройка ЮKassa webhook

В личном кабинете ЮKassa → HTTP-уведомления:
- URL: `https://bot.example.com/webhooks/yukassa`
- События: `payment.succeeded`, `payment.canceled`.

HMAC-подпись включается на стороне ЮKassa в том же разделе (используется `YUKASSA_SECRET_KEY`).

---

## Настройка Telegram webhook

Бот сам вызывает `set_webhook` при старте, если задан `WEBHOOK_HOST`. Ничего руками делать не надо.

---

## Мониторинг

**UptimeRobot / Pingdom:**
```bash
DOMAIN=bot.example.com BOT_TOKEN=... ./scripts/uptime_check.sh
```
Либо настройте HTTP-check на `https://bot.example.com/health` и ждите `"status":"ok"`.

**Prometheus / Grafana** (опционально): `https://internal-host/metrics` — только из внутренней сети (nginx блокирует внешние запросы на `/metrics`).

---

## Бэкапы

Автоматические ежедневные дампы лежат в volume `db_backups`. Получить локальную копию:

```bash
docker run --rm -v bukvatrans_db_backups:/src -v $(pwd):/dst alpine \
    sh -c 'cp /src/transcribe_bot_*.sql.gz /dst/'
```

Восстановление — см. `docs/RUNBOOK.md`.
