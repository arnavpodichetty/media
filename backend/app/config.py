from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit, parse_qsl

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, populated from environment variables / .env file."""

    database_url: str

    tmdb_api_key: str

    # Left blank/unused until later milestones (AniList needs no key).
    hardcover_api_token: str = ""
    rawg_api_key: str = ""
    lastfm_api_key: str = ""

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # --- LLM backend (taste-profile generation + recommendation reranking) ---
    # Any OpenAI-compatible chat-completions endpoint works: a local
    # llama.cpp/Ollama server, or a hosted API like Groq / DeepSeek /
    # OpenRouter. base_url must include the /v1 suffix.
    #   - llama-server (local): http://127.0.0.1:8080/v1  (api_key blank)
    #   - Groq:                 https://api.groq.com/openai/v1
    #   - DeepSeek:             https://api.deepseek.com/v1
    local_llm_base_url: str = "http://127.0.0.1:8080/v1"
    # Cosmetic for llama-server (serves whatever GGUF is loaded); for hosted
    # providers this must be a real model id (e.g. "llama-3.3-70b-versatile").
    local_llm_model: str = "local-model"
    # Bearer token for hosted providers. Leave blank for local servers.
    local_llm_api_key: str = ""
    # Minimum seconds between LLM calls in the seed script. 0 for a local
    # server (no limit); raise it if a hosted provider rate-limits you.
    llm_min_interval_seconds: float = 0.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def async_database_url(self) -> str:
        """Rewrite a standard postgres:// URL for SQLAlchemy's asyncpg driver."""
        parts = urlsplit(self.database_url)
        scheme = "postgresql+asyncpg"
        # asyncpg doesn't understand ?sslmode=require in the DSN itself;
        # we strip it here and pass ssl via connect_args instead (see db.py).
        query_pairs = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() != "sslmode"]
        new_query = "&".join(f"{k}={v}" for k, v in query_pairs)
        return urlunsplit((scheme, parts.netloc, parts.path, new_query, ""))

    @property
    def requires_ssl(self) -> bool:
        return "sslmode=require" in self.database_url or "neon.tech" in self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
