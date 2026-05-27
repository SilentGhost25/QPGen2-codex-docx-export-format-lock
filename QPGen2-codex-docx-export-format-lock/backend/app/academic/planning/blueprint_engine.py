from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Tuple

from ..policies import derive_difficulty_for_rbt, derive_rbt_for_co, CO_RBT_POLICY

# ---------------------------------------------------------------------------
# Core Object Models (Requested by User)
# ---------------------------------------------------------------------------

@dataclass
class SubQuestion:
    label: str | None  # "a", "b", or None
    text: str
    marks: int
    co: str
    rbt: str
    image_path: str | None = None
    difficulty: str = "balanced"
    figure_image_paths: list[str] = field(default_factory=list)


@dataclass
class QuestionBlock:
    qno: int
    is_or_pair: bool
    subquestions: list[SubQuestion]
    marks_total: int

    @property
    def module(self) -> int:
        return (self.qno - 1) // 2 + 1

    @property
    def co(self) -> str:
        return self.subquestions[0].co if self.subquestions else "CO1"

    @property
    def rbt(self) -> str:
        return self.subquestions[0].rbt if self.subquestions else "L2"

    @property
    def type(self) -> str:
        count = len(self.subquestions)
        if count == 1 and not self.subquestions[0].label:
            return "single"
        return "two_part" if count == 2 else "three_part"


@dataclass
class ModuleBlock:
    module_no: int
    left_question: QuestionBlock
    right_question: QuestionBlock | None  # None for IAT/50-marks


@dataclass
class PaperBlueprint:
    paper_type: str
    total_marks: int
    duration: int
    modules: list[ModuleBlock]

    @property
    def slots(self) -> list[QuestionBlock]:
        slotList = []
        for mod in self.modules:
            slotList.append(mod.left_question)
            if mod.right_question:
                slotList.append(mod.right_question)
        return slotList

    @property
    def pattern(self) -> str:
        return "flat_ia" if self.total_marks == 50 else "mixed_dynamic"

    @property
    def max_marks(self) -> int:
        return self.total_marks

    @property
    def tasks(self) -> list[QuestionTask]:
        taskList = []
        for mod in self.modules:
            # Left question
            for sub in mod.left_question.subquestions:
                taskList.append(
                    QuestionTask(
                        question_number=mod.left_question.qno,
                        subpart=sub.label or "",
                        label=f"{mod.left_question.qno}({sub.label})" if sub.label else str(mod.left_question.qno),
                        module=mod.module_no,
                        co=sub.co,
                        rbt=sub.rbt,
                        difficulty=sub.difficulty,
                        marks=sub.marks,
                    )
                )
            # Right question
            if mod.right_question:
                for sub in mod.right_question.subquestions:
                    taskList.append(
                        QuestionTask(
                            question_number=mod.right_question.qno,
                            subpart=sub.label or "",
                            label=f"{mod.right_question.qno}({sub.label})" if sub.label else str(mod.right_question.qno),
                            module=mod.module_no,
                            co=sub.co,
                            rbt=sub.rbt,
                            difficulty=sub.difficulty,
                            marks=sub.marks,
                        )
                    )
        return taskList

    @property
    def blocks(self) -> list[QuestionBlockLegacy]:
        blockList = []
        for mod in self.modules:
            # Left Question Block
            subquestions_left = []
            for sub in mod.left_question.subquestions:
                subquestions_left.append(
                    QuestionTask(
                        question_number=mod.left_question.qno,
                        subpart=sub.label or "",
                        label=f"{mod.left_question.qno}({sub.label})" if sub.label else str(mod.left_question.qno),
                        module=mod.module_no,
                        co=sub.co,
                        rbt=sub.rbt,
                        difficulty=sub.difficulty,
                        marks=sub.marks,
                    )
                )
            blockList.append(
                QuestionBlockLegacy(
                    qno=mod.left_question.qno,
                    module=mod.module_no,
                    type="single" if len(subquestions_left) == 1 else "two_part" if len(subquestions_left) == 2 else "three_part",
                    subquestions=subquestions_left,
                    is_or=False,
                )
            )
            
            # Right Question Block
            if mod.right_question:
                subquestions_right = []
                for sub in mod.right_question.subquestions:
                    subquestions_right.append(
                        QuestionTask(
                            question_number=mod.right_question.qno,
                            subpart=sub.label or "",
                            label=f"{mod.right_question.qno}({sub.label})" if sub.label else str(mod.right_question.qno),
                            module=mod.module_no,
                            co=sub.co,
                            rbt=sub.rbt,
                            difficulty=sub.difficulty,
                            marks=sub.marks,
                        )
                    )
                blockList.append(
                    QuestionBlockLegacy(
                        qno=mod.right_question.qno,
                        module=mod.module_no,
                        type="single" if len(subquestions_right) == 1 else "two_part" if len(subquestions_right) == 2 else "three_part",
                        subquestions=subquestions_right,
                        is_or=True,  # Right question represents choice B (OR option)
                    )
                )
        return blockList


# ---------------------------------------------------------------------------
# Backward-Compatible Type definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaperSlot:
    slot_id: int
    module: int
    marks: int
    co: str
    rbt: str
    kind: str          # "single", "two_part", "three_part"
    parts: Tuple[int, ...]  # e.g. (5, 5) or (2, 3, 5)


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
class QuestionBlockLegacy:
    qno: int
    module: int
    type: str
    subquestions: list[QuestionTask]
    is_or: bool = False


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
    """Create the structure before any LLM call."""
    selected_modules = modules or [1, 2, 3, 4, 5]
    module_blocks = []
    
    if max_marks < 100:
        # IAT Paper (< 100 Marks)
        # Allowed: single question (10 marks) or 2 subquestions (5+5 marks). NO 3-subquestion modules.
        # Exactly two alternatives per module (e.g. Q1 OR Q2)
        for m in selected_modules:
            co = _get_module_co(m, module_co_map)
            allowed_rbts = CO_RBT_POLICY.get(co, ["L1", "L2", "L3"])
            left_qno = (m - 1) * 2 + 1
            right_qno = (m - 1) * 2 + 2
            
            # Left Question Block
            rbt_l = random.choice(allowed_rbts) if allowed_rbts else "L" + str(min(m + 1, 6))
            is_two_part_l = random.choice([True, False])
            if is_two_part_l:
                subquestions_l = [
                    SubQuestion(label="a", text="", marks=5, co=co, rbt=rbt_l),
                    SubQuestion(label="b", text="", marks=5, co=co, rbt=rbt_l),
                ]
            else:
                subquestions_l = [SubQuestion(label=None, text="", marks=10, co=co, rbt=rbt_l)]
            left = QuestionBlock(
                qno=left_qno,
                is_or_pair=False,
                subquestions=subquestions_l,
                marks_total=10,
            )
            
            # Right Question Block
            rbt_r = random.choice(allowed_rbts) if allowed_rbts else "L" + str(min(m + 1, 6))
            is_two_part_r = random.choice([True, False])
            if is_two_part_r:
                subquestions_r = [
                    SubQuestion(label="a", text="", marks=5, co=co, rbt=rbt_r),
                    SubQuestion(label="b", text="", marks=5, co=co, rbt=rbt_r),
                ]
            else:
                subquestions_r = [SubQuestion(label=None, text="", marks=10, co=co, rbt=rbt_r)]
            right = QuestionBlock(
                qno=right_qno,
                is_or_pair=True,
                subquestions=subquestions_r,
                marks_total=10,
            )
            
            module_blocks.append(
                ModuleBlock(
                    module_no=m,
                    left_question=left,
                    right_question=right,
                )
            )
    else:
        # End-Sem Paper (> 50 marks, typically 100 marks)
        # Rule 3: exactly ONE module has a 3-subquestion structure, others have single or 2-subquestions.
        three_sub_module = random.choice(selected_modules)
        
        for module in selected_modules:
            co = _get_module_co(module, module_co_map)
            allowed_rbts = CO_RBT_POLICY.get(co, ["L1", "L2", "L3"])
            left_qno = (module - 1) * 2 + 1
            right_qno = (module - 1) * 2 + 2
            
            if module == three_sub_module:
                # 3 subquestions format for both choice options (Left and Right)
                distribution = random.choice([[6, 6, 8], [8, 8, 4]])
                
                # Left
                subparts_left = []
                subpart_chars = ["a", "b", "c"]
                rbt_l = random.choice(allowed_rbts) if allowed_rbts else "L" + str(min(module + 1, 6))
                for idx, part_marks in enumerate(distribution):
                    subparts_left.append(SubQuestion(label=subpart_chars[idx], text="", marks=part_marks, co=co, rbt=rbt_l))
                left = QuestionBlock(
                    qno=left_qno,
                    is_or_pair=False,
                    subquestions=subparts_left,
                    marks_total=20,
                )
                
                # Right
                subparts_right = []
                rbt_r = random.choice(allowed_rbts) if allowed_rbts else "L" + str(min(module + 1, 6))
                for idx, part_marks in enumerate(distribution):
                    subparts_right.append(SubQuestion(label=subpart_chars[idx], text="", marks=part_marks, co=co, rbt=rbt_r))
                right = QuestionBlock(
                    qno=right_qno,
                    is_or_pair=True,
                    subquestions=subparts_right,
                    marks_total=20,
                )
            else:
                # 1 or 2 subquestions format
                # Let's decide randomly for each question option
                # Left
                is_two_part_left = random.choice([True, False])
                rbt_l = random.choice(allowed_rbts) if allowed_rbts else "L" + str(min(module + 1, 6))
                if is_two_part_left:
                    subparts_left = [
                        SubQuestion(label="a", text="", marks=10, co=co, rbt=rbt_l),
                        SubQuestion(label="b", text="", marks=10, co=co, rbt=rbt_l),
                    ]
                else:
                    subparts_left = [SubQuestion(label=None, text="", marks=20, co=co, rbt=rbt_l)]
                left = QuestionBlock(
                    qno=left_qno,
                    is_or_pair=False,
                    subquestions=subparts_left,
                    marks_total=20,
                )
                
                # Right
                is_two_part_right = random.choice([True, False])
                rbt_r = random.choice(allowed_rbts) if allowed_rbts else "L" + str(min(module + 1, 6))
                if is_two_part_right:
                    subparts_right = [
                        SubQuestion(label="a", text="", marks=10, co=co, rbt=rbt_r),
                        SubQuestion(label="b", text="", marks=10, co=co, rbt=rbt_r),
                    ]
                else:
                    subparts_right = [SubQuestion(label=None, text="", marks=20, co=co, rbt=rbt_r)]
                right = QuestionBlock(
                    qno=right_qno,
                    is_or_pair=True,
                    subquestions=subparts_right,
                    marks_total=20,
                )
                
            module_blocks.append(
                ModuleBlock(
                    module_no=module,
                    left_question=left,
                    right_question=right,
                )
            )
            
    # Verification and Validation Check
    three_subquestion_modules = sum(1 for m in module_blocks if len(m.left_question.subquestions) == 3)
    if max_marks >= 100 and three_subquestion_modules > 1:
        raise ValueError("End-Sem papers cannot have more than ONE 3-subquestion module.")
        
    return PaperBlueprint(
        paper_type="semester-end" if max_marks >= 100 else "internal-assessment",
        total_marks=max_marks,
        duration=180 if max_marks >= 100 else 90,
        modules=module_blocks,
    )


def blueprint_to_legacy_slots(blueprint: list[PaperSlot]) -> list[dict]:
    legacy = []
    qno = 1
    for slot in blueprint:
        subpart_chars = ["a", "b", "c", "d"]
        for idx, part_marks in enumerate(slot.parts):
            subpart = subpart_chars[idx] if len(slot.parts) > 1 else ""
            label = f"{qno}({subpart})" if subpart else str(qno)
            legacy.append(
                {
                    "question_number": qno,
                    "subpart": subpart,
                    "label": label,
                    "marks": part_marks,
                    "module_number": slot.module,
                    "co": slot.co,
                    "rbt": slot.rbt,
                    "difficulty": "balanced",
                    "is_image_question": False,
                }
            )
        qno += 1
    return legacy

