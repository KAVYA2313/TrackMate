import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_APP_PASSWORD = os.getenv("MAIL_APP_PASSWORD")


def _send_email(to_email: str, subject: str, body: str) -> bool:
    if not MAIL_USERNAME or not MAIL_APP_PASSWORD or MAIL_APP_PASSWORD == "your_gmail_app_password":
        print("\n========== TRACKMATE EMAIL DEBUG ==========")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(body)
        print("==========================================\n")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = MAIL_USERNAME
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(MAIL_USERNAME, MAIL_APP_PASSWORD)
        smtp.send_message(message)

    return True


def send_otp_email(to_email: str, otp: str) -> None:
    subject = "TrackMate OTP Verification"

    body = f"""
Hello,

Your TrackMate verification OTP is:

{otp}

This OTP will expire in 5 minutes.

Regards,
TrackMate Team
"""

    _send_email(to_email, subject, body)


def send_weak_chapter_email(
    to_email: str,
    student_name: str,
    chapter_name: str,
    retention: float,
    priority_score: float,
) -> bool:
    subject = f"TrackMate Reminder: Revise {chapter_name}"

    body = f"""
Hello {student_name},

TrackMate found that this chapter needs revision:

Chapter: {chapter_name}
Current Retention: {retention}%
Priority Score: {priority_score}

This chapter is becoming weak, so please revise it today and take a small test again.

Recommended action:
Revise the chapter basics, solve practice questions, and retake the chapter test.

Regards,
TrackMate Team
"""

    return _send_email(to_email, subject, body)