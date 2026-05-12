from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Chapter, DailySchedule, StudentChapterProgress


def _next_chapter_to_study(db: Session, student_id: int, subject_id: int):
    studied_ids = {
        row.chapter_id
        for row in db.query(StudentChapterProgress)
        .filter(StudentChapterProgress.student_id == student_id, StudentChapterProgress.subject_id == subject_id)
        .all()
    }

    chapters = (
        db.query(Chapter)
        .filter(Chapter.subject_id == subject_id)
        .order_by(Chapter.chapter_order)
        .all()
    )

    for chapter in chapters:
        if chapter.id not in studied_ids:
            return chapter

    return chapters[0] if chapters else None


def generate_schedule_service(db: Session, student_id: int, subject_id: int, start_date=None, days: int = 7, daily_minutes: int = 120):
    if start_date is None:
        start_date = date.today()

    # Keep old past records safe. Replace only schedule from start_date onward.
    db.query(DailySchedule).filter(
        DailySchedule.student_id == student_id,
        DailySchedule.subject_id == subject_id,
        DailySchedule.schedule_date >= start_date,
        DailySchedule.status == "SCHEDULED",
    ).delete(synchronize_session=False)

    weak_progress = (
        db.query(StudentChapterProgress)
        .filter(
            StudentChapterProgress.student_id == student_id,
            StudentChapterProgress.subject_id == subject_id,
            StudentChapterProgress.status == "WEAK",
        )
        .order_by(StudentChapterProgress.memory_loss.desc())
        .all()
    )

    average_progress = (
        db.query(StudentChapterProgress)
        .filter(
            StudentChapterProgress.student_id == student_id,
            StudentChapterProgress.subject_id == subject_id,
            StudentChapterProgress.status == "AVERAGE",
        )
        .order_by(StudentChapterProgress.memory_loss.desc())
        .all()
    )

    created_items = []
    backlog = list(weak_progress) + list(average_progress)

    for day_index in range(days):
        plan_date = start_date + timedelta(days=day_index)
        remaining = daily_minutes

        # Priority 1: weak/average chapters revision + retest.
        while backlog and remaining >= 60:
            progress = backlog.pop(0)
            task_type = "RETEST" if progress.status == "WEAK" else "REVISION"
            minutes = 90 if progress.status == "WEAK" and remaining >= 90 else 60

            item = DailySchedule(
                student_id=student_id,
                schedule_date=plan_date,
                subject_id=subject_id,
                chapter_id=progress.chapter_id,
                task_type=task_type,
                planned_minutes=minutes,
                reason=f"{progress.status} chapter. Last score {progress.last_score}%, retention {progress.retention}%.",
            )
            db.add(item)
            created_items.append(item)
            remaining -= minutes

        # Priority 2: new chapter if time remains.
        if remaining >= 60:
            next_chapter = _next_chapter_to_study(db, student_id, subject_id)
            if next_chapter:
                item = DailySchedule(
                    student_id=student_id,
                    schedule_date=plan_date,
                    subject_id=subject_id,
                    chapter_id=next_chapter.id,
                    task_type="STUDY_NEW",
                    planned_minutes=min(remaining, 120),
                    reason="Continue next chapter in sequence.",
                )
                db.add(item)
                created_items.append(item)

    db.commit()

    return {
        "message": "Schedule generated successfully",
        "student_id": student_id,
        "subject_id": subject_id,
        "start_date": str(start_date),
        "days": days,
        "total_items": len(created_items),
    }
