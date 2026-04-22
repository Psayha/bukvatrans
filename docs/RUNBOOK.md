# Runbook

Сценарии инцидентов с проверенными командами. Все команды выполняются на хосте, где запущен `docker compose`.

---

## Как посмотреть состояние кластера

```bash
docker compose ps
docker compose logs --tail=100 -f <service>
docker compose exec db psql -U bot transcribe_bot
docker compose exec redis redis-cli
```

---

## Инцидент: `/health` возвращает 503

1. Проверить, что БД отвечает:
   ```bash
   docker compose exec db pg_isready -U bot -d transcribe_bot
   docker compose logs db | tail -50
   ```
2. Проверить Redis:
   ```bash
   docker compose exec redis redis-cli ping
   ```
3. Если БД не стартует — проверить диск:
   ```bash
   df -h
   ```
4. Если диск забит — см. «Забился диск».

---

## Инцидент: транскрибации висят в status=processing

1. Посмотреть очередь:
   ```bash
   docker compose exec redis redis-cli -n 0 LLEN transcription
   docker compose exec redis redis-cli -n 0 LLEN celery_dlq
   ```
2. Проверить, что воркер жив:
   ```bash
   docker compose ps worker
   docker compose logs worker --tail=200
   ```
3. Если воркер упал и задачи застряли > 40 мин — рестарт:
   ```bash
   docker compose restart worker
   ```
   При `task_acks_late=True` незавершённые задачи будут переданы новому воркеру.
4. Если в DLQ много сообщений — их надо разобрать вручную:
   ```bash
   docker compose exec redis redis-cli -n 0 LRANGE celery_dlq 0 -1
   ```

---

## Инцидент: Groq API недоступен (массовые ошибки)

1. Проверить статус: https://status.groq.com/
2. Если подтверждённый outage — **поставить очередь на паузу**:
   ```bash
   docker compose exec worker celery -A src.worker.app control cancel_consumer transcription
   ```
   Новые задачи не будут приниматься, пользователи увидят ошибку скачивания.
3. После восстановления — возобновить:
   ```bash
   docker compose exec worker celery -A src.worker.app control add_consumer transcription
   ```
4. Задачи из очереди обрабатываются по FIFO.

---

## Инцидент: ЮKassa webhook не приходит

1. Проверить последние поступления в логах:
   ```bash
   docker compose logs nginx | grep '/webhooks/yukassa'
   docker compose logs api | grep yukassa
   ```
2. Если нет даже в nginx — проблема на стороне ЮKassa или DNS. Проверить:
   ```bash
   curl -I https://bot.example.com/webhooks/yukassa
   # должен быть 405 Method Not Allowed (т.к. POST only)
   ```
3. Если webhook приходит, но возвращает 403 — проверить IP и подпись:
   ```bash
   docker compose logs api | grep yukassa_webhook_rejected
   ```
4. Найти пропущенный платёж в ЛК ЮKassa по `payment_id`, ручками вставить транзакцию:
   ```bash
   docker compose exec api python -c "
   import asyncio
   from src.api.webhooks import _handle_payment_succeeded
   from src.db.base import async_session_factory
   obj = {
       'id': 'YOOKASSA_PAYMENT_ID',
       'amount': {'value': '649.00', 'currency': 'RUB'},
       'metadata': {'user_id': '111111', 'plan_key': 'basic_monthly'}
   }
   async def run():
       async with async_session_factory() as s:
           await _handle_payment_succeeded(obj, None, s)
   asyncio.run(run())
   "
   ```

---

## Инцидент: забился диск

```bash
df -h
du -sh /var/lib/docker/volumes/* | sort -rh | head -10
```

Частые причины:

- **Логи контейнеров**: ротация настроена (`50m x 5 = 250 МБ`/контейнер), но может быть > 2 ГБ суммарно. `docker compose restart` чистит текущие.
- **db_backups**: хранение 14 дней, но при малом диске можно ужать:
  ```bash
  BACKUP_RETENTION_DAYS=7  # в .env
  docker compose up -d db_backup
  ```
- **postgres_data**: растёт из-за неочищенных `transcriptions.result_text`. Retention-таска должна чистить (3 дня по умолчанию). Форс:
  ```bash
  docker compose exec worker_maintenance celery -A src.worker.app call src.worker.tasks.maintenance.purge_old_transcription_text
  ```
- **Временные файлы**: `cleanup_tmp_files` раз в 30 мин. Форс:
  ```bash
  docker compose exec worker_maintenance celery -A src.worker.app call src.worker.tasks.maintenance.cleanup_tmp_files
  ```

---

## Восстановление БД из бэкапа {#restore-from-backup}

**ВНИМАНИЕ:** операция деструктивна, выполняется только на инстансе с подтверждённым инцидентом.

```bash
# 1. Остановить всё, что пишет в БД.
docker compose stop bot worker worker_summary worker_maintenance beat api

# 2. Посмотреть доступные дампы:
docker compose run --rm -v bukvatrans_db_backups:/bk alpine ls -lh /bk

# 3. Восстановить.
docker compose run --rm -v bukvatrans_db_backups:/bk -e PGPASSWORD=$DB_PASSWORD postgres:16-alpine \
    sh -c "gunzip -c /bk/transcribe_bot_YYYYMMDDTHHMMSSZ.sql.gz | psql -h db -U bot -d transcribe_bot"

# 4. Проверить целостность:
docker compose exec db psql -U bot -d transcribe_bot -c "SELECT count(*) FROM users;"

# 5. Запустить сервисы:
docker compose up -d
```

---

## Инцидент: Sentry шлёт алерт `transcription_error`

1. Проверить, что за ошибка:
   ```bash
   docker compose logs worker --tail=500 | grep -B 2 transcription_error
   ```
2. Типовые причины:
   - `UnsafeURLError` — пользователь прислал опасную ссылку, не проблема.
   - `URLTooLargeError` — видео слишком длинное/тяжёлое, не проблема.
   - `HTTPStatusError: 429` от Groq — rate limit, временно. Снизить `GROQ_MAX_CONCURRENCY` в `services/transcription.py` (5 → 3).
   - `HTTPStatusError: 5xx` от Groq — outage, см. соответствующий пункт.
3. Массовые ошибки → ставить очередь на паузу.

---

## Ротация Telegram webhook secret

Если подозрение на утечку `WEBHOOK_SECRET`:

```bash
# 1. Сгенерить новый:
python -c 'import secrets; print(secrets.token_urlsafe(48))'

# 2. Обновить в .env, сделать restart бота:
docker compose restart bot

# 3. Бот при старте перерегистрирует webhook с новым секретом.
```

---

## Ротация BOT_TOKEN

```bash
# В @BotFather → /revoke → получить новый токен.
# Обновить BOT_TOKEN в .env, restart всего:
docker compose restart bot api worker worker_summary worker_maintenance beat
```

---

## Ротация YUKASSA_SECRET_KEY

```bash
# В ЛК ЮKassa → перевыпустить секретный ключ.
# Обновить YUKASSA_SECRET_KEY в .env:
docker compose restart api bot
```

---

## Полный перезапуск

```bash
docker compose down
docker compose up -d --wait
```

`--wait` дожидается всех healthcheck. `down` **без** `-v` не трогает volumes (БД, Redis, бэкапы сохраняются).
