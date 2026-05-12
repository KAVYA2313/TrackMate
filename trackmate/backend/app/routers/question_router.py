from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Question
from app.schemas import CreateQuestionRequest

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.post("/")
def create_question(request: CreateQuestionRequest, db: Session = Depends(get_db)):
    question = Question(
        subject_id=request.subject_id,
        chapter_id=request.chapter_id,
        question_text=request.question_text.strip(),
        option_a=request.option_a.strip(),
        option_b=request.option_b.strip(),
        option_c=request.option_c.strip(),
        option_d=request.option_d.strip(),
        correct_answer=request.correct_answer.upper(),
        difficulty=request.difficulty,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.get("/")
def get_questions(db: Session = Depends(get_db)):
    return db.query(Question).order_by(Question.id).all()


@router.get("/chapter/{chapter_id}")
def get_questions_by_chapter(chapter_id: int, db: Session = Depends(get_db)):
    return db.query(Question).filter(Question.chapter_id == chapter_id).order_by(Question.id).all()
