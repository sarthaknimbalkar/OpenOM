# Generate the openOM extension icons (#63): a rounded teal square with a white ring + inner dot —
# a compact "verified origin" mark. Placeholder-grade but real; refine in the design pass (#71).
# Requires Pillow. Regenerate: python extension/scripts/gen_icons.py
from PIL import Image, ImageDraw
from pathlib import Path

BG = (13, 94, 92, 255)  # deep teal
RING = (255, 255, 255, 255)
DOT = (120, 220, 200, 255)
OUT = Path(__file__).resolve().parent.parent / "public" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

for size in (16, 32, 48, 128):
    s = size * 4  # supersample for crisp edges, then downscale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=BG)
    m, w = int(s * 0.24), max(2, int(s * 0.09))
    d.ellipse([m, m, s - m, s - m], outline=RING, width=w)
    c = int(s * 0.38)
    d.ellipse([c, c, s - c, s - c], fill=DOT)
    img.resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png")
    print("wrote", f"icon-{size}.png")
