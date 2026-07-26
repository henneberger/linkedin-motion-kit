from __future__ import annotations

import argparse
import json
from pathlib import Path

from .renderer import render_gif


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="motionkit",
        description="Render a layered animated GIF from a generated still.",
    )
    parser.add_argument("scene", type=Path, help="Path to a scene JSON file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output GIF path (overrides scene output)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Render 12 low-resolution frames for a quick iteration",
    )
    args = parser.parse_args()

    scene_path = args.scene.resolve()
    with scene_path.open() as handle:
        scene = json.load(handle)

    project_root = scene_path.parent.parent
    output = args.output or project_root / scene.get("output", "output/render.gif")
    output = output.resolve()
    result = render_gif(scene, project_root, output, preview=args.preview)
    print(
        f"Rendered {result['frames']} frames at {result['width']}x{result['height']} "
        f"to {output}"
    )
