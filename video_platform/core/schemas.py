from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from video_platform.core.enums import Capability, JobStatus, ReviewDecision


class JobCreateRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=2000)
    input_uri: str
    callback_url: str | None = None
    force_capability: Capability | None = None
    safety_override: bool = False
    override_reason: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    instruction: str
    input_uri: str
    output_uri: str | None = None
    capability: Capability | None = None
    model_bundle: str | None = None
    model_config = {"protected_namespaces": ()}
    risk_level: str | None = None
    current_iteration: int
    max_iterations: int
    latest_qa_score: float | None = None
    created_at: datetime
    updated_at: datetime


class ArtifactManifestResponse(BaseModel):
    job_id: str
    raw: list[str]
    intermediate: list[str]
    output: list[str]
    audit: list[str]
    retention_days: dict[str, int]


class QAReportResponse(BaseModel):
    job_id: str
    iteration: int
    overall_score: float
    dimension_scores: dict[str, float]
    issues: list[dict[str, Any]]
    hard_fail_flags: list[str]
    recommendations: list[str]
    created_at: datetime


class ReviewDecisionRequest(BaseModel):
    decision: ReviewDecision
    reviewer: str = Field(default="ops-reviewer")
    reason: str = Field(default="manual review action")


class ReviewDecisionResponse(BaseModel):
    job_id: str
    decision: ReviewDecision
    resulting_status: JobStatus


class ModelRecommendationRequest(BaseModel):
    include_download_estimate: bool = True


class DeviceProfile(BaseModel):
    gpu_name: str | None
    gpu_count: int
    gpu_vram_gb: int
    cuda_available: bool
    cpu_cores: int
    memory_gb: int
    disk_free_gb: int


class ModelBundleSpec(BaseModel):
    name: str
    min_vram_gb: int
    estimated_time_minutes: int
    download_size_gb: float
    quality_tier: str
    enabled_modules: list[str]
    recommended: bool


class ModelRecommendationResponse(BaseModel):
    device: DeviceProfile
    bundles: list[ModelBundleSpec]
    default_bundle: str
    runtime_mode: str
    api_provider: str


class ModelInstallRequest(BaseModel):
    bundle_name: str


class ModelInstallResponse(BaseModel):
    bundle_name: str
    status: str
    install_path: str
    message: str | None = None


class CaseSearchRequest(BaseModel):
    query: str = Field(min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)


class CaseSearchResult(BaseModel):
    case_id: str
    task_summary: str
    tags: list[str]
    failure_reason: str | None
    fix_strategy: str | None
    score: float


class CaseSearchResponse(BaseModel):
    query: str
    results: list[CaseSearchResult]


class CaseResponse(BaseModel):
    case_id: str
    job_id: str | None
    task_summary: str
    tags: list[str]
    failure_reason: str | None
    fix_strategy: str | None
    final_metrics: dict[str, Any]
    created_at: datetime


class EditPlan(BaseModel):
    capability: Capability
    tool_chain: list[str]
    model_bundle: str
    iteration_budget: int
    constraints: dict[str, Any]
    fix_map: list[dict[str, str]]
    model_config = {"protected_namespaces": ()}


class QAReport(BaseModel):
    overall_score: float
    dimension_scores: dict[str, float]
    issues: list[dict[str, Any]]
    hard_fail_flags: list[str]
    recommendations: list[str]


class HealthResponse(BaseModel):
    status: str
    now: datetime


class JobListResponse(BaseModel):
    items: list[JobResponse]


class JobEventResponse(BaseModel):
    event_id: str
    job_id: str | None
    stage: str
    level: str
    message: str
    payload: dict[str, Any]
    created_at: datetime


class DependencyHealth(BaseModel):
    name: str
    ok: bool
    detail: str | None = None


class ReadyResponse(BaseModel):
    status: str
    dependencies: list[DependencyHealth]
    now: datetime


class ErrorResponse(BaseModel):
    error: str
    request_id: str | None = None
