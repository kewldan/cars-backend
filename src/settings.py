from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB: str = "georgiancars"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    JWT_SECRET: str | None = None
    DEBUG: bool = True
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    TG_API_ID: int = 0
    TG_API_HASH: str = ""
    TG_SESSION_NAME: str = "georgiancars"
    TG_SESSION_DIR: str = "data/sessions"

    QWEN_BASE_URL: str = "http://localhost:11434/v1"
    QWEN_MODEL: str = "qwen2.5:7b"
    QWEN_TIMEOUT: int = 600
    QWEN_THINKING: bool = False


settings = Settings()
