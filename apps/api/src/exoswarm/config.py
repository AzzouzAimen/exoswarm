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
    max_model_calls: int = Field(default=16, ge=0)
    max_tool_calls: int = Field(default=8, ge=0)
    max_model_retries: int = Field(default=1, ge=0)
    max_critic_revisions: int = Field(default=1, ge=0)
