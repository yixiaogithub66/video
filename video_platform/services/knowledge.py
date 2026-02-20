from __future__ import annotations

import hashlib
import math
from typing import Any

from sqlalchemy import select

from video_platform.config import settings
from video_platform.db import CaseRecord

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels
except Exception:  # pragma: no cover - optional runtime dependency
    QdrantClient = None
    qmodels = None


def simple_embedding(text: str, dims: int = 16) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec = [digest[i] / 255.0 for i in range(dims)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _qdrant_client() -> QdrantClient:
    if QdrantClient is None:
        raise RuntimeError("qdrant-client package is not installed")
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    try:
        client = _qdrant_client()
        existing = {c.name for c in client.get_collections().collections}
        if settings.qdrant_collection not in existing:
            if qmodels is not None:
                client.create_collection(
                    collection_name=settings.qdrant_collection,
                    vectors_config=qmodels.VectorParams(size=16, distance=qmodels.Distance.COSINE),
                )
    except Exception:
        # Keep platform available even when Qdrant is temporarily unavailable.
        return


def upsert_case_embedding(case: CaseRecord) -> None:
    if not case.embedding:
        return

    payload = {
        "case_id": case.id,
        "task_summary": case.task_summary,
        "tags": case.tags,
        "failure_reason": case.failure_reason,
        "fix_strategy": case.fix_strategy,
    }

    try:
        client = _qdrant_client()
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                qmodels.PointStruct(id=case.id, vector=case.embedding, payload=payload)
            ],
        )
    except Exception:
        return


def search_cases(session, query: str, top_k: int) -> list[dict[str, Any]]:
    query_vec = simple_embedding(query)

    try:
        client = _qdrant_client()
        hits = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vec,
            limit=top_k,
        )
        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "case_id": payload.get("case_id", str(hit.id)),
                    "task_summary": payload.get("task_summary", ""),
                    "tags": payload.get("tags", []),
                    "failure_reason": payload.get("failure_reason"),
                    "fix_strategy": payload.get("fix_strategy"),
                    "score": float(hit.score),
                }
            )
        if results:
            return results
    except Exception:
        pass

    # Fallback lexical search from PostgreSQL.
    rows = session.execute(select(CaseRecord).order_by(CaseRecord.created_at.desc()).limit(200)).scalars().all()
    query_tokens = {token for token in query.lower().split() if token}
    ranked: list[dict[str, Any]] = []
    for row in rows:
        text = f"{row.task_summary} {' '.join(row.tags or [])}".lower()
        tokens = set(text.split())
        overlap = len(tokens.intersection(query_tokens))
        score = overlap / max(1, len(query_tokens))
        ranked.append(
            {
                "case_id": row.id,
                "task_summary": row.task_summary,
                "tags": row.tags or [],
                "failure_reason": row.failure_reason,
                "fix_strategy": row.fix_strategy,
                "score": float(score),
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]
