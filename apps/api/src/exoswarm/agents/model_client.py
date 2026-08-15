from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from exoswarm.domain.errors import ModelNotConfiguredError


class InferenceClient(Protocol):
    async def decide(
        self, *, role: str, context: BaseModel, output_schema: type[BaseModel]
    ) -> BaseModel: ...


class UnconfiguredInferenceClient:
    async def decide(
        self, *, role: str, context: BaseModel, output_schema: type[BaseModel]
    ) -> BaseModel:
        del role, context, output_schema
        raise ModelNotConfiguredError("live model inference is not configured in the scaffold")

