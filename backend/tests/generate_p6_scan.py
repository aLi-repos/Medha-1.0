"""Generate ONE synthetic scanned industrial-style inspection document (P6).

Clearly fictional / demo-safe. Not real MRPL data.
Creates:
  backend/tests/fixtures/Pump_P204_Scanned_Inspection.png
  backend/tests/fixtures/Pump_P204_Scanned_Inspection.pdf
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
PNG_PATH = os.path.join(FIXTURE_DIR, "Pump_P204_Scanned_Inspection.png")
PDF_PATH = os.path.join(FIXTURE_DIR, "Pump_P204_Scanned_Inspection.pdf")

LINES = [
    "PUMP P-204 INSPECTION REPORT (SYNTHETIC DEMO)",
    "Equipment: Centrifugal Pump P-204",
    "Inspection Date: 2026-01-15 (Demo Date)",
    "Observed Vibration: 4.8 mm/s RMS (synthetic value)",
    "Temperature: 62 C (synthetic value)",
    "Inspection finding: elevated vibration detected.",
    "Recommended action: monitor trend and schedule seal inspection.",
    "This document is synthetic demonstration content for SIH26117.",
    "NOT real MRPL operational data.",
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in (
        "arial.ttf",
        "arialbd.ttf",
        "segoeui.ttf",
        "consola.ttf",
        "DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def generate_png(path: str = PNG_PATH) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    width, height = 900, 640
    # Slightly off-white “paper” background
    img = Image.new("RGB", (width, height), (248, 246, 240))
    draw = ImageDraw.Draw(img)

    # Border like a scanned form
    draw.rectangle([24, 24, width - 24, height - 24], outline=(40, 40, 40), width=2)

    title_font = _font(28)
    body_font = _font(20)

    y = 50
    for i, line in enumerate(LINES):
        font = title_font if i == 0 else body_font
        color = (15, 23, 42) if i != 0 else (15, 23, 42)
        draw.text((48, y), line, fill=color, font=font)
        y += 48 if i == 0 else 40
        if i == 0:
            draw.line([(48, y - 12), (width - 48, y - 12)], fill=(80, 80, 80), width=1)

    # Light scan noise (very subtle) to resemble a scan without destroying OCR
    noise = Image.new("L", (width, height))
    npix = noise.load()
    # Deterministic light pattern (no RNG dependency for reproducibility)
    for yy in range(0, height, 4):
        for xx in range(0, width, 4):
            v = 0 if (xx // 4 + yy // 4) % 7 == 0 else 255
            for dy in range(4):
                for dx in range(4):
                    if yy + dy < height and xx + dx < width:
                        npix[xx + dx, yy + dy] = v
    noise = noise.filter(ImageFilter.GaussianBlur(0.4))
    overlay = Image.merge("RGB", (noise, noise, noise))
    img = Image.blend(img, overlay, alpha=0.03)

    img.save(path, "PNG")
    return path


def generate_pdf(png_path: str = PNG_PATH, pdf_path: str = PDF_PATH) -> str:
    """Single-page PDF that embeds the scan image (scanned-PDF style)."""
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    if not os.path.isfile(png_path):
        generate_png(png_path)
    img = Image.open(png_path).convert("RGB")
    img.save(pdf_path, "PDF", resolution=150.0)
    return pdf_path


def main() -> None:
    png = generate_png()
    pdf = generate_pdf(png)
    print(f"PNG: {png}")
    print(f"PDF: {pdf}")


if __name__ == "__main__":
    main()
