from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailySchedule
from app.schemas import GenerateScheduleRequest, MarkScheduleRequest
from app.services.schedule_service import generate_schedule_service

router = APIRouter(prefix="/schedule", tags=["Schedule"])


@router.post("/generate")
def generate_schedule(request: GenerateScheduleRequest, db: Session = Depends(get_db)):
    return generate_schedule_service(
        db=db,
        student_id=request.student_id,
        subject_id=request.subject_id,
        start_date=request.start_date,
        days=request.days,
        daily_minutes=request.daily_minutes,
    )


@router.get("/today/{student_id}")
def get_today_schedule(student_id: int, db: Session = Depends(get_db)):
    today = date.today()
    return (
        db.query(DailySchedule)
        .filter(DailySchedule.student_id == student_id, DailySchedule.schedule_date == today)
        .order_by(DailySchedule.id)
        .all()
    )


@router.get("/week/{student_id}")
def get_week_schedule(student_id: int, db: Session = Depends(get_db)):
    today = date.today()
    return (
        db.query(DailySchedule)
        .filter(DailySchedule.student_id == student_id, DailySchedule.schedule_date >= today)
        .order_by(DailySchedule.schedule_date, DailySchedule.id)
        .all()
    )


@router.patch("/{schedule_id}/status")
def mark_schedule_status(schedule_id: int, request: MarkScheduleRequest, db: Session = Depends(get_db)):
    item = db.query(DailySchedule).filter(DailySchedule.id == schedule_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Schedule item not found")

    item.status = request.status
    db.commit()
    db.refresh(item)
    return item
