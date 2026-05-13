import json
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.openai_service import generate_json_with_openai, OPENAI_MODEL


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _get_topic_context(db: Session, topic_id: int) -> Dict[str, Any]:
    row = db.execute(
        text("""
            SELECT
                ct.id AS topic_id,
                ct.topic_name,
                ct.topic_order,
                COALESCE(ct.difficulty, 'Medium') AS topic_difficulty,
                COALESCE(ct.estimated_minutes, 30) AS estimated_minutes,
                c.id AS chapter_id,
                c.chapter_name,
                s.id AS subject_id,
                s.subject_name
            FROM chapter_topics ct
            JOIN chapters c ON c.id = ct.chapter_id
            JOIN subjects s ON s.id = c.subject_id
            WHERE ct.id = :topic_id
        """),
        {"topic_id": topic_id},
    ).mappings().first()

    if not row:
        raise ValueError("Topic not found")

    return {
        "topic_id": _safe_int(row["topic_id"]),
        "topic_name": row["topic_name"],
        "topic_order": _safe_int(row["topic_order"]),
        "topic_difficulty": row["topic_difficulty"],
        "estimated_minutes": _safe_int(row["estimated_minutes"], 30),
        "chapter_id": _safe_int(row["chapter_id"]),
        "chapter_name": row["chapter_name"],
        "subject_id": _safe_int(row["subject_id"]),
        "subject_name": row["subject_name"],
    }


def _get_student_topic_history(db: Session, student_id: int, topic_id: int) -> Dict[str, Any]:
    row = db.execute(
        text("""
            SELECT
                COUNT(*) AS wrong_count,
                MAX(confidence) AS max_confidence
            FROM question_topic_analysis
            WHERE student_id = :student_id
              AND predicted_topic_id = :topic_id
        """),
        {"student_id": student_id, "topic_id": topic_id},
    ).mappings().first()

    schedule_row = db.execute(
        text("""
            SELECT COUNT(*) AS scheduled_count
            FROM daily_schedule
            WHERE student_id = :student_id
              AND topic_id = :topic_id
        """),
        {"student_id": student_id, "topic_id": topic_id},
    ).mappings().first()

    return {
        "wrong_question_count": _safe_int(row["wrong_count"]) if row else 0,
        "max_confidence": float(row["max_confidence"] or 0) if row else 0,
        "scheduled_count": _safe_int(schedule_row["scheduled_count"]) if schedule_row else 0,
    }


def _build_revision_prompt(topic: Dict[str, Any], history: Dict[str, Any]) -> str:
    return f"""
You are TrackMate AI Revision Coach.

Create a micro revision plan for a student.

Important:
- Use very simple English.
- Do not use technical system words like retention, priority score, algorithm, confidence.
- Make it useful for a real student.
- Do not make the student feel bad.
- Give practical steps.
- Return ONLY valid JSON.

Topic context:
{json.dumps(topic, indent=2)}

Student history:
{json.dumps(history, indent=2)}

Return JSON exactly:
{{
  "title": "short title",
  "why_this_topic": "1 simple sentence",
  "concept_recap": [
    "point 1",
    "point 2",
    "point 3"
  ],
  "common_mistakes": [
    "mistake 1",
    "mistake 2"
  ],
  "practice_tasks": [
    "task 1",
    "task 2",
    "task 3"
  ],
  "mini_plan": [
    {{
      "minutes": 5,
      "activity": "what to do"
    }},
    {{
      "minutes": 10,
      "activity": "what to do"
    }},
    {{
      "minutes": 15,
      "activity": "what to do"
    }}
  ],
  "retest_advice": "1 sentence"
}}
"""


def _fallback_revision_plan(topic: Dict[str, Any]) -> Dict[str, Any]:
    topic_name = topic["topic_name"]

    return {
        "title": f"Revise {topic_name}",
        "why_this_topic": f"This topic needs a short focused revision before moving ahead.",
        "concept_recap": [
            f"Read the basic idea of {topic_name}.",
            "Write one simple example in your notebook.",
            "Solve one question slowly and check each step.",
        ],
        "common_mistakes": [
            "Skipping the first step.",
            "Solving without checking the given values.",
        ],
        "practice_tasks": [
            f"Solve 3 easy questions from {topic_name}.",
            "Solve 2 medium questions without hints.",
            "Review every wrong answer and write the correct method.",
        ],
        "mini_plan": [
            {"minutes": 5, "activity": "Read the topic summary."},
            {"minutes": 10, "activity": "Practice easy examples."},
            {"minutes": 15, "activity": "Solve mixed questions and review mistakes."},
        ],
        "retest_advice": "After revision, take a short test to check improvement.",
    }


def generate_revision_plan_for_topic(
    db: Session,
    student_id: int,
    topic_id: int,
    force_new: bool = False,
) -> Dict[str, Any]:
    if not force_new:
        existing = db.execute(
            text("""
                SELECT id, plan_json, model, created_at
                FROM ai_revision_plans
                WHERE student_id = :student_id
                  AND topic_id = :topic_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"student_id": student_id, "topic_id": topic_id},
        ).mappings().first()

        if existing:
            return {
                "revision_plan_id": existing["id"],
                "topic_id": topic_id,
                "plan": existing["plan_json"],
                "model": existing["model"],
                "cached": True,
            }

    topic = _get_topic_context(db, topic_id)
    history = _get_student_topic_history(db, student_id, topic_id)

    prompt = _build_revision_prompt(topic, history)

    try:
        plan = generate_json_with_openai(prompt, temperature=0.35)
        model = OPENAI_MODEL
        ai_used = True
    except Exception:
        plan = _fallback_revision_plan(topic)
        model = "fallback"
        ai_used = False

    row = db.execute(
        text("""
            INSERT INTO ai_revision_plans (
                student_id,
                subject_id,
                chapter_id,
                topic_id,
                topic_name,
                plan_json,
                model
            )
            VALUES (
                :student_id,
                :subject_id,
                :chapter_id,
                :topic_id,
                :topic_name,
                CAST(:plan_json AS jsonb),
                :model
            )
            RETURNING id
        """),
        {
            "student_id": student_id,
            "subject_id": topic["subject_id"],
            "chapter_id": topic["chapter_id"],
            "topic_id": topic["topic_id"],
            "topic_name": topic["topic_name"],
            "plan_json": json.dumps(plan),
            "model": model,
        },
    ).mappings().first()

    db.commit()

    return {
        "revision_plan_id": row["id"],
        "topic_id": topic_id,
        "topic": topic,
        "plan": plan,
        "model": model,
        "ai_used": ai_used,
        "cached": False,
    }