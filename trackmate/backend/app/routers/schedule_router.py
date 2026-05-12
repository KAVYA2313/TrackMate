from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_student
from app.services.schedule_service import (
    get_schedule_dashboard,
    generate_smart_schedule,
    toggle_schedule_task,
    mark_task_missed,
)

router = APIRouter(
    prefix="/schedule",
    tags=["Schedule"]
)


@router.get("/dashboard")
def schedule_dashboard(
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        return get_schedule_dashboard(db, current_student)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-smart")
def generate_schedule(
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        result = generate_smart_schedule(db, current_student, days=7)
        dashboard = get_schedule_dashboard(db, current_student)

        return {
            "message": result["message"],
            "created_tasks": result["created_tasks"],
            "dashboard": dashboard,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/task/{task_id}/toggle")
def toggle_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        return toggle_schedule_task(db, current_student, task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/task/{task_id}/missed")
def missed_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        return mark_task_missed(db, current_student, task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))