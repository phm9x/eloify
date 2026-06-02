import shutil

import pytest
from PIL import Image

from eloify import headshot
from eloify.headshot import HeadshotError, art_text, generate

HAVE_CHAFA = shutil.which("chafa") is not None


def _write(path, color, size=(400, 500)):
    Image.new("RGB", size, color).save(path)
    return str(path)


def test_art_text_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(headshot, "ART_DIR", tmp_path)
    assert art_text("ghost") is None


def test_not_an_image_raises(tmp_path):
    p = tmp_path / "junk.png"
    p.write_text("definitely not an image")
    with pytest.raises(HeadshotError):
        generate("x", str(p))


@pytest.mark.skipif(not HAVE_CHAFA, reason="chafa not installed")
def test_generate_writes_committed_text_and_ignored_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setattr(headshot, "ART_DIR", tmp_path / "art")
    monkeypatch.setattr(headshot, "IMAGE_DIR", tmp_path / "img")

    out = generate("ghost", _write(tmp_path / "src.png", (180, 140, 120)))

    # Braille art is committed-as-text and now readable by username.
    assert out == tmp_path / "art" / "ghost.txt"
    text = art_text("ghost")
    assert text and out.read_text() == text
    # The source thumbnail is a small square kept out of the committed tree.
    thumb = tmp_path / "img" / "ghost.jpg"
    assert thumb.exists() and Image.open(thumb).size == (headshot.THUMB_SIZE, headshot.THUMB_SIZE)


@pytest.mark.skipif(HAVE_CHAFA, reason="chafa is installed")
def test_generate_without_chafa_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(headshot, "ART_DIR", tmp_path / "art")
    monkeypatch.setattr(headshot, "IMAGE_DIR", tmp_path / "img")
    with pytest.raises(HeadshotError):
        generate("ghost", _write(tmp_path / "src.png", (180, 140, 120)))
