from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app config, populated from environment variables / .env.

    embedding_provider/llm_provider select which app/llm implementation the
    factory functions in app/llm/factory.py return - see that module for
    what each value means.
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

    # Provider selection - "local" costs nothing and needs no key. "openai"/
    # "gemini" require the matching *_api_key below and will make billed API
    # calls once selected - never flip these without meaning to.
    embedding_provider: str = "local"
    llm_provider: str = "local"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    # Clustering (Section 7 stage 3). Both are starting points, not
    # validated thresholds - this build environment can't download the
    # embedding model to tune them against real data (see README Phase 2
    # section), so expect to adjust similarity_threshold after looking at
    # real clustering output.
    clustering_time_window_hours: int = 48
    clustering_similarity_threshold: float = 0.55


settings = Settings()
