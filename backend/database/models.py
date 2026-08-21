"""
database/models.py
SQLAlchemy ORM models for TrustAI.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from database.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Authentication models ──────────────────────────────────────────────────────

class User(Base):
    """Registered application user."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(128), nullable=False)
    email = Column(String(254), unique=True, nullable=False, index=True)  # stored lowercase
    password_hash = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="user")  # "user" | "admin"
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")


class PasswordResetToken(Base):
    """Single-use, time-limited password-reset token.

    The raw token is never stored — only its SHA-256 hex digest.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 of raw token
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)  # None = not yet used

    user = relationship("User", back_populates="reset_tokens")


# ── Analysis models ───────────────────────────────────────────────────────────

class Analysis(Base):
    """Top-level record for each analysis request."""

    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=_uuid)
    type = Column(String(16), nullable=False)          # "image" | "video" | "url"
    input_hash = Column(String(64), nullable=True)     # SHA-256 of file or URL
    url = Column(Text, nullable=True)                  # stored only for URL type
    trust_score = Column(Integer, nullable=True)
    risk_level = Column(String(32), nullable=True)
    confidence = Column(Float, nullable=True)
    prediction = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    # Relationships
    model_results = relationship("ModelResult", back_populates="analysis", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="analysis", cascade="all, delete-orphan")
    files = relationship("AnalysisFile", back_populates="analysis", cascade="all, delete-orphan")


class ModelResult(Base):
    """Stores per-model raw output for an analysis."""

    __tablename__ = "model_results"

    id = Column(String(36), primary_key=True, default=_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id"), nullable=False)
    model_name = Column(String(64), nullable=False)
    prediction = Column(String(64), nullable=True)
    probability = Column(Float, nullable=True)
    raw_output = Column(Text, nullable=True)   # JSON string for additional data

    analysis = relationship("Analysis", back_populates="model_results")


class Evidence(Base):
    """Individual evidence items attached to an analysis."""

    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id"), nullable=False)
    source = Column(String(64), nullable=False)      # e.g. "url_ml_model", "virustotal"
    description = Column(Text, nullable=False)
    severity = Column(String(16), nullable=False)    # "high" | "medium" | "low" | "info"
    supporting_value = Column(Text, nullable=True)   # numeric or label string

    analysis = relationship("Analysis", back_populates="evidence")


class AnalysisFile(Base):
    """Track uploaded file paths for an analysis (cleaned up post-processing)."""

    __tablename__ = "analysis_files"

    id = Column(String(36), primary_key=True, default=_uuid)
    analysis_id = Column(String(36), ForeignKey("analyses.id"), nullable=False)
    file_path = Column(Text, nullable=False)
    file_type = Column(String(32), nullable=True)   # "image" | "video"

    analysis = relationship("Analysis", back_populates="files")
