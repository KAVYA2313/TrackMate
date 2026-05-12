from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Question, StudentChapterProgress, Test, TestAnswer, TestQuestion
from app.services.retention_service import (
    get_level,
    reminder_needed,
    update_retention_after_chapter_test,
)


DIFFICULTY_WEIGHT = {
    "Easy": 1,
    "Medium": 2,
    "Hard": 3,
}


def normalize_answer(answer: str) -> str:
    return str(answer or "").upper().strip()


def normalize_difficulty(difficulty: str) -> str:
    value = str(difficulty or "Medium").strip().capitalize()

    if value not in ["Easy", "Medium", "Hard"]:
        return "Medium"

    return value


def choose_chapter_difficulty(difficulty_counts: dict) -> str:
    """
    Calculates chapter difficulty from questions used in that chapter.

    Example:
    3 Easy + 2 Hard = Medium/Hard based on average.
    """
    if not difficulty_counts:
        return "Medium"

    total_count = sum(difficulty_counts.values())

    if total_count <= 0:
        return "Medium"

    weighted_sum = 0

    for difficulty, count in difficulty_counts.items():
        normalized = normalize_difficulty(difficulty)
        weighted_sum += DIFFICULTY_WEIGHT.get(normalized, 2) * count

    avg = weighted_sum / total_count

    if avg >= 2.5:
        return "Hard"

    if avg >= 1.5:
        return "Medium"

    return "Easy"


def submit_test_service(db: Session, test_id: int, answers: list):
    test = db.query(Test).filter(Test.id == test_id).first()

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if test.status == "SUBMITTED":
        raise HTTPException(status_code=400, detail="This test is already submitted")

    test_questions = (
        db.query(TestQuestion)
        .filter(TestQuestion.test_id == test_id)
        .all()
    )

    if not test_questions:
        raise HTTPException(status_code=400, detail="No questions found for this test")

    required_question_ids = {item.question_id for item in test_questions}

    submitted_question_ids = [item.question_id for item in answers]
    submitted_question_id_set = set(submitted_question_ids)

    if len(submitted_question_ids) != len(submitted_question_id_set):
        raise HTTPException(status_code=400, detail="Duplicate question answers found")

    missing_questions = required_question_ids - submitted_question_id_set
    extra_questions = submitted_question_id_set - required_question_ids

    if missing_questions:
        raise HTTPException(
            status_code=400,
            detail=f"Please answer all questions. Missing question IDs: {list(missing_questions)}",
        )

    if extra_questions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid questions submitted: {list(extra_questions)}",
        )

    answer_map = {
        item.question_id: normalize_answer(item.selected_answer)
        for item in answers
    }

    obtained_marks = 0
    chapter_score_map = {}

    for test_question in test_questions:
        question = db.query(Question).filter(Question.id == test_question.question_id).first()

        if not question:
            raise HTTPException(
                status_code=404,
                detail=f"Question ID {test_question.question_id} not found",
            )

        selected = answer_map.get(question.id)
        correct = normalize_answer(question.correct_answer)

        if selected not in ["A", "B", "C", "D"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid selected answer for question {question.id}. Use A/B/C/D only.",
            )

        is_correct = selected == correct

        if is_correct:
            obtained_marks += 1

        test_answer = TestAnswer(
            test_id=test_id,
            question_id=question.id,
            selected_answer=selected,
            correct_answer=correct,
            is_correct=is_correct,
        )
        db.add(test_answer)

        if question.chapter_id not in chapter_score_map:
            chapter_score_map[question.chapter_id] = {
                "correct": 0,
                "total": 0,
                "difficulty_counts": {},
            }

        chapter_score_map[question.chapter_id]["total"] += 1

        if is_correct:
            chapter_score_map[question.chapter_id]["correct"] += 1

        difficulty = normalize_difficulty(question.difficulty)
        chapter_score_map[question.chapter_id]["difficulty_counts"][difficulty] = (
            chapter_score_map[question.chapter_id]["difficulty_counts"].get(difficulty, 0) + 1
        )

    total_marks = len(test_questions)
    percentage = round((obtained_marks / total_marks) * 100, 2) if total_marks > 0 else 0.0

    test.obtained_marks = obtained_marks
    test.total_marks = total_marks
    test.percentage = percentage
    test.status = "SUBMITTED"
    test.submitted_at = datetime.now(timezone.utc)

    chapter_results = []
    retention_results = []

    for chapter_id, score_data in chapter_score_map.items():
        chapter_obtained = score_data["correct"]
        chapter_total = score_data["total"]

        chapter_percentage = round(
            (chapter_obtained / chapter_total) * 100,
            2,
        ) if chapter_total > 0 else 0.0

        chapter_difficulty = choose_chapter_difficulty(score_data["difficulty_counts"])

        retention_result = update_retention_after_chapter_test(
            db=db,
            student_id=test.student_id,
            subject_id=test.subject_id,
            chapter_id=chapter_id,
            difficulty=chapter_difficulty,
            obtained_marks=chapter_obtained,
            total_marks=chapter_total,
        )

        progress = (
            db.query(StudentChapterProgress)
            .filter(
                StudentChapterProgress.student_id == test.student_id,
                StudentChapterProgress.subject_id == test.subject_id,
                StudentChapterProgress.chapter_id == chapter_id,
            )
            .first()
        )

        if not progress:
            progress = StudentChapterProgress(
                student_id=test.student_id,
                subject_id=test.subject_id,
                chapter_id=chapter_id,
                last_score=0,
                retention=0,
                memory_loss=100,
                test_count=0,
                status="NOT_STARTED",
            )
            db.add(progress)

        progress.last_score = retention_result["last_score"]
        progress.retention = retention_result["retention"]
        progress.memory_loss = round(100 - retention_result["retention"], 2)
        progress.test_count = (progress.test_count or 0) + 1
        progress.status = get_level(chapter_percentage)

        chapter_results.append(
            {
                "chapter_id": chapter_id,
                "score": chapter_percentage,
                "status": progress.status,
                "retention": retention_result["retention"],
                "weak_chapter": retention_result["weak_chapter"],
                "priority_score": retention_result["priority_score"],
                "reminder_needed": reminder_needed(retention_result["retention"]),
                "recommended_action": retention_result["recommended_action"],
            }
        )

        retention_results.append(retention_result)

    db.commit()

    return {
        "test_id": test.id,
        "student_id": test.student_id,
        "subject_id": test.subject_id,
        "obtained_marks": obtained_marks,
        "total_marks": total_marks,
        "percentage": percentage,
        "result_level": get_level(percentage),
        "chapter_results": chapter_results,
        "retention_results": retention_results,
        "next_step": "Retention updated successfully. Now scheduling can use priority_score.",
    }