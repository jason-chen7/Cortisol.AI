"""
gemini_summarizer.py
Calls the Gemini REST API to generate a short warm spoken summary.

Set env var:  GEMINI_API_KEY=your_key
"""

import os

import httpx

FEATHERLESS_URL = "https://api.featherless.ai/v1/chat/completions"
MODEL_ID        = "meta-llama/Meta-Llama-3.1-8B-Instruct"

_SYSTEM = (
    "You are a compassionate AI stress coach. Write warm, empathetic spoken "
    "responses that will be read aloud by an AI avatar. Be direct and natural — "
    "like a supportive friend, not a doctor. Never use bullet points or formatting."
)

_USER_TMPL = """\
A user just finished a vocal stress analysis session. Write a 2-3 sentence \
spoken response under 60 words total. End with one brief practical encouragement.

Session data:
- Overall stress level: {overall_stress}
- Average stress score: {avg_pct}%
- Dominant emotion: {dominant_emotion}
- Stress breakdown: Low {low}% | Medium {medium}% | High {high}%
- Transcript: "{transcript}"

Spoken response:\
"""


async def generate_spoken_summary(
    overall_stress: str,
    avg_score: float,
    distribution: dict[str, float],
    dominant_emotion: str,
    transcript: str,
) -> str:
    api_key = os.environ.get("FEATHERLESS_API_KEY", "").strip()
    if not api_key:
        return ""

    transcript_snippet = (transcript.strip() or "No transcript available")[:400]

    user_msg = _USER_TMPL.format(
        overall_stress=overall_stress,
        avg_pct=round(avg_score * 100),
        dominant_emotion=dominant_emotion,
        low=distribution.get("Low", 0),
        medium=distribution.get("Medium", 0),
        high=distribution.get("High", 0),
        transcript=transcript_snippet,
    )

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        "max_tokens": 120,
        "temperature": 0.75,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                FEATHERLESS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )

        if response.status_code == 200:
            text = response.json()["choices"][0]["message"]["content"].strip()
            print(f"[Spoken summary] ✓ {text[:80]}…")
            return text

        print(f"[Spoken summary] HTTP {response.status_code}: {response.text[:200]}")
    except Exception as exc:
        print(f"[Spoken summary] Error: {exc}")

    return ""
