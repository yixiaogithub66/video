from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from video_platform.config import settings
from video_platform.utils.time import now_utc


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    instruction: Mapped[str] = mapped_column(Text)
    input_uri: Mapped[str] = mapped_column(Text)
    output_uri: Mapped[str | None] = mapped_column(Text)
    capability: Mapped[str | None] = mapped_column(String(64), index=True)
    model_bundle: Mapped[str | None] = mapped_column(String(64))
    risk_level: Mapped[str | None] = mapped_column(String(32))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    latest_qa_score: Mapped[float | None] = mapped_column(Float)
    current_iteration: Mapped[int] = mapped_column(Integer, default=0)
    max_iterations: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    iterations: Mapped[list[JobIteration]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobIteration(Base):
    __tablename__ = "job_iterations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer)
    edit_plan: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_log: Mapped[dict] = mapped_column(JSON, default=dict)
    output_uri: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    job: Mapped[Job] = relationship(back_populates="iterations")


class QAReport(Base):
    __tablename__ = "qa_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    iteration: Mapped[int] = mapped_column(Integer)
    overall_score: Mapped[float] = mapped_column(Float)
    dimension_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    hard_fail_flags: Mapped[list] = mapped_column(JSON, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    raw_report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reviewer: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ModelBundle(Base):
    __tablename__ = "model_bundles"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    min_vram_gb: Mapped[int] = mapped_column(Integer)
    estimated_time_minutes: Mapped[int] = mapped_column(Integer)
    download_size_gb: Mapped[float] = mapped_column(Float)
    quality_tier: Mapped[str] = mapped_column(String(32))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class CaseRecord(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    task_summary: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    fix_strategy: Mapped[str | None] = mapped_column(Text)
    final_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_ids: Mapped[list] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("jobs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(64), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


engine_kwargs = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
