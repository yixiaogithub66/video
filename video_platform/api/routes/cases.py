from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from video_platform.api.deps import get_db, require_token
from video_platform.core.schemas import CaseResponse, CaseSearchRequest, CaseSearchResponse, CaseSearchResult
from video_platform.services.knowledge import search_cases
from video_platform.services.repository import get_case

router = APIRouter(prefix="/api/v1/cases", tags=["cases"], dependencies=[Depends(require_token)])


@router.post("/search", response_model=CaseSearchResponse)
def search_cases_endpoint(payload: CaseSearchRequest, db: Session = Depends(get_db)):
    matches = search_cases(db, query=payload.query, top_k=payload.top_k)
    return CaseSearchResponse(
        query=payload.query,
        results=[CaseSearchResult(**row) for row in matches],
    )


@router.get("/{case_id}", response_model=CaseResponse)
def get_case_endpoint(case_id: str, db: Session = Depends(get_db)):
    case = get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")

    return CaseResponse(
        case_id=case.id,
        job_id=case.job_id,
        task_summary=case.task_summary,
        tags=case.tags or [],
        failure_reason=case.failure_reason,
        fix_strategy=case.fix_strategy,
        final_metrics=case.final_metrics or {},
        created_at=case.created_at,
    )
