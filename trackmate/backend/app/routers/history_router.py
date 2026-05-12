from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_student


router = APIRouter(
    prefix="/history",
    tags=["History"]
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        if isinstance(value, Decimal):
            return round(float(value), 2)

        return round(float(value), 2)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default

        return int(value)
    except Exception:
        return default


def _date_to_string(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    return str(value)


def _performance_label(percentage: float) -> str:
    if percentage >= 75:
        return "Strong"
    if percentage >= 40:
        return "Average"
    return "Weak"


def _performance_badge(percentage: float) -> str:
    if percentage >= 75:
        return "good"
    if percentage >= 40:
        return "warn"
    return "bad"


def _build_recommendation(chapter_performance: List[Dict], tests: List[Dict]) -> Dict:
    if not tests:
        return {
            "title": "Start your first test",
            "message": "No test history found yet. Generate a chapter-wise test first, then TrackMate will show your performance history.",
            "type": "info"
        }

    if not chapter_performance:
        latest = tests[0]
        return {
            "title": "Keep testing regularly",
            "message": f"Your latest score is {latest['percentage']}%. Continue giving chapter-wise tests so TrackMate can detect weak chapters properly.",
            "type": "info"
        }

    weakest = sorted(
        chapter_performance,
        key=lambda item: (
            item.get("average_percentage", 0),
            item.get("retention", 100),
            -item.get("attempt_count", 0)
        )
    )[0]

    chapter_name = weakest.get("chapter_name", "a chapter")
    avg = weakest.get("average_percentage", 0)
    retention = weakest.get("retention", 0)
    priority = weakest.get("priority_score", 0)

    if avg < 40:
        return {
            "title": f"Revise {chapter_name}",
            "message": f"Your average score in {chapter_name} is only {avg}%. Revise this chapter first and then take a retest.",
            "type": "danger",
            "chapter_name": chapter_name,
            "average_percentage": avg,
            "retention": retention,
            "priority_score": priority
        }

    if retention < 40:
        return {
            "title": f"Memory drop in {chapter_name}",
            "message": f"Your retention for {chapter_name} is {retention}%. Add this chapter to revision before studying new topics.",
            "type": "warning",
            "chapter_name": chapter_name,
            "average_percentage": avg,
            "retention": retention,
            "priority_score": priority
        }

    return {
        "title": "Good progress",
        "message": "Your test performance is stable. Continue your schedule and keep taking chapter-wise tests for better accuracy.",
        "type": "success"
    }


@router.get("/dashboard")
def get_history_dashboard(
    db: Session = Depends(get_db),
    current_student=Depends(get_current_student),
):
    try:
        student_id = current_student.id

        tests_query = text("""
            SELECT
                t.id,
                t.student_id,
                t.subject_id,
                COALESCE(s.subject_name, 'Maths') AS subject_name,
                COALESCE(t.total_questions, 0) AS total_questions,
                COALESCE(t.obtained_marks, 0) AS obtained_marks,
                COALESCE(t.total_marks, t.total_questions, 0) AS total_marks,
                COALESCE(t.percentage, 0) AS percentage,
                t.status,
                t.created_at,
                t.submitted_at
            FROM tests t
            LEFT JOIN subjects s ON s.id = t.subject_id
            WHERE t.student_id = :student_id
              AND t.status = 'SUBMITTED'
            ORDER BY COALESCE(t.submitted_at, t.created_at) DESC, t.id DESC
        """)

        test_rows = db.execute(
            tests_query,
            {"student_id": student_id}
        ).mappings().all()

        chapters_query = text("""
            SELECT
                t.id AS test_id,
                c.id AS chapter_id,
                COALESCE(c.chapter_name, CONCAT('Chapter ', tq.chapter_id)) AS chapter_name,
                COUNT(tq.question_id) AS total_questions,
                COALESCE(SUM(CASE WHEN ta.is_correct = TRUE THEN 1 ELSE 0 END), 0) AS obtained_marks,
                ROUND(
                    (
                        COALESCE(SUM(CASE WHEN ta.is_correct = TRUE THEN 1 ELSE 0 END), 0)::numeric
                        / NULLIF(COUNT(tq.question_id), 0)
                    ) * 100,
                    2
                ) AS percentage
            FROM tests t
            JOIN test_questions tq ON tq.test_id = t.id
            LEFT JOIN test_answers ta
                ON ta.test_id = t.id
               AND ta.question_id = tq.question_id
            LEFT JOIN chapters c ON c.id = tq.chapter_id
            WHERE t.student_id = :student_id
              AND t.status = 'SUBMITTED'
            GROUP BY t.id, c.id, c.chapter_name, tq.chapter_id
            ORDER BY t.id DESC, c.id ASC
        """)

        chapter_rows = db.execute(
            chapters_query,
            {"student_id": student_id}
        ).mappings().all()

        chapter_map: Dict[int, List[Dict]] = {}

        for row in chapter_rows:
            test_id = _safe_int(row["test_id"])

            chapter_map.setdefault(test_id, []).append({
                "chapter_id": _safe_int(row["chapter_id"]),
                "chapter_name": row["chapter_name"],
                "total_questions": _safe_int(row["total_questions"]),
                "obtained_marks": _safe_int(row["obtained_marks"]),
                "percentage": _safe_float(row["percentage"]),
                "label": _performance_label(_safe_float(row["percentage"])),
                "badge": _performance_badge(_safe_float(row["percentage"])),
            })

        tests: List[Dict] = []

        for row in test_rows:
            test_id = _safe_int(row["id"])
            percentage = _safe_float(row["percentage"])
            obtained_marks = _safe_int(row["obtained_marks"])
            total_marks = _safe_int(row["total_marks"])

            tests.append({
                "id": test_id,
                "subject_id": _safe_int(row["subject_id"]),
                "subject_name": row["subject_name"],
                "total_questions": _safe_int(row["total_questions"]),
                "obtained_marks": obtained_marks,
                "total_marks": total_marks,
                "percentage": percentage,
                "status": row["status"],
                "created_at": _date_to_string(row["created_at"]),
                "submitted_at": _date_to_string(row["submitted_at"]),
                "date_label": _date_to_string(row["submitted_at"] or row["created_at"]),
                "performance_label": _performance_label(percentage),
                "performance_badge": _performance_badge(percentage),
                "chapters": chapter_map.get(test_id, []),
            })

        performance_query = text("""
            SELECT
                c.id AS chapter_id,
                COALESCE(c.chapter_name, CONCAT('Chapter ', tq.chapter_id)) AS chapter_name,
                COUNT(DISTINCT t.id) AS attempt_count,
                COUNT(tq.question_id) AS total_questions,
                COALESCE(SUM(CASE WHEN ta.is_correct = TRUE THEN 1 ELSE 0 END), 0) AS obtained_marks,
                ROUND(
                    (
                        COALESCE(SUM(CASE WHEN ta.is_correct = TRUE THEN 1 ELSE 0 END), 0)::numeric
                        / NULLIF(COUNT(tq.question_id), 0)
                    ) * 100,
                    2
                ) AS average_percentage
            FROM tests t
            JOIN test_questions tq ON tq.test_id = t.id
            LEFT JOIN test_answers ta
                ON ta.test_id = t.id
               AND ta.question_id = tq.question_id
            LEFT JOIN chapters c ON c.id = tq.chapter_id
            WHERE t.student_id = :student_id
              AND t.status = 'SUBMITTED'
            GROUP BY c.id, c.chapter_name, tq.chapter_id
            ORDER BY average_percentage ASC, attempt_count DESC
        """)

        performance_rows = db.execute(
            performance_query,
            {"student_id": student_id}
        ).mappings().all()

        retention_query = text("""
            SELECT
                chapter_id,
                chapter_name,
                COALESCE(retention, 0) AS retention,
                COALESCE(priority_score, 0) AS priority_score,
                COALESCE(last_score, 0) AS last_score,
                COALESCE(weak_chapter, FALSE) AS weak_chapter
            FROM retention_states
            WHERE student_id = :student_id
        """)

        retention_rows = db.execute(
            retention_query,
            {"student_id": student_id}
        ).mappings().all()

        retention_map: Dict[int, Dict] = {}

        for row in retention_rows:
            retention_map[_safe_int(row["chapter_id"])] = {
                "retention": _safe_float(row["retention"]),
                "priority_score": _safe_float(row["priority_score"]),
                "last_score": _safe_float(row["last_score"]),
                "weak_chapter": bool(row["weak_chapter"]),
            }

        chapter_performance: List[Dict] = []

        for row in performance_rows:
            chapter_id = _safe_int(row["chapter_id"])
            avg = _safe_float(row["average_percentage"])
            retention_data = retention_map.get(chapter_id, {})

            chapter_performance.append({
                "chapter_id": chapter_id,
                "chapter_name": row["chapter_name"],
                "attempt_count": _safe_int(row["attempt_count"]),
                "total_questions": _safe_int(row["total_questions"]),
                "obtained_marks": _safe_int(row["obtained_marks"]),
                "average_percentage": avg,
                "label": _performance_label(avg),
                "badge": _performance_badge(avg),
                "retention": retention_data.get("retention", 0),
                "priority_score": retention_data.get("priority_score", 0),
                "last_score": retention_data.get("last_score", avg),
                "weak_chapter": retention_data.get("weak_chapter", avg < 40),
            })

        total_tests = len(tests)
        total_questions = sum(item["total_questions"] for item in tests)
        total_obtained = sum(item["obtained_marks"] for item in tests)
        total_marks = sum(item["total_marks"] for item in tests)

        average_percentage = (
            round(sum(item["percentage"] for item in tests) / total_tests, 2)
            if total_tests > 0
            else 0
        )

        best_test = max(tests, key=lambda item: item["percentage"], default=None)
        latest_test = tests[0] if tests else None

        strong_count = len([item for item in tests if item["percentage"] >= 75])
        average_count = len([item for item in tests if 40 <= item["percentage"] < 75])
        weak_count = len([item for item in tests if item["percentage"] < 40])

        trend = []

        for item in reversed(tests):
            trend.append({
                "test_id": item["id"],
                "label": f"Test {item['id']}",
                "date": item["date_label"],
                "percentage": item["percentage"],
            })

        summary = {
            "total_tests": total_tests,
            "total_questions": total_questions,
            "total_obtained_marks": total_obtained,
            "total_marks": total_marks,
            "average_percentage": average_percentage,
            "best_percentage": best_test["percentage"] if best_test else 0,
            "best_test_id": best_test["id"] if best_test else None,
            "latest_percentage": latest_test["percentage"] if latest_test else 0,
            "latest_test_id": latest_test["id"] if latest_test else None,
            "strong_tests": strong_count,
            "average_tests": average_count,
            "weak_tests": weak_count,
        }

        distribution = {
            "strong": strong_count,
            "average": average_count,
            "weak": weak_count,
            "total": total_tests,
        }

        recommendation = _build_recommendation(chapter_performance, tests)

        return {
            "student": {
                "id": current_student.id,
                "name": current_student.name,
                "email": current_student.email,
            },
            "summary": summary,
            "distribution": distribution,
            "trend": trend,
            "chapter_performance": chapter_performance,
            "tests": tests,
            "recommendation": recommendation,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))