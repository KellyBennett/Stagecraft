# Stagecraft direction

## Destination

A tested vertical slice from a local image, through human perspective alignment, to a primitive Blender blockout with a matched camera.

## Notes

Direction follows [Matt Pocock's Wayfinder](https://github.com/mattpocock/skills/blob/main/skills/engineering/wayfinder/SKILL.md). The user's explicit build request overrides its planning-only default and session stopping points. No issue tracker configuration exists; this document uses its local Markdown fallback. README prose follows the installed README writer skill.

## Decisions so far

- [Make camera calibration explicit](#make-camera-calibration-explicit): center principal point, two perpendicular horizontal directions, a reference plane, and user distance.
- [Keep geometry under agent control](#keep-geometry-under-agent-control): versioned primitive description instead of fabricated image reconstruction.
- [Keep the human handoff local](#keep-the-human-handoff-local): temporary browser session with JSON CLI events and resumable project files.

## Not yet specified

Future efforts can investigate guided geometry placement in image coordinates, richer perspective models, and a protocol for model-assisted primitive proposals. These are not required to deliver this slice.

## Out of scope

Image generation, automatic reconstruction, fSpy import, and downstream depth rendering services.

## Make camera calibration explicit

Question: What can two vanishing directions establish without inventing scale?

Resolution: Two perpendicular finite vanishing points constrain focal length under centered principal point and square pixels. Their rays establish orientation. A plane origin anchors translation and supplied distance sets scale. The reference plane may be below the camera or overhead, so upward photos can use a visible catwalk. Synthetic projection tests and Blender reprojection checks validate these choices. A plausible photograph alone does not guarantee that two usable perpendicular ground directions are visible.

## Keep geometry under agent control

Question: How can an agent produce a useful blockout in the first slice?

Resolution: Supply boxes, planes, cylinders, and spheres with explicit world transforms in a versioned JSON file. The example is a starting shape arrangement, not a reconstruction of arbitrary input photos. A future vision-assisted proposal system needs separate product and accuracy decisions.

## Keep the human handoff local

Question: How does an agent yield one task to a human and resume?

Resolution: A loopback server emits a session URL, validates the alignment, persists it atomically, and exits after save or timeout. The CLI can resume from the persisted project. No hosted service or account is needed.
