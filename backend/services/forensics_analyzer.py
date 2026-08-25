"""
services/forensics_analyzer.py
MediaForensicsAnalyzer — Local Forensic Analysis Engine for TrustAI.

Provides:
  • Image forensics: ELA (Error Level Analysis), DCT frequency analysis,
    Laplacian noise pattern analysis, EXIF metadata extraction, deep feature extraction.
  • Video forensics: Multi-position frame extraction (0%, 25%, 50%, 75%, 100%),
    inter-frame structural variance / optical delta, face detection crops.

False Positive Protection:
  • Forensic signals are strictly supplementary.
  • Normal camera compression, resizing, and missing EXIF are recorded as
    informational signals only and never treated as proof of AI generation.
"""

import io
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ExifTags

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

logger = logging.getLogger("trustai.forensics")

DEVICE = ("cuda" if _TORCH_AVAILABLE and torch.cuda.is_available() else "cpu") if _TORCH_AVAILABLE else "cpu"
_feature_model = None
_feature_load_error: Optional[str] = None


def _init_feature_model() -> None:
    global _feature_model, _feature_load_error
    if not _TORCH_AVAILABLE:
        _feature_load_error = "PyTorch not installed"
        return
    try:
        import torchvision.models as tvm
        m = tvm.efficientnet_b0(weights=tvm.EfficientNet_B0_Weights.IMAGENET1K_V1)
        m.classifier = torch.nn.Identity()
        m.to(DEVICE).eval()
        _feature_model = m
    except Exception as exc:
        _feature_load_error = str(exc)


_init_feature_model()


class MediaForensicsAnalyzer:
    """
    Comprehensive media forensics analysis for images and video frames.
    """

    # ── Image Forensics ───────────────────────────────────────────────────────

    @classmethod
    def analyze_image_forensics(cls, pil_img: Image.Image, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Run all local forensic checks on a PIL Image.
        """
        w, h = pil_img.size
        exif_data = cls.extract_exif(file_path) if file_path else {}
        has_exif = len(exif_data) > 0

        # Signal 1: ELA
        ela_score = cls.compute_ela(pil_img)

        # Signal 2: DCT Frequency Analysis
        freq_score = cls.compute_dct_frequency(pil_img)

        # Signal 3: Noise Pattern Analysis
        noise_score = cls.compute_noise_pattern(pil_img)

        # Signal 4: Deep Feature Extractor
        deep_score, deep_ok = cls.compute_deep_features(pil_img)

        # Calibration note: Forensic score should be conservative to avoid false positives on compressed photos
        # Compression can elevate ELA/Noise without being AI-generated.
        forensic_ai_score = (
            0.35 * freq_score +
            0.25 * (deep_score if deep_ok else freq_score) +
            0.20 * min(ela_score, 0.7) +
            0.20 * min(noise_score, 0.7)
        )
        forensic_ai_score = float(np.clip(forensic_ai_score, 0.0, 1.0))

        return {
            "forensic_ai_score": round(forensic_ai_score, 4),
            "ela_score": round(ela_score, 4),
            "freq_score": round(freq_score, 4),
            "noise_score": round(noise_score, 4),
            "deep_score": round(deep_score, 4) if deep_ok else None,
            "deep_features_available": deep_ok,
            "has_exif": has_exif,
            "exif_tags_count": len(exif_data),
            "width": w,
            "height": h,
        }

    @staticmethod
    def extract_exif(image_path: Path) -> Dict[str, Any]:
        """Extract EXIF tags safely from file path."""
        try:
            with Image.open(image_path) as img:
                raw = img._getexif()
                if not raw:
                    return {}
                return {
                    ExifTags.TAGS.get(k, str(k)): str(v)[:80]
                    for k, v in raw.items()
                    if k in ExifTags.TAGS
                }
        except Exception:
            return {}

    @staticmethod
    def compute_ela(pil_img: Image.Image, quality: int = 90) -> float:
        """
        Error Level Analysis (ELA).
        Re-saves image at quality=90 and measures pixel-level difference.
        Returns float [0.0, 1.0].
        """
        try:
            buf = io.BytesIO()
            rgb_img = pil_img.convert("RGB")
            rgb_img.save(buf, "JPEG", quality=quality)
            buf.seek(0)
            resaved = Image.open(buf)

            diff = ImageChops.difference(rgb_img, resaved)
            arr = np.asarray(diff, dtype=np.float32)
            mean_diff = float(arr.mean())
            max_diff = float(arr.max())

            score = (mean_diff / 15.0) * 0.7 + (max_diff / 180.0) * 0.3
            return float(np.clip(score, 0.0, 1.0))
        except Exception as exc:
            logger.warning("[MediaForensicsAnalyzer] ELA error: %s", exc)
            return 0.3

    @staticmethod
    def compute_dct_frequency(pil_img: Image.Image) -> float:
        """
        2D DCT Frequency Analysis.
        Measures high vs low frequency energy distribution.
        """
        try:
            gray = np.array(pil_img.convert("L"), dtype=np.float32)
            if gray.shape[0] < 32 or gray.shape[1] < 32:
                return 0.3

            # Crop or resize center 256x256
            h, w = gray.shape
            ch, cw = min(h, 256), min(w, 256)
            start_y, start_x = (h - ch) // 2, (w - cw) // 2
            patch = gray[start_y:start_y + ch, start_x:start_x + cw]

            dct = cv2.dct(patch)
            dct_abs = np.abs(dct)

            rows, cols = dct_abs.shape
            r_idx, c_idx = np.ogrid[:rows, :cols]
            dist = np.sqrt(r_idx**2 + c_idx**2)
            max_dist = math.sqrt(rows**2 + cols**2)

            low_mask = dist < (max_dist * 0.25)
            high_mask = dist > (max_dist * 0.50)

            low_energy = float(dct_abs[low_mask].sum()) + 1e-6
            high_energy = float(dct_abs[high_mask].sum())

            ratio = high_energy / low_energy
            score = 1.0 / (1.0 + math.exp(-6.0 * (ratio - 0.15)))
            return float(np.clip(score, 0.0, 1.0))
        except Exception as exc:
            logger.warning("[MediaForensicsAnalyzer] DCT error: %s", exc)
            return 0.35

    @staticmethod
    def compute_noise_pattern(pil_img: Image.Image) -> float:
        """
        Noise pattern analysis using Laplacian operator.
        """
        try:
            gray = np.array(pil_img.convert("L"), dtype=np.float32)
            lap = cv2.Laplacian(gray, cv2.CV_32F)
            local_vars = []
            step = 32
            h, w = lap.shape
            for y in range(0, h - step, step):
                for x in range(0, w - step, step):
                    blk = lap[y:y + step, x:x + step]
                    local_vars.append(float(np.var(blk)))

            if not local_vars:
                return 0.35

            var_of_vars = float(np.std(local_vars)) / (float(np.mean(local_vars)) + 1e-4)
            score = 1.0 - (1.0 / (1.0 + math.exp(-4.0 * (var_of_vars - 0.5))))
            return float(np.clip(score, 0.0, 1.0))
        except Exception as exc:
            logger.warning("[MediaForensicsAnalyzer] Noise analysis error: %s", exc)
            return 0.35

    @staticmethod
    def compute_deep_features(pil_img: Image.Image) -> Tuple[float, bool]:
        """Extract deep features using EfficientNet-B0 feature extractor."""
        if _feature_model is None or not _TORCH_AVAILABLE:
            return 0.5, False
        try:
            transform = T.Compose([
                T.Resize((224, 224)),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
            tensor = transform(pil_img.convert("RGB")).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                feat = _feature_model(tensor)
                feat = feat.squeeze().cpu().numpy()

            l2_norm = float(np.linalg.norm(feat))
            sparsity = float((np.abs(feat) < 0.01).mean())
            score = 0.5 * min(1.0, l2_norm / 80.0) + 0.5 * min(1.0, sparsity / 0.5)
            return float(np.clip(score, 0.0, 1.0)), True
        except Exception as exc:
            logger.warning("[MediaForensicsAnalyzer] Deep feature error: %s", exc)
            return 0.5, False

    # ── Video Forensics & Frame Sampling ──────────────────────────────────────

    @classmethod
    def sample_video_frames(
        cls,
        video_path: Path,
        target_positions: Optional[List[float]] = None,
        max_frames: int = 12
    ) -> Tuple[List[Image.Image], Dict[str, Any]]:
        """
        Sample representative video frames throughout the video:
        Default positions: [0.02, 0.25, 0.50, 0.75, 0.98] + evenly spaced intermediates.

        Returns:
            (list_of_pil_frames, video_metadata_dict)
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning("Could not open video file: %s", video_path)
            return [], {}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_sec = total_frames / max(fps, 1.0)

        metadata = {
            "total_frames": total_frames,
            "fps": round(fps, 2),
            "width": width,
            "height": height,
            "duration_seconds": round(duration_sec, 2),
        }

        if total_frames <= 0:
            cap.release()
            return [], metadata

        # Determine frame indices to sample
        positions = target_positions or [0.02, 0.15, 0.25, 0.40, 0.50, 0.65, 0.75, 0.90, 0.98]
        frame_indices = sorted(list(set(
            min(total_frames - 1, max(0, int(pos * total_frames)))
            for pos in positions
        )))

        sampled_pil_frames: List[Image.Image] = []
        for idx in frame_indices[:max_frames]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                # Convert BGR to RGB
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                sampled_pil_frames.append(Image.fromarray(rgb))

        cap.release()
        return sampled_pil_frames, metadata

    @classmethod
    def compute_temporal_consistency(cls, pil_frames: List[Image.Image]) -> Dict[str, Any]:
        """
        Compute inter-frame delta and temporal variance across the frame sequence.
        Returns temporal metrics dictionary.
        """
        if len(pil_frames) < 2:
            return {
                "temporal_consistency_score": 0.85,
                "frame_deltas": [],
                "mean_delta": 0.0,
                "delta_variance": 0.0,
            }

        deltas = []
        prev_gray = None

        for frame in pil_frames:
            gray = cv2.resize(np.array(frame.convert("L")), (128, 128))
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                norm_diff = float(diff.mean()) / 255.0
                deltas.append(norm_diff)
            prev_gray = gray

        mean_delta = float(np.mean(deltas)) if deltas else 0.0
        std_delta = float(np.std(deltas)) if deltas else 0.0

        # Normal real video has smooth temporal flow (consistent moderate delta)
        # Deepfakes often have sudden spikes / jitter in facial boundaries
        consistency_score = 1.0 - min(1.0, std_delta * 3.0 + (1.0 if mean_delta > 0.4 else 0.0) * 0.2)
        consistency_score = float(np.clip(consistency_score, 0.1, 0.98))

        return {
            "temporal_consistency_score": round(consistency_score, 4),
            "frame_deltas": [round(d, 4) for d in deltas],
            "mean_delta": round(mean_delta, 4),
            "delta_variance": round(std_delta, 4),
        }
