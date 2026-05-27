from typing import List, Tuple
from .question_body_builder import QuestionSlot

ALLOWED_PAIRS = {
    1: (1, 2),
    2: (3, 4),
    3: (5, 6),
    4: (7, 8),
    5: (9, 10),
}

def validate_slots(
    slots: List[QuestionSlot],
    exam_type: str = "IAT",
    expected_total_marks: int = 50
) -> Tuple[bool, List[str]]:
    """
    Returns (is_valid, list_of_error_messages).
    """
    errors = []

    # Group slots by module
    modules_seen = {}
    for slot in slots:
        modules_seen.setdefault(slot.module, []).append(slot)

    # Rule 1: exactly 5 modules for semester-end papers
    if expected_total_marks >= 100 and len(modules_seen) != 5:
        errors.append(
            f"Expected 5 modules, found {len(modules_seen)}: "
            f"{sorted(modules_seen.keys())}"
        )

    # Rule 2: module numbers must be 1-5
    for mod in modules_seen:
        if mod not in ALLOWED_PAIRS:
            errors.append(f"Invalid module number: {mod}")

    # Rule 3: each module must have exactly 2 distinct qno values
    for mod, mod_slots in modules_seen.items():
        qnos = set(s.qno for s in mod_slots)
        allowed = set(ALLOWED_PAIRS.get(mod, ()))
        if qnos != allowed:
            errors.append(
                f"Module {mod}: expected question numbers {allowed}, "
                f"found {qnos}"
            )

    # Rule 4: no duplicate qno+subpart combinations
    seen_labels = {}
    for slot in slots:
        key = slot.qno_label
        if key in seen_labels:
            errors.append(f"Duplicate question label: {key}")
        seen_labels[key] = True

    # Rule 5: subpart count rules
    # Group by qno to count subparts
    qno_subparts = {}
    for slot in slots:
        qno_subparts.setdefault(slot.qno, []).append(slot.subpart)

    three_part_questions = []
    for qno, subparts in qno_subparts.items():
        actual_parts = [s for s in subparts if s is not None]
        if len(actual_parts) > 0:
            count = len(actual_parts)
            if exam_type.upper() in ("IAT", "IAT-1", "IAT-2", "INTERNAL ASSESSMENT TEST - I", "INTERNAL ASSESSMENT TEST - II"):
                if count > 2:
                    errors.append(
                        f"IAT question {qno} has {count} subparts. "
                        f"Max allowed is 2."
                    )
            else:
                if count > 3:
                    errors.append(
                        f"Question {qno} has {count} subparts. "
                        f"Max allowed is 3."
                    )
                if count == 3:
                    three_part_questions.append(qno)

    if exam_type.upper() not in ("IAT", "IAT-1", "IAT-2", "INTERNAL ASSESSMENT TEST - I", "INTERNAL ASSESSMENT TEST - II"):
        # Map question numbers in three_part_questions to their modules
        three_part_modules = {((qno - 1) // 2 + 1) for qno in three_part_questions}
        if len(three_part_modules) > 1:
            errors.append(
                f"Only one module in the entire paper can have 3-subpart questions. "
                f"Found 3-subpart questions in modules: {sorted(three_part_modules)} (questions: {three_part_questions})"
            )

    # Rule 6: marks must be positive integers
    for slot in slots:
        if not isinstance(slot.marks, int) or slot.marks <= 0:
            errors.append(
                f"Question {slot.qno_label} has invalid marks: {slot.marks}"
            )

    # Rule 7: total marks check
    # Only count one alternative per module.
    # In DSATM, there is a LEFT (odd) and RIGHT (even) choice per module.
    # Therefore, the sum of all slots in the blueprint is double the paper marks (since the student picks 1 of the 2).
    # Let's verify that the total marks of Left alternatives equals expected, and Right equals expected.
    left_total = sum(s.marks for s in slots if s.qno % 2 != 0)
    right_total = sum(s.marks for s in slots if s.qno % 2 == 0)

    if left_total != expected_total_marks or right_total != expected_total_marks:
        errors.append(
            f"Alternative marks mismatch: Left options sum to {left_total}, "
            f"Right options sum to {right_total}, expected {expected_total_marks} each."
        )

    # Rule 8: required fields
    for slot in slots:
        if not slot.text or not slot.text.strip():
            errors.append(f"Question {slot.qno_label} has empty text.")
        if not slot.co:
            errors.append(f"Question {slot.qno_label} has no CO.")
        if not slot.rbt:
            errors.append(f"Question {slot.qno_label} has no RBT level.")

    return len(errors) == 0, errors
