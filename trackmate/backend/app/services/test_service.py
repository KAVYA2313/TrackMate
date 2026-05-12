import random
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Question, Test, TestQuestion


def normalize_difficulty(difficulty: str) -> str:
    value = str(difficulty or "Easy").strip().capitalize()

    if value not in ["Easy", "Medium", "Hard"]:
        raise HTTPException(
            status_code=400,
            detail="Difficulty must be Easy, Medium, or Hard",
        )

    return value


def split_question_count(total_questions: int, chapter_ids: list[int]) -> dict[int, int]:
    """
    Example:
    total_questions = 10
    chapter_ids = [1, 6]

    Output:
    chapter 1 = 5 questions
    chapter 6 = 5 questions
    """
    if total_questions <= 0:
        raise HTTPException(
            status_code=400,
            detail="Question count must be greater than 0",
        )

    if not chapter_ids:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one chapter",
        )

    base_count = total_questions // len(chapter_ids)
    extra_count = total_questions % len(chapter_ids)

    chapter_question_count = {}

    for index, chapter_id in enumerate(chapter_ids):
        chapter_question_count[chapter_id] = base_count + (1 if index < extra_count else 0)

    return chapter_question_count


def generate_test_service(
    db: Session,
    student_id: int,
    subject_id: int,
    chapter_ids: list[int],
    question_count: int,
    difficulty: str = "Easy",
):
    difficulty = normalize_difficulty(difficulty)

    chapter_question_count = split_question_count(
        total_questions=question_count,
        chapter_ids=chapter_ids,
    )

    selected_questions = []

    for chapter_id, required_count in chapter_question_count.items():
        questions = (
            db.query(Question)
            .filter(
                Question.subject_id == subject_id,
                Question.chapter_id == chapter_id,
                Question.difficulty == difficulty,
            )
            .all()
        )

        if len(questions) < required_count:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Not enough {difficulty} questions for chapter_id {chapter_id}. "
                    f"Required {required_count}, available {len(questions)}."
                ),
            )

        selected_questions.extend(random.sample(questions, required_count))

    random.shuffle(selected_questions)

    test = Test(
        student_id=student_id,
        subject_id=subject_id,
        total_questions=len(selected_questions),
        total_marks=len(selected_questions),
        status="GENERATED",
    )

    db.add(test)
    db.commit()
    db.refresh(test)

    for question in selected_questions:
        test_question = TestQuestion(
            test_id=test.id,
            question_id=question.id,
            chapter_id=question.chapter_id,
        )
        db.add(test_question)

    db.commit()

    question_output = []

    for question in selected_questions:
        question_output.append(
            {
                "question_id": question.id,
                "chapter_id": question.chapter_id,
                "question_text": question.question_text,
                "option_a": question.option_a,
                "option_b": question.option_b,
                "option_c": question.option_c,
                "option_d": question.option_d,
                "difficulty": question.difficulty,
            }
        )

    return {
        "test_id": test.id,
        "student_id": student_id,
        "subject_id": subject_id,
        "difficulty": difficulty,
        "selected_chapters": chapter_ids,
        "requested_questions": question_count,
        "total_questions": len(question_output),
        "questions": question_output,
        "message": f"{difficulty} level test generated successfully",
    }