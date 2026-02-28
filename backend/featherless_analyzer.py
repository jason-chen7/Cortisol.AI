"""
featherless_analyzer.py
Uses Featherless AI's OpenAI-compatible chat API to generate an enhanced,
LLM-based stress analysis from the session transcript + audio emotion data.

Set env var:  FEATHERLESS_API_KEY=your_key
Docs:         https://featherless.ai/docs
"""

import os

import httpx

FEATHERLESS_API_KEY = os.environ.get("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE    = "https://api.featherless.ai/v1"

# Any instruction-tuned model hosted on Featherless works here.
# Smaller = faster and cheaper; adjust to taste.
MODEL_ID = "meta-llama/Meta-Llama-3.1-8B-Instruct"

_SYSTEM = (
    "You are a clinical psychologist specialising in vocal stress analysis. "
    "You receive a speech transcript alongside acoustic emotion data and produce "
    "a concise, evidence-based stress assessment. Be factual and avoid speculation."
)

_USER_TEMPLATE = """\
Below is a speech transcript captured during a real-time stress-detection session, \
along with acoustic emotion analysis results.

=== TRANSCRIPT ===
{transcript}

=== AUDIO EMOTION ANALYSIS ===
- Dominant emotion detected: {dominant_emotion}
- Stress distribution: Low {low}% | Medium {medium}% | High {high}%
- Average stress score: {avg_score:.0%}

Task: Write 3-4 sentences that:
1. Identify linguistic patterns in the transcript (word choice, repetition, hedging) \
that indicate the speaker's stress level.
2. Note whether the spoken content aligns or contrasts with the acoustic emotion data.
3. State the overall stress assessment supported by both sources of evidence.

Do not use bullet points. Do not repeat the raw numbers verbatim.\
"""


async def analyze_transcript(
    transcript: str,
    distribution: dict[str, float],
    dominant_emotion: str,
    avg_score: float,
) -> str:
    """
    Call Featherless AI and return an LLM-generated stress analysis paragraph.
    Returns "" when the API key is absent, the transcript is empty, or the
    call fails for any reason.
    """
    if not FEATHERLESS_API_KEY:
        return ""

    transcript = transcript.strip()
    if len(transcript) < 20:
        return ""

    user_msg = _USER_TEMPLATE.format(
        transcript=transcript[:3_000],   # hard cap to stay within context
        dominant_emotion=dominant_emotion,
        low=distribution.get("Low", 0),
        medium=distribution.get("Medium", 0),
        high=distribution.get("High", 0),
        avg_score=avg_score,
    )

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        "max_tokens": 250,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{FEATHERLESS_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {FEATHERLESS_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code == 200:
            return (
                response.json()["choices"][0]["message"]["content"].strip()
            )
        print(f"[Featherless] HTTP {response.status_code}: {response.text[:200]}")
    except Exception as exc:
        print(f"[Featherless] Error: {exc}")

    return ""
