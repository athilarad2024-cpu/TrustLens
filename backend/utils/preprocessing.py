"""
utils/preprocessing.py
Shared preprocessing helpers: temp-file lifecycle, image transforms.
torchvision is imported lazily — server boots without it installed.
"""

import hashlib
import os
import uuid
from pathlib import Path
from typing import Optional

from PIL import Image

# ── Torch / torchvision — lazy import ─────────────────────────────────────────
try:
    import torchvision.transforms as T
    _TV_AVAILABLE = True
except ImportError:
    T = None  # type: ignore
    _TV_AVAILABLE = False


# ── Temp-file helpers ──────────────────────────────────────────────────────────

def get_upload_dir() -> Path:
    upload_dir = Path(os.getenv("UPLOAD_DIR", "uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def save_temp_file(data: bytes, suffix: str) -> Path:
    """
    Save bytes to a randomly named temp file in the upload directory.
    Returns the path. Caller is responsible for cleanup.
    """
    upload_dir = get_upload_dir()
    filename = f"{uuid.uuid4().hex}{suffix}"
    path = upload_dir / filename
    path.write_bytes(data)
    return path


def cleanup_temp_file(path: Optional[Path]) -> None:
    """Delete a temp file silently — never raise on failure."""
    try:
        if path and path.exists():
            path.unlink()
    except Exception:
        pass


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of bytes — used for input deduplication."""
    return hashlib.sha256(data).hexdigest()


# ── Image transforms ───────────────────────────────────────────────────────────

# EfficientNet / ConvNet family normalisation values
_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD  = [0.229, 0.224, 0.225]

if _TV_AVAILABLE:
    INFERENCE_TRANSFORM = T.Compose([
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
    ])

    TRAIN_TRANSFORM = T.Compose([
        T.RandomResizedCrop(224),
        T.RandomHorizontalFlip(),
        T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        T.ToTensor(),
        T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
    ])
else:
    INFERENCE_TRANSFORM = None  # type: ignore
    TRAIN_TRANSFORM = None      # type: ignore


def load_pil_image(path: Path) -> Image.Image:
    """Open an image, convert to RGB (handles RGBA/greyscale/palette modes)."""
    img = Image.open(path)
    return img.convert("RGB")
