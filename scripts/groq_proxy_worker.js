/**
 * Cloudflare Worker — прозрачный прокси на api.groq.com.
 *
 * Зачем: Groq блокирует по geoIP некоторые регионы (RU/CN и т.п.).
 *   Workers бесплатный тариф — 100k запросов/день, хватает с запасом.
 *
 * Деплой:
 *   1. https://dash.cloudflare.com → Workers & Pages → Create → Hello World
 *   2. Замени код worker.js на этот файл, нажми Deploy
 *   3. На сервере в .env:
 *        GROQ_API_BASE=https://<name>.<account>.workers.dev
 *   4. docker compose up -d --force-recreate worker worker_summary
 *
 * Реализация: через `new Request(url, request)` — канонический паттерн
 * Cloudflare для прокси. Наследует ВСЁ от входящего запроса (метод,
 * headers включая Authorization, body со всеми multipart boundary).
 * Только hostname переписывается.
 *
 * Ранее был более сложный вариант с ручным копированием headers, но
 * он молча терял Authorization при multipart/form-data POST'ах — Groq
 * отдавал 401 Invalid API Key на пустой auth.
 */
export default {
    async fetch(request) {
        const url = new URL(request.url);
        if (!url.pathname.startsWith("/openai/")) {
            return new Response("Not Found", { status: 404 });
        }
        url.hostname = "api.groq.com";
        url.port = "";
        return fetch(new Request(url.toString(), request));
    },
};
