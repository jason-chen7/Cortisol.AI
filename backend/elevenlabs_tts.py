"""
elevenlabs_tts.py
Converts text to speech using ElevenLabs TTS and returns raw MP3 bytes.
Falls back to b"" if the API key is absent or the call fails.

Set env var:  ELEVENLABS_API_KEY=your_key
"""

import os

import httpx

# Rachel — warm, conversational female voice available on all plans
VOICE_ID  = "21m00Tcm4TlvDq8ikWAM"
MODEL_ID  = "eleven_turbo_v2"
TTS_URL   = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"


async def synthesize_speech(text: str) -> bytes:
    """
    Send text to ElevenLabs TTS and return MP3 bytes.
    Returns b"" when the API key is absent or the call fails.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key or not text.strip():
        return b""

    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": 0.55,
            "similarity_boost": 0.75,
            "style": 0.2,
            "use_speaker_boost": True,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                TTS_URL,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code == 200:
            print(f"[ElevenLabs TTS] ✓ synthesized {len(response.content)} bytes")
            return response.content
        print(f"[ElevenLabs TTS] HTTP {response.status_code}: {response.text[:300]}")
    except Exception as exc:
        print(f"[ElevenLabs TTS] Error: {exc}")

    return b""
