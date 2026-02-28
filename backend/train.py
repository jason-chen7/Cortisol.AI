"""
train.py — Fine-tune HuBERT-base for 3-class stress detection (Low / Medium / High).

Usage:
    cd backend
    python train.py

Strategy: pre-extract frozen HuBERT features once, then train only the
classifier head on cached vectors.  Total time ~3-5 min on GPU.
"""

import os
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from datasets import Audio, Dataset, concatenate_datasets, load_dataset
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit
from transformers import (
    AutoFeatureExtractor,
    AutoModelForAudioClassification,
)

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_MODEL = "superb/hubert-base-superb-er"
OUTPUT_DIR = "models/stress_model"
DATA_DIR = "data"
SAMPLE_RATE = 16_000
MAX_DURATION_SEC = 3.0
SEED = 42

LABEL2ID = {"Low": 0, "Medium": 1, "High": 2}
ID2LABEL = {0: "Low", 1: "Medium", 2: "High"}

EMOTION_TO_STRESS = {
    "neutral": 0, "calm": 0, "happy": 0,
    "sad": 1, "surprised": 1, "surprise": 1,
    "anger": 2, "angry": 2,
    "fear": 2, "fearful": 2,
    "disgust": 2,
}

RAVDESS_EMOTIONS = {
    "01": "neutral", "02": "calm", "03": "happy", "04": "sad",
    "05": "angry", "06": "fearful", "07": "disgust", "08": "surprised",
}

# ── Dataset loaders ───────────────────────────────────────────────────────────


def _download_progress(count, block_size, total_size):
    pct = min(100, count * block_size * 100 // max(total_size, 1))
    mb_done = count * block_size // 1_048_576
    mb_total = total_size // 1_048_576
    print(f"\r  {pct:3d}%  ({mb_done}/{mb_total} MB)", end="", flush=True)


def load_ravdess() -> Dataset:
    """Download RAVDESS speech audio from Zenodo and return a Dataset."""
    ravdess_dir = Path(DATA_DIR) / "ravdess"

    if not any(ravdess_dir.glob("Actor_*")):
        ravdess_dir.mkdir(parents=True, exist_ok=True)
        zip_path = ravdess_dir / "ravdess.zip"
        url = "https://zenodo.org/records/1188976/files/Audio_Speech_Actors_01-24.zip"
        print("  Downloading RAVDESS from Zenodo ...")
        urllib.request.urlretrieve(url, str(zip_path), _download_progress)
        print()
        print("  Extracting ...")
        with zipfile.ZipFile(str(zip_path)) as zf:
            zf.extractall(str(ravdess_dir))
        zip_path.unlink()

    paths, labels, speakers = [], [], []
    for wav in sorted(ravdess_dir.rglob("*.wav")):
        parts = wav.stem.split("-")
        if len(parts) < 7:
            continue
        emotion = RAVDESS_EMOTIONS.get(parts[2])
        if emotion is None or emotion not in EMOTION_TO_STRESS:
            continue
        paths.append(str(wav))
        labels.append(EMOTION_TO_STRESS[emotion])
        speakers.append(f"ravdess_{parts[6]}")

    ds = Dataset.from_dict({"audio": paths, "label": labels, "speaker_id": speakers})
    ds = ds.cast_column("audio", Audio(sampling_rate=SAMPLE_RATE))
    print(f"  RAVDESS : {len(ds):,} samples - {len(set(speakers))} speakers")
    return ds


def load_cremad() -> Dataset:
    """Load CREMA-D from HuggingFace, remap emotion labels to stress levels."""
    print("  Loading CREMA-D from HuggingFace ...")
    raw = load_dataset("AbstractTTS/CREMA-D", split="train")

    def _remap(example):
        emotion = example["major_emotion"].lower()
        actor_id = example["file"].split("_")[0]
        return {
            "label": EMOTION_TO_STRESS.get(emotion, 1),
            "speaker_id": f"cremad_{actor_id}",
        }

    cols_keep = {"audio"}
    cols_drop = [c for c in raw.column_names if c not in cols_keep]
    ds = raw.map(_remap, remove_columns=cols_drop)
    ds = ds.cast_column("audio", Audio(sampling_rate=SAMPLE_RATE))
    print(f"  CREMA-D : {len(ds):,} samples - {len(set(ds['speaker_id']))} speakers")
    return ds


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    print("=" * 60)
    print("  HuBERT Stress Detection -- Fast Fine-tuning")
    print("=" * 60)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nDevice : {device}")
    if device == "cuda":
        print(f"  GPU  : {torch.cuda.get_device_name(0)}")

    # ── 1. Load datasets ─────────────────────────────────────────────────
    print("\n[1/5] Loading datasets ...")
    ravdess = load_ravdess()
    cremad = load_cremad()
    dataset = concatenate_datasets([ravdess, cremad])

    labels_list = dataset["label"]
    print(f"\n  Total : {len(dataset):,} samples")
    for idx, name in ID2LABEL.items():
        n = labels_list.count(idx)
        print(f"    {name:8s}: {n:5,}  ({n / len(labels_list) * 100:5.1f}%)")

    # ── 2. Split ─────────────────────────────────────────────────────────
    print("\n[2/5] Speaker-disjoint split ...")
    speakers = np.array(dataset["speaker_id"])
    indices = np.arange(len(dataset))

    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.1, random_state=SEED)
    trainval_idx, test_idx = next(gss1.split(indices, groups=speakers))
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.1 / 0.9, random_state=SEED)
    train_rel, val_rel = next(gss2.split(trainval_idx, groups=speakers[trainval_idx]))
    train_idx = trainval_idx[train_rel]
    val_idx = trainval_idx[val_rel]

    print(f"  Train : {len(train_idx):,}  |  Val : {len(val_idx):,}  |  Test : {len(test_idx):,}")

    # ── 3. Extract features ──────────────────────────────────────────────
    print(f"\n[3/5] Extracting HuBERT features (one pass, no grad) ...")
    feature_extractor = AutoFeatureExtractor.from_pretrained(BASE_MODEL)
    model = AutoModelForAudioClassification.from_pretrained(
        BASE_MODEL,
        num_labels=3,
        label2id=LABEL2ID,
        id2label=ID2LABEL,
        ignore_mismatched_sizes=True,
    )
    model.to(device)
    model.eval()

    max_len = int(MAX_DURATION_SEC * SAMPLE_RATE)

    def extract_batch(indices_list):
        all_feats, all_labels = [], []
        batch_size = 16
        for start in range(0, len(indices_list), batch_size):
            end = min(start + batch_size, len(indices_list))
            batch_idx = indices_list[start:end]
            batch = dataset.select(batch_idx.tolist())

            arrays = [x["array"] for x in batch["audio"]]
            inputs = feature_extractor(
                arrays,
                sampling_rate=SAMPLE_RATE,
                max_length=max_len,
                truncation=True,
                padding="max_length",
                return_attention_mask=True,
                return_tensors="pt",
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model.hubert(**inputs)
                hidden = outputs.last_hidden_state
                if "attention_mask" in inputs:
                    mask = model._get_feature_vector_attention_mask(
                        hidden.shape[1], inputs["attention_mask"]
                    )
                    hidden[~mask] = 0.0
                    pooled = hidden.sum(dim=1) / mask.sum(dim=1, keepdim=True).float()
                else:
                    pooled = hidden.mean(dim=1)

            proj = model.projector(pooled)
            all_feats.append(proj.detach().cpu())
            all_labels.append(torch.tensor(batch["label"]))

            done = min(end, len(indices_list))
            print(f"\r    {done}/{len(indices_list)}", end="", flush=True)

        print()
        return torch.cat(all_feats), torch.cat(all_labels)

    print("  Train features ...")
    train_feats, train_labels = extract_batch(train_idx)
    print("  Val features ...")
    val_feats, val_labels = extract_batch(val_idx)
    print("  Test features ...")
    test_feats, test_labels = extract_batch(test_idx)

    # ── 4. Train classifier head ─────────────────────────────────────────
    print(f"\n[4/5] Training classifier on cached features ...")
    feat_dim = train_feats.shape[1]

    classifier = nn.Linear(feat_dim, 3).to(device)
    nn.init.xavier_uniform_(classifier.weight)
    nn.init.zeros_(classifier.bias)

    optimizer = torch.optim.AdamW(classifier.parameters(), lr=1e-3, weight_decay=0.01)
    class_counts = torch.bincount(train_labels, minlength=3).float()
    class_weights = (1.0 / class_counts.clamp(min=1))
    class_weights = (class_weights / class_weights.sum() * 3).to(device)
    print(f"  Class weights: {class_weights.tolist()}")
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    train_loader = DataLoader(
        TensorDataset(train_feats, train_labels),
        batch_size=128, shuffle=True,
    )
    val_loader = DataLoader(
        TensorDataset(val_feats, val_labels),
        batch_size=128,
    )

    best_f1 = 0.0
    best_weights = None
    patience_counter = 0
    max_patience = 5

    for epoch in range(50):
        classifier.train()
        losses = []
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            loss = criterion(classifier(xb), yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(loss.item())

        classifier.eval()
        all_preds, all_true = [], []
        with torch.no_grad():
            for xb, yb in val_loader:
                preds = classifier(xb.to(device)).argmax(dim=-1).cpu()
                all_preds.append(preds)
                all_true.append(yb)
        all_preds = torch.cat(all_preds).numpy()
        all_true = torch.cat(all_true).numpy()
        f1 = f1_score(all_true, all_preds, average="macro")
        acc = accuracy_score(all_true, all_preds)

        print(f"  Epoch {epoch+1:2d}  loss={np.mean(losses):.4f}  val_acc={acc:.4f}  val_f1={f1:.4f}")

        if f1 > best_f1:
            best_f1 = f1
            best_weights = {k: v.clone() for k, v in classifier.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= max_patience:
                print(f"  Early stopping at epoch {epoch+1}")
                break

    classifier.load_state_dict(best_weights)

    # ── 5. Evaluate & Save ───────────────────────────────────────────────
    print("\n[5/5] Evaluating on test set ...")
    classifier.eval()
    all_preds, all_true = [], []
    with torch.no_grad():
        for xb, yb in DataLoader(TensorDataset(test_feats, test_labels), batch_size=128):
            preds = classifier(xb.to(device)).argmax(dim=-1).cpu()
            all_preds.append(preds)
            all_true.append(yb)
    all_preds = torch.cat(all_preds).numpy()
    all_true = torch.cat(all_true).numpy()

    print(f"  Accuracy   : {accuracy_score(all_true, all_preds):.4f}")
    print(f"  F1 (macro) : {f1_score(all_true, all_preds, average='macro'):.4f}")
    print("\n" + classification_report(all_true, all_preds, target_names=["Low", "Medium", "High"]))

    # Graft trained classifier back into the full model
    model.classifier.weight.data.copy_(best_weights["weight"])
    model.classifier.bias.data.copy_(best_weights["bias"])

    save_dir = Path(OUTPUT_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(save_dir))
    feature_extractor.save_pretrained(str(save_dir))
    print(f"\nModel saved to {save_dir}/")
    print("The server will automatically use this model on next startup.")


if __name__ == "__main__":
    main()
