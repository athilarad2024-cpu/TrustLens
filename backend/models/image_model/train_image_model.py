"""
models/image_model/train_image_model.py

EfficientNet-B0 fine-tuning script for AI-generated / real image classification.
Section 15 of the master document.

Dataset structure expected:
    datasets/image/
    ├── train/
    │   ├── real/
    │   └── ai_generated/
    ├── validation/
    │   ├── real/
    │   └── ai_generated/
    └── test/
        ├── real/
        └── ai_generated/

Usage:
    python backend/models/image_model/train_image_model.py

The script saves:
    trained_models/image_model.pt    — model weights (state_dict)
    trained_models/image_model_metrics.json
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

# Ensure backend/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from utils.preprocessing import TRAIN_TRANSFORM, INFERENCE_TRANSFORM

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "datasets" / "image"
TRAINED_MODELS_DIR = PROJECT_ROOT / "trained_models"
MODEL_OUTPUT = TRAINED_MODELS_DIR / "image_model.pt"
METRICS_OUTPUT = TRAINED_MODELS_DIR / "image_model_metrics.json"

TRAINED_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Hyper-parameters ──────────────────────────────────────────────────────────
NUM_CLASSES = 2          # real=0, ai_generated=1
BATCH_SIZE = 32
EPOCHS = 10
LR = 3e-4
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ── Class mapping ──────────────────────────────────────────────────────────────
# torchvision ImageFolder assigns labels alphabetically:
#   ai_generated -> 0,  real -> 1
# We invert so that label 1 = "phishing/fake" for consistency.
# Adjust CLASS_NAMES based on your actual folder names.
FAKE_CLASS_INDEX = 0   # adjust if folder order differs

print(f"[TrustAI] Image Model Training — Device: {DEVICE}")


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
    # ── Validate dataset exists ──────────────────────────────────────────────
    for split in ("train", "validation", "test"):
        split_path = DATA_ROOT / split
        if not split_path.exists():
            print(f"[ERROR] Dataset split not found: {split_path}")
            print("        Please prepare the image dataset before running this script.")
            print("        See README.md -> 'Training Your Own Models' for instructions.")
            sys.exit(1)

    # ── Data loaders ─────────────────────────────────────────────────────────
    train_ds = datasets.ImageFolder(DATA_ROOT / "train", transform=TRAIN_TRANSFORM)
    val_ds = datasets.ImageFolder(DATA_ROOT / "validation", transform=INFERENCE_TRANSFORM)
    test_ds = datasets.ImageFolder(DATA_ROOT / "test", transform=INFERENCE_TRANSFORM)

    print(f"[INFO] Classes: {train_ds.classes}")
    print(f"[INFO] Train: {len(train_ds)} | Val: {len(val_ds)} | Test: {len(test_ds)}")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    # ── Model ─────────────────────────────────────────────────────────────────
    model = build_model().to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    criterion = nn.CrossEntropyLoss()

    # ── Training loop ─────────────────────────────────────────────────────────
    best_val_f1 = 0.0
    best_state = None
    for epoch in range(1, EPOCHS + 1):
        train_loss = train_epoch(model, train_loader, optimizer, criterion, DEVICE)
        scheduler.step()
        y_true, y_pred, y_prob = evaluate_model(model, val_loader, DEVICE)
        val_metrics = compute_metrics(y_true, y_pred, y_prob)
        print(
            f"Epoch {epoch:02d}/{EPOCHS} | loss={train_loss:.4f} | "
            f"val_f1={val_metrics['f1']:.4f} | val_auc={val_metrics['roc_auc']:.4f}"
        )
        if val_metrics["f1"] >= best_val_f1:
            best_val_f1 = val_metrics["f1"]
            best_state = {k: v.cpu() for k, v in model.state_dict().items()}

    # ── Final test evaluation ──────────────────────────────────────────────────
    if best_state:
        model.load_state_dict({k: v.to(DEVICE) for k, v in best_state.items()})
    y_true, y_pred, y_prob = evaluate_model(model, test_loader, DEVICE)
    test_metrics = compute_metrics(y_true, y_pred, y_prob)
    print("\n[INFO] Test set metrics:")
    for k, v in test_metrics.items():
        if k != "confusion_matrix":
            print(f"  {k}: {v:.4f}")
    print(f"  confusion_matrix: {test_metrics['confusion_matrix']}")

    # ── Save ──────────────────────────────────────────────────────────────────
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
    print(f"[INFO] Metrics saved -> {METRICS_OUTPUT}")
    print("[TrustAI] Image model training complete.")


if __name__ == "__main__":
    main()
