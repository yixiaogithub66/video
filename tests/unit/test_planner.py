from video_platform.core.enums import Capability
from video_platform.services.planner import detect_capability, generate_plan


def test_detect_capability_remove_object():
    cap = detect_capability("Please remove the logo from the shirt")
    assert cap == Capability.remove_logo


def test_generate_plan_has_expected_fields():
    plan = generate_plan(
        instruction="Replace the cup with a flower vase",
        model_bundle="balanced_12g_bundle",
        prior_issues=[{"code": "temporal_flicker", "description": "flicker issue"}],
    )
    assert plan.iteration_budget == 3
    assert plan.model_bundle == "balanced_12g_bundle"
    assert len(plan.tool_chain) >= 3
    assert len(plan.fix_map) == 1
