"""
services/video_service.py
Video deepfake / manipulation detection service — Section 16.

Pipeline:
  Video -> sampled frames -> face detection/crop -> frame classifier
       -> frame scores -> aggregation -> video-level probability

Face detection uses OpenCV Haar Cascade (no external dependency).
Model: EfficientNet-B0 frame classifier loaded from trained_models/deepfake_model.pt
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
try:
    import torch
    import torch.nn.functional as F
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    F = None      # type: ignore
    _TORCH_AVAILABLE = False
from PIL import Image

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "trained_models" / "deepfake_model.pt"
DEVICE = ("cuda" if torch.cuda.is_available() else "cpu") if _TORCH_AVAILABLE else "cpu"

# ── Frame sampling config ─────────────────────────────────────────────────────
TARGET_FRAMES = 40          # target number of frames to sample
MIN_FRAMES_REQUIRED = 5     # minimum frames needed for a reliable estimate
FACE_DETECTION_SCALE = 1.1
FACE_DETECTION_NEIGHBORS = 5
FACE_CROP_MARGIN = 0.2      # fractional margin around face crop

_model = None
_model_meta: Dict[str, Any] = {}
_model_load_error: Optional[str] = None
_face_cascade: Optional[Any] = None  # cv2.CascadeClassifier (Any for OpenCV 5.x compat)


def _load_model() -> None:
    global _model, _model_meta, _model_load_error
    if not _TORCH_AVAILABLE:
        _model_load_error = "PyTorch not installed. Run: pip install torch torchvision"
        logger.warning("[VideoService] %s", _model_load_error)
        return
    try:
        import timm
        checkpoint = torch.load(MODEL_PATH, map_location=DEVICE, weights_only=False)
        arch = checkpoint.get("model_arch", "efficientnet_b0")
        num_classes = len(checkpoint.get("class_names", ["fake", "real"]))
        model = timm.create_model(arch, pretrained=False, num_classes=num_classes)
        model.load_state_dict(checkpoint["state_dict"])
        model.to(DEVICE).eval()
        _model = model
        _model_meta = checkpoint
        logger.info("[VideoService] Deepfake model loaded: %s", MODEL_PATH)
    except FileNotFoundError:
        _model_load_error = (
            f"Deepfake model not found at {MODEL_PATH}. "
            "Run backend/models/deepfake_model/train_deepfake_model.py first."
        )
        logger.warning("[VideoService] %s", _model_load_error)
    except Exception as exc:
        _model_load_error = str(exc)
        logger.error("[VideoService] Load error: %s", exc)


def _load_face_cascade() -> None:
    """
    Load face detector. OpenCV 5.x removed CascadeClassifier.
    Uses FaceDetectorYN (YuNet) when available, otherwise falls back to None
    (in which case full frames are used without cropping).
    """
    global _face_cascade
    try:
        # OpenCV 5.x: FaceDetectorYN (requires onnx model — may not be bundled)
        if hasattr(cv2, 'FaceDetectorYN_create'):
            # Try to create a minimal detector; if model file missing, will fail silently
            _face_cascade = None  # FaceDetectorYN requires external .onnx — skip for now
            logger.info("[VideoService] OpenCV 5 detected. Using full-frame mode (no face crop).")
        elif hasattr(cv2, 'CascadeClassifier'):
            # OpenCV 4.x path
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            _face_cascade = cv2.CascadeClassifier(cascade_path)
            logger.info("[VideoService] Haar cascade loaded.")
        else:
            logger.warning("[VideoService] No face detector available — using full frames.")
    except Exception as exc:
        logger.warning("[VideoService] Face detector load failed: %s", exc)
        _face_cascade = None


_load_model()
_load_face_cascade()


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_video(video_path: Path) -> Dict[str, Any]:
    """
    Analyze a video file for deepfake / manipulation signals.

    Returns:
        model_available, deepfake_probability, frames_analyzed,
        suspicious_frames, suspicious_frame_ratio, prediction,
        confidence, technical_signals, limitations
    """
    limitations: List[str] = []

    # ── Extract frames ─────────────────────────────────────────────────────────
    frames, video_meta = _sample_frames(video_path)
    if not frames:
        return {
            "model_available": False,
            "deepfake_probability": None,
            "frames_analyzed": 0,
            "suspicious_frames": 0,
            "suspicious_frame_ratio": None,
            "prediction": "analysis_unavailable",
            "confidence": None,
            "technical_signals": video_meta,
            "limitations": [
                "Could not extract frames from the video. "
                "Ensure the video codec is supported (mp4, avi, mov, mkv, webm)."
            ],
        }

    # ── Face detection and cropping ────────────────────────────────────────────
    face_crops, faces_found = _extract_face_crops(frames)

    if not faces_found or len(face_crops) < MIN_FRAMES_REQUIRED:
        limitations.append(
            f"Insufficient detectable faces ({len(face_crops)} face crops from "
            f"{len(frames)} sampled frames). Deepfake analysis requires clear, "
            "front-facing faces. Results are not reliable for this video."
        )
        # Fall back to full-frame analysis if face crops too few
        if len(face_crops) < MIN_FRAMES_REQUIRED:
            face_crops = frames[:TARGET_FRAMES]
            limitations.append("Falling back to full-frame analysis (less accurate).")

    # ── Model inference ────────────────────────────────────────────────────────
    if _model is None:
        return {
            "model_available": False,
            "deepfake_probability": None,
            "frames_analyzed": len(frames),
            "suspicious_frames": 0,
            "suspicious_frame_ratio": None,
            "prediction": "model_unavailable",
            "confidence": None,
            "technical_signals": video_meta,
            "limitations": [_model_load_error or "Deepfake model not loaded."] + limitations,
        }

    frame_probs = _run_frame_inference(face_crops)

    if not frame_probs:
        return {
            "model_available": False,
            "deepfake_probability": None,
            "frames_analyzed": len(frames),
            "suspicious_frames": 0,
            "suspicious_frame_ratio": None,
            "prediction": "inference_failed",
            "confidence": None,
            "technical_signals": video_meta,
            "limitations": ["Frame-level inference failed."] + limitations,
        }

    # ── Aggregation ───────────────────────────────────────────────────────────
    mean_prob = float(np.mean(frame_probs))
    median_prob = float(np.median(frame_probs))
    # Weighted: give slightly more weight to the mean for stability
    agg_prob = 0.6 * mean_prob + 0.4 * median_prob
    suspicious_frames = int(sum(1 for p in frame_probs if p >= 0.5))
    suspicious_ratio = suspicious_frames / max(len(frame_probs), 1)

    prediction = "likely_deepfake" if agg_prob >= 0.5 else "likely_authentic"
    # Confidence is higher when frames agree
    agreement = 1.0 - float(np.std(frame_probs))
    confidence = max(0.0, min(1.0, agreement))

    if len(face_crops) < 10:
        limitations.append("Small number of frames analyzed; confidence is limited.")
        limitations.append("Model accuracy depends on training dataset quality.")

    return {
        "model_available": True,
        "deepfake_probability": round(agg_prob, 4),
        "frames_analyzed": len(frames),
        "suspicious_frames": suspicious_frames,
        "suspicious_frame_ratio": round(suspicious_ratio, 4),
        "prediction": prediction,
        "confidence": round(confidence, 4),
        "technical_signals": video_meta,
        "limitations": limitations,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sample_frames(video_path: Path) -> Tuple[List[np.ndarray], Dict]:
    """Sample TARGET_FRAMES evenly from a video. Returns (frame list, metadata)."""
    cap = cv2.VideoCapture(str(video_path))
    meta: Dict[str, Any] = {}
    frames: List[np.ndarray] = []

    if not cap.isOpened():
        return frames, meta

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration_s = total_frames / fps if fps > 0 else 0

    meta = {
        "total_frames": total_frames,
        "fps": round(fps, 2),
        "width": width,
        "height": height,
        "duration_seconds": round(duration_s, 2),
    }

    if total_frames == 0:
        cap.release()
        return frames, meta

    step = max(1, total_frames // TARGET_FRAMES)
    indices = list(range(0, total_frames, step))[:TARGET_FRAMES]

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    cap.release()
    return frames, meta


def _extract_face_crops(frames: List[np.ndarray]) -> Tuple[List[np.ndarray], bool]:
    """
    Detect and crop faces from each frame.
    When face detection is unavailable (OpenCV 5 without model file),
    returns full frames so inference still runs.
    Returns (list_of_cropped_or_full_arrays, at_least_one_face_found).
    """
    crops: List[np.ndarray] = []
    any_face = False

    # No cascade available — fall back to full frames
    if _face_cascade is None:
        return frames, False

    # OpenCV 4.x Haar cascade path
    if not hasattr(_face_cascade, 'detectMultiScale'):
        return frames, False

    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        faces = _face_cascade.detectMultiScale(
            gray,
            scaleFactor=FACE_DETECTION_SCALE,
            minNeighbors=FACE_DETECTION_NEIGHBORS,
            minSize=(60, 60),
        )
        if len(faces) > 0:
            any_face = True
            x, y, w, h = faces[0]  # take first face
            h_img, w_img = frame.shape[:2]
            mx = int(w * FACE_CROP_MARGIN)
            my = int(h * FACE_CROP_MARGIN)
            x1 = max(0, x - mx)
            y1 = max(0, y - my)
            x2 = min(w_img, x + w + mx)
            y2 = min(h_img, y + h + my)
            crops.append(frame[y1:y2, x1:x2])

    return crops, any_face


def _run_frame_inference(crops: List[np.ndarray]) -> List[float]:
    """Run the deepfake classifier on each face crop and return probabilities."""
    from utils.preprocessing import INFERENCE_TRANSFORM

    fake_idx = _model_meta.get("fake_class_index", 0)
    probs: List[float] = []

    with torch.no_grad():
        for crop in crops:
            try:
                pil_img = Image.fromarray(crop).convert("RGB")
                tensor = INFERENCE_TRANSFORM(pil_img).unsqueeze(0).to(DEVICE)
                logits = _model(tensor)
                p = F.softmax(logits, dim=1)[0][fake_idx].item()
                probs.append(float(p))
            except Exception as exc:
                logger.debug("[VideoService] Frame inference error: %s", exc)

    return probs
