from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Authentication
    auth_key: str

    # Claude CLI Configuration
    claude_path: str = "claude"
    claude_model: str = "opus"
    claude_timeout: int = 300

    # App Configuration
    upload_max_size_mb: int = 10

    # Paths (derived)
    base_dir: Path = Path(__file__).parent.parent

    @property
    def tasks_dir(self) -> Path:
        return self.base_dir / "tasks"

    @property
    def tasks_index_path(self) -> Path:
        return self.base_dir / "tasks_index.json"

    @property
    def tasks_data_path(self) -> Path:
        return self.base_dir / "data" / "tasks.json"

    @property
    def submissions_dir(self) -> Path:
        return self.base_dir / "data" / "submissions"

    @property
    def uploads_dir(self) -> Path:
        return self.base_dir / "uploads"

    @property
    def prompts_dir(self) -> Path:
        return self.base_dir / "prompts"

    @property
    def system_prompt_path(self) -> Path:
        return self.prompts_dir / "system_prompt.txt"


settings = Settings()
