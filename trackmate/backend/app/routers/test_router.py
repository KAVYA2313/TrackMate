from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Test, TestAnswer
from app.schemas import GenerateTestRequest, SubmitTestRequest
from app.services.scoring_service import submit_test_service
from app.services.test_service import generate_test_service

router = APIRouter(prefix="/tests", tags=["Tests"])


@router.post("/generate")
def generate_test(request: GenerateTestRequest, db: Session = Depends(get_db)):
    return generate_test_service(
        db=db,
        student_id=request.student_id,
        subject_id=request.subject_id,
        chapter_ids=request.chapter_ids,
        question_count=request.question_count,
        difficulty=request.difficulty,
    )


@router.post("/{test_id}/submit")
def submit_test(test_id: int, request: SubmitTestRequest, db: Session = Depends(get_db)):
    return submit_test_service(
        db=db,
        test_id=test_id,
        answers=request.answers,
    )


@router.get("/history/{student_id}")
def get_test_history(student_id: int, db: Session = Depends(get_db)):
    tests = (
        db.query(Test)
        .filter(Test.student_id == student_id)
        .order_by(Test.created_at.desc())
        .all()
    )

    return {
        "student_id": student_id,
        "total": len(tests),
        "history": tests,
    }


@router.get("/{test_id}/result-details")
def get_test_result_details(test_id: int, db: Session = Depends(get_db)):
    test = db.query(Test).filter(Test.id == test_id).first()

    if not test:
        return {
            "error": "Test not found"
        }

    answers = (
        db.query(TestAnswer)
        .filter(TestAnswer.test_id == test_id)
        .all()
    )

    return {
        "test": test,
        "answers": answers,
    }