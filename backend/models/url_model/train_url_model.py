"""
models/url_model/train_url_model.py

End-to-end URL phishing model training script — Section 14 of the master document.

Usage
-----
    python backend/models/url_model/train_url_model.py

The script will:
  1. Load a CSV dataset from  datasets/url/url_dataset.csv  (or generate synthetic
     demo data if the file is not found).
  2. Extract URL features via url_features.py.
  3. Compare Logistic Regression, Random Forest, and XGBoost on a held-out test set.
  4. Save the best model (by F1 on test set) to  trained_models/url_model.pkl.
  5. Print evaluation metrics for each model.

Replace the synthetic data with a real labeled dataset (e.g., PhishTank + Alexa)
before claiming production-quality metrics.
"""

import os
import sys
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix, classification_report,
)
from xgboost import XGBClassifier

# Ensure backend/ is importable when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from models.url_model.url_features import extract_features, FEATURE_NAMES

warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = PROJECT_ROOT / "datasets" / "url" / "url_dataset.csv"
TRAINED_MODELS_DIR = PROJECT_ROOT / "trained_models"
MODEL_OUTPUT_PATH = TRAINED_MODELS_DIR / "url_model.pkl"

TRAINED_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_or_generate_dataset() -> pd.DataFrame:
    if DATASET_PATH.exists():
        print(f"[INFO] Loading dataset from {DATASET_PATH}")
        df = pd.read_csv(DATASET_PATH)
        assert "url" in df.columns and "label" in df.columns, \
            "Dataset must have 'url' and 'label' columns (0=benign, 1=phishing)."
        return df

    print("[WARN] Real dataset not found. Generating synthetic demo data.")
    print(f"       Place your real dataset at:  {DATASET_PATH}")
    from datasets.url.generate_demo_data import generate  # type: ignore
    return generate()


def build_feature_matrix(df: pd.DataFrame):
    rows = []
    for url in df["url"]:
        try:
            rows.append(extract_features(str(url)))
        except Exception:
            rows.append({k: 0.0 for k in FEATURE_NAMES})
    X = pd.DataFrame(rows)[FEATURE_NAMES].values
    y = df["label"].values.astype(int)
    return X, y


def evaluate(name: str, model, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    y_pred = model.predict(X_test)
    try:
        y_prob = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_prob)
    except Exception:
        auc = float("nan")

    metrics = {
        "model": name,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": auc,
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }
    return metrics


def print_metrics(metrics: dict) -> None:
    print(f"\n{'='*50}")
    print(f"  Model : {metrics['model']}")
    print(f"  Accuracy  : {metrics['accuracy']:.4f}")
    print(f"  Precision : {metrics['precision']:.4f}")
    print(f"  Recall    : {metrics['recall']:.4f}")
    print(f"  F1 Score  : {metrics['f1']:.4f}")
    print(f"  ROC-AUC   : {metrics['roc_auc']:.4f}")
    print(f"  Confusion Matrix:\n    {metrics['confusion_matrix']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n[TrustAI] URL Phishing Model Training")
    print("=" * 50)

    # 1 — Load data
    df = load_or_generate_dataset()
    print(f"[INFO] Dataset size: {len(df)} rows | Phishing: {df['label'].sum()} | Benign: {(df['label']==0).sum()}")

    # 2 — Feature extraction
    print("[INFO] Extracting features …")
    X, y = build_feature_matrix(df)
    print(f"[INFO] Feature matrix shape: {X.shape}")

    # 3 — Train/val/test split (70/15/15)
    X_tmp, X_test, y_tmp, y_test = train_test_split(X, y, test_size=0.15, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_tmp, y_tmp, test_size=0.15 / 0.85, random_state=42, stratify=y_tmp)

    print(f"[INFO] Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")

    # 4 — Define candidate models
    candidates = {
        "LogisticRegression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)),
        ]),
        "RandomForest": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42, n_jobs=-1)),
        ]),
        "XGBoost": XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            eval_metric="logloss",
            random_state=42,
        ),
    }

    # 5 — Train & evaluate
    all_metrics = []
    trained_models = {}
    for name, model in candidates.items():
        print(f"\n[INFO] Training {name} …")
        model.fit(X_train, y_train)
        metrics = evaluate(name, model, X_test, y_test)
        print_metrics(metrics)
        all_metrics.append(metrics)
        trained_models[name] = model

    # 6 — Select best model by F1
    best_metrics = max(all_metrics, key=lambda m: m["f1"])
    best_model = trained_models[best_metrics["model"]]
    print(f"\n[INFO] Best model: {best_metrics['model']}  (F1={best_metrics['f1']:.4f})")

    # 7 — Save model artifact
    artifact = {
        "model": best_model,
        "feature_names": FEATURE_NAMES,
        "model_name": best_metrics["model"],
        "metrics": best_metrics,
    }
    joblib.dump(artifact, MODEL_OUTPUT_PATH)
    print(f"[INFO] Saved model artifact -> {MODEL_OUTPUT_PATH}")

    # 8 — Save metrics JSON for the report
    metrics_path = TRAINED_MODELS_DIR / "url_model_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(all_metrics, f, indent=2)
    print(f"[INFO] Metrics saved -> {metrics_path}")

    print("\n[TrustAI] Training complete.")


if __name__ == "__main__":
    main()
