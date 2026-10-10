"""
Application settings using Pydantic Settings.
Loads configuration from environment variables.
"""
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "Secretary - Member Management"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")

    # Database (PostgreSQL)
    database_host: str = Field(default="localhost", env="DATABASE_HOST")
    database_port: int = Field(default=5432, env="DATABASE_PORT")
    database_user: str = Field(default="postgres", env="DATABASE_USER")
    database_password: str = Field(default="postgres", env="DATABASE_PASSWORD")
    database_name: str = Field(default="secretary", env="DATABASE_NAME")
    database_pool_size: int = Field(default=20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, env="DATABASE_MAX_OVERFLOW")
    database_sslmode: str = Field(default="disable", env="DATABASE_SSLMODE")

    @property
    def database_url(self) -> str:
        """Construct async PostgreSQL connection URL."""
        return (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def database_connect_args(self) -> dict:
        """Extra connect_args for asyncpg (e.g. SSL mode).

        asyncpg 0.29 + OpenSSL 3.x can raise OSError([Errno 22])
        during SSL cert chain loading in forked Celery workers.
        Using ``ssl=False`` (boolean) completely skips SSL code paths,
        whereas the string ``"disable"`` still probes the server.
        """
        if self.database_sslmode == "disable":
            return {"ssl": False}
        return {"ssl": self.database_sslmode}

    # Redis
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Milvus (Vector Database)
    milvus_host: str = Field(default="localhost", env="MILVUS_HOST")
    milvus_port: int = Field(default=19530, env="MILVUS_PORT")

    # Neo4j (Graph Database, Optional)
    neo4j_uri: Optional[str] = Field(default=None, env="NEO4J_URI")
    neo4j_user: Optional[str] = Field(default=None, env="NEO4J_USER")
    neo4j_password: Optional[str] = Field(default=None, env="NEO4J_PASSWORD")

    # LLM Providers
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_api_base: Optional[str] = Field(default=None, env="OPENAI_API_BASE")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    anthropic_base_url: Optional[str] = Field(default=None, env="ANTHROPIC_BASE_URL")
    anthropic_model: str = Field(default="claude-sonnet-4-20250514", env="ANTHROPIC_MODEL")
    llm_provider: str = Field(default="openai", env="LLM_PROVIDER")  # openai or anthropic
    llm_model: str = Field(default="gpt-4", env="LLM_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")

    # Curation LLM Token Limits
    curation_dedup_max_tokens: int = Field(default=65536, env="CURATION_DEDUP_MAX_TOKENS")
    curation_association_max_tokens: int = Field(default=8000, env="CURATION_ASSOCIATION_MAX_TOKENS")
    curation_association_top_k: int = Field(default=8, env="CURATION_ASSOCIATION_TOP_K")
    curation_association_min_confidence: float = Field(
        default=0.5,
        env="CURATION_ASSOCIATION_MIN_CONFIDENCE",
    )
    curation_association_min_title_chars: int = Field(
        default=3,
        env="CURATION_ASSOCIATION_MIN_TITLE_CHARS",
    )
    curation_association_min_reason_chars: int = Field(
        default=8,
        env="CURATION_ASSOCIATION_MIN_REASON_CHARS",
    )
    curation_low_information_association_limit: int = Field(
        default=1,
        env="CURATION_LOW_INFORMATION_ASSOCIATION_LIMIT",
    )
    curation_low_importance_event_types: List[str] = Field(
        default=["holiday_solar_term", "solar_term"],
        env="CURATION_LOW_IMPORTANCE_EVENT_TYPES",
    )
    curation_conflict_window_days: int = Field(
        default=7,
        env="CURATION_CONFLICT_WINDOW_DAYS",
    )
    curation_auto_resolve_buffer_days: int = Field(
        default=1,
        env="CURATION_AUTO_RESOLVE_BUFFER_DAYS",
    )
    curation_max_auto_resolve_offset_days: int = Field(
        default=90,
        env="CURATION_MAX_AUTO_RESOLVE_OFFSET_DAYS",
    )
    curation_weekend_trip_keywords: List[str] = Field(
        default=["周末"],
        env="CURATION_WEEKEND_TRIP_KEYWORDS",
    )
    curation_stale_contact_days: int = Field(default=90, env="CURATION_STALE_CONTACT_DAYS")
    curation_stale_contact_min_importance: int = Field(
        default=5,
        env="CURATION_STALE_CONTACT_MIN_IMPORTANCE",
    )

    # Native Thinking (DashScope Anthropic-compatible API)
    thinking_enabled: bool = Field(default=True, env="THINKING_ENABLED")
    thinking_budget_tokens: int = Field(default=4096, env="THINKING_BUDGET_TOKENS")

    # Claude Agent SDK Settings
    # Note: claude_model is deprecated, use anthropic_model instead
    claude_model: str = Field(default="", env="CLAUDE_MODEL")

    @property
    def effective_anthropic_model(self) -> str:
        """Get the effective Anthropic model (CLAUDE_MODEL overrides anthropic_model)."""
        return self.claude_model or self.anthropic_model
    claude_agent_max_turns: int = Field(default=20, env="CLAUDE_AGENT_MAX_TURNS")
    # Claude Agent SDK extended thinking (disables StreamEvent partials when enabled)
    claude_agent_thinking_enabled: bool = Field(
        default=False,
        env="CLAUDE_AGENT_THINKING_ENABLED",
    )
    claude_agent_enabled: bool = Field(default=False, env="CLAUDE_AGENT_ENABLED")
    # SDK idle timeout in seconds; set to 0 to disable idle timeout.
    agent_idle_timeout_seconds: int = Field(default=0, env="AGENT_IDLE_TIMEOUT_SECONDS")
    # Feature flag to switch between old and new conversation service

    # Insight LLM Content Generation Feature Flags
    enable_llm_relationship_reminders: bool = Field(default=True, env="ENABLE_LLM_RELATIONSHIP_REMINDERS")

    # FeedbackBus emission toggle — disable to stop all real-time feedback
    # signal distribution without a code deploy (PLAN-001 rollback safety).
    feedback_bus_emission_enabled: bool = Field(default=True, env="FEEDBACK_BUS_EMISSION_ENABLED")

    # Bi-modal Routing Settings (New Architecture)
    bimodal_routing_enabled: bool = Field(default=False, env="BIMODAL_ROUTING_ENABLED")
    bimodal_routing_percentage: int = Field(default=0, env="BIMODAL_ROUTING_PERCENTAGE")
    intent_router_model: str = Field(default="claude-haiku-4-5-20251001", env="INTENT_ROUTER_MODEL")
    fast_worker_model: str = Field(default="claude-haiku-4-5-20251001", env="FAST_WORKER_MODEL")
    intent_router_fast_threshold: float = Field(default=0.9, env="INTENT_ROUTER_FAST_THRESHOLD")
    intent_router_hybrid_cooldown_hours: int = Field(default=4, env="INTENT_ROUTER_HYBRID_COOLDOWN")
    fast_agentic_enabled: bool = Field(default=True, env="FAST_AGENTIC_ENABLED")
    fast_agentic_max_turns: int = Field(default=3, env="FAST_AGENTIC_MAX_TURNS")
    fast_agentic_max_tool_calls: int = Field(default=2, env="FAST_AGENTIC_MAX_TOOL_CALLS")
    fast_agentic_tool_timeout_seconds: int = Field(default=8, env="FAST_AGENTIC_TOOL_TIMEOUT_SECONDS")
    # Weather calls may need extra headroom due to geocoding + provider fallback.
    fast_weather_tool_timeout_seconds: int = Field(default=20, env="FAST_WEATHER_TOOL_TIMEOUT_SECONDS")

    # Tool Gateway Settings
    tool_provider_type: str = Field(default="simulation", env="TOOL_PROVIDER_TYPE") # simulation or real

    # Agent Worker Settings
    run_agent_worker_in_process: bool = Field(default=False, env="RUN_AGENT_WORKER_IN_PROCESS")
    session_affinity_ttl_seconds: int = Field(default=1800, env="SESSION_AFFINITY_TTL_SECONDS")
    worker_heartbeat_ttl_seconds: int = Field(default=30, env="WORKER_HEARTBEAT_TTL_SECONDS")
    worker_heartbeat_interval_seconds: int = Field(default=10, env="WORKER_HEARTBEAT_INTERVAL_SECONDS")
    worker_max_concurrent_tasks: int = Field(default=3, env="WORKER_MAX_CONCURRENT_TASKS")
    worker_task_timeout_seconds: int = Field(default=300, env="WORKER_TASK_TIMEOUT_SECONDS")
    session_mailbox_enabled: bool = Field(default=True, env="SESSION_MAILBOX_ENABLED")
    session_mailbox_idle_seconds: int = Field(default=120, env="SESSION_MAILBOX_IDLE_SECONDS")
    session_mailbox_max_queue_size: int = Field(default=0, env="SESSION_MAILBOX_MAX_QUEUE_SIZE")
    agentic_tool_timeout_seconds: int = Field(default=30, env="AGENTIC_TOOL_TIMEOUT_SECONDS")
    # Stale message claim timeout (ms). Messages pending longer than this can be
    # claimed by another worker.  Should be slightly larger than heartbeat_ttl
    # (30s) to avoid prematurely stealing in-flight tasks.
    # Total recovery: 30s heartbeat TTL + 35s claim = ~65s (down from ~2min).
    claim_timeout_ms: int = Field(default=35000, env="CLAIM_TIMEOUT_MS")
    # Maximum number of times a message can be delivered before being sent to
    # the dead-letter queue.  Prevents poison messages from looping forever.
    max_delivery_count: int = Field(default=3, env="MAX_DELIVERY_COUNT")

    # SDK Client Pool Settings (CLI process reuse)
    sdk_client_pool_enabled: bool = Field(default=True, env="SDK_CLIENT_POOL_ENABLED")
    sdk_client_pool_idle_timeout_seconds: int = Field(default=1800, env="SDK_CLIENT_POOL_IDLE_TIMEOUT_SECONDS")
    sdk_client_pool_max_clients: int = Field(default=50, env="SDK_CLIENT_POOL_MAX_CLIENTS")
    # Enable per-session streaming-input actor for pooled slow/hybrid execution.
    sdk_streaming_input_enabled: bool = Field(default=True, env="SDK_STREAMING_INPUT_ENABLED")
    sdk_streaming_input_idle_seconds: int = Field(default=120, env="SDK_STREAMING_INPUT_IDLE_SECONDS")
    # Safety-net timeout for streaming-input tasks (slow/hybrid).  These
    # tasks disable the normal worker_task_timeout_seconds to allow long
    # multi-turn conversations, but we still want an upper bound to prevent
    # indefinitely stuck workers.
    streaming_input_max_timeout_seconds: int = Field(default=600, env="STREAMING_INPUT_MAX_TIMEOUT_SECONDS")

    # Encryption
    encryption_master_key: str = Field(
        default="CHANGE_THIS_IN_PRODUCTION_32_CHARS",
        env="ENCRYPTION_MASTER_KEY"
    )

    # JWT Authentication
    jwt_secret: str = Field(default="CHANGE_THIS_IN_PRODUCTION", env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiration_minutes: int = Field(default=1440, env="JWT_EXPIRATION_MINUTES")  # 24 hours

    # Authentication Mode
    # SECURITY: Defaults to True for production safety - set to False only for development
    strict_auth_enabled: bool = Field(default=True, env="STRICT_AUTH_ENABLED")

    # CORS (mobile-app-first; no bundled web frontend)
    cors_origins: List[str] = Field(
        default=[],
        env="CORS_ORIGINS"
    )

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")

    # Tool Gateway Internal Token
    tool_gateway_internal_secret: str = Field(
        default="CHANGE_THIS_IN_PRODUCTION",
        env="TOOL_GATEWAY_INTERNAL_SECRET",
    )

    # Rate Limiting - Per-tier limits (requests_per_minute, requests_per_hour, burst_allowance)
    rate_limit_per_minute: int = Field(default=100, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_minute_unauthenticated: int = Field(default=10, env="RATE_LIMIT_PER_MINUTE_UNAUTH")
    rate_limit_unauth_per_hour: int = Field(default=100, env="RATE_LIMIT_UNAUTH_PER_HOUR")
    rate_limit_unauth_burst: int = Field(default=3, env="RATE_LIMIT_UNAUTH_BURST")
    rate_limit_free_per_minute: int = Field(default=60, env="RATE_LIMIT_FREE_PER_MINUTE")
    rate_limit_free_per_hour: int = Field(default=1000, env="RATE_LIMIT_FREE_PER_HOUR")
    rate_limit_free_burst: int = Field(default=10, env="RATE_LIMIT_FREE_BURST")
    rate_limit_basic_per_minute: int = Field(default=120, env="RATE_LIMIT_BASIC_PER_MINUTE")
    rate_limit_basic_per_hour: int = Field(default=3000, env="RATE_LIMIT_BASIC_PER_HOUR")
    rate_limit_basic_burst: int = Field(default=20, env="RATE_LIMIT_BASIC_BURST")
    rate_limit_premium_per_minute: int = Field(default=300, env="RATE_LIMIT_PREMIUM_PER_MINUTE")
    rate_limit_premium_per_hour: int = Field(default=10000, env="RATE_LIMIT_PREMIUM_PER_HOUR")
    rate_limit_premium_burst: int = Field(default=50, env="RATE_LIMIT_PREMIUM_BURST")

    # Spending Limits - Per-transaction (¥)
    spending_limit_free: float = Field(default=0.0, env="SPENDING_LIMIT_FREE")
    spending_limit_basic: float = Field(default=1000.0, env="SPENDING_LIMIT_BASIC")
    spending_limit_premium: float = Field(default=10000.0, env="SPENDING_LIMIT_PREMIUM")
    spending_limit_enterprise: float = Field(default=0.0, env="SPENDING_LIMIT_ENTERPRISE")  # 0 = unlimited

    # Spending Limits - Daily (¥)
    daily_spending_limit_free: float = Field(default=0.0, env="DAILY_SPENDING_LIMIT_FREE")
    daily_spending_limit_basic: float = Field(default=5000.0, env="DAILY_SPENDING_LIMIT_BASIC")
    daily_spending_limit_premium: float = Field(default=50000.0, env="DAILY_SPENDING_LIMIT_PREMIUM")
    daily_spending_limit_enterprise: float = Field(default=0.0, env="DAILY_SPENDING_LIMIT_ENTERPRISE")  # 0 = unlimited

    # Confirmation threshold (¥) - amounts above this require user confirmation
    confirmation_amount_threshold: float = Field(default=100.0, env="CONFIRMATION_AMOUNT_THRESHOLD")

    # Action-specific max amounts (¥)
    purchase_max_amount: float = Field(default=1000.0, env="PURCHASE_MAX_AMOUNT")
    transfer_max_amount: float = Field(default=5000.0, env="TRANSFER_MAX_AMOUNT")

    # Firebase Cloud Messaging (Push Notifications)
    firebase_service_account_path: Optional[str] = Field(
        default=None, env="FIREBASE_SERVICE_ACCOUNT_PATH"
    )
    fcm_enabled: bool = Field(default=False, env="FCM_ENABLED")

    # ASR (Automatic Speech Recognition)
    asr_provider: str = Field(default="whisper", env="ASR_PROVIDER")  # whisper or dashscope
    asr_model: str = Field(default="", env="ASR_MODEL")  # empty = provider default
    asr_max_audio_size_mb: int = Field(default=10, env="ASR_MAX_AUDIO_SIZE_MB")
    asr_default_language: str = Field(default="", env="ASR_DEFAULT_LANGUAGE")  # empty = auto-detect

    # DashScope (Alibaba Cloud)
    dashscope_api_key: str = Field(default="", env="DASHSCOPE_API_KEY")

    # Voice Streaming (real-time ASR via Dashscope WebSocket)
    # Defaults to False — requires DASHSCOPE_API_KEY to be set (M-7).
    voice_streaming_enabled: bool = Field(default=False, env="VOICE_STREAMING_ENABLED")
    voice_streaming_model: str = Field(
        default="paraformer-realtime-v2",
        env="VOICE_STREAMING_MODEL",
    )

    # Celery
    celery_broker_url: Optional[str] = Field(default=None, env="CELERY_BROKER_URL")
    celery_result_backend: Optional[str] = Field(default=None, env="CELERY_RESULT_BACKEND")

    # MCP (Model Context Protocol) Settings
    mcp_enabled: bool = Field(default=True, env="MCP_ENABLED")
    # Master switch for MCP functionality

    # MCP security: allowed base commands (first part of command)
    mcp_allowed_commands: List[str] = Field(
        default=["npx", "node", "python", "python3"],
        env="MCP_ALLOWED_COMMANDS"
    )

    # NotebookLM MCP Server (deprecated, use generic_mcp instead)
    notebooklm_mcp_enabled: bool = Field(default=False, env="NOTEBOOKLM_MCP_ENABLED")
    notebooklm_mcp_profile: str = Field(default="minimal", env="NOTEBOOKLM_MCP_PROFILE")
    notebooklm_mcp_command: Optional[str] = Field(default=None, env="NOTEBOOKLM_MCP_COMMAND")

    # Filesystem MCP Server
    filesystem_mcp_enabled: bool = Field(default=False, env="FILESYSTEM_MCP_ENABLED")
    filesystem_mcp_allowed_dirs: List[str] = Field(
        default=["/tmp/secretary"],
        env="FILESYSTEM_MCP_ALLOWED_DIRS"
    )

    # Fetch MCP Server (web content fetching)
    fetch_mcp_enabled: bool = Field(default=True, env="FETCH_MCP_ENABLED")

    # Memory MCP Server (persistent AI memory)
    memory_mcp_enabled: bool = Field(default=False, env="MEMORY_MCP_ENABLED")

    # Web Search Settings (for real-time information retrieval)
    tavily_api_key: Optional[str] = Field(default=None, env="TAVILY_API_KEY")
    serper_api_key: Optional[str] = Field(default=None, env="SERPER_API_KEY")
    # At least one search API should be configured for accurate restaurant recommendations

    # Data Connection Settings (OAuth configuration for external services)
    app_url: str = Field(default="secretary://", env="APP_URL")
    # Default redirect URI for OAuth callbacks

    # Google OAuth (Calendar, Gmail)
    google_client_id: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        default="secretary://oauth/callback/google",
        env="GOOGLE_REDIRECT_URI"
    )

    # Microsoft OAuth (Outlook Calendar, Outlook Mail)
    microsoft_client_id: Optional[str] = Field(default=None, env="MICROSOFT_CLIENT_ID")
    microsoft_client_secret: Optional[str] = Field(default=None, env="MICROSOFT_CLIENT_SECRET")
    microsoft_redirect_uri: str = Field(
        default="secretary://oauth/callback/microsoft",
        env="MICROSOFT_REDIRECT_URI"
    )
    microsoft_tenant_id: str = Field(default="common", env="MICROSOFT_TENANT_ID")

    @property
    def celery_broker(self) -> str:
        """Get Celery broker URL (defaults to Redis)."""
        return self.celery_broker_url or self.redis_url

    @property
    def celery_backend(self) -> str:
        """Get Celery result backend URL (defaults to Redis)."""
        return self.celery_result_backend or self.redis_url

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        """Refuse to start in production with sentinel secret values."""
        if self.environment == "production":
            sentinel_fields = {
                "jwt_secret": self.jwt_secret,
                "encryption_master_key": self.encryption_master_key,
                "tool_gateway_internal_secret": self.tool_gateway_internal_secret,
            }
            for field_name, value in sentinel_fields.items():
                if "CHANGE_THIS" in value:
                    raise ValueError(
                        f"{field_name} must be configured in production "
                        f"(current value contains 'CHANGE_THIS')"
                    )
        return self


# Global settings instance
settings = Settings()
