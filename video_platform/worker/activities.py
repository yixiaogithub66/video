from __future__ import annotations

from temporalio import activity

from video_platform.config import settings
from video_platform.core.enums import Capability, JobStatus
from video_platform.core.schemas import EditPlan
from video_platform.db import db_session
from video_platform.services import executor, planner, qa, safety
from video_platform.services.callbacks import callback_url_from_metadata, send_callback
from video_platform.services.knowledge import search_cases
from video_platform.services.repository import (
    create_case_record,
    create_qa_report,
    get_job,
    log_job_event,
    log_safety_event,
    set_job_status,
    update_job_iteration,
)
from video_platform.worker.contracts import (
    ActivityExecutionResult,
    ActivityPlanResult,
    ActivityQAResult,
    ActivitySafetyResult,
)


def _notify_terminal_callback(session, job, final_status: str, qa_report: dict | None = None, output_uri: str | None = None) -> None:
    callback_url = callback_url_from_metadata(job.metadata_json)
    if not callback_url:
        return

    payload = {
        "job_id": job.id,
        "status": final_status,
        "instruction": job.instruction,
        "capability": job.capability,
        "output_uri": output_uri or job.output_uri,
        "latest_qa_score": job.latest_qa_score,
        "qa_report": qa_report or {},
    }
    ok, detail = send_callback(callback_url, payload)
    log_job_event(
        session=session,
        job_id=job.id,
        stage="callback_delivery",
        message="Callback delivered" if ok else "Callback delivery failed",
        payload={"callback_url": callback_url, "detail": detail, "status": final_status},
        level="info" if ok else "warning",
    )


@activity.defn
async def safety_precheck(job_id: str) -> ActivitySafetyResult:
    with db_session() as session:
        job = get_job(session, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")

        metadata = job.metadata_json or {}
        override_requested = bool(metadata.get("admin_override"))
        override_reason = metadata.get("override_reason")
        if not isinstance(override_reason, str):
            override_reason = None

        result = safety.evaluate_instruction(
            job.instruction,
            admin_override=override_requested,
            override_reason=override_reason,
        )
        job.risk_level = result.risk_level
        log_safety_event(
            session=session,
            job_id=job_id,
            blocked=not result.allowed,
            rule_ids=result.blocked_rules,
            reason=result.reason,
            payload={
                "instruction": job.instruction,
                "override_requested": override_requested,
                "override_reason": override_reason,
            },
            risk_level=result.risk_level,
            override_applied=result.override_applied,
        )

        if result.override_applied:
            log_job_event(
                session=session,
                job_id=job_id,
                stage="safety_override_applied",
                message="Admin safety override applied",
                payload={"blocked_rules": result.blocked_rules, "override_reason": override_reason},
                level="warning",
            )

        if not result.allowed:
            set_job_status(session, job_id, JobStatus.blocked)

        return ActivitySafetyResult(
            allowed=result.allowed,
            blocked_rules=result.blocked_rules,
            reason=result.reason,
        )


@activity.defn
async def plan_iteration(job_id: str, iteration: int, prior_issues: list[dict]) -> ActivityPlanResult:
    with db_session() as session:
        set_job_status(session, job_id, JobStatus.planning)
        job = get_job(session, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")

        retrieved_cases = search_cases(session, query=job.instruction, top_k=5)
        forced_capability = None
        if job.capability:
            forced_capability = Capability(job.capability)

        model_bundle = job.model_bundle or "balanced_12g_bundle"

        plan = planner.generate_plan(
            instruction=job.instruction,
            model_bundle=model_bundle,
            prior_issues=prior_issues,
            forced=forced_capability,
        )

        plan_payload = plan.model_dump()
        plan_payload["retrieved_cases"] = retrieved_cases

        job.capability = plan.capability.value
        if not job.model_bundle:
            job.model_bundle = model_bundle
        return ActivityPlanResult(edit_plan=plan_payload)


@activity.defn
async def execute_iteration(job_id: str, iteration: int, edit_plan: dict) -> ActivityExecutionResult:
    with db_session() as session:
        set_job_status(session, job_id, JobStatus.editing)
        job = get_job(session, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")

        plan = EditPlan.model_validate(edit_plan)

        run = executor.execute_plan(
            job_id=job_id,
            iteration=iteration,
            input_uri=job.input_uri,
            instruction=job.instruction,
            plan=plan,
        )

        update_job_iteration(
            session=session,
            job_id=job_id,
            iteration=iteration,
            edit_plan=edit_plan,
            execution_log=run["execution_log"],
            output_uri=run["output_uri"],
        )

        return ActivityExecutionResult(
            output_uri=run["output_uri"],
            execution_log=run["execution_log"],
        )


@activity.defn
async def qa_iteration(job_id: str, iteration: int, output_uri: str) -> ActivityQAResult:
    with db_session() as session:
        set_job_status(session, job_id, JobStatus.qa)
        job = get_job(session, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")

        report = qa.evaluate(
            qa.QAContext(
                instruction=job.instruction,
                iteration=iteration,
                capability=job.capability or "unknown",
                output_uri=output_uri,
            )
        )
        report_payload = report.model_dump()
        create_qa_report(session, job_id=job_id, iteration=iteration, report=report_payload)

        passed = qa.should_pass(report)
        requires_manual_review = False
        gate_reasons: list[str] = []
        if passed:
            requires_manual_review, gate_reasons = qa.should_route_manual_review(
                job_id=job.id,
                report=report,
                risk_level=job.risk_level,
            )
            if requires_manual_review:
                log_job_event(
                    session=session,
                    job_id=job_id,
                    stage="qa_gate_manual_review",
                    message="QA passed but task routed to manual review",
                    payload={"gate_reasons": gate_reasons, "risk_level": job.risk_level},
                    level="warning",
                )

        return ActivityQAResult(
            report=report_payload,
            passed=passed,
            requires_manual_review=requires_manual_review,
            gate_reasons=gate_reasons,
        )


@activity.defn
async def finalize_success(job_id: str, iteration: int, qa_report: dict, output_uri: str) -> None:
    with db_session() as session:
        job = set_job_status(session, job_id, JobStatus.succeeded)
        job.output_uri = output_uri
        create_case_record(
            session=session,
            job_id=job_id,
            task_summary=job.instruction,
            tags=[job.capability or "unknown", "auto_passed"],
            failure_reason=None,
            fix_strategy="n/a",
            final_metrics={
                "overall_score": qa_report.get("overall_score"),
                "iterations": iteration,
                "threshold": settings.qa_threshold,
            },
        )
        _notify_terminal_callback(session, job, final_status=JobStatus.succeeded.value, qa_report=qa_report, output_uri=output_uri)


@activity.defn
async def finalize_human_review(
    job_id: str,
    iteration: int,
    qa_report: dict,
    reason: str = "manual_review_required",
) -> None:
    with db_session() as session:
        job = set_job_status(session, job_id, JobStatus.human_review)
        tags = [job.capability or "unknown", "human_review"]
        if "random_spot_check" in reason:
            tags.append("random_sampled")
        if "high_risk" in reason:
            tags.append("high_risk")
        create_case_record(
            session=session,
            job_id=job_id,
            task_summary=job.instruction,
            tags=tags,
            failure_reason=reason,
            fix_strategy="manual_review_required",
            final_metrics={
                "overall_score": qa_report.get("overall_score"),
                "iterations": iteration,
                "threshold": settings.qa_threshold,
            },
        )
        log_job_event(
            session=session,
            job_id=job_id,
            stage="manual_review_routed",
            message="Job routed to manual review",
            payload={"reason": reason},
            level="warning",
        )
        _notify_terminal_callback(session, job, final_status=JobStatus.human_review.value, qa_report=qa_report, output_uri=job.output_uri)


@activity.defn
async def finalize_blocked(job_id: str, reason: str) -> None:
    with db_session() as session:
        job = get_job(session, job_id)
        if job is None:
            return
        set_job_status(session, job_id, JobStatus.blocked, enforce=False)
        log_job_event(
            session=session,
            job_id=job_id,
            stage="job_blocked",
            message="Blocked by safety policy",
            payload={"reason": reason},
            level="warning",
        )
        _notify_terminal_callback(session, job, final_status=JobStatus.blocked.value, qa_report={"reason": reason}, output_uri=None)
