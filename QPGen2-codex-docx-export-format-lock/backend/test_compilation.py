import os
import sys
from pathlib import Path

# Add backend folder to path
backend_path = Path(__file__).resolve().parent
sys.path.append(str(backend_path))

from app.academic.planning.blueprint_engine import build_paper_blueprint
from app.generator import rebuild_blueprint_from_questions, DSATMQuestionPaperGenerator, PaperConfig

def test_ia_compilation():
    print("Testing 50-mark IA paper blueprint and dynamic rendering...")
    
    # 1. Build blueprint
    bp = build_paper_blueprint(
        max_marks=50,
        modules=[1, 2, 3, 4, 5],
    )
    assert bp.total_marks == 50
    assert len(bp.slots) == 10
    print("50-mark Blueprint constructed successfully.")

    # 2. Build dummy questions list matching blueprint
    questions = []
    subpart_chars = ["a", "b", "c"]
    for slot in bp.slots:
        if slot.type == "single":
            questions.append({
                "text": f"Explain the core concept of Module {slot.module} in detail.",
                "marks": 10,
                "course_outcome": slot.co,
                "bloom_level": slot.rbt,
                "module_number": slot.module,
                "question_number": slot.qno,
                "subpart": "",
                "section_label": str(slot.qno),
            })
        else:
            # Multi-part question for IAT (max 2 parts, 5+5 marks)
            marks_split = [5, 5]
            for idx, m in enumerate(marks_split):
                questions.append({
                    "text": f"State and explain sub-task {subpart_chars[idx]} of question {slot.qno}.",
                    "marks": m,
                    "course_outcome": slot.co,
                    "bloom_level": slot.rbt,
                    "module_number": slot.module,
                    "question_number": slot.qno,
                    "subpart": subpart_chars[idx],
                    "section_label": f"{slot.qno}({subpart_chars[idx]})",
                })

    # 3. Rebuild blueprint from questions
    rebuild_bp = rebuild_blueprint_from_questions(50, questions)
    assert len(rebuild_bp.slots) == 10
    print("✓ Blueprint reconstructed from dictionary successfully.")

    # 4. Generate Document
    config = PaperConfig(
        department="Computer Science & Engineering",
        subject="AI & Machine Learning",
        subject_code="21CS61",
        semester="VI",
        max_marks=50,
        duration="90 Minutes",
        date="26-05-2026",
        batch="2023-2027",
        teaching_department="CSE",
        exam_type="Internal Assessment Test - I",
        modules=[1, 2, 3, 4, 5],
        rbt_levels=["L1", "L2", "L3"],
        co_targets=["CO1", "CO2", "CO3", "CO4", "CO5"],
    )

    generator = DSATMQuestionPaperGenerator()
    doc = generator.generate(config, rebuild_bp)
    
    output_file = Path("test_ia_output.docx")
    generator.save(doc, output_file)
    assert output_file.exists()
    print("✓ Dynamic DOCX generated and saved successfully.")
    
    # Clean up
    if output_file.exists():
        os.remove(output_file)

def test_endsem_compilation():
    print("\nTesting 100-mark EndSem paper blueprint and dynamic rendering...")
    
    # 1. Build blueprint
    bp = build_paper_blueprint(
        max_marks=100,
        modules=[1, 2, 3, 4, 5],
    )
    assert bp.total_marks == 100
    assert len(bp.slots) == 10  # 2 questions per module (internal choice)
    print("✓ 100-mark Blueprint constructed successfully.")

    # 2. Build dummy questions list matching blueprint
    questions = []
    subpart_chars = ["a", "b", "c"]
    for slot in bp.slots:
        if slot.type == "single":
            questions.append({
                "text": f"Discuss the implementation details for slot {slot.qno}.",
                "marks": 20,
                "course_outcome": slot.co,
                "bloom_level": slot.rbt,
                "module_number": slot.module,
                "question_number": slot.qno,
                "subpart": "",
                "section_label": str(slot.qno),
            })
        else:
            # Multi-part question
            marks_split = [8, 8, 4] if slot.type == "three_part" else [10, 10]
            for idx, m in enumerate(marks_split):
                questions.append({
                    "text": f"State and explain sub-task {subpart_chars[idx]} of question {slot.qno}.",
                    "marks": m,
                    "course_outcome": slot.co,
                    "bloom_level": slot.rbt,
                    "module_number": slot.module,
                    "question_number": slot.qno,
                    "subpart": subpart_chars[idx],
                    "section_label": f"{slot.qno}({subpart_chars[idx]})",
                })

    # 3. Rebuild blueprint from questions
    rebuild_bp = rebuild_blueprint_from_questions(100, questions)
    assert len(rebuild_bp.slots) == 10
    print("✓ Blueprint reconstructed from dictionary successfully.")

    # 4. Generate Document
    config = PaperConfig(
        department="Computer Science & Engineering",
        subject="AI & Machine Learning",
        subject_code="21CS61",
        semester="VI",
        max_marks=100,
        duration="180 Minutes",
        date="26-05-2026",
        batch="2023-2027",
        teaching_department="CSE",
        exam_type="Semester End Examination",
        modules=[1, 2, 3, 4, 5],
        rbt_levels=["L1", "L2", "L3"],
        co_targets=["CO1", "CO2", "CO3", "CO4", "CO5"],
    )

    generator = DSATMQuestionPaperGenerator()
    doc = generator.generate(config, rebuild_bp)
    
    output_file = Path("test_endsem_output.docx")
    generator.save(doc, output_file)
    assert output_file.exists()
    print("✓ Dynamic EndSem DOCX generated and saved successfully.")
    
    # Clean up
    if output_file.exists():
        os.remove(output_file)

if __name__ == "__main__":
    try:
        test_ia_compilation()
        test_endsem_compilation()
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
