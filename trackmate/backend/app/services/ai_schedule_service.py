import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.services.openai_service import generate_ai_schedule_json, OPENAI_MODEL


DEFAULT_START_TIME = "18:00"
MIN_DAILY_MINUTES = 30
MIN_TASK_MINUTES = 20
MAX_TASK_MINUTES = 60
DEFAULT_TASK_MINUTES = 30


# ==========================================================
# Basic helpers
# ==========================================================

def _today() -> date:
    return date.today()


def _now():
    return datetime.now(timezone.utc)


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


def _weekday(d: date) -> str:
    return d.strftime("%A")


def _parse_time(value: str) -> time:
    try:
        hour, minute = str(value).split(":")
        return time(int(hour), int(minute))
    except Exception:
        return time(18, 0)


def _add_minutes(base: time, minutes: int) -> time:
    dummy = datetime.combine(date.today(), base)
    dummy = dummy + timedelta(minutes=minutes)
    return dummy.time()


def _time_to_str(value) -> Optional[str]:
    if not value:
        return None
    return str(value)[:5]


def _date_label(d: date) -> str:
    today = _today()

    if d == today - timedelta(days=1):
        return "Yesterday"

    if d == today:
        return "Today"

    if d == today + timedelta(days=1):
        return "Tomorrow"

    return "Plan"


def _normalize_status(value: str) -> str:
    value = str(value or "SCHEDULED").upper()

    if value not in {"SCHEDULED", "COMPLETED", "MISSED"}:
        return "SCHEDULED"

    return value


def _parse_date_from_any(value: Any) -> Optional[date]:
    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


# ==========================================================
# Exam countdown logic
# ==========================================================

def _update_exam_day_left(db: Session, student) -> Dict[str, Any]:
    """
    Uses existing student table column: exam_days_left.
    Adds daily countdown using exam_day_last_updated.

    Example:
    Today: 200
    Tomorrow: 199
    Next day: 198
    """

    today = _today()

    try:
        row = db.execute(
            text("""
                SELECT
                    exam_days_left,
                    exam_day_last_updated
                FROM students
                WHERE id = :student_id
            """),
            {"student_id": student.id},
        ).mappings().first()
    except Exception as e:
        db.rollback()
        return {
            "exam_day_left": 0,
            "exam_days_left": 0,
            "exam_day_last_updated": str(today),
            "days_passed": 0,
            "message": "Exam countdown columns missing. Run SQL migration.",
            "error": str(e),
        }

    if not row:
        return {
            "exam_day_left": 0,
            "exam_days_left": 0,
            "exam_day_last_updated": str(today),
            "days_passed": 0,
            "message": "Student not found",
        }

    exam_days_left = _safe_int(row["exam_days_left"], 0)
    last_updated = _parse_date_from_any(row["exam_day_last_updated"])

    if last_updated is None:
        last_updated = today

        db.execute(
            text("""
                UPDATE students
                SET exam_day_last_updated = :today
                WHERE id = :student_id
            """),
            {
                "today": today,
                "student_id": student.id,
            },
        )

        db.commit()

    days_passed = max((today - last_updated).days, 0)

    if days_passed > 0:
        exam_days_left = max(0, exam_days_left - days_passed)

        db.execute(
            text("""
                UPDATE students
                SET exam_days_left = :exam_days_left,
                    exam_day_last_updated = :today
                WHERE id = :student_id
            """),
            {
                "exam_days_left": exam_days_left,
                "today": today,
                "student_id": student.id,
            },
        )

        db.commit()

    return {
        "exam_day_left": exam_days_left,
        "exam_days_left": exam_days_left,
        "exam_day_last_updated": str(today),
        "days_passed": days_passed,
        "message": "Exam countdown updated",
    }


# ==========================================================
# Student time / budget logic
# ==========================================================

def _student_study_hours(student) -> float:
    return _safe_float(getattr(student, "study_hours_per_day", 1.5), 1.5)


def _student_total_minutes(student) -> int:
    study_hours = _student_study_hours(student)
    total = int(study_hours * 60)
    return max(MIN_DAILY_MINUTES, total)


def _has_test_history(retention_states: List[Dict[str, Any]], recent_tests: List[Dict[str, Any]]) -> bool:
    return bool(retention_states or recent_tests)


def _has_revision_need(
    retention_states: List[Dict[str, Any]],
    wrong_topics: List[Dict[str, Any]],
    pending_missed_tasks: List[Dict[str, Any]],
) -> bool:
    if wrong_topics:
        return True

    for task in pending_missed_tasks:
        if str(task.get("status", "")).upper() == "MISSED":
            return True

    for state in retention_states:
        if (
            bool(state.get("weak_chapter"))
            or _safe_float(state.get("retention")) < 45
            or _safe_float(state.get("last_score")) < 50
            or _safe_float(state.get("priority_score")) >= 70
        ):
            return True

    return False


def _make_time_budget(
    student,
    retention_states: List[Dict[str, Any]],
    recent_tests: List[Dict[str, Any]],
    wrong_topics: List[Dict[str, Any]],
    pending_missed_tasks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Main rule requested by user:

    student.study_hours_per_day = 6
    total_minutes = 360

    If no exam/test history:
      Study = 70% of total
      Revision = 0
      Buffer = 30%

    If exam/test exists and weak/revision need exists:
      Study = 70%
      Revision = 30%

    If exam/test exists but no revision need:
      Mostly study and keep remaining as buffer.
    """

    total_minutes = _student_total_minutes(student)
    has_history = _has_test_history(retention_states, recent_tests)
    revision_needed = _has_revision_need(retention_states, wrong_topics, pending_missed_tasks)

    study_minutes = int(total_minutes * 0.70)
    revision_minutes = total_minutes - study_minutes

    if not has_history:
        return {
            "total_minutes": total_minutes,
            "study_minutes": total_minutes,
            "revision_minutes": 0,
            "buffer_minutes": 0,
            "mode": "NEW_STUDENT_FULL_STUDY",
            "rule": (
                "Student has no test history. There is no revision task yet, "
                "so use the full available day for study only."
            ),
        }

    if not revision_needed:
        return {
            "total_minutes": total_minutes,
            "study_minutes": total_minutes,
            "revision_minutes": 0,
            "buffer_minutes": 0,
            "mode": "FULL_STUDY_NO_REVISION",
            "rule": (
                "Student has no urgent revision task for this plan. "
                "Use the full available day for study only."
            ),
        }

    return {
        "total_minutes": total_minutes,
        "study_minutes": study_minutes,
        "revision_minutes": revision_minutes,
        "buffer_minutes": 0,
        "mode": "STUDY_REVISION_70_30",
        "rule": (
            "Student has weak/missed/revision need. Use full time with 70% study and 30% revision."
        ),
    }



# ==========================================================
# Revision time allocation using priority_score
# ==========================================================

def _calculate_and_save_revision_time_allocation(
    db: Session,
    student_id: int,
    total_revision_minutes: int,
) -> List[Dict[str, Any]]:
    """
    Divides the 30% revision time using retention_states.priority_score.

    Example:
    Student has 6 hours = 360 minutes.
    Revision time = 30% = 108 minutes.

    Weak chapters:
    Chapter A priority = 143
    Chapter B priority = 147
    Chapter C priority = 56

    Total priority = 346

    A time = 143 / 346 * 108 = 44.63 => 45 minutes
    B time = 147 / 346 * 108 = 45.88 => 46 minutes
    C time = 56  / 346 * 108 = 17.48 => 17 minutes

    These values are saved into retention_states.time_for_revision.
    The AI schedule prompt then uses time_for_revision for REVISION tasks.
    """

    total_revision_minutes = _safe_int(total_revision_minutes, 0)

    # Reset old allocation first so non-revision chapters do not keep stale minutes.
    db.execute(
        text("""
            UPDATE retention_states
            SET time_for_revision = 0,
                revision_time_percentage = 0,
                revision_time_updated_at = NOW()
            WHERE student_id = :student_id
        """),
        {"student_id": student_id},
    )

    if total_revision_minutes <= 0:
        db.commit()
        return []

    rows = db.execute(
        text("""
            SELECT
                id,
                student_id,
                subject_id,
                chapter_id,
                chapter_name,
                COALESCE(retention, 0) AS retention,
                COALESCE(last_score, 0) AS last_score,
                COALESCE(priority_score, 0) AS priority_score,
                COALESCE(weak_chapter, FALSE) AS weak_chapter,
                COALESCE(difficulty, 'Medium') AS difficulty
            FROM retention_states
            WHERE student_id = :student_id
              AND (
                    COALESCE(weak_chapter, FALSE) = TRUE
                    OR COALESCE(last_score, 100) < 50
                    OR COALESCE(retention, 100) < 45
                    OR COALESCE(priority_score, 0) >= 70
              )
            ORDER BY COALESCE(priority_score, 0) DESC,
                     COALESCE(retention, 100) ASC,
                     COALESCE(last_score, 100) ASC
        """),
        {"student_id": student_id},
    ).mappings().all()

    if not rows:
        db.commit()
        return []

    # Avoid creating too many very small revision blocks.
    max_revision_slots = max(1, total_revision_minutes // MIN_TASK_MINUTES)
    selected_rows = list(rows)[:max_revision_slots]

    # If a priority score is zero, give it a small positive weight.
    weighted_rows = []
    for row in selected_rows:
        priority = max(_safe_float(row["priority_score"], 0.0), 0.0)
        if priority <= 0:
            priority = 1.0
        weighted_rows.append({"row": row, "priority": priority})

    total_priority = sum(item["priority"] for item in weighted_rows)
    if total_priority <= 0:
        total_priority = float(len(weighted_rows))

    allocations = []
    for item in weighted_rows:
        row = item["row"]
        priority = item["priority"]
        percentage = (priority / total_priority) * 100
        raw_minutes = (priority / total_priority) * total_revision_minutes

        allocations.append(
            {
                "row": row,
                "priority": priority,
                "percentage": percentage,
                "raw_minutes": raw_minutes,
                "minutes": int(round(raw_minutes)),
            }
        )

    # Give each selected revision chapter at least MIN_TASK_MINUTES if possible.
    if len(allocations) * MIN_TASK_MINUTES <= total_revision_minutes:
        for item in allocations:
            item["minutes"] = max(MIN_TASK_MINUTES, item["minutes"])

    # Fix rounding so total allocated minutes equals total_revision_minutes.
    current_total = sum(item["minutes"] for item in allocations)
    diff = total_revision_minutes - current_total

    if diff > 0:
        allocations.sort(key=lambda x: x["priority"], reverse=True)
        index = 0
        while diff > 0 and allocations:
            allocations[index % len(allocations)]["minutes"] += 1
            diff -= 1
            index += 1

    elif diff < 0:
        allocations.sort(key=lambda x: x["priority"])
        index = 0
        safety = 0
        while diff < 0 and allocations and safety < 10000:
            item = allocations[index % len(allocations)]
            minimum_allowed = MIN_TASK_MINUTES if len(allocations) * MIN_TASK_MINUTES <= total_revision_minutes else 0

            if item["minutes"] > minimum_allowed:
                item["minutes"] -= 1
                diff += 1

            index += 1
            safety += 1

    result = []

    for item in allocations:
        row = item["row"]
        minutes = max(0, int(item["minutes"]))
        percentage = round(float(item["percentage"]), 2)

        db.execute(
            text("""
                UPDATE retention_states
                SET time_for_revision = :time_for_revision,
                    revision_time_percentage = :revision_time_percentage,
                    revision_time_updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": row["id"],
                "time_for_revision": minutes,
                "revision_time_percentage": percentage,
            },
        )

        result.append(
            {
                "retention_state_id": row["id"],
                "subject_id": row["subject_id"],
                "chapter_id": row["chapter_id"],
                "chapter_name": row["chapter_name"],
                "priority_score": round(_safe_float(row["priority_score"]), 2),
                "revision_time_percentage": percentage,
                "time_for_revision": minutes,
                "reason": (
                    "Revision time calculated from this chapter priority compared "
                    "with total revision priority."
                ),
            }
        )

    db.commit()
    return result


# ==========================================================
# Data fetchers
# ==========================================================

def _student_context(student, time_budget: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    study_hours = _student_study_hours(student)
    total_minutes = _student_total_minutes(student)

    return {
        "student_id": student.id,
        "student_name": (
            getattr(student, "name", None)
            or getattr(student, "student_name", None)
            or "Student"
        ),
        "study_hours_per_day": study_hours,
        "daily_total_minutes": total_minutes,
        "daily_maths_minutes": total_minutes,
        "time_budget": time_budget or {},
        "important_rule": (
            "Use the full study_hours_per_day from students table. "
            "If student enters 6 hours, total daily schedule budget is 360 minutes. "
            "Do not cap the plan at 90 minutes."
        ),
    }


def _fetch_topics(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT
                ct.id AS topic_id,
                ct.topic_name,
                ct.topic_order,
                COALESCE(ct.estimated_minutes, 30) AS estimated_minutes,
                COALESCE(ct.difficulty, 'Medium') AS difficulty,
                c.id AS chapter_id,
                c.chapter_name,
                c.chapter_order,
                s.id AS subject_id,
                s.subject_name
            FROM chapter_topics ct
            JOIN chapters c ON c.id = ct.chapter_id
            JOIN subjects s ON s.id = c.subject_id
            WHERE COALESCE(ct.is_active, TRUE) = TRUE
            ORDER BY c.chapter_order ASC, ct.topic_order ASC
        """)
    ).mappings().all()

    return [
        {
            "topic_id": _safe_int(row["topic_id"]),
            "topic_name": row["topic_name"],
            "topic_order": _safe_int(row["topic_order"]),
            "estimated_minutes": _safe_int(row["estimated_minutes"], 30),
            "difficulty": row["difficulty"] or "Medium",
            "chapter_id": _safe_int(row["chapter_id"]),
            "chapter_name": row["chapter_name"],
            "chapter_order": _safe_int(row["chapter_order"]),
            "subject_id": _safe_int(row["subject_id"]),
            "subject_name": row["subject_name"],
        }
        for row in rows
    ]


def _fetch_completed_topic_ids(db: Session, student_id: int) -> Set[int]:
    rows = db.execute(
        text("""
            SELECT DISTINCT topic_id
            FROM daily_schedule
            WHERE student_id = :student_id
              AND topic_id IS NOT NULL
              AND status = 'COMPLETED'
        """),
        {"student_id": student_id},
    ).fetchall()

    return {_safe_int(row[0]) for row in rows if row[0] is not None}


def _fetch_completed_chapter_topic_count(db: Session, student_id: int) -> Dict[int, int]:
    rows = db.execute(
        text("""
            SELECT chapter_id, COUNT(DISTINCT topic_id) AS completed_count
            FROM daily_schedule
            WHERE student_id = :student_id
              AND topic_id IS NOT NULL
              AND chapter_id IS NOT NULL
              AND status = 'COMPLETED'
            GROUP BY chapter_id
        """),
        {"student_id": student_id},
    ).mappings().all()

    return {
        _safe_int(row["chapter_id"]): _safe_int(row["completed_count"])
        for row in rows
    }


def _fetch_existing_tasks(db: Session, student_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT
                ds.id,
                ds.schedule_date,
                ds.topic_id,
                ds.chapter_id,
                ds.subject_id,
                ds.status,
                ds.section,
                ds.task_type,
                ds.planned_minutes,
                COALESCE(ds.carry_count, 0) AS carry_count,
                ds.reason,
                ds.ai_reason,
                COALESCE(ds.ai_generated, FALSE) AS ai_generated,
                COALESCE(ds.locked_by_student, FALSE) AS locked_by_student,
                ds.submitted_at,
                ct.topic_name,
                c.chapter_name
            FROM daily_schedule ds
            LEFT JOIN chapter_topics ct ON ct.id = ds.topic_id
            LEFT JOIN chapters c ON c.id = ds.chapter_id
            WHERE ds.student_id = :student_id
            ORDER BY ds.schedule_date ASC, ds.start_time ASC NULLS LAST, ds.id ASC
        """),
        {"student_id": student_id},
    ).mappings().all()

    today = _today()
    output = []

    for row in rows:
        d = row["schedule_date"]
        output.append(
            {
                "schedule_id": _safe_int(row["id"]),
                "schedule_date": str(d),
                "days_from_today": (d - today).days if d else 0,
                "topic_id": _safe_int(row["topic_id"]) if row["topic_id"] else None,
                "topic_name": row["topic_name"],
                "chapter_id": _safe_int(row["chapter_id"]) if row["chapter_id"] else None,
                "chapter_name": row["chapter_name"],
                "status": row["status"],
                "section": row["section"],
                "task_type": row["task_type"],
                "planned_minutes": _safe_int(row["planned_minutes"], 30),
                "carry_count": _safe_int(row["carry_count"]),
                "reason": row["reason"] or row["ai_reason"],
                "ai_generated": bool(row["ai_generated"]),
                "locked_by_student": bool(row["locked_by_student"]),
                "submitted_at": str(row["submitted_at"]) if row["submitted_at"] else None,
            }
        )

    return output


def _fetch_pending_or_missed_tasks(db: Session, student_id: int) -> List[Dict[str, Any]]:
    all_tasks = _fetch_existing_tasks(db, student_id)

    return [
        item
        for item in all_tasks
        if item["status"] in {"SCHEDULED", "MISSED"}
        and item["topic_id"] is not None
    ]


def _fetch_retention_states(db: Session, student_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT
                rs.student_id,
                rs.subject_id,
                rs.chapter_id,
                COALESCE(rs.chapter_name, c.chapter_name) AS chapter_name,
                COALESCE(rs.difficulty, 'Medium') AS difficulty,
                COALESCE(rs.stability, 0) AS stability,
                COALESCE(rs.revision_count, 0) AS revision_count,
                COALESCE(rs.last_score, 0) AS last_score,
                COALESCE(rs.retention, 0) AS retention,
                COALESCE(rs.weak_chapter, FALSE) AS weak_chapter,
                COALESCE(rs.priority_score, 0) AS priority_score,
                COALESCE(rs.time_for_revision, 0) AS time_for_revision,
                COALESCE(rs.revision_time_percentage, 0) AS revision_time_percentage,
                rs.revision_time_updated_at,
                rs.last_activity_at,
                rs.last_decay_at
            FROM retention_states rs
            LEFT JOIN chapters c ON c.id = rs.chapter_id
            WHERE rs.student_id = :student_id
            ORDER BY COALESCE(rs.priority_score, 0) DESC,
                     COALESCE(rs.retention, 100) ASC
        """),
        {"student_id": student_id},
    ).mappings().all()

    return [
        {
            "chapter_id": _safe_int(row["chapter_id"]),
            "chapter_name": row["chapter_name"],
            "difficulty": row["difficulty"] or "Medium",
            "stability": _safe_float(row["stability"]),
            "revision_count": _safe_int(row["revision_count"]),
            "last_score": _safe_float(row["last_score"]),
            "retention": _safe_float(row["retention"]),
            "weak_chapter": bool(row["weak_chapter"]),
            "priority_score": _safe_float(row["priority_score"]),
            "time_for_revision": _safe_int(row["time_for_revision"]),
            "revision_time_percentage": _safe_float(row["revision_time_percentage"]),
            "revision_time_updated_at": str(row["revision_time_updated_at"]) if row["revision_time_updated_at"] else None,
            "last_activity_at": str(row["last_activity_at"]) if row["last_activity_at"] else None,
            "last_decay_at": str(row["last_decay_at"]) if row["last_decay_at"] else None,
        }
        for row in rows
    ]


def _fetch_recent_tests(db: Session, student_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT
                id,
                subject_id,
                total_questions,
                obtained_marks,
                total_marks,
                percentage,
                status,
                submitted_at,
                created_at
            FROM tests
            WHERE student_id = :student_id
              AND status = 'SUBMITTED'
            ORDER BY submitted_at DESC NULLS LAST, created_at DESC
            LIMIT 10
        """),
        {"student_id": student_id},
    ).mappings().all()

    return [
        {
            "test_id": _safe_int(row["id"]),
            "total_questions": _safe_int(row["total_questions"]),
            "obtained_marks": _safe_int(row["obtained_marks"]),
            "total_marks": _safe_int(row["total_marks"]),
            "percentage": _safe_float(row["percentage"]),
            "submitted_at": str(row["submitted_at"] or row["created_at"]),
        }
        for row in rows
    ]


def _fetch_wrong_question_topic_analysis(db: Session, student_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT
                qta.predicted_topic_id,
                qta.predicted_topic_name,
                COALESCE(qta.confidence, 0) AS confidence,
                qta.llm_reason,
                qta.chapter_id,
                c.chapter_name
            FROM question_topic_analysis qta
            LEFT JOIN chapters c ON c.id = qta.chapter_id
            WHERE qta.student_id = :student_id
              AND COALESCE(qta.confidence, 0) >= 75
            ORDER BY qta.created_at DESC
            LIMIT 20
        """),
        {"student_id": student_id},
    ).mappings().all()

    return [
        {
            "topic_id": _safe_int(row["predicted_topic_id"]) if row["predicted_topic_id"] else None,
            "topic_name": row["predicted_topic_name"],
            "confidence": _safe_float(row["confidence"]),
            "chapter_id": _safe_int(row["chapter_id"]) if row["chapter_id"] else None,
            "chapter_name": row["chapter_name"],
            "reason": row["llm_reason"],
        }
        for row in rows
    ]


# ==========================================================
# Schedule cleanup / focus logic
# ==========================================================

def _mark_old_scheduled_tasks_missed(db: Session, student_id: int):
    today = _today()

    db.execute(
        text("""
            UPDATE daily_schedule
            SET status = 'MISSED'
            WHERE student_id = :student_id
              AND schedule_date < :today
              AND status = 'SCHEDULED'
        """),
        {"student_id": student_id, "today": today},
    )

    db.commit()


def _clear_future_unlocked_scheduled_tasks(db: Session, student_id: int, start_date: date):
    db.execute(
        text("""
            DELETE FROM daily_schedule
            WHERE student_id = :student_id
              AND schedule_date >= :start_date
              AND status = 'SCHEDULED'
              AND COALESCE(locked_by_student, FALSE) = FALSE
        """),
        {"student_id": student_id, "start_date": start_date},
    )

    db.commit()


def _find_focus_chapters(retention_states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not retention_states:
        return []

    sorted_states = sorted(
        retention_states,
        key=lambda x: (
            -_safe_float(x.get("priority_score")),
            _safe_float(x.get("retention", 100)),
            _safe_float(x.get("last_score", 100)),
        ),
    )

    focus_list = []

    for state in sorted_states:
        priority = _safe_float(state.get("priority_score"))
        retention = _safe_float(state.get("retention"))
        last_score = _safe_float(state.get("last_score"))
        weak = bool(state.get("weak_chapter"))

        if priority >= 70 or retention < 45 or last_score < 50 or weak:
            focus_list.append(
                {
                    "chapter_id": state["chapter_id"],
                    "chapter_name": state["chapter_name"],
                    "priority_score": priority,
                    "retention": retention,
                    "last_score": last_score,
                    "difficulty": state.get("difficulty", "Medium"),
                    "revision_count": state.get("revision_count", 0),
                    "time_for_revision": _safe_int(state.get("time_for_revision")),
                    "revision_time_percentage": _safe_float(state.get("revision_time_percentage")),
                    "rule": "This chapter needs revision attention before heavy new study.",
                }
            )

    return focus_list[:5]


def _find_focus_chapter(retention_states: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    focus = _find_focus_chapters(retention_states)
    return focus[0] if focus else None


def _find_current_study_chapter(
    topics: List[Dict[str, Any]],
    completed_topic_ids: Set[int],
) -> Optional[Dict[str, Any]]:
    for topic in topics:
        if topic["topic_id"] not in completed_topic_ids:
            return {
                "chapter_id": topic["chapter_id"],
                "chapter_name": topic["chapter_name"],
                "chapter_order": topic["chapter_order"],
                "rule": "For STUDY_NEW tasks, continue this chapter first before jumping to next chapter.",
            }

    return None


def _topic_map(topics: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {item["topic_id"]: item for item in topics}


def _build_scenario_signals(
    retention_states: List[Dict[str, Any]],
    recent_tests: List[Dict[str, Any]],
    pending_missed_tasks: List[Dict[str, Any]],
    completed_topic_ids: Set[int],
    time_budget: Dict[str, Any],
    wrong_topics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    today = _today()

    missed_tasks = [t for t in pending_missed_tasks if str(t.get("status", "")).upper() == "MISSED"]
    old_missed_tasks = [t for t in missed_tasks if _safe_int(t.get("days_from_today"), 0) < -1]
    scheduled_today = [
        t for t in pending_missed_tasks
        if t.get("schedule_date") == str(today)
        and str(t.get("status", "")).upper() == "SCHEDULED"
    ]

    weak_states = [
        s for s in retention_states
        if bool(s.get("weak_chapter"))
        or _safe_float(s.get("retention")) < 45
        or _safe_float(s.get("last_score")) < 50
        or _safe_float(s.get("priority_score")) >= 70
    ]

    low_score_states = [s for s in retention_states if _safe_float(s.get("last_score")) < 40]
    average_score_states = [s for s in retention_states if 40 <= _safe_float(s.get("last_score")) < 70]
    high_score_states = [s for s in retention_states if _safe_float(s.get("last_score")) >= 70]
    repeated_fail_states = [
        s for s in retention_states
        if _safe_float(s.get("last_score")) < 40
        and _safe_int(s.get("revision_count")) >= 2
    ]
    repeated_high_states = [
        s for s in retention_states
        if _safe_float(s.get("last_score")) >= 80
        and _safe_int(s.get("revision_count")) >= 2
    ]

    recent_percentages = [_safe_float(t.get("percentage")) for t in recent_tests[:2]]
    improved_after_retest = len(recent_percentages) >= 2 and recent_percentages[0] > recent_percentages[1]
    worse_than_previous = len(recent_percentages) >= 2 and recent_percentages[0] < recent_percentages[1]

    score_groups: Dict[int, List[str]] = {}
    priority_groups: Dict[int, List[str]] = {}
    for state in retention_states:
        score_key = int(_safe_float(state.get("last_score")))
        priority_key = int(_safe_float(state.get("priority_score")) // 10) * 10
        score_groups.setdefault(score_key, []).append(state.get("chapter_name"))
        priority_groups.setdefault(priority_key, []).append(state.get("chapter_name"))

    same_score = {k: v for k, v in score_groups.items() if len(v) > 1}
    same_priority = {k: v for k, v in priority_groups.items() if len(v) > 1}

    return {
        "1_student_misses_one_full_day": len(missed_tasks) > 0,
        "2_student_partially_completes_today_chapter_task": len(scheduled_today) > 0 and len(completed_topic_ids) > 0,
        "3_student_misses_many_days_continuously": len(old_missed_tasks) >= 2,
        "4_student_gets_low_marks": len(low_score_states) > 0,
        "5_student_gets_average_marks": len(average_score_states) > 0,
        "6_student_gets_high_marks": len(high_score_states) > 0,
        "7_student_has_less_available_study_time_today": time_budget["total_minutes"] <= 60,
        "8_one_chapter_gets_delayed_multiple_days": len(old_missed_tasks) >= 2,
        "9_too_many_weak_chapters_come_in_one_day": len(weak_states) >= 3,
        "10_new_student_has_no_test_history": len(recent_tests) == 0 and len(retention_states) == 0,
        "11_student_studies_chapter_but_does_not_take_test": len(completed_topic_ids) > 0 and len(recent_tests) == 0,
        "12_student_starts_chapter_but_leaves_it_incomplete": len(scheduled_today) > 0,
        "13_student_completes_chapter_but_gets_low_marks_again": len(repeated_fail_states) > 0,
        "14_student_improves_after_retaking_chapter_test": improved_after_retest,
        "15_student_performs_worse_than_previous_test": worse_than_previous,
        "16_student_skips_only_highest_priority_chapter": len(missed_tasks) > 0 and len(weak_states) > 0,
        "17_student_completes_today_plan_early": False,
        "18_student_has_extra_study_time_today": time_budget["total_minutes"] >= 180,
        "19_student_changes_daily_available_study_time": True,
        "20_student_has_same_score_in_multiple_chapters": bool(same_score),
        "21_two_chapters_have_same_priority_level": bool(same_priority),
        "22_student_repeatedly_fails_same_chapter": len(repeated_fail_states) > 0,
        "23_student_repeatedly_scores_high_same_chapter": len(repeated_high_states) > 0,
        "24_student_has_chapter_data_but_no_marks_weightage": len(retention_states) > 0 and len(recent_tests) == 0,
        "25_student_misses_test_after_studying_chapter": len(completed_topic_ids) > 0 and len(recent_tests) == 0,
        "26_student_completes_easy_chapters_but_avoids_difficult_chapters": False,
        "27_student_has_only_30_minutes_available_today": time_budget["total_minutes"] <= 30,
        "28_student_has_not_studied_any_chapter_for_long_time": len(old_missed_tasks) >= 3,
        "29_student_has_old_pending_chapters_plus_new_weak_chapters": len(missed_tasks) > 0 and len(wrong_topics) > 0,
        "wrong_answer_exact_topics_available": len(wrong_topics) > 0,
        "same_score_groups": same_score,
        "same_priority_groups": same_priority,
        "scenario_notes": "These signals guide OpenAI. The final task reason must stay student-friendly.",
    }


# ==========================================================
# Prompt context
# ==========================================================
def _fetch_pending_topics_sidebar(db: Session, student_id: int) -> List[Dict[str, Any]]:
    """
    Fetch pending topics for schedule sidebar.

    These topics are not automatically added into the new schedule.
    They are shown only in the pending sidebar.

    Required table:
    student_pending_topics
    """

    try:
        rows = db.execute(
            text("""
                SELECT
                    id,
                    student_id,
                    subject_id,
                    chapter_id,
                    topic_id,
                    subject_name,
                    chapter_name,
                    topic_name,
                    pending_reason,
                    carry_count,
                    last_schedule_date,
                    status,
                    created_at,
                    updated_at
                FROM student_pending_topics
                WHERE student_id = :student_id
                  AND status = 'ACTIVE'
                ORDER BY updated_at DESC NULLS LAST, id DESC
            """),
            {"student_id": student_id},
        ).mappings().all()

    except Exception:
        db.rollback()
        return []

    return [
        {
            "id": _safe_int(row["id"]),
            "student_id": _safe_int(row["student_id"]),
            "subject_id": _safe_int(row["subject_id"]) if row["subject_id"] else None,
            "chapter_id": _safe_int(row["chapter_id"]) if row["chapter_id"] else None,
            "topic_id": _safe_int(row["topic_id"]) if row["topic_id"] else None,
            "subject_name": row["subject_name"] or "Maths",
            "chapter_name": row["chapter_name"] or "Chapter",
            "topic_name": row["topic_name"] or "Pending Topic",
            "pending_reason": row["pending_reason"] or "This topic is pending.",
            "carry_count": _safe_int(row["carry_count"]),
            "last_schedule_date": str(row["last_schedule_date"]) if row["last_schedule_date"] else None,
            "status": row["status"] or "ACTIVE",
            "created_at": str(row["created_at"]) if row["created_at"] else None,
            "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
        }
        for row in rows
    ]

def build_schedule_context(db: Session, student, start_date: Optional[date] = None) -> Dict[str, Any]:
    if start_date is None:
        start_date = _today()

    topics = _fetch_topics(db)
    completed_topic_ids = _fetch_completed_topic_ids(db, student.id)
    retention_states = _fetch_retention_states(db, student.id)
    recent_tests = _fetch_recent_tests(db, student.id)
    pending_and_missed = _fetch_pending_or_missed_tasks(db, student.id)
    wrong_topics = _fetch_wrong_question_topic_analysis(db, student.id)

    time_budget = _make_time_budget(
        student=student,
        retention_states=retention_states,
        recent_tests=recent_tests,
        wrong_topics=wrong_topics,
        pending_missed_tasks=pending_and_missed,
    )

    revision_time_allocations = _calculate_and_save_revision_time_allocation(
        db=db,
        student_id=student.id,
        total_revision_minutes=_safe_int(time_budget.get("revision_minutes"), 0),
    )

    # Re-fetch retention states after saving time_for_revision into retention_states.
    retention_states = _fetch_retention_states(db, student.id)

    focus_chapters = _find_focus_chapters(retention_states)
    focus_chapter = focus_chapters[0] if focus_chapters else None
    current_study_chapter = _find_current_study_chapter(topics, completed_topic_ids)

    end_date = start_date + timedelta(days=6)

    scenario_signals = _build_scenario_signals(
        retention_states=retention_states,
        recent_tests=recent_tests,
        pending_missed_tasks=pending_and_missed,
        completed_topic_ids=completed_topic_ids,
        time_budget=time_budget,
        wrong_topics=wrong_topics,
    )

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "today": str(_today()),
        "today_weekday": _weekday(_today()),
        "student": _student_context(student, time_budget),
        "time_budget": time_budget,
        "revision_time_allocations": revision_time_allocations,
        "topics": topics,
        "completed_topic_ids": sorted(list(completed_topic_ids)),
        "completed_chapter_topic_count": _fetch_completed_chapter_topic_count(db, student.id),
        "pending_and_missed_tasks": pending_and_missed,
        "pending_topics_sidebar_only": _fetch_pending_topics_sidebar(db, student.id),
        "retention_states": retention_states,
        "focus_chapter": focus_chapter,
        "focus_chapters": focus_chapters,
        "current_study_chapter": current_study_chapter,
        "recent_tests": recent_tests,
        "wrong_question_topics_confidence_75_plus": wrong_topics,
        "scenario_signals": scenario_signals,
    }


def _build_ai_prompt(context: Dict[str, Any]) -> str:
    return f"""
You are TrackMate AI Dynamic Schedule Engine.

You are not a normal timetable generator.
You are a smart study-planning mentor that creates a daily updating schedule for a student.

Your job:
Create a personalized 7-day schedule using ONLY the database context.

The schedule must update based on:
1. Yesterday's completed tasks
2. Yesterday's incomplete tasks
3. Today's available study time
4. Test result data
5. weak_chapter from retention_states
6. wrong-answer topic analysis
7. priority_score based revision time
8. completed topics
9. missed tasks
10. pending topics

IMPORTANT:
- Return ONLY valid JSON.
- No markdown.
- No explanation outside JSON.
- Do NOT invent topic_id, chapter_id, subject_id, chapter names, topic names, or scores.
- Use only topic_id values from the topics list.
- Backend will save your JSON into daily_schedule table.
- Frontend will show completion icon based on task status from database.
- You should create planned tasks only. Do not mark new tasks as completed.

Student-friendly language rule:
Do NOT use technical words in task reason:
- retention
- weak_chapter
- priority_score
- memory decay
- algorithm
- backend
- formula
- database

Use simple words:
- last test showed this needs practice
- revise this topic before moving ahead
- continue next topic
- quick review
- practice again
- retest after revision

Main daily time rule:
- Read student.study_hours_per_day from database.
- Convert it into daily_total_minutes.
- Example: 6 hours = 360 minutes.
- Do NOT cap at 90 minutes.
- Every day must respect daily_total_minutes.

Study and revision split:
- If a day has revision need:
  - Use about 70% of the day for STUDY.
  - Use about 30% of the day for REVISION.
  - Example: 360 minutes = 252 minutes study + 108 minutes revision.
- If there is NO revision task needed for that day:
  - Use full available time for STUDY.
  - Do not waste 30% time as empty revision.
- If revision topics are fewer than revision time:
  - Use leftover time for STUDY.
- Do not overload one day.

Revision time allocation rule:
- retention_states may contain time_for_revision.
- Backend calculates time_for_revision using this formula:
  time_for_revision = (chapter priority_score / total priority_score of revision chapters) × total revision minutes.
- Use retention_states.time_for_revision for REVISION tasks when it is greater than 0.
- Do not divide revision time equally if time_for_revision exists.
- Higher priority chapters should get more revision minutes.
- If time_for_revision is 0 or missing, use a reasonable revision time like 20 to 40 minutes.
- Do not show priority_score or retention value in reason.

Weak chapter revision rule:
- retention_states contains chapter-wise test result data.
- If any item in retention_states has weak_chapter = true, that chapter MUST be added as a REVISION task.
- If schedule is generated after test submit, weak chapter should appear in tomorrow's plan.
- Tomorrow means the day immediately after start_date.
- Use that weak chapter's chapter_id and chapter_name.
- Choose the best available topic from that chapter.
- If wrong_question_topics_confidence_75_plus has a topic from the same chapter, use that exact topic first.
- The weak chapter revision task must be in section = "REVISION".
- Do NOT put weak chapter revision inside STUDY section.
- task_type should be "REVISION", "PRACTICE", or "RETEST".
- Use simple reason:
  "Last test showed this chapter needs more practice, so revise it before moving ahead."

Wrong answer topic rule:
- wrong_question_topics_confidence_75_plus contains exact weak topics found from wrong answers.
- If a wrong-answer topic exists, put it in REVISION section.
- Prefer exact wrong-answer topic over random topic from same chapter.
- Do not place wrong-answer topics inside STUDY section.

Completed task rule:
- completed_topic_ids means student already completed those topics.
- Completed topics must NEVER appear again in STUDY section.
- Completed topics can appear only in REVISION section if:
  1. weak_chapter is true for its chapter
  2. wrong-answer topic analysis selected it
  3. latest test result says it needs practice again
- If completed topic is not weak, skip it and choose next incomplete topic.

Yesterday work rule:
- If yesterday's task is completed, do not repeat it in STUDY.
- If yesterday's task is not completed, move it forward.
- Move unfinished tasks day by day inside the same week.
- Do not punish the student.
- Do not overload today with too many old tasks.
- If today has less time, move only the most important unfinished task.

Pending list rule:
- If pending_topics_sidebar_only exists, those topics are already moved to pending list.
- Do NOT automatically add pending list topics into the new daily schedule.
- Pending topics should stay visible in sidebar only.
- From Monday, continue normal next incomplete topics in STUDY section.
- Pending topics can be manually reviewed later.

Study section rule:
- STUDY section is only for new/incomplete learning topics.
- Continue chapter order.
- If chapter is incomplete, continue remaining non-completed topics first.
- Do not jump randomly to a new chapter unless current chapter is completed.
- If no test history exists, start from Chapter 1 Topic 1 and continue in order.
- If no revision is needed, use full study time for STUDY tasks.

Revision section rule:
- REVISION section is only for:
  1. weak chapters
  2. low test score chapters
  3. wrong-answer topics
  4. missed tasks inside the same week
  5. retest/practice tasks
- AI Revision Plan button is shown only for REVISION section tasks in frontend.
- If a task needs micro revision support, section must be "REVISION".

Dynamic daily update rule:
- The schedule should change based on previous day work.
- If student completed tasks yesterday, move forward to next topic.
- If student missed tasks yesterday, carry them forward carefully.
- If student submitted a test and got low score, add revision for that chapter.
- If student performed well, reduce revision and move forward.
- If student has no revision need, use full day for study.

Completion icon rule:
- Frontend shows completion icon using task status from database.
- New tasks should be created as planned tasks.
- Do not mark new tasks completed in JSON.
- Do not create completed icons in JSON.
- Just generate tasks. Backend/frontend will handle tick mark.

Allowed sections:
- STUDY
- REVISION

Allowed task_type:
- STUDY_NEW
- REVISION
- PRACTICE
- RETEST
- CATCH_UP

Important validation rules:
1. Create exactly 7 days from start_date to end_date.
2. Every day must stay within daily_total_minutes.
3. Do not repeat the same topic_id in the same day.
4. Do not repeat completed topics in STUDY section.
5. Do not put weak-topic revision into STUDY section.
6. Do not create empty duplicate cards.
7. Use start_time in HH:MM format.
8. planned_minutes must be realistic.
9. If time_for_revision exists, use it for that chapter revision.
10. Keep task reason short and student-friendly.

Output JSON format:
{{
  "summary": "short student-friendly summary",
  "schedule_logic": "short explanation of how today's plan was created",
  "weak_topic_suggestion": {{
    "chapter_id": 2,
    "chapter_name": "chapter name",
    "topic_id": 10,
    "topic_name": "topic name",
    "reason": "simple reason"
  }},
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "weekday": "Monday",
      "day_strategy": "simple reason for this day",
      "planned_total_minutes": 360,
      "planned_study_minutes": 252,
      "planned_revision_minutes": 108,
      "tasks": [
        {{
          "topic_id": 1,
          "chapter_id": 1,
          "section": "STUDY",
          "task_type": "STUDY_NEW",
          "planned_minutes": 45,
          "start_time": "18:00",
          "reason": "Continue the next topic in order."
        }},
        {{
          "topic_id": 7,
          "chapter_id": 2,
          "section": "REVISION",
          "task_type": "REVISION",
          "planned_minutes": 50,
          "start_time": "19:00",
          "reason": "Last test showed this chapter needs more practice, so revise it before moving ahead."
        }}
      ]
    }}
  ]
}}

Database context:
{json.dumps(context, indent=2)}
"""


# ==========================================================
# Fallback plan
# ==========================================================

def _next_topics_for_chapter(
    topics: List[Dict[str, Any]],
    chapter_id: int,
    completed_ids: Set[int],
    used_ids: Set[int],
) -> List[Dict[str, Any]]:
    return [
        topic for topic in topics
        if topic["chapter_id"] == chapter_id
        and topic["topic_id"] not in completed_ids
        and topic["topic_id"] not in used_ids
    ]


def _fallback_plan(context: Dict[str, Any]) -> Dict[str, Any]:
    start_date = date.fromisoformat(context["start_date"])
    topics = context["topics"]

    completed_ids = set(context.get("completed_topic_ids", []))
    used_topic_ids: Set[int] = set()

    focus_chapters = context.get("focus_chapters") or []
    current_study = context.get("current_study_chapter")
    time_budget = context["time_budget"]

    daily_total = _safe_int(time_budget.get("total_minutes"), 90)
    study_budget = _safe_int(time_budget.get("study_minutes"), int(daily_total * 0.70))
    revision_budget = _safe_int(time_budget.get("revision_minutes"), daily_total - study_budget)

    wrong_topic_ids = [
        _safe_int(item.get("topic_id"))
        for item in context.get("wrong_question_topics_confidence_75_plus", [])
        if item.get("topic_id")
    ]

    days = []

    for i in range(7):
        d = start_date + timedelta(days=i)
        current_time = _parse_time(DEFAULT_START_TIME)

        remaining_total = daily_total
        remaining_study = study_budget
        remaining_revision = revision_budget

        tasks = []

        # 1. Revision from wrong-answer topics first.
        if remaining_revision >= MIN_TASK_MINUTES:
            for topic_id in wrong_topic_ids:
                if remaining_revision < MIN_TASK_MINUTES:
                    break

                if topic_id in used_topic_ids:
                    continue

                topic = next((t for t in topics if t["topic_id"] == topic_id), None)

                if not topic:
                    continue

                minutes = min(30, remaining_revision, remaining_total)

                tasks.append(
                    {
                        "topic_id": topic["topic_id"],
                        "chapter_id": topic["chapter_id"],
                        "subject_id": topic["subject_id"],
                        "topic_name": topic["topic_name"],
                        "chapter_name": topic["chapter_name"],
                        "section": "REVISION",
                        "task_type": "REVISION",
                        "planned_minutes": minutes,
                        "start_time": current_time.strftime("%H:%M"),
                        "reason": "This topic needs a focused review because recent answers showed confusion.",
                    }
                )

                used_topic_ids.add(topic["topic_id"])
                current_time = _add_minutes(current_time, minutes)
                remaining_revision -= minutes
                remaining_total -= minutes

        # 2. Revision from focus chapters.
        if focus_chapters and remaining_revision >= MIN_TASK_MINUTES:
            for focus in focus_chapters:
                if remaining_revision < MIN_TASK_MINUTES:
                    break

                focus_topics = _next_topics_for_chapter(
                    topics=topics,
                    chapter_id=focus["chapter_id"],
                    completed_ids=completed_ids,
                    used_ids=used_topic_ids,
                )

                if not focus_topics:
                    focus_topics = [
                        topic for topic in topics
                        if topic["chapter_id"] == focus["chapter_id"]
                        and topic["topic_id"] not in used_topic_ids
                    ]

                if not focus_topics:
                    continue

                topic = focus_topics[0]
                allocated_minutes = _safe_int(focus.get("time_for_revision"), 30)

                if allocated_minutes <= 0:
                    allocated_minutes = 30

                minutes = min(allocated_minutes, remaining_revision, remaining_total)
                task_type = "RETEST" if i >= 1 and _safe_float(focus.get("last_score")) < 40 else "REVISION"

                tasks.append(
                    {
                        "topic_id": topic["topic_id"],
                        "chapter_id": topic["chapter_id"],
                        "subject_id": topic["subject_id"],
                        "topic_name": topic["topic_name"],
                        "chapter_name": topic["chapter_name"],
                        "section": "REVISION",
                        "task_type": task_type,
                        "planned_minutes": minutes,
                        "start_time": current_time.strftime("%H:%M"),
                        "reason": "This chapter needs attention, so revise it before moving too far ahead.",
                    }
                )

                used_topic_ids.add(topic["topic_id"])
                current_time = _add_minutes(current_time, minutes)
                remaining_revision -= minutes
                remaining_total -= minutes

        # 3. Study new topics in order.
        study_topics = topics

        if current_study:
            same_chapter = [
                topic for topic in topics
                if topic["chapter_id"] == current_study["chapter_id"]
            ]

            next_chapters = [
                topic for topic in topics
                if topic["chapter_id"] != current_study["chapter_id"]
            ]

            study_topics = same_chapter + next_chapters

        for topic in study_topics:
            if remaining_study < MIN_TASK_MINUTES or remaining_total < MIN_TASK_MINUTES:
                break

            if topic["topic_id"] in completed_ids:
                continue

            if topic["topic_id"] in used_topic_ids:
                continue

            minutes = min(30, remaining_study, remaining_total)

            tasks.append(
                {
                    "topic_id": topic["topic_id"],
                    "chapter_id": topic["chapter_id"],
                    "subject_id": topic["subject_id"],
                    "topic_name": topic["topic_name"],
                    "chapter_name": topic["chapter_name"],
                    "section": "STUDY",
                    "task_type": "STUDY_NEW",
                    "planned_minutes": minutes,
                    "start_time": current_time.strftime("%H:%M"),
                    "reason": "Continue the next topic in order.",
                }
            )

            used_topic_ids.add(topic["topic_id"])
            current_time = _add_minutes(current_time, minutes)
            remaining_study -= minutes
            remaining_total -= minutes

        days.append(
            {
                "date": str(d),
                "weekday": _weekday(d),
                "day_strategy": "Fallback plan created using study time, revision need and topic order.",
                "planned_total_minutes": daily_total - remaining_total,
                "planned_study_minutes": study_budget - remaining_study,
                "planned_revision_minutes": revision_budget - remaining_revision,
                "tasks": tasks,
            }
        )

    weak_suggestion = None

    if focus_chapters:
        focus = focus_chapters[0]
        focus_topic = next(
            (topic for topic in topics if topic["chapter_id"] == focus["chapter_id"]),
            None,
        )

        if focus_topic:
            weak_suggestion = {
                "chapter_id": focus["chapter_id"],
                "chapter_name": focus["chapter_name"],
                "topic_id": focus_topic["topic_id"],
                "topic_name": focus_topic["topic_name"],
                "reason": "This chapter needs more practice first.",
            }

    return {
        "summary": "Fallback schedule generated using study time and topic progress.",
        "weak_topic_suggestion": weak_suggestion,
        "days": days,
    }


# ==========================================================
# Validation
# ==========================================================

def _validate_ai_plan(ai_plan: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    topics = context["topics"]
    topic_by_id = _topic_map(topics)
    valid_topic_ids = set(topic_by_id.keys())

    time_budget = context["time_budget"]
    daily_total_limit = _safe_int(time_budget.get("total_minutes"), 90)
    daily_study_limit = _safe_int(time_budget.get("study_minutes"), int(daily_total_limit * 0.70))
    daily_revision_limit = _safe_int(time_budget.get("revision_minutes"), daily_total_limit - daily_study_limit)

    start_date = date.fromisoformat(context["start_date"])
    allowed_dates = [start_date + timedelta(days=i) for i in range(7)]
    allowed_date_strings = {str(d) for d in allowed_dates}

    used_topic_ids: Set[int] = set()
    output_days: List[Dict[str, Any]] = []

    raw_days = ai_plan.get("days", [])

    for raw_day in raw_days:
        day_date = str(raw_day.get("date", "")).strip()

        if day_date not in allowed_date_strings:
            continue

        raw_tasks = raw_day.get("tasks", [])
        raw_day_has_revision = any(
            str(item.get("section", "STUDY")).upper() == "REVISION"
            for item in raw_tasks
        )
        effective_study_limit = (
            daily_study_limit
            if raw_day_has_revision and daily_revision_limit > 0
            else daily_total_limit
        )

        day_minutes = 0
        study_minutes = 0
        revision_minutes = 0
        tasks = []

        for raw_task in raw_tasks:
            topic_id = _safe_int(raw_task.get("topic_id"))

            if topic_id not in valid_topic_ids:
                continue

            if topic_id in used_topic_ids:
                continue

            topic = topic_by_id[topic_id]

            completed_topic_ids = set(context.get("completed_topic_ids", []))

            section = str(raw_task.get("section", "STUDY")).upper()
            if section not in {"STUDY", "REVISION"}:
                section = "STUDY"

            # Completed topic protection:
            # Once a topic is completed by the student, it must not come back
            # in STUDY section. It can only come as REVISION/RETEST/PRACTICE
            # if weak-topic / wrong-answer logic selected it.
            if section == "STUDY" and topic_id in completed_topic_ids:
                continue

            task_type = str(raw_task.get("task_type", "STUDY_NEW")).upper()
            if task_type not in {"STUDY_NEW", "REVISION", "RETEST", "CATCH_UP", "PRACTICE"}:
                task_type = "STUDY_NEW"

            planned = _safe_int(raw_task.get("planned_minutes"), DEFAULT_TASK_MINUTES)
            max_task_minutes_for_section = MAX_TASK_MINUTES

            if section == "REVISION":
                max_task_minutes_for_section = max(MAX_TASK_MINUTES, daily_revision_limit)

            planned = max(MIN_TASK_MINUTES, min(planned, max_task_minutes_for_section))

            if day_minutes + planned > daily_total_limit:
                continue

            if section == "STUDY" and study_minutes + planned > effective_study_limit:
                continue

            if section == "REVISION" and revision_minutes + planned > daily_revision_limit:
                continue

            if section == "REVISION" and daily_revision_limit <= 0:
                continue

            start_time = str(raw_task.get("start_time", DEFAULT_START_TIME)).strip()
            _parse_time(start_time)

            tasks.append(
                {
                    "topic_id": topic_id,
                    "chapter_id": topic["chapter_id"],
                    "subject_id": topic["subject_id"],
                    "topic_name": topic["topic_name"],
                    "chapter_name": topic["chapter_name"],
                    "section": section,
                    "task_type": task_type,
                    "planned_minutes": planned,
                    "start_time": start_time,
                    "reason": str(raw_task.get("reason", "AI selected this task."))[:500],
                }
            )

            used_topic_ids.add(topic_id)
            day_minutes += planned

            if section == "STUDY":
                study_minutes += planned
            else:
                revision_minutes += planned

        output_days.append(
            {
                "date": day_date,
                "weekday": raw_day.get("weekday") or _weekday(date.fromisoformat(day_date)),
                "day_strategy": str(raw_day.get("day_strategy", "AI generated schedule."))[:500],
                "planned_total_minutes": day_minutes,
                "planned_study_minutes": study_minutes,
                "planned_revision_minutes": revision_minutes,
                "tasks": tasks,
            }
        )

    if len(output_days) < 7:
        return _fallback_plan(context)

    return {
        "summary": str(ai_plan.get("summary", "AI schedule generated."))[:500],
        "weak_topic_suggestion": ai_plan.get("weak_topic_suggestion"),
        "days": output_days,
    }


# ==========================================================
# Save
# ==========================================================

def _save_schedule(db: Session, student_id: int, plan: Dict[str, Any]):
    for day in plan.get("days", []):
        schedule_date = date.fromisoformat(day["date"])

        for task in day.get("tasks", []):
            start = _parse_time(task["start_time"])
            end = _add_minutes(start, task["planned_minutes"])

            schedule_title = f"{task['chapter_name']} - {task['topic_name']}"

            db.execute(
                text("""
                    INSERT INTO daily_schedule (
                        student_id,
                        schedule_date,
                        subject_id,
                        chapter_id,
                        topic_id,
                        section,
                        task_type,
                        schedule_title,
                        planned_minutes,
                        start_time,
                        end_time,
                        status,
                        reason,
                        ai_generated,
                        ai_reason,
                        source_type,
                        day_label,
                        carry_count,
                        locked_by_student
                    )
                    VALUES (
                        :student_id,
                        :schedule_date,
                        :subject_id,
                        :chapter_id,
                        :topic_id,
                        :section,
                        :task_type,
                        :schedule_title,
                        :planned_minutes,
                        :start_time,
                        :end_time,
                        'SCHEDULED',
                        :reason,
                        TRUE,
                        :ai_reason,
                        'OPENAI',
                        :day_label,
                        0,
                        FALSE
                    )
                """),
                {
                    "student_id": student_id,
                    "schedule_date": schedule_date,
                    "subject_id": task["subject_id"],
                    "chapter_id": task["chapter_id"],
                    "topic_id": task["topic_id"],
                    "section": task["section"],
                    "task_type": task["task_type"],
                    "schedule_title": schedule_title,
                    "planned_minutes": task["planned_minutes"],
                    "start_time": start,
                    "end_time": end,
                    "reason": task["reason"],
                    "ai_reason": task["reason"],
                    "day_label": day["weekday"],
                },
            )

    db.commit()


def _save_ai_run(
    db: Session,
    student_id: int,
    start_date: date,
    end_date: date,
    context: Dict[str, Any],
    output: Dict[str, Any],
    status: str,
    error_message: Optional[str] = None,
):
    db.execute(
        text("""
            INSERT INTO ai_schedule_runs (
                student_id,
                start_date,
                end_date,
                model,
                prompt_summary,
                input_json,
                output_json,
                status,
                error_message
            )
            VALUES (
                :student_id,
                :start_date,
                :end_date,
                :model,
                :prompt_summary,
                CAST(:input_json AS jsonb),
                CAST(:output_json AS jsonb),
                :status,
                :error_message
            )
        """),
        {
            "student_id": student_id,
            "start_date": start_date,
            "end_date": end_date,
            "model": OPENAI_MODEL,
            "prompt_summary": "AI schedule generated using study_hours_per_day, 70/30 split and all scenario rules.",
            "input_json": json.dumps(context),
            "output_json": json.dumps(output),
            "status": status,
            "error_message": error_message,
        },
    )

    db.commit()


# ==========================================================
# Public: Generate schedule
# ==========================================================

def generate_openai_week_schedule(
    db: Session,
    student,
    start_date: Optional[date] = None,
    reason: str = "manual",
) -> Dict[str, Any]:
    if start_date is None:
        start_date = _today()

    end_date = start_date + timedelta(days=6)

    _mark_old_scheduled_tasks_missed(db, student.id)

    # Build context before deleting future scheduled tasks, so old pending/missed tasks are visible to AI.
    context = build_schedule_context(db, student, start_date)
    context["generation_reason"] = reason

    prompt = _build_ai_prompt(context)

    _clear_future_unlocked_scheduled_tasks(db, student.id, start_date)

    try:
        raw_plan = generate_ai_schedule_json(prompt)
        plan = _validate_ai_plan(raw_plan, context)

        _save_schedule(db, student.id, plan)
        _save_ai_run(db, student.id, start_date, end_date, context, plan, "SUCCESS")

        return {
            "message": "OpenAI schedule generated successfully",
            "model": OPENAI_MODEL,
            "ai_used": True,
            "plan": plan,
        }

    except Exception as e:
        plan = _fallback_plan(context)

        _save_schedule(db, student.id, plan)
        _save_ai_run(db, student.id, start_date, end_date, context, plan, "FALLBACK", str(e))

        return {
            "message": "Fallback schedule generated because OpenAI failed",
            "model": "fallback",
            "ai_used": False,
            "error": str(e),
            "plan": plan,
        }


# ==========================================================
# Dashboard helpers
# ==========================================================

def _task_to_dict(row) -> Dict[str, Any]:
    return {
        "id": _safe_int(row["id"]),
        "schedule_date": str(row["schedule_date"]),
        "section": row["section"] or "STUDY",
        "task_type": row["task_type"] or "STUDY_NEW",
        "title": row["schedule_title"],
        "subject_id": row["subject_id"],
        "subject_name": row["subject_name"] or "Maths",
        "chapter_id": row["chapter_id"],
        "chapter_name": row["chapter_name"] or f"Chapter {row['chapter_id']}",
        "topic_id": row["topic_id"],
        "topic_name": row["topic_name"],
        "topic_order": row["topic_order"],
        "difficulty": row["difficulty"],
        "planned_minutes": row["planned_minutes"],
        "start_time": _time_to_str(row["start_time"]),
        "end_time": _time_to_str(row["end_time"]),
        "status": row["status"],
        "reason": row["reason"],
        "ai_reason": row["ai_reason"],
        "ai_generated": bool(row["ai_generated"]),
        "source_type": row["source_type"],
        "is_completed": row["status"] == "COMPLETED",
    }


def _tasks_for_date(db: Session, student_id: int, target_date: date) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT
                ds.id,
                ds.schedule_date,
                ds.subject_id,
                COALESCE(s.subject_name, 'Maths') AS subject_name,
                ds.chapter_id,
                c.chapter_name,
                ds.topic_id,
                ct.topic_name,
                ct.topic_order,
                ct.difficulty,
                ds.section,
                ds.task_type,
                ds.schedule_title,
                ds.planned_minutes,
                ds.start_time,
                ds.end_time,
                ds.status,
                ds.reason,
                ds.ai_reason,
                COALESCE(ds.ai_generated, FALSE) AS ai_generated,
                COALESCE(ds.source_type, 'SYSTEM') AS source_type
            FROM daily_schedule ds
            LEFT JOIN subjects s ON s.id = ds.subject_id
            LEFT JOIN chapters c ON c.id = ds.chapter_id
            LEFT JOIN chapter_topics ct ON ct.id = ds.topic_id
            WHERE ds.student_id = :student_id
              AND ds.schedule_date = :target_date
            ORDER BY ds.start_time ASC NULLS LAST, ds.id ASC
        """),
        {"student_id": student_id, "target_date": target_date},
    ).mappings().all()

    return [_task_to_dict(row) for row in rows]


def _day_block(db: Session, student_id: int, target_date: date) -> Dict[str, Any]:
    tasks = _tasks_for_date(db, student_id, target_date)

    study_tasks = [t for t in tasks if t["section"] == "STUDY"]
    revision_tasks = [t for t in tasks if t["section"] == "REVISION"]

    completed = len([t for t in tasks if t["status"] == "COMPLETED"])

    return {
        "label": _date_label(target_date),
        "date": str(target_date),
        "weekday": _weekday(target_date),
        "total_tasks": len(tasks),
        "completed_tasks": completed,
        "pending_tasks": max(len(tasks) - completed, 0),
        "study_tasks": study_tasks,
        "revision_tasks": revision_tasks,
        "tasks": tasks,
    }


def _stats(db: Session, student) -> Dict[str, Any]:
    retention_states = _fetch_retention_states(db, student.id)

    if not retention_states:
        return {
            "overall_retention": 0,
            "weak_topics": 0,
            "upcoming_reviews": 0,
            "learning_stability": 0,
            "study_hours_per_day": _student_study_hours(student),
        }

    avg_retention = round(
        sum(item["retention"] for item in retention_states) / len(retention_states),
        2,
    )

    weak_count = len(
        [
            item
            for item in retention_states
            if item["weak_chapter"]
            or item["retention"] < 40
            or item["last_score"] < 40
        ]
    )

    today = _today()
    tomorrow = today + timedelta(days=1)

    upcoming_reviews = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM daily_schedule
            WHERE student_id = :student_id
              AND schedule_date IN (:today, :tomorrow)
              AND section = 'REVISION'
              AND status = 'SCHEDULED'
        """),
        {
            "student_id": student.id,
            "today": today,
            "tomorrow": tomorrow,
        },
    ).mappings().first()

    avg_stability = round(
        sum(item["stability"] for item in retention_states) / len(retention_states),
        2,
    )

    return {
        "overall_retention": avg_retention,
        "weak_topics": weak_count,
        "upcoming_reviews": _safe_int(upcoming_reviews["cnt"]),
        "learning_stability": avg_stability,
        "study_hours_per_day": _student_study_hours(student),
    }


def _ai_recommendation(db: Session, student) -> Dict[str, Any]:
    states = _fetch_retention_states(db, student.id)

    if not states:
        return {
            "title": "Start Chapter 1",
            "message": "No test history found. Start with the first chapter topics and take a test after studying.",
            "action": "Generate AI Plan",
        }

    states = sorted(
        states,
        key=lambda x: (-x["priority_score"], x["retention"], x["last_score"]),
    )

    top = states[0]

    if top["last_score"] < 40:
        message = (
            f"{top['chapter_name']} needs more practice. "
            f"Revise planned topics first, then take a short retest."
        )
    elif top["retention"] < 40:
        message = (
            f"{top['chapter_name']} needs a quick review today. "
            f"Add revision before new study."
        )
    else:
        message = (
            f"{top['chapter_name']} should be reviewed before moving too far ahead."
        )

    return {
        "title": f"Recommended: {top['chapter_name']}",
        "message": message,
        "action": "Review Now",
        "retention": top["retention"],
        "priority_score": top["priority_score"],
        "last_score": top["last_score"],
    }


def get_ai_schedule_dashboard(db: Session, student) -> Dict[str, Any]:
    _mark_old_scheduled_tasks_missed(db, student.id)

    exam_countdown = _update_exam_day_left(db, student)

    today = _today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    today_count = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM daily_schedule
            WHERE student_id = :student_id
              AND schedule_date = :today
        """),
        {"student_id": student.id, "today": today},
    ).mappings().first()

    tomorrow_count = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM daily_schedule
            WHERE student_id = :student_id
              AND schedule_date = :tomorrow
        """),
        {"student_id": student.id, "tomorrow": tomorrow},
    ).mappings().first()

    if _safe_int(today_count["cnt"]) == 0 or _safe_int(tomorrow_count["cnt"]) == 0:
        generate_openai_week_schedule(
            db,
            student,
            start_date=today,
            reason="dashboard_auto_missing_plan",
        )

    retention_states = _fetch_retention_states(db, student.id)
    recent_tests = _fetch_recent_tests(db, student.id)
    pending_and_missed = _fetch_pending_or_missed_tasks(db, student.id)
    wrong_topics = _fetch_wrong_question_topic_analysis(db, student.id)

    time_budget = _make_time_budget(
        student=student,
        retention_states=retention_states,
        recent_tests=recent_tests,
        wrong_topics=wrong_topics,
        pending_missed_tasks=pending_and_missed,
    )

    return {
        "student": {
            "id": student.id,
            "name": getattr(student, "name", "Student"),
            "study_hours_per_day": _student_study_hours(student),
            "exam_day_left": exam_countdown["exam_day_left"],
            "exam_days_left": exam_countdown["exam_days_left"],
        },
        "exam_countdown": exam_countdown,
        "budget": {
            "total_minutes": time_budget["total_minutes"],
            "study_minutes": time_budget["study_minutes"],
            "revision_minutes": time_budget["revision_minutes"],
            "buffer_minutes": time_budget["buffer_minutes"],
            "mode": time_budget["mode"],
        },
        "stats": _stats(db, student),
        "ai_recommendation": _ai_recommendation(db, student),
        "days": [
            _day_block(db, student.id, yesterday),
            _day_block(db, student.id, today),
            _day_block(db, student.id, tomorrow),
        ],
    }


# ==========================================================
# Public: Whole plan
# ==========================================================

def get_whole_week_plan(db: Session, student) -> Dict[str, Any]:
    """
    Whole plan must always show Monday to Sunday.

    Example:
    If today is Wednesday, this page still shows:
    Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday.
    Not Wednesday to Tuesday.
    """

    today = _today()

    # Monday = 0, Sunday = 6
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    rows = db.execute(
        text("""
            SELECT
                ds.id,
                ds.schedule_date,
                ds.day_label,
                ds.section,
                ds.task_type,
                ds.schedule_title,
                ds.planned_minutes,
                ds.start_time,
                ds.end_time,
                ds.status,
                ds.reason,
                ds.ai_reason,
                COALESCE(ds.ai_generated, FALSE) AS ai_generated,
                COALESCE(ds.source_type, 'SYSTEM') AS source_type,
                ds.topic_id,
                ct.topic_name,
                c.chapter_name
            FROM daily_schedule ds
            LEFT JOIN chapter_topics ct ON ct.id = ds.topic_id
            LEFT JOIN chapters c ON c.id = ds.chapter_id
            WHERE ds.student_id = :student_id
              AND ds.schedule_date BETWEEN :week_start AND :week_end
            ORDER BY ds.schedule_date ASC, ds.start_time ASC NULLS LAST, ds.id ASC
        """),
        {
            "student_id": student.id,
            "week_start": week_start,
            "week_end": week_end,
        },
    ).mappings().all()

    day_map: Dict[str, Dict[str, Any]] = {}

    for i in range(7):
        d = week_start + timedelta(days=i)
        day_map[str(d)] = {
            "date": str(d),
            "weekday": _weekday(d),
            "label": _date_label(d),
            "is_today": d == today,
            "is_past": d < today,
            "is_future": d > today,
            "study_tasks": [],
            "revision_tasks": [],
            "tasks": [],
        }

    for row in rows:
        d = str(row["schedule_date"])

        if d not in day_map:
            continue

        task = {
            "id": _safe_int(row["id"]),
            "section": row["section"],
            "task_type": row["task_type"],
            "title": row["schedule_title"],
            "topic_id": row["topic_id"],
            "topic_name": row["topic_name"],
            "chapter_name": row["chapter_name"],
            "planned_minutes": row["planned_minutes"],
            "start_time": _time_to_str(row["start_time"]),
            "end_time": _time_to_str(row["end_time"]),
            "status": row["status"],
            "reason": row["reason"],
            "ai_generated": bool(row["ai_generated"]),
            "ai_reason": row["ai_reason"],
            "source_type": row["source_type"],
        }

        day_map[d]["tasks"].append(task)

        if str(row["section"] or "").upper() == "REVISION":
            day_map[d]["revision_tasks"].append(task)
        else:
            day_map[d]["study_tasks"].append(task)

    return {
        "start_date": str(week_start),
        "end_date": str(week_end),
        "week_start": str(week_start),
        "week_end": str(week_end),
        "today": str(today),
        "week_label": f"{week_start.strftime('%d %b')} - {week_end.strftime('%d %b')}",
        "days": list(day_map.values()),
    }

# ==========================================================
# Public: Submit today
# ==========================================================

def submit_today_schedule(db: Session, student) -> Dict[str, Any]:
    today = _today()

    row = db.execute(
        text("""
            SELECT COUNT(*) AS pending_count
            FROM daily_schedule
            WHERE student_id = :student_id
              AND schedule_date = :today
              AND status = 'SCHEDULED'
        """),
        {"student_id": student.id, "today": today},
    ).mappings().first()

    pending = _safe_int(row["pending_count"])

    if pending > 0:
        return {
            "submitted": False,
            "message": f"{pending} tasks are still pending. Complete or mark missed first.",
        }

    db.execute(
        text("""
            UPDATE daily_schedule
            SET submitted_at = :submitted_at,
                locked_by_student = TRUE
            WHERE student_id = :student_id
              AND schedule_date = :today
        """),
        {
            "student_id": student.id,
            "today": today,
            "submitted_at": _now(),
        },
    )

    db.commit()

    return {
        "submitted": True,
        "message": "Today schedule submitted successfully.",
    }


# ==========================================================
# Public: Regenerate after test submit
# ==========================================================

def regenerate_schedule_after_test_submit(db: Session, student_id: int) -> Dict[str, Any]:
    student = (
        db.query(models.Student)
        .filter(models.Student.id == student_id)
        .first()
    )

    if not student:
        return {
            "ai_schedule_regenerated": False,
            "reason": "student not found",
        }

    result = generate_openai_week_schedule(
        db=db,
        student=student,
        start_date=_today(),
        reason="after_test_submit",
    )

    return {
        "ai_schedule_regenerated": True,
        "ai_used": result.get("ai_used", False),
        "message": result.get("message"),
    }
