import json
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.openai_service import generate_json_with_openai, OPENAI_MODEL


CONFIDENCE_THRESHOLD = 75


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return round(float(value), 2)
    except Exception:
        return default


def _get_chapter_topics(db: Session, chapter_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT
                id AS topic_id,
                topic_name,
                topic_order,
                COALESCE(difficulty, 'Medium') AS difficulty,
                COALESCE(estimated_minutes, 30) AS estimated_minutes
            FROM chapter_topics
            WHERE chapter_id = :chapter_id
              AND COALESCE(is_active, TRUE) = TRUE
            ORDER BY topic_order ASC
        """),
        {"chapter_id": chapter_id},
    ).mappings().all()

    return [
        {
            "topic_id": _safe_int(row["topic_id"]),
            "topic_name": row["topic_name"],
            "topic_order": _safe_int(row["topic_order"]),
            "difficulty": row["difficulty"],
            "estimated_minutes": _safe_int(row["estimated_minutes"], 30),
        }
        for row in rows
    ]


def _get_wrong_questions(db: Session, test_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT
                q.id AS question_id,
                q.question_text,
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_answer,
                q.difficulty,
                q.chapter_id,
                q.topic_id,
                c.chapter_name,
                ta.selected_answer
            FROM test_answers ta
            JOIN questions q ON q.id = ta.question_id
            JOIN chapters c ON c.id = q.chapter_id
            WHERE ta.test_id = :test_id
              AND ta.is_correct = FALSE
            ORDER BY q.chapter_id ASC, q.id ASC
        """),
        {"test_id": test_id},
    ).mappings().all()

    return [
        {
            "question_id": _safe_int(row["question_id"]),
            "question_text": row["question_text"],
            "option_a": row["option_a"],
            "option_b": row["option_b"],
            "option_c": row["option_c"],
            "option_d": row["option_d"],
            "correct_answer": row["correct_answer"],
            "selected_answer": row["selected_answer"],
            "difficulty": row["difficulty"],
            "chapter_id": _safe_int(row["chapter_id"]),
            "chapter_name": row["chapter_name"],
            "db_topic_id": _safe_int(row["topic_id"]) if row["topic_id"] else None,
        }
        for row in rows
    ]


def _build_topic_detection_prompt(question: Dict[str, Any], topics: List[Dict[str, Any]]) -> str:
    return f"""
You are TrackMate AI Topic Detector.

Your job:
Find which exact topic this wrong question belongs to.

Use only the topic_id values from the available topics list.

Important rules:
1. Return ONLY valid JSON.
2. Do not use markdown.
3. Do not explain outside JSON.
4. confidence must be 0 to 100.
5. If you are not sure, choose the closest topic but keep confidence below 75.
6. If confidence is 75 or more, the app will schedule that topic for revision.
7. Use simple reason that a teacher can understand.

Wrong question:
{json.dumps(question, indent=2)}

Available topics for this chapter:
{json.dumps(topics, indent=2)}

Return JSON exactly:
{{
  "predicted_topic_id": 1,
  "predicted_topic_name": "topic name",
  "confidence": 85,
  "reason": "simple reason"
}}
"""


def _fallback_topic_detection(question: Dict[str, Any], topics: List[Dict[str, Any]]) -> Dict[str, Any]:
    db_topic_id = question.get("db_topic_id")

    if db_topic_id:
        for topic in topics:
            if topic["topic_id"] == db_topic_id:
                return {
                    "predicted_topic_id": topic["topic_id"],
                    "predicted_topic_name": topic["topic_name"],
                    "confidence": 90,
                    "reason": "The question is already linked with this topic in the question bank.",
                    "llm_used": False,
                    "model": "fallback_db_topic",
                }

    if topics:
        first = topics[0]
        return {
            "predicted_topic_id": first["topic_id"],
            "predicted_topic_name": first["topic_name"],
            "confidence": 60,
            "reason": "Fallback selected the first topic because OpenAI was not available.",
            "llm_used": False,
            "model": "fallback_first_topic",
        }

    return {
        "predicted_topic_id": None,
        "predicted_topic_name": None,
        "confidence": 0,
        "reason": "No topics found for this chapter.",
        "llm_used": False,
        "model": "fallback_no_topic",
    }


def detect_topic_for_wrong_question(
    db: Session,
    question: Dict[str, Any],
) -> Dict[str, Any]:
    topics = _get_chapter_topics(db, question["chapter_id"])

    if not topics:
        return _fallback_topic_detection(question, topics)

    prompt = _build_topic_detection_prompt(question, topics)

    try:
        data = generate_json_with_openai(prompt, temperature=0.15)

        topic_id = _safe_int(data.get("predicted_topic_id"))
        confidence = _safe_float(data.get("confidence"))

        valid_topics = {topic["topic_id"]: topic for topic in topics}

        if topic_id not in valid_topics:
            return _fallback_topic_detection(question, topics)

        topic = valid_topics[topic_id]

        return {
            "predicted_topic_id": topic_id,
            "predicted_topic_name": data.get("predicted_topic_name") or topic["topic_name"],
            "confidence": confidence,
            "reason": data.get("reason") or "OpenAI matched this question with the topic.",
            "llm_used": True,
            "model": OPENAI_MODEL,
        }

    except Exception as e:
        fallback = _fallback_topic_detection(question, topics)
        fallback["reason"] = f"{fallback['reason']} OpenAI fallback reason: {str(e)}"
        return fallback


def save_topic_analysis(
    db: Session,
    student_id: int,
    test_id: int,
    question: Dict[str, Any],
    result: Dict[str, Any],
):
    db.execute(
        text("""
            INSERT INTO question_topic_analysis (
                student_id,
                test_id,
                question_id,
                chapter_id,
                predicted_topic_id,
                predicted_topic_name,
                confidence,
                llm_reason
            )
            VALUES (
                :student_id,
                :test_id,
                :question_id,
                :chapter_id,
                :predicted_topic_id,
                :predicted_topic_name,
                :confidence,
                :llm_reason
            )
        """),
        {
            "student_id": student_id,
            "test_id": test_id,
            "question_id": question["question_id"],
            "chapter_id": question["chapter_id"],
            "predicted_topic_id": result.get("predicted_topic_id"),
            "predicted_topic_name": result.get("predicted_topic_name"),
            "confidence": result.get("confidence", 0),
            "llm_reason": result.get("reason"),
        },
    )


def analyze_wrong_questions_for_test(
    db: Session,
    student_id: int,
    test_id: int,
) -> Dict[str, Any]:
    wrong_questions = _get_wrong_questions(db, test_id)

    if not wrong_questions:
        return {
            "analyzed": True,
            "wrong_question_count": 0,
            "saved_topic_count": 0,
            "topics": [],
            "message": "No wrong answers. No topic detection needed.",
        }

    detected_topics = []
    saved_count = 0

    for question in wrong_questions:
        result = detect_topic_for_wrong_question(db, question)

        detected_topics.append(
            {
                "question_id": question["question_id"],
                "chapter_id": question["chapter_id"],
                "chapter_name": question["chapter_name"],
                "predicted_topic_id": result.get("predicted_topic_id"),
                "predicted_topic_name": result.get("predicted_topic_name"),
                "confidence": result.get("confidence", 0),
                "reason": result.get("reason"),
                "llm_used": result.get("llm_used", False),
            }
        )

        if result.get("predicted_topic_id") and _safe_float(result.get("confidence")) >= CONFIDENCE_THRESHOLD:
            save_topic_analysis(
                db=db,
                student_id=student_id,
                test_id=test_id,
                question=question,
                result=result,
            )
            saved_count += 1

    db.flush()

    return {
        "analyzed": True,
        "wrong_question_count": len(wrong_questions),
        "saved_topic_count": saved_count,
        "topics": detected_topics,
        "message": "OpenAI analyzed wrong answers and detected weak topics.",
    }