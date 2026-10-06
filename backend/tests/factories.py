"""測試用的資料產生器。"""

from app.modules.ingest.schemas import ImportBundle


def make_bundle(source_key: str = "test-paper-1", questions: int = 3, **paper_overrides) -> ImportBundle:
    paper = {
        "source_key": source_key,
        "origin": "official",
        "exam_type": "普考",
        "year": 115,
        "subject": "測試科目",
        "categories": ["一般行政"],
        **paper_overrides,
    }
    return ImportBundle.model_validate(
        {
            "paper": paper,
            "expected_question_count": questions,
            "questions": [
                {
                    "number": n,
                    "stem": f"第 {n} 題題幹",
                    "options": ["甲", "乙", "丙", "丁"],
                    "answer": ["A"],
                    "answer_source": "ANS",
                    "points": 2,
                }
                for n in range(1, questions + 1)
            ],
        }
    )
