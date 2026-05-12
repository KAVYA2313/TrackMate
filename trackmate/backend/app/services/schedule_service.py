from datetime import date, datetime, timedelta, time
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models


MAX_SINGLE_SUBJECT_MINUTES = 90
DEFAULT_START_HOUR = 18
DEFAULT_START_MINUTE = 0


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _week_name(d: date) -> str:
    return d.strftime("%A")


def _add_minutes_to_time(base: time, minutes: int) -> time:
    dummy = datetime.combine(date.today(), base)
    dummy = dummy + timedelta(minutes=minutes)
    return dummy.time()


def _get_daily_minutes(student) -> int:
    """
    We fetch study_hours_per_day from student table.
    For now only Maths subject is used, so we cap one subject to 1.5 hours.
    Example:
    student has 6 hours/day -> Maths gets 90 minutes.
    student has 30 minutes/day -> Maths gets 30 minutes.
    """
    study_hours = _safe_float(getattr(student, "study_hours_per_day", None), 1.5)
    total = int(study_hours * 60)

    if total <= 0:
        total = 90

    return max(30, min(total, MAX_SINGLE_SUBJECT_MINUTES))


def _get_study_revision_budget(student, has_revision_work: bool) -> Dict:
    total_minutes = _get_daily_minutes(student)

    if not has_revision_work:
        study_minutes = total_minutes
        revision_minutes = 0
    else:
        study_minutes = int(total_minutes * 0.70)
        revision_minutes = total_minutes - study_minutes

        if revision_minutes < 30 and total_minutes >= 60:
            revision_minutes = 30
            study_minutes = total_minutes - revision_minutes

    return {
        "total_minutes": total_minutes,
        "study_minutes": study_minutes,
        "revision_minutes": revision_minutes,
    }


def _mark_old_tasks_missed(db: Session, student_id: int):
    today = date.today()

    old_tasks = (
        db.query(models.DailySchedule)
        .filter(
            models.DailySchedule.student_id == student_id,
            models.DailySchedule.schedule_date < today,
            models.DailySchedule.status == "SCHEDULED",
        )
        .all()
    )

    for task in old_tasks:
        task.status = "MISSED"

    db.commit()


def _get_subject(db: Session):
    subject = (
        db.query(models.Subject)
        .filter(models.Subject.subject_name.ilike("Math%"))
        .first()
    )

    if not subject:
        subject = db.query(models.Subject).order_by(models.Subject.id.asc()).first()

    return subject


def _get_chapter(db: Session, chapter_id: Optional[int]):
    if not chapter_id:
        return None
    return db.query(models.Chapter).filter(models.Chapter.id == chapter_id).first()


def _get_topic(db: Session, topic_id: Optional[int]):
    if not topic_id:
        return None
    return db.query(models.ChapterTopic).filter(models.ChapterTopic.id == topic_id).first()


def _get_retention_states(db: Session, student_id: int) -> List:
    return (
        db.query(models.RetentionState)
        .filter(models.RetentionState.student_id == student_id)
        .all()
    )


def _retention_map_by_chapter(db: Session, student_id: int) -> Dict[int, object]:
    states = _get_retention_states(db, student_id)
    return {state.chapter_id: state for state in states if state.chapter_id is not None}


def _completed_topic_ids(db: Session, student_id: int) -> set:
    rows = (
        db.query(models.DailySchedule.topic_id)
        .filter(
            models.DailySchedule.student_id == student_id,
            models.DailySchedule.topic_id.isnot(None),
            models.DailySchedule.status == "COMPLETED",
        )
        .all()
    )
    return {r[0] for r in rows if r[0] is not None}


def _future_scheduled_topic_ids(db: Session, student_id: int, start_date: date) -> set:
    rows = (
        db.query(models.DailySchedule.topic_id)
        .filter(
            models.DailySchedule.student_id == student_id,
            models.DailySchedule.schedule_date >= start_date,
            models.DailySchedule.topic_id.isnot(None),
            models.DailySchedule.status == "SCHEDULED",
        )
        .all()
    )
    return {r[0] for r in rows if r[0] is not None}


def _clear_future_scheduled_tasks(db: Session, student_id: int, start_date: date):
    """
    Delete only future SCHEDULED tasks.
    Completed history is safe.
    """
    (
        db.query(models.DailySchedule)
        .filter(
            models.DailySchedule.student_id == student_id,
            models.DailySchedule.schedule_date >= start_date,
            models.DailySchedule.status == "SCHEDULED",
        )
        .delete()
    )
    db.commit()


def _build_study_candidates(db: Session, student_id: int) -> List[Dict]:
    subject = _get_subject(db)
    if not subject:
        return []

    completed_topics = _completed_topic_ids(db, student_id)

    topics = (
        db.query(models.ChapterTopic)
        .filter(
            models.ChapterTopic.subject_id == subject.id,
            models.ChapterTopic.is_active == True,
        )
        .order_by(models.ChapterTopic.chapter_id.asc(), models.ChapterTopic.topic_order.asc())
        .all()
    )

    candidates = []
    for topic in topics:
        if topic.id in completed_topics:
            continue

        chapter = _get_chapter(db, topic.chapter_id)

        candidates.append({
            "subject_id": topic.subject_id,
            "chapter_id": topic.chapter_id,
            "topic_id": topic.id,
            "chapter_name": chapter.chapter_name if chapter else f"Chapter {topic.chapter_id}",
            "topic_name": topic.topic_name,
            "topic_order": topic.topic_order,
            "estimated_minutes": topic.estimated_minutes or 30,
            "difficulty": topic.difficulty or "Medium",
            "section": "STUDY",
            "task_type": "STUDY_NEW",
            "priority": 10,
            "reason": "Continue next topic in sequence.",
        })

    return candidates


def _build_revision_candidates(db: Session, student_id: int) -> List[Dict]:
    states = _get_retention_states(db, student_id)

    if not states:
        return []

    candidates = []

    for state in states:
        retention = _safe_float(getattr(state, "retention", 0), 0)
        priority_score = _safe_float(getattr(state, "priority_score", 0), 0)
        last_score = _safe_float(getattr(state, "last_score", 0), 0)
        weak_chapter = bool(getattr(state, "weak_chapter", False))

        needs_revision = (
            weak_chapter
            or retention < 60
            or priority_score >= 50
            or last_score < 60
        )

        if not needs_revision:
            continue

        topics = (
            db.query(models.ChapterTopic)
            .filter(
                models.ChapterTopic.chapter_id == state.chapter_id,
                models.ChapterTopic.is_active == True,
            )
            .order_by(models.ChapterTopic.topic_order.asc())
            .all()
        )

        chapter = _get_chapter(db, state.chapter_id)

        for topic in topics:
            base_priority = priority_score

            if retention < 40:
                base_priority += 40

            if last_score < 40:
                base_priority += 35

            if weak_chapter:
                base_priority += 30

            if topic.difficulty == "Hard":
                base_priority += 10
            elif topic.difficulty == "Medium":
                base_priority += 5

            if last_score < 40:
                task_type = "RETEST"
                reason = "Low marks detected. Revise this topic and take a retest."
            elif retention < 40:
                task_type = "REVISION"
                reason = "Retention is below 40%. Revise this topic first."
            elif priority_score >= 50:
                task_type = "REVISION"
                reason = "High priority score. This topic needs revision."
            else:
                task_type = "REVISION"
                reason = "Average performance. Light revision recommended."

            candidates.append({
                "subject_id": topic.subject_id,
                "chapter_id": topic.chapter_id,
                "topic_id": topic.id,
                "chapter_name": chapter.chapter_name if chapter else f"Chapter {topic.chapter_id}",
                "topic_name": topic.topic_name,
                "topic_order": topic.topic_order,
                "estimated_minutes": min(topic.estimated_minutes or 30, 30),
                "difficulty": topic.difficulty or "Medium",
                "section": "REVISION",
                "task_type": task_type,
                "priority": base_priority,
                "reason": reason,
                "retention": retention,
                "priority_score": priority_score,
                "last_score": last_score,
                "weak_chapter": weak_chapter,
            })

    candidates.sort(key=lambda x: (-x["priority"], x["chapter_id"], x["topic_order"]))
    return candidates


def _build_carry_forward_candidates(db: Session, student_id: int) -> List[Dict]:
    today = date.today()

    missed_tasks = (
        db.query(models.DailySchedule)
        .filter(
            models.DailySchedule.student_id == student_id,
            models.DailySchedule.schedule_date < today,
            models.DailySchedule.status == "MISSED",
            models.DailySchedule.topic_id.isnot(None),
        )
        .order_by(models.DailySchedule.schedule_date.asc(), models.DailySchedule.id.asc())
        .all()
    )

    candidates = []

    used_topic_ids = set()

    for task in missed_tasks:
        if task.topic_id in used_topic_ids:
            continue

        used_topic_ids.add(task.topic_id)

        topic = _get_topic(db, task.topic_id)
        chapter = _get_chapter(db, task.chapter_id)

        candidates.append({
            "subject_id": task.subject_id,
            "chapter_id": task.chapter_id,
            "topic_id": task.topic_id,
            "chapter_name": chapter.chapter_name if chapter else f"Chapter {task.chapter_id}",
            "topic_name": topic.topic_name if topic else f"Topic {task.topic_id}",
            "topic_order": topic.topic_order if topic else 0,
            "estimated_minutes": task.planned_minutes or 30,
            "difficulty": topic.difficulty if topic else "Medium",
            "section": "REVISION",
            "task_type": "CATCH_UP",
            "priority": 999 + (task.carry_count or 0),
            "reason": "This topic was missed earlier, so it is shifted to today.",
            "carried_from_schedule_id": task.id,
            "carry_count": (task.carry_count or 0) + 1,
        })

    return candidates


def _create_task(
    db: Session,
    student_id: int,
    task_date: date,
    candidate: Dict,
    start_time_value: time,
) -> models.DailySchedule:
    planned_minutes = _safe_int(candidate.get("estimated_minutes"), 30)
    end_time_value = _add_minutes_to_time(start_time_value, planned_minutes)

    schedule_title = f"{candidate.get('chapter_name')} - {candidate.get('topic_name')}"

    task = models.DailySchedule(
        student_id=student_id,
        schedule_date=task_date,
        subject_id=candidate.get("subject_id"),
        chapter_id=candidate.get("chapter_id"),
        topic_id=candidate.get("topic_id"),
        section=candidate.get("section", "STUDY"),
        task_type=candidate.get("task_type", "STUDY_NEW"),
        schedule_title=schedule_title,
        planned_minutes=planned_minutes,
        start_time=start_time_value,
        end_time=end_time_value,
        status="SCHEDULED",
        reason=candidate.get("reason"),
        carried_from_schedule_id=candidate.get("carried_from_schedule_id"),
        carry_count=candidate.get("carry_count", 0),
    )

    db.add(task)
    db.flush()

    return task


def _fill_tasks_for_day(
    db: Session,
    student,
    task_date: date,
    study_candidates: List[Dict],
    revision_candidates: List[Dict],
    carry_candidates: List[Dict],
    used_topic_ids: set,
):
    student_id = student.id

    has_revision_work = bool(revision_candidates or carry_candidates)
    budget = _get_study_revision_budget(student, has_revision_work)

    study_budget = budget["study_minutes"]
    revision_budget = budget["revision_minutes"]

    current_time = time(DEFAULT_START_HOUR, DEFAULT_START_MINUTE)

    created_tasks = []

    day_used_topic_ids = set()

    # 1. Revision section first: carry-forward tasks get highest priority
    revision_pool = carry_candidates + revision_candidates
    revision_pool.sort(key=lambda x: (-x.get("priority", 0), x["chapter_id"], x.get("topic_order", 0)))

    remaining_revision = revision_budget

    for candidate in revision_pool:
        topic_id = candidate.get("topic_id")

        if not topic_id:
            continue

        duplicate_key = (topic_id, candidate.get("task_type"))

        if duplicate_key in day_used_topic_ids:
            continue

        planned = _safe_int(candidate.get("estimated_minutes"), 30)

        if remaining_revision <= 0:
            break

        if planned > remaining_revision and remaining_revision >= 20:
            candidate["estimated_minutes"] = remaining_revision
            planned = remaining_revision

        if planned > remaining_revision:
            continue

        task = _create_task(db, student_id, task_date, candidate, current_time)
        created_tasks.append(task)

        current_time = _add_minutes_to_time(current_time, planned)
        remaining_revision -= planned
        day_used_topic_ids.add(duplicate_key)

        if candidate.get("task_type") == "CATCH_UP":
            used_topic_ids.add(topic_id)

    # 2. Study section
    remaining_study = study_budget

    for candidate in study_candidates:
        topic_id = candidate.get("topic_id")

        if not topic_id:
            continue

        if topic_id in used_topic_ids:
            continue

        planned = _safe_int(candidate.get("estimated_minutes"), 30)

        if remaining_study <= 0:
            break

        if planned > remaining_study and remaining_study >= 20:
            candidate["estimated_minutes"] = remaining_study
            planned = remaining_study

        if planned > remaining_study:
            continue

        task = _create_task(db, student_id, task_date, candidate, current_time)
        created_tasks.append(task)

        current_time = _add_minutes_to_time(current_time, planned)
        remaining_study -= planned
        used_topic_ids.add(topic_id)

    return created_tasks


def generate_smart_schedule(db: Session, student, days: int = 7, start_date: Optional[date] = None) -> Dict:
    """
    Main smart scheduling engine.

    Handles:
    - New student with no test history
    - 70% study and 30% revision
    - Missed tasks carry-forward
    - Weak chapter priority
    - Low/average/high marks
    - Less available time
    - Too many weak chapters
    - Repeated delayed chapters
    """

    if start_date is None:
        start_date = date.today()

    _mark_old_tasks_missed(db, student.id)
    _clear_future_scheduled_tasks(db, student.id, start_date)

    study_candidates = _build_study_candidates(db, student.id)
    revision_candidates = _build_revision_candidates(db, student.id)
    carry_candidates = _build_carry_forward_candidates(db, student.id)

    used_topic_ids = _completed_topic_ids(db, student.id)

    created_total = 0

    for i in range(days):
        task_date = start_date + timedelta(days=i)

        created_tasks = _fill_tasks_for_day(
            db=db,
            student=student,
            task_date=task_date,
            study_candidates=study_candidates,
            revision_candidates=revision_candidates,
            carry_candidates=carry_candidates if i == 0 else [],
            used_topic_ids=used_topic_ids,
        )

        created_total += len(created_tasks)

    db.commit()

    return {
        "message": "Smart schedule generated successfully",
        "created_tasks": created_total,
        "start_date": str(start_date),
        "days": days,
    }


def _task_to_dict(db: Session, task) -> Dict:
    subject = None
    chapter = None
    topic = None

    if task.subject_id:
        subject = db.query(models.Subject).filter(models.Subject.id == task.subject_id).first()

    if task.chapter_id:
        chapter = db.query(models.Chapter).filter(models.Chapter.id == task.chapter_id).first()

    if task.topic_id:
        topic = db.query(models.ChapterTopic).filter(models.ChapterTopic.id == task.topic_id).first()

    return {
        "id": task.id,
        "schedule_date": str(task.schedule_date),
        "section": task.section or "STUDY",
        "task_type": task.task_type,
        "title": task.schedule_title,
        "subject_id": task.subject_id,
        "subject_name": subject.subject_name if subject else "Maths",
        "chapter_id": task.chapter_id,
        "chapter_name": chapter.chapter_name if chapter else f"Chapter {task.chapter_id}",
        "topic_id": task.topic_id,
        "topic_name": topic.topic_name if topic else None,
        "topic_order": topic.topic_order if topic else None,
        "difficulty": topic.difficulty if topic else None,
        "planned_minutes": task.planned_minutes,
        "start_time": str(task.start_time)[:5] if task.start_time else None,
        "end_time": str(task.end_time)[:5] if task.end_time else None,
        "status": task.status,
        "reason": task.reason,
        "carry_count": task.carry_count or 0,
        "is_completed": task.status == "COMPLETED",
    }


def _get_tasks_for_date(db: Session, student_id: int, target_date: date) -> List:
    return (
        db.query(models.DailySchedule)
        .filter(
            models.DailySchedule.student_id == student_id,
            models.DailySchedule.schedule_date == target_date,
        )
        .order_by(
            models.DailySchedule.start_time.asc().nullslast(),
            models.DailySchedule.id.asc(),
        )
        .all()
    )


def _build_day_block(db: Session, student_id: int, target_date: date, label: str) -> Dict:
    tasks = _get_tasks_for_date(db, student_id, target_date)

    task_dicts = [_task_to_dict(db, task) for task in tasks]

    study_tasks = [t for t in task_dicts if t["section"] == "STUDY"]
    revision_tasks = [t for t in task_dicts if t["section"] == "REVISION"]

    completed = len([t for t in task_dicts if t["status"] == "COMPLETED"])
    total = len(task_dicts)

    return {
        "label": label,
        "date": str(target_date),
        "weekday": _week_name(target_date),
        "total_tasks": total,
        "completed_tasks": completed,
        "pending_tasks": max(total - completed, 0),
        "study_tasks": study_tasks,
        "revision_tasks": revision_tasks,
        "tasks": task_dicts,
    }


def _build_stats(db: Session, student) -> Dict:
    states = _get_retention_states(db, student.id)

    if not states:
        return {
            "overall_retention": 0,
            "weak_topics": 0,
            "upcoming_reviews": 0,
            "learning_stability": 0,
            "study_hours_per_day": _safe_float(getattr(student, "study_hours_per_day", 0), 0),
        }

    retentions = [_safe_float(getattr(s, "retention", 0), 0) for s in states]
    stabilities = [_safe_float(getattr(s, "stability", 0), 0) for s in states]

    weak_count = len([
        s for s in states
        if bool(getattr(s, "weak_chapter", False)) or _safe_float(getattr(s, "retention", 0), 0) < 40
    ])

    today = date.today()
    tomorrow = today + timedelta(days=1)

    upcoming_reviews = (
        db.query(models.DailySchedule)
        .filter(
            models.DailySchedule.student_id == student.id,
            models.DailySchedule.schedule_date.in_([today, tomorrow]),
            models.DailySchedule.section == "REVISION",
            models.DailySchedule.status == "SCHEDULED",
        )
        .count()
    )

    return {
        "overall_retention": round(sum(retentions) / len(retentions), 1) if retentions else 0,
        "weak_topics": weak_count,
        "upcoming_reviews": upcoming_reviews,
        "learning_stability": round(sum(stabilities) / len(stabilities), 1) if stabilities else 0,
        "study_hours_per_day": _safe_float(getattr(student, "study_hours_per_day", 0), 0),
    }


def _build_ai_recommendation(db: Session, student) -> Dict:
    states = _get_retention_states(db, student.id)

    if not states:
        return {
            "title": "Start with your first chapter",
            "message": "You have no test history yet. Start with Chapter 1 topics, complete today’s plan, and then take a chapter test.",
            "action": "Start Study",
        }

    states.sort(
        key=lambda s: (
            -_safe_float(getattr(s, "priority_score", 0), 0),
            _safe_float(getattr(s, "retention", 100), 100),
        )
    )

    top = states[0]

    chapter_name = getattr(top, "chapter_name", None) or f"Chapter {top.chapter_id}"
    retention = _safe_float(getattr(top, "retention", 0), 0)
    priority = _safe_float(getattr(top, "priority_score", 0), 0)
    last_score = _safe_float(getattr(top, "last_score", 0), 0)

    if last_score < 40:
        message = f"Your latest score in {chapter_name} is low. Revise the scheduled topics first, then take a retest."
    elif retention < 40:
        message = f"Your retention for {chapter_name} is below 40%. Revise this chapter today before studying new topics."
    elif priority >= 70:
        message = f"{chapter_name} has the highest priority score. Complete its revision task before moving to new topics."
    else:
        message = f"Your progress is stable. Follow today’s study plan and complete the pending topics."

    return {
        "title": f"Recommended: {chapter_name}",
        "message": message,
        "action": "Review Now",
        "retention": retention,
        "priority_score": priority,
        "last_score": last_score,
    }


def get_schedule_dashboard(db: Session, student) -> Dict:
    _mark_old_tasks_missed(db, student.id)

    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    existing_today_tomorrow = (
        db.query(models.DailySchedule)
        .filter(
            models.DailySchedule.student_id == student.id,
            models.DailySchedule.schedule_date.in_([today, tomorrow]),
        )
        .count()
    )

    if existing_today_tomorrow == 0:
        generate_smart_schedule(db, student, days=7, start_date=today)

    budget = _get_study_revision_budget(
        student,
        has_revision_work=bool(_build_revision_candidates(db, student.id) or _build_carry_forward_candidates(db, student.id)),
    )

    return {
        "student": {
            "id": student.id,
            "name": student.name,
            "study_hours_per_day": _safe_float(getattr(student, "study_hours_per_day", 0), 0),
        },
        "budget": budget,
        "stats": _build_stats(db, student),
        "ai_recommendation": _build_ai_recommendation(db, student),
        "days": [
            _build_day_block(db, student.id, yesterday, "Yesterday"),
            _build_day_block(db, student.id, today, "Today"),
            _build_day_block(db, student.id, tomorrow, "Tomorrow"),
        ],
    }


def toggle_schedule_task(db: Session, student, task_id: int) -> Dict:
    task = (
        db.query(models.DailySchedule)
        .filter(
            models.DailySchedule.id == task_id,
            models.DailySchedule.student_id == student.id,
        )
        .first()
    )

    if not task:
        raise ValueError("Schedule task not found")

    if task.status == "COMPLETED":
        task.status = "SCHEDULED"
        task.completed_at = None
    else:
        task.status = "COMPLETED"
        task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)

    return {
        "message": "Task updated successfully",
        "task": _task_to_dict(db, task),
    }


def mark_task_missed(db: Session, student, task_id: int) -> Dict:
    task = (
        db.query(models.DailySchedule)
        .filter(
            models.DailySchedule.id == task_id,
            models.DailySchedule.student_id == student.id,
        )
        .first()
    )

    if not task:
        raise ValueError("Schedule task not found")

    task.status = "MISSED"
    db.commit()
    db.refresh(task)

    return {
        "message": "Task marked as missed",
        "task": _task_to_dict(db, task),
    }