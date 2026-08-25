"""
services/gemini_analyzer.py
Google Gemini Multimodal AI Integration for TrustAI.

Provides:
  • GeminiImageAnalyzer — Multimodal visual analysis for AI-generated / manipulated images
  • GeminiVideoAnalyzer — Multi-frame temporal & visual analysis for AI-generated / deepfake videos
  • GeminiUrlAnalyzer   — Semantic URL analysis for phishing, spoofing, and brand impersonation

Design Principles:
  1. No external proprietary SDK locks — uses robust HTTPS REST requests with response_mime_type="application/json".
  2. Resilient fallback — if GEMINI_API_KEY is not set or API fails, returns status indicating unavailable without crashing.
  3. Strict schema validation — ensures all probabilities are floats [0.0, 1.0] and predictions are normalized.
  4. False positive protection — prompts specifically instruct Gemini not to flag normal camera compression, lighting, or noise as AI generation.
"""

import base64
import json
import logging
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from PIL import Image

logger = logging.getLogger("trustai.gemini")

# Default Gemini model and API endpoint
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def get_gemini_api_key() -> str:
    """Retrieve GEMINI_API_KEY from environment."""
    return os.getenv("GEMINI_API_KEY", "").strip()


def is_gemini_configured() -> bool:
    """Check if a non-empty Gemini API key is configured."""
    key = get_gemini_api_key()
    return bool(key) and key != "your-gemini-api-key-here"


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON object from a model response string."""
    if not text:
        return None

    # First try direct parse
    try:
        return json.loads(text.strip())
    except Exception:
        pass

    # Try matching json markdown block
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Try finding outermost { ... }
    match_braces = re.search(r"(\{[\s\S]*\})", text)
    if match_braces:
        try:
            return json.loads(match_braces.group(1))
        except Exception:
            pass

    return None


def _call_gemini_api(payload: Dict[str, Any], timeout: int = 30) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Execute POST request to Gemini generateContent REST API.
    Returns: (success, parsed_json_dict, error_message)
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return False, None, "GEMINI_API_KEY environment variable is not configured."

    url = GEMINI_API_URL.format(model=DEFAULT_MODEL) + f"?key={api_key}"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if response.status_code != 200:
            err_msg = f"Gemini API returned status {response.status_code}: {response.text[:300]}"
            logger.warning(err_msg)
            return False, None, err_msg

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return False, None, "Gemini returned no response candidates."

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return False, None, "Gemini returned empty content parts."

        text_content = parts[0].get("text", "")
        parsed = _extract_json_from_text(text_content)
        if not parsed:
            logger.warning("Failed to parse JSON from Gemini text: %s", text_content[:200])
            return False, None, "Could not parse structured JSON from Gemini response."

        return True, parsed, None

    except requests.exceptions.Timeout:
        logger.warning("Gemini API call timed out after %ds", timeout)
        return False, None, f"Gemini API request timed out ({timeout}s)."
    except Exception as exc:
        logger.exception("Gemini API request failed: %s", exc)
        return False, None, f"Gemini API request failed: {str(exc)}"


def _pil_to_base64(img: Image.Image, max_dim: int = 1024, quality: int = 85) -> Tuple[str, str]:
    """Convert PIL image to base64 JPEG string and mime-type, resizing if too large."""
    img_copy = img.copy()
    if max_dim and (img_copy.width > max_dim or img_copy.height > max_dim):
        img_copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    if img_copy.mode != "RGB":
        img_copy = img_copy.convert("RGB")

    buffer = BytesIO()
    img_copy.save(buffer, format="JPEG", quality=quality)
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return b64_str, "image/jpeg"


# ==============================================================================
# 1. GeminiImageAnalyzer
# ==============================================================================

class GeminiImageAnalyzer:
    """
    Multimodal Image Analyzer using Google Gemini Vision.
    Performs comprehensive visual inspection of image authenticity.
    """

    IMAGE_ANALYSIS_PROMPT = """You are a senior digital forensics expert specializing in detecting AI-generated images (e.g. Midjourney, DALL-E, Stable Diffusion, Flux, Imagen, FaceApp, Photoshop generative fill).

Analyze the provided image for authenticity vs AI generation.

Perform a thorough visual examination of:
1. Faces & Anatomy: Eyes (pupil symmetry, reflections, iris roundness), teeth alignment, hands & fingers (count, joints, malformations), ears, limb proportions.
2. Skin & Hair: Unnatural smoothness, synthetic porcelain skin, weird hair blending or melting into shoulders/background.
3. Physics & Lighting: Shadows consistency with light sources, reflections in eyes and mirrors, perspective distortion, unnatural ambient lighting.
4. Textures & Background: Unnatural background blur, melting objects, repetitive wallpaper/tiling patterns, garbled or non-existent background text.
5. Photographic vs Synthetic Artifacts: Distinguish normal camera artifacts (JPEG compression, sensor noise, low-light grain, lens blur, motion blur) from AI generation artifacts.

CRITICAL INSTRUCTIONS FOR FALSE POSITIVE PROTECTION:
- Real smartphone photos, selfies, DSLR portraits, low-light photos, social media re-compressed photos, and resized photos MUST NOT be classified as AI-generated simply due to compression noise or lack of sharpness.
- Do NOT treat standard photographic compression or portrait mode blur as AI generation.
- If the image looks natural without synthetic generation hallmarks, classify it as "likely_authentic".
- If evidence is mixed, subtle, or inconclusive, classify as "uncertain".
- If strong synthetic generation artifacts are clearly present, classify as "likely_ai_generated".

Return ONLY a valid JSON object matching this schema exactly:
{
  "media_type": "image",
  "classification": "likely_ai_generated" | "likely_authentic" | "uncertain",
  "ai_probability": <float between 0.0 and 1.0>,
  "confidence": <float between 0.0 and 1.0>,
  "reasons": [
    "<Concise natural language bullet point explaining what was observed>"
  ],
  "visual_signals": [
    {
      "feature": "<e.g. eyes | hands | lighting | skin | background | physics | text>",
      "observation": "<Specific visual observation>",
      "assessment": "natural" | "synthetic" | "inconclusive"
    }
  ],
  "limitations": [
    "<Any limitations affecting this image analysis, e.g. resolution, heavy compression>"
  ]
}
"""

    @classmethod
    def analyze(cls, pil_image: Image.Image) -> Dict[str, Any]:
        """
        Send image to Gemini for multimodal analysis.
        Returns normalized dictionary with classification, probabilities, and observations.
        """
        if not is_gemini_configured():
            return {
                "available": False,
                "classification": "uncertain",
                "ai_probability": 0.5,
                "confidence": 0.0,
                "reasons": ["Gemini API key is not configured in backend environment."],
                "visual_signals": [],
                "limitations": ["Gemini multimodal vision analysis was unavailable (API key missing)."],
            }

        try:
            b64_data, mime_type = _pil_to_base64(pil_image)
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": cls.IMAGE_ANALYSIS_PROMPT},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": b64_data,
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                    "max_output_tokens": 1500,
                }
            }

            success, data, err = _call_gemini_api(payload, timeout=35)
            if not success or not data:
                return {
                    "available": False,
                    "classification": "uncertain",
                    "ai_probability": 0.5,
                    "confidence": 0.0,
                    "reasons": [f"Gemini analysis unavailable: {err or 'Unknown error'}"],
                    "visual_signals": [],
                    "limitations": [f"Gemini multimodal vision failed ({err}). Analysis fell back to local forensics."],
                }

            # Normalize and validate returned fields
            ai_prob = float(data.get("ai_probability", 0.5))
            ai_prob = max(0.0, min(1.0, ai_prob))

            confidence = float(data.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))

            classification = str(data.get("classification", "uncertain")).lower()
            if classification not in ("likely_ai_generated", "likely_authentic", "uncertain"):
                if ai_prob >= 0.70:
                    classification = "likely_ai_generated"
                elif ai_prob <= 0.30:
                    classification = "likely_authentic"
                else:
                    classification = "uncertain"

            reasons = [str(r) for r in data.get("reasons", []) if r]
            visual_signals = data.get("visual_signals", [])
            limitations = [str(l) for l in data.get("limitations", []) if l]

            return {
                "available": True,
                "classification": classification,
                "ai_probability": round(ai_prob, 4),
                "confidence": round(confidence, 4),
                "reasons": reasons,
                "visual_signals": visual_signals,
                "limitations": limitations,
            }

        except Exception as exc:
            logger.exception("[GeminiImageAnalyzer] Exception: %s", exc)
            return {
                "available": False,
                "classification": "uncertain",
                "ai_probability": 0.5,
                "confidence": 0.0,
                "reasons": [f"Error during Gemini analysis: {str(exc)}"],
                "visual_signals": [],
                "limitations": ["Gemini multimodal analysis encountered an unexpected error."],
            }


# ==============================================================================
# 2. GeminiVideoAnalyzer
# ==============================================================================

class GeminiVideoAnalyzer:
    """
    Multimodal Video Analyzer using Google Gemini Vision.
    Processes representative frame sequences sampled across video duration
    to analyze frame-level details and temporal consistency.
    """

    VIDEO_ANALYSIS_PROMPT = """You are a digital forensics expert analyzing representative sequential frames extracted from a video to detect AI video generation (e.g. Sora, Runway Gen-2/Gen-3, Pika, Kling, Luma Dream Machine, Stable Video) or Face Deepfakes (e.g. Roop, DeepFaceLab, FaceSwap).

The attached images are sequential keyframes sampled across the video duration (from start, quarter, middle, three-quarters, to end).

Analyze both FRAME-LEVEL and TEMPORAL consistency:

1. Frame-Level Signals:
   - Facial features (eyes, pupils, teeth, skin texture, ear shape)
   - Anatomy & limbs (finger counts, joint bending, body proportions)
   - Physical plausibility of objects and textures
   - Rendering artifacts and synthetic glossiness

2. Temporal & Cross-Frame Consistency:
   - Identity consistency: Does the person's face geometry or identity morph between frames?
   - Flickering & warping: Do backgrounds, hair strands, glasses, or facial edges warp or flicker?
   - Lighting & shadow coherence across time
   - Background stability: Do background objects deform or change structure?
   - Unnatural motion artifacts or melting boundaries

CRITICAL INSTRUCTIONS FOR FALSE POSITIVE PROTECTION:
- Real human videos recorded on smartphones, compressed with h.264/h.265, exhibiting motion blur, camera shake, or low light noise are NATURAL and must NOT be flagged as deepfakes or AI generation.
- Video compression blocking / macroblocking is NOT proof of AI generation.
- If identity and physics remain stable across frames, classify as "likely_authentic".
- If borderline or ambiguous, classify as "uncertain".
- Only classify as "likely_ai_generated" if there is clear evidence of synthetic rendering or temporal morphing.

Return ONLY a valid JSON object matching this schema exactly:
{
  "media_type": "video",
  "classification": "likely_ai_generated" | "likely_authentic" | "uncertain",
  "ai_probability": <float between 0.0 and 1.0>,
  "confidence": <float between 0.0 and 1.0>,
  "temporal_consistency_score": <float between 0.0 (erratic/warping) and 1.0 (highly consistent)>,
  "reasons": [
    "<Concise natural language bullet point explaining temporal or visual findings>"
  ],
  "visual_signals": [
    {
      "feature": "<e.g. facial_identity | hands | lighting | background>",
      "observation": "<Observation>",
      "assessment": "natural" | "synthetic" | "inconclusive"
    }
  ],
  "temporal_signals": [
    {
      "signal": "<e.g. identity_stability | boundary_warping | texture_flicker | lighting_coherence>",
      "observation": "<Observation across frames>",
      "is_suspicious": <boolean>
    }
  ],
  "limitations": [
    "<Any limitations affecting this video analysis, e.g. low frame count, compression>"
  ]
}
"""

    @classmethod
    def analyze(cls, sampled_frames: List[Image.Image]) -> Dict[str, Any]:
        """
        Send sampled video frames to Gemini for multimodal analysis.
        """
        if not is_gemini_configured():
            return {
                "available": False,
                "classification": "uncertain",
                "ai_probability": 0.5,
                "confidence": 0.0,
                "temporal_consistency_score": 0.5,
                "frames_analyzed": len(sampled_frames),
                "reasons": ["Gemini API key is not configured in backend environment."],
                "visual_signals": [],
                "temporal_signals": [],
                "limitations": ["Gemini multimodal video analysis was unavailable (API key missing)."],
            }

        if not sampled_frames:
            return {
                "available": False,
                "classification": "uncertain",
                "ai_probability": 0.5,
                "confidence": 0.0,
                "temporal_consistency_score": 0.5,
                "frames_analyzed": 0,
                "reasons": ["No frames could be extracted from the video."],
                "visual_signals": [],
                "temporal_signals": [],
                "limitations": ["Video decoding produced 0 frames."],
            }

        try:
            # Prepare parts: prompt + each frame
            parts: List[Dict[str, Any]] = [{"text": cls.VIDEO_ANALYSIS_PROMPT}]

            # Cap frames to at most 8 to stay well within token limits and latency targets
            frames_to_send = sampled_frames[:8]
            for i, frame in enumerate(frames_to_send):
                b64_data, mime_type = _pil_to_base64(frame, max_dim=800, quality=80)
                parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": b64_data,
                    }
                })

            payload = {
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                    "max_output_tokens": 2000,
                }
            }

            success, data, err = _call_gemini_api(payload, timeout=50)
            if not success or not data:
                return {
                    "available": False,
                    "classification": "uncertain",
                    "ai_probability": 0.5,
                    "confidence": 0.0,
                    "temporal_consistency_score": 0.5,
                    "frames_analyzed": len(sampled_frames),
                    "reasons": [f"Gemini video analysis unavailable: {err or 'Unknown error'}"],
                    "visual_signals": [],
                    "temporal_signals": [],
                    "limitations": [f"Gemini video analysis failed ({err}). Analysis fell back to local heuristics."],
                }

            ai_prob = float(data.get("ai_probability", 0.5))
            ai_prob = max(0.0, min(1.0, ai_prob))

            confidence = float(data.get("confidence", 0.7))
            confidence = max(0.0, min(1.0, confidence))

            temporal_score = float(data.get("temporal_consistency_score", 0.7))
            temporal_score = max(0.0, min(1.0, temporal_score))

            classification = str(data.get("classification", "uncertain")).lower()
            if classification not in ("likely_ai_generated", "likely_authentic", "uncertain"):
                if ai_prob >= 0.70:
                    classification = "likely_ai_generated"
                elif ai_prob <= 0.30:
                    classification = "likely_authentic"
                else:
                    classification = "uncertain"

            reasons = [str(r) for r in data.get("reasons", []) if r]
            visual_signals = data.get("visual_signals", [])
            temporal_signals = data.get("temporal_signals", [])
            limitations = [str(l) for l in data.get("limitations", []) if l]

            return {
                "available": True,
                "classification": classification,
                "ai_probability": round(ai_prob, 4),
                "confidence": round(confidence, 4),
                "temporal_consistency_score": round(temporal_score, 4),
                "frames_analyzed": len(sampled_frames),
                "reasons": reasons,
                "visual_signals": visual_signals,
                "temporal_signals": temporal_signals,
                "limitations": limitations,
            }

        except Exception as exc:
            logger.exception("[GeminiVideoAnalyzer] Exception: %s", exc)
            return {
                "available": False,
                "classification": "uncertain",
                "ai_probability": 0.5,
                "confidence": 0.0,
                "temporal_consistency_score": 0.5,
                "frames_analyzed": len(sampled_frames),
                "reasons": [f"Error during Gemini video analysis: {str(exc)}"],
                "visual_signals": [],
                "temporal_signals": [],
                "limitations": ["Gemini video analysis encountered an unexpected error."],
            }


# ==============================================================================
# 3. GeminiUrlAnalyzer
# ==============================================================================

class GeminiUrlAnalyzer:
    """
    Semantic URL and Phishing Analyzer using Google Gemini AI.
    Analyzes domain structure, brand impersonation, typosquatting, and deceptive paths.
    """

    URL_ANALYSIS_PROMPT = """You are a cybersecurity expert specializing in phishing detection and malicious URL analysis.

Analyze the following URL for phishing, credential harvesting, brand impersonation, typosquatting, and deception:
URL: "{url}"

Analyze:
1. Domain & Brand Impersonation: Is the domain spoofing a recognized brand (e.g. PayPal, Google, Microsoft, Apple, Amazon, Banking) using typosquatting, subdomains, or prefix/suffix attacks (e.g. paypal-login.com, login.microsoft.security-verify.net)?
2. Top-Level Domain (TLD): Is the TLD high-risk, unusual, or deceptive?
3. Path & Query Parameters: Are there suspicious authentication/login paths on an untrusted domain (e.g. /wp-includes/login.php, /auth/signin.html)?
4. Obfuscation & Deception: Are there hex/URL encoding tricks, IP address hosts, @ signs, or excessive subdomains?
5. Legitimate Sites: If this is a verified authentic domain of a legitimate organization (e.g., google.com, github.com, wikipedia.org, amazon.com), classify it as "safe".

Return ONLY a valid JSON object matching this schema exactly:
{
  "media_type": "url",
  "classification": "phishing" | "safe" | "suspicious" | "uncertain",
  "phishing_probability": <float between 0.0 and 1.0>,
  "confidence": <float between 0.0 and 1.0>,
  "reasons": [
    "<Concise bullet point explaining domain, brand, or path analysis>"
  ],
  "risk_indicators": [
    {
      "indicator": "<e.g. brand_spoofing | typosquatting | suspicious_path | clean_domain>",
      "severity": "high" | "medium" | "low" | "none",
      "detail": "<Explanation>"
    }
  ],
  "limitations": [
    "<Any limitations, e.g. domain without live page inspection>"
  ]
}
"""

    @classmethod
    def analyze(cls, url: str) -> Dict[str, Any]:
        """
        Analyze a URL using Gemini AI.
        """
        if not is_gemini_configured():
            return {
                "available": False,
                "classification": "uncertain",
                "phishing_probability": 0.5,
                "confidence": 0.0,
                "reasons": ["Gemini API key is not configured in backend environment."],
                "risk_indicators": [],
                "limitations": ["Gemini semantic URL analysis was unavailable (API key missing)."],
            }

        try:
            prompt = cls.URL_ANALYSIS_PROMPT.format(url=url)
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                    "max_output_tokens": 1200,
                }
            }

            success, data, err = _call_gemini_api(payload, timeout=25)
            if not success or not data:
                return {
                    "available": False,
                    "classification": "uncertain",
                    "phishing_probability": 0.5,
                    "confidence": 0.0,
                    "reasons": [f"Gemini URL analysis unavailable: {err or 'Unknown error'}"],
                    "risk_indicators": [],
                    "limitations": [f"Gemini URL analysis failed ({err}). Analysis fell back to local ML model."],
                }

            prob = float(data.get("phishing_probability", 0.5))
            prob = max(0.0, min(1.0, prob))

            confidence = float(data.get("confidence", 0.75))
            confidence = max(0.0, min(1.0, confidence))

            classification = str(data.get("classification", "uncertain")).lower()
            if classification not in ("phishing", "safe", "suspicious", "uncertain"):
                if prob >= 0.70:
                    classification = "phishing"
                elif prob <= 0.30:
                    classification = "safe"
                else:
                    classification = "suspicious"

            reasons = [str(r) for r in data.get("reasons", []) if r]
            indicators = data.get("risk_indicators", [])
            limitations = [str(l) for l in data.get("limitations", []) if l]

            return {
                "available": True,
                "classification": classification,
                "phishing_probability": round(prob, 4),
                "confidence": round(confidence, 4),
                "reasons": reasons,
                "risk_indicators": indicators,
                "limitations": limitations,
            }

        except Exception as exc:
            logger.exception("[GeminiUrlAnalyzer] Exception: %s", exc)
            return {
                "available": False,
                "classification": "uncertain",
                "phishing_probability": 0.5,
                "confidence": 0.0,
                "reasons": [f"Error during Gemini URL analysis: {str(exc)}"],
                "risk_indicators": [],
                "limitations": ["Gemini URL analysis encountered an unexpected error."],
            }
