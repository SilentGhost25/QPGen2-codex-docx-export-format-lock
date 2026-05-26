from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .docx_exporter import (
    DSATMQuestionPaperGenerator,
    generate_question_paper,
    rebuild_blueprint_from_questions,
)
from ..academic.planning.blueprint_engine import build_paper_blueprint, QuestionTask

@dataclass
class PaperConfig:
    department: str
    subject: str
    subject_code: str
    semester: str
    max_marks: int
    duration: str
    date: str
    batch: str
    teaching_department: str
    exam_type: str
    modules: list[int]
    rbt_levels: list[str]
    co_targets: list[str]
    year: str = "2026"
    instructions: str = "Instruction: Answer the following questions"
    college_name: str = "Dayananda Sagar Academy of Technology & Management"
    affiliation: str = "(Autonomous Institute under VTU)"
    program_line: str = "6 Programs Accredited by NBA (CSE, ISE, ECE, EEE, MECH, CV)"
    co_descriptions: dict[str, str] = field(default_factory=dict)
    co_percentages: dict[str, int] = field(default_factory=dict)
    module_percentages: dict[str, int] = field(default_factory=dict)
    left_seal_label: str = "DSATM"
    right_seal_label: str = "IQAC"
    template_note: str | None = None
    template_family: str = "dsatm"


def build_question_blueprint(max_marks: int) -> list[QuestionTask]:
    bp = build_paper_blueprint(max_marks=max_marks, modules=[1, 2, 3, 4, 5])
    return bp.tasks


docx_generator = DSATMQuestionPaperGenerator()
