import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # E2E Testing Mode - enables test utility endpoints
    e2e_mode: bool = False

    # Authentication
    auth_disabled: bool = False  # Set to True to disable all auth (local dev)
    auth_key: str = ""  # Deprecated, kept for backward compatibility

    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None

    # Access control
    # Public access: when True, all authenticated users can submit (with rate limits)
    # Allowlisted users still bypass rate limits
    public_access: bool = False

    # Email allowlist (comma-separated) - used for rate limit bypass when public_access=True
    # When public_access=False, only allowlisted users get full access
    allowed_emails: Optional[str] = None  # e.g., "user1@gmail.com,user2@gmail.com"

    # Admin emails (comma-separated) - users with access to admin panel
    admin_emails: Optional[str] = None  # e.g., "admin1@gmail.com,admin2@gmail.com"

    # Option 2: Google Groups API (requires Workspace Admin + Domain-Wide Delegation)
    google_group_email: str = "omj-validator-alpha@googlegroups.com"
    google_service_account_json: Optional[str] = None  # JSON string or file path

    # Session - MUST be set explicitly in production for multi-worker consistency
    session_secret_key: Optional[str] = None

    # Frontend URL for OAuth redirects (only needed if frontend/backend on different domains)
    # Not required for co-hosted deployment behind Nginx
    frontend_url: Optional[str] = None

    @model_validator(mode="after")
    def validate_session_secret(self):
        """Ensure session_secret_key is set in production (when auth is enabled)."""
        if not self.auth_disabled and not self.session_secret_key:
            # Auto-generate for development, but warn
            import logging
            logging.warning(
                "SESSION_SECRET_KEY not set. Generating random key. "
                "This will cause session loss on restart and issues with multiple workers. "
                "Set SESSION_SECRET_KEY in production!"
            )
            self.session_secret_key = secrets.token_hex(32)
        elif self.auth_disabled and not self.session_secret_key:
            # Auth disabled, generate a throwaway key
            self.session_secret_key = secrets.token_hex(32)
        return self

    # AI Provider Selection
    ai_provider: str = "gemini"

    # Gemini API Configuration
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3-pro-preview"
    gemini_timeout: int = 90
    gemini_api_base_url: Optional[str] = None  # Custom API endpoint for testing
    gemini_debug_logs: bool = False  # Enable verbose debug logging for Gemini API
    gemini_thinking_level: str = "low"  # Thinking effort: "low" (fast) or "high" (thorough)

    # Google Cloud Translation v2 (for status message translation EN->PL)
    translate_enabled: bool = False  # Enable status message translation
    translate_api_key: Optional[str] = None  # API key for Translation v2 Basic
    translate_timeout: float = 2.0  # Translation timeout in seconds
    translate_api_endpoint: Optional[str] = None  # Custom endpoint for e2e testing

    # App Configuration
    upload_max_size_mb: int = 10

    # Rate Limiting (rolling 24h windows)
    rate_limit_new_users_per_day: int = 50           # Max new user registrations per 24h
    rate_limit_submissions_per_user_per_day: int = 30  # Max submissions per user per 24h
    rate_limit_submissions_global_per_day: int = 500   # Max total submissions per 24h

    # Database
    database_url: Optional[str] = None  # Override with DATABASE_URL env var

    # Paths - can be overridden via environment
    data_dir: Optional[str] = None  # External data dir for cloud deployments

    # Paths (derived)
    base_dir: Path = Path(__file__).parent.parent

    @property
    def _data_path(self) -> Path:
        """Get data directory - external if set, otherwise base_dir."""
        if self.data_dir:
            return Path(self.data_dir)
        return self.base_dir

    @property
    def tasks_dir(self) -> Path:
        return self.base_dir / "tasks"

    @property
    def tasks_data_dir(self) -> Path:
        return self.base_dir / "data" / "tasks"

    def task_data_path(self, year: str, etap: str, number: int) -> Path:
        """Path to individual task metadata file."""
        return self.tasks_data_dir / year / etap / f"task_{number}.json"

    @property
    def submissions_dir(self) -> Path:
        path = self._data_path / "data" / "submissions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def uploads_dir(self) -> Path:
        path = self._data_path / "data" / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def prompts_dir(self) -> Path:
        return self.base_dir / "prompts"

    def gemini_prompt_path(self, etap: str = "etap2") -> Path:
        """Get Gemini prompt path for specific etap (etap1, etap2, or etap3)."""
        return self.prompts_dir / f"gemini_prompt_{etap}.txt"

    @property
    def db_url(self) -> str:
        """Get database URL, defaulting to local PostgreSQL."""
        if self.database_url:
            return self.database_url
        # Default to local PostgreSQL (via Docker on port 5433)
        return "postgresql://omj:omj@localhost:5433/omj"


settings = Settings()
