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
    # Multilingual (~50 languages, includes Hindi) as of the swap from
    # all-MiniLM-L6-v2 - see app/llm/local_embedding.py's docstring for
    # why, the memory-footprint tradeoff this made, and its unverified
    # status in this build environment.
    local_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
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

    # Phase 3: admin session auth. No default on purpose - signing session
    # cookies with a hardcoded/well-known key would let anyone forge a
    # logged-in session, so this must be set explicitly (a long random
    # string) rather than silently falling back to something insecure.
    # Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
    secret_key: str
    # Section 5's staleness SLA - configurable in case it needs adjusting
    # without a code change; still no auto-escalation on breach (Section 11,
    # deferred), just the visual "overdue" flag in the admin queue.
    review_sla_hours: int = 48

    # Section 13 social listening. YouTube Data API is free-tier and
    # always available (no cost gating) once a key is set - unset simply
    # means "skip YouTube fetching," same fail-open-by-omission posture as
    # OPENAI_API_KEY. X is the platform's first genuinely metered-cost
    # feature: the official pay-per-use API, never a third-party reseller
    # or self-scraping - real dollars per post read, gated per-entity on
    # live client access (app/social/pipeline.py), never a global switch.
    youtube_api_key: str | None = None
    x_api_bearer_token: str | None = None
    # Real X API pricing as of this platform's own research at build time -
    # verify against X's current developer pricing page before trusting
    # this for an actual contracted ceiling; it's a config value specifically
    # so a price change is a .env edit, not a code change.
    x_cost_per_post_usd: float = 0.005
    # Capped per entity per fetch call, same reasoning as CLUSTERING_TIME_
    # WINDOW_HOURS and /process/run's limit - bounds one call's cost and
    # runtime rather than pulling an entity's entire available history at
    # once.
    social_fetch_max_results_per_entity: int = 10
    # Fraction of a client's x_spend_ceiling_usd at which the super-admin
    # cost screen flags "approaching" rather than "ok" - a starting point,
    # not a validated figure (no real client contracts exist yet to tune
    # it against), same caveat as the clustering similarity threshold.
    social_ceiling_warn_ratio: float = 0.8


settings = Settings()
