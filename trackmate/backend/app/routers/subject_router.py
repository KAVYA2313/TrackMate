from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Subject
from app.schemas import SubjectCreate

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.get("/")
def get_subjects(db: Session = Depends(get_db)):
    return db.query(Subject).order_by(Subject.id).all()


@router.post("/")
def create_subject(request: SubjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Subject).filter(Subject.subject_name.ilike(request.subject_name)).first()
    if existing:
        return existing

    subject = Subject(subject_name=request.subject_name.strip())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject
