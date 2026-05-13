import json
import os
import re
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def is_openai_available() -> bool:
    return bool(OPENAI_API_KEY)


def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing in backend/.env")

    return OpenAI(api_key=OPENAI_API_KEY)


def extract_json_from_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}

    return {}


def generate_json_with_openai(prompt: str, temperature: float = 0.25) -> Dict[str, Any]:
    client = get_openai_client()

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        temperature=temperature,
    )

    text = getattr(response, "output_text", "") or ""

    data = extract_json_from_text(text)

    if not data:
        raise RuntimeError("OpenAI did not return valid JSON.")

    return data


def generate_text_with_openai(prompt: str, temperature: float = 0.35) -> str:
    client = get_openai_client()

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        temperature=temperature,
    )

    text = getattr(response, "output_text", "") or ""

    if not text.strip():
        raise RuntimeError("OpenAI returned empty text.")

    return text.strip()


# Keep old function name so your schedule code does not break
def generate_ai_schedule_json(prompt: str) -> Dict[str, Any]:
    return generate_json_with_openai(prompt, temperature=0.25)