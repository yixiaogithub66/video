from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from video_platform.db import (
    CaseRecord,
    Job,
    JobEvent,
    JobIteration,
    QAReport,
    ReviewAction,
    SafetyEvent,
    db_session,
    init_db,
)


@pytest.fixture(autouse=True)
def clean_state():
    init_db()
    with db_session() as session:
        session.query(ReviewAction).delete()
        session.query(JobEvent).delete()
        session.query(QAReport).delete()
        session.query(JobIteration).delete()
        session.query(SafetyEvent).delete()
        session.query(CaseRecord).delete()
        session.query(Job).delete()

    models_dir = Path("models")
    if models_dir.exists():
        for item in models_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
    yield
