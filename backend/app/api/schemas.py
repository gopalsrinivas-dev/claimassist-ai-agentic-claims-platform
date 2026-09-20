"""Shared transport schemas for operational endpoints and errors."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class StatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "ready"]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)
    correlation_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
