from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserCreateRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=128)
    password_hash: str | None = Field(default=None, max_length=255)


class UserCreateResponse(BaseModel):
    id: str
    phone: str | None
    email: str | None
    role: Literal["student", "admin"]
    status: Literal["active", "disabled"]
    created_at: datetime


class AssignmentCreateRequest(BaseModel):
    user_id: str
    title: str = Field(..., min_length=2, max_length=200)
    question_text: str = Field(..., min_length=20)
    essay_text: str = Field(..., min_length=50)


class AssignmentCreateResponse(BaseModel):
    id: str
    user_id: str
    title: str
    status: Literal["submitted", "grading", "graded", "failed"]
    word_count: int
    submitted_at: datetime


class AssignmentHistoryItem(BaseModel):
    assignment_id: str
    title: str
    status: Literal["submitted", "grading", "graded", "failed"]
    word_count: int
    latest_score: float | None = None
    submitted_at: datetime


class GradingStrategyCreateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., min_length=2, max_length=100)
    scoring_standard: str = Field(..., min_length=2, max_length=50)
    prompt_template: str = Field(..., min_length=20)
    model_provider: str = Field(default="mock", max_length=50)
    model_name: str = Field(default="shenlun-heuristic-v1", max_length=100)
    is_active: bool = True


class GradingStrategyResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    name: str
    scoring_standard: str
    prompt_template: str
    model_provider: str
    model_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CorrectionSubmitRequest(BaseModel):
    assignment_id: str = Field(..., description="作业 ID")
    essay_text: str = Field(..., min_length=50, description="申论正文")
    question_text: str = Field(..., min_length=20, description="题干或材料摘要")
    scoring_standard: str = Field(default="shenlun_v1", max_length=50)
    target_score: float | None = Field(default=None, ge=0, le=100)
    is_regrade: bool = False
    trace_id: str | None = Field(default=None, max_length=100)


class CorrectionSubmitResponse(BaseModel):
    task_id: str
    status: Literal["queued", "processing"]
    estimated_seconds: int
    created_at: datetime


class ModelInfo(BaseModel):
    provider: str
    model: str
    prompt_version: str


class TokenUsage(BaseModel):
    input: int
    output: int
    total: int


class CorrectionStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    task_id: str
    status: Literal["processing", "succeeded", "failed"]
    correction_id: str | None = None
    overall_score: float | None = None
    dimension_scores: dict | None = None
    summary: str | None = None
    key_issues: list[str] | None = None
    revision_plan: list[str] | None = None
    model_info: ModelInfo
    token_usage: TokenUsage | None = None
    latency_ms: int | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class AssignmentDetailResponse(BaseModel):
    id: str
    user_id: str
    title: str
    question_text: str
    essay_text: str
    word_count: int
    status: Literal["submitted", "grading", "graded", "failed"]
    latest_correction_id: str | None
    submitted_at: datetime
