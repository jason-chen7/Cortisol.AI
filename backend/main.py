"""
main.py — FastAPI server with WebSocket audio streaming, stress inference,
          live transcription (ElevenLabs) and LLM summary (Featherless AI).
"""

import asyncio
import json
import os
from collections import Counter

import numpy as np

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from audio_utils import SlidingWindowBuffer, float32_to_tensor, pcm16_to_float32
from elevenlabs_transcriber import transcribe_chunk
from featherless_analyzer import analyze_transcript
from model import SAMPLE_RATE, get_model
from smoothing import EMASmoothing

app = FastAPI(title="Cortisol.AI Stress Detection")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Emotion → Stress mapping ──────────────────────────────────────────────────
_EMOTION_TABLE: dict[str, tuple[str, float, str]] = {
    "calm":      ("Low",    0.2, "green"),
    "neutral":   ("Low",    0.2, "green"),
    "neu":       ("Low",    0.2, "green"),
    "happy":     ("Low",    0.2, "green"),
    "hap":       ("Low",    0.2, "green"),
    "sad":       ("Medium", 0.5, "yellow"),
    "surprised": ("Medium", 0.5, "yellow"),
    "sur":       ("Medium", 0.5, "yellow"),
    "angry":     ("High",   0.8, "red"),
    "ang":       ("High",   0.8, "red"),
    "fearful":   ("High",   0.8, "red"),
    "fear":      ("High",   0.8, "red"),
    "fea":       ("High",   0.8, "red"),
    "disgust":   ("High",   0.8, "red"),
    "dis":       ("High",   0.8, "red"),
}


def map_emotion(emotion: str) -> tuple[str, float, str]:
    key = emotion.lower().strip()
    if key in _EMOTION_TABLE:
        return _EMOTION_TABLE[key]
    for table_key, val in _EMOTION_TABLE.items():
        if key.startswith(table_key[:3]) or table_key.startswith(key[:3]):
            return val
    return ("Medium", 0.5, "yellow")


def score_to_level(score: float) -> tuple[str, str]:
    if score < 0.35:
        return "Low", "green"
    if score < 0.65:
        return "Medium", "yellow"
    return "High", "red"


# ── Rule-based fallback reasoning ─────────────────────────────────────────────
def build_reasoning(
    distribution: dict[str, float],
    dominant_emotion: str,
    avg_score: float,
) -> str:
    high   = distribution.get("High", 0)
    medium = distribution.get("Medium", 0)
    low    = distribution.get("Low", 0)

    if avg_score >= 0.65:
        overall, desc = "high", "frequent high-arousal emotional states"
    elif avg_score >= 0.35:
        overall, desc = "moderate", "a mix of neutral and elevated emotional arousal"
    else:
        overall, desc = "low", "predominantly calm and neutral emotional states"

    parts: list[str] = []
    if high   > 0: parts.append(f"{high:.0f}% of segments showed high-stress emotions")
    if medium > 0: parts.append(f"{medium:.0f}% showed moderate emotional arousal")
    if low    > 0: parts.append(f"{low:.0f}% were calm or neutral")

    segment_line = (", ".join(parts) + ".") if parts else ""
    return (
        f"Analysis indicates {overall} overall stress. "
        f"The dominant emotion detected was '{dominant_emotion}', reflecting {desc}. "
        f"{segment_line}"
    )


# ── Model preload + API key check ─────────────────────────────────────────────
@app.on_event("startup")
async def _preload_model() -> None:
    get_model()
    eleven_key    = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    featherless_key = os.environ.get("FEATHERLESS_API_KEY", "").strip()
    print(f"[startup] ElevenLabs key   : {'✓ set' if eleven_key    else '✗ NOT SET — transcription disabled'}")
    print(f"[startup] Featherless key  : {'✓ set' if featherless_key else '✗ NOT SET — LLM analysis disabled'}")


# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/stream")
async def stream_audio(websocket: WebSocket) -> None:
    await websocket.accept()

    model   = get_model()
    buf     = SlidingWindowBuffer(window_size_sec=1.5, stride_sec=0.75)
    smoother = EMASmoothing(window=3, alpha=0.5)
    loop    = asyncio.get_running_loop()

    chunk_results:    list[dict]    = []
    transcript_parts: list[str]    = []

    # ElevenLabs works best on ≥3 s of audio — batch every 2 emotion windows
    transcription_audio_buf: list[np.ndarray] = []
    TRANSCRIPTION_BATCH = 2   # windows to accumulate before sending to STT

    try:
        while True:
            try:
                raw: bytes = await asyncio.wait_for(
                    websocket.receive_bytes(), timeout=2.0
                )
            except asyncio.TimeoutError:
                break

            audio_np = pcm16_to_float32(raw)
            buf.add(audio_np)

            for start_sample, window in buf.get_windows():
                start_time = start_sample / SAMPLE_RATE
                end_time   = start_time + 1.5

                # ── Emotion detection (every window) ──────────────────────────
                prediction = await loop.run_in_executor(
                    None, model.predict_emotion, float32_to_tensor(window)
                )

                emotion: str      = prediction["emotion"]
                confidence: float = prediction["confidence"]

                _, raw_score, _ = map_emotion(emotion)
                smoothed_score  = smoother.update(raw_score)
                stress_level, color = score_to_level(smoothed_score)

                result = {
                    "type":         "chunk_result",
                    "start_time":   round(start_time, 2),
                    "end_time":     round(end_time, 2),
                    "emotion":      emotion,
                    "stress_level": stress_level,
                    "confidence":   round(confidence, 4),
                    "color":        color,
                    "stress_score": round(smoothed_score, 4),
                }
                chunk_results.append(result)
                await websocket.send_text(json.dumps(result))

                # ── Transcription (batched — every TRANSCRIPTION_BATCH windows) ─
                transcription_audio_buf.append(window)
                if len(transcription_audio_buf) >= TRANSCRIPTION_BATCH:
                    batch_audio = np.concatenate(transcription_audio_buf)
                    transcription_audio_buf.clear()
                    transcript_text = await transcribe_chunk(batch_audio)
                    if transcript_text:
                        transcript_parts.append(transcript_text)
                        await websocket.send_text(json.dumps({
                            "type": "transcript",
                            "text": transcript_text,
                        }))

        # Flush any remaining audio to transcription
        if transcription_audio_buf:
            batch_audio = np.concatenate(transcription_audio_buf)
            transcript_text = await transcribe_chunk(batch_audio)
            if transcript_text:
                transcript_parts.append(transcript_text)
                await websocket.send_text(json.dumps({
                    "type": "transcript",
                    "text": transcript_text,
                }))

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "message": str(exc)})
            )
        except Exception:
            pass
    finally:
        full_transcript = " ".join(transcript_parts)
        await _send_summary(websocket, chunk_results, full_transcript)
        try:
            await websocket.close()
        except Exception:
            pass


async def _send_summary(
    websocket: WebSocket,
    results: list[dict],
    transcript: str,
) -> None:
    if not results:
        return

    scores  = [r["stress_score"] for r in results]
    levels  = [r["stress_level"] for r in results]
    emotions = [r["emotion"] for r in results]

    avg_score    = sum(scores) / len(scores)
    total        = len(levels)
    level_counts = Counter(levels)

    distribution = {
        "Low":    round(level_counts.get("Low",    0) / total * 100, 1),
        "Medium": round(level_counts.get("Medium", 0) / total * 100, 1),
        "High":   round(level_counts.get("High",   0) / total * 100, 1),
    }

    dominant_emotion = Counter(emotions).most_common(1)[0][0]
    overall_stress, _ = score_to_level(avg_score)

    # Rule-based reasoning is always available as a fallback
    reasoning = build_reasoning(distribution, dominant_emotion, avg_score)

    # LLM-enhanced reasoning from Featherless AI (uses transcript + audio data)
    enhanced_reasoning = await analyze_transcript(
        transcript, distribution, dominant_emotion, avg_score
    )

    summary = {
        "type":               "final_summary",
        "overall_stress":     overall_stress,
        "average_score":      round(avg_score, 4),
        "distribution":       distribution,
        "dominant_emotion":   dominant_emotion,
        "reasoning":          reasoning,
        "enhanced_reasoning": enhanced_reasoning,   # "" when Featherless key absent
        "transcript":         transcript,
    }

    try:
        await websocket.send_text(json.dumps(summary))
    except Exception:
        pass
