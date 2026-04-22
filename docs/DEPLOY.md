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

```bash
CERTBOT_EMAIL=ops@example.com ./nginx/init-letsencrypt.sh
```

При тестировании можно добавить `CERTBOT_STAGING=1` — cert от Let's Encrypt staging (не валидный, но rate-limit мягче).

---

## Шаг 3. Запуск

```bash
docker compose up -d
docker compose ps
docker compose logs -f bot
```

При первом запуске:
1. `db` поднимается, ждёт healthcheck.
2. `api` / `bot` стартуют, `entrypoint.sh` выполняет `alembic upgrade head` — схема создаётся автоматически.
3. `nginx` подставляет `${DOMAIN}` в конфиг и слушает 80/443.
4. `certbot` сидит и раз в 12 часов пробует обновить серт.

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
