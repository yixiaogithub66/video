from video_platform.services import safety


def test_safety_blocks_risky_face_swap():
    result = safety.evaluate_instruction("Do a celebrity face swap deepfake")
    assert not result.allowed
    assert "high_risk_face_swap" in result.blocked_rules


def test_safety_allows_regular_edit():
    result = safety.evaluate_instruction("Remove the closed book from the table")
    assert result.allowed
    assert result.blocked_rules == []


def test_safety_admin_override_can_allow_blocked_rule(monkeypatch):
    class _TestSettings:
        def high_risk_review_keywords(self):
            return []

        def safety_override_allow_rules(self):
            return {"high_risk_face_swap"}

    monkeypatch.setattr(safety, "settings", _TestSettings())
    result = safety.evaluate_instruction(
        "Do a celebrity face swap deepfake",
        admin_override=True,
        override_reason="approved for internal benchmark",
    )
    assert result.allowed
    assert result.override_applied
