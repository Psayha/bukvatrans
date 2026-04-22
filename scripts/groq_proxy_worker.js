/**
 * Cloudflare Worker — прозрачный прокси на api.groq.com.
 *
 * Зачем: Groq блокирует по geoIP некоторые регионы (RU/CN и т.п.).
 *   Workers бесплатный тариф — 100k запросов/день, этого хватает для
 *   одного бота на транскрибации с запасом.
 *
 * Деплой:
 *   1. https://dash.cloudflare.com → Workers & Pages → Create → Hello World
 *   2. Замени код worker.js на этот файл
 *   3. Deploy → получишь URL вида https://<name>.<account>.workers.dev
 *   4. На сервере в .env положи:
 *        GROQ_API_BASE=https://<name>.<account>.workers.dev
 *   5. docker compose restart worker worker_summary
 *
 * Безопасность:
 *   Прокси НЕ логирует API-ключ (Groq-авторизация передаётся в заголовке
 *   Authorization и уходит вместе с запросом, Worker её не читает).
 *   Для параноидальной защиты можно поставить WORKER_SECRET проверку
 *   на стороне Worker'а (см. опциональный блок ниже).
 */

// Разрешаем запросы только на пути Groq API (экономит 100k-лимит Worker'а).
const ALLOWED_PATH_PREFIX = "/openai/";

export default {
    async fetch(request, env) {
        // --- опционально: защита от посторонних вызовов на твой Worker ---
        // const clientSecret = request.headers.get("X-Proxy-Secret");
        // if (clientSecret !== env.PROXY_SECRET) {
        //     return new Response("Forbidden", { status: 403 });
        // }

        const url = new URL(request.url);

        if (!url.pathname.startsWith(ALLOWED_PATH_PREFIX)) {
            return new Response("Not Found", { status: 404 });
        }

        const upstream = new URL(url.pathname + url.search, "https://api.groq.com");

        // Копируем запрос 1-в-1 — httpx со стороны бота прикрепит
        // Authorization: Bearer gsk_... , тело (multipart/form-data), нужные заголовки.
        const init = {
            method: request.method,
            headers: new Headers(request.headers),
            body: request.body,
        };
        init.headers.set("Host", "api.groq.com");
        // Cloudflare добавляет свои X-Forwarded-For / CF-* — Groq их принимает.

        const response = await fetch(upstream, init);

        // Отдаём назад как есть.
        return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers: response.headers,
        });
    },
};
