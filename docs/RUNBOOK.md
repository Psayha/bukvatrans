# Runbook

Сценарии инцидентов с проверенными командами. Все команды выполняются на хосте, где запущен `docker compose`. Перед запуском — `cd /srv/bukvatrans` (иначе compose не найдёт файл и упадёт с `no configuration file provided`).

---

## Как посмотреть состояние кластера

```bash
docker compose ps
docker compose logs --tail=100 -f <service>
docker compose exec db psql -U bot transcribe_bot
docker compose exec redis redis-cli

# Память по контейнерам — сразу видно, кто упирается
docker stats --no-stream

# Системно
uptime              # load average
free -h             # ОЗУ + swap
df -h /             # диск
```

---

## Инцидент: бот не отвечает на команды

Самый частый случай. Воркфлоу:

1. **Telegram-сторона** — копит ли он апдейты:
   ```bash
   . ./.env
   curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool | grep -E 'pending|last_error'
   ```
   - `pending_update_count > 0` + свежий `last_error_date` → апдейты не доходят до сервера.
   - `pending_update_count: 0` → дело не во вебхуке, см. дальше.

2. **End-to-end-проба webhook'а от себя**:
   ```bash
   curl -sk -X POST https://bot.example.com/webhooks/telegram \
     -H "X-Telegram-Bot-Api-Secret-Token: $WEBHOOK_SECRET" \
     -H 'Content-Type: application/json' \
     -d '{"update_id":1}' \
     -w '\nHTTP %{http_code}\n'
   ```
   Ожидаем `HTTP 200 {"ok":true}`. Если 502 — см. «nginx 502 на webhook».

3. **api-логи**:
   ```bash
   docker compose logs --tail=50 api | grep -iE 'error|exception|killed|oom'
   ```

4. **Был ли OOM-килл**:
   ```bash
   sudo dmesg -T | grep -iE 'oom-kill|killed process' | tail -10
   ```
   Если убивали api/uvicorn — см. «OOM-cascade».

---

## Инцидент: nginx 502 на /webhooks/telegram

Симптомы:
```
nginx-1 | connect() failed (111: Connection refused)
        | upstream: "http://172.18.0.10:8000/webhooks/telegram"
```

Почти всегда — **nginx закэшировал старый IP api**. OSS nginx резолвит `server <name>` в `upstream` только при старте конфига и игнорит TTL.

В коде стека уже стоит `resolver 127.0.0.11 valid=10s ipv6=off;` + variable-based `proxy_pass`. После рестарта api он подхватит новый IP в течение 10 секунд.

Если правка ещё не задеплоена (старый образ):
```bash
docker compose restart nginx       # одноразовый workaround
```

Долгосрочно — задеплоить ветку, в которой `nginx/nginx.conf` использует `set $upstream_api ...; proxy_pass http://$upstream_api;` (см. коммит `d6377c3`).

Проверить, что фикс на месте:
```bash
docker compose exec -T nginx grep -E 'resolver|upstream_api' /etc/nginx/nginx.conf
```

---

## Инцидент: OOM-cascade (api / uvicorn / worker убиты)

Симптомы в `dmesg`:
```
Out of memory: Killed process ... (uvicorn) anon-rss:200000kB
Out of memory: Killed process ... (node)    total-vm:12422788kB
```

Что делать:

1. **Проверить swap**:
   ```bash
   swapon --show
   ```
   Если пусто — включить:
   ```bash
   sudo sh scripts/enable_swap.sh
   ```

2. **Проверить mem_limit'ы** в `docker-compose.yml`:
   ```bash
   docker stats --no-stream | awk '{print $1, $2, $4}' | column -t
   ```
   Если `MEM_USAGE` стучится в `LIMIT` (>90%) на каком-то сервисе — увеличьте лимит этого сервиса в compose, `docker compose up -d <service>`.

3. **Проверить, не запущен ли npm build в admin/web_panel** — это самый прожорливый процесс (node до 12 ГиБ виртуала). На штатном compose эти контейнеры идемпотентны (skip если `index.html` есть), но если кто-то удалил volume — пересборка заведётся:
   ```bash
   docker run --rm -v bukvatrans_admin_dist:/v alpine ls /v
   docker run --rm -v bukvatrans_web_dist:/v alpine ls /v
   ```
   Если `index.html` есть — никакого rebuild не было. Если нет — он сейчас запущен и будет жечь память.

4. **Снизить celery concurrency, если транскрибация раздувает память**:
   В `docker-compose.yml` сервисы `worker` (`--concurrency=2`) и `worker_summary` (`--concurrency=1`). Если стало совсем туго — `worker --concurrency=1`. После правки: `docker compose up -d worker`.

---

## Инцидент: транскрибация валится с 429 от Groq

Симптомы (в новых логах с `groq_http_error`):
```
status: 429
body: "Rate limit reached for model whisper-large-v3-turbo
       service tier on_demand on seconds of audio per hour (ASPH):
       Limit 7200, Used 6445, Requested 1601.
       Please try again in 7m3s"
```

Это **не баг**, это лимит Groq Free Tier — 7200 секунд аудио в час (= 2 часа). Решения:

1. **Подождать** окно — лимит скользящий, на 7 минутах он отпустит.
2. **Upgrade Groq** до Dev/Production tier: https://console.groq.com/settings/billing — × 10 лимиты. ~$0–10/мес для типичных объёмов.
3. **Понизить параллелизм воркера** на время — `concurrency: 1` в compose, `up -d worker`. Поможет растянуть окно.

Текущий `_should_retry` в `src/services/transcription.py` ретраит 429, но с потолком ожидания в 8 секунд (tenacity exponential 2..8). То есть на Groq-режиме «жди 7 минут» ретраи не помогают, и юзер получает ошибку. Tech-debt: парсить `Retry-After`/`message` и ждать столько, сколько просит Groq.

Чтобы посмотреть, что Groq на самом деле отвечает (после деплоя ветки `claude/investigate-system-load-bgXJJ`):
```bash
docker compose logs --since=10m worker 2>&1 | grep -A 2 'groq_http_error'
```

---

## Инцидент: транскрибация валится с 500 от Deno-прокси

Симптомы в логах:
```
status: 500
body: {"error":{"message":"Internal Server Error","type":"internal_server_error"}}
```

Это Deno Deploy не справляется с большим телом. Опции:

1. **Перенести Groq-прокси на Cloudflare Worker** — `scripts/groq_proxy_worker.js`. У CF: 100 МБ body, 30s wall-clock. У Deno Free: гораздо строже.
2. **Уменьшить размер чанков** — `CHUNK_DURATION_SECONDS` в `src/services/audio_processor.py` (сейчас 300с). Снижение до 180с почти вдвое сокращает body. Перебилд образа, рестарт worker.

---

## Инцидент: транскрибации висят в status=processing

1. Очередь:
   ```bash
   docker compose exec redis redis-cli -n 0 LLEN transcription
   docker compose exec redis redis-cli -n 0 LLEN celery_dlq
   ```

2. Воркер:
   ```bash
   docker compose ps worker
   docker compose logs worker --tail=200
   ```

3. Если воркер упал и задачи застряли > 40 мин:
   ```bash
   docker compose restart worker
   ```
   При `task_acks_late=True` незавершённые передадутся новому.

4. DLQ — разобрать вручную:
   ```bash
   docker compose exec redis redis-cli -n 0 LRANGE celery_dlq 0 -1
   ```

---

## Инцидент: yt-dlp падает с `Network is unreachable` или 60s-timeout

Симптомы (в логах worker):
```
Errno 101: Network is unreachable
```
или
```
Probe timeout (60s): <domain>
```

Это egress-блок: ваш VPS-провайдер null-route'ит CIDR этого сервиса (часто Instagram, иногда Twitter и пр.).

Вариант 1 — **отключить домен** в whitelist `src/utils/validators.py`. Пользователь увидит `URL_NOT_SUPPORTED` мгновенно, без 60-секундной задержки.

Вариант 2 — **поднять прокси** для yt-dlp. См. [«Включить WARP-прокси для yt-dlp»](#warp-proxy) ниже.

⚠️ Помните: `YDL_PROXY` применяется ко **всем** загрузкам. Если прописать ради одного домена — VK/RuTube/YouTube тоже пойдут через прокси, и могут начать timeout'ить.

---

## Включить WARP-прокси для yt-dlp {#warp-proxy}

Бесплатный SOCKS5 через Cloudflare WARP — пригодится для гео-блокированных платформ.

```bash
# 1. WARP в proxy-режиме (он слушает 127.0.0.1:40000 на хосте)
warp-cli registration show 2>/dev/null || warp-cli registration new
warp-cli mode proxy
warp-cli connect

# 2. socat-форвардер docker-bridge → loopback
apt-get install -y socat
GATEWAY=$(docker network inspect bukvatrans_default --format '{{(index .IPAM.Config 0).Gateway}}')
echo "Docker gateway: $GATEWAY"

# 3. systemd-unit, чтобы переживал ребут
cat > /etc/systemd/system/warp-bridge.service <<EOF
[Unit]
Description=Forward docker bridge to host WARP SOCKS5 proxy
After=warp-svc.service docker.service
Requires=warp-svc.service docker.service

[Service]
Type=simple
ExecStartPre=/bin/sh -c 'until docker network inspect bukvatrans_default >/dev/null 2>&1; do sleep 2; done'
ExecStart=/bin/sh -c 'GW=\$(docker network inspect bukvatrans_default --format "{{(index .IPAM.Config 0).Gateway}}"); exec /usr/bin/socat TCP-LISTEN:40000,bind=\$GW,reuseaddr,fork TCP:127.0.0.1:40000'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now warp-bridge.service

# 4. .env
echo "YDL_PROXY=socks5h://${GATEWAY}:40000" >> /srv/bukvatrans/.env
docker compose up -d worker bot
```

Проверка:
```bash
docker compose exec -T worker yt-dlp --proxy "$YDL_PROXY" \
  --no-playlist --skip-download --print 'TITLE: %(title)s' \
  https://www.instagram.com/reel/<id>/
```

Откатить — закомментировать `YDL_PROXY` в `.env`, `docker compose up -d worker bot`.

---

## Инцидент: ЮKassa webhook не приходит

1. Поступления в логах:
   ```bash
   docker compose logs nginx | grep '/webhooks/yukassa'
   docker compose logs api | grep yukassa
   ```

2. Если нет даже в nginx — на стороне ЮKassa или DNS:
   ```bash
   curl -I https://bot.example.com/webhooks/yukassa
   # 405 Method Not Allowed (POST only) = nginx виден, всё ок
   ```

3. 403 — сверить IP/подпись:
   ```bash
   docker compose logs api | grep yukassa_webhook_rejected
   ```

4. Найти пропущенный платёж в ЛК ЮKassa, провести ручками:
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
docker system df
du -sh /var/lib/docker/volumes/* | sort -rh | head -10
```

Частые причины:

- **Логи контейнеров**: ротация 50m × 5 = 250 МиБ/контейнер, при 12 контейнерах ~3 ГиБ. `docker compose restart` чистит текущие.
- **build cache** + **dangling images** — растёт с каждым deployment'ом. Освобождается:
  ```bash
  docker system prune -af --volumes=false   # БЕЗ удаления volumes — НЕ ТРОНЕТ БД
  docker builder prune -af                  # build cache отдельно
  ```
  Обычно освобождает 5–10 ГиБ.
- **db_backups**: хранение `BACKUP_RETENTION_DAYS=14`. Убрать:
  ```bash
  BACKUP_RETENTION_DAYS=7  # в .env
  docker compose up -d db_backup
  ```
- **postgres_data**: растёт из-за неочищенных `transcriptions.result_text`. Retention-таска чистит (`TRANSCRIPTION_RETENTION_DAYS=3`). Форс:
  ```bash
  docker compose exec worker_maintenance celery -A src.worker.app call src.worker.tasks.maintenance.purge_old_transcription_text
  ```
- **/tmp в worker**: `cleanup_tmp_files` каждые 30 мин. Форс:
  ```bash
  docker compose exec worker_maintenance celery -A src.worker.app call src.worker.tasks.maintenance.cleanup_tmp_files
  ```

---

## Инцидент: Конфликт имени контейнера при `up -d`

```
Error response from daemon: Conflict.
The container name "/bukvatrans-api-1" is already in use by container "..."
```

Бывает после кривого редеплоя — старый контейнер не успел удалиться. Лечится:
```bash
docker rm -f bukvatrans-api-1
docker compose up -d
```

Универсально:
```bash
docker rm -f $(docker ps -aq --filter 'name=bukvatrans-')
docker compose up -d
```

---

## Восстановление БД из бэкапа {#restore-from-backup}

**ВНИМАНИЕ:** операция деструктивна.

```bash
# 1. Остановить пишущие сервисы.
docker compose stop bot worker worker_summary worker_maintenance beat api

# 2. Доступные дампы.
docker compose run --rm -v bukvatrans_db_backups:/bk alpine ls -lh /bk

# 3. Восстановление.
docker compose run --rm -v bukvatrans_db_backups:/bk -e PGPASSWORD=$DB_PASSWORD postgres:16-alpine \
    sh -c "gunzip -c /bk/transcribe_bot_YYYYMMDDTHHMMSSZ.sql.gz | psql -h db -U bot -d transcribe_bot"

# 4. Целостность.
docker compose exec db psql -U bot -d transcribe_bot -c "SELECT count(*) FROM users;"

# 5. Запустить сервисы.
docker compose up -d
```

---

## Инцидент: Sentry шлёт алерт `transcription_error`

```bash
docker compose logs worker --tail=500 | grep -B 2 transcription_error
```

Типовые причины:
- `UnsafeURLError` — пользователь прислал опасную ссылку. Не проблема.
- `URLTooLargeError` — видео слишком длинное/тяжёлое. Не проблема.
- `HTTPStatusError: 429` от Groq — rate limit; см. «Транскрибация валится с 429».
- `HTTPStatusError: 5xx` от Groq/Deno — см. «500 от Deno-прокси».
- `groq_http_error` event — детали в `body=...`, оттуда диагноз.

---

## Утечка BOT_TOKEN

Если токен попал в чат / лог / Sentry:

```bash
# 1. В @BotFather → /revoke → подтвердить → получить новый токен.
# 2. Обновить BOT_TOKEN в .env (на сервере + у Deno-прокси, если он держит токен у себя).
# 3. Перезапустить всё, кто использует токен:
docker compose restart bot api worker worker_summary worker_maintenance beat
# 4. Проверить, что бот живой (см. «бот не отвечает на команды»).
```

⚠️ aiogram/aiohttp/celery логируют **полный URL** Telegram-API, который включает токен. Это значит, любая ошибка `bot.send_message(...)` попадает в логи с токеном в URL. Tech-debt: подмешать redact в structlog-processor.

---

## Ротация Telegram webhook secret

Если подозрение на утечку `WEBHOOK_SECRET`:

```bash
# 1. Сгенерить новый:
python -c 'import secrets; print(secrets.token_urlsafe(48))'

# 2. Обновить в .env, restart бота:
docker compose restart bot

# 3. Бот при старте перерегистрирует webhook с новым секретом.

# 4. Если используется Deno-прокси для webhook — обновить и в нём.
```

---

## Ротация YUKASSA_SECRET_KEY

```bash
# 1. ЛК ЮKassa → перевыпустить секретный ключ.
# 2. Обновить YUKASSA_SECRET_KEY в .env:
docker compose restart api bot
```

---

## Полный перезапуск

```bash
docker compose down
docker compose up -d --wait
```

`--wait` дожидается healthcheck. `down` **без** `-v` не трогает volumes (БД, Redis, бэкапы сохраняются).

⚠️ После `down` админ/веб-панели заберут на пересборку (если их volumes пустые) — это **тяжёлая** операция (до 200 МиБ RAM на node, ~12 ГиБ виртуала). На 2 ГиБ VPS это потенциальный OOM. Если такое случилось — посмотрите `dmesg | grep -i oom` и при необходимости поднимите этими сервисами вручную, по одному:
```bash
docker compose up -d db redis migrate
docker compose up -d bot api worker worker_summary worker_maintenance beat
docker compose up -d nginx admin_panel web_panel certbot db_backup watchtower
```
