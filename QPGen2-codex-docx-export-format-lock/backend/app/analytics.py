from collections import Counter

def compute_paper_analytics(
    questions: list[dict],
    requested_modules: list[int],
    requested_rbt: dict[str, int],
    requested_co: dict[str, int],
) -> dict:
    """
    Compute real analytics based on the final generated questions
    rather than the planned blueprint.
    """
    total_marks = 0
    by_module = Counter({str(m): 0 for m in (requested_modules or [1, 2, 3, 4, 5])})
    by_rbt = Counter({f"L{i}": 0 for i in range(1, 7)})
    by_co = Counter({f"CO{i}": 0 for i in range(1, 7)})

    for q in questions:
        marks = int(q.get("marks", 0))
        total_marks += marks
        
        module = str(q.get("module_number", "1"))
        rbt = str(q.get("bloom_level", "L1"))
        co = str(q.get("course_outcome", "CO1")).upper()
        
        by_module[module] += marks
        by_rbt[rbt] += marks
        by_co[co] += marks

    total_marks = max(total_marks, 1)

    return {
        "question_count": len(questions),
        "by_module": dict(by_module),
        "by_rbt": dict(by_rbt),
        "by_co": dict(by_co),
        "requested": {
            "modules": requested_modules,
            "rbt": requested_rbt,
            "co": requested_co,
        },
        "percentages": {
            "co": {
                k: round((v / total_marks) * 100)
                for k, v in by_co.items()
                if k in requested_co or v > 0
            },
            "modules": {
                k: round((v / total_marks) * 100)
                for k, v in by_module.items()
                if str(k) in map(str, requested_modules) or v > 0
            },
            "rbt": {
                k: round((v / total_marks) * 100)
                for k, v in by_rbt.items()
                if k in requested_rbt or v > 0
            }
        },
    }
