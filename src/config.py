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

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

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


settings = Settings()
