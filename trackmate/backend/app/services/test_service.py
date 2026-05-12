import random

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Chapter, Question, Test, TestQuestion


def normalize_difficulty(difficulty: str) -> str:
    value = str(difficulty or "Easy").strip().capitalize()

    if value not in ["Easy", "Medium", "Hard"]:
        raise HTTPException(
            status_code=400,
            detail="Difficulty must be Easy, Medium, or Hard",
        )

    return value


def normalize_chapter_ids(chapter_ids: list[int]) -> list[int]:
    """
    Remove duplicate chapter IDs while preserving selected order.
    """
    cleaned_ids = []

    for chapter_id in chapter_ids:
        try:
            chapter_id = int(chapter_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chapter id: {chapter_id}",
            )

        if chapter_id not in cleaned_ids:
            cleaned_ids.append(chapter_id)

    if not cleaned_ids:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one chapter",
        )

    return cleaned_ids


def split_question_count(total_questions: int, chapter_ids: list[int]) -> dict[int, int]:
    """
    Example:
    total_questions = 10
    chapter_ids = [1, 2, 3]

    Output:
    chapter 1 = 4 questions
    chapter 2 = 3 questions
    chapter 3 = 3 questions
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
        chapter_question_count[chapter_id] = base_count + (
            1 if index < extra_count else 0
        )

    return chapter_question_count


def get_chapter_map(db: Session, subject_id: int, chapter_ids: list[int]) -> dict[int, Chapter]:
    chapters = (
        db.query(Chapter)
        .filter(
            Chapter.subject_id == subject_id,
            Chapter.id.in_(chapter_ids),
        )
        .all()
    )

    chapter_map = {chapter.id: chapter for chapter in chapters}

    missing_chapters = [chapter_id for chapter_id in chapter_ids if chapter_id not in chapter_map]

    if missing_chapters:
        raise HTTPException(
            status_code=404,
            detail=f"These chapters do not exist for subject {subject_id}: {missing_chapters}",
        )

    return chapter_map


def generate_test_service(
    db: Session,
    student_id: int,
    subject_id: int,
    chapter_ids: list[int],
    question_count: int,
    difficulty: str = "Easy",
):
    difficulty = normalize_difficulty(difficulty)
    chapter_ids = normalize_chapter_ids(chapter_ids)

    chapter_map = get_chapter_map(
        db=db,
        subject_id=subject_id,
        chapter_ids=chapter_ids,
    )

    chapter_question_count = split_question_count(
        total_questions=question_count,
        chapter_ids=chapter_ids,
    )

    selected_questions = []
    generation_summary = []

    for chapter_id, required_count in chapter_question_count.items():
        chapter = chapter_map[chapter_id]

        questions = (
            db.query(Question)
            .filter(
                Question.subject_id == subject_id,
                Question.chapter_id == chapter_id,
                func.lower(Question.difficulty) == difficulty.lower(),
            )
            .all()
        )

        available_count = len(questions)

        generation_summary.append(
            {
                "chapter_id": chapter_id,
                "chapter_order": chapter.chapter_order,
                "chapter_name": chapter.chapter_name,
                "difficulty": difficulty,
                "required_questions": required_count,
                "available_questions": available_count,
            }
        )

        if available_count < required_count:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Not enough {difficulty} questions for Chapter {chapter.chapter_order} "
                    f"({chapter.chapter_name}). Required {required_count}, available {available_count}."
                ),
            )

        selected_questions.extend(random.sample(questions, required_count))

    # Final safety check:
    # Every selected question must belong only to selected chapters and selected difficulty.
    for question in selected_questions:
        if question.chapter_id not in chapter_ids:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid question selected from chapter {question.chapter_id}",
            )

        if str(question.difficulty).strip().lower() != difficulty.lower():
            raise HTTPException(
                status_code=500,
                detail=f"Invalid difficulty selected: {question.difficulty}",
            )

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
        chapter = chapter_map[question.chapter_id]

        question_output.append(
            {
                "question_id": question.id,
                "chapter_id": question.chapter_id,
                "chapter_order": chapter.chapter_order,
                "chapter_name": chapter.chapter_name,
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
        "generation_summary": generation_summary,
        "questions": question_output,
        "message": (
            f"{difficulty} level test generated successfully from selected chapters only."
        ),
    }