from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    editing = "editing"
    qa = "qa"
    human_review = "human_review"
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"


class Capability(str, Enum):
    remove_object = "remove_object"
    replace_object = "replace_object"
    replace_background = "replace_background"
    stylize = "stylize"
    color_grade = "color_grade"
    remove_logo = "remove_logo"


class ReviewDecision(str, Enum):
    approve = "approve"
    reject = "reject"
    rerun = "rerun"
