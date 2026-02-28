"""
elevenlabs_transcriber.py
Sends each audio window to ElevenLabs Scribe (speech-to-text) and returns
the transcript text.  Fails silently if the API key is missing.

Set env var:  ELEVENLABS_API_KEY=your_key
"""

import io
import os
import wave

import httpx
import numpy as np

ELEVEN_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
SAMPLE_RATE    = 16_000


def _build_wav(pcm_float32: np.ndarray) -> bytes:
    """Wrap a float32 array in a valid 16-bit PCM WAV container."""
    pcm_int16 = (np.clip(pcm_float32, -1.0, 1.0) * 32_767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_int16.tobytes())
    return buf.getvalue()


async def transcribe_chunk(audio_np: np.ndarray) -> str:
    """
    Send one audio window to ElevenLabs Scribe and return the transcript.
    Returns "" when the API key is absent, the audio is silent, or the
    call fails for any reason.
    """
    # Read key at call time so it picks up the env var even after hot-reload
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        return ""

    # Skip near-silent windows (lowered threshold for quieter mics)
    rms = float(np.sqrt(np.mean(audio_np ** 2)))
    if rms < 0.001:
        return ""

    wav_bytes = _build_wav(audio_np)

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                ELEVEN_STT_URL,
                headers={"xi-api-key": api_key},
                files={"file": ("chunk.wav", wav_bytes, "audio/wav")},
                data={"model_id": "scribe_v1"},
            )
        if response.status_code == 200:
            text = response.json().get("text", "").strip()
            if text:
                print(f"[ElevenLabs STT] ✓ '{text}'")
            return text
        print(f"[ElevenLabs STT] HTTP {response.status_code}: {response.text[:300]}")
    except Exception as exc:
        print(f"[ElevenLabs STT] Error: {exc}")

    return ""
