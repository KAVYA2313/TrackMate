from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models import Student
from app.services.retention_service import refresh_retention_for_student

scheduler = BackgroundScheduler()


def refresh_all_students_retention():
    db = SessionLocal()

    try:
        students = db.query(Student).filter(Student.is_active == True).all()

        for student in students:
            refresh_retention_for_student(db=db, student_id=student.id)

        print(f"Daily retention refresh completed for {len(students)} students")

    except Exception as error:
        print("Daily retention refresh failed:", error)

    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            refresh_all_students_retention,
            trigger="cron",
            hour=2,
            minute=0,
            id="daily_retention_refresh",
            replace_existing=True,
        )

        scheduler.start()
        print("TrackMate daily retention scheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("TrackMate daily retention scheduler stopped")