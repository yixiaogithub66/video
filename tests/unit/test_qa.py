from video_platform.services.qa import QAContext, evaluate, should_pass, should_route_manual_review


def test_qa_threshold_logic():
    r1 = evaluate(QAContext(instruction="remove object", iteration=1, capability="remove_object", output_uri="x"))
    r3 = evaluate(QAContext(instruction="remove object", iteration=3, capability="remove_object", output_uri="x"))

    assert r1.overall_score < r3.overall_score
    assert not should_pass(r1)
    assert should_pass(r3)


def test_qa_routes_high_risk_tasks_to_manual_review():
    report = evaluate(QAContext(instruction="color grade", iteration=3, capability="color_grade", output_uri="x"))
    route, reasons = should_route_manual_review("job-a", report, risk_level="high")
    assert route
    assert "high_risk_task_requires_manual_review" in reasons
