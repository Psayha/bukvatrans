# Техническое задание: Telegram-бот транскрибации аудио/видео

**Версия:** 1.0  
**Дата:** 2026-03-06  
**Статус:** Draft  

---

## Содержание

1. [Общее описание проекта](#1-общее-описание-проекта)
2. [Функциональные требования](#2-функциональные-требования)
3. [Архитектура системы](#3-архитектура-системы)
4. [База данных](#4-база-данных)
5. [API и интеграции](#5-api-и-интеграции)
6. [Telegram-бот: команды и сценарии](#6-telegram-бот-команды-и-сценарии)
7. [Монетизация и тарифы](#7-монетизация-и-тарифы)
8. [Безопасность](#8-безопасность)
9. [Обработка ошибок](#9-обработка-ошибок)
10. [Юнит-тесты](#10-юнит-тесты)
11. [Инфраструктура и деплой](#11-инфраструктура-и-деплой)
12. [Метрики и мониторинг](#12-метрики-и-мониторинг)
13. [Структура проекта](#13-структура-проекта)
14. [Роадмап и фазы разработки](#14-роадмап-и-фазы-разработки)

---

## 1. Общее описание проекта

### 1.1 Название и суть

**Рабочее название:** TranscribeBot  
**Тип:** Telegram-бот (без TWA)  
**Суть:** Сервис автоматической транскрибации аудио и видео с помощью ИИ. Пользователь отправляет файл или ссылку — получает текст и конспект.

### 1.2 Целевая аудитория

- Маркетологи, SMM-специалисты — расшифровка кастдевов, интервью
- Онлайн-школы, эксперты — конспекты лекций, вебинаров
- Предприниматели, ассистенты — протоколы встреч, созвонов
- HR, рекрутеры — расшифровка собеседований
- Журналисты — оперативная расшифровка интервью
- Студенты — конспекты лекций

### 1.3 Ключевые метрики продукта

- Время транскрибации: 1 час аудио ≤ 3 минут
- Точность: ≥ 97% на чистой речи на русском языке
- Uptime: ≥ 99.5%
- Время ответа бота на команду: ≤ 1 секунды

### 1.4 Технологический стек

| Компонент | Технология |
|---|---|
| Язык | Python 3.12 |
| Telegram-бот | aiogram 3.x |
| Веб-сервер | FastAPI (для вебхуков и внутренних эндпоинтов) |
| База данных | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x (async) |
| Очередь задач | Celery 5.x |
| Брокер очереди | Redis 7.x |
| Транскрибация | Groq Whisper API (whisper-large-v3-turbo) |
| Конспект | Claude API (claude-haiku-4-5) |
| Скачивание видео | yt-dlp |
| Оплата | ЮKassa |
| Хранилище файлов | S3-совместимое (Yandex Object Storage / MinIO) |
| Миграции БД | Alembic |
| Логирование | structlog + Sentry |
| Тесты | pytest + pytest-asyncio |
| Контейнеризация | Docker + Docker Compose |
| CI/CD | GitHub Actions |

---

## 2. Функциональные требования

### 2.1 Входные данные (что принимает бот)

| Тип | Детали |
|---|---|
| Голосовое сообщение TG | До 20 МБ (ограничение Telegram Bot API) |
| Аудиофайл | MP3, WAV, OGG, M4A, FLAC, AAC — до 2 ГБ |
| Видеофайл | MP4, MOV, AVI, MKV — до 2 ГБ |
| Видеосообщение TG (кружок) | До 20 МБ |
| Ссылка YouTube | До 4 часов |
| Ссылка Rutube | До 4 часов |
| Ссылка Google Drive | Публичный файл, до 2 ГБ |
| Ссылка Яндекс Диск | Публичный файл, до 2 ГБ |

### 2.2 Выходные данные

| Тип | Детали |
|---|---|
| Текст транскрибации | Полный текст сообщением в Telegram (если ≤ 4096 символов) |
| Текстовый файл .txt | Всегда прикладывается как документ |
| Файл .docx | По запросу пользователя |
| Конспект | Структурированная выжимка — отдельным сообщением |
| Субтитры .srt | По запросу (только для файлов, не ссылок) |

### 2.3 Функции системы

#### F-01: Транскрибация
- Принять медиа или ссылку
- Поставить в очередь
- Уведомить о начале обработки
- Извлечь аудио (если видео)
- Нарезать на чанки если > 25 МБ (лимит Groq)
- Транскрибировать через Groq Whisper
- Собрать результат
- Отправить пользователю

#### F-02: Конспект
- После транскрибации предложить кнопку "Сделать конспект"
- Прогнать текст через Claude API с шаблонным промптом
- Вернуть структурированную выжимку: тезисы, ключевые идеи, цитаты

#### F-03: Баланс и тарифы
- Учёт баланса в минутах/часах
- 3 бесплатные транскрибации при регистрации (≤ 30 минут каждая)
- Платные тарифы по подписке
- Pay-as-you-go пополнение баланса

#### F-04: Оплата
- Выставление счёта через ЮKassa
- Обработка webhook от ЮKassa
- Зачисление баланса после успешной оплаты
- История платежей в профиле

#### F-05: Реферальная программа
- Уникальная реф-ссылка для каждого пользователя
- 20% от оплат рефералов начисляется как бонусный баланс
- Вывод только на оплату сервиса (не на карту)

#### F-06: Профиль пользователя
- Текущий баланс
- Использованное время
- История транскрибаций (последние 10)
- Активная подписка
- Реф-ссылка и статистика рефералов

#### F-07: Очередь и статус
- Показ позиции в очереди
- Уведомление о завершении
- Отмена задачи (если ещё в очереди)

---

## 3. Архитектура системы

### 3.1 Компонентная схема

```
┌─────────────────────────────────────────────────────────────┐
│                        ПОЛЬЗОВАТЕЛЬ                          │
│                    (Telegram Client)                         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (Webhook / Polling)
┌──────────────────────────▼──────────────────────────────────┐
│                    TELEGRAM BOT SERVICE                      │
│                  aiogram 3.x + FastAPI                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Handlers   │  │  Middlewares │  │    FSM States     │  │
│  │  (команды,  │  │  (auth, rate │  │  (ожидание файла, │  │
│  │   медиа,    │  │   limit,     │  │   выбор действия, │  │
│  │  callback)  │  │   logging)   │  │   ввод оплаты)    │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
└──────────┬──────────────────────────────────────────────────┘
           │ push task
┌──────────▼──────────────────────────────────────────────────┐
│                      REDIS (Broker)                          │
│                   Очередь задач + FSM Storage                │
└──────────┬──────────────────────────────────────────────────┘
           │ consume task
┌──────────▼──────────────────────────────────────────────────┐
│                    CELERY WORKERS                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Task: transcribe_audio                              │   │
│  │  1. Скачать файл (TG API / yt-dlp / прямая ссылка)  │   │
│  │  2. Извлечь аудио (ffmpeg)                           │   │
│  │  3. Нарезать на чанки если > 25 МБ                  │   │
│  │  4. Отправить в Groq Whisper API                     │   │
│  │  5. Собрать текст                                    │   │
│  │  6. Сохранить в БД                                   │   │
│  │  7. Уведомить бота → отправить результат юзеру       │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Task: generate_summary                              │   │
│  │  1. Взять текст из БД                                │   │
│  │  2. Отправить в Claude API                           │   │
│  │  3. Вернуть конспект                                 │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────┬──────────────────────────────────────────────────┘
           │ read/write
┌──────────▼──────────────────────────────────────────────────┐
│                     POSTGRESQL                               │
│  users │ subscriptions │ transactions │ transcriptions │     │
│  usage_log │ referrals │ promo_codes                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  ВНЕШНИЕ СЕРВИСЫ                             │
│  Groq API │ Claude API │ ЮKassa │ Telegram Bot API           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              YANDEX OBJECT STORAGE (S3)                      │
│  Временное хранение аудиофайлов (TTL: 24 часа)              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Поток обработки транскрибации

```
User отправляет файл/ссылку
         │
         ▼
Handler validates input
         │
         ▼
Check user balance ──── Недостаточно ────▶ Предложить оплату
         │
    Достаточно
         │
         ▼
Create transcription record (status: PENDING)
         │
         ▼
Push task to Celery queue
         │
         ▼
Bot: "⏳ Принято! Позиция в очереди: N"
         │
         ▼
Worker picks up task
         │
         ▼
Download & extract audio ──── Ошибка ────▶ Notify user, refund
         │
         ▼
Split into chunks (if > 25MB)
         │
         ▼
Groq Whisper API (each chunk) ─── Ошибка ──▶ Retry x3, then refund
         │
         ▼
Merge results
         │
         ▼
Save to DB + S3
         │
         ▼
Deduct balance (actual duration)
         │
         ▼
Send result to user
+ inline buttons: [📋 Конспект] [📄 DOCX] [📑 SRT]
```

### 3.3 Принцип чанкинга аудио

Groq Whisper принимает файлы до 25 МБ. Для больших файлов:

```
Аудио > 25 МБ
     │
     ▼
ffmpeg: нарезка на сегменты по 10 минут с перекрытием 5 секунд
     │
     ▼
Параллельная отправка чанков в Groq (asyncio.gather)
     │
     ▼
Слияние текстов с учётом перекрытия (дедупликация по границам)
```

---

## 4. База данных

### 4.1 Схема таблиц

```sql
-- Пользователи
CREATE TABLE users (
    id              BIGINT PRIMARY KEY,           -- Telegram user_id
    username        VARCHAR(255),
    first_name      VARCHAR(255),
    last_name       VARCHAR(255),
    language_code   VARCHAR(10) DEFAULT 'ru',
    balance_seconds INTEGER DEFAULT 0,            -- баланс в секундах
    free_uses_left  INTEGER DEFAULT 3,            -- бесплатные транскрибации
    referrer_id     BIGINT REFERENCES users(id),  -- кто пригласил
    is_banned       BOOLEAN DEFAULT FALSE,
    is_admin        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Подписки
CREATE TABLE subscriptions (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    plan            VARCHAR(50) NOT NULL,         -- 'basic', 'pro'
    status          VARCHAR(20) NOT NULL,         -- 'active', 'cancelled', 'expired'
    seconds_limit   INTEGER,                      -- NULL = безлимит
    started_at      TIMESTAMPTZ NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    yukassa_sub_id  VARCHAR(255),                 -- ID подписки в ЮKassa
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Транзакции / платежи
CREATE TABLE transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    type            VARCHAR(30) NOT NULL,    -- 'subscription', 'topup', 'refund', 'referral_bonus'
    amount_rub      NUMERIC(10, 2),
    seconds_added   INTEGER,
    status          VARCHAR(20) NOT NULL,    -- 'pending', 'success', 'failed', 'refunded'
    yukassa_id      VARCHAR(255),
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Транскрибации
CREATE TABLE transcriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 'pending', 'processing', 'done', 'failed', 'cancelled'
    source_type     VARCHAR(20) NOT NULL,
    -- 'voice', 'audio', 'video', 'youtube', 'rutube', 'gdrive', 'yadisk'
    source_url      TEXT,                         -- ссылка, если была ссылка
    file_name       VARCHAR(500),
    file_size_bytes BIGINT,
    duration_seconds INTEGER,                     -- реальная длительность
    language        VARCHAR(10),                  -- определённый язык
    result_text     TEXT,                         -- полный текст
    s3_key          VARCHAR(500),                 -- ключ в S3
    summary_text    TEXT,                         -- конспект
    error_message   TEXT,
    celery_task_id  VARCHAR(255),
    seconds_charged INTEGER DEFAULT 0,
    is_free         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- Лог использования (аналитика)
CREATE TABLE usage_log (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    action          VARCHAR(50) NOT NULL,
    -- 'transcribe_start', 'transcribe_done', 'summary_request', 'payment', etc.
    meta            JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Рефералы
CREATE TABLE referrals (
    id              SERIAL PRIMARY KEY,
    referrer_id     BIGINT NOT NULL REFERENCES users(id),
    referred_id     BIGINT NOT NULL REFERENCES users(id) UNIQUE,
    bonus_earned_rub NUMERIC(10,2) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Промокоды
CREATE TABLE promo_codes (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(50) UNIQUE NOT NULL,
    type            VARCHAR(30) NOT NULL,   -- 'free_seconds', 'discount_percent'
    value           INTEGER NOT NULL,       -- секунды или процент
    max_uses        INTEGER,
    used_count      INTEGER DEFAULT 0,
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Использования промокодов
CREATE TABLE promo_code_uses (
    id              SERIAL PRIMARY KEY,
    promo_code_id   INTEGER NOT NULL REFERENCES promo_codes(id),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(promo_code_id, user_id)
);
```

### 4.2 Индексы

```sql
CREATE INDEX idx_transcriptions_user_id ON transcriptions(user_id);
CREATE INDEX idx_transcriptions_status ON transcriptions(status);
CREATE INDEX idx_transcriptions_created_at ON transcriptions(created_at DESC);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_usage_log_user_id_created ON usage_log(user_id, created_at DESC);
CREATE INDEX idx_subscriptions_user_status ON subscriptions(user_id, status);
```

---

## 5. API и интеграции

### 5.1 Groq Whisper API

**Эндпоинт:** `https://api.groq.com/openai/v1/audio/transcriptions`  
**Модель:** `whisper-large-v3-turbo`  
**Лимит файла:** 25 МБ  
**Поддерживаемые форматы:** mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg  

```python
# src/services/transcription.py

import httpx
from pathlib import Path

async def transcribe_chunk(
    audio_path: Path,
    language: str = "ru",
    api_key: str = ""
) -> str:
    """Транскрибировать один чанк аудио через Groq Whisper."""
    async with httpx.AsyncClient(timeout=120) as client:
        with open(audio_path, "rb") as f:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (audio_path.name, f, "audio/mpeg")},
                data={
                    "model": "whisper-large-v3-turbo",
                    "language": language,
                    "response_format": "verbose_json",  # для таймкодов
                    "temperature": 0,
                }
            )
        response.raise_for_status()
        data = response.json()
        return data["text"]
```

**Rate limits Groq:**
- Free tier: 7200 секунд аудио в час
- Paid: без ограничений
- Retry стратегия: exponential backoff, max 3 попытки, задержки 2s → 4s → 8s

### 5.2 Claude API (конспекты)

**Модель:** `claude-haiku-4-5` (дешевле, достаточно для суммаризации)  

**Промпт для конспекта:**

```python
SUMMARY_PROMPT = """Ты — профессиональный редактор и конспектировщик. 
Тебе дан текст транскрибации аудио/видео материала.

Создай структурированный конспект строго на русском языке со следующими разделами:

## 📌 Ключевая мысль
[1-2 предложения — главная идея всего материала]

## 📋 Основные тезисы
[3-7 ключевых тезиса маркированным списком]

## 💡 Важные детали
[Факты, цифры, имена, конкретные примеры из текста]

## 🗣️ Цитаты
[2-3 наиболее значимые цитаты из текста]

## ✅ Итог / Выводы
[Краткое резюме в 2-3 предложениях]

Текст транскрибации:
{text}

Важно: отвечай ТОЛЬКО конспектом, без вступлений и пояснений."""
```

**Обрезка текста:** если текст > 150 000 символов — берём первые 50 000, середину (50 000) и последние 50 000 с пометкой о пропуске.

### 5.3 ЮKassa

**Webhook URL:** `POST /webhooks/yukassa`  
**Подпись:** проверка через `X-Request-Id` и IP whitelist ЮKassa

```python
# src/api/webhooks.py

YUKASSA_IPS = [
    "185.71.76.0/27",
    "185.71.77.0/27", 
    "77.75.153.0/25",
    "77.75.156.11",
    "77.75.156.35",
    "77.75.154.128/25",
    "2a02:5180::/32",
]

async def handle_yukassa_webhook(request: Request) -> JSONResponse:
    """Обработка webhook от ЮKassa."""
    # 1. Проверить IP источника
    # 2. Распарсить тело запроса
    # 3. Найти транзакцию по payment_id
    # 4. Проверить статус: succeeded / cancelled
    # 5. Зачислить баланс или отметить ошибку
    # 6. Вернуть 200 OK (иначе ЮKassa будет повторять)
```

**Тарифы и суммы:**

| Тариф | Период | Цена | Что даёт |
|---|---|---|---|
| Базовый | 1 месяц | 649₽ | 108 000 сек (30 ч) |
| Базовый | 1 год | 3 890₽ | 1 296 000 сек (360 ч) |
| Про | 1 месяц | 1 449₽ | Безлимит (-1 в БД) |
| Про | 1 год | 8 690₽ | Безлимит (-1 в БД) |
| Пополнение | Разовое | 99₽ | 7 200 сек (2 ч) |
| Пополнение | Разовое | 299₽ | 25 200 сек (7 ч) |
| Пополнение | Разовое | 499₽ | 43 200 сек (12 ч) |

> Безлимит в БД хранится как `seconds_limit = -1`

### 5.4 yt-dlp

```python
# src/services/downloader.py

import asyncio
import yt_dlp

YDL_OPTS = {
    "format": "bestaudio/best",
    "outtmpl": "/tmp/%(id)s.%(ext)s",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "128",   # достаточно для речи
    }],
    "max_filesize": 2 * 1024 * 1024 * 1024,  # 2 ГБ
    "socket_timeout": 30,
    "retries": 3,
    "quiet": True,
    "no_warnings": True,
}

SUPPORTED_DOMAINS = [
    "youtube.com", "youtu.be",
    "rutube.ru",
    "vk.com", "vkvideo.ru",
    "ok.ru",
    "drive.google.com",
    "disk.yandex.ru", "yadi.sk",
]
```

### 5.5 ffmpeg — нарезка чанков

```python
# src/services/audio_processor.py

import asyncio
import subprocess
from pathlib import Path

CHUNK_DURATION_SECONDS = 600   # 10 минут
OVERLAP_SECONDS = 5            # перекрытие для контекста на границах

async def split_audio(input_path: Path, output_dir: Path) -> list[Path]:
    """Нарезать аудио на чанки по 10 минут с перекрытием."""
    chunks = []
    duration = await get_audio_duration(input_path)
    
    start = 0
    chunk_idx = 0
    while start < duration:
        chunk_path = output_dir / f"chunk_{chunk_idx:04d}.mp3"
        end = min(start + CHUNK_DURATION_SECONDS + OVERLAP_SECONDS, duration)
        
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(end - start),
            "-i", str(input_path),
            "-acodec", "libmp3lame",
            "-ab", "128k",
            str(chunk_path)
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        chunks.append(chunk_path)
        
        start += CHUNK_DURATION_SECONDS
        chunk_idx += 1
    
    return chunks

async def get_audio_duration(path: Path) -> float:
    """Получить длительность аудио через ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    stdout, _ = await proc.communicate()
    return float(stdout.decode().strip())
```

---

## 6. Telegram-бот: команды и сценарии

### 6.1 Команды бота

| Команда | Описание |
|---|---|
| `/start` | Приветствие, регистрация, 3 бесплатных использования |
| `/start ref_USERID` | Регистрация по реф-ссылке |
| `/help` | Инструкция по использованию |
| `/profile` | Профиль: баланс, статистика, подписка |
| `/balance` | Текущий баланс и история списаний |
| `/subscribe` | Выбор тарифа и оплата |
| `/topup` | Разовое пополнение баланса |
| `/history` | Последние 10 транскрибаций |
| `/referral` | Реф-ссылка и статистика |
| `/promo` | Ввод промокода |
| `/cancel` | Отмена текущей задачи (если в очереди) |
| `/status` | Статус текущей задачи |
| `/language` | Выбор языка транскрибации |
| `/admin` | Админ-панель (только для is_admin=True) |

### 6.2 FSM состояния

```python
# src/bot/states.py
from aiogram.fsm.state import State, StatesGroup

class LanguageSelect(StatesGroup):
    waiting_language = State()

class PaymentFlow(StatesGroup):
    selecting_plan = State()
    selecting_period = State()
    awaiting_payment = State()

class PromoFlow(StatesGroup):
    waiting_code = State()

class AdminFlow(StatesGroup):
    main_menu = State()
    broadcast_message = State()
    user_lookup = State()
    add_balance = State()
```

### 6.3 Inline-кнопки после транскрибации

```
┌─────────────────────────────────────┐
│  ✅ Транскрибация готова!            │
│  Длительность: 43 мин 20 сек        │
│  Списано: 2600 сек с баланса         │
│  Остаток: 104 800 сек (~29 ч)        │
│                                     │
│  [📋 Конспект]  [📄 DOCX]           │
│  [📑 SRT субтитры]  [🔄 Повторить]  │
└─────────────────────────────────────┘
```

### 6.4 Сценарий: новый пользователь

```
1. /start
   → Приветствие + что умеет бот
   → Зарегистрировать в БД
   → "У вас 3 бесплатные транскрибации (до 30 мин каждая)"
   → Кнопка [Отправить аудио/видео]

2. Пользователь отправляет голосовое
   → "⏳ Принято! Обрабатываем... (это займёт ~1 мин)"
   → Задача в Celery
   → Результат через 30–60 сек
   → Кнопки: [📋 Конспект] [📄 DOCX]

3. После 3-й бесплатной транскрибации
   → "Бесплатные попытки использованы"
   → Предложить тарифы с кнопками
```

### 6.5 Сценарий: оплата подписки

```
/subscribe
   → Показать тарифы inline-кнопками:
   
   [Базовый — 649₽/мес] [Базовый — 3890₽/год]
   [Про — 1449₽/мес]    [Про — 8690₽/год]
   
   → Выбор тарифа
   → "Вы выбрали: Про, 1 месяц — 1449₽"
   → Создать платёж в ЮKassa
   → Отправить inline-кнопку [💳 Оплатить] с ссылкой на payment URL
   → Ждать webhook от ЮKassa
   → Зачислить баланс / активировать подписку
   → "✅ Подписка активирована! Безлимит до 06.04.2026"
```

### 6.6 Middlewares

```python
# src/bot/middlewares/

# 1. DatabaseMiddleware — инжектирует сессию БД в хэндлер
# 2. UserMiddleware — регистрирует/обновляет пользователя
# 3. BanMiddleware — проверяет is_banned, блокирует запросы
# 4. RateLimitMiddleware — ограничение: не более 10 запросов в 60 сек на user_id
# 5. LoggingMiddleware — логирует все входящие update
```

### 6.7 Тексты и локализация

Все тексты хранятся в `src/bot/texts/ru.py` как константы. Не хардкодить строки в хэндлерах. На старте — только русский язык.

---

## 7. Монетизация и тарифы

### 7.1 Логика списания баланса

```python
def calculate_charge(duration_seconds: int, user: User) -> int:
    """
    Вернуть количество секунд к списанию.
    Округление вверх до полной минуты.
    """
    if user.has_active_unlimited_subscription():
        return 0  # безлимит не списывает
    
    # округляем вверх до полной минуты
    minutes = math.ceil(duration_seconds / 60)
    return minutes * 60
```

### 7.2 Проверка баланса перед транскрибацией

```python
async def check_can_transcribe(user: User, estimated_duration: int) -> tuple[bool, str]:
    """
    Проверить, может ли пользователь запустить транскрибацию.
    Для ссылок — estimated_duration = None (проверяем только факт наличия баланса > 0).
    """
    if user.is_banned:
        return False, "Ваш аккаунт заблокирован."
    
    if user.has_active_unlimited_subscription():
        return True, ""
    
    if user.free_uses_left > 0:
        return True, ""
    
    if user.balance_seconds <= 0:
        return False, "Недостаточно баланса. Пополните счёт или оформите подписку."
    
    if estimated_duration and user.balance_seconds < estimated_duration:
        return False, f"Недостаточно баланса. Файл ~{estimated_duration//60} мин, у вас {user.balance_seconds//60} мин."
    
    return True, ""
```

### 7.3 Реферальная программа

- Ссылка формата: `https://t.me/BOT_USERNAME?start=ref_{user_id}`
- При регистрации по ссылке: записать `referrer_id` в `users`
- При каждой успешной оплате реферала: начислить 20% суммы в рублях как `bonus_balance_rub`
- Бонусный баланс конвертируется в секунды по курсу: 1₽ = 73 сек (≈ 49₽/час → 1 час = 3600 сек)
- Реф-баланс можно тратить только на оплату внутри бота, не выводить

---

## 8. Безопасность

### 8.1 Telegram Bot API

**Проверка подписи webhook:**
```python
import hashlib, hmac

def verify_telegram_webhook(token: str, body: bytes, secret_header: str) -> bool:
    """Проверить X-Telegram-Bot-Api-Secret-Token."""
    secret = hashlib.sha256(token.encode()).digest()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, secret_header)
```

**Никогда не доверять `user_id` из текста сообщения** — только из `message.from_user.id`.

### 8.2 Валидация входных данных

```python
# Файлы
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024   # 2 ГБ
MAX_DURATION_SECONDS = 4 * 3600                  # 4 часа
ALLOWED_MIME_TYPES = {
    "audio/mpeg", "audio/ogg", "audio/wav", "audio/mp4",
    "audio/aac", "audio/flac", "video/mp4", "video/quicktime",
    "video/x-msvideo", "video/x-matroska",
}

# Ссылки — валидация домена перед yt-dlp
def is_allowed_url(url: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    return any(domain.endswith(d) for d in SUPPORTED_DOMAINS)
```

### 8.3 Rate Limiting

```python
# Redis-based rate limiting
RATE_LIMITS = {
    "transcription": {"calls": 5, "period": 300},   # 5 за 5 минут
    "payment": {"calls": 3, "period": 60},           # 3 за минуту
    "commands": {"calls": 30, "period": 60},          # 30 команд за минуту
}
```

### 8.4 Защита от злоупотреблений

- **Дублирование задач:** Redis-lock на `user_id` — один пользователь не может запустить 2 задачи одновременно
- **Повторная отправка одного файла:** Проверка `file_unique_id` из Telegram — если уже транскрибировали за последние 24 часа, вернуть кэшированный результат без списания баланса
- **Бан:** Автоматический бан при 50+ запросах в минуту. Ручной бан через `/admin`
- **Webhook ЮKassa:** Whitelist IP + проверка `idempotence_key` чтобы не зачислить дважды

### 8.5 Хранение секретов

- Все секреты в `.env` (не в коде)
- `.env` добавлен в `.gitignore`
- В production — использовать Yandex Lockbox или аналог
- Ротация API ключей: Groq и Claude — раз в 90 дней

```
# .env.example
BOT_TOKEN=
GROQ_API_KEY=
CLAUDE_API_KEY=
YUKASSA_SHOP_ID=
YUKASSA_SECRET_KEY=
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=
WEBHOOK_SECRET=
ADMIN_IDS=123456789,987654321
```

### 8.6 Безопасность файлов

- Файлы пользователей хранятся в S3 с **TTL 24 часа** (lifecycle policy)
- Доступ к S3 — только через presigned URLs (срок жизни 1 час)
- Временные файлы на диске (при обработке) удаляются в `finally` блоке
- Имена файлов санируются (только UUID + расширение, без имени от пользователя)

```python
# Всегда использовать такой паттерн для файлов
import uuid, tempfile
from pathlib import Path

async def process_audio(file_data: bytes, original_ext: str) -> Path:
    safe_filename = f"{uuid.uuid4()}.{original_ext.lower()}"
    tmp_path = Path(tempfile.gettempdir()) / safe_filename
    try:
        tmp_path.write_bytes(file_data)
        # ... обработка ...
        return result
    finally:
        tmp_path.unlink(missing_ok=True)
```

### 8.7 SQL Injection

- **Только SQLAlchemy ORM / параметризованные запросы**
- Никакой конкатенации строк в SQL

### 8.8 Логирование чувствительных данных

Не логировать: `BOT_TOKEN`, `API_KEY`, содержимое транскрибаций, `file_path`, персональные данные.

Логировать: `user_id`, `action`, `task_id`, `duration`, `error_type` (без стектрейса в продакшне).

---

## 9. Обработка ошибок

### 9.1 Классификация ошибок

| Код | Тип | Действие |
|---|---|---|
| `E001` | Неподдерживаемый формат файла | Сообщить пользователю, не списывать |
| `E002` | Файл слишком большой | Сообщить, не списывать |
| `E003` | Ошибка скачивания (yt-dlp) | Retry x2, затем сообщить, не списывать |
| `E004` | Groq API недоступен | Retry x3 exponential backoff, затем возврат баланса |
| `E005` | Groq API rate limit | Ставить в конец очереди, retry через 60 сек |
| `E006` | Файл не содержит аудио | Сообщить, не списывать |
| `E007` | Приватная ссылка (нет доступа) | Сообщить, не списывать |
| `E008` | Claude API недоступен | Только для конспекта — предложить повторить позже |
| `E009` | ЮKassa ошибка | Логировать, уведомить пользователя, не активировать |

### 9.2 Возврат баланса

```python
async def refund_transcription(transcription_id: UUID, session: AsyncSession):
    """Вернуть списанный баланс при ошибке транскрибации."""
    transcription = await get_transcription(transcription_id, session)
    if transcription.seconds_charged > 0:
        await add_balance(
            user_id=transcription.user_id,
            seconds=transcription.seconds_charged,
            reason=f"refund:transcription:{transcription_id}",
            session=session
        )
        transcription.seconds_charged = 0
        transcription.status = "failed"
```

### 9.3 Dead Letter Queue

Задачи, упавшие более 3 раз, уходят в `celery_dlq` очередь. Мониторинг DLQ — алерт в Telegram-чат разработчика.

---

## 10. Юнит-тесты

### 10.1 Структура тестов

```
tests/
├── conftest.py              # фикстуры: БД, бот, моки
├── unit/
│   ├── test_audio_processor.py
│   ├── test_transcription_service.py
│   ├── test_billing.py
│   ├── test_referral.py
│   ├── test_validators.py
│   └── test_url_validator.py
├── integration/
│   ├── test_groq_integration.py
│   ├── test_yukassa_webhook.py
│   └── test_bot_handlers.py
└── e2e/
    └── test_full_transcription_flow.py
```

### 10.2 conftest.py

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.db.models import Base
from src.db.models.user import User

@pytest_asyncio.fixture
async def db_session():
    """Тестовая БД в памяти."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession)
    async with async_session() as session:
        yield session
    
    await engine.dispose()

@pytest.fixture
def mock_groq_client():
    mock = AsyncMock()
    mock.audio.transcriptions.create.return_value = MagicMock(
        text="Тестовый текст транскрибации.",
        segments=[{"start": 0.0, "end": 5.0, "text": "Тестовый текст транскрибации."}]
    )
    return mock

@pytest.fixture
def mock_claude_client():
    mock = AsyncMock()
    mock.messages.create.return_value = MagicMock(
        content=[MagicMock(text="## 📌 Ключевая мысль\nТестовый конспект.")]
    )
    return mock

@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(
        id=123456789,
        username="testuser",
        first_name="Test",
        balance_seconds=7200,
        free_uses_left=0,
    )
    db_session.add(user)
    await db_session.commit()
    return user
```

### 10.3 test_billing.py

```python
# tests/unit/test_billing.py
import pytest
from src.services.billing import calculate_charge, check_can_transcribe

class TestCalculateCharge:
    def test_exact_minute(self):
        """Ровно 60 секунд → 60 секунд списывается."""
        assert calculate_charge(60) == 60

    def test_rounds_up(self):
        """61 секунда → округляется вверх до 120."""
        assert calculate_charge(61) == 120

    def test_zero_duration(self):
        """0 секунд → 0."""
        assert calculate_charge(0) == 0

    def test_large_file(self):
        """1 час 30 минут 1 секунда → округляется до 1 ч 31 мин."""
        assert calculate_charge(5401) == 5460  # 91 мин


class TestCheckCanTranscribe:
    @pytest.mark.asyncio
    async def test_banned_user_cannot_transcribe(self, test_user, db_session):
        test_user.is_banned = True
        can, msg = await check_can_transcribe(test_user, 3600)
        assert can is False
        assert "заблокирован" in msg

    @pytest.mark.asyncio
    async def test_free_uses_allow_transcribe(self, test_user, db_session):
        test_user.free_uses_left = 1
        test_user.balance_seconds = 0
        can, msg = await check_can_transcribe(test_user, 3600)
        assert can is True

    @pytest.mark.asyncio
    async def test_insufficient_balance(self, test_user, db_session):
        test_user.balance_seconds = 60
        test_user.free_uses_left = 0
        can, msg = await check_can_transcribe(test_user, 3600)
        assert can is False
        assert "баланса" in msg

    @pytest.mark.asyncio
    async def test_sufficient_balance(self, test_user, db_session):
        test_user.balance_seconds = 7200
        test_user.free_uses_left = 0
        can, msg = await check_can_transcribe(test_user, 3600)
        assert can is True
```

### 10.4 test_validators.py

```python
# tests/unit/test_validators.py
import pytest
from src.utils.validators import is_allowed_url, validate_file_size, validate_mime_type

class TestUrlValidator:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=test123", True),
        ("https://youtu.be/test123", True),
        ("https://rutube.ru/video/test", True),
        ("https://drive.google.com/file/d/test", True),
        ("https://disk.yandex.ru/i/test", True),
        ("https://yadi.sk/d/test", True),
        ("https://evil.com/malicious", False),
        ("https://youtube.evil.com/watch", False),
        ("javascript:alert(1)", False),
        ("", False),
        ("not_a_url", False),
    ])
    def test_url_validation(self, url, expected):
        assert is_allowed_url(url) == expected


class TestFileSizeValidator:
    def test_file_within_limit(self):
        assert validate_file_size(100 * 1024 * 1024) is True  # 100 МБ

    def test_file_exceeds_limit(self):
        assert validate_file_size(3 * 1024 * 1024 * 1024) is False  # 3 ГБ

    def test_zero_size(self):
        assert validate_file_size(0) is False


class TestMimeTypeValidator:
    @pytest.mark.parametrize("mime,expected", [
        ("audio/mpeg", True),
        ("audio/ogg", True),
        ("video/mp4", True),
        ("application/pdf", False),
        ("image/jpeg", False),
        ("text/plain", False),
    ])
    def test_mime_validation(self, mime, expected):
        assert validate_mime_type(mime) == expected
```

### 10.5 test_audio_processor.py

```python
# tests/unit/test_audio_processor.py
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from src.services.audio_processor import split_audio, merge_transcriptions

class TestSplitAudio:
    @pytest.mark.asyncio
    async def test_short_audio_no_split(self, tmp_path):
        """Файл < 10 минут → один чанк."""
        with patch("src.services.audio_processor.get_audio_duration", return_value=300.0):
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_proc.return_value = AsyncMock(wait=AsyncMock(return_value=0))
                chunks = await split_audio(Path("/fake/audio.mp3"), tmp_path)
                assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_long_audio_splits_correctly(self, tmp_path):
        """Файл 25 минут → 3 чанка (10+10+5 с перекрытием)."""
        with patch("src.services.audio_processor.get_audio_duration", return_value=1500.0):
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_proc.return_value = AsyncMock(wait=AsyncMock(return_value=0))
                chunks = await split_audio(Path("/fake/audio.mp3"), tmp_path)
                assert len(chunks) == 3


class TestMergeTranscriptions:
    def test_single_chunk(self):
        texts = ["Привет, это тест."]
        result = merge_transcriptions(texts)
        assert result == "Привет, это тест."

    def test_multiple_chunks_merged(self):
        texts = ["Первая часть текста.", "Вторая часть текста."]
        result = merge_transcriptions(texts)
        assert "Первая часть" in result
        assert "Вторая часть" in result

    def test_empty_chunks_skipped(self):
        texts = ["Нормальный текст.", "", "  ", "Ещё текст."]
        result = merge_transcriptions(texts)
        assert result.count("  ") == 0
```

### 10.6 test_yukassa_webhook.py

```python
# tests/integration/test_yukassa_webhook.py
import pytest
import json
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

WEBHOOK_PAYLOAD_SUCCESS = {
    "type": "notification",
    "event": "payment.succeeded",
    "object": {
        "id": "test_payment_123",
        "status": "succeeded",
        "amount": {"value": "649.00", "currency": "RUB"},
        "metadata": {"user_id": "123456789", "plan": "basic", "period": "monthly"},
        "paid": True,
    }
}

class TestYukassaWebhook:
    @pytest.mark.asyncio
    async def test_successful_payment_activates_subscription(self, async_client, db_session, test_user):
        with patch("src.api.webhooks.activate_subscription", new_callable=AsyncMock) as mock_activate:
            response = await async_client.post(
                "/webhooks/yukassa",
                json=WEBHOOK_PAYLOAD_SUCCESS,
                headers={"X-Request-Id": "test-idempotency-key"}
            )
            assert response.status_code == 200
            mock_activate.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_webhook_idempotent(self, async_client, db_session, test_user):
        """Повторный webhook с тем же idempotency_key не должен дублировать зачисление."""
        with patch("src.api.webhooks.activate_subscription", new_callable=AsyncMock) as mock_activate:
            headers = {"X-Request-Id": "same-key-123"}
            await async_client.post("/webhooks/yukassa", json=WEBHOOK_PAYLOAD_SUCCESS, headers=headers)
            await async_client.post("/webhooks/yukassa", json=WEBHOOK_PAYLOAD_SUCCESS, headers=headers)
            assert mock_activate.call_count == 1

    @pytest.mark.asyncio
    async def test_invalid_ip_rejected(self, async_client):
        """Запрос не с IP ЮKassa должен быть отклонён."""
        response = await async_client.post(
            "/webhooks/yukassa",
            json=WEBHOOK_PAYLOAD_SUCCESS,
            headers={"X-Forwarded-For": "1.2.3.4"}  # не IP ЮKassa
        )
        assert response.status_code == 403
```

### 10.7 test_referral.py

```python
# tests/unit/test_referral.py
import pytest
from src.services.referral import process_referral_bonus, calculate_bonus_seconds

class TestReferralBonus:
    def test_bonus_calculation_20_percent(self):
        """20% от 649₽ = 129.8₽ → конвертируем в секунды."""
        bonus_rub = calculate_bonus_seconds(649.00)
        assert abs(bonus_rub - 129.8) < 0.01

    @pytest.mark.asyncio
    async def test_referral_bonus_added_on_payment(self, db_session, test_user):
        referrer = test_user
        referred = ...  # создать второго юзера с referrer_id = referrer.id
        
        initial_balance = referrer.balance_seconds
        await process_referral_bonus(
            referrer_id=referrer.id,
            payment_amount_rub=649.0,
            session=db_session
        )
        await db_session.refresh(referrer)
        assert referrer.balance_seconds > initial_balance

    @pytest.mark.asyncio
    async def test_no_bonus_without_referrer(self, db_session, test_user):
        """Пользователь без реферера — не начислять."""
        test_user.referrer_id = None
        initial_balance = test_user.balance_seconds
        await process_referral_bonus(
            referrer_id=None,
            payment_amount_rub=649.0,
            session=db_session
        )
        assert test_user.balance_seconds == initial_balance
```

### 10.8 Конфигурация pytest

```ini
# pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests (no external dependencies)
    integration: Integration tests (may require external services)
    e2e: End-to-end tests
filterwarnings =
    ignore::DeprecationWarning
```

### 10.9 Запуск тестов

```bash
# Только юнит-тесты (быстро, в CI всегда)
pytest tests/unit/ -v --cov=src --cov-report=term-missing

# Интеграционные (с моками внешних сервисов)
pytest tests/integration/ -v -m "not e2e"

# Все тесты
pytest tests/ -v --cov=src --cov-report=html

# Покрытие — целевой показатель: ≥ 80%
```

---

## 11. Инфраструктура и деплой

### 11.1 Docker Compose

```yaml
# docker-compose.yml
version: "3.9"

services:
  bot:
    build: .
    command: python -m src.bot.main
    env_file: .env
    depends_on: [db, redis]
    restart: unless-stopped

  worker:
    build: .
    command: celery -A src.worker.app worker --loglevel=info --concurrency=4
    env_file: .env
    depends_on: [db, redis]
    restart: unless-stopped

  beat:
    build: .
    command: celery -A src.worker.app beat --loglevel=info
    env_file: .env
    depends_on: [redis]
    restart: unless-stopped

  api:
    build: .
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
    env_file: .env
    ports:
      - "8000:8000"
    depends_on: [db, redis]
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: transcribe_bot
      POSTGRES_USER: bot
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### 11.2 Dockerfile

```dockerfile
FROM python:3.12-slim

# Системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# yt-dlp отдельно (обновляется чаще)
RUN pip install --no-cache-dir yt-dlp

COPY . .

# Не запускать от root
RUN useradd -m -u 1000 appuser
USER appuser
```

### 11.3 GitHub Actions CI/CD

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
      redis:
        image: redis:7

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/unit/ -v --cov=src --cov-fail-under=80

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to VPS
        run: |
          ssh ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} '
            cd /app && git pull &&
            docker compose pull &&
            docker compose up -d --build &&
            docker compose exec -T bot alembic upgrade head
          '
```

### 11.4 Требования к серверу

| Параметр | Минимум (MVP) | Рекомендуется |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 ГБ | 8 ГБ |
| SSD | 40 ГБ | 80 ГБ |
| Сеть | 100 Мбит/с | 1 Гбит/с |
| ОС | Ubuntu 22.04 | Ubuntu 22.04 |

> Подходит: Yandex Cloud (yc1-4 за ~2500₽/мес), Timeweb Cloud, Selectel.

### 11.5 Nginx (reverse proxy)

```nginx
server {
    listen 443 ssl;
    server_name bot.yourdomain.ru;

    ssl_certificate /etc/letsencrypt/live/bot.yourdomain.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.yourdomain.ru/privkey.pem;

    location /webhooks/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## 12. Метрики и мониторинг

### 12.1 Celery Beat — фоновые задачи

```python
# Расписание
CELERY_BEAT_SCHEDULE = {
    "expire_subscriptions": {
        "task": "src.worker.tasks.maintenance.expire_subscriptions",
        "schedule": 3600,  # каждый час
    },
    "cleanup_tmp_files": {
        "task": "src.worker.tasks.maintenance.cleanup_tmp_files",
        "schedule": 1800,  # каждые 30 минут
    },
    "send_dlq_alert": {
        "task": "src.worker.tasks.maintenance.check_dead_letter_queue",
        "schedule": 300,  # каждые 5 минут
    },
    "daily_stats": {
        "task": "src.worker.tasks.stats.send_daily_report",
        "schedule": crontab(hour=9, minute=0),  # каждый день в 9:00
    },
}
```

### 12.2 Алерты администратору (Telegram)

```python
ALERT_EVENTS = [
    "worker_down",           # воркер упал
    "dlq_message_count > 5", # много мёртвых задач
    "groq_api_error_rate > 10%",
    "payment_webhook_failed",
    "db_connection_error",
]
```

### 12.3 Ежедневный отчёт боту-администратору

```
📊 Статистика за 05.03.2026

👤 Новых пользователей: 47
💰 Оплат: 12 на 8 731₽
🎙 Транскрибаций: 234 (общая длительность: 89 ч)
⚡ Среднее время обработки: 1 мин 43 сек
❌ Ошибок: 3 (1.3%)
📋 Конспектов создано: 98
🔗 Рефералов пришло: 8
```

### 12.4 Sentry

```python
import sentry_sdk
sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    environment=settings.ENV,  # "production" / "staging"
    traces_sample_rate=0.1,    # 10% трейсов
    profiles_sample_rate=0.1,
)
```

---

## 13. Структура проекта

```
transcribe-bot/
├── src/
│   ├── bot/
│   │   ├── main.py                  # точка входа бота
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── start.py             # /start, /help
│   │   │   ├── media.py             # аудио, видео, голосовые
│   │   │   ├── links.py             # ссылки на YouTube и т.д.
│   │   │   ├── profile.py           # /profile, /balance, /history
│   │   │   ├── payment.py           # /subscribe, /topup
│   │   │   ├── referral.py          # /referral
│   │   │   ├── promo.py             # /promo
│   │   │   ├── admin.py             # /admin
│   │   │   └── callbacks.py         # inline кнопки
│   │   ├── middlewares/
│   │   │   ├── database.py
│   │   │   ├── user.py
│   │   │   ├── ban.py
│   │   │   └── rate_limit.py
│   │   ├── keyboards/
│   │   │   ├── reply.py             # reply keyboards
│   │   │   └── inline.py            # inline keyboards
│   │   ├── texts/
│   │   │   └── ru.py                # все тексты
│   │   └── states.py                # FSM состояния
│   │
│   ├── api/
│   │   ├── main.py                  # FastAPI app
│   │   └── webhooks.py              # ЮKassa webhook
│   │
│   ├── worker/
│   │   ├── app.py                   # Celery app
│   │   └── tasks/
│   │       ├── transcription.py     # основная задача
│   │       ├── summary.py           # конспект
│   │       ├── maintenance.py       # очистка, экспирация
│   │       └── stats.py             # статистика
│   │
│   ├── services/
│   │   ├── transcription.py         # Groq Whisper интеграция
│   │   ├── summary.py               # Claude API интеграция
│   │   ├── audio_processor.py       # ffmpeg, нарезка
│   │   ├── downloader.py            # yt-dlp
│   │   ├── billing.py               # баланс, списание
│   │   ├── referral.py              # реф программа
│   │   ├── storage.py               # S3
│   │   └── notification.py          # отправка сообщений юзеру из воркера
│   │
│   ├── db/
│   │   ├── base.py                  # Base, engine, sessionmaker
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── subscription.py
│   │   │   ├── transaction.py
│   │   │   ├── transcription.py
│   │   │   ├── referral.py
│   │   │   └── promo_code.py
│   │   └── repositories/            # слой доступа к данным
│   │       ├── user.py
│   │       ├── transcription.py
│   │       └── transaction.py
│   │
│   ├── utils/
│   │   ├── validators.py
│   │   ├── formatters.py            # форматирование текста, времени, рублей
│   │   └── redis_lock.py            # распределённые локи
│   │
│   └── config.py                    # pydantic Settings
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
│
├── alembic/
│   ├── env.py
│   └── versions/
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```

---

## 14. Роадмап и фазы разработки

### Фаза 1 — MVP (2 недели)

**Цель:** рабочий бот, принимающий голосовые и аудиофайлы

- [ ] Структура проекта, Docker Compose, CI
- [ ] Модели БД + миграции Alembic
- [ ] Базовый бот: `/start`, `/help`, `/profile`
- [ ] Приём голосовых и аудиофайлов
- [ ] Celery worker + Groq транскрибация
- [ ] Отдача результата `.txt` файлом
- [ ] 3 бесплатные попытки
- [ ] Юнит-тесты на billing + validators (покрытие ≥ 60%)

### Фаза 2 — Монетизация (1 неделя)

**Цель:** первые платящие пользователи

- [ ] ЮKassa интеграция (подписки + разовые пополнения)
- [ ] Webhook обработка + idempotency
- [ ] Тарифная сетка в боте
- [ ] `/subscribe`, `/topup` сценарии
- [ ] Тесты webhook

### Фаза 3 — Контент-фичи (1 неделя)

**Цель:** повышение ценности продукта

- [ ] yt-dlp: YouTube, Rutube, Google Drive, Яндекс Диск
- [ ] Конспект через Claude API
- [ ] DOCX экспорт (python-docx)
- [ ] Реферальная программа
- [ ] Промокоды

### Фаза 4 — Качество и масштаб (1 неделя)

**Цель:** надёжность в продакшне

- [ ] Sentry интеграция
- [ ] Ежедневная статистика в admin чат
- [ ] Алерты по DLQ и ошибкам API
- [ ] Rate limiting + защита от злоупотреблений
- [ ] Покрытие тестами ≥ 80%
- [ ] Нагрузочное тестирование (locust)

### Фаза 5 — Рост (по мере необходимости)

- [ ] Деление на спикеров (диаризация через pyannote.audio)
- [ ] SRT субтитры с таймкодами
- [ ] Партнёрский кабинет (статистика рефералов расширенная)
- [ ] API для B2B клиентов (REST)
- [ ] Многоязычный интерфейс (EN/UK)

---

## Приложение: Расчёт экономики

### Себестоимость одной транскрибации (1 час аудио)

| Статья | Стоимость |
|---|---|
| Groq Whisper ($0.02/час) | ~1.8₽ |
| Claude конспект (~15k токенов) | ~5₽ |
| Хранение S3 (24ч, ~50 МБ) | ~0.01₽ |
| Вычисления VPS (amortized) | ~0.5₽ |
| **Итого** | **~7.3₽** |

### Точка безубыточности

| VPS | 2 500₽/мес |
|---|---|
| Sentry, прочие SaaS | 500₽/мес |
| **Фикс. расходы** | **3 000₽/мес** |

При среднем чеке подписки 649₽ → нужно **5 платящих пользователей** для покрытия фиксированных расходов.

При 100 пользователях на Базовом тарифе → **64 900₽ выручки** при переменных затратах ~7 300₽ (100 × 30 ч × 7.3₽/ч).

---

*Документ подготовлен для разработки сервиса транскрибации аудио/видео на базе Telegram-бота.*
