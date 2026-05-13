import json
import os
import re
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return round(float(value), 2)
    except Exception:
        return default


def _clean_text(value: Any, max_len: int = 500) -> str:
    text = "" if value is None else str(value)

    text = re.sub(r"\s+", " ", text).strip()

    unwanted_labels = [
        "TITLE:",
        "MESSAGE:",
        "Title:",
        "Message:",
        "ACTION:",
        "Action:",
    ]

    for label in unwanted_labels:
        text = text.replace(label, "").strip()

    return text[:max_len]


def _fallback_notification(
    student_name: str,
    subject_name: str,
    chapter_name: str,
    retention_score: float,
    priority_score: float,
    last_score: float,
    difficulty: str,
) -> Dict[str, Any]:
    student_name = _clean_text(student_name or "Student", 60)
    subject_name = _clean_text(subject_name or "Maths", 60)
    chapter_name = _clean_text(chapter_name or "this chapter", 120)
    difficulty = _clean_text(difficulty or "Medium", 30)

    retention_score = _safe_float(retention_score)
    priority_score = _safe_float(priority_score)
    last_score = _safe_float(last_score)

    if last_score <= 40 or retention_score <= 40:
        title = f"Revise {chapter_name}"
        message = (
            f"{student_name}, spend a short focused session on {chapter_name}. "
            f"Start with the scheduled topics and try a quick practice test after revision."
        )
        action = "Review scheduled topics"
    elif priority_score >= 70:
        title = f"Focus on {chapter_name}"
        message = (
            f"{student_name}, {chapter_name} needs attention today. "
            f"Revise the planned topic first, then continue your next study task."
        )
        action = "Start focused revision"
    else:
        title = "Quick Revision Reminder"
        message = (
            f"{student_name}, revise one topic from {chapter_name} today "
            f"to keep your {subject_name} preparation steady."
        )
        action = "Revise one topic"

    return {
        "title": _clean_text(title, 90),
        "message": _clean_text(message, 280),
        "action": _clean_text(action, 80),
        "llm_used": False,
        "model": "fallback",
    }


def is_llm_available() -> bool:
    return bool(OPENAI_API_KEY)


def _extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    if not raw_text:
        return {}

    text = raw_text.strip()

    text = text.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}


def _extract_title_message_action(raw_text: str, fallback: Dict[str, Any]) -> Dict[str, str]:
    raw_text = raw_text or ""
    raw_text = raw_text.strip()

    json_data = _extract_json_from_text(raw_text)

    if json_data:
        title = (
            json_data.get("title")
            or json_data.get("TITLE")
            or fallback["title"]
        )

        message = (
            json_data.get("message")
            or json_data.get("MESSAGE")
            or fallback["message"]
        )

        action = (
            json_data.get("action")
            or json_data.get("ACTION")
            or fallback.get("action", "Review now")
        )

        return {
            "title": _clean_text(title, 90),
            "message": _clean_text(message, 280),
            "action": _clean_text(action, 80),
        }

    title_match = re.search(
        r"TITLE\s*:\s*(.*?)(?=MESSAGE\s*:|ACTION\s*:|$)",
        raw_text,
        re.IGNORECASE | re.DOTALL,
    )

    message_match = re.search(
        r"MESSAGE\s*:\s*(.*?)(?=ACTION\s*:|$)",
        raw_text,
        re.IGNORECASE | re.DOTALL,
    )

    action_match = re.search(
        r"ACTION\s*:\s*(.*)$",
        raw_text,
        re.IGNORECASE | re.DOTALL,
    )

    title = title_match.group(1).strip() if title_match else ""
    message = message_match.group(1).strip() if message_match else ""
    action = action_match.group(1).strip() if action_match else ""

    if title or message or action:
        return {
            "title": _clean_text(title or fallback["title"], 90),
            "message": _clean_text(message or fallback["message"], 280),
            "action": _clean_text(action or fallback.get("action", "Review now"), 80),
        }

    clean = _clean_text(raw_text, 280)

    if clean:
        return {
            "title": fallback["title"],
            "message": clean,
            "action": fallback.get("action", "Review now"),
        }

    return {
        "title": fallback["title"],
        "message": fallback["message"],
        "action": fallback.get("action", "Review now"),
    }


def _build_notification_prompt(
    student_name: str,
    subject_name: str,
    chapter_name: str,
    retention_score: float,
    priority_score: float,
    last_score: float,
    difficulty: str,
) -> str:
    return f"""
You are TrackMate, a friendly study coach for school/college students.

Create one short notification for the student.

Important writing rules:
- Use very simple English.
- Do NOT use technical words like retention, priority score, weak chapter, algorithm, memory decay, analytics, or low marks.
- Do NOT say "you failed".
- Do NOT make the student feel bad.
- Sound helpful, calm, and motivating.
- Mention the chapter name.
- Tell the student one clear action.
- Keep title short.
- Keep message under 32 words.
- Return ONLY valid JSON. No markdown. No extra text.

Internal data for your decision:
Student name: {student_name}
Subject: {subject_name}
Chapter: {chapter_name}
Question level: {difficulty}
Memory value: {retention_score}
Latest test percentage: {last_score}
Urgency value: {priority_score}

Meaning of internal data:
- If latest test percentage is below 40, suggest revision and a short practice test.
- If memory value is below 40, suggest quick revision today.
- If urgency value is high, suggest this chapter before new topics.
- Never show these numbers in the message unless it sounds natural.

Return JSON in this exact format:
{{
  "title": "max 7 words",
  "message": "max 32 words, simple student-friendly English",
  "action": "max 5 words"
}}
"""


def generate_weak_chapter_notification(
    student_name: str,
    subject_name: str,
    chapter_name: str,
    retention_score: float,
    priority_score: float = 0,
    last_score: float = 0,
    difficulty: str = "Medium",
) -> Dict[str, Any]:
    """
    OpenAI-based notification generator.

    Output:
    {
        "title": "...",
        "message": "...",
        "action": "...",
        "llm_used": True/False,
        "model": "gpt-4o-mini" / "fallback"
    }

    This function never crashes the app.
    If OpenAI fails, fallback message is returned.
    """

    retention_score = _safe_float(retention_score)
    priority_score = _safe_float(priority_score)
    last_score = _safe_float(last_score)

    student_name = _clean_text(student_name or "Student", 60)
    subject_name = _clean_text(subject_name or "Maths", 60)
    chapter_name = _clean_text(chapter_name or "Chapter", 120)
    difficulty = _clean_text(difficulty or "Medium", 30)

    fallback = _fallback_notification(
        student_name=student_name,
        subject_name=subject_name,
        chapter_name=chapter_name,
        retention_score=retention_score,
        priority_score=priority_score,
        last_score=last_score,
        difficulty=difficulty,
    )

    if not is_llm_available():
        return fallback

    prompt = _build_notification_prompt(
        student_name=student_name,
        subject_name=subject_name,
        chapter_name=chapter_name,
        retention_score=retention_score,
        priority_score=priority_score,
        last_score=last_score,
        difficulty=difficulty,
    )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
            temperature=0.35,
        )

        raw_text = getattr(response, "output_text", "") or ""

        parsed = _extract_title_message_action(raw_text, fallback)

        return {
            "title": parsed["title"],
            "message": parsed["message"],
            "action": parsed["action"],
            "llm_used": True,
            "model": OPENAI_MODEL,
        }

    except Exception:
        return fallback