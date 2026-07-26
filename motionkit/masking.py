from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def _pixels_box(box: list[float], size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    return (
        round(box[0] * width),
        round(box[1] * height),
        round(box[2] * width),
        round(box[3] * height),
    )


def _pixels_points(
    points: list[list[float]],
    size: tuple[int, int],
) -> list[tuple[int, int]]:
    width, height = size
    return [(round(point[0] * width), round(point[1] * height)) for point in points]


def _draw_shape(
    shape: dict[str, Any],
    size: tuple[int, int],
) -> Image.Image:
    image = Image.new("L", size, 0)
    draw = ImageDraw.Draw(image)
    kind = shape["shape"]
    fill = round(255 * float(shape.get("opacity", 1.0)))

    if kind == "ellipse":
        draw.ellipse(_pixels_box(shape["box"], size), fill=fill)
    elif kind == "rectangle":
        draw.rectangle(_pixels_box(shape["box"], size), fill=fill)
    elif kind == "rounded_rectangle":
        radius = round(float(shape.get("radius", 0.03)) * min(size))
        draw.rounded_rectangle(_pixels_box(shape["box"], size), radius=radius, fill=fill)
    elif kind == "polygon":
        draw.polygon(_pixels_points(shape["points"], size), fill=fill)
    elif kind == "line":
        line_width = max(1, round(float(shape.get("width", 0.02)) * min(size)))
        draw.line(
            _pixels_points(shape["points"], size),
            fill=fill,
            width=line_width,
            joint="curve",
        )
    else:
        raise ValueError(f"Unknown mask shape: {kind}")

    shape_feather = float(shape.get("feather", 0))
    if shape_feather:
        image = image.filter(ImageFilter.GaussianBlur(shape_feather))
    return image


def prepare_masks(
    scene: dict[str, Any],
    root: Path,
    size: tuple[int, int],
) -> dict[str, Path]:
    """Build named grayscale masks declared by a scene.

    This is intentionally primitive-based: Codex can inspect any generated image
    and describe the useful regions with normalized ellipses, polygons, and lines.
    """
    outputs: dict[str, Path] = {}
    for name, definition in scene.get("masks", {}).items():
        mask = Image.new("L", size, 0)
        for shape in definition.get("shapes", []):
            rendered = _draw_shape(shape, size)
            if shape.get("op", "add") == "subtract":
                mask = ImageChops.subtract(mask, rendered)
            else:
                mask = ImageChops.lighter(mask, rendered)

        feather = float(definition.get("feather", 0))
        if feather:
            mask = mask.filter(ImageFilter.GaussianBlur(feather))

        output = Path(definition.get("output", f"assets/masks/generated/{name}.png"))
        output = output if output.is_absolute() else root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        mask.save(output)
        outputs[name] = output
    return outputs
