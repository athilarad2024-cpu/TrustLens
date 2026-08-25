"""
services/video_service.py

Video deepfake and AI-generated video detection service for TrustAI.
Pipeline:
  1. Multi-position representative keyframe extraction across video duration
     (beginning, 15%, 25%, 40%, 50%, 65%, 75%, 90%, end).
  2. Gemini Multimodal Video analysis for frame-level and cross-frame temporal reasoning.
  3. Local temporal consistency & pixel/optical flow delta calculations.
  4. Unified fusion, calibration, and false-positive protection.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from services.gemini_analyzer import GeminiVideoAnalyzer, is_gemini_configured
from services.forensics_analyzer import MediaForensicsAnalyzer

logger = logging.getLogger("trustai.video")

# Alias for health check
_model = True


def analyze_video(video_path: Path) -> Dict[str, Any]:
    """
    Analyze a video file for deepfake manipulation and AI generation.
    Returns structured JSON:
    {
      "media_type": "video",
      "classification": "likely_ai_generated | likely_authentic | uncertain",
      "ai_probability": 0.0,
      "confidence": 0.0,
      "frames_analyzed": 0,
      "temporal_consistency_score": 0.0,
      "reasons": [],
      "visual_signals": [],
      "temporal_signals": [],
      "limitations": []
    }
    """
    limitations: List[str] = []

    # 1. Sample representative frames throughout video
    sampled_frames, video_meta = MediaForensicsAnalyzer.sample_video_frames(
        video_path,
        target_positions=[0.02, 0.15, 0.25, 0.40, 0.50, 0.65, 0.75, 0.90, 0.98],
        max_frames=10,
    )

    if not sampled_frames:
        return _error_result("Could not decode frames from video. Supported formats: MP4, AVI, MOV, MKV, WEBM.")

    frames_count = len(sampled_frames)

    # 2. Local Temporal Consistency Analysis
    temporal_forensics = MediaForensicsAnalyzer.compute_temporal_consistency(sampled_frames)
    local_temporal_score = temporal_forensics["temporal_consistency_score"]

    # 3. Gemini Multimodal Video Analysis
    gemini_result = GeminiVideoAnalyzer.analyze(sampled_frames)
    gemini_available = gemini_result.get("available", False)

    reasons: List[str] = []
    visual_signals: List[Dict[str, Any]] = []
    temporal_signals: List[Dict[str, Any]] = []

    if gemini_available:
        gemini_prob = gemini_result["ai_probability"]
        gemini_conf = gemini_result["confidence"]
        gemini_temporal = gemini_result["temporal_consistency_score"]

        reasons.extend(gemini_result.get("reasons", []))
        visual_signals.extend(gemini_result.get("visual_signals", []))
        temporal_signals.extend(gemini_result.get("temporal_signals", []))
        limitations.extend(gemini_result.get("limitations", []))

        # Blended temporal consistency score
        final_temporal_score = 0.65 * gemini_temporal + 0.35 * local_temporal_score

        # Temporal instability penalty/bonus
        temporal_risk = 1.0 - final_temporal_score

        # Unified probability: Gemini multimodal analysis (70%) + temporal motion delta (30%)
        ai_prob = 0.70 * gemini_prob + 0.30 * temporal_risk
        confidence = 0.75 * gemini_conf + 0.25 * (0.85 if frames_count >= 5 else 0.55)
    else:
        # Fallback to local heuristics
        limitations.extend(gemini_result.get("limitations", []))
        final_temporal_score = local_temporal_score
        temporal_risk = 1.0 - local_temporal_score

        # Heuristic estimation
        ai_prob = 0.5 * temporal_risk + 0.5 * (0.35 if frames_count >= 5 else 0.5)
        confidence = 0.45 if frames_count >= 5 else 0.30

        if local_temporal_score > 0.8:
            reasons.append(f"Temporal consistency across {frames_count} sampled frames is smooth and natural.")
        elif local_temporal_score < 0.5:
            reasons.append("Abnormal inter-frame variance detected across sampled video keyframes.")
        else:
            reasons.append(f"Processed {frames_count} representative keyframes with moderate temporal stability.")

    # Clamp
    ai_prob = float(np.clip(ai_prob, 0.0, 1.0))
    confidence = float(np.clip(confidence, 0.2, 0.98))
    final_temporal_score = float(np.clip(final_temporal_score, 0.0, 1.0))

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

    limitations.append("Video AI detection is probabilistic; video compression & encoding may degrade forensic quality.")
    limitations.append("High-quality generative video models continue to evolve rapidly.")

    technical_signals = {
        "frames_sampled": frames_count,
        "total_video_frames": video_meta.get("total_frames", 0),
        "fps": video_meta.get("fps", 0),
        "duration_seconds": video_meta.get("duration_seconds", 0),
        "width": video_meta.get("width", 0),
        "height": video_meta.get("height", 0),
        "temporal_consistency": round(final_temporal_score, 4),
        "gemini_available": gemini_available,
        "mean_frame_delta": temporal_forensics.get("mean_delta", 0.0),
    }

    return {
        "media_type": "video",
        "type": "video",
        "classification": classification,
        "prediction": classification,
        "ai_probability": round(ai_prob, 4),
        "deepfake_probability": round(ai_prob, 4),
        "confidence": round(confidence, 4),
        "frames_analyzed": frames_count,
        "temporal_consistency_score": round(final_temporal_score, 4),
        "reasons": reasons,
        "visual_signals": visual_signals,
        "temporal_signals": temporal_signals,
        "technical_signals": technical_signals,
        "model_available": True,
        "gemini_available": gemini_available,
        "limitations": list(dict.fromkeys(limitations)),
    }


def _error_result(msg: str) -> Dict[str, Any]:
    return {
        "media_type": "video",
        "type": "video",
        "classification": "uncertain",
        "prediction": "uncertain",
        "ai_probability": 0.5,
        "deepfake_probability": 0.5,
        "confidence": 0.0,
        "frames_analyzed": 0,
        "temporal_consistency_score": 0.5,
        "reasons": [msg],
        "visual_signals": [],
        "temporal_signals": [],
        "technical_signals": {},
        "model_available": False,
        "gemini_available": False,
        "limitations": [msg],
    }
