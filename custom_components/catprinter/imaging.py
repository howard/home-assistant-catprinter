"""Image and text -> printer-row conversion using Pillow.

This replaces rbaron/catprinter's OpenCV-based pipeline with Pillow + numpy,
both of which ship with Home Assistant core, so the integration needs no extra
``requirements`` and avoids heavy native wheels.

The output of :func:`image_to_rows` / :func:`text_to_rows` is a 2-D boolean
numpy array of shape ``(height, PRINT_WIDTH)`` where ``True`` means "burn this
pixel" (black), matching what :func:`commands.cmds_print_img` expects.

Only Pillow and numpy are imported at module load so this file stays importable
(and unit-testable) without Home Assistant. The Home Assistant helpers used by
:func:`async_fetch_image` are imported lazily inside that coroutine.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PRINT_WIDTH = 384

DITHER_FLOYD_STEINBERG = "floyd-steinberg"
DITHER_MEAN_THRESHOLD = "mean-threshold"
DITHER_NONE = "none"
DITHER_OPTIONS = (DITHER_FLOYD_STEINBERG, DITHER_MEAN_THRESHOLD, DITHER_NONE)

_THRESHOLD = 127


def _to_black_mask(image: Image.Image, dither: str) -> np.ndarray:
    """Binarize an 8-bit grayscale ``image`` into a True==black boolean array."""
    if dither == DITHER_FLOYD_STEINBERG:
        # Pillow's "1" conversion applies Floyd-Steinberg dithering. In mode
        # "1", True == white (255), so invert to get True == black.
        return ~np.asarray(image.convert("1"), dtype=bool)

    arr = np.asarray(image, dtype=np.uint8)
    if dither == DITHER_MEAN_THRESHOLD:
        # Pixels darker than the mean are burned.
        return arr <= arr.mean()
    if dither == DITHER_NONE:
        return arr <= _THRESHOLD
    raise ValueError(
        f"unknown image binarization algorithm: {dither!r}; "
        f"expected one of {DITHER_OPTIONS}"
    )


def image_to_rows(source: bytes | str, dither: str = DITHER_FLOYD_STEINBERG) -> np.ndarray:
    """Convert image bytes (or a file path) into printer rows.

    The image is converted to grayscale and scaled to ``PRINT_WIDTH`` pixels
    wide (preserving aspect ratio), then binarized with the chosen ``dither``
    algorithm. ``dither='none'`` performs a plain threshold and requires the
    source image to already be ``PRINT_WIDTH`` pixels wide.
    """
    if dither not in DITHER_OPTIONS:
        raise ValueError(
            f"unknown image binarization algorithm: {dither!r}; "
            f"expected one of {DITHER_OPTIONS}"
        )

    fp = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    with Image.open(fp) as opened:
        image = opened.convert("L")

        if dither == DITHER_NONE:
            if image.width != PRINT_WIDTH:
                raise ValueError(
                    f"image width is {image.width}px; a width of {PRINT_WIDTH}px "
                    f"is required for dither='none'"
                )
        else:
            height = max(1, round(image.height * PRINT_WIDTH / image.width))
            image = image.resize((PRINT_WIDTH, height), Image.LANCZOS)

        return _to_black_mask(image, dither)


def _load_font(font_size: int) -> ImageFont.ImageFont:
    """Best-effort scalable font, falling back to Pillow's bundled default."""
    try:
        # Pillow >= 10.1 lets load_default take a size and returns a scalable font.
        return ImageFont.load_default(size=font_size)
    except TypeError:
        pass
    for candidate in ("DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(candidate, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw,
               max_width: int) -> list[str]:
    """Greedily wrap ``text`` so each rendered line fits within ``max_width``."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=font) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


def text_to_rows(text: str, font_size: int = 24) -> np.ndarray:
    """Render ``text`` (word-wrapped to the paper width) into printer rows."""
    measure = Image.new("L", (PRINT_WIDTH, font_size * 2), color=255)
    draw = ImageDraw.Draw(measure)
    font = _load_font(font_size)

    lines = _wrap_text(text, font, draw, PRINT_WIDTH)
    line_height = font_size + max(2, font_size // 6)
    height = max(line_height, line_height * len(lines))

    canvas = Image.new("L", (PRINT_WIDTH, height), color=255)
    pen = ImageDraw.Draw(canvas)
    for index, line in enumerate(lines):
        if line:
            pen.text((0, index * line_height), line, fill=0, font=font)

    return _to_black_mask(canvas, DITHER_NONE)


async def async_fetch_image(hass, source: str) -> bytes:
    """Fetch image bytes from an http(s) URL or an allow-listed local path."""
    if source.startswith(("http://", "https://")):
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        session = async_get_clientsession(hass)
        async with session.get(source) as response:
            response.raise_for_status()
            return await response.read()

    if not hass.config.is_allowed_path(source):
        raise ValueError(
            f"path {source!r} is not allowed; add its directory to "
            f"allowlist_external_dirs in configuration.yaml"
        )

    def _read() -> bytes:
        with open(source, "rb") as handle:
            return handle.read()

    return await hass.async_add_executor_job(_read)
