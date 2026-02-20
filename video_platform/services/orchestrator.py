from __future__ import annotations

import asyncio

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
from video_platform.worker.temporal_client import get_client


def _notify_callback(job, final_status: str, qa_report: dict | None = None):
    callback_url = callback_url_from_metadata(job.metadata_json)
    if not callback_url:
        return
    ok, detail = send_callback(
        callback_url,
        {
            "job_id": job.id,
            "status": final_status,
            "instruction": job.instruction,
            "capability": job.capability,
            "output_uri": job.output_uri,
            "latest_qa_score": job.latest_qa_score,
            "qa_report": qa_report or {},
        },
    )
    with db_session() as session:
        log_job_event(
            session=session,
            job_id=job.id,
            stage="callback_delivery",
            message="Callback delivered" if ok else "Callback delivery failed",
            payload={"callback_url": callback_url, "detail": detail, "status": final_status},
            level="info" if ok else "warning",
        )


async def start_orchestration(job_id: str) -> None:
    client = await get_client()
    if client is not None:
        try:
            from video_platform.worker.contracts import WorkflowInput
            from video_platform.worker.workflows import VideoEditWorkflow

            await client.start_workflow(
                VideoEditWorkflow.run,
                WorkflowInput(job_id=job_id),
                id=f"video-edit-{job_id}",
                task_queue=settings.temporal_task_queue,
            )
            with db_session() as session:
                log_job_event(
                    session=session,
                    job_id=job_id,
                    stage="workflow_started",
                    message="Temporal workflow started",
                    payload={"task_queue": settings.temporal_task_queue},
                )
            return
        except Exception as exc:
            with db_session() as session:
                log_job_event(
                    session=session,
                    job_id=job_id,
                    stage="workflow_start_error",
                    message="Failed to start Temporal workflow",
                    payload={"error": str(exc)},
                    level="error",
                )

    if settings.enable_fallback_orchestrator:
        asyncio.create_task(run_fallback(job_id))
        with db_session() as session:
            log_job_event(
                session=session,
                job_id=job_id,
                stage="fallback_started",
                message="Temporal unavailable, fallback orchestrator started",
                payload={},
                level="warning",
            )
        return

    with db_session() as session:
        set_job_status(session, job_id, JobStatus.failed, enforce=False)
        log_job_event(
            session=session,
            job_id=job_id,
            stage="job_failed",
            message="Temporal unavailable and fallback disabled",
            payload={},
            level="error",
        )
    raise RuntimeError("unable to start workflow")


async def run_fallback(job_id: str) -> dict:
    with db_session() as session:
        job = get_job(session, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")

        metadata = job.metadata_json or {}
        override_requested = bool(metadata.get("admin_override"))
        override_reason = metadata.get("override_reason")
        if not isinstance(override_reason, str):
            override_reason = None

        safety_result = safety.evaluate_instruction(
            job.instruction,
            admin_override=override_requested,
            override_reason=override_reason,
        )
        job.risk_level = safety_result.risk_level
        log_safety_event(
            session=session,
            job_id=job_id,
            blocked=not safety_result.allowed,
            rule_ids=safety_result.blocked_rules,
            reason=safety_result.reason,
            payload={
                "instruction": job.instruction,
                "override_requested": override_requested,
                "override_reason": override_reason,
            },
            risk_level=safety_result.risk_level,
            override_applied=safety_result.override_applied,
        )

        if safety_result.override_applied:
            log_job_event(
                session=session,
                job_id=job_id,
                stage="safety_override_applied",
                message="Admin safety override applied",
                payload={"blocked_rules": safety_result.blocked_rules, "override_reason": override_reason},
                level="warning",
            )

        if not safety_result.allowed:
            set_job_status(session, job_id, JobStatus.blocked)
            log_job_event(
                session=session,
                job_id=job_id,
                stage="job_blocked",
                message="Blocked by safety policy",
                payload={"reason": safety_result.reason},
                level="warning",
            )
            _notify_callback(job, JobStatus.blocked.value, qa_report={"reason": safety_result.reason})
            return {"final_status": JobStatus.blocked.value, "iterations": 0}

    prior_issues: list[dict] = []
    latest_output_uri: str | None = None
    latest_report: dict = {}

    for iteration in range(1, settings.max_iterations + 1):
        with db_session() as session:
            set_job_status(session, job_id, JobStatus.planning)
            job = get_job(session, job_id)
            if job is None:
                raise ValueError(f"job {job_id} not found")

            _ = search_cases(session, query=job.instruction, top_k=5)
            forced = Capability(job.capability) if job.capability else None
            model_bundle = job.model_bundle or "balanced_12g_bundle"
            plan = planner.generate_plan(
                instruction=job.instruction,
                model_bundle=model_bundle,
                prior_issues=prior_issues,
                forced=forced,
            )

            set_job_status(session, job_id, JobStatus.editing)
            run = executor.execute_plan(
                job_id=job_id,
                iteration=iteration,
                input_uri=job.input_uri,
                instruction=job.instruction,
                plan=EditPlan.model_validate(plan.model_dump()),
            )
            update_job_iteration(
                session=session,
                job_id=job_id,
                iteration=iteration,
                edit_plan=plan.model_dump(),
                execution_log=run["execution_log"],
                output_uri=run["output_uri"],
            )
            set_job_status(session, job_id, JobStatus.qa)

            report = qa.evaluate(
                qa.QAContext(
                    instruction=job.instruction,
                    iteration=iteration,
                    capability=plan.capability.value,
                    output_uri=run["output_uri"],
                )
            )
            report_payload = report.model_dump()
            create_qa_report(session, job_id=job_id, iteration=iteration, report=report_payload)

            latest_output_uri = run["output_uri"]
            latest_report = report_payload

            if qa.should_pass(report):
                route_manual, gate_reasons = qa.should_route_manual_review(
                    job_id=job.id,
                    report=report,
                    risk_level=job.risk_level,
                )
                if route_manual:
                    reason = ",".join(gate_reasons)
                    tags = [plan.capability.value, "human_review"]
                    if "random_spot_check" in gate_reasons:
                        tags.append("random_sampled")
                    if "high_risk_task_requires_manual_review" in gate_reasons:
                        tags.append("high_risk")
                    set_job_status(session, job_id, JobStatus.human_review)
                    create_case_record(
                        session=session,
                        job_id=job_id,
                        task_summary=job.instruction,
                        tags=tags,
                        failure_reason=reason,
                        fix_strategy="manual_review_required",
                        final_metrics={
                            "overall_score": report.overall_score,
                            "iterations": iteration,
                            "threshold": settings.qa_threshold,
                        },
                    )
                    log_job_event(
                        session=session,
                        job_id=job_id,
                        stage="manual_review_routed",
                        message="QA passed but routed to manual review",
                        payload={"reason": reason},
                        level="warning",
                    )
                    _notify_callback(job, JobStatus.human_review.value, qa_report=latest_report)
                    return {
                        "final_status": JobStatus.human_review.value,
                        "iterations": iteration,
                        "output_uri": latest_output_uri,
                    }

                set_job_status(session, job_id, JobStatus.succeeded)
                create_case_record(
                    session=session,
                    job_id=job_id,
                    task_summary=job.instruction,
                    tags=[plan.capability.value, "auto_passed"],
                    failure_reason=None,
                    fix_strategy="n/a",
                    final_metrics={
                        "overall_score": report.overall_score,
                        "iterations": iteration,
                        "threshold": settings.qa_threshold,
                    },
                )
                _notify_callback(job, JobStatus.succeeded.value, qa_report=latest_report)
                return {
                    "final_status": JobStatus.succeeded.value,
                    "iterations": iteration,
                    "output_uri": latest_output_uri,
                }

            prior_issues = report.issues

    with db_session() as session:
        set_job_status(session, job_id, JobStatus.human_review)
        job = get_job(session, job_id)
        if job is not None:
            create_case_record(
                session=session,
                job_id=job_id,
                task_summary=job.instruction,
                tags=[job.capability or "unknown", "human_review"],
                failure_reason="qa_not_passed_after_max_iterations",
                fix_strategy="manual_review_required",
                final_metrics={
                    "overall_score": latest_report.get("overall_score"),
                    "iterations": settings.max_iterations,
                    "threshold": settings.qa_threshold,
                },
            )
            _notify_callback(job, JobStatus.human_review.value, qa_report=latest_report)

    return {
        "final_status": JobStatus.human_review.value,
        "iterations": settings.max_iterations,
        "output_uri": latest_output_uri,
    }
