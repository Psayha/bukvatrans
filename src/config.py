from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Bot
    BOT_TOKEN: str = ""
    WEBHOOK_HOST: str = ""
    WEBHOOK_SECRET: str = ""

    # External APIs
    GROQ_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""

    # Payment
    YUKASSA_SHOP_ID: str = ""
    YUKASSA_SECRET_KEY: str = ""

    # Database
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


settings = Settings()
