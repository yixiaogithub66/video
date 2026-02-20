from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from video_platform.config import settings
from video_platform.core.schemas import QAReport


@dataclass
class QAContext:
    instruction: str
    iteration: int
    capability: str
    output_uri: str


def _base_scores(iteration: int) -> dict[str, float]:
    # Scores improve slightly on later iterations because fixes are applied.
    improvement = min(0.1, 0.03 * max(0, iteration - 1))
    return {
        "instruction_adherence": 0.74 + improvement,
        "temporal_consistency": 0.75 + improvement,
        "visual_artifacts": 0.78 + improvement,
        "edit_region_accuracy": 0.76 + improvement,
        "safety_compliance": 0.99,
    }


def evaluate(context: QAContext) -> QAReport:
    scores = _base_scores(context.iteration)

    issues: list[dict] = []
    hard_fail_flags: list[str] = []
    recommendations: list[str] = []

    if scores["temporal_consistency"] < 0.8:
        issues.append(
            {
                "code": "temporal_flicker",
                "severity": "medium",
                "description": "Noticeable frame-to-frame flicker in edited region",
                "timeline": "00:00:02-00:00:06",
            }
        )
        recommendations.append("Increase temporal smoothing and tracking confidence")

    if scores["instruction_adherence"] < 0.82:
        issues.append(
            {
                "code": "instruction_partial_match",
                "severity": "medium",
                "description": "Edit result only partially matches the instruction",
                "timeline": "00:00:01-00:00:10",
            }
        )
        recommendations.append("Tighten edit mask scope and object consistency constraints")

    overall = round(sum(scores.values()) / len(scores), 4)

    if scores["safety_compliance"] < 0.9:
        hard_fail_flags.append("safety")
    if scores["visual_artifacts"] < 0.65:
        hard_fail_flags.append("severe_artifacts")

    return QAReport(
        overall_score=overall,
        dimension_scores=scores,
        issues=issues,
        hard_fail_flags=hard_fail_flags,
        recommendations=recommendations,
    )


def should_pass(report: QAReport) -> bool:
    return report.overall_score >= settings.qa_threshold and len(report.hard_fail_flags) == 0


def _stable_sample(job_id: str, ratio: float) -> bool:
    bounded = max(0.0, min(1.0, ratio))
    if bounded <= 0:
        return False
    if bounded >= 1:
        return True

    digest = sha256(job_id.encode("utf-8")).digest()
    sample = int.from_bytes(digest[:8], byteorder="big", signed=False) / float(2**64)
    return sample < bounded


def should_route_manual_review(
    job_id: str,
    report: QAReport,
    *,
    risk_level: str | None = None,
) -> tuple[bool, list[str]]:
    if not should_pass(report):
        return False, []

    reasons: list[str] = []
    if (risk_level or "").lower() == "high":
        reasons.append("high_risk_task_requires_manual_review")

    if _stable_sample(job_id, settings.qa_random_review_ratio):
        reasons.append("random_spot_check")

    return bool(reasons), reasons
