import hashlib
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models import OTPVerification, Student
from app.services.email_service import send_otp_email

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "trackmate_secret")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_context.verify(password, hashed_password)


def create_access_token(student_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(student_id),
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def hash_otp(otp: str) -> str:
    return hashlib.sha256(str(otp).encode()).hexdigest()


def signup_student(db: Session, name: str, email: str, password: str) -> Student:
    existing = db.query(Student).filter(Student.email == email.lower()).first()

    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    student = Student(
        name=name.strip(),
        email=email.lower(),
        password_hash=hash_password(password),
        profile_completed=False,
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    return student


def request_login_otp(db: Session, email: str, password: str) -> dict:
    student = db.query(Student).filter(Student.email == email.lower()).first()

    if not student:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not student.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    otp = generate_otp()

    otp_record = OTPVerification(
        student_id=student.id,
        email=student.email,
        otp_hash=hash_otp(otp),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
        is_used=False,
        attempts=0,
    )

    db.add(otp_record)
    db.commit()

    send_otp_email(student.email, otp)

    return {
        "message": "OTP sent successfully",
        "email": student.email,
    }


def verify_login_otp(db: Session, email: str, otp: str) -> dict:
    student = db.query(Student).filter(Student.email == email.lower()).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    otp_record: Optional[OTPVerification] = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.student_id == student.id,
            OTPVerification.email == student.email,
            OTPVerification.is_used == False,
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="OTP not found. Please login again.")

    now = datetime.now(timezone.utc)

    expires_at = otp_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        raise HTTPException(status_code=400, detail="OTP expired. Please login again.")

    if otp_record.attempts >= 5:
        raise HTTPException(status_code=400, detail="Too many wrong attempts. Please login again.")

    if otp_record.otp_hash != hash_otp(otp):
        otp_record.attempts = (otp_record.attempts or 0) + 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP")

    otp_record.is_used = True
    db.commit()

    token = create_access_token(student.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "profile_completed": student.profile_completed,
        "student": student,
    }