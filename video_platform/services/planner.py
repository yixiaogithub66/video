from __future__ import annotations

from dataclasses import asdict

from video_platform.config import settings
from video_platform.core.enums import Capability
from video_platform.core.schemas import EditPlan
from video_platform.services.capabilities import CAPABILITY_HINTS, CAPABILITY_TOOLCHAIN


def detect_capability(instruction: str, forced: Capability | None = None) -> Capability:
    if forced is not None:
        return forced

    normalized = instruction.lower()

    # Prioritize highly specific intents before generic keyword scoring.
    if any(token in normalized for token in ("logo", "watermark", "去logo", "水印")):
        return Capability.remove_logo

    scored: list[tuple[int, int, Capability]] = []
    for capability, hints in CAPABILITY_HINTS.items():
        match_tokens = [token for token in hints if token in normalized]
        if not match_tokens:
            continue
        score = sum(2 if len(token) >= 6 else 1 for token in match_tokens)
        specificity = max(len(token) for token in match_tokens)
        scored.append((score, specificity, capability))

    if scored:
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return scored[0][2]

    return Capability.replace_object


def build_fix_map(prior_issues: list[dict]) -> list[dict[str, str]]:
    fix_map: list[dict[str, str]] = []
    for issue in prior_issues:
        issue_code = issue.get("code", "unknown_issue")
        description = issue.get("description", "improve quality")
        fix_map.append(
            {
                "fix_point": issue_code,
                "tool_action": f"adjust_pipeline_for_{issue_code}",
                "expected_improvement": description,
            }
        )
    return fix_map


def generate_plan(
    instruction: str,
    model_bundle: str,
    prior_issues: list[dict] | None = None,
    forced: Capability | None = None,
) -> EditPlan:
    capability = detect_capability(instruction=instruction, forced=forced)
    fix_map = build_fix_map(prior_issues or [])

    constraints = {
        "max_resolution": "1920x1080",
        "max_duration_seconds": 30,
        "quality_priority": True,
        "strict_safety": True,
    }

    return EditPlan(
        capability=capability,
        tool_chain=CAPABILITY_TOOLCHAIN[capability],
        model_bundle=model_bundle,
        iteration_budget=settings.max_iterations,
        constraints=constraints,
        fix_map=fix_map,
    )


def plan_as_dict(plan: EditPlan) -> dict:
    return asdict(plan) if hasattr(plan, "__dataclass_fields__") else plan.model_dump()
