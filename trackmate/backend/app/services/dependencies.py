import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Student

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "trackmate_secret")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_student(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Student:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        student_id = payload.get("sub")

        if student_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    student = db.query(Student).filter(Student.id == int(student_id)).first()

    if not student:
        raise HTTPException(status_code=401, detail="Student not found")

    if not student.is_active:
        raise HTTPException(status_code=403, detail="Student account inactive")

    return student