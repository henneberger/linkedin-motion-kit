from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from .masking import prepare_masks


Color = tuple[int, int, int]


def _hex(value: str) -> Color:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    scaled = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (scaled.width - target_w) // 2
    top = (scaled.height - target_h) // 2
    return scaled.crop((left, top, left + target_w, top + target_h))


def _contain(
    image: Image.Image,
    size: tuple[int, int],
    background: Color,
) -> Image.Image:
    target_w, target_h = size
    scale = min(target_w / image.width, target_h / image.height)
    scaled = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    result = Image.new("RGB", size, background)
    result.paste(
        scaled,
        ((target_w - scaled.width) // 2, (target_h - scaled.height) // 2),
    )
    return result


def _load_mask(root: Path, source: str, size: tuple[int, int]) -> Image.Image:
    mask = Image.open(_resolve(root, source)).convert("L")
    if mask.size != size:
        mask = mask.resize(size, Image.Resampling.LANCZOS)
    return mask


def _phase(t: float, speed: float = 1.0, offset: float = 0.0) -> float:
    return (t * speed + offset) % 1.0


def _pulse(t: float, speed: float = 1.0, offset: float = 0.0) -> float:
    return 0.5 + 0.5 * math.sin(math.tau * _phase(t, speed, offset))


def _composite_color(
    frame: Image.Image,
    mask: Image.Image,
    color: Color,
    opacity: float,
) -> Image.Image:
    alpha = mask.point(lambda p: round(p * max(0.0, min(opacity, 1.0))))
    overlay = Image.new("RGBA", frame.size, (*color, 0))
    overlay.putalpha(alpha)
    return Image.alpha_composite(frame, overlay)


def _glow(
    frame: Image.Image,
    mask: Image.Image,
    color: Color,
    amount: float,
    blur: float,
) -> Image.Image:
    halo = mask.filter(ImageFilter.GaussianBlur(blur))
    frame = _composite_color(frame, halo, color, 0.32 * amount)
    return _composite_color(frame, mask, color, 0.12 * amount)


def _bezier(points: list[list[float]], u: float) -> tuple[float, float]:
    if len(points) == 2:
        a, b = points
        return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
    if len(points) == 3:
        a, b, c = points
        v = 1 - u
        return (
            v * v * a[0] + 2 * v * u * b[0] + u * u * c[0],
            v * v * a[1] + 2 * v * u * b[1] + u * u * c[1],
        )
    if len(points) == 4:
        a, b, c, d = points
        v = 1 - u
        return (
            v**3 * a[0] + 3 * v * v * u * b[0] + 3 * v * u * u * c[0] + u**3 * d[0],
            v**3 * a[1] + 3 * v * v * u * b[1] + 3 * v * u * u * c[1] + u**3 * d[1],
        )
    raise ValueError("A flow path needs 2, 3, or 4 normalized points")


def _flow_layer(
    frame: Image.Image,
    layer: dict[str, Any],
    t: float,
    size: tuple[int, int],
) -> Image.Image:
    width, height = size
    color = _hex(layer.get("color", "#55ddff"))
    particles = int(layer.get("particles", 3))
    speed = float(layer.get("speed", 1.0))
    offset = float(layer.get("offset", 0.0))
    radius = float(layer.get("radius", 3.4))
    points = layer["points"]

    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    core = Image.new("RGBA", size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    core_draw = ImageDraw.Draw(core)

    for index in range(particles):
        u = _phase(t, speed, offset + index / particles)
        x, y = _bezier(points, u)
        x *= width
        y *= height
        fade = math.sin(math.pi * u) ** 0.45
        r = radius * (0.78 + 0.22 * fade)
        glow_draw.ellipse(
            (x - r * 4, y - r * 4, x + r * 4, y + r * 4),
            fill=(*color, round(150 * fade)),
        )
        core_draw.ellipse(
            (x - r, y - r, x + r, y + r),
            fill=(245, 252, 255, round(245 * fade)),
        )

        trail_steps = 7
        for step in range(1, trail_steps + 1):
            trail_u = max(0.0, u - step * 0.012)
            tx, ty = _bezier(points, trail_u)
            tr = r * (1 - step / (trail_steps + 1))
            core_draw.ellipse(
                (
                    tx * width - tr,
                    ty * height - tr,
                    tx * width + tr,
                    ty * height + tr,
                ),
                fill=(*color, round(95 * fade * (1 - step / trail_steps))),
            )

    glow = glow.filter(ImageFilter.GaussianBlur(radius * 2.4))
    return Image.alpha_composite(Image.alpha_composite(frame, glow), core)


def _sheen_layer(
    frame: Image.Image,
    mask: Image.Image,
    layer: dict[str, Any],
    t: float,
) -> Image.Image:
    width, height = frame.size
    color = _hex(layer.get("color", "#ffffff"))
    band = max(12, int(width * float(layer.get("width", 0.11))))
    position = int(
        (-band * 2)
        + _phase(
            t,
            float(layer.get("speed", 0.7)),
            float(layer.get("offset", 0.0)),
        )
        * (width + band * 4)
    )
    sweep = Image.new("L", frame.size, 0)
    draw = ImageDraw.Draw(sweep)
    draw.polygon(
        [
            (position - band, 0),
            (position + band, 0),
            (position + band - height // 3, height),
            (position - band - height // 3, height),
        ],
        fill=210,
    )
    sweep = sweep.filter(ImageFilter.GaussianBlur(band * 0.55))
    clipped = ImageChops.multiply(sweep, mask)
    return _composite_color(frame, clipped, color, float(layer.get("opacity", 0.18)))


def _orbit_layer(
    frame: Image.Image,
    layer: dict[str, Any],
    t: float,
    size: tuple[int, int],
) -> Image.Image:
    width, height = size
    cx, cy = layer["center"]
    rx, ry = layer.get("radius", [0.09, 0.07])
    color = _hex(layer.get("color", "#c9a3ff"))
    count = int(layer.get("particles", 2))
    speed = float(layer.get("speed", 0.5))
    dot_radius = float(layer.get("dot_radius", 2.3))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    glow_draw = ImageDraw.Draw(glow)
    for index in range(count):
        angle = math.tau * (_phase(t, speed, index / count))
        x = (cx + math.cos(angle) * rx) * width
        y = (cy + math.sin(angle) * ry) * height
        glow_draw.ellipse(
            (x - dot_radius * 4, y - dot_radius * 4, x + dot_radius * 4, y + dot_radius * 4),
            fill=(*color, 135),
        )
        draw.ellipse(
            (x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius),
            fill=(252, 250, 255, 235),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(dot_radius * 2))
    return Image.alpha_composite(Image.alpha_composite(frame, glow), overlay)


def _animate_frame(
    base: Image.Image,
    scene: dict[str, Any],
    root: Path,
    t: float,
    masks: dict[str, Image.Image],
) -> Image.Image:
    frame = base.copy().convert("RGBA")
    size = frame.size
    for layer in scene.get("layers", []):
        if not layer.get("enabled", True):
            continue
        kind = layer["type"]
        if kind == "masked_glow":
            mask = masks[layer["mask"]]
            amount = 0.35 + 0.65 * _pulse(
                t,
                float(layer.get("speed", 1.0)),
                float(layer.get("offset", 0.0)),
            )
            frame = _glow(
                frame,
                mask,
                _hex(layer.get("color", "#55ddff")),
                amount * float(layer.get("opacity", 1.0)),
                float(layer.get("blur", 22)),
            )
        elif kind == "masked_sheen":
            frame = _sheen_layer(frame, masks[layer["mask"]], layer, t)
        elif kind == "flow_path":
            frame = _flow_layer(frame, layer, t, size)
        elif kind == "orbit":
            frame = _orbit_layer(frame, layer, t, size)
        else:
            raise ValueError(f"Unknown layer type: {kind}")

    if scene.get("finishing", {}).get("breathe", True):
        amount = 0.985 + 0.025 * _pulse(t, 0.5)
        frame = ImageEnhance.Brightness(frame).enhance(amount)

    return frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)


def render_gif(
    scene: dict[str, Any],
    root: Path,
    output: Path,
    preview: bool = False,
) -> dict[str, int]:
    canvas = scene.get("canvas", {})
    width = int(canvas.get("width", 540))
    height = int(canvas.get("height", 675))
    fps = int(canvas.get("fps", 16))
    duration = float(canvas.get("duration", 3.0))
    frame_count = max(2, round(fps * duration))
    if preview:
        width //= 2
        height //= 2
        frame_count = 12

    size = (width, height)
    source = Image.open(_resolve(root, scene["base"])).convert("RGB")
    fit = canvas.get("fit", "cover")
    if fit == "contain":
        base = _contain(source, size, _hex(canvas.get("background", "#07101f")))
    elif fit == "cover":
        base = _cover(source, size)
    else:
        raise ValueError("canvas.fit must be 'cover' or 'contain'")

    generated_masks = prepare_masks(scene, root, size)
    masks: dict[str, Image.Image] = {}
    for layer in scene.get("layers", []):
        if "mask" in layer and layer["mask"] not in masks:
            mask_reference = layer["mask"]
            source_path = generated_masks.get(mask_reference, mask_reference)
            masks[mask_reference] = _load_mask(root, str(source_path), size)

    frames = [
        _animate_frame(base, scene, root, index / frame_count, masks)
        for index in range(frame_count)
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    # GIF timing is stored in centiseconds. Distribute the remainder so the
    # complete loop keeps the requested duration instead of drifting.
    total_centiseconds = round(duration * 100)
    base_centiseconds, remainder = divmod(total_centiseconds, frame_count)
    frame_durations = []
    for index in range(frame_count):
        gets_extra_tick = (
            ((index + 1) * remainder) // frame_count
            > (index * remainder) // frame_count
        )
        frame_durations.append((base_centiseconds + int(gets_extra_tick)) * 10)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=frame_durations,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return {"frames": frame_count, "width": width, "height": height}
