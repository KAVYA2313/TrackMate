from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_student
from app.services.ai_coach_service import ask_ai_coach


router = APIRouter(
    prefix="/coach",
    tags=["AI Coach"]
)


class CoachAskRequest(BaseModel):
    message: str


@router.post("/ask")
def ask_coach(
    payload: CoachAskRequest,
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        return ask_ai_coach(
            db=db,
            student_id=current_student.id,
            user_message=payload.message,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))