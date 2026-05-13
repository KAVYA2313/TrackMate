import json
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.openai_service import generate_text_with_openai, OPENAI_MODEL


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _student_context(db: Session, student_id: int) -> Dict[str, Any]:
    student = db.execute(
        text("""
            SELECT id, name, email, COALESCE(study_hours_per_day, 1.5) AS study_hours_per_day
            FROM students
            WHERE id = :student_id
        """),
        {"student_id": student_id},
    ).mappings().first()

    weak_rows = db.execute(
        text("""
            SELECT
                chapter_id,
                chapter_name,
                retention,
                priority_score,
                last_score,
                weak_chapter
            FROM retention_states
            WHERE student_id = :student_id
            ORDER BY priority_score DESC NULLS LAST
            LIMIT 5
        """),
        {"student_id": student_id},
    ).mappings().all()

    today_rows = db.execute(
        text("""
            SELECT
                ds.schedule_date,
                ds.section,
                ds.task_type,
                ds.schedule_title,
                ds.planned_minutes,
                ds.status,
                ct.topic_name,
                c.chapter_name
            FROM daily_schedule ds
            LEFT JOIN chapter_topics ct ON ct.id = ds.topic_id
            LEFT JOIN chapters c ON c.id = ds.chapter_id
            WHERE ds.student_id = :student_id
              AND ds.schedule_date = CURRENT_DATE
            ORDER BY ds.start_time ASC NULLS LAST, ds.id ASC
        """),
        {"student_id": student_id},
    ).mappings().all()

    recent_tests = db.execute(
        text("""
            SELECT
                id,
                obtained_marks,
                total_marks,
                percentage,
                submitted_at
            FROM tests
            WHERE student_id = :student_id
              AND status = 'SUBMITTED'
            ORDER BY submitted_at DESC NULLS LAST
            LIMIT 5
        """),
        {"student_id": student_id},
    ).mappings().all()

    return {
        "student": dict(student) if student else {"id": student_id, "name": "Student"},
        "important_chapters": [dict(row) for row in weak_rows],
        "today_schedule": [dict(row) for row in today_rows],
        "recent_tests": [dict(row) for row in recent_tests],
    }


def _recent_chat_history(db: Session, student_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT user_message, ai_answer, created_at
            FROM ai_coach_messages
            WHERE student_id = :student_id
            ORDER BY created_at DESC
            LIMIT 6
        """),
        {"student_id": student_id},
    ).mappings().all()

    return [dict(row) for row in reversed(rows)]


def _build_coach_prompt(context: Dict[str, Any], history: List[Dict[str, Any]], user_message: str) -> str:
    return f"""
You are TrackMate AI Study Coach.

You help a student understand what to study, why it matters, and how to improve.

Rules:
- Use simple friendly English.
- Do not use heavy technical words like retention, priority score, memory decay, algorithm.
- Do not shame the student.
- Be practical.
- If the student asks what to study, use today's schedule first.
- If the student has a weak chapter, suggest revision before new study.
- If the student has only 30 minutes, give a small plan.
- Keep answer under 130 words.
- Give clear steps.

Student context:
{json.dumps(context, indent=2, default=str)}

Recent coach chat:
{json.dumps(history, indent=2, default=str)}

Student question:
{user_message}

Answer now:
"""


def ask_ai_coach(db: Session, student_id: int, user_message: str) -> Dict[str, Any]:
    user_message = str(user_message or "").strip()

    if not user_message:
        return {
            "answer": "Please ask me what you want to study or improve today.",
            "model": "fallback",
            "ai_used": False,
        }

    context = _student_context(db, student_id)
    history = _recent_chat_history(db, student_id)
    prompt = _build_coach_prompt(context, history, user_message)

    try:
        answer = generate_text_with_openai(prompt, temperature=0.45)
        model = OPENAI_MODEL
        ai_used = True
    except Exception:
        answer = (
            "Start with today's scheduled topic. If a chapter feels difficult, "
            "revise it for 20 minutes and then solve a short practice test."
        )
        model = "fallback"
        ai_used = False

    db.execute(
        text("""
            INSERT INTO ai_coach_messages (
                student_id,
                user_message,
                ai_answer,
                model
            )
            VALUES (
                :student_id,
                :user_message,
                :ai_answer,
                :model
            )
        """),
        {
            "student_id": student_id,
            "user_message": user_message,
            "ai_answer": answer,
            "model": model,
        },
    )

    db.commit()

    return {
        "answer": answer,
        "model": model,
        "ai_used": ai_used,
    }