#!/usr/bin/env python3
"""Convert Lucide SVG icons to crisp 1-bit PNGs for the 2.9" e-paper display.

Usage: python3 convert_icons.py <folder_with_lucide_svgs> [size]
Output: ./icons/<name>.png (mode "1": black icon on white background)
"""
import io, re, sys
from pathlib import Path
import cairosvg
from PIL import Image

ICONS = [
    "sun",              # clear
    "cloud-sun",        # partly cloudy
    "cloud",            # overcast
    "cloud-fog",        # fog
    "cloud-drizzle",    # drizzle
    "cloud-rain",       # rain
    "cloud-sun-rain",   # mostly sunny with showers
    "cloud-snow",       # snow
    "sun-snow",         # mostly sunny with snow showers
    "cloud-lightning",  # thunderstorm
]
STROKE = 2.5   # Lucide default is 2; thicker survives 1-bit conversion
SUPERSAMPLE = 4

def convert(svg_path: Path, out_path: Path, size: int):
    svg = svg_path.read_text()
    svg = re.sub(r'stroke-width="[^"]*"', f'stroke-width="{STROKE}"', svg)
    svg = svg.replace("currentColor", "black")
    big = size * SUPERSAMPLE
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=big,
                           output_height=big, background_color="white")
    img = Image.open(io.BytesIO(png)).convert("L").resize((size, size), Image.LANCZOS)
    img.point(lambda p: 255 if p > 140 else 0).convert("1").save(out_path)

if __name__ == "__main__":
    src = Path(sys.argv[1])
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    out = Path("icons"); out.mkdir(exist_ok=True)
    for name in ICONS:
        convert(src / f"{name}.svg", out / f"{name}.png", size)
        print("ok", name)
