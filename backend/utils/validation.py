"""
utils/validation.py
Input validation — file type/MIME, size limits, URL syntax/protocol.
Includes a basic SSRF guard per Section 25 of the master document.
"""

import ipaddress
import os
import re
from typing import Tuple

import validators
from fastapi import HTTPException, UploadFile

# ── Allowed MIME types ─────────────────────────────────────────────────────────
ALLOWED_IMAGE_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}

ALLOWED_VIDEO_MIME = {
    "video/mp4",
    "video/x-msvideo",   # .avi
    "video/quicktime",   # .mov
    "video/x-matroska",  # .mkv
    "video/webm",
}

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

# Private / loopback ranges — block SSRF to internal services
_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
]


def _max_image_bytes() -> int:
    return int(os.getenv("MAX_IMAGE_MB", "10")) * 1024 * 1024


def _max_video_bytes() -> int:
    return int(os.getenv("MAX_VIDEO_MB", "100")) * 1024 * 1024


# ── File validators ────────────────────────────────────────────────────────────

def validate_image_upload(file: UploadFile) -> None:
    """Raise HTTPException if the uploaded file is not an accepted image."""
    _check_extension(file.filename or "", ALLOWED_IMAGE_EXTENSIONS, "image")
    _check_content_type(file.content_type or "", ALLOWED_IMAGE_MIME, "image")


def validate_video_upload(file: UploadFile) -> None:
    """Raise HTTPException if the uploaded file is not an accepted video."""
    _check_extension(file.filename or "", ALLOWED_VIDEO_EXTENSIONS, "video")
    _check_content_type(file.content_type or "", ALLOWED_VIDEO_MIME, "video")


async def check_file_size(file: UploadFile, max_bytes: int, label: str) -> bytes:
    """
    Read the entire file into memory (up to max_bytes+1) and raise if too large.
    Returns file bytes for further processing.
    """
    data = await file.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "File too large",
                "message": f"{label} must be smaller than {max_bytes // (1024*1024)} MB.",
            },
        )
    return data


def image_max_bytes() -> int:
    return _max_image_bytes()


def video_max_bytes() -> int:
    return _max_video_bytes()


# ── URL validator ──────────────────────────────────────────────────────────────

def validate_url(url: str) -> str:
    """
    Validate URL syntax, enforce http/https only, and apply a basic SSRF guard.
    Returns the (stripped) URL or raises HTTPException.
    """
    url = url.strip()

    if not url:
        raise HTTPException(
            status_code=422,
            detail={"error": "Empty URL", "message": "Please provide a URL to analyze."},
        )

    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Unsupported protocol",
                "message": "Only http:// and https:// URLs are supported.",
            },
        )

    if not validators.url(url):
        raise HTTPException(
            status_code=422,
            detail={"error": "Invalid URL", "message": "The URL format is not valid."},
        )

    _ssrf_guard(url)
    return url


def _ssrf_guard(url: str) -> None:
    """Block URLs that resolve to private/loopback IP ranges."""
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""

    # Block direct IP addresses in private ranges
    try:
        addr = ipaddress.ip_address(hostname)
        for net in _PRIVATE_RANGES:
            if addr in net:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "Invalid URL",
                        "message": "URLs pointing to private/internal addresses are not allowed.",
                    },
                )
    except ValueError:
        pass  # hostname is a domain name, not an IP — allow through


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_extension(filename: str, allowed: set, label: str) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Unsupported file type",
                "message": f"Please upload a supported {label} format: {', '.join(sorted(allowed))}",
            },
        )


def _check_content_type(content_type: str, allowed: set, label: str) -> None:
    # Strip parameters like '; charset=utf-8'
    mime = content_type.split(";")[0].strip().lower()
    if mime not in allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Unsupported file type",
                "message": f"Detected MIME type '{mime}' is not an accepted {label} format.",
            },
        )
