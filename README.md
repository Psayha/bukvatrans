# TranscribeBot (bukvatrans / Littera)

Telegram-бот для транскрибации аудио и видео с подписками, реферальной программой и интеграцией с ЮKassa (54-ФЗ). Дополнительно — публичная веб-версия и админ-панель.

**Стек:** aiogram 3 · FastAPI · Celery + Redis · PostgreSQL · Groq Whisper · OpenRouter (LLM саммари) · yt-dlp · nginx + Let's Encrypt · React (frontend).

---

## Архитектура

12 сервисов в `docker-compose.yml`, все с `mem_limit` (важно — стек рассчитан на работу на VPS 1.9 ГиБ с 2 ГиБ swap):

| Сервис | Что делает | mem_limit |
|---|---|---|
| **bot** | aiogram dispatcher; в webhook-режиме регистрирует endpoint и спит | 256m |
| **api** | FastAPI — `/webhooks/telegram`, `/webhooks/yukassa`, `/api/v1/*`, `/api/admin/*`, `/health`, `/metrics` | 320m |
| **worker** | Celery: транскрибация (Groq Whisper), concurrency=2 | 640m |
| **worker_summary** | Celery: саммари через OpenRouter, concurrency=1 | 320m |
| **worker_maintenance** | Celery: cleanup, ретеншн, expire-уведомления | 160m |
| **beat** | Celery beat scheduler | 128m |
| **db** | PostgreSQL 16, тюнинг через -c флаги | 256m |
| **redis** | broker (DB0) + cache/FSM/ratelimit, AOF, `maxmemory 96m noeviction` | 128m |
| **nginx** | TLS-терминатор + статика admin/web, docker-DNS resolver | 64m |
| **certbot** | автообновление Let's Encrypt | 64m |
| **db_backup** | ежедневный pg_dump в volume | 96m |
| **watchtower** | подтягивает свежий `:latest` из ghcr.io каждые 5 минут | 64m |

Плюс two one-shot сервиса: `migrate` (alembic upgrade head, при каждом старте), `admin_panel`/`web_panel` (npm build для React, **идемпотентно** — пропускает если `index.html` уже есть в томе).

---

## Поддерживаемые источники

- **Файлы** в чате: voice, audio, video.
- **Ссылки** через yt-dlp: YouTube, VK Видео, RuTube, TikTok, Google Диск, Яндекс Диск.
- **Instagram** — отключён. Без cookies (= без бот-аккаунта в IG) yt-dlp нестабилен, плюс на типичных RU-egress IP-блок Instagram'а налагается на сетевом уровне. См. `src/utils/validators.py`, чтобы вернуть.

---

## Прокси для гео-блокированных сервисов

Из РФ обычно недоступны напрямую: `api.telegram.org`, `api.groq.com`, иногда `api.openai.com`, Instagram. Для каждого — отдельный механизм:

| Кому нужен | Переменная | Что туда писать |
|---|---|---|
| Доставка Telegram-вебхука внутрь сервера | `WEBHOOK_HOST` | URL Deno/CF Worker, который редиректит `/webhooks/telegram` на ваш сервер. Шаблон: `scripts/telegram_webhook_proxy_worker.js` |
| Запросы бота `bot.send_message(...)` | прокси на уровне OS / aiogram | (см. ниже) |
| Скачивание аудио yt-dlp | `YDL_PROXY` | `socks5h://host:port` (например, через WARP) |
| Транскрибация (Groq Whisper) | `GROQ_API_BASE` | URL Deno/CF Worker, шаблон в `scripts/groq_proxy_deno.js` или `scripts/groq_proxy_worker.js` |

Подробнее в [`docs/DEPLOY.md#proxies`](docs/DEPLOY.md).

---

## Развёртывание

См. [`docs/DEPLOY.md`](docs/DEPLOY.md) — пошаговая инструкция для чистого VPS, включая swap-файл, начальный TLS, настройку прокси.

**TL;DR:**

```bash
git clone https://github.com/Psayha/bukvatrans.git /srv/bukvatrans
cd /srv/bukvatrans
cp .env.example .env             # заполнить
chmod 600 .env

sudo sh scripts/enable_swap.sh   # 2 ГиБ swap (если VPS < 4 ГиБ RAM)

DOMAIN=bot.example.com CERTBOT_EMAIL=ops@example.com ./nginx/init-letsencrypt.sh
docker compose up -d
```

Миграции применяются автоматически one-shot сервисом `migrate` (см. `scripts/entrypoint.sh`).

---

## Эксплуатация

- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — инциденты с проверенными командами (OOM, забитый диск, стейл-DNS у nginx, Groq rate-limit, ротация секретов, потеря Telegram webhook'а и т.д.).
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — деплой, обновление, откат, прокси.
- [`docs/LEGAL.md`](docs/LEGAL.md) — чек-лист требований 152-ФЗ, 54-ФЗ, ToS Telegram.
- [`docs/legal/`](docs/legal/) — шаблоны Политики ПДн и Оферты.

**Наблюдаемость:**
- `/health` — БД + Redis (для UptimeRobot).
- `/metrics` — Prometheus, доступ только из приватных подсетей (nginx `allow 10.0.0.0/8 …`).
- Sentry — ошибки с `_sentry_before_send` фильтром токенов.
- Логи: structlog → JSON, ротация `50m × 5 = 250 МиБ` на контейнер.

**Резервные копии:**
- `db_backup` делает `pg_dump --format=plain | gzip` ежедневно в `BACKUP_HOUR_UTC` (по умолчанию 03:00 UTC), хранит `BACKUP_RETENTION_DAYS=14` в volume `db_backups`.
- Восстановление: см. [`docs/RUNBOOK.md`](docs/RUNBOOK.md#восстановление-бд-из-бэкапа-restore-from-backup).

---

## Разработка

```bash
pip install -r requirements.txt -r requirements-dev.txt
BOT_TOKEN=fake pytest tests/ --cov=src
ruff check src/ tests/ --select=E,W,F --ignore=E501
alembic upgrade head    # против локальной БД из .env
```

**Staging:**
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```
Staging — HTTP на :8080, без certbot/db_backup, пониженная concurrency.

---

## Команды бота

| Команда | Назначение |
|---|---|
| `/start` | регистрация / приветствие |
| `/help` | список команд |
| `/profile`, `/balance`, `/history` | профиль и статистика |
| `/subscribe`, `/topup` | покупка подписки / пополнение |
| `/referral` | реферальная ссылка и статистика |
| `/promo` | ввод промокода (5 попыток/час) |
| `/language` | язык транскрибации |
| `/cancel` | отмена текущей задачи |
| `/privacy`, `/terms` | юридическая информация |
| `/admin*` | админ-команды (2FA через второго админа) |

---

## Лицензия и контакты

Proprietary. Всё исходящее из этого репозитория обрабатывается в РФ по 152-ФЗ.
