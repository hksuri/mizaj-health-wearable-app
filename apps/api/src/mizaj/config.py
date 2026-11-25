from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://localhost:3000"
    data_dir: Path = Path("data")
    duckdb_path: Path = Path("data/health.duckdb")
    sqlite_url: str = "sqlite:///data/mizaj.sqlite"
    anthropic_api_key: str | None = None
    app_model: str = "claude-haiku-5-5"
    judge_model: str = "claude-sonnet-5-5"
    log_level: str = "INFO"


settings = Settings()
