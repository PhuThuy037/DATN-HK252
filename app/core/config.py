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
    gemini_model: str = "gemini-2.5-flash"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.1-8b-instant"
    non_embedding_llm_provider: str = "groq"  # groq | gemini | ollama
    non_embedding_llm_timeout_seconds: float = 12.0
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    google_api_key: str | None = None
    groq_api_key: str | None = None
    chat_provider: str = "groq"  # groq | gemini | ollama
    default_system_prompt: str | None = "You are a helpful assistant."

    # CORS: comma-separated values; use * only when you do not need credentials.
    cors_allowed_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

