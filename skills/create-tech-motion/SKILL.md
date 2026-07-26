---
name: create-tech-motion
description: Turn a plain-English technology concept into a complete animated GIF by using Codex image generation for original artwork, inspecting the generated image, deriving masks and motion paths from its actual geometry, and rendering the result with LinkedIn Motion Kit. Use for animated tech comparisons, context graphs, AI or data flows, architecture diagrams, cloud/security/developer-tool visuals, and LinkedIn graphics when the user expects generation through final animation rather than a supplied still.
---

# Create Tech Motion

Create the artwork and the animation. Never stop after writing a prompt, generating a still, or explaining how the user could mask it.

## Workflow

1. Locate the LinkedIn Motion Kit project root. Require `motionkit/`, `presets/`, and `PROMPTS.md`.
2. Convert the user's brief into a production prompt using the Midnight Signal style block in `PROMPTS.md`.
3. Use the built-in Codex `image_gen` tool to generate a new base still. Do not ask the user to supply the still.
4. Copy the selected generated image into `assets/source/<slug>/base.png`. Keep the original generated file.
5. Inspect the project copy with `view_image`. Record the actual positions of subjects, routes, nodes, and modules; do not assume the prompt's intended geometry matches the output.
6. Create `presets/<slug>.json` from the actual image:
   - Set a canvas that preserves the artwork. Prefer `540x675` for 4:5; use `fit: contain` or a source-matched height when cover-cropping would remove headings or subjects.
   - Declare named `masks` using normalized ellipse, rectangle, rounded rectangle, polygon, or line primitives.
   - Reference those names from `masked_glow` and `masked_sheen` layers.
   - Add `flow_path` layers that trace visible connections. Use 2 points for a line, 3 for a quadratic curve, or 4 for a cubic curve.
   - Use `path_trace` for progressive relationship reveals, `scan_line` for search or inspection, `ripple` for decisions/confidence, and `masked_particles` for activity inside a bounded graph.
   - Use subdued motion on the weak/negative side of comparisons and clearer staged motion on the strong/positive side.
7. Run `.venv/bin/python -m motionkit presets/<slug>.json`. The renderer must generate declared mask PNGs automatically before rendering.
8. Build a six-frame contact sheet with ImageMagick and inspect it with `view_image`.
9. Adjust masks and paths when effects do not align with the generated geometry, then rerender.
10. Save the final GIF at `output/<slug>.gif` and report the still, preset, masks, GIF, and exact generation prompt.

## Scene mask schema

Use normalized coordinates where `[0, 0]` is top-left and `[1, 1]` is bottom-right:

```json
{
  "masks": {
    "model-core": {
      "output": "assets/masks/example/model-core.png",
      "feather": 5,
      "shapes": [
        {"shape": "ellipse", "box": [0.35, 0.3, 0.65, 0.62]},
        {"shape": "polygon", "points": [[0.4, 0.3], [0.7, 0.5], [0.4, 0.7]]},
        {"shape": "line", "points": [[0.2, 0.5], [0.8, 0.5]], "width": 0.02}
      ]
    }
  }
}
```

Use `op: "subtract"` on a shape to cut it out of prior shapes. Use `opacity` for partial influence.

## Motion direction

- Use one primary visual idea per loop.
- Animate semantic relationships: ingress, transformation, classification, branching, retrieval, or rejection.
- Keep headings and explanatory text static.
- Use no more than 2–3 particles on one path unless density is the concept.
- Offset pulses so stages read in sequence.
- Keep the loop between 3 and 5 seconds.

## Required validation

Verify:

- the GIF opens, loops, and has the requested duration;
- every effect aligns with the generated image rather than an imagined layout;
- comparison sides remain legible in at least six sampled frames;
- masks were generated into the project and are not only temporary files;
- the output still communicates the user's specific concept without relying on the README.

If built-in image generation is unavailable, stop and report that constraint. Do not silently replace it with stock art, deterministic SVG, or an API runner.
