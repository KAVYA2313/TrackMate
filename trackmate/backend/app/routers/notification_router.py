from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_student
from app.models import Notification, Student
from app.services.retention_service import refresh_retention_for_student

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/me")
def get_my_notifications(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    notifications = (
        db.query(Notification)
        .filter(Notification.student_id == current_student.id)
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )

    unread_count = (
        db.query(Notification)
        .filter(
            Notification.student_id == current_student.id,
            Notification.is_read == False,
        )
        .count()
    )

    return {
        "student_id": current_student.id,
        "unread_count": unread_count,
        "notifications": notifications,
    }


@router.post("/refresh")
def refresh_and_get_notifications(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    refresh_result = refresh_retention_for_student(
        db=db,
        student_id=current_student.id,
    )

    notifications = (
        db.query(Notification)
        .filter(Notification.student_id == current_student.id)
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )

    unread_count = (
        db.query(Notification)
        .filter(
            Notification.student_id == current_student.id,
            Notification.is_read == False,
        )
        .count()
    )

    return {
        "refresh_result": refresh_result,
        "unread_count": unread_count,
        "notifications": notifications,
    }


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.student_id == current_student.id,
        )
        .first()
    )

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()

    return {
        "message": "Notification marked as read"
    }


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    notifications = (
        db.query(Notification)
        .filter(
            Notification.student_id == current_student.id,
            Notification.is_read == False,
        )
        .all()
    )

    for notification in notifications:
        notification.is_read = True

    db.commit()

    return {
        "message": "All notifications marked as read",
        "count": len(notifications),
    }