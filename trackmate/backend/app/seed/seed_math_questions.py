from app.database import Base, SessionLocal, engine
from app.models import Chapter, Question, Subject

Base.metadata.create_all(bind=engine)

CHAPTERS = [
    "Rational Numbers",
    "Linear Equations in One Variable",
    "Understanding Quadrilaterals",
    "Data Handling",
    "Squares and Square Roots",
    "Cubes and Cube Roots",
    "Comparing Quantities",
    "Algebraic Expressions and Identities",
    "Mensuration",
    "Exponents and Powers",
]


def make_question(chapter_id: int, subject_id: int, chapter_name: str, number: int):
    correct = ["A", "B", "C", "D"][number % 4]
    return Question(
        subject_id=subject_id,
        chapter_id=chapter_id,
        question_text=f"{chapter_name}: Demo question {number}. Choose the correct option.",
        option_a=f"Option A for question {number}",
        option_b=f"Option B for question {number}",
        option_c=f"Option C for question {number}",
        option_d=f"Option D for question {number}",
        correct_answer=correct,
        difficulty="Easy" if number <= 5 else "Medium",
    )


def seed():
    db = SessionLocal()
    try:
        subject = db.query(Subject).filter(Subject.subject_name == "Maths").first()
        if not subject:
            subject = Subject(subject_name="Maths")
            db.add(subject)
            db.commit()
            db.refresh(subject)

        for index, chapter_name in enumerate(CHAPTERS, start=1):
            chapter = (
                db.query(Chapter)
                .filter(Chapter.subject_id == subject.id, Chapter.chapter_name == chapter_name)
                .first()
            )
            if not chapter:
                chapter = Chapter(subject_id=subject.id, chapter_name=chapter_name, chapter_order=index)
                db.add(chapter)
                db.commit()
                db.refresh(chapter)

            existing_count = db.query(Question).filter(Question.chapter_id == chapter.id).count()
            if existing_count < 12:
                for q_no in range(existing_count + 1, 13):
                    db.add(make_question(chapter.id, subject.id, chapter.chapter_name, q_no))
                db.commit()

        print("Seed completed: Maths subject, 10 chapters, 12 demo questions per chapter.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
