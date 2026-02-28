"""
model.py — Emotion / stress inference wrapper.

Loads the fine-tuned 3-class stress model from models/stress_model/ when
available, otherwise falls back to the pre-trained HuBERT emotion checkpoint.
Both expose the same predict_emotion() interface for main.py compatibility.
"""

from pathlib import Path

import torch
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

# ── Model paths ───────────────────────────────────────────────────────────────
_LOCAL_MODEL = "models/stress_model"
_FALLBACK_MODEL = "superb/hubert-base-superb-er"
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16_000


class EmotionModel:
    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.sample_rate = SAMPLE_RATE
        self._load_model()

    def _load_model(self) -> None:
        if Path(_LOCAL_MODEL).exists():
            source = _LOCAL_MODEL
            print(f"[model] Loading fine-tuned stress model from {source}")
        else:
            source = _FALLBACK_MODEL
            print(f"[model] {_LOCAL_MODEL} not found — using pre-trained {source}")
            print("[model] Run 'python train.py' to fine-tune for stress detection")

        self.feature_extractor = AutoFeatureExtractor.from_pretrained(source)
        self.model = AutoModelForAudioClassification.from_pretrained(source)
        self.model.to(self.device)
        self.model.eval()

    def predict_emotion(self, audio_tensor: torch.Tensor) -> dict:
        """
        Args:
            audio_tensor: 1-D float32 tensor of mono 16 kHz audio.
        Returns:
            {"emotion": str, "confidence": float}
        """
        audio_np = audio_tensor.cpu().numpy()

        inputs = self.feature_extractor(
            audio_np,
            sampling_rate=self.sample_rate,
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            logits = self.model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)
            cls_id = torch.argmax(probs, dim=-1).item()
            confidence = probs[0][cls_id].item()

        emotion = self.model.config.id2label[cls_id].lower()
        return {"emotion": emotion, "confidence": confidence}


# ── Singleton ────────────────────────────────────────────────────────────────
_instance: EmotionModel | None = None


def get_model() -> EmotionModel:
    global _instance
    if _instance is None:
        _instance = EmotionModel()
    return _instance
