"""
api/url.py
POST /api/analyze/url  — Full URL phishing analysis (ML + security intel + scoring).
GET  /api/preview/url  — Fast structural preview (no ML, no network calls).
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import get_db
from database import models as db_models
from services import url_service, security_service, scoring_service
from explanation.explanation_engine import generate_url_evidence
from utils.validation import validate_url

router = APIRouter()


class URLRequest(BaseModel):
    url: str


@router.post("/analyze/url")
async def analyze_url(request: URLRequest, db: Session = Depends(get_db)):
    # ── 1. Validate ───────────────────────────────────────────────────────────
    url = validate_url(request.url)

    analysis_id = str(uuid.uuid4())

    # ── 2. URL phishing model ─────────────────────────────────────────────────
    url_result = await url_service.analyze_url(url)

    # ── 3. External security intelligence ─────────────────────────────────────
    security_result = security_service.check_url(url)

    # ── 4. Trust Score ────────────────────────────────────────────────────────
    scoring = scoring_service.compute_url_trust_score(url_result, security_result)

    # ── 5. Evidence + Explanation ────────────────────────────────────────────────────
    explanation_data = generate_url_evidence(
        url, url_result, security_result, scoring["trust_score"],
        verified_safe=scoring.get("verified_safe", False),
        ext_status=scoring.get("ext_status", "unavailable"),
    )

    # ── 6. Persist to DB ──────────────────────────────────────────────────────
    try:
        import hashlib
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        record = db_models.Analysis(
            id=analysis_id,
            type="url",
            input_hash=url_hash,
            url=url,
            trust_score=scoring["trust_score"],
            risk_level=scoring["risk_level"],
            confidence=scoring["confidence"],
            prediction=url_result.get("prediction"),
        )
        db.add(record)
        # Store model result
        if url_result.get("phishing_probability") is not None:
            db.add(db_models.ModelResult(
                analysis_id=analysis_id,
                model_name="url_phishing_model",
                prediction=url_result.get("prediction"),
                probability=url_result.get("phishing_probability"),
            ))
        # Store top evidence
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
        db.rollback()  # DB failure must not crash the response

    # ── 7. Build response ─────────────────────────────────────────────────────
    return {
        "analysis_id": analysis_id,
        "type": "url",
        "url": url,
        "trust_score": scoring["trust_score"],
        "risk_level": scoring["risk_level"],
        "prediction": url_result.get("prediction"),
        "phishing_probability": url_result.get("phishing_probability"),
        "security_status": _security_status(security_result),
        "confidence": scoring["confidence"],
        "model_available": url_result.get("model_available", False),
        # Verified-safe signals — the frontend should use these rather than
        # hardcoding domain names to decide what badge/label to show.
        "verified_safe": scoring.get("verified_safe", False),
        "trusted_domain_applied": scoring.get("trusted_domain_applied", False),
        "ext_status": scoring.get("ext_status", "unavailable"),
        "external_intelligence": {
            "google_safe_browsing": security_result.get("google_safe_browsing", {}),
            "virustotal": security_result.get("virustotal", {}),
            "any_threat_found": security_result.get("any_threat_found", False),
        },
        "feature_values": url_result.get("feature_values", {}),
        "gemini_available": url_result.get("gemini_available", False),
        "gemini_reasons": url_result.get("gemini_reasons", []),
        "gemini_indicators": url_result.get("gemini_indicators", []),
        "evidence": explanation_data["evidence"],
        "explanation": explanation_data["explanation"],
        "limitations": explanation_data["limitations"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _security_status(security_result: dict) -> str:
    if security_result.get("any_threat_found"):
        return "malicious"
    gsb_ok = security_result.get("google_safe_browsing", {}).get("status") == "ok"
    vt_ok = security_result.get("virustotal", {}).get("status") == "ok"
    if gsb_ok or vt_ok:
        return "clean"
    return "unchecked"


@router.get("/preview/url")
async def preview_url(url: str = Query(..., description="URL to preview")):
    """
    Instant structural preview of a URL.

    No ML inference and no network calls (except a Google favicon lookup).
    Returns structural risk flags, domain info, and an instant risk score
    in milliseconds — useful for showing a preview card in the UI before
    committing to a full analysis.
    """
    try:
        validated = validate_url(url)
    except HTTPException as exc:
        raise exc

    return url_service.get_url_preview(validated)
