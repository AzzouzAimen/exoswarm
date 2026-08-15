from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are read from the environment only."""

    model_config = SettingsConfigDict(env_prefix="EXOSWARM_", env_file=".env", extra="ignore")

    env: str = "development"
    model: str = "DeepSeek-V4-Flash-0731"
    runs_dir: Path = Path("runs")
    data_dir: Path = Path("data")
    max_steps: int = Field(default=12, ge=1)
    max_adaptive_experiments: int = Field(default=4, ge=0)

