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
