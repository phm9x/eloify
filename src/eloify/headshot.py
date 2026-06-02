"""Player headshots, stored as committed braille art.

A player's avatar lives in two places: the source photo — a small square JPEG —
sits in a git-ignored folder, while the *rendered* art is committed as a
plain-text file and is what actually gets displayed. So the repo carries the
little braille faces but never the real photos.

`generate` (used by `elo set-headshot`) face-crops a source image into the
git-ignored folder and renders it to braille with `chafa`. Displaying a headshot
just prints the committed text, so it needs nothing installed — only generating
one requires Pillow, OpenCV (face crop) and the `chafa` binary (rendering).
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

ART_COLS = 40  # character columns in the committed art
ART_ROWS = 20  # rows (terminal cells are ~2x tall as wide, so cols:rows ≈ 2:1)
THUMB_SIZE = 512  # px; the git-ignored source images are square face crops

_PKG = Path(__file__).parent
# Committed ASCII art: assets/headshots/<username>.txt
ART_DIR = _PKG / "assets" / "headshots"
# Git-ignored source images (present in a dev checkout): <repo>/headshots/<username>.jpg
IMAGE_DIR = _PKG.parents[1] / "headshots"


class HeadshotError(RuntimeError):
    """Couldn't load or render a headshot image (user-facing)."""


def art_text(username: str) -> str | None:
    """The committed braille headshot for `username`, or None if there isn't one."""
    p = ART_DIR / f"{username}.txt"
    return p.read_text() if p.exists() else None


def _load_bytes(src: str) -> bytes:
    """Fetch raw image bytes from an http(s) URL or a local file path."""
    if src.startswith(("http://", "https://")):
        try:
            req = Request(src, headers={"User-Agent": "eloify"})
            with urlopen(req, timeout=10) as resp:  # noqa: S310 — scheme checked above
                return resp.read()
        except OSError as e:
            raise HeadshotError(f"couldn't fetch {src}: {e}") from e
    path = os.path.expanduser(src)
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        raise HeadshotError(f"couldn't read {path}: {e}") from e


def _pillow():
    """Import Pillow, or raise a friendly HeadshotError if it isn't installed."""
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError

        return Image, ImageOps, UnidentifiedImageError
    except ImportError as e:
        raise HeadshotError(
            "Pillow and OpenCV are needed to add headshots — install them with "
            "`pip install 'eloify[headshots]'`."
        ) from e


def _open(src: str):
    """Load `src` (path or URL) into an EXIF-corrected Pillow image, or raise."""
    Image, ImageOps, UnidentifiedImageError = _pillow()
    try:
        img = Image.open(io.BytesIO(_load_bytes(src)))
        return ImageOps.exif_transpose(img)  # honour any rotation metadata
    except (UnidentifiedImageError, OSError) as e:
        raise HeadshotError(f"not a readable image: {src}") from e


def _render_braille(image_path: Path) -> str:
    """Render an image file to monochrome braille art with chafa."""
    if shutil.which("chafa") is None:
        raise HeadshotError(
            "chafa is needed to render headshots — install it (e.g. `brew install chafa`)."
        )
    try:
        result = subprocess.run(
            ["chafa", "-f", "symbols", "-c", "none", "--symbols", "braille",
             "-s", f"{ART_COLS}x{ART_ROWS}", "--stretch", str(image_path)],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        raise HeadshotError(f"chafa failed: {e.stderr.strip() or e}") from e
    return result.stdout.rstrip("\n") + "\n"


def _face_square(img):
    """Crop `img` to a square framing the largest detected face.

    Falls back to a top-biased centre square when no face is found (these are
    portrait headshots, so the face sits high in the frame). Returns a PIL image.
    """
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        raise HeadshotError(
            "Pillow and OpenCV are needed to add headshots — install them with "
            "`pip install 'eloify[headshots]'`."
        ) from e

    W, H = img.size
    gray = np.array(img.convert("L"))
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(H // 12, H // 12)
    )
    if len(faces):
        fx, fy, fw, fh = max(faces, key=lambda b: b[2] * b[3])
        side = min(fh * 1.45, W, H)
        cx, cy = fx + fw / 2, fy + fh / 2 - fh * 0.15  # nudge up to keep the hair
    else:
        side = min(W, H)
        cx, cy = W / 2, side / 2 + (H - side) * 0.2
    left = max(0, min(cx - side / 2, W - side))
    top = max(0, min(cy - side / 2, H - side))
    return img.crop((round(left), round(top), round(left + side), round(top + side)))


def generate(username: str, src: str) -> Path:
    """Face-crop `src` and write the player's braille headshot.

    The square face crop is saved to the git-ignored image folder; chafa renders
    it to braille, written (and meant to be committed) under the package as
    <username>.txt. Returns the art path.
    """
    Image, ImageOps, _ = _pillow()

    crop = ImageOps.fit(
        _face_square(_open(src).convert("RGB")), (THUMB_SIZE, THUMB_SIZE), Image.LANCZOS
    )
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    img_path = IMAGE_DIR / f"{username}.jpg"
    crop.save(img_path, "JPEG", quality=90)

    ART_DIR.mkdir(parents=True, exist_ok=True)
    art = ART_DIR / f"{username}.txt"
    art.write_text(_render_braille(img_path))
    return art
