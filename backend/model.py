"""
model.py — Emotion inference wrapper.

Swap this file's _load_model() to point at a local path when ready:
    MODEL_SOURCE = "models/stress_model/"
All other files remain unchanged.
"""

import torch
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

# ── Change this constant to switch models ────────────────────────────────────
MODEL_SOURCE = "superb/wav2vec2-base-superb-er"
# MODEL_SOURCE = "models/stress_model/"          # ← local model (future)
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16_000


class EmotionModel:
    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.sample_rate = SAMPLE_RATE
        self._load_model()

    def _load_model(self) -> None:
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(MODEL_SOURCE)
        self.model = AutoModelForAudioClassification.from_pretrained(MODEL_SOURCE)
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
