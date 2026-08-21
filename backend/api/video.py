"""
api/video.py
POST /api/analyze/video — Video deepfake analysis endpoint.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from database.database import get_db
from database import models as db_models
from services import video_service, scoring_service
from explanation.explanation_engine import generate_video_evidence
from utils.validation import validate_video_upload, check_file_size, video_max_bytes
from utils.preprocessing import save_temp_file, cleanup_temp_file, sha256_bytes

router = APIRouter()


@router.post("/analyze/video")
async def analyze_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # ── 1. Validate ───────────────────────────────────────────────────────────
    validate_video_upload(file)

    # ── 2. Read & size-check ──────────────────────────────────────────────────
    data = await check_file_size(file, video_max_bytes(), "Video")

    analysis_id = str(uuid.uuid4())
    input_hash = sha256_bytes(data)

    # ── 3. Save temp file ─────────────────────────────────────────────────────
    import os
    ext = os.path.splitext(file.filename or ".mp4")[1].lower() or ".mp4"
    temp_path = save_temp_file(data, ext)

    try:
        # ── 4. Run video service ──────────────────────────────────────────────
        video_result = video_service.analyze_video(temp_path)

        # ── 5. Trust Score ────────────────────────────────────────────────────
        scoring = scoring_service.compute_video_trust_score(video_result)

        # ── 6. Evidence + Explanation ─────────────────────────────────────────
        explanation_data = generate_video_evidence(video_result, scoring["trust_score"])

        # ── 7. Persist ────────────────────────────────────────────────────────
        try:
            record = db_models.Analysis(
                id=analysis_id,
                type="video",
                input_hash=input_hash,
                trust_score=scoring["trust_score"],
                risk_level=scoring["risk_level"],
                confidence=scoring["confidence"],
                prediction=video_result.get("prediction"),
            )
            db.add(record)
            if video_result.get("deepfake_probability") is not None:
                db.add(db_models.ModelResult(
                    analysis_id=analysis_id,
                    model_name="deepfake_efficientnet_b0",
                    prediction=video_result.get("prediction"),
                    probability=video_result.get("deepfake_probability"),
                ))
            for ev in explanation_data["evidence"][:10]:
                db.add(db_models.Evidence(
                    analysis_id=analysis_id,
                    source=ev["source"],
                    description=ev["description"],
                    severity=ev["severity"],
                    supporting_value=ev.get("supporting_value"),
                ))
            db.commit()
        except Exception:
            db.rollback()

        return {
            "analysis_id": analysis_id,
            "type": "video",
            "filename": file.filename,
            "trust_score": scoring["trust_score"],
            "risk_level": scoring["risk_level"],
            "prediction": video_result.get("prediction"),
            "deepfake_probability": video_result.get("deepfake_probability"),
            "frames_analyzed": video_result.get("frames_analyzed", 0),
            "suspicious_frames": video_result.get("suspicious_frames", 0),
            "suspicious_frame_ratio": video_result.get("suspicious_frame_ratio"),
            "confidence": scoring["confidence"],
            "model_available": video_result.get("model_available", False),
            "technical_signals": video_result.get("technical_signals", {}),
            "evidence": explanation_data["evidence"],
            "explanation": explanation_data["explanation"],
            "limitations": explanation_data["limitations"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        cleanup_temp_file(temp_path)
