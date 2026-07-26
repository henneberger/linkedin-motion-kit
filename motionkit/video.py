from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .renderer import _flow_layer, _orbit_layer, _path_trace_layer, _ripple_layer


Color = tuple[int, int, int]


def _hex(value: str) -> Color:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _clamp(value: float) -> float:
    return max(0.0, min(value, 1.0))


def _ease_out_cubic(value: float) -> float:
    value = _clamp(value)
    return 1 - (1 - value) ** 3


def _ease_in_out(value: float) -> float:
    value = _clamp(value)
    return 4 * value**3 if value < 0.5 else 1 - ((-2 * value + 2) ** 3) / 2


def _ease_out_back(value: float) -> float:
    value = _clamp(value)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (value - 1) ** 3 + c1 * (value - 1) ** 2


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> str:
    output: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            output.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if draw.textlength(candidate, font=font) <= max_width:
                line = candidate
            else:
                output.append(line)
                line = word
        output.append(line)
    return "\n".join(output)


def _multiply_alpha(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return image
    result = image.copy()
    alpha = result.getchannel("A").point(lambda value: round(value * opacity))
    result.putalpha(alpha)
    return result


def _background_frame(
    source: Image.Image,
    slide: dict[str, Any],
    progress: float,
    size: tuple[int, int],
) -> Image.Image:
    config = slide.get("background", {})
    width, height = size
    zoom_from, zoom_to = config.get("zoom", [1.0, 1.025])
    zoom = zoom_from + (zoom_to - zoom_from) * _ease_in_out(progress)
    cover_scale = max(width / source.width, height / source.height) * zoom
    scaled = source.resize(
        (round(source.width * cover_scale), round(source.height * cover_scale)),
        Image.Resampling.LANCZOS,
    )

    focus_from = config.get("focus_from", [0.5, 0.5])
    focus_to = config.get("focus_to", focus_from)
    focus_x = focus_from[0] + (focus_to[0] - focus_from[0]) * _ease_in_out(progress)
    focus_y = focus_from[1] + (focus_to[1] - focus_from[1]) * _ease_in_out(progress)
    max_left = max(0, scaled.width - width)
    max_top = max(0, scaled.height - height)
    left = round(max_left * focus_x)
    top = round(max_top * focus_y)
    frame = scaled.crop((left, top, left + width, top + height)).convert("RGBA")

    blur = float(config.get("blur", 0))
    if blur:
        frame = frame.filter(ImageFilter.GaussianBlur(blur))

    tint = _hex(config.get("tint", "#020711"))
    dim = float(config.get("dim", 0.36))
    overlay = Image.new("RGBA", size, (*tint, round(255 * dim)))
    return Image.alpha_composite(frame, overlay)


def _enter_state(
    element: dict[str, Any],
    local_time: float,
    size: tuple[int, int],
) -> tuple[float, float, float, float]:
    delay = float(element.get("delay", 0.0))
    duration = max(0.01, float(element.get("enter_duration", 0.65)))
    raw = _clamp((local_time - delay) / duration)
    easing = element.get("easing", "cubic")
    progress = _ease_out_back(raw) if easing == "back" else _ease_out_cubic(raw)
    opacity = _clamp(raw / 0.62)
    enter = element.get("enter", "fade")
    width, height = size
    offset_x = 0.0
    offset_y = 0.0
    scale = 1.0
    distance = float(element.get("distance", 0.065))

    if enter == "slide_left":
        offset_x = -(1 - progress) * width * distance
    elif enter == "slide_right":
        offset_x = (1 - progress) * width * distance
    elif enter == "slide_up":
        offset_y = (1 - progress) * height * distance
    elif enter == "slide_down":
        offset_y = -(1 - progress) * height * distance
    elif enter == "scale":
        scale = 0.88 + 0.12 * progress
    elif enter not in {"fade", "none"}:
        raise ValueError(f"Unknown enter animation: {enter}")

    if enter == "none":
        opacity = 1.0

    jitter = element.get("jitter")
    if jitter:
        start = float(jitter.get("start", delay + duration))
        jitter_duration = max(0.01, float(jitter.get("duration", 0.45)))
        jitter_t = (local_time - start) / jitter_duration
        if 0 <= jitter_t <= 1:
            amplitude = float(jitter.get("amplitude", 7.0)) * (1 - jitter_t) ** 1.6
            frequency = float(jitter.get("frequency", 24.0))
            offset_x += math.sin(local_time * frequency * 1.31) * amplitude
            offset_y += math.sin(local_time * frequency * 1.87 + 0.8) * amplitude * 0.58

    return opacity, offset_x, offset_y, scale


def _paste_text(
    frame: Image.Image,
    element: dict[str, Any],
    local_time: float,
    fonts: dict[str, Path],
    size: tuple[int, int],
) -> None:
    width, height = size
    font_size = round(float(element.get("size", 64)) * height / 1080)
    selected_font = _font(fonts[element.get("font", "bold")], font_size)
    max_width = round(float(element.get("max_width", 0.8)) * width)
    scratch = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    scratch_draw = ImageDraw.Draw(scratch)
    content = _wrap_text(element["text"], selected_font, max_width, scratch_draw)
    spacing = round(float(element.get("spacing", 0.18)) * font_size)
    bbox = scratch_draw.multiline_textbbox(
        (0, 0),
        content,
        font=selected_font,
        spacing=spacing,
        align=element.get("text_align", "left"),
        stroke_width=int(element.get("stroke_width", 0)),
    )
    text_width = max(1, bbox[2] - bbox[0])
    text_height = max(1, bbox[3] - bbox[1])
    padding = max(12, round(font_size * 0.18))
    layer = Image.new(
        "RGBA",
        (text_width + padding * 2, text_height + padding * 2),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(layer)
    color = _hex(element.get("color", "#eef8ff"))
    draw.multiline_text(
        (padding - bbox[0], padding - bbox[1]),
        content,
        font=selected_font,
        fill=(*color, 255),
        spacing=spacing,
        align=element.get("text_align", "left"),
        stroke_width=int(element.get("stroke_width", 0)),
        stroke_fill=(*_hex(element.get("stroke_color", "#07101f")), 255),
    )

    opacity, offset_x, offset_y, scale = _enter_state(element, local_time, size)
    if scale != 1:
        layer = layer.resize(
            (max(1, round(layer.width * scale)), max(1, round(layer.height * scale))),
            Image.Resampling.LANCZOS,
        )
    layer = _multiply_alpha(layer, opacity * float(element.get("opacity", 1.0)))

    x = round(float(element.get("x", 0.1)) * width + offset_x)
    y = round(float(element.get("y", 0.1)) * height + offset_y)
    anchor = element.get("anchor", "left")
    if anchor == "center":
        x -= layer.width // 2
    elif anchor == "right":
        x -= layer.width
    frame.alpha_composite(layer, (x, y))


def _draw_panel(
    frame: Image.Image,
    element: dict[str, Any],
    local_time: float,
    size: tuple[int, int],
) -> None:
    width, height = size
    opacity, offset_x, offset_y, _ = _enter_state(element, local_time, size)
    x = round(float(element["x"]) * width + offset_x)
    y = round(float(element["y"]) * height + offset_y)
    panel_width = round(float(element["width"]) * width)
    panel_height = round(float(element["height"]) * height)
    radius = round(float(element.get("radius", 0.02)) * min(size))
    color = _hex(element.get("color", "#0b1728"))
    alpha = round(255 * float(element.get("opacity", 0.78)) * opacity)
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (x, y, x + panel_width, y + panel_height),
        radius=radius,
        fill=(*color, alpha),
        outline=(*_hex(element.get("outline", "#263c59")), round(alpha * 0.75)),
        width=max(1, round(float(element.get("outline_width", 1.0)) * height / 1080)),
    )
    frame.alpha_composite(overlay)


def _draw_rule(
    frame: Image.Image,
    element: dict[str, Any],
    local_time: float,
    size: tuple[int, int],
) -> None:
    width, height = size
    opacity, offset_x, offset_y, _ = _enter_state(element, local_time, size)
    progress = _ease_out_cubic(
        (local_time - float(element.get("delay", 0.0)))
        / max(0.01, float(element.get("enter_duration", 0.65)))
    )
    x = round(float(element["x"]) * width + offset_x)
    y = round(float(element["y"]) * height + offset_y)
    rule_width = round(float(element["width"]) * width * progress)
    thickness = max(1, round(float(element.get("thickness", 4)) * height / 1080))
    color = _hex(element.get("color", "#56e4ff"))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (x, y, x + rule_width, y + thickness),
        radius=thickness // 2,
        fill=(*color, round(255 * opacity)),
    )
    frame.alpha_composite(overlay)


def _render_slide(
    source: Image.Image,
    slide: dict[str, Any],
    local_time: float,
    motion_time: float,
    motion_layers: list[dict[str, Any]],
    fonts: dict[str, Path],
    size: tuple[int, int],
) -> Image.Image:
    duration = float(slide["duration"])
    progress = _clamp(local_time / max(duration, 0.01))
    frame = _background_frame(source, slide, progress, size)
    for layer in motion_layers:
        kind = layer["type"]
        if kind == "flow_path":
            frame = _flow_layer(frame, layer, motion_time, size)
        elif kind == "path_trace":
            frame = _path_trace_layer(frame, layer, motion_time, size)
        elif kind == "ripple":
            frame = _ripple_layer(frame, layer, motion_time, size)
        elif kind == "orbit":
            frame = _orbit_layer(frame, layer, motion_time, size)
        else:
            raise ValueError(f"Unknown video background motion layer: {kind}")
    for element in slide.get("elements", []):
        kind = element["type"]
        if kind == "panel":
            _draw_panel(frame, element, local_time, size)
        elif kind == "text":
            _paste_text(frame, element, local_time, fonts, size)
        elif kind == "rule":
            _draw_rule(frame, element, local_time, size)
        else:
            raise ValueError(f"Unknown slideshow element: {kind}")
    return frame


def _transition(
    previous: Image.Image,
    current: Image.Image,
    progress: float,
    kind: str,
) -> Image.Image:
    progress = _ease_in_out(progress)
    width, height = current.size
    if kind == "fade":
        return Image.blend(previous, current, progress)
    if kind == "push_left":
        result = Image.new("RGBA", current.size, (4, 9, 18, 255))
        result.alpha_composite(previous, (-round(progress * width), 0))
        result.alpha_composite(current, (round((1 - progress) * width), 0))
        return result
    if kind == "split_fade":
        result = previous.copy()
        half = width // 2
        left = current.crop((0, 0, half, height))
        right = current.crop((half, 0, width, height))
        left = _multiply_alpha(left, progress)
        right = _multiply_alpha(right, progress)
        result.alpha_composite(left, (-round((1 - progress) * half), 0))
        result.alpha_composite(right, (half + round((1 - progress) * half), 0))
        return result
    if kind == "wipe":
        result = previous.copy()
        edge = round(progress * width)
        feather = max(8, width // 80)
        mask = Image.new("L", current.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle((0, 0, edge, height), fill=255)
        if 0 < edge < width:
            gradient = Image.new("L", (feather, 1))
            gradient.putdata([round(255 * index / max(1, feather - 1)) for index in range(feather)])
            gradient = gradient.resize((feather, height))
            mask.paste(gradient, (max(0, edge - feather), 0))
        result.paste(current, (0, 0), mask)
        return result
    raise ValueError(f"Unknown slide transition: {kind}")


def render_video(deck: dict[str, Any], root: Path, output: Path) -> dict[str, Any]:
    canvas = deck.get("canvas", {})
    width = int(canvas.get("width", 1920))
    height = int(canvas.get("height", 1080))
    fps = int(canvas.get("fps", 24))
    if width % 2 or height % 2:
        raise ValueError(
            "H.264 yuv420p output requires even canvas width and height"
        )
    size = (width, height)
    source = Image.open(root / deck["background"]).convert("RGB")
    fonts = {
        "regular": Path(deck["fonts"]["regular"]),
        "bold": Path(deck["fonts"]["bold"]),
        "mono": Path(deck["fonts"].get("mono", deck["fonts"]["regular"])),
    }
    slides = deck["slides"]
    motion_layers = deck.get("motion_layers", [])
    total_duration = sum(float(slide["duration"]) for slide in slides)
    total_frames = round(total_duration * fps)
    boundaries: list[float] = []
    running = 0.0
    for slide in slides:
        running += float(slide["duration"])
        boundaries.append(running)

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        canvas.get("preset", "medium"),
        "-crf",
        str(canvas.get("crf", 19)),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None

    thumbnail_time = float(deck.get("thumbnail_time", 1.5))
    thumbnail_path = root / deck.get(
        "thumbnail",
        f"output/{output.stem}-thumbnail.png",
    )
    thumbnail_written = False

    for frame_index in range(total_frames):
        time = frame_index / fps
        slide_index = next(
            (index for index, boundary in enumerate(boundaries) if time < boundary),
            len(slides) - 1,
        )
        slide_start = 0.0 if slide_index == 0 else boundaries[slide_index - 1]
        local_time = time - slide_start
        slide = slides[slide_index]
        current = _render_slide(
            source,
            slide,
            local_time,
            time,
            motion_layers,
            fonts,
            size,
        )

        transition_config = slide.get("transition", {})
        transition_duration = float(transition_config.get("duration", 0.0))
        if slide_index > 0 and transition_duration > 0 and local_time < transition_duration:
            previous_slide = slides[slide_index - 1]
            previous = _render_slide(
                source,
                previous_slide,
                float(previous_slide["duration"]),
                time,
                motion_layers,
                fonts,
                size,
            )
            current = _transition(
                previous,
                current,
                local_time / transition_duration,
                transition_config.get("type", "fade"),
            )

        rgb = current.convert("RGB")
        if not thumbnail_written and time >= thumbnail_time:
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
            rgb.save(thumbnail_path)
            thumbnail_written = True
        process.stdin.write(rgb.tobytes())

    process.stdin.close()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {return_code}")
    return {
        "frames": total_frames,
        "duration": total_duration,
        "width": width,
        "height": height,
        "fps": fps,
        "thumbnail": str(thumbnail_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="motionkit-video",
        description="Render a kinetic typography slideshow to LinkedIn-compatible MP4.",
    )
    parser.add_argument("deck", type=Path, help="Path to a video deck JSON file")
    parser.add_argument("-o", "--output", type=Path, help="Override output MP4 path")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Render at 960x540 and 12 fps for fast layout review",
    )
    args = parser.parse_args()

    deck_path = args.deck.resolve()
    with deck_path.open() as handle:
        deck = json.load(handle)
    if args.preview:
        deck["canvas"].update(
            {
                "width": 960,
                "height": 540,
                "fps": 12,
                "crf": 24,
                "preset": "ultrafast",
            }
        )
        deck["thumbnail"] = "output/context-graph-story-preview-thumbnail.png"
    root = deck_path.parent.parent
    output = (args.output or root / deck.get("output", "output/slideshow.mp4")).resolve()
    result = render_video(deck, root, output)
    print(
        f"Rendered {result['frames']} frames at {result['width']}x{result['height']} "
        f"and {result['fps']} fps to {output}"
    )
    print(f"Thumbnail: {result['thumbnail']}")


if __name__ == "__main__":
    main()
