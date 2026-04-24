/**
 * Deno Deploy — прозрачный прокси Telegram webhook → наш backend.
 *
 * Зачем: Российские ISP периодически режут входящий трафик с IP-диапазонов
 * Telegram Bot API (149.154.160.0/20, 91.108.4.0/22). Обычные клиенты с
 * мобильного интернета при этом ходят на наш сайт без проблем — то есть
 * блок узкий, именно на Telegram-инфру. Deno Deploy выходит с IP
 * Google Cloud / AWS, эти диапазоны хостер не режет.
 *
 * Поток:
 *   Telegram ─POST─► <worker>.deno.net/webhooks/telegram
 *                    ─POST─► https://littera.site/webhooks/telegram
 *                             (всё тело + заголовки целиком, включая
 *                              X-Telegram-Bot-Api-Secret-Token, который
 *                              на нашей стороне проверяется FastAPI-хендлером)
 *
 * Деплой: создать новый Playground на https://deno.com/deploy → вставить этот
 * код → Save & Deploy → в .env на сервере:
 *   WEBHOOK_HOST=https://<worker>.deno.net
 * и перезапустить бот — он сам вызовет setWebhook на новый URL.
 *
 * Безопасность: прокси не читает и не логирует WEBHOOK_SECRET. Он идёт в
 * заголовке X-Telegram-Bot-Api-Secret-Token из Telegram насквозь. Попытка
 * кого-то постороннего стукнуть в Deno без правильного секрета получит 403
 * от нашего FastAPI.
 */
const ORIGIN = "https://littera.site";

Deno.serve(async (request) => {
    const url = new URL(request.url);

    // Диагностика — версионный эндпоинт для sanity-check при деплое.
    if (url.pathname === "/__version") {
        return new Response("tg-proxy-v1");
    }

    // Проксируем только Telegram webhook. Всё остальное — 404.
    if (url.pathname !== "/webhooks/telegram") {
        return new Response("Not Found", { status: 404 });
    }

    if (request.method !== "POST") {
        return new Response("Method Not Allowed", { status: 405 });
    }

    const upstream = ORIGIN + url.pathname + url.search;

    // new Request(url, oldRequest) — канонический Deno/CF паттерн. Наследует
    // метод, body (stream) и все заголовки от Telegram; мы только меняем URL.
    const forwarded = new Request(upstream, request);
    return fetch(forwarded);
});
