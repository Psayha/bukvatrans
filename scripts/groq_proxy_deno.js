/**
 * Deno Deploy — прозрачный прокси на api.groq.com.
 *
 * Зачем: Groq блокирует по geoIP некоторые регионы (RU/CN и т.п.).
 * Deno Deploy выходит с IP Google Cloud / AWS, которые Groq пропускает.
 *
 * Деплой:
 *   1. https://deno.com/deploy → New Playground → вставить этот код → Save & Deploy.
 *   2. В .env на сервере:
 *        GROQ_API_BASE=https://<project>.<account>.deno.net
 *   3. docker compose up -d --force-recreate worker worker_summary
 *
 * Реализация: new Request(url, oldRequest) — канонический Deno/CF паттерн.
 * Наследует ВСЁ от входящего запроса (метод, headers включая Authorization,
 * body со всеми multipart boundary). Переписываем только hostname.
 */
Deno.serve(async (request) => {
    const url = new URL(request.url);

    // Диагностика — sanity-check после деплоя.
    if (url.pathname === "/__version") {
        return new Response("groq-proxy-v1");
    }

    // Пропускаем только пути Groq API. Всё остальное — 404.
    if (!url.pathname.startsWith("/openai/")) {
        return new Response("Not Found", { status: 404 });
    }

    url.hostname = "api.groq.com";
    url.port = "";
    url.protocol = "https:";

    const forwarded = new Request(url.toString(), request);
    return fetch(forwarded);
});
