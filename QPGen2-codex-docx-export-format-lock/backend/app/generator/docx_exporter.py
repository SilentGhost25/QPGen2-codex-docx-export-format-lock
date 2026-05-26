from docx import Document
from docx.shared import Inches
from typing import List, Any
import io
from pathlib import Path

from .header_builder import build_header
from .question_body_builder import build_question_body, QuestionSlot
from .footer_builder import build_footer
from .validator import validate_slots
from ..academic.planning.blueprint_engine import PaperBlueprint, ModuleBlock, QuestionBlock, SubQuestion
from collections import defaultdict


def rebuild_slots_from_blueprint(blueprint: PaperBlueprint) -> List[QuestionSlot]:
    slots = []
    for mod in blueprint.modules:
        # Render left question (primary)
        left = mod.left_question
        for idx, sub in enumerate(left.subquestions):
            slots.append(
                QuestionSlot(
                    qno=left.qno,
                    module=mod.module_no,
                    marks=sub.marks,
                    co=sub.co,
                    rbt=sub.rbt,
                    text=sub.text,
                    subpart=sub.label,
                    image_path=sub.image_path,
                    is_or_boundary=False,
                )
            )
            
        # Render right question (alternative) if exists
        if mod.right_question:
            right = mod.right_question
            for idx, sub in enumerate(right.subquestions):
                slots.append(
                    QuestionSlot(
                        qno=right.qno,
                        module=mod.module_no,
                        marks=sub.marks,
                        co=sub.co,
                        rbt=sub.rbt,
                        text=sub.text,
                        subpart=sub.label,
                        image_path=sub.image_path,
                        is_or_boundary=(idx == 0),  # OR separator goes before the first subquestion of right block
                    )
                )
    return slots


def rebuild_slots_from_questions(questions: List[dict[str, Any]], max_marks: int | None = None) -> List[QuestionSlot]:
    if max_marks is None:
        # Deduce max_marks by summing marks of unique odd question numbers
        seen_odds = set()
        total = 0
        for q in questions:
            qno = q.get("question_number") or 1
            if qno % 2 != 0 and qno not in seen_odds:
                seen_odds.add(qno)
                total += int(q.get("marks") or 10)
        max_marks = total if total > 0 else 50
        
    blueprint = rebuild_blueprint_from_questions(max_marks, questions)
    return rebuild_slots_from_blueprint(blueprint)


def blueprint_to_questions_list(blueprint: PaperBlueprint) -> List[dict[str, Any]]:
    questions_list = []
    for mod in blueprint.modules:
        # Left
        for sub in mod.left_question.subquestions:
            questions_list.append({
                "question_number": mod.left_question.qno,
                "subpart": sub.label or "",
                "marks": sub.marks,
                "course_outcome": sub.co,
                "bloom_level": sub.rbt,
                "text": sub.text,
                "figure_image_paths": sub.figure_image_paths or ([sub.image_path] if sub.image_path else []),
                "module_number": mod.module_no,
            })
        # Right
        if mod.right_question:
            for sub in mod.right_question.subquestions:
                questions_list.append({
                    "question_number": mod.right_question.qno,
                    "subpart": sub.label or "",
                    "marks": sub.marks,
                    "course_outcome": sub.co,
                    "bloom_level": sub.rbt,
                    "text": sub.text,
                    "figure_image_paths": sub.figure_image_paths or ([sub.image_path] if sub.image_path else []),
                    "module_number": mod.module_no,
                })
    return questions_list


def rebuild_blueprint_from_questions(max_marks: int, questions: List[dict[str, Any]]) -> PaperBlueprint:
    # Group questions by question_number (slot QNo)
    slots_map = defaultdict(list)
    for q in questions:
        qno = q.get("question_number") or 1
        slots_map[qno].append(q)
        
    question_blocks = {}
    for qno in sorted(slots_map.keys()):
        parts = slots_map[qno]
        first = parts[0]
        co = first.get("course_outcome") or "CO1"
        rbt = first.get("bloom_level") or "L2"
        marks_total = sum(int(p.get("marks") or 10) for p in parts)
        
        subquestions = []
        subpart_chars = ["a", "b", "c", "d"]
        
        # If there's only 1 part and it has no subpart, it's a single question.
        # Otherwise it's a subquestion tree.
        if len(parts) > 1 or (len(parts) == 1 and parts[0].get("subpart")):
            for idx, p in enumerate(parts):
                image_path = None
                img_paths = p.get("figure_image_paths") or []
                if img_paths:
                    image_path = img_paths[0]
                
                subquestions.append(
                    SubQuestion(
                        label=p.get("subpart") or subpart_chars[idx],
                        text=p.get("text") or "",
                        marks=int(p.get("marks") or 5),
                        co=p.get("course_outcome") or co,
                        rbt=p.get("bloom_level") or rbt,
                        image_path=image_path,
                        figure_image_paths=img_paths,
                    )
                )
        else:
            img_paths = first.get("figure_image_paths") or []
            image_path = img_paths[0] if img_paths else None
            subquestions.append(
                SubQuestion(
                    label=None,
                    text=first.get("text") or "",
                    marks=marks_total,
                    co=co,
                    rbt=rbt,
                    image_path=image_path,
                    figure_image_paths=img_paths,
                )
            )
            
        is_or_pair = (qno % 2 == 0)
        
        question_blocks[qno] = QuestionBlock(
            qno=qno,
            is_or_pair=is_or_pair,
            subquestions=subquestions,
            marks_total=marks_total,
        )
        
    # Group QuestionBlocks into ModuleBlocks
    modules_map = defaultdict(list)
    for qno, block in sorted(question_blocks.items()):
        module_no = (qno - 1) // 2 + 1
        modules_map[module_no].append(block)
        
    module_blocks = []
    for module_no in sorted(modules_map.keys()):
        blocks = modules_map[module_no]
        left_question = blocks[0]
        right_question = blocks[1] if len(blocks) > 1 else None
        module_blocks.append(
            ModuleBlock(
                module_no=module_no,
                left_question=left_question,
                right_question=right_question,
            )
        )
        
    return PaperBlueprint(
        paper_type="semester-end" if max_marks >= 100 else "internal-assessment",
        total_marks=max_marks,
        duration=180 if max_marks >= 100 else 90,
        modules=module_blocks,
    )


def build_paper(
    meta: dict,
    slots: List[QuestionSlot],
    course_outcomes: dict,
    exam_type: str = "IAT",
    expected_total_marks: int = 50,
    output_path: str = None
) -> bytes:
    """
    Full pipeline:
      1. Validate slots
      2. Create blank document
      3. Build header
      4. Build question table dynamically
      5. Build footer
      6. Return as bytes (and optionally save to output_path)
    """
    # Step 1: Validate
    is_valid, errors = validate_slots(slots, exam_type, expected_total_marks)
    if not is_valid:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "Question paper validation had warnings/errors:\n" +
            "\n".join(f"  - {e}" for e in errors)
        )

    # Step 2: Blank document — never load an old template
    document = Document()

    # Set margins
    for section in document.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.7)
        section.right_margin = Inches(0.7)

    # Step 3: Header
    build_header(document, meta)

    # Step 4: Question body (dynamic, no fixed rows)
    build_question_body(document, slots)

    # Step 5: Footer
    if course_outcomes:
        build_footer(document, course_outcomes)

    # Step 6: Save
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    content = buffer.read()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(content)

    return content


class DSATMQuestionPaperGenerator:
    def generate(self, config: Any, questions: List[dict[str, Any]] | PaperBlueprint) -> Document:
        if isinstance(questions, PaperBlueprint):
            blueprint = questions
        else:
            blueprint = rebuild_blueprint_from_questions(config.max_marks, questions)

        slots = rebuild_slots_from_blueprint(blueprint)
        
        meta = {
            "left_logo_path": str(Path(__file__).parent.parent / "assets" / "dsatm-seal.png"),
            "right_logo_path": str(Path(__file__).parent.parent / "assets" / "iqac-seal.png"),
            "institute_name": config.college_name,
            "autonomous": config.affiliation,
            "affiliated": "Affiliated to VTU",
            "approved": "Approved by AICTE",
            "accredited": "Accredited by NAAC with A+ Grade",
            "nba": "6 Programs Accredited by NBA",
            "nba_programs": "(CSE, ISE, ECE, EEE, MECH, CV)",
            "usn": "",
            "department": f"Department of {config.department}",
            "exam_title": config.exam_type,
            "subject": config.subject,
            "subject_code": config.subject_code,
            "semester": config.semester,
            "max_marks": str(config.max_marks),
            "batch": config.batch,
            "duration": config.duration,
            "date": config.date,
            "teaching_department": config.teaching_department,
            "instruction": config.instructions,
        }

        # Validate and construct paper
        build_paper(
            meta=meta,
            slots=slots,
            course_outcomes=config.co_descriptions,
            exam_type=config.exam_type,
            expected_total_marks=config.max_marks
        )
        
        # Build the document object for returning (DSATMQuestionPaperGenerator generate returns a Document)
        document = Document()
        for section in document.sections:
            section.top_margin = Inches(0.6)
            section.bottom_margin = Inches(0.6)
            section.left_margin = Inches(0.7)
            section.right_margin = Inches(0.7)
            
        build_header(document, meta)
        build_question_body(document, slots)
        if config.co_descriptions:
            build_footer(document, config.co_descriptions)
            
        return document

    def save(self, document: Document, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(output_path))
        return output_path


def generate_question_paper(config: Any, questions: List[dict[str, Any]] | PaperBlueprint, output_dir: Path) -> Path:
    generator = DSATMQuestionPaperGenerator()
    document = generator.generate(config, questions)
    filename = (
        f"QP_{config.subject_code}_{config.exam_type}_{config.date.replace('-', '')}.docx"
    )
    return generator.save(document, output_dir / filename)
