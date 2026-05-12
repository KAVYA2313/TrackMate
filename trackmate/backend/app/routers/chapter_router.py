from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter
from app.schemas import ChapterCreate

router = APIRouter(prefix="/chapters", tags=["Chapters"])


@router.get("/")
def get_chapters(db: Session = Depends(get_db)):
    return db.query(Chapter).order_by(Chapter.subject_id, Chapter.chapter_order).all()


@router.get("/subject/{subject_id}")
def get_chapters_by_subject(subject_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Chapter)
        .filter(Chapter.subject_id == subject_id)
        .order_by(Chapter.chapter_order)
        .all()
    )


@router.post("/")
def create_chapter(request: ChapterCreate, db: Session = Depends(get_db)):
    chapter = Chapter(
        subject_id=request.subject_id,
        chapter_name=request.chapter_name.strip(),
        chapter_order=request.chapter_order,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter
