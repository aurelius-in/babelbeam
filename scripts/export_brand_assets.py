"""Crop the approved showcase and write transparent brand rasters.

The source art is a white-background showcase, not a production asset.
This script removes the white field, splits the wordmark from the app icon,
and builds a light wordmark for dark surfaces. It does not invent a new mark.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "reference" / "approved-logo-showcase.png"
OUT_BRAND = ROOT / "apps" / "web" / "public" / "brand"
OUT_ICONS = ROOT / "apps" / "web" / "public" / "icons"


def _is_showcase_background(red: int, green: int, blue: int) -> bool:
    """White field and the app-icon tile, not the cyan beam or navy mark."""
    if _is_cyan(red, green, blue):
        return False
    spread = max(red, green, blue) - min(red, green, blue)
    return min(red, green, blue) > 188 and spread < 36


def _knock_out_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if _is_showcase_background(red, green, blue):
                pixels[x, y] = (red, green, blue, 0)
            elif min(red, green, blue) > 170 and not _is_cyan(red, green, blue):
                fade = int(255 * (188 - min(red, green, blue)) / 18)
                pixels[x, y] = (red, green, blue, min(alpha, max(0, fade)))
    return rgba


def _content_rows(image: Image.Image) -> list[int]:
    pixels = image.load()
    width, height = image.size
    rows: list[int] = []
    for y in range(height):
        if any(pixels[x, y][3] > 12 for x in range(width)):
            rows.append(y)
    return rows


def _bands(rows: list[int]) -> list[tuple[int, int]]:
    if not rows:
        return []
    bands: list[tuple[int, int]] = []
    start = previous = rows[0]
    for row in rows[1:]:
        if row - previous > 24:
            bands.append((start, previous))
            start = row
        previous = row
    bands.append((start, previous))
    return bands


def _trim(image: Image.Image, pad: int = 8) -> Image.Image:
    bbox = image.getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(image.width, right + pad)
    bottom = min(image.height, bottom + pad)
    return image.crop((left, top, right, bottom))


def _is_cyan(red: int, green: int, blue: int) -> bool:
    luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return blue > 150 and green > 110 and (blue - red) > 25 and luma > 70


def _to_light(image: Image.Image) -> Image.Image:
    """Lift navy ink toward ice so the wordmark stays visible on a dark canvas."""
    light = image.copy()
    pixels = light.load()
    width, height = light.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 8 or _is_cyan(red, green, blue):
                continue
            luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            if luma >= 170:
                continue
            lift = (170 - luma) / 170
            pixels[x, y] = (
                min(255, int(red + (245 - red) * lift)),
                min(255, int(green + (251 - green) * lift)),
                min(255, int(blue + (255 - blue) * lift)),
                alpha,
            )
    return light


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)
    print(f"wrote {path.relative_to(ROOT)} {image.size}")


def _maskable(icon: Image.Image, size: int = 512) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (8, 17, 31, 255))
    inner = int(size * 0.62)
    fitted = icon.copy()
    fitted.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    x = (size - fitted.width) // 2
    y = (size - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))
    return canvas


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source art: {SOURCE}")
    knocked = _knock_out_white(Image.open(SOURCE))
    rows = _content_rows(knocked)
    bands = _bands(rows)
    if len(bands) < 2:
        raise SystemExit(f"Expected wordmark and icon bands, found {len(bands)}")
    word_top, word_bottom = bands[0]
    icon_top, icon_bottom = bands[1]
    word = _trim(knocked.crop((0, word_top, knocked.width, word_bottom + 1)), pad=12)
    icon = _trim(knocked.crop((0, icon_top, knocked.width, icon_bottom + 1)), pad=16)
    _save(word, OUT_BRAND / "logo-full.png")
    _save(_to_light(word), OUT_BRAND / "logo-light.png")
    _save(icon, OUT_BRAND / "icon.png")
    for size, name in (
        (512, "icon-512.png"),
        (192, "icon-192.png"),
        (180, "apple-touch-icon-180.png"),
        (32, "favicon-32.png"),
        (16, "favicon-16.png"),
    ):
        resized = icon.copy()
        resized.thumbnail((size, size), Image.Resampling.LANCZOS)
        plate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        plate.alpha_composite(
            resized,
            ((size - resized.width) // 2, (size - resized.height) // 2),
        )
        _save(plate, OUT_ICONS / name)
    _save(_maskable(icon), OUT_ICONS / "maskable-512.png")


if __name__ == "__main__":
    main()
