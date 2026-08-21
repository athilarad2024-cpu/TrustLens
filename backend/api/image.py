"""
api/image.py
POST /api/analyze/image — Image AI-detection endpoint.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from database.database import get_db
from database import models as db_models
from services import image_service, scoring_service
from explanation.explanation_engine import generate_image_evidence
from utils.validation import validate_image_upload, check_file_size, image_max_bytes
from utils.preprocessing import save_temp_file, cleanup_temp_file, sha256_bytes

router = APIRouter()


@router.post("/analyze/image")
async def analyze_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # ── 1. Validate type ──────────────────────────────────────────────────────
    validate_image_upload(file)

    # ── 2. Read & size-check ──────────────────────────────────────────────────
    data = await check_file_size(file, image_max_bytes(), "Image")

    analysis_id = str(uuid.uuid4())
    input_hash = sha256_bytes(data)

    # ── 3. Save temp file ─────────────────────────────────────────────────────
    import os
    ext = os.path.splitext(file.filename or ".jpg")[1].lower() or ".jpg"
    temp_path = save_temp_file(data, ext)

    try:
        # ── 4. Run image service ──────────────────────────────────────────────
        image_result = image_service.analyze_image(temp_path)

        # ── 5. Trust Score ────────────────────────────────────────────────────
        scoring = scoring_service.compute_image_trust_score(image_result)

        # ── 6. Evidence + Explanation ─────────────────────────────────────────
        explanation_data = generate_image_evidence(image_result, scoring["trust_score"])

        # ── 7. Persist ────────────────────────────────────────────────────────
        try:
            record = db_models.Analysis(
                id=analysis_id,
                type="image",
                input_hash=input_hash,
                trust_score=scoring["trust_score"],
                risk_level=scoring["risk_level"],
                confidence=scoring["confidence"],
                prediction=image_result.get("prediction"),
            )
            db.add(record)
            if image_result.get("ai_generated_probability") is not None:
                db.add(db_models.ModelResult(
                    analysis_id=analysis_id,
                    model_name="image_efficientnet_b0",
                    prediction=image_result.get("prediction"),
                    probability=image_result.get("ai_generated_probability"),
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
            "type": "image",
            "filename": file.filename,
            "trust_score": scoring["trust_score"],
            "risk_level": scoring["risk_level"],
            "prediction": image_result.get("prediction"),
            "ai_generated_probability": image_result.get("ai_generated_probability"),
            "manipulation_probability": image_result.get("manipulation_probability"),
            "confidence": scoring["confidence"],
            "model_available": image_result.get("model_available", False),
            "technical_signals": image_result.get("technical_signals", {}),
            "evidence": explanation_data["evidence"],
            "explanation": explanation_data["explanation"],
            "limitations": explanation_data["limitations"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        cleanup_temp_file(temp_path)
