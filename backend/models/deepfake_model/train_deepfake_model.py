"""
models/deepfake_model/train_deepfake_model.py

Frame-level EfficientNet-B0 fine-tuning for deepfake / face manipulation detection.
Section 16 of the master document.

Dataset structure expected (pre-cropped face frames):
    datasets/video/
    ├── train/
    │   ├── real/       (individual face-crop frames, .jpg/.png)
    │   └── fake/
    └── test/
        ├── real/
        └── fake/

IMPORTANT: Split by SOURCE VIDEO, not by individual frames, to avoid leakage.

Usage:
    python backend/models/deepfake_model/train_deepfake_model.py

Saves:
    trained_models/deepfake_model.pt
    trained_models/deepfake_model_metrics.json
"""

import json
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets
import timm
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.preprocessing import TRAIN_TRANSFORM, INFERENCE_TRANSFORM

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "datasets" / "video"
TRAINED_MODELS_DIR = PROJECT_ROOT / "trained_models"
MODEL_OUTPUT = TRAINED_MODELS_DIR / "deepfake_model.pt"
METRICS_OUTPUT = TRAINED_MODELS_DIR / "deepfake_model_metrics.json"

TRAINED_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
NUM_CLASSES = 2          # real=0 (alphabetically first), fake=1
BATCH_SIZE = 32
EPOCHS = 10
LR = 3e-4
FAKE_CLASS_INDEX = 0    # ImageFolder assigns 'fake'->0, 'real'->1 alphabetically
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"[TrustAI] Deepfake Frame Classifier Training — Device: {DEVICE}")


def build_model() -> nn.Module:
    model = timm.create_model("efficientnet_b0", pretrained=True, num_classes=NUM_CLASSES)
    return model


def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    for imgs, labels in loader:
        imgs, labels = imgs.to(device), labels.to(device)
        optimizer.zero_grad()
        logits = model(imgs)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / max(len(loader), 1)


@torch.no_grad()
def evaluate_model(model, loader, device):
    model.eval()
    all_labels, all_preds, all_probs = [], [], []
    for imgs, labels in loader:
        imgs = imgs.to(device)
        logits = model(imgs)
        probs = torch.softmax(logits, dim=1)[:, FAKE_CLASS_INDEX].cpu().numpy()
        preds = (probs >= 0.5).astype(int)
        all_labels.extend(labels.numpy())
        all_preds.extend(preds)
        all_probs.extend(probs)
    return all_labels, all_preds, all_probs


def compute_metrics(y_true, y_pred, y_prob) -> dict:
    try:
        auc = roc_auc_score(y_true, y_prob)
    except Exception:
        auc = float("nan")
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": auc,
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }


def main():
    for split in ("train", "test"):
        split_path = DATA_ROOT / split
        if not split_path.exists():
            print(f"[ERROR] Dataset split not found: {split_path}")
            print("        Prepare face-crop frames split by SOURCE VIDEO, not frame.")
            sys.exit(1)

    train_ds = datasets.ImageFolder(DATA_ROOT / "train", transform=TRAIN_TRANSFORM)
    test_ds = datasets.ImageFolder(DATA_ROOT / "test", transform=INFERENCE_TRANSFORM)

    print(f"[INFO] Classes: {train_ds.classes}  (FAKE_CLASS_INDEX={FAKE_CLASS_INDEX})")
    print(f"[INFO] Train frames: {len(train_ds)} | Test frames: {len(test_ds)}")
    print("[WARN] Ensure frames are split by source video, not individual frames.")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    model = build_model().to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    criterion = nn.CrossEntropyLoss()

    best_f1 = 0.0
    best_state = None
    for epoch in range(1, EPOCHS + 1):
        train_loss = train_epoch(model, train_loader, optimizer, criterion, DEVICE)
        scheduler.step()
        y_true, y_pred, y_prob = evaluate_model(model, test_loader, DEVICE)
        m = compute_metrics(y_true, y_pred, y_prob)
        print(f"Epoch {epoch:02d}/{EPOCHS} | loss={train_loss:.4f} | f1={m['f1']:.4f} | auc={m['roc_auc']:.4f}")
        if m["f1"] >= best_f1:
            best_f1 = m["f1"]
            best_state = {k: v.cpu() for k, v in model.state_dict().items()}

    if best_state:
        model.load_state_dict({k: v.to(DEVICE) for k, v in best_state.items()})
    y_true, y_pred, y_prob = evaluate_model(model, test_loader, DEVICE)
    test_metrics = compute_metrics(y_true, y_pred, y_prob)

    print("\n[INFO] Final test metrics:")
    for k, v in test_metrics.items():
        if k != "confusion_matrix":
            print(f"  {k}: {v:.4f}")

    torch.save(
        {
            "state_dict": best_state or model.state_dict(),
            "class_names": train_ds.classes,
            "fake_class_index": FAKE_CLASS_INDEX,
            "model_arch": "efficientnet_b0",
            "metrics": test_metrics,
        },
        MODEL_OUTPUT,
    )
    print(f"[INFO] Model saved -> {MODEL_OUTPUT}")

    with open(METRICS_OUTPUT, "w") as f:
        json.dump(test_metrics, f, indent=2)
    print("[TrustAI] Deepfake model training complete.")


if __name__ == "__main__":
    main()
