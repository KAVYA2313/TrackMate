from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_student
from app.services.ai_revision_service import generate_revision_plan_for_topic


router = APIRouter(
    prefix="/revision",
    tags=["AI Revision"]
)


@router.get("/topic/{topic_id}")
def get_revision_plan(
    topic_id: int,
    force_new: bool = False,
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        return generate_revision_plan_for_topic(
            db=db,
            student_id=current_student.id,
            topic_id=topic_id,
            force_new=force_new,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))