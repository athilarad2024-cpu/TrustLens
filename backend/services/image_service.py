"""
services/image_service.py

AI-generated / manipulated image detection pipeline for TrustAI.
Fuses Gemini Multimodal Vision analysis with local forensic signals
(Error Level Analysis, DCT 2D frequency analysis, noise pattern analysis,
and deep feature extraction).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from services.gemini_analyzer import GeminiImageAnalyzer, is_gemini_configured
from services.forensics_analyzer import MediaForensicsAnalyzer

logger = logging.getLogger("trustai.image")

# Alias for health check
_model = True


def analyze_image(image_path: Path) -> Dict[str, Any]:
    """
    Analyze an image for AI generation, deepfake artifacts, and digital manipulation.
    Combines Gemini Multimodal Vision with local forensic analysis.

    Returns structured JSON:
    {
      "media_type": "image",
      "classification": "likely_ai_generated | likely_authentic | uncertain",
      "ai_probability": 0.0,
      "confidence": 0.0,
      "reasons": [],
      "visual_signals": [],
      "limitations": []
    }
    """
    limitations: List[str] = []

    # 1. Load image safely
    try:
        pil_img = Image.open(image_path).convert("RGB")
    except Exception as exc:
        return _error_result(f"Could not open image: {exc}")

    w, h = pil_img.size
    img_format = Path(image_path).suffix.lstrip(".").upper() or "JPEG"

    # 2. Run Local Forensics
    forensics = MediaForensicsAnalyzer.analyze_image_forensics(pil_img, file_path=image_path)
    forensic_ai_score = forensics["forensic_ai_score"]
    ela_score = forensics["ela_score"]
    freq_score = forensics["freq_score"]
    noise_score = forensics["noise_score"]
    deep_score = forensics["deep_score"]
    has_exif = forensics["has_exif"]

    if not forensics["deep_features_available"]:
        limitations.append("Deep feature neural extractor unavailable; using statistical heuristics.")

    if not has_exif:
        limitations.append("Image contains no EXIF metadata (common on web/social platforms; not proof of AI).")

    # 3. Run Gemini Multimodal Analysis
    gemini_result = GeminiImageAnalyzer.analyze(pil_img)
    gemini_available = gemini_result.get("available", False)

    reasons: List[str] = []
    visual_signals: List[Dict[str, Any]] = []

    if gemini_available:
        gemini_prob = gemini_result["ai_probability"]
        gemini_conf = gemini_result["confidence"]
        reasons.extend(gemini_result.get("reasons", []))
        visual_signals.extend(gemini_result.get("visual_signals", []))
        limitations.extend(gemini_result.get("limitations", []))

        # Unified Fusion:
        # Gemini multimodal visual intelligence (65%) + Local forensics (35%)
        # Note: Forensics are conservative to protect against compression false positives.
        ai_prob = 0.65 * gemini_prob + 0.35 * forensic_ai_score
        confidence = 0.70 * gemini_conf + 0.30 * (0.85 if forensics["deep_features_available"] else 0.65)
    else:
        # Fallback to local forensics only
        limitations.extend(gemini_result.get("limitations", []))
        ai_prob = forensic_ai_score
        confidence = 0.55 if forensics["deep_features_available"] else 0.40

        # Generate forensic reasons
        if freq_score > 0.6:
            reasons.append("Abnormal high-frequency energy distribution detected by DCT spectral analysis.")
        if ela_score > 0.55:
            reasons.append("Elevated compression rate variance detected by Error Level Analysis.")
        if not reasons:
            reasons.append("No significant synthetic rendering artifacts detected by local forensic filters.")

    # Clamp
    ai_prob = float(np.clip(ai_prob, 0.0, 1.0))
    confidence = float(np.clip(confidence, 0.2, 0.98))

    # 4. Uncertainty & Classification Calibration
    # 0.00 - 0.30: likely_authentic
    # 0.30 - 0.70: uncertain (e.g. 52.8% AI probability is UNCERTAIN, not AI-generated)
    # 0.70 - 1.00: likely_ai_generated
    if ai_prob >= 0.70:
        classification = "likely_ai_generated"
    elif ai_prob <= 0.30:
        classification = "likely_authentic"
    else:
        classification = "uncertain"

    # Manipulation probability (ELA + Noise fusion)
    manip_prob = float(np.clip(0.6 * ela_score + 0.4 * noise_score, 0.0, 1.0))

    # Standard limitations
    limitations.append("AI detection is probabilistic and serves as decision support, not an absolute truth oracle.")
    limitations.append("Severe compression, resizing, or extreme editing can alter forensic indicators.")

    technical_signals = {
        "format": img_format,
        "width": w,
        "height": h,
        "has_exif": has_exif,
        "ela_score": round(ela_score, 4),
        "freq_score": round(freq_score, 4),
        "noise_score": round(noise_score, 4),
        "deep_score": round(deep_score, 4) if deep_score is not None else None,
        "gemini_available": gemini_available,
        "gemini_ai_prob": round(gemini_result.get("ai_probability", 0.5), 4) if gemini_available else None,
    }

    return {
        "media_type": "image",
        "type": "image",
        "classification": classification,
        "prediction": classification,
        "ai_probability": round(ai_prob, 4),
        "ai_generated_probability": round(ai_prob, 4),
        "manipulation_probability": round(manip_prob, 4),
        "confidence": round(confidence, 4),
        "reasons": reasons,
        "visual_signals": visual_signals,
        "technical_signals": technical_signals,
        "model_available": True,
        "gemini_available": gemini_available,
        "limitations": list(dict.fromkeys(limitations)),  # deduplicate
    }


def _error_result(msg: str) -> Dict[str, Any]:
    return {
        "media_type": "image",
        "type": "image",
        "classification": "uncertain",
        "prediction": "uncertain",
        "ai_probability": 0.5,
        "ai_generated_probability": 0.5,
        "manipulation_probability": 0.5,
        "confidence": 0.0,
        "reasons": [msg],
        "visual_signals": [],
        "technical_signals": {},
        "model_available": False,
        "gemini_available": False,
        "limitations": [msg],
    }
