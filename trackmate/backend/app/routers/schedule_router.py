from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_student

from app.services.ai_schedule_service import (
    generate_openai_week_schedule,
    get_ai_schedule_dashboard,
    get_whole_week_plan,
    submit_today_schedule,
)

from app.services.schedule_service import (
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
        return get_ai_schedule_dashboard(db, current_student)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-ai-week")
def generate_ai_week_schedule(
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        return generate_openai_week_schedule(
            db=db,
            student=current_student,
            reason="manual_generate_button",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whole-plan")
def whole_plan(
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        return get_whole_week_plan(db, current_student)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit-today")
def submit_today(
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        return submit_today_schedule(db, current_student)
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