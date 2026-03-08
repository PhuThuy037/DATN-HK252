from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str | None = None
    policy_ingest_queue_name: str = "policy_ingest_jobs"
    rule_duplicate_top_k: int = 5
    rule_duplicate_exact_threshold: float = 0.92
    rule_duplicate_near_threshold: float = 0.82
    rule_duplicate_embed_model: str = "local-hash-1536-v1"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    gemini_model: str = "gemini-3.1-flash-lite-preview"
    non_embedding_llm_provider: str = "gemini"  # gemini | ollama
    non_embedding_llm_timeout_seconds: float = 12.0
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    google_api_key: str | None = None
    chat_provider: str = "gemini"  # gemini | ollama
    default_system_prompt: str | None = "You are a helpful assistant."

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
