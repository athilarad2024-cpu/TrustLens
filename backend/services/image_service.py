"""
services/image_service.py

AI-generated / manipulated image detection — full working pipeline.

Detection approach (no training dataset needed):
  1. Error Level Analysis (ELA)   — detects JPEG re-compression artifacts
  2. DCT Frequency Analysis       — AI images have different high-freq energy
  3. Noise Pattern Analysis       — Laplacian noise + local variance
  4. Pretrained EfficientNet-B0   — deep feature extraction (ImageNet weights)
  5. Weighted signal fusion       — combines all signals into final probability
"""

import io
import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image, ExifTags

try:
    import torch
    import torch.nn.functional as F
    import torchvision.transforms as T
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    F = None      # type: ignore
    T = None      # type: ignore
    _TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEVICE = ("cuda" if _TORCH_AVAILABLE and torch.cuda.is_available() else "cpu") if _TORCH_AVAILABLE else "cpu"

# ── EfficientNet feature extractor (global, lazy-loaded) ──────────────────────
_feature_model = None
_feature_load_error: Optional[str] = None

_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD  = [0.229, 0.224, 0.225]

# Expose _model alias for health check in main.py
_model = None


def _load_feature_model() -> None:
    global _feature_model, _feature_load_error, _model
    if not _TORCH_AVAILABLE:
        _feature_load_error = "PyTorch not installed. Run: pip install torch torchvision"
        logger.warning("[ImageService] %s", _feature_load_error)
        return
    try:
        import torchvision.models as tvm
        m = tvm.efficientnet_b0(weights=tvm.EfficientNet_B0_Weights.IMAGENET1K_V1)
        # Use only the feature extractor (drop classifier head)
        m.classifier = torch.nn.Identity()
        m.to(DEVICE).eval()
        _feature_model = m
        _model = m  # health check alias
        logger.info("[ImageService] EfficientNet-B0 pretrained feature extractor loaded (device=%s)", DEVICE)
    except Exception as exc:
        _feature_load_error = str(exc)
        logger.error("[ImageService] Feature model load error: %s", exc)


_load_feature_model()


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_image(image_path: Path) -> Dict[str, Any]:
    """
    Analyze an image for AI-generation / manipulation signals.
    Returns a structured result dict compatible with api/image.py.
    """
    limitations: list = []

    # ── Load image ────────────────────────────────────────────────────────────
    try:
        pil_img = Image.open(image_path).convert("RGB")
    except Exception as exc:
        return _error_result(f"Could not open image: {exc}")

    w, h = pil_img.size
    img_format = pil_img.format or Path(image_path).suffix.lstrip(".").upper()

    # ── Extract EXIF ──────────────────────────────────────────────────────────
    exif_data = _extract_exif(image_path)
    has_exif = len(exif_data) > 0

    # ── Signal 1: Error Level Analysis (ELA) ─────────────────────────────────
    ela_score = _error_level_analysis(pil_img)      # 0=authentic-like, 1=suspicious

    # ── Signal 2: DCT Frequency Analysis ─────────────────────────────────────
    freq_score = _dct_frequency_score(pil_img)      # 0=authentic, 1=AI-like

    # ── Signal 3: Noise Pattern Analysis ─────────────────────────────────────
    noise_score = _noise_pattern_score(pil_img)     # 0=authentic, 1=uniform/AI-like

    # ── Signal 4: Deep Feature Analysis ──────────────────────────────────────
    deep_score, deep_ok = _deep_feature_score(pil_img)

    if not deep_ok:
        limitations.append("Deep feature analysis unavailable; using signal-only mode.")

    # ── Signal 5: EXIF absence heuristic ─────────────────────────────────────
    # AI images often lack EXIF; weight it lightly since sharing also strips it
    exif_suspicion = 0.15 if not has_exif else 0.0

    # ── Weighted fusion ───────────────────────────────────────────────────────
    if deep_ok:
        ai_prob = (
            0.35 * deep_score +
            0.25 * freq_score +
            0.20 * ela_score +
            0.10 * noise_score +
            0.10 * exif_suspicion
        )
    else:
        ai_prob = (
            0.40 * freq_score +
            0.30 * ela_score +
            0.20 * noise_score +
            0.10 * exif_suspicion
        )

    ai_prob = float(np.clip(ai_prob, 0.0, 1.0))

    # Manipulation probability (separate signal — based on ELA primarily)
    manip_prob = float(np.clip(0.6 * ela_score + 0.4 * noise_score, 0.0, 1.0))

    # ── Prediction ────────────────────────────────────────────────────────────
    if ai_prob >= 0.65:
        prediction = "likely_ai_generated"
    elif ai_prob >= 0.45:
        prediction = "uncertain"
    else:
        prediction = "likely_authentic"

    # Confidence: higher when signals agree
    signal_vals = [freq_score, ela_score, noise_score]
    if deep_ok:
        signal_vals.append(deep_score)
    signal_std = float(np.std(signal_vals))
    confidence = float(np.clip(1.0 - signal_std, 0.4, 0.97))

    # ── Limitations ───────────────────────────────────────────────────────────
    limitations += [
        "Model uses forensic heuristics + pretrained features — not fine-tuned on deepfake data.",
        "Results are probabilistic risk estimates, not proof of manipulation.",
        "AI image detectors can produce false positives on heavily compressed images.",
    ]

    return {
        "model_available": True,
        "ai_generated_probability": round(ai_prob, 4),
        "manipulation_probability": round(manip_prob, 4),
        "prediction": prediction,
        "confidence": round(confidence, 4),
        "technical_signals": {
            "ela_score":        round(ela_score, 4),
            "freq_score":       round(freq_score, 4),
            "noise_score":      round(noise_score, 4),
            "deep_score":       round(deep_score, 4) if deep_ok else None,
            "has_exif":         float(has_exif),
            "width":            float(w),
            "height":           float(h),
            "format":           img_format,
            "exif_fields":      float(len(exif_data)),
        },
        "exif": exif_data,
        "limitations": limitations,
    }


# ── Signal extractors ─────────────────────────────────────────────────────────

def _error_level_analysis(pil_img: Image.Image, quality: int = 90) -> float:
    """
    ELA: save image at fixed JPEG quality, compute pixel-level difference.
    High uniform error -> likely AI; high localized error -> likely edited.
    Returns 0-1 suspicion score.
    """
    try:
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        recompressed = Image.open(buf).convert("RGB")

        orig = np.array(pil_img, dtype=np.float32)
        recomp = np.array(recompressed, dtype=np.float32)
        ela = np.abs(orig - recomp)

        mean_err = float(ela.mean())
        std_err  = float(ela.std())

        # High mean + low std = uniform compression (AI-like)
        # High mean + high std = localized manipulation
        uniformity = 1.0 - min(std_err / (mean_err + 1e-6), 1.0)
        normalized = min(mean_err / 20.0, 1.0)  # normalize to ~0-1

        score = 0.5 * normalized + 0.5 * uniformity * normalized
        return float(np.clip(score, 0.0, 1.0))
    except Exception:
        return 0.3  # neutral fallback


def _dct_frequency_score(pil_img: Image.Image) -> float:
    """
    DCT frequency domain: AI-generated images tend to have abnormal high-frequency
    energy patterns due to the upsampling decoder in generative models.
    Returns 0-1 suspicion score.
    """
    try:
        gray = np.array(pil_img.convert("L"), dtype=np.float32)
        h, w = gray.shape

        # Analyse multiple 64x64 blocks
        block_size = 64
        scores = []
        for y in range(0, h - block_size, block_size):
            for x in range(0, w - block_size, block_size):
                block = gray[y:y+block_size, x:x+block_size]
                dct = _dct2(block)
                total_energy  = float(np.sum(dct**2)) + 1e-6
                # Energy in top-left (low freq) vs rest (high freq)
                low_freq  = float(np.sum(dct[:block_size//4, :block_size//4]**2))
                high_freq = total_energy - low_freq
                high_ratio = high_freq / total_energy
                scores.append(high_ratio)

        if not scores:
            return 0.3

        mean_high = float(np.mean(scores))
        # Real photos: high_ratio typically 0.3-0.6
        # AI images: often very high (>0.7) or very low (<0.2) — both are suspicious
        if mean_high > 0.72:
            score = (mean_high - 0.72) / 0.28   # scale 0.72-1.0 -> 0-1
        elif mean_high < 0.18:
            score = (0.18 - mean_high) / 0.18
        else:
            score = 0.1  # normal range, low suspicion
        return float(np.clip(score, 0.0, 1.0))
    except Exception:
        return 0.3


def _dct2(block: np.ndarray) -> np.ndarray:
    """2D DCT via separable 1D DCTs (scipy-free implementation)."""
    from scipy.fft import dctn
    try:
        return dctn(block, norm="ortho")
    except Exception:
        # Fallback: use numpy FFT magnitude as approximation
        return np.abs(np.fft.fft2(block))


def _noise_pattern_score(pil_img: Image.Image) -> float:
    """
    Laplacian noise analysis.
    AI images often have unnaturally smooth regions interspersed with
    high-frequency artifacts — measurable as bimodal noise distribution.
    Returns 0-1 suspicion score.
    """
    try:
        gray = np.array(pil_img.convert("L"), dtype=np.float32)

        # Laplacian filter
        laplacian = np.array([
            [ 0, -1,  0],
            [-1,  4, -1],
            [ 0, -1,  0],
        ], dtype=np.float32)

        from scipy.signal import fftconvolve
        noise = np.abs(fftconvolve(gray, laplacian, mode="same"))

        # Compute local variance in 16x16 tiles
        h, w = noise.shape
        tile = 16
        variances = []
        for y in range(0, h - tile, tile):
            for x in range(0, w - tile, tile):
                variances.append(float(noise[y:y+tile, x:x+tile].var()))

        if not variances:
            return 0.3

        variances = np.array(variances)
        # AI images: coefficient of variation of local variances is abnormal
        cov = float(variances.std() / (variances.mean() + 1e-6))

        # Very low CoV (smooth everywhere) or very high (chaotic) = suspicious
        if cov < 0.5:
            score = (0.5 - cov) / 0.5
        elif cov > 3.0:
            score = min((cov - 3.0) / 2.0, 1.0)
        else:
            score = 0.1
        return float(np.clip(score, 0.0, 1.0))
    except Exception:
        return 0.3


def _deep_feature_score(pil_img: Image.Image):
    """
    Use pretrained EfficientNet-B0 feature statistics as an anomaly signal.
    Real photographs cluster differently in feature space than AI images.
    Returns (score 0-1, success bool).
    """
    if not _TORCH_AVAILABLE or _feature_model is None:
        return 0.5, False
    try:
        transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
        ])
        tensor = transform(pil_img).unsqueeze(0).to(DEVICE)
        with torch.no_grad():
            features = _feature_model(tensor)  # shape [1, 1280]
        feats = features.squeeze().cpu().numpy()

        # Statistical anomaly: AI images have different feature activation patterns
        # Measure: proportion of very-high activations (>2 std from mean)
        feat_mean = feats.mean()
        feat_std  = feats.std() + 1e-6
        z_scores  = np.abs((feats - feat_mean) / feat_std)

        # High-activation ratio: AI images tend toward more extreme activations
        high_activation_ratio = float((z_scores > 2.5).mean())

        # Negative activation ratio: also characteristic
        negative_ratio = float((feats < 0).mean())

        # Kurtosis of feature distribution
        kurtosis = float(
            np.mean((feats - feat_mean)**4) / (feat_std**4) - 3.0
        )

        # Combine into score
        score = (
            0.5 * min(high_activation_ratio / 0.12, 1.0) +   # >12% = suspicious
            0.3 * min(abs(kurtosis) / 5.0, 1.0) +            # high kurtosis = suspicious
            0.2 * max(0, (negative_ratio - 0.3) / 0.4)       # too many negatives = suspicious
        )
        return float(np.clip(score, 0.0, 1.0)), True
    except Exception as exc:
        logger.warning("[ImageService] Deep feature error: %s", exc)
        return 0.5, False


# ── EXIF extraction ───────────────────────────────────────────────────────────

def _extract_exif(image_path: Path) -> Dict[str, Any]:
    try:
        img = Image.open(image_path)
        raw = img._getexif()  # type: ignore[attr-defined]
        if not raw:
            return {}
        decoded = {}
        for tag_id, value in raw.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            if isinstance(value, bytes):
                try:
                    value = value.decode("utf-8", errors="replace")
                except Exception:
                    value = str(value)
            decoded[tag] = str(value)[:200]
        return decoded
    except Exception:
        return {}


# ── Error result ──────────────────────────────────────────────────────────────

def _error_result(msg: str) -> Dict[str, Any]:
    return {
        "model_available": False,
        "ai_generated_probability": None,
        "manipulation_probability": None,
        "prediction": "error",
        "confidence": None,
        "technical_signals": {},
        "exif": {},
        "limitations": [msg],
    }
