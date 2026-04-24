FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir -U yt-dlp

COPY . .
RUN chmod +x /app/scripts/entrypoint.sh

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# No image-wide HEALTHCHECK: this same image runs as api / bot / celery
# worker / beat, and each role exposes a different liveness surface. Each
# service declares its own healthcheck in docker-compose.yml.

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
