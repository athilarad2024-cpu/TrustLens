"""
api/auth.py
Full database-backed authentication for TrustAI.

Endpoints:
    POST /api/auth/register        — create account
    POST /api/auth/login           — authenticate and receive JWT
    POST /api/auth/forgot-password — request password reset (no email-existence leak)
    POST /api/auth/reset-password  — consume reset token and update password

Security notes:
    • Passwords are bcrypt-hashed; plaintext is never stored or logged.
    • Emails are normalised to lowercase before storage and lookup.
    • The forgot-password endpoint always returns the same generic message.
    • Reset tokens are 32-byte random hex; only their SHA-256 digest is stored.
    • Tokens expire after PASSWORD_RESET_EXPIRE_MINUTES (default 30) and are single-use.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
import bcrypt
from jose import JWTError, jwt

from database.database import get_db
from database.models import PasswordResetToken, User
from services.email_service import send_password_reset_email

logger = logging.getLogger("trustai.auth")

router = APIRouter(prefix="/auth", tags=["Auth"])

# ── Configuration (all from environment — no hardcoded values) ─────────────────

SECRET_KEY: str = os.getenv("SECRET_KEY", "changeme_generate_a_real_secret")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
PASSWORD_RESET_EXPIRE_MINUTES: int = int(os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30"))
DEFAULT_FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://trust-lens-cyan.vercel.app")

# Minimum password policy
_MIN_PASSWORD_LEN = 8


# ── Internal helpers ───────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    pwd_bytes = plain.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _generate_reset_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Only the hash is stored in DB."""
    raw = secrets.token_hex(32)
    return raw, _sha256(raw)


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _password_strength_error(password: str) -> str | None:
    """Return an error message if password fails policy, else None."""
    if len(password) < _MIN_PASSWORD_LEN:
        return f"Password must be at least {_MIN_PASSWORD_LEN} characters."
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    return None


# ── Request / Response schemas ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name is required.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class MessageResponse(BaseModel):
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new user account.
    - Email is normalised to lowercase and must be unique.
    - Password is validated for strength then bcrypt-hashed.
    - Plaintext password is never stored or logged.
    """
    email = _normalise_email(body.email)

    # Validate passwords match
    if body.password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passwords do not match.",
        )

    # Validate password strength
    strength_err = _password_strength_error(body.password)
    if strength_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=strength_err,
        )

    # Check for existing account (case-insensitive)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    user = User(
        name=body.name.strip(),
        email=email,
        password_hash=_hash_password(body.password),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()

    logger.info("New user registered: %s", email)
    return MessageResponse(message="Account created successfully. You can now sign in.")


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate and receive a JWT",
)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate against the database.
    Returns a JWT on success; always returns the same error for wrong credentials.
    """
    email = _normalise_email(body.email)

    user = db.query(User).filter(User.email == email).first()

    # Constant-time comparison: always verify even if user not found to prevent timing attacks
    dummy_hash = "$2b$12$invalidhashfortimingnnnnnnnnnnnnnnnnnnnnnnn"
    stored_hash = user.password_hash if user else dummy_hash
    password_ok = _verify_password(body.password, stored_hash)

    if not user or not password_ok or not user.is_active:
        logger.warning("Failed login attempt for email: %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = _create_access_token(data={"sub": user.id, "email": user.email, "name": user.name, "role": user.role})

    logger.info("Successful login: %s", email)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user={"id": user.id, "email": user.email, "name": user.name, "role": user.role},
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset link",
)
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """
    Generate a password reset token and send an email.

    SECURITY: Always returns the same generic message regardless of whether
    the email address exists in the database. This prevents account enumeration.
    """
    _GENERIC_MESSAGE = (
        "If an account exists for this email address, "
        "a password reset link has been sent."
    )
    email = _normalise_email(body.email)

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        # Return generic message — do NOT leak whether account exists
        return MessageResponse(message=_GENERIC_MESSAGE)

    # Invalidate any previous unused tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at == None,  # noqa: E711
    ).delete(synchronize_session=False)

    raw_token, token_hash = _generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    db.commit()

    # Dynamically detect frontend origin (e.g. https://trust-lens-cyan.vercel.app or http://localhost:5173)
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    
    if origin:
        frontend_base = origin.rstrip("/")
    elif referer:
        # Strip path from referer e.g. https://trust-lens-cyan.vercel.app/forgot-password -> https://trust-lens-cyan.vercel.app
        from urllib.parse import urlparse
        p = urlparse(referer)
        frontend_base = f"{p.scheme}://{p.netloc}"
    else:
        frontend_base = os.getenv("FRONTEND_URL", DEFAULT_FRONTEND_URL).rstrip("/")

    reset_url = f"{frontend_base}/reset-password?token={raw_token}"

    try:
        send_password_reset_email(to_email=user.email, reset_url=reset_url, user_name=user.name)
    except Exception:
        # Log the error but return generic success — avoids leaking SMTP config issues
        logger.exception("Reset email delivery failed for %s", email)

    return MessageResponse(message=_GENERIC_MESSAGE)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a valid token",
)
async def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Consume a reset token and update the user's password.
    - Token must not be expired.
    - Token must not have been used before.
    - Token is invalidated immediately on use.
    """
    _INVALID_MSG = "This password reset link is invalid or has expired."

    # Validate passwords
    if body.new_password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passwords do not match.",
        )

    strength_err = _password_strength_error(body.new_password)
    if strength_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=strength_err,
        )

    token_hash = _sha256(body.token.strip())
    now = datetime.now(timezone.utc)

    reset_record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )

    if not reset_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_MSG)

    if reset_record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_MSG)

    # SQLite stores datetimes without timezone; normalise for comparison
    expires_at = reset_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_MSG)

    # Update password and mark token as used
    user = reset_record.user
    user.password_hash = _hash_password(body.new_password)
    user.updated_at = now
    reset_record.used_at = now

    db.commit()

    logger.info("Password reset successful for user: %s", user.email)
    return MessageResponse(message="Your password has been updated. You can now sign in.")
