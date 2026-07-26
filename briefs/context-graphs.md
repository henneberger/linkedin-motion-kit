# Context graph comparison

## User brief

Compare two context graphs: one without search, and one that uses prediction and classification models.

## Codex image-generation prompt

```text
Use case: infographic-diagram
Asset type: animated LinkedIn comparison graphic base frame, portrait 4:5
Primary request: visually compare two context graphs side by side: the left graph operates without search and forms a weak, sparse, uncertain context; the right graph uses prediction and classification models to create a richer, organized, confident context graph
Scene/backdrop: deep ink-black to midnight-navy matte field with subtle paper grain and a faint architectural grid; a restrained vertical divider between the two systems
Subject: left half contains a small fragmented graph with dim disconnected nodes, broken or wandering filaments, and one muted input source; right half contains a denser but readable graph where an input passes through two distinct model modules—prediction and classification—then fans into a structured context network with stronger connections; make the two model modules clear geometric objects that can be separately masked and animated
Style/medium: sophisticated editorial 3D illustration blended with crisp vector-like information design; frosted glass nodes, anodized metal, soft translucent membranes; consistent with a premium technology design system
Composition/framing: portrait 4:5 comparison layout; left and right systems have equal visual area; safe margins; clean paths that remain easy to trace for later particle animation; preserve negative space around every cluster
Lighting/mood: restrained cinematic glow, intelligent and technical, no science-fiction spectacle
Color palette: midnight navy and charcoal base; left side subdued blue-gray and lilac; right side electric cyan and warm coral with tiny lilac accents
Materials/textures: fine paper grain, frosted glass nodes, subtle bloom, precise luminous filaments
Text (verbatim): "WITHOUT SEARCH" above the left system; "PREDICT + CLASSIFY" above the right system
Constraints: render the two headings exactly once and spell them exactly; no other text, letters, or numbers; no logos or watermark; all important routes and model modules must be visibly separable so local masks and moving particles can be aligned after generation
Avoid: stock crypto art, neon overload, circuit-board cliché, brains, robots, dashboards, illegible UI, floating decorative text, lens flares, excessive tiny particles
```

The image was generated with the built-in Codex image-generation tool. Its actual geometry—not only this prompt—was used to create `presets/context-graphs.json`.
