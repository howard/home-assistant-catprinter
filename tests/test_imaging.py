"""Tests for the Pillow-based imaging module.

These exercise the pure (non-Home-Assistant) parts of ``imaging.py``: turning
an image or text into printer rows. They require Pillow + numpy but not Home
Assistant.
"""
import io
import os
import sys

from PIL import Image

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "catprinter"),
)

import imaging  # noqa: E402


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_image_to_rows_width_and_type():
    src = Image.new("L", (200, 100), color=255)  # all white
    rows = imaging.image_to_rows(_png_bytes(src), dither="floyd-steinberg")
    assert len(rows) > 0
    # Every row is exactly the printer width.
    assert all(len(r) == imaging.PRINT_WIDTH for r in rows)
    # Aspect ratio preserved: 200x100 -> width 384 -> height ~192.
    assert abs(len(rows) - 192) <= 2
    # Pixels are booleans.
    assert all(isinstance(bool(p), bool) for p in rows[0])


def test_all_white_image_has_no_black_pixels():
    src = Image.new("L", (384, 50), color=255)
    rows = imaging.image_to_rows(_png_bytes(src), dither="none")
    assert not any(any(row) for row in rows)  # True == black; none expected


def test_all_black_image_is_all_black():
    src = Image.new("L", (384, 50), color=0)
    rows = imaging.image_to_rows(_png_bytes(src), dither="none")
    assert all(all(row) for row in rows)  # every pixel True (black)


def test_none_dither_requires_correct_width():
    src = Image.new("L", (200, 50), color=255)
    try:
        imaging.image_to_rows(_png_bytes(src), dither="none")
    except ValueError:
        return
    raise AssertionError("expected ValueError for wrong width with dither='none'")


def test_unknown_dither_raises():
    src = Image.new("L", (384, 10), color=255)
    try:
        imaging.image_to_rows(_png_bytes(src), dither="bogus")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown dither algorithm")


def test_text_to_rows_produces_black_pixels():
    rows = imaging.text_to_rows("Hello, cat!", font_size=24)
    assert all(len(r) == imaging.PRINT_WIDTH for r in rows)
    # Some ink must have been laid down.
    assert any(any(row) for row in rows)


def test_text_to_rows_blank_for_empty_string():
    rows = imaging.text_to_rows("", font_size=24)
    assert all(len(r) == imaging.PRINT_WIDTH for r in rows)
    assert not any(any(row) for row in rows)
