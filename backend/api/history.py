"""
api/history.py
GET /api/analysis/{id}   — retrieve single analysis
GET /api/history         — retrieve analysis history (paginated)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.database import get_db
from database import models as db_models

router = APIRouter()


@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    record = db.query(db_models.Analysis).filter(db_models.Analysis.id == analysis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail={"error": "Not found", "message": f"No analysis with id '{analysis_id}'."})
    return _serialize(record, db)


@router.get("/history")
def get_history(
    limit: int = Query(default=20, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    type: str = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(db_models.Analysis)
    if type in ("url", "image", "video"):
        q = q.filter(db_models.Analysis.type == type)
    total = q.count()
    records = q.order_by(db_models.Analysis.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": [_serialize_summary(r) for r in records],
    }


def _serialize_summary(r: db_models.Analysis) -> dict:
    return {
        "analysis_id": r.id,
        "type": r.type,
        "trust_score": r.trust_score,
        "risk_level": r.risk_level,
        "prediction": r.prediction,
        "confidence": r.confidence,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "url": r.url if r.type == "url" else None,
    }


def _serialize(r: db_models.Analysis, db: Session) -> dict:
    evidence = db.query(db_models.Evidence).filter(db_models.Evidence.analysis_id == r.id).all()
    model_results = db.query(db_models.ModelResult).filter(db_models.ModelResult.analysis_id == r.id).all()
    return {
        "analysis_id": r.id,
        "type": r.type,
        "trust_score": r.trust_score,
        "risk_level": r.risk_level,
        "prediction": r.prediction,
        "confidence": r.confidence,
        "url": r.url,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "model_results": [
            {"model_name": m.model_name, "prediction": m.prediction, "probability": m.probability}
            for m in model_results
        ],
        "evidence": [
            {"source": e.source, "description": e.description, "severity": e.severity, "supporting_value": e.supporting_value}
            for e in evidence
        ],
    }
