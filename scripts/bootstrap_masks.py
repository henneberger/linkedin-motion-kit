from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent.parent
SIZE = (540, 675)


def circle_mask(name: str, center: tuple[float, float], radius: float, feather: int) -> None:
    width, height = SIZE
    x, y = center[0] * width, center[1] * height
    r = radius * width
    image = Image.new("L", SIZE, 0)
    draw = ImageDraw.Draw(image)
    draw.ellipse((x - r, y - r, x + r, y + r), fill=255)
    if feather:
        image = image.filter(ImageFilter.GaussianBlur(feather))
    destination = ROOT / "assets" / "masks" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


circle_mask("central-node.png", (0.50, 0.455), 0.115, 7)
circle_mask("satellite-nodes.png", (0.145, 0.425), 0.074, 5)

# Add the other satellites into a single mask layer.
satellites = Image.open(ROOT / "assets/masks/satellite-nodes.png").convert("L")
draw = ImageDraw.Draw(satellites)
for center, radius in [
    ((0.47, 0.05), 0.065),
    ((0.19, 0.18), 0.057),
    ((0.78, 0.17), 0.067),
    ((0.88, 0.48), 0.050),
    ((0.18, 0.74), 0.049),
    ((0.79, 0.79), 0.065),
    ((0.52, 0.91), 0.057),
]:
    x, y = center[0] * SIZE[0], center[1] * SIZE[1]
    r = radius * SIZE[0]
    draw.ellipse((x - r, y - r, x + r, y + r), fill=255)
satellites = satellites.filter(ImageFilter.GaussianBlur(4))
satellites.save(ROOT / "assets/masks/satellite-nodes.png")

print("Created assets/masks/central-node.png and satellite-nodes.png")
