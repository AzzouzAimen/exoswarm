from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from exoswarm.domain.enums import AgentRole, ThinkingMode


class Settings(BaseSettings):
    """Runtime configuration. Secrets are read from the environment only."""

    model_config = SettingsConfigDict(env_prefix="EXOSWARM_", env_file=".env", extra="ignore")

    env: str = "development"
    model: str = "deepseek-ai/DeepSeek-V4-Flash-0731"
    featherless_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "featherless_api_key", "FEATHERLESS_API_KEY", "EXOSWARM_FEATHERLESS_API_KEY"
        ),
    )
    featherless_base_url: str = Field(
        default="https://api.featherless.ai/v1",
        validation_alias=AliasChoices(
            "featherless_base_url", "FEATHERLESS_BASE_URL", "EXOSWARM_FEATHERLESS_BASE_URL"
        ),
    )
    inference_timeout_seconds: float = Field(default=120.0, gt=0)
    inference_max_input_tokens: int = Field(default=32_000, ge=1, le=32_000)
    inference_max_output_tokens: int = Field(default=20_000, ge=1, le=20_000)
    agent_fallback_enabled: bool = False
    multi_agent_enabled: bool = True
    specialist_advisory_enabled: bool = True
    role_thinking_modes: dict[AgentRole, ThinkingMode] = Field(default_factory=dict)
    thinking_confirmed_roles: set[AgentRole] = Field(default_factory=set)
    runs_dir: Path = Path("runs")
    data_dir: Path = Path("data")
    target_manifest_path: Path | None = None
    max_steps: int = Field(default=12, ge=1)
    max_adaptive_experiments: int = Field(default=4, ge=0)
    max_adaptive_cost_units: int = Field(default=4, ge=0)
    max_model_calls: int = Field(default=32, ge=0)
    max_tool_calls: int = Field(default=8, ge=0)
    max_model_retries: int = Field(default=4, ge=0)
    max_critic_revisions: int = Field(default=1, ge=0)
    run_timeout_seconds: float = Field(default=600.0, gt=0)
    sse_poll_interval_seconds: float = Field(default=0.05, gt=0, le=5)

    @field_validator("featherless_api_key", mode="before")
    @classmethod
    def blank_api_key_is_unconfigured(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            return None if not value.get_secret_value().strip() else value
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def resolved_target_manifest_path(self) -> Path:
        configured = self.target_manifest_path
        if configured is not None:
            return configured.resolve()
        return (self.data_dir / "targets/source_manifest.json").resolve()

    def thinking_mode_for(self, role: AgentRole | str) -> ThinkingMode:
        return self.role_thinking_modes.get(AgentRole(role), ThinkingMode.OFF)
