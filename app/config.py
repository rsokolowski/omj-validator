from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Authentication
    auth_key: str

    # AI Provider Selection
    ai_provider: str = "gemini"

    # Gemini API Configuration
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-3-pro-preview"
    gemini_timeout: int = 90

    # App Configuration
    upload_max_size_mb: int = 10

    # Paths - can be overridden via environment
    data_dir: Optional[str] = None  # External data dir (e.g., /data on Render)

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
    def tasks_index_path(self) -> Path:
        return self.base_dir / "tasks_index.json"

    @property
    def tasks_data_path(self) -> Path:
        return self.base_dir / "data" / "tasks.json"

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

    @property
    def gemini_prompt_path(self) -> Path:
        return self.prompts_dir / "gemini_prompt.txt"


settings = Settings()
