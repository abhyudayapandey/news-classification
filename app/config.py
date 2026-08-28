from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app config, populated from environment variables / .env.

    Phase 2 fields (embedding_provider, llm_provider, and the provider API
    keys/models) are read here but not consumed by any code yet - they exist
    so the config surface is stable across phases. See app/llm/base.py for
    the interface that will read them.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str

    @field_validator("database_url")
    @classmethod
    def _normalize_driver(cls, v: str) -> str:
        """Neon/Supabase dashboards hand out plain postgresql:// (or
        postgres://) connection strings with no driver suffix, which makes
        SQLAlchemy default to psycopg2 - not installed here, since this
        project standardized on psycopg3. Normalize both to +psycopg so a
        pasted-as-is connection string just works.
        """
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    app_env: str = "development"
    log_level: str = "INFO"

    # Phase 2 - not used in Phase 1
    embedding_provider: str = "local"
    llm_provider: str = "local"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"


settings = Settings()
