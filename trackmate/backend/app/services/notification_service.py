from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Notification, RetentionState, Student
from app.services.email_service import send_weak_chapter_email


EMAIL_COOLDOWN_HOURS = 24


def should_send_email(notification: Notification) -> bool:
    if not notification.email_sent:
        return True

    if not notification.last_email_sent_at:
        return True

    last_sent = notification.last_email_sent_at

    if last_sent.tzinfo is None:
        last_sent = last_sent.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) - last_sent >= timedelta(hours=EMAIL_COOLDOWN_HOURS)


def create_or_update_weak_chapter_notification(
    db: Session,
    retention_state: RetentionState,
) -> Notification | None:
    student = (
        db.query(Student)
        .filter(Student.id == retention_state.student_id)
        .first()
    )

    if not student:
        return None

    title = "Weak Chapter Reminder"

    message = (
        f"{retention_state.chapter_name} retention is "
        f"{round(retention_state.retention or 0, 2)}%. "
        f"This chapter is weak. Revise it today."
    )

    notification = (
        db.query(Notification)
        .filter(
            Notification.student_id == retention_state.student_id,
            Notification.chapter_id == retention_state.chapter_id,
            Notification.notification_type == "WEAK_RETENTION",
            Notification.is_read == False,
        )
        .first()
    )

    if not notification:
        notification = Notification(
            student_id=retention_state.student_id,
            chapter_id=retention_state.chapter_id,
            notification_type="WEAK_RETENTION",
            title=title,
            message=message,
            retention=retention_state.retention or 0,
            priority_score=retention_state.priority_score or 0,
            is_read=False,
            email_sent=False,
        )
        db.add(notification)
        db.flush()
    else:
        notification.title = title
        notification.message = message
        notification.retention = retention_state.retention or 0
        notification.priority_score = retention_state.priority_score or 0

    if should_send_email(notification):
        send_weak_chapter_email(
            to_email=student.email,
            student_name=student.name,
            chapter_name=retention_state.chapter_name,
            retention=round(retention_state.retention or 0, 2),
            priority_score=round(retention_state.priority_score or 0, 2),
        )

        notification.email_sent = True
        notification.last_email_sent_at = datetime.now(timezone.utc)

    return notification