from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Question Paper Generator API"
    app_env: str = "development"
    database_url: str = "sqlite:///./qpgen.db"
    jwt_secret_key: str = "change-this-in-production-please-use-32-plus-chars"
    access_token_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 60 * 24 * 3
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    ollama_vision_model: str = "mistral"
    ollama_request_timeout_seconds: float = 180.0
    ollama_generation_timeout_seconds: float = 240.0
    ollama_health_timeout_seconds: float = 3.0
    prewarm_embeddings_on_startup: bool = False
    academic_sync_processing_limit_bytes: int = 2 * 1024 * 1024
    storage_root: str = "./storage"
    allow_demo_seed: bool = True

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_root).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
