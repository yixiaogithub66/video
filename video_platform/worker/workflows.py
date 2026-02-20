from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

from video_platform.config import settings
from video_platform.core.enums import JobStatus
from video_platform.worker.contracts import WorkflowInput, WorkflowResult

with workflow.unsafe.imports_passed_through():
    from video_platform.worker.activities import (
        execute_iteration,
        finalize_blocked,
        finalize_human_review,
        finalize_success,
        plan_iteration,
        qa_iteration,
        safety_precheck,
    )


@workflow.defn
class VideoEditWorkflow:
    @workflow.run
    async def run(self, payload: WorkflowInput) -> WorkflowResult:
        safety_result = await workflow.execute_activity(
            safety_precheck,
            payload.job_id,
            start_to_close_timeout=timedelta(minutes=2),
        )
        if not safety_result.allowed:
            await workflow.execute_activity(
                finalize_blocked,
                args=[payload.job_id, safety_result.reason],
                start_to_close_timeout=timedelta(minutes=2),
            )
            return WorkflowResult(
                job_id=payload.job_id,
                final_status=JobStatus.blocked.value,
                final_output_uri=None,
                iterations=0,
            )

        prior_issues: list[dict] = []
        latest_output_uri: str | None = None
        latest_report: dict = {}

        for iteration in range(1, settings.max_iterations + 1):
            plan = await workflow.execute_activity(
                plan_iteration,
                args=[payload.job_id, iteration, prior_issues],
                start_to_close_timeout=timedelta(minutes=5),
            )

            execution = await workflow.execute_activity(
                execute_iteration,
                args=[payload.job_id, iteration, plan.edit_plan],
                start_to_close_timeout=timedelta(minutes=20),
            )

            qa = await workflow.execute_activity(
                qa_iteration,
                args=[payload.job_id, iteration, execution.output_uri],
                start_to_close_timeout=timedelta(minutes=5),
            )

            latest_output_uri = execution.output_uri
            latest_report = qa.report

            if qa.passed:
                if qa.requires_manual_review:
                    reason = ",".join(qa.gate_reasons) if qa.gate_reasons else "manual_review_required"
                    await workflow.execute_activity(
                        finalize_human_review,
                        args=[payload.job_id, iteration, qa.report, reason],
                        start_to_close_timeout=timedelta(minutes=2),
                    )
                    return WorkflowResult(
                        job_id=payload.job_id,
                        final_status=JobStatus.human_review.value,
                        final_output_uri=execution.output_uri,
                        iterations=iteration,
                    )
                await workflow.execute_activity(
                    finalize_success,
                    args=[payload.job_id, iteration, qa.report, execution.output_uri],
                    start_to_close_timeout=timedelta(minutes=2),
                )
                return WorkflowResult(
                    job_id=payload.job_id,
                    final_status=JobStatus.succeeded.value,
                    final_output_uri=execution.output_uri,
                    iterations=iteration,
                )

            prior_issues = qa.report.get("issues", [])

        await workflow.execute_activity(
            finalize_human_review,
            args=[payload.job_id, settings.max_iterations, latest_report, "qa_not_passed_after_max_iterations"],
            start_to_close_timeout=timedelta(minutes=2),
        )

        return WorkflowResult(
            job_id=payload.job_id,
            final_status=JobStatus.human_review.value,
            final_output_uri=latest_output_uri,
            iterations=settings.max_iterations,
        )
