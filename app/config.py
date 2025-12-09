import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Authentication
    auth_disabled: bool = False  # Set to True to disable all auth (local dev)
    auth_key: str = ""  # Deprecated, kept for backward compatibility

    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None

    # Access control for alpha users
    # Option 1: Email allowlist (comma-separated, simplest approach)
    allowed_emails: Optional[str] = None  # e.g., "user1@gmail.com,user2@gmail.com"

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

    # App Configuration
    upload_max_size_mb: int = 10

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
