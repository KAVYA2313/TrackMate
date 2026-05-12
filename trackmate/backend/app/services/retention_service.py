import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import Chapter, RetentionState, Subject
from app.services.notification_service import create_or_update_weak_chapter_notification


WEAK_RETENTION_LIMIT = 40.0

MIN_STABILITY = 2.0
DEFAULT_STABILITY = 5.0
MAX_STABILITY = 30.0

BASE_RETENTION_FOR_LOW_CONFIDENCE_TEST = 50.0


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def normalize_difficulty(difficulty: Optional[str]) -> str:
    value = str(difficulty or "Medium").strip().capitalize()

    if value not in ["Easy", "Medium", "Hard"]:
        return "Medium"

    return value


def calculate_score_percentage(obtained_marks: float, total_marks: float) -> float:
    if total_marks <= 0:
        return 0.0

    return round((obtained_marks / total_marks) * 100, 2)


def get_level(score_percentage: float) -> str:
    if score_percentage < 40:
        return "WEAK"

    if score_percentage < 70:
        return "AVERAGE"

    return "STRONG"


def reminder_needed(retention: float) -> bool:
    return retention < WEAK_RETENTION_LIMIT


def get_days_passed(last_activity_at) -> float:
    """
    Calculates days passed from last retention update/test activity.
    """
    if not last_activity_at:
        return 0.0

    now = datetime.now(timezone.utc)

    if last_activity_at.tzinfo is None:
        last_activity_at = last_activity_at.replace(tzinfo=timezone.utc)

    diff = now - last_activity_at
    return round(max(0.0, diff.total_seconds() / 86400), 2)


def calculate_test_confidence(question_count: int) -> float:
    """
    More questions = more confidence in score.

    1-2 questions  -> 0.40 confidence
    3-4 questions  -> 0.60 confidence
    5-7 questions  -> 0.80 confidence
    8+ questions   -> 1.00 confidence
    """
    if question_count <= 0:
        return 0.0

    if question_count <= 2:
        return 0.40

    if question_count <= 4:
        return 0.60

    if question_count <= 7:
        return 0.80

    return 1.00


def calculate_decayed_retention(
    old_retention: float,
    stability: float,
    days_passed: float,
) -> float:
    """
    Ebbinghaus-style forgetting curve.

    Formula:
    decayed_retention = old_retention * e^(-days_passed / stability)

    Higher stability means slower forgetting.
    """
    old_retention = clamp(old_retention, 0.0, 100.0)
    stability = clamp(stability, MIN_STABILITY, MAX_STABILITY)
    days_passed = max(0.0, days_passed)

    decayed = old_retention * math.exp(-days_passed / stability)

    return round(clamp(decayed, 0.0, 100.0), 2)


def calculate_retention_after_test(
    is_first_test: bool,
    previous_retention: float,
    previous_stability: float,
    days_passed: float,
    latest_score: float,
    question_count: int,
) -> Dict[str, float]:
    """
    Product-level retention update.

    First test:
        If enough questions, retention = score.
        If very few questions, score is adjusted using confidence.

    Repeated test:
        First decay old retention.
        Then combine decayed retention with latest score.

    latest test has more importance because it shows current reality.
    """
    latest_score = clamp(latest_score, 0.0, 100.0)
    confidence = calculate_test_confidence(question_count)

    if is_first_test:
        if confidence >= 1.0:
            retention = latest_score
        else:
            retention = (
                BASE_RETENTION_FOR_LOW_CONFIDENCE_TEST * (1 - confidence)
                + latest_score * confidence
            )

        return {
            "retention": round(clamp(retention, 0.0, 100.0), 2),
            "decayed_retention": 0.0,
            "test_confidence": confidence,
        }

    decayed_retention = calculate_decayed_retention(
        old_retention=previous_retention,
        stability=previous_stability,
        days_passed=days_passed,
    )

    latest_weight = 0.65 * confidence
    old_weight = 1 - latest_weight

    retention = (decayed_retention * old_weight) + (latest_score * latest_weight)

    return {
        "retention": round(clamp(retention, 0.0, 100.0), 2),
        "decayed_retention": decayed_retention,
        "test_confidence": confidence,
    }


def get_score_gain(score_percentage: float) -> float:
    """
    Score impact on stability.
    High score increases stability.
    Low score can reduce stability slightly.
    """
    if score_percentage >= 90:
        return 4.0

    if score_percentage >= 75:
        return 3.0

    if score_percentage >= 60:
        return 2.0

    if score_percentage >= 40:
        return 1.0

    return -1.5


def get_difficulty_mastery_bonus(difficulty: str, score_percentage: float) -> float:
    """
    Difficulty bonus is given only when student performs well.
    If student scores low in hard test, do not reward difficulty.
    """
    difficulty = normalize_difficulty(difficulty)

    if score_percentage < 70:
        return 0.0

    if difficulty == "Hard":
        return 1.2

    if difficulty == "Medium":
        return 0.6

    return 0.0


def calculate_stability(
    previous_stability: float,
    score_percentage: float,
    difficulty: str,
    revision_count: int,
    question_count: int,
) -> float:
    """
    Stability = how strongly the chapter is stored in memory.
    Higher stability = slower forgetting.
    """
    previous_stability = clamp(
        safe_float(previous_stability, DEFAULT_STABILITY),
        MIN_STABILITY,
        MAX_STABILITY,
    )

    confidence = calculate_test_confidence(question_count)

    score_gain = get_score_gain(score_percentage)
    difficulty_bonus = get_difficulty_mastery_bonus(difficulty, score_percentage)
    revision_bonus = min(2.5, math.log(revision_count + 1) * 0.8)

    total_change = (score_gain + difficulty_bonus + revision_bonus) * confidence

    new_stability = previous_stability + total_change

    return round(clamp(new_stability, MIN_STABILITY, MAX_STABILITY), 2)


def is_weak_chapter(retention: float, last_score: float) -> bool:
    """
    Chapter is weak if memory is low OR latest test score is low.
    """
    return retention < WEAK_RETENTION_LIMIT or last_score < 40


def get_score_penalty(last_score: float) -> float:
    if last_score < 40:
        return 25.0

    if last_score < 70:
        return 12.0

    return 0.0


def get_difficulty_penalty(difficulty: str, last_score: float, retention: float) -> float:
    """
    Hard/Medium difficulty increases priority only when chapter is not strong.
    If student already has high score and high retention, no difficulty penalty.
    """
    difficulty = normalize_difficulty(difficulty)

    if last_score >= 70 and retention >= 70:
        return 0.0

    if difficulty == "Hard":
        return 10.0

    if difficulty == "Medium":
        return 5.0

    return 0.0


def get_recommended_action(retention: float, last_score: float) -> str:
    if last_score < 40:
        return "Relearn chapter basics and retake test"

    if retention < 40:
        return "Revise chapter because memory is dropping"

    if last_score < 70:
        return "Practice more questions and do quick revision"

    if retention < 70:
        return "Light revision recommended"

    return "Chapter is strong, keep for later revision"


def calculate_priority_score(
    retention: float,
    stability: float,
    revision_count: int,
    last_score: float,
    difficulty: str,
    weak_chapter: bool,
    question_count: int,
    days_passed: float,
) -> float:
    """
    Priority score decides schedule order.

    Higher priority_score = chapter should come earlier in schedule.
    """
    memory_loss = 100 - retention

    score_penalty = get_score_penalty(last_score)
    difficulty_penalty = get_difficulty_penalty(difficulty, last_score, retention)
    weak_bonus = 20.0 if weak_chapter else 0.0
    stability_penalty = max(0.0, 10.0 - stability)

    confidence = calculate_test_confidence(question_count)

    # If student scored high but test had very few questions, do not fully trust it.
    low_confidence_penalty = 0.0
    if confidence < 0.70 and last_score >= 70:
        low_confidence_penalty = 8.0

    # If many days passed, chapter should slowly become more urgent.
    stale_bonus = min(15.0, days_passed * 1.2)

    # Revisions reduce priority only if chapter is not weak.
    if weak_chapter:
        revision_relief = min(4.0, revision_count * 0.5)
    else:
        revision_relief = min(10.0, revision_count * 1.5)

    priority_score = (
        memory_loss
        + score_penalty
        + difficulty_penalty
        + weak_bonus
        + stability_penalty
        + low_confidence_penalty
        + stale_bonus
        - revision_relief
    )

    return round(clamp(priority_score, 0.0, 150.0), 2)


def update_retention_after_chapter_test(
    db: Session,
    student_id: int,
    subject_id: int,
    chapter_id: int,
    difficulty: str,
    obtained_marks: float,
    total_marks: float,
) -> Dict[str, Any]:
    """
    Main retention update function.

    This runs after test submit for each chapter.
    """
    difficulty = normalize_difficulty(difficulty)

    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()

    subject_name = subject.subject_name if subject else "Unknown"
    chapter_name = chapter.chapter_name if chapter else f"Chapter {chapter_id}"

    score_percentage = calculate_score_percentage(obtained_marks, total_marks)
    question_count = int(total_marks)

    existing_state = (
        db.query(RetentionState)
        .filter(
            RetentionState.student_id == student_id,
            RetentionState.subject_id == subject_id,
            RetentionState.chapter_id == chapter_id,
        )
        .first()
    )

    is_first_test = existing_state is None

    if existing_state:
        previous_retention = safe_float(existing_state.retention, 50.0)
        previous_stability = safe_float(existing_state.stability, DEFAULT_STABILITY)
        revision_count = int(existing_state.revision_count or 0) + 1
        days_passed = get_days_passed(existing_state.last_activity_at)
    else:
        previous_retention = 0.0
        previous_stability = DEFAULT_STABILITY
        revision_count = 1
        days_passed = 0.0

    retention_info = calculate_retention_after_test(
        is_first_test=is_first_test,
        previous_retention=previous_retention,
        previous_stability=previous_stability,
        days_passed=days_passed,
        latest_score=score_percentage,
        question_count=question_count,
    )

    retention = retention_info["retention"]

    stability = calculate_stability(
        previous_stability=previous_stability,
        score_percentage=score_percentage,
        difficulty=difficulty,
        revision_count=revision_count,
        question_count=question_count,
    )

    weak_chapter = is_weak_chapter(
        retention=retention,
        last_score=score_percentage,
    )

    priority_score = calculate_priority_score(
        retention=retention,
        stability=stability,
        revision_count=revision_count,
        last_score=score_percentage,
        difficulty=difficulty,
        weak_chapter=weak_chapter,
        question_count=question_count,
        days_passed=days_passed,
    )

    now = datetime.now(timezone.utc)

    if not existing_state:
        existing_state = RetentionState(
            student_id=student_id,
            subject_id=subject_id,
            chapter_id=chapter_id,
            subject=subject_name,
            chapter_name=chapter_name,
        )
        db.add(existing_state)

    existing_state.subject = subject_name
    existing_state.chapter_name = chapter_name
    existing_state.difficulty = difficulty
    existing_state.stability = stability
    existing_state.revision_count = revision_count
    existing_state.last_score = score_percentage
    existing_state.retention = retention
    existing_state.weak_chapter = weak_chapter
    existing_state.priority_score = priority_score
    existing_state.last_activity_at = now
    existing_state.last_decay_at = now

    if weak_chapter:
        create_or_update_weak_chapter_notification(db, existing_state)

    return {
        "student_id": student_id,
        "subject_id": subject_id,
        "chapter_id": chapter_id,
        "subject": subject_name,
        "chapter_name": chapter_name,
        "difficulty": difficulty,
        "score_percentage": score_percentage,
        "stability": stability,
        "revision_count": revision_count,
        "last_score": score_percentage,
        "retention": retention,
        "weak_chapter": weak_chapter,
        "priority_score": priority_score,
        "recommended_action": get_recommended_action(retention, score_percentage),
        "days_passed": days_passed,
        "decayed_retention": retention_info["decayed_retention"],
        "test_confidence": retention_info["test_confidence"],
        "last_activity_at": now.isoformat(),
        "logic_used": "first_test_score_based" if is_first_test else "decay_plus_latest_score",
    }

def refresh_retention_for_student(db: Session, student_id: int) -> Dict[str, Any]:
    """
    This function runs when:
    1. Student opens dashboard
    2. Daily scheduler runs

    It applies daily forgetting decay.
    It does NOT update last_activity_at because opening dashboard is not studying.
    It updates last_decay_at to avoid double decay.
    """
    records = (
        db.query(RetentionState)
        .filter(RetentionState.student_id == student_id)
        .all()
    )

    now = datetime.now(timezone.utc)
    refreshed = []

    for record in records:
        decay_base_time = record.last_decay_at or record.last_activity_at
        days_passed = get_days_passed(decay_base_time)

        if days_passed <= 0:
            refreshed.append(
                {
                    "chapter_id": record.chapter_id,
                    "chapter_name": record.chapter_name,
                    "retention": record.retention,
                    "weak_chapter": record.weak_chapter,
                    "priority_score": record.priority_score,
                    "days_passed": days_passed,
                    "message": "No decay needed yet",
                }
            )
            continue

        decayed_retention = calculate_decayed_retention(
            old_retention=safe_float(record.retention),
            stability=safe_float(record.stability, DEFAULT_STABILITY),
            days_passed=days_passed,
        )

        weak_chapter = is_weak_chapter(
            retention=decayed_retention,
            last_score=safe_float(record.last_score),
        )

        priority_score = calculate_priority_score(
            retention=decayed_retention,
            stability=safe_float(record.stability, DEFAULT_STABILITY),
            revision_count=int(record.revision_count or 0),
            last_score=safe_float(record.last_score),
            difficulty=record.difficulty,
            weak_chapter=weak_chapter,
            question_count=10,
            days_passed=days_passed,
        )

        record.retention = decayed_retention
        record.weak_chapter = weak_chapter
        record.priority_score = priority_score

        # This is only decay checkpoint, not student learning activity.
        record.last_decay_at = now

        if weak_chapter:
            create_or_update_weak_chapter_notification(db, record)

        refreshed.append(
            {
                "chapter_id": record.chapter_id,
                "chapter_name": record.chapter_name,
                "retention": record.retention,
                "weak_chapter": record.weak_chapter,
                "priority_score": record.priority_score,
                "days_passed": days_passed,
                "recommended_action": get_recommended_action(
                    record.retention,
                    safe_float(record.last_score),
                ),
            }
        )

    db.commit()

    return {
        "student_id": student_id,
        "updated_count": len(refreshed),
        "retention_data": refreshed,
    }