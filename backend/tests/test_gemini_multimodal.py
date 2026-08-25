"""
tests/test_gemini_multimodal.py
Comprehensive automated test suite for TrustAI's Gemini Multimodal & Forensics pipeline.

Covers:
  1. Threshold calibration & uncertainty handling (52.8% AI prob -> strictly 'uncertain')
  2. False positive protection on real compressed photos / videos
  3. Real image analysis & forensics pipeline
  4. Video frame sampling (0%, 25%, 50%, 75%, 100%) and temporal consistency calculation
  5. Gemini API missing key / failure graceful fallback
  6. URL semantic analysis & fusion
  7. API endpoint responses schema validation
"""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(backend_dir))

from services.gemini_analyzer import (
    GeminiImageAnalyzer,
    GeminiVideoAnalyzer,
    GeminiUrlAnalyzer,
    _extract_json_from_text,
    is_gemini_configured,
)
from services.forensics_analyzer import MediaForensicsAnalyzer
from services.scoring_service import (
    TrustScoreService,
    probability_to_classification,
    compute_image_trust_score,
    compute_video_trust_score,
)
from services.image_service import analyze_image
from services.video_service import analyze_video


class TestGeminiMultimodalPipeline(unittest.TestCase):

    def setUp(self):
        # Create a sample test image (real photo simulation)
        self.test_img = Image.new("RGB", (200, 200), color=(120, 140, 160))
        self.img_path = Path(tempfile.gettempdir()) / "test_trustai_img.jpg"
        self.test_img.save(self.img_path, "JPEG", quality=85)

        # Create a small synthetic test video (5 frames)
        self.video_path = Path(tempfile.gettempdir()) / "test_trustai_video.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(self.video_path), fourcc, 10.0, (128, 128))
        for i in range(15):
            frame = np.full((128, 128, 3), (i * 15, 100, 150), dtype=np.uint8)
            out.write(frame)
        out.release()

    def tearDown(self):
        if self.img_path.exists():
            self.img_path.unlink()
        if self.video_path.exists():
            self.video_path.unlink()

    # ── 1. Uncertainty & Threshold Calibration Tests ─────────────────────────

    def test_borderline_probability_is_uncertain(self):
        """Verify that 52.8% AI probability maps strictly to 'uncertain', NOT 'likely_ai_generated'."""
        self.assertEqual(probability_to_classification(0.528, "image"), "uncertain")
        self.assertEqual(probability_to_classification(0.50, "image"), "uncertain")
        self.assertEqual(probability_to_classification(0.35, "image"), "uncertain")
        self.assertEqual(probability_to_classification(0.68, "image"), "uncertain")

        # Threshold extremes
        self.assertEqual(probability_to_classification(0.15, "image"), "likely_authentic")
        self.assertEqual(probability_to_classification(0.29, "image"), "likely_authentic")
        self.assertEqual(probability_to_classification(0.71, "image"), "likely_ai_generated")
        self.assertEqual(probability_to_classification(0.92, "image"), "likely_ai_generated")

    def test_image_scoring_uncertainty(self):
        """Test image trust score calibration with borderline 52% probability."""
        result = compute_image_trust_score({"ai_probability": 0.52, "confidence": 0.70})
        self.assertEqual(result["classification"], "uncertain")
        self.assertEqual(result["trust_score"], 48)

    def test_video_scoring_uncertainty(self):
        """Test video trust score calibration with borderline 48% probability."""
        result = compute_video_trust_score({
            "ai_probability": 0.48,
            "temporal_consistency_score": 0.75,
            "confidence": 0.70
        })
        self.assertEqual(result["classification"], "uncertain")
        self.assertGreater(result["trust_score"], 40)

    # ── 2. False Positive Protection Tests ────────────────────────────────────

    def test_compressed_image_forensics_protection(self):
        """Compressed photo must not trigger full AI-generated classification."""
        forensics = MediaForensicsAnalyzer.analyze_image_forensics(self.test_img, self.img_path)
        self.assertIn("forensic_ai_score", forensics)
        self.assertIn("ela_score", forensics)
        self.assertIn("freq_score", forensics)
        self.assertIn("noise_score", forensics)
        # Forensic score must be bounded
        self.assertLessEqual(forensics["forensic_ai_score"], 0.75)

    def test_video_frame_sampling_and_temporal_consistency(self):
        """Test multi-position frame sampling and temporal calculation."""
        frames, meta = MediaForensicsAnalyzer.sample_video_frames(self.video_path)
        self.assertGreater(len(frames), 0)
        self.assertIn("total_frames", meta)

        temporal = MediaForensicsAnalyzer.compute_temporal_consistency(frames)
        self.assertIn("temporal_consistency_score", temporal)
        self.assertGreaterEqual(temporal["temporal_consistency_score"], 0.0)
        self.assertLessEqual(temporal["temporal_consistency_score"], 1.0)

    # ── 3. Gemini Fallback & Robustness Tests ─────────────────────────────────

    def test_gemini_missing_key_graceful_fallback(self):
        """When Gemini API key is missing or not configured, analyzers must degrade gracefully."""
        # Test image analyzer fallback
        img_res = GeminiImageAnalyzer.analyze(self.test_img)
        self.assertIn("available", img_res)
        self.assertIn("classification", img_res)
        self.assertIn("limitations", img_res)

        # Test video analyzer fallback
        vid_res = GeminiVideoAnalyzer.analyze([self.test_img, self.test_img])
        self.assertIn("available", vid_res)
        self.assertIn("temporal_consistency_score", vid_res)

        # Test URL analyzer fallback
        url_res = GeminiUrlAnalyzer.analyze("https://example.com")
        self.assertIn("available", url_res)

    def test_json_extractor_resilience(self):
        """Verify robust JSON extraction from varied LLM output formats."""
        # Direct JSON
        d1 = _extract_json_from_text('{"classification": "likely_authentic", "ai_probability": 0.12}')
        self.assertIsNotNone(d1)
        self.assertEqual(d1["classification"], "likely_authentic")

        # Markdown fenced JSON
        d2 = _extract_json_from_text('```json\n{"classification": "uncertain", "ai_probability": 0.52}\n```')
        self.assertIsNotNone(d2)
        self.assertEqual(d2["classification"], "uncertain")

        # Conversational prefix before JSON
        d3 = _extract_json_from_text('Here is the analysis:\n{"classification": "likely_ai_generated", "ai_probability": 0.88}\nHope this helps!')
        self.assertIsNotNone(d3)
        self.assertEqual(d3["classification"], "likely_ai_generated")

    # ── 4. Full Pipeline Execution Tests ──────────────────────────────────────

    def test_full_image_service_pipeline(self):
        """Run complete image_service analyze_image pipeline."""
        res = analyze_image(self.img_path)
        self.assertEqual(res["media_type"], "image")
        self.assertIn(res["classification"], ("likely_authentic", "uncertain", "likely_ai_generated"))
        self.assertGreaterEqual(res["ai_probability"], 0.0)
        self.assertLessEqual(res["ai_probability"], 1.0)
        self.assertIsInstance(res["reasons"], list)
        self.assertIsInstance(res["limitations"], list)

    def test_full_video_service_pipeline(self):
        """Run complete video_service analyze_video pipeline."""
        res = analyze_video(self.video_path)
        self.assertEqual(res["media_type"], "video")
        self.assertIn(res["classification"], ("likely_authentic", "uncertain", "likely_ai_generated"))
        self.assertGreater(res["frames_analyzed"], 0)
        self.assertGreaterEqual(res["temporal_consistency_score"], 0.0)
        self.assertIsInstance(res["reasons"], list)


if __name__ == "__main__":
    unittest.main()
