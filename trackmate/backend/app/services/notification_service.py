from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.services.llm_service import generate_weak_chapter_notification


EMAIL_COOLDOWN_HOURS = 24
LLM_REGENERATE_HOURS = 12


def _now():
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return round(float(value), 2)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _to_aware_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _get_student(db: Session, student_id: int):
    return (
        db.query(models.Student)
        .filter(models.Student.id == student_id)
        .first()
    )


def _get_chapter(db: Session, chapter_id: int):
    return (
        db.query(models.Chapter)
        .filter(models.Chapter.id == chapter_id)
        .first()
    )


def _get_subject(db: Session, subject_id: Optional[int]):
    if not subject_id:
        return None

    return (
        db.query(models.Subject)
        .filter(models.Subject.id == subject_id)
        .first()
    )


def _subject_name_from_chapter(db: Session, chapter) -> str:
    if not chapter:
        return "Maths"

    subject_id = getattr(chapter, "subject_id", None)
    subject = _get_subject(db, subject_id)

    if subject:
        return getattr(subject, "subject_name", None) or "Maths"

    return "Maths"


def _chapter_name(chapter, chapter_id: int) -> str:
    if not chapter:
        return f"Chapter {chapter_id}"

    return (
        getattr(chapter, "chapter_name", None)
        or getattr(chapter, "name", None)
        or f"Chapter {chapter_id}"
    )


def _student_name(student) -> str:
    if not student:
        return "Student"

    return (
        getattr(student, "name", None)
        or getattr(student, "student_name", None)
        or "Student"
    )


def _student_email(student) -> Optional[str]:
    if not student:
        return None

    return getattr(student, "email", None)


def _extract_notification_input(
    record_or_student_id,
    chapter_id,
    retention,
    priority_score,
):
    """
    Supports:
    create_or_update_weak_chapter_notification(db, retention_state_record)

    Also supports:
    create_or_update_weak_chapter_notification(
        db,
        student_id=1,
        chapter_id=2,
        retention=35,
        priority_score=80
    )
    """

    if hasattr(record_or_student_id, "student_id"):
        record = record_or_student_id

        return {
            "record": record,
            "student_id": _safe_int(getattr(record, "student_id", None)),
            "subject_id": _safe_int(getattr(record, "subject_id", None), None),
            "chapter_id": _safe_int(getattr(record, "chapter_id", None)),
            "retention": _safe_float(getattr(record, "retention", retention)),
            "priority_score": _safe_float(
                getattr(record, "priority_score", priority_score)
            ),
            "last_score": _safe_float(getattr(record, "last_score", 0)),
            "difficulty": getattr(record, "difficulty", None) or "Medium",
            "chapter_name": getattr(record, "chapter_name", None),
        }

    return {
        "record": None,
        "student_id": _safe_int(record_or_student_id),
        "subject_id": None,
        "chapter_id": _safe_int(chapter_id),
        "retention": _safe_float(retention),
        "priority_score": _safe_float(priority_score),
        "last_score": 0,
        "difficulty": "Medium",
        "chapter_name": None,
    }


def _find_existing_unread_notification(
    db: Session,
    student_id: int,
    chapter_id: int,
):
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.student_id == student_id,
            models.Notification.chapter_id == chapter_id,
            models.Notification.notification_type == "WEAK_CHAPTER",
            models.Notification.is_read == False,
        )
        .order_by(models.Notification.created_at.desc())
        .first()
    )


def _should_regenerate_llm_message(existing_notification, new_retention: float) -> bool:
    if not existing_notification:
        return True

    old_message = getattr(existing_notification, "message", None)

    if not old_message:
        return True

    old_retention = _safe_float(
        getattr(existing_notification, "retention", None),
        -1,
    )

    if abs(old_retention - new_retention) >= 8:
        return True

    updated_at = _to_aware_datetime(
        getattr(existing_notification, "updated_at", None)
    )

    created_at = _to_aware_datetime(
        getattr(existing_notification, "created_at", None)
    )

    last_time = updated_at or created_at

    if not last_time:
        return True

    return (_now() - last_time) >= timedelta(hours=LLM_REGENERATE_HOURS)


def _should_send_email(notification) -> bool:
    if not notification:
        return False

    email_sent = bool(getattr(notification, "email_sent", False))

    last_email_sent_at = _to_aware_datetime(
        getattr(notification, "last_email_sent_at", None)
    )

    if not email_sent:
        return True

    if not last_email_sent_at:
        return True

    return (_now() - last_email_sent_at) >= timedelta(hours=EMAIL_COOLDOWN_HOURS)


def _call_email_service(
    student,
    title: str,
    message: str,
    chapter_name: str,
    retention: float,
) -> bool:
    """
    Defensive email call.
    If email service function name/arguments differ, notification still works.
    """

    email = _student_email(student)
    name = _student_name(student)

    if not email:
        return False

    try:
        from app.services import email_service
    except Exception:
        return False

    possible_function_names = [
        "send_weak_chapter_email",
        "send_weak_chapter_reminder_email",
        "send_retention_email",
        "send_notification_email",
    ]

    for fn_name in possible_function_names:
        fn = getattr(email_service, fn_name, None)

        if not callable(fn):
            continue

        keyword_payload = {
            "to_email": email,
            "email": email,
            "student_email": email,
            "student_name": name,
            "name": name,
            "chapter_name": chapter_name,
            "chapter": chapter_name,
            "retention": retention,
            "retention_score": retention,
            "title": title,
            "subject": title,
            "message": message,
            "body": message,
        }

        try:
            import inspect

            signature = inspect.signature(fn)
            params = signature.parameters

            if any(param.kind == param.VAR_KEYWORD for param in params.values()):
                fn(**keyword_payload)
                return True

            accepted_kwargs = {
                key: value
                for key, value in keyword_payload.items()
                if key in params
            }

            if accepted_kwargs:
                fn(**accepted_kwargs)
                return True

        except TypeError:
            pass
        except Exception:
            return False

        try:
            fn(email, name, chapter_name, retention, message)
            return True
        except TypeError:
            pass
        except Exception:
            return False

        try:
            fn(email, title, message)
            return True
        except TypeError:
            pass
        except Exception:
            return False

    return False


def create_or_update_weak_chapter_notification(
    db: Session,
    record_or_student_id=None,
    chapter_id: Optional[int] = None,
    retention: Optional[float] = None,
    priority_score: Optional[float] = None,
    student_id: Optional[int] = None,
):
    """
    Called by retention_service.py after chapter performance update.

    It creates a student-friendly OpenAI notification like:
    "Revise Linear Equations"
    "Spend 20 minutes on the scheduled topics, then try a short practice test."
    """

    if student_id is not None and record_or_student_id is None:
        record_or_student_id = student_id

    data = _extract_notification_input(
        record_or_student_id=record_or_student_id,
        chapter_id=chapter_id,
        retention=retention,
        priority_score=priority_score,
    )

    student_id_value = data["student_id"]
    chapter_id_value = data["chapter_id"]
    retention_value = data["retention"]
    priority_score_value = data["priority_score"]
    last_score_value = data["last_score"]
    difficulty_value = data["difficulty"]

    if not student_id_value or not chapter_id_value:
        return {
            "created": False,
            "updated": False,
            "reason": "student_id or chapter_id missing",
        }

    student = _get_student(db, student_id_value)
    chapter = _get_chapter(db, chapter_id_value)

    if not student:
        return {
            "created": False,
            "updated": False,
            "reason": "student not found",
        }

    subject_name = _subject_name_from_chapter(db, chapter)
    chapter_name = data.get("chapter_name") or _chapter_name(
        chapter,
        chapter_id_value,
    )

    existing = _find_existing_unread_notification(
        db=db,
        student_id=student_id_value,
        chapter_id=chapter_id_value,
    )

    regenerate_llm = _should_regenerate_llm_message(
        existing_notification=existing,
        new_retention=retention_value,
    )

    if regenerate_llm:
        generated = generate_weak_chapter_notification(
            student_name=_student_name(student),
            subject_name=subject_name,
            chapter_name=chapter_name,
            retention_score=retention_value,
            priority_score=priority_score_value,
            last_score=last_score_value,
            difficulty=difficulty_value,
        )

        title = generated.get("title") or f"Revise {chapter_name}"
        message = generated.get("message") or (
            f"Spend a short focused session on {chapter_name}, "
            f"then try a quick practice test."
        )

        action = generated.get("action") or "Review now"
        llm_used = bool(generated.get("llm_used", False))
        llm_model = generated.get("model", "fallback")
    else:
        title = existing.title
        message = existing.message
        action = "Review now"
        llm_used = False
        llm_model = "reused_existing_message"

    now = _now()

    if existing:
        notification = existing
        notification.title = title
        notification.message = message
        notification.retention = retention_value
        notification.priority_score = priority_score_value
        notification.is_read = False

        if hasattr(notification, "updated_at"):
            notification.updated_at = now

        created = False
        updated = True
    else:
        notification = models.Notification(
            student_id=student_id_value,
            chapter_id=chapter_id_value,
            notification_type="WEAK_CHAPTER",
            title=title,
            message=message,
            retention=retention_value,
            priority_score=priority_score_value,
            is_read=False,
            email_sent=False,
            created_at=now,
            updated_at=now,
        )

        db.add(notification)
        db.flush()

        created = True
        updated = False

    email_sent_now = False

    if _should_send_email(notification):
        email_sent_now = _call_email_service(
            student=student,
            title=title,
            message=message,
            chapter_name=chapter_name,
            retention=retention_value,
        )

        if email_sent_now:
            notification.email_sent = True
            notification.last_email_sent_at = now

            if hasattr(notification, "updated_at"):
                notification.updated_at = now

    db.flush()

    return {
        "created": created,
        "updated": updated,
        "notification_id": notification.id,
        "title": title,
        "message": message,
        "action": action,
        "retention": retention_value,
        "priority_score": priority_score_value,
        "email_sent_now": email_sent_now,
        "llm_used": llm_used,
        "llm_model": llm_model,
    }