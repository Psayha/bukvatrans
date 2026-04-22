# TranscribeBot (bukvatrans)

Telegram-бот транскрибации аудио/видео с подписками, реферальной программой и интеграцией с ЮKassa (54-ФЗ).

**Стек:** aiogram 3 · FastAPI · Celery + Redis · PostgreSQL · Groq Whisper · Anthropic Claude · yt-dlp · nginx + Let's Encrypt.

---

## Развёртывание

См. [`docs/DEPLOY.md`](docs/DEPLOY.md) — пошаговая инструкция для чистого VPS.

**Короткая версия:**

```bash
git clone ... && cd bukvatrans
cp .env.example .env    # заполни все поля
DOMAIN=bot.example.com CERTBOT_EMAIL=ops@example.com ./nginx/init-letsencrypt.sh
docker compose up -d
```

Миграции применяются автоматически при запуске контейнеров (см. `scripts/entrypoint.sh`).

---

## Эксплуатация

- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — инциденты и их разрешение.
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — деплой, откат, обновление.
- [`docs/LEGAL.md`](docs/LEGAL.md) — чек-лист юридических требований.
- [`docs/legal/`](docs/legal/) — шаблоны Политики ПДн и Оферты.

**Наблюдаемость:**
- `/health` — состояние БД и Redis (для UptimeRobot).
- `/metrics` — Prometheus, доступен только из внутренней сети (nginx `allow 10.0.0.0/8`).
- Sentry — ошибки с фильтрацией токенов.
- Логи: JSON через structlog, ротация `50m x 5` на контейнер.

**Резервные копии:**
- Сервис `db_backup` делает `pg_dump --format=plain` ежедневно в 03:00 UTC, хранит `BACKUP_RETENTION_DAYS` (по умолчанию 14) в volume `db_backups`.
- Восстановление: см. [`docs/RUNBOOK.md#restore-from-backup`](docs/RUNBOOK.md).

---

## Разработка

```bash
pip install -r requirements.txt -r requirements-dev.txt
BOT_TOKEN=... pytest tests/ --cov=src
ruff check src/ tests/ --select=E,W,F --ignore=E501
alembic upgrade head    # против локальной БД из .env
```

**Staging:**
```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```
Staging использует HTTP на порту 8080, отключает certbot и db_backup, снижает concurrency.

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
