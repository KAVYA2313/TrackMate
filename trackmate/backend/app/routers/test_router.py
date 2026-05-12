from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_student
from app.models import Student, Test, TestAnswer
from app.schemas import GenerateTestRequest, SubmitTestRequest
from app.services.scoring_service import submit_test_service
from app.services.test_service import generate_test_service

router = APIRouter(prefix="/tests", tags=["Tests"])


@router.post("/generate")
def generate_test(
    request: GenerateTestRequest,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    return generate_test_service(
        db=db,
        student_id=current_student.id,
        subject_id=request.subject_id,
        chapter_ids=request.chapter_ids,
        question_count=request.question_count,
        difficulty=request.difficulty,
    )


@router.post("/{test_id}/submit")
def submit_test(
    test_id: int,
    request: SubmitTestRequest,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    test = db.query(Test).filter(Test.id == test_id).first()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if test.student_id != current_student.id:
        raise HTTPException(status_code=403, detail="You are not allowed to submit this test")

    return submit_test_service(
        db=db,
        test_id=test_id,
        answers=request.answers,
    )


@router.get("/history")
def get_my_test_history(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    tests = (
        db.query(Test)
        .filter(Test.student_id == current_student.id)
        .order_by(Test.created_at.desc())
        .all()
    )

    return {
        "student_id": current_student.id,
        "total": len(tests),
        "history": tests,
    }


@router.get("/{test_id}/result-details")
def get_test_result_details(
    test_id: int,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    test = db.query(Test).filter(Test.id == test_id).first()

    if not test:
        return {
            "error": "Test not found"
        }

    if test.student_id != current_student.id:
        raise HTTPException(status_code=403, detail="You are not allowed to view this test")

    answers = (
        db.query(TestAnswer)
        .filter(TestAnswer.test_id == test_id)
        .all()
    )

    return {
        "test": test,
        "answers": answers,
    }