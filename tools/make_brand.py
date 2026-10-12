"""Cut the emblem and wordmark out of the supplied logo and write HA brand images.

usage: python tools/make_brand.py tools/source/italtecnica-logo.png custom_components/sirio/brand
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

im = Image.open(src).convert("RGBA")
W, H = im.size

# Column split found by inspection: emblem = cols 3..179, wordmark = cols 210..end
EMBLEM = (0, 0, 195, H)
WORDMARK = (195, 0, W, H)


def trim(img: Image.Image) -> Image.Image:
    bbox = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return img.crop(bbox) if bbox else img


def to_dark(img: Image.Image) -> Image.Image:
    """Light-on-dark version: invert neutral (black/grey) pixels, keep the red,
    and turn the white 'holes' transparent so the dark background shows through."""
    a = np.array(img).astype(float)
    rgb = a[..., :3]
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    lum = rgb.mean(axis=2)
    neutral = chroma < 50
    for c in range(3):
        a[..., c] = np.where(neutral, 255 - lum, a[..., c])
    hole = neutral & (lum > 235)
    a[..., 3] = np.where(hole, 0, a[..., 3])
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def square_icon(img: Image.Image, size: int = 256, margin: int = 12) -> Image.Image:
    img = trim(img)
    inner = size - 2 * margin
    scale = inner / max(img.size)
    new = img.resize(
        (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
        Image.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(new, ((size - new.width) // 2, (size - new.height) // 2), new)
    return canvas


emblem = im.crop(EMBLEM)
wordmark = trim(im.crop(WORDMARK))

icon = square_icon(emblem)
logo = wordmark  # native resolution; its shortest side (height) is within 128-256 px

icon.save(out / "icon.png")
to_dark(icon).save(out / "dark_icon.png")
logo.save(out / "logo.png")
to_dark(logo).save(out / "dark_logo.png")

# Preview sheet: light and dark backgrounds (for checking only, not shipped)
sheet = Image.new("RGBA", (900, 520), (255, 255, 255, 255))
dark_bg = Image.new("RGBA", (900, 260), (24, 28, 32, 255))
sheet.paste(dark_bg, (0, 260))
sheet.alpha_composite(icon, (20, 2))
sheet.alpha_composite(logo, (290, 40))
sheet.alpha_composite(to_dark(icon), (20, 262))
sheet.alpha_composite(to_dark(logo), (290, 300))
sheet.convert("RGB").save(Path(__file__).resolve().parent / "brand_preview.png")

for f in sorted(out.iterdir()):
    with Image.open(f) as i:
        print(f.name, i.size)
