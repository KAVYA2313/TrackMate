from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RetentionState
from app.services.retention_service import refresh_retention_for_student

router = APIRouter(prefix="/retention", tags=["Retention"])


@router.get("/{student_id}")
def get_student_retention(student_id: int, db: Session = Depends(get_db)):
    records = (
        db.query(RetentionState)
        .filter(RetentionState.student_id == student_id)
        .order_by(RetentionState.priority_score.desc())
        .all()
    )

    return {
        "student_id": student_id,
        "total": len(records),
        "retention_data": records,
    }


@router.get("/{student_id}/weak")
def get_weak_chapters(student_id: int, db: Session = Depends(get_db)):
    records = (
        db.query(RetentionState)
        .filter(
            RetentionState.student_id == student_id,
            RetentionState.weak_chapter == True,
        )
        .order_by(RetentionState.priority_score.desc())
        .all()
    )

    return {
        "student_id": student_id,
        "total": len(records),
        "weak_chapters": records,
    }


@router.post("/{student_id}/refresh")
def refresh_student_retention(student_id: int, db: Session = Depends(get_db)):
    return refresh_retention_for_student(db=db, student_id=student_id)