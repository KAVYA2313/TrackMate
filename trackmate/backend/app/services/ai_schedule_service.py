import json
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.services.openai_service import generate_ai_schedule_json, OPENAI_MODEL


DEFAULT_START_TIME = "18:00"
MAX_DAILY_MINUTES = 90
MIN_TASK_MINUTES = 20
MAX_TASK_MINUTES = 45
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


# ==========================================================
# Data fetchers
# ==========================================================

def _student_context(student) -> Dict[str, Any]:
    study_hours = _safe_float(getattr(student, "study_hours_per_day", 1.5), 1.5)
    total_minutes = max(30, int(study_hours * 60))
    maths_minutes = min(total_minutes, MAX_DAILY_MINUTES)

    return {
        "student_id": student.id,
        "student_name": getattr(student, "name", "Student"),
        "study_hours_per_day": study_hours,
        "daily_maths_minutes": maths_minutes,
        "normal_rule": "For Maths demo, max 90 minutes per day.",
        "split_rule": "If revision exists, use revision first and keep total daily load realistic.",
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
    """
    Important:
    Clear all future SCHEDULED tasks, not only AI tasks.
    This prevents duplicate static + AI schedule mixing.
    Completed and missed history stays safe.
    """

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


def _find_focus_chapter(retention_states: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Decides if one chapter should control the plan.

    If priority is very high or last score is very low,
    LLM should first revise this chapter before moving forward.
    """

    if not retention_states:
        return None

    sorted_states = sorted(
        retention_states,
        key=lambda x: (
            -_safe_float(x.get("priority_score")),
            _safe_float(x.get("retention", 100)),
            _safe_float(x.get("last_score", 100)),
        ),
    )

    top = sorted_states[0]

    priority = _safe_float(top.get("priority_score"))
    retention = _safe_float(top.get("retention"))
    last_score = _safe_float(top.get("last_score"))
    weak = bool(top.get("weak_chapter"))

    if priority >= 90 or retention < 35 or last_score < 40 or weak:
        return {
            "chapter_id": top["chapter_id"],
            "chapter_name": top["chapter_name"],
            "priority_score": priority,
            "retention": retention,
            "last_score": last_score,
            "difficulty": top.get("difficulty", "Medium"),
            "rule": (
                "This is focus chapter. Put revision/retest tasks for this chapter first. "
                "Do not overload, but do not ignore this chapter."
            ),
        }

    return None


def _find_current_study_chapter(
    topics: List[Dict[str, Any]],
    completed_topic_ids: Set[int],
) -> Optional[Dict[str, Any]]:
    """
    Keeps study sequence clean:
    finish current chapter topics before jumping to next chapter.
    """

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


# ==========================================================
# Prompt
# ==========================================================

def build_schedule_context(db: Session, student, start_date: Optional[date] = None) -> Dict[str, Any]:
    if start_date is None:
        start_date = _today()

    topics = _fetch_topics(db)
    completed_topic_ids = _fetch_completed_topic_ids(db, student.id)
    retention_states = _fetch_retention_states(db, student.id)

    focus_chapter = _find_focus_chapter(retention_states)
    current_study_chapter = _find_current_study_chapter(topics, completed_topic_ids)

    end_date = start_date + timedelta(days=6)

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "today": str(_today()),
        "today_weekday": _weekday(_today()),
        "student": _student_context(student),
        "topics": topics,
        "completed_topic_ids": sorted(list(completed_topic_ids)),
        "completed_chapter_topic_count": _fetch_completed_chapter_topic_count(db, student.id),
        "pending_and_missed_tasks": _fetch_pending_or_missed_tasks(db, student.id),
        "retention_states": retention_states,
        "focus_chapter": focus_chapter,
        "current_study_chapter": current_study_chapter,
        "recent_tests": _fetch_recent_tests(db, student.id),
        "wrong_question_topics_confidence_75_plus": _fetch_wrong_question_topic_analysis(db, student.id),
    }


def _build_ai_prompt(context: Dict[str, Any]) -> str:
    return f"""
You are an expert AI study planner for students.

Your job is to create a personalized 7-day study schedule using ONLY the student data provided.

IMPORTANT:
All calculations such as retention, weak chapter detection, priority score, and recommended actions are already calculated by the backend system.
DO NOT recalculate them.
DO NOT change priorities.
DO NOT invent scores or chapters.

Your job is ONLY to intelligently convert the provided data into a realistic study plan.

RULES:

1. Higher priority chapters should generally come earlier.

2. Respect the student's available daily study time.
   Never overload the student.

3. Use simple student-friendly language.
   Do not mention:

* retention score
* priority algorithm
* backend logic
* decay
* memory formula
* system calculations

Instead say:

* needs urgent revision
* needs extra practice
* strong topic
* quick review
* revisit basics

4. If the student missed previous study days:
   Reschedule intelligently.
   Do not dump all missed tasks into one day.

5. If a chapter was partially completed:
   Continue remaining work first.

6. If a chapter was started but left incomplete:
   Resume it before starting too many new chapters.

7. If a student repeatedly performs poorly:
   Break the chapter into smaller sessions across multiple days.

8. If a student improved after retesting:
   Reduce urgency.

9. If a student performs worse than before:
   Increase practice and revision time.

10. If many weak chapters exist:
    Distribute them across multiple days.

11. If student has very little study time:
    Focus only on highest-priority tasks.

12. If student has extra time:
    Add bonus practice, revision, or self-tests.

13. If student has no history:
    Create a balanced beginner-friendly schedule.

14. If easy chapters are repeatedly chosen while difficult chapters are avoided:
    Encourage difficult chapter scheduling.

15. If student has pending old chapters plus new weak chapters:
    Balance backlog with urgent work.

16. If two chapters have similar priority:
    Balance workload using difficulty and pending status.

17. If student repeatedly skips the same chapter:
    Split it into smaller manageable tasks.

18. Output must be realistic and motivating for non-technical students.

OUTPUT FORMAT:

Return exactly 7 days.

For each day include:

* day number
* total planned study time
* chapter/task list
* short simple explanation

Example style:

Day 1 (90 mins)
• Algebra — 40 mins
This topic needs extra attention, so begin here.

• Trigonometry — 30 mins
Quick revision to keep concepts fresh.

• Mini practice quiz — 20 mins


Output JSON format:
{{
  "summary": "short summary of plan",
  "weak_topic_suggestion": {{
    "chapter_id": 2,
    "chapter_name": "chapter name",
    "topic_id": 10,
    "topic_name": "topic name",
    "reason": "why this is weak"
  }},
  "days": [
    {{
      "date": "YYYY-MM-DD",
      "weekday": "Wednesday",
      "day_strategy": "short reason",
      "tasks": [
        {{
          "topic_id": 1,
          "chapter_id": 1,
          "section": "STUDY",
          "task_type": "STUDY_NEW",
          "planned_minutes": 30,
          "start_time": "18:00",
          "reason": "why selected"
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

def _fallback_plan(context: Dict[str, Any]) -> Dict[str, Any]:
    start_date = date.fromisoformat(context["start_date"])
    topics = context["topics"]
    topic_by_id = _topic_map(topics)

    completed_ids = set(context.get("completed_topic_ids", []))
    used_topic_ids: Set[int] = set()

    focus = context.get("focus_chapter")
    current_study = context.get("current_study_chapter")

    days = []

    for i in range(7):
        d = start_date + timedelta(days=i)
        current_time = _parse_time(DEFAULT_START_TIME)
        remaining_minutes = _safe_int(context["student"]["daily_maths_minutes"], MAX_DAILY_MINUTES)

        tasks = []

        # Focus chapter first if weak/high priority
        if focus and remaining_minutes >= 30:
            focus_topics = [
                t for t in topics
                if t["chapter_id"] == focus["chapter_id"]
                and t["topic_id"] not in completed_ids
                and t["topic_id"] not in used_topic_ids
            ]

            if not focus_topics:
                focus_topics = [
                    t for t in topics
                    if t["chapter_id"] == focus["chapter_id"]
                    and t["topic_id"] not in used_topic_ids
                ]

            if focus_topics:
                topic = focus_topics[0]
                task_type = "RETEST" if i >= 1 and focus.get("last_score", 0) < 40 else "REVISION"

                tasks.append(
                    {
                        "topic_id": topic["topic_id"],
                        "chapter_id": topic["chapter_id"],
                        "subject_id": topic["subject_id"],
                        "topic_name": topic["topic_name"],
                        "chapter_name": topic["chapter_name"],
                        "section": "REVISION",
                        "task_type": task_type,
                        "planned_minutes": 30,
                        "start_time": current_time.strftime("%H:%M"),
                        "reason": f"Focus chapter: priority {focus['priority_score']}, retention {focus['retention']}%, last score {focus['last_score']}%.",
                    }
                )

                used_topic_ids.add(topic["topic_id"])
                current_time = _add_minutes(current_time, 30)
                remaining_minutes -= 30

        # Study new topics in current chapter order
        study_topics = topics

        if current_study:
            chapter_id = current_study["chapter_id"]
            same_chapter = [t for t in topics if t["chapter_id"] == chapter_id]
            next_chapters = [t for t in topics if t["chapter_id"] != chapter_id]
            study_topics = same_chapter + next_chapters

        for topic in study_topics:
            if remaining_minutes < 30:
                break

            if topic["topic_id"] in completed_ids:
                continue

            if topic["topic_id"] in used_topic_ids:
                continue

            tasks.append(
                {
                    "topic_id": topic["topic_id"],
                    "chapter_id": topic["chapter_id"],
                    "subject_id": topic["subject_id"],
                    "topic_name": topic["topic_name"],
                    "chapter_name": topic["chapter_name"],
                    "section": "STUDY",
                    "task_type": "STUDY_NEW",
                    "planned_minutes": 30,
                    "start_time": current_time.strftime("%H:%M"),
                    "reason": "Continue next incomplete topic in order.",
                }
            )

            used_topic_ids.add(topic["topic_id"])
            current_time = _add_minutes(current_time, 30)
            remaining_minutes -= 30

        days.append(
            {
                "date": str(d),
                "weekday": _weekday(d),
                "day_strategy": "Fallback schedule created using priority and topic order.",
                "tasks": tasks,
            }
        )

    weak_suggestion = None

    if focus:
        focus_topics = [t for t in topics if t["chapter_id"] == focus["chapter_id"]]
        if focus_topics:
            weak_suggestion = {
                "chapter_id": focus["chapter_id"],
                "chapter_name": focus["chapter_name"],
                "topic_id": focus_topics[0]["topic_id"],
                "topic_name": focus_topics[0]["topic_name"],
                "reason": "Highest priority weak chapter.",
            }

    return {
        "summary": "Fallback schedule generated with priority and topic order.",
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

        day_minutes = 0
        tasks = []

        for raw_task in raw_day.get("tasks", []):
            topic_id = _safe_int(raw_task.get("topic_id"))

            if topic_id not in valid_topic_ids:
                continue

            # Hard duplicate prevention
            if topic_id in used_topic_ids:
                continue

            topic = topic_by_id[topic_id]

            section = str(raw_task.get("section", "STUDY")).upper()
            if section not in {"STUDY", "REVISION"}:
                section = "STUDY"

            task_type = str(raw_task.get("task_type", "STUDY_NEW")).upper()
            if task_type not in {"STUDY_NEW", "REVISION", "RETEST", "CATCH_UP"}:
                task_type = "STUDY_NEW"

            planned = _safe_int(raw_task.get("planned_minutes"), DEFAULT_TASK_MINUTES)
            planned = max(MIN_TASK_MINUTES, min(planned, MAX_TASK_MINUTES))

            if day_minutes + planned > context["student"]["daily_maths_minutes"]:
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

        output_days.append(
            {
                "date": day_date,
                "weekday": raw_day.get("weekday") or _weekday(date.fromisoformat(day_date)),
                "day_strategy": str(raw_day.get("day_strategy", "AI generated schedule."))[:500],
                "tasks": tasks,
            }
        )

    # If AI returned bad/empty schedule, use fallback
    if len(output_days) < 7:
        return _fallback_plan(context)

    weak_suggestion = ai_plan.get("weak_topic_suggestion")

    return {
        "summary": str(ai_plan.get("summary", "AI schedule generated."))[:500],
        "weak_topic_suggestion": weak_suggestion,
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
            "prompt_summary": "Full AI schedule generation using retention, priority score, missed tasks and topics.",
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
    _clear_future_unlocked_scheduled_tasks(db, student.id, start_date)

    context = build_schedule_context(db, student, start_date)

    context["generation_reason"] = reason

    prompt = _build_ai_prompt(context)

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
# Public: Dashboard
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
            "study_hours_per_day": _safe_float(getattr(student, "study_hours_per_day", 1.5), 1.5),
        }

    avg_retention = round(
        sum(item["retention"] for item in retention_states) / len(retention_states),
        2,
    )

    weak_count = len(
        [
            item
            for item in retention_states
            if item["weak_chapter"] or item["retention"] < 40 or item["last_score"] < 40
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
        "study_hours_per_day": _safe_float(getattr(student, "study_hours_per_day", 1.5), 1.5),
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
            f"Your latest score in {top['chapter_name']} is low. "
            f"Revise weak topics first, then take a retest."
        )
    elif top["retention"] < 40:
        message = (
            f"Your retention in {top['chapter_name']} is low. "
            f"Add revision before new study topics."
        )
    else:
        message = (
            f"{top['chapter_name']} has the highest priority score. "
            f"Review it before moving ahead."
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

    # Fully AI controlled:
    # if no plan exists, generate AI plan instead of static schedule.
    if _safe_int(today_count["cnt"]) == 0 or _safe_int(tomorrow_count["cnt"]) == 0:
        generate_openai_week_schedule(db, student, start_date=today, reason="dashboard_auto_missing_plan")

    study_hours = _safe_float(getattr(student, "study_hours_per_day", 1.5), 1.5)
    total_minutes = min(max(int(study_hours * 60), 30), MAX_DAILY_MINUTES)

    return {
        "student": {
            "id": student.id,
            "name": getattr(student, "name", "Student"),
            "study_hours_per_day": study_hours,
        },
        "budget": {
            "total_minutes": total_minutes,
            "study_minutes": int(total_minutes * 0.70),
            "revision_minutes": total_minutes - int(total_minutes * 0.70),
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
    today = _today()
    end_date = today + timedelta(days=6)

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
              AND ds.schedule_date BETWEEN :today AND :end_date
            ORDER BY ds.schedule_date ASC, ds.start_time ASC NULLS LAST, ds.id ASC
        """),
        {
            "student_id": student.id,
            "today": today,
            "end_date": end_date,
        },
    ).mappings().all()

    day_map: Dict[str, Dict[str, Any]] = {}

    for i in range(7):
        d = today + timedelta(days=i)
        day_map[str(d)] = {
            "date": str(d),
            "weekday": _weekday(d),
            "tasks": [],
        }

    for row in rows:
        d = str(row["schedule_date"])

        day_map[d]["tasks"].append(
            {
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
        )

    return {
        "start_date": str(today),
        "end_date": str(end_date),
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