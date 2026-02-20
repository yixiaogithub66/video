from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkflowInput:
    job_id: str
    forced_capability: str | None = None


@dataclass
class ActivitySafetyResult:
    allowed: bool
    blocked_rules: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class ActivityPlanResult:
    edit_plan: dict


@dataclass
class ActivityExecutionResult:
    output_uri: str
    execution_log: dict


@dataclass
class ActivityQAResult:
    report: dict
    passed: bool
    requires_manual_review: bool = False
    gate_reasons: list[str] = field(default_factory=list)


@dataclass
class WorkflowResult:
    job_id: str
    final_status: str
    final_output_uri: str | None = None
    iterations: int = 0
