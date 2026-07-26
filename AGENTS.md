# Repository instructions

When a user asks for an animated technology graphic, comparison, system diagram, or LinkedIn visual:

1. Use the bundled `create-tech-motion` skill at `skills/create-tech-motion/SKILL.md`.
2. Use Codex built-in image generation to create the base artwork from the user's brief. Do not require the user to supply a still.
3. Inspect the generated image, derive named mask primitives and motion paths from its actual geometry, and add them to a new scene preset.
4. Render and visually validate the final GIF before finishing.

Do not substitute the included example artwork for a requested concept.
