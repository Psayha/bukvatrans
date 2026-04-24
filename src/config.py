from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Bot
    BOT_TOKEN: str = ""
    WEBHOOK_HOST: str = ""
    WEBHOOK_SECRET: str = ""

    # External APIs
    GROQ_API_KEY: str = ""
    # Override if api.groq.com is geo-blocked from the server; point this at
    # a Cloudflare Worker (or similar HTTPS proxy) that forwards to the
    # real host. Must NOT end with a slash.
    GROQ_API_BASE: str = "https://api.groq.com"

    # Summarization via OpenRouter (OpenAI-compatible gateway that covers
    # Claude / GPT / Gemini / Llama behind one key). Override the model
    # without touching code; same client works for every provider.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "anthropic/claude-3.5-haiku"

    # Payment
    YUKASSA_SHOP_ID: str = ""
    YUKASSA_SECRET_KEY: str = ""

    # Database — SQLite default is strictly for local unit tests. The
    # validator below refuses to start in ENV=production with a SQLite
    # URL, so forgetting to set DATABASE_URL on the server fails loud
    # instead of silently writing to an ephemeral file.
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"

    # Redis / Celery (broker DB0, cache DB1, FSM DB2, rate_limit DB3)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_DB: int = 1
    REDIS_FSM_DB: int = 2
    REDIS_RATELIMIT_DB: int = 3

    # DB pool
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    # CORS
    CORS_ALLOWED_ORIGINS: str = ""

    # Limits
    MAX_URL_DURATION_SECONDS: int = 4 * 3600
    MAX_URL_FILESIZE_BYTES: int = 2 * 1024 * 1024 * 1024
    CELERY_SOFT_TIME_LIMIT: int = 1800
    CELERY_TIME_LIMIT: int = 2100

    # Retention (days to keep transcription text before purging).
    TRANSCRIPTION_RETENTION_DAYS: int = 3

    # Admin 2FA
    ADMIN_APPROVAL_TTL_SECONDS: int = 300

    # Legal boilerplate (used in /privacy and /terms responses).
    COMPANY_NAME: str = "{COMPANY_NAME}"
    COMPANY_INN: str = "{COMPANY_INN}"
    COMPANY_OGRN: str = "{COMPANY_OGRN}"
    COMPANY_ADDRESS: str = "{COMPANY_ADDRESS}"
    SUPPORT_EMAIL: str = "{SUPPORT_EMAIL}"
    # Telegram handle (without @) of the live-support account.
    SUPPORT_HANDLE: str = "bukvitsa_support"
    PRIVACY_POLICY_URL: str = ""
    TERMS_URL: str = ""

    # 54-ФЗ receipts — VAT code per FNS: 1=no VAT, 2=0%, 6=VAT 20%.
    YUKASSA_VAT_CODE: int = 1

    # S3
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = ""

    # Admin
    ADMIN_IDS: str = ""

    # Monitoring
    ENV: str = "development"
    SENTRY_DSN: str = ""

    @property
    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(i.strip()) for i in self.ADMIN_IDS.split(",") if i.strip()]

    @property
    def cors_allowed_origins_list(self) -> List[str]:
        if not self.CORS_ALLOWED_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    def _redis_url_with_db(self, db: int) -> str:
        """Return REDIS_URL with the DB suffix replaced."""
        base = self.REDIS_URL.rstrip("/")
        if "/" in base.split("//", 1)[-1]:
            base = base.rsplit("/", 1)[0]
        return f"{base}/{db}"

    @property
    def redis_cache_url(self) -> str:
        return self._redis_url_with_db(self.REDIS_CACHE_DB)

    @property
    def redis_fsm_url(self) -> str:
        return self._redis_url_with_db(self.REDIS_FSM_DB)

    @property
    def redis_ratelimit_url(self) -> str:
        return self._redis_url_with_db(self.REDIS_RATELIMIT_DB)


def _validate_production(s: "Settings") -> None:
    """Fail loud on obvious misconfiguration in production.

    Forgetting to set DATABASE_URL on the server would silently fall back to
    the SQLite default and write to an ephemeral file inside the container —
    all user data disappears on redeploy. Better to crash at import time.
    """
    if s.ENV != "production":
        return
    problems: list[str] = []
    if s.DATABASE_URL.startswith("sqlite"):
        problems.append("DATABASE_URL is SQLite — set a Postgres URL for production.")
    if not s.BOT_TOKEN:
        problems.append("BOT_TOKEN is empty.")
    if s.WEBHOOK_HOST and not s.WEBHOOK_SECRET:
        problems.append("WEBHOOK_HOST is set but WEBHOOK_SECRET is empty.")
    if problems:
        raise RuntimeError(
            "Production config invalid:\n  - " + "\n  - ".join(problems)
        )


settings = Settings()
_validate_production(settings)
