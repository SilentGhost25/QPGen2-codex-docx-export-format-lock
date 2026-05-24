from __future__ import annotations

from dataclasses import dataclass, field
import random

from ..policies import derive_difficulty_for_rbt, derive_rbt_for_co, CO_RBT_POLICY


EXAM_PATTERNS = (
    "all_10_mark",
    "one_6_6_8_rest_10",
    "mixed_dynamic",
    "two_8_8_4",
    "adaptive_randomized",
)


@dataclass(frozen=True)
class QuestionTask:
    question_number: int
    subpart: str
    label: str
    module: int
    co: str
    rbt: str
    difficulty: str
    marks: int
    topic: str = ""
    keywords: list[str] = field(default_factory=list)
    requires_image: bool = False


@dataclass(frozen=True)
class QuestionBlock:
    qno: int
    module: int
    type: str
    subquestions: list[QuestionTask]
    is_or: bool = False


@dataclass(frozen=True)
class PaperBlueprint:
    pattern: str
    max_marks: int
    blocks: list[QuestionBlock]
    tasks: list[QuestionTask]


def _format_label(question_number: int, subpart: str) -> str:
    return f"{question_number}({subpart})" if subpart else str(question_number)


def _get_module_co(module: int, module_co_map: dict[int | str, str] | None) -> str:
    if module_co_map:
        val = None
        if module in module_co_map:
            val = module_co_map[module]
        elif str(module) in module_co_map:
            val = module_co_map[str(module)]
            
        if val and isinstance(val, str):
            return val.upper().strip()
    return f"CO{min(module, 5)}"


def _distribution_for_module(pattern: str, module: int) -> list[int]:
    if pattern == "all_10_mark":
        return [10]
    if pattern == "two_8_8_4":
        return [8, 8, 4]
    if pattern == "one_6_6_8_rest_10":
        return [6, 6, 8] if module == 1 else [10]
    if pattern == "mixed_dynamic":
        return [6, 6, 8] if module in {1, 3} else [10]
    return [8, 8, 4] if module % 2 else [10]


def build_paper_blueprint(
    *,
    max_marks: int,
    modules: list[int],
    co_targets: dict[str, int] | None = None,
    module_co_map: dict[int, str] | None = None,
    module_image_map: dict[int, bool] | None = None,
    exam_style: str | None = None,
) -> PaperBlueprint:
    """Create the structure before any LLM call.

    The planner owns numbering, OR blocks, marks, CO, RBT, difficulty, and image
    task intent. LLMs only fill text for these tasks.
    """
    selected_modules = modules or [1, 2, 3, 4, 5]
    requested_pattern = exam_style if exam_style in EXAM_PATTERNS else None
    pattern = requested_pattern or ("one_6_6_8_rest_10" if max_marks >= 80 else "mixed_dynamic")

    blocks: list[QuestionBlock] = []
    tasks: list[QuestionTask] = []
    question_number = 1

    for module in selected_modules:
        distribution = _distribution_for_module(pattern, module)
        block_type = "single" if len(distribution) == 1 else f"{len(distribution)}_sub"
        for choice_index in range(2):
            subquestions: list[QuestionTask] = []
            co = _get_module_co(module, module_co_map)
            for sub_index, marks in enumerate(distribution):
                subpart = "" if len(distribution) == 1 else "abcd"[sub_index]
                
                # Derive RBT level automatically from the single selected CO
                allowed_rbts = CO_RBT_POLICY.get(co, ["L1", "L2"])
                rbt = random.choice(allowed_rbts)
                
                task = QuestionTask(
                    question_number=question_number,
                    subpart=subpart,
                    label=_format_label(question_number, subpart),
                    module=module,
                    co=co,
                    rbt=rbt,
                    difficulty=derive_difficulty_for_rbt(rbt),
                    marks=marks,
                    requires_image=bool(module_image_map and module_image_map.get(module) and choice_index == 0 and sub_index == 0),
                )
                subquestions.append(task)
                tasks.append(task)
            blocks.append(
                QuestionBlock(
                    qno=question_number,
                    module=module,
                    type=block_type,
                    subquestions=subquestions,
                    is_or=choice_index == 1,
                )
            )
            question_number += 1

    return PaperBlueprint(pattern=pattern, max_marks=max_marks, blocks=blocks, tasks=tasks)


def blueprint_to_legacy_slots(blueprint: PaperBlueprint) -> list[dict]:
    return [
        {
            "question_number": task.question_number,
            "subpart": task.subpart,
            "label": task.label,
            "marks": task.marks,
            "module_number": task.module,
            "co": task.co,
            "rbt": task.rbt,
            "difficulty": task.difficulty,
            "is_image_question": task.requires_image,
        }
        for task in blueprint.tasks
    ]
