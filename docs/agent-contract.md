# Agent contract, version 1

Stagecraft is local. An agent provides geometry; the human provides the perspective alignment. No model API or image generation service is called.

## Commands and results

- `init IMAGE --project DIR`: create a new directory, normalize EXIF orientation into `image.png`, write `project.json`.
- `align --project DIR [--no-open] [--timeout SECONDS]`: serve the human UI on an ephemeral loopback port. Emit `needs_human` with a capability URL, then `aligned` after a valid save. Default timeout is 900 seconds. The server closes after saving or timeout. Keep the capability URL private.
- `status --project DIR`: report `needs_human` or `aligned` (alignment present; use `solve` to validate edits).
- `solve --project DIR`: emit `solved` with the camera solution.
- `export --project DIR --scene FILE --output FILE.blend [--blender EXECUTABLE] [--force]`: solve and validate, invoke background Blender, atomically publish the output. Existing files are rejected unless `--force` is set.
- `run IMAGE --project DIR --scene FILE --output FILE.blend`: compose init, align, export; accepts the alignment and export flags above.

Stdout is newline-delimited JSON. Exit 0 means success; exit 1 means error (`status: error`, `error` message); Ctrl-C returns 130 and `cancelled`. Argument parsing errors use argparse's stderr and exit 2. Paths are resolved locally. Blender output is captured and included in export errors, not mixed with JSON stdout. A fresh project directory is required for `init` and `run`. No alignment, source image, or scene file is overwritten by export.

## Scene JSON

Top-level `version: 1` and `objects: [...]` are required. Between 1 and 1000 primitives are accepted. Each needs:

| Field | Meaning |
| --- | --- |
| `name` | Nonempty, unique string |
| `type` | `box`, `plane`, `cylinder`, or `sphere` |
| `location` | Three finite numbers, center in world meters |
| `dimensions` | Three positive finite numbers, local size before rotation |
| `rotation_degrees` | Optional XYZ Euler angles, defaults to `[0,0,0]` |

World Z points up. X follows the orange horizontal direction; Y is perpendicular and chosen to preserve an upright right-handed frame. Axis signs are ambiguous from parallel lines alone. Inspect the solved camera when authoring placements. Planes lie in local XY; Z dimension has no effect. Cylinders use 12 sides; spheres use 12 segments and 6 rings. Names may be adjusted by Blender if they collide with the camera name.

## Alignment and camera

`project.json` stores version, image dimensions, and an `alignment` object after saving. Image dimensions are read from `image.png` for solving. Alignment uses original normalized image pixels, x right and y down:

```json
{
  "x": [[[40, 400], [250, 300]], [[90, 500], [300, 350]]],
  "y": [[[550, 300], [760, 400]], [[500, 350], [710, 500]]],
  "origin": [400, 500],
  "camera_height": 1.6,
  "reference_plane": "ground"
}
```

Each axis has two segments. Their intersection is its vanishing point; off-image vanishing points are supported. Segments need at least two pixels of length. Nearly parallel pairs, nonpositive focal length, and origins on the wrong side of the horizon are rejected. These checks catch mathematical failures, not all mistaken human alignments.

The principal point is fixed at the image center. Orthogonal vanishing points constrain `f² = -(vx-c)·(vy-c)`. Camera coordinates use x right, y up, forward -z. `rotation` maps camera vectors to world vectors. `location` places the camera at the supplied distance from the reference plane while projecting world origin to the selected image pixel. Lens millimeters are reported against a 36 mm horizontal sensor. Blender uses horizontal sensor fit and square pixels.

The optional `reference_plane` is `ground` by default, placing the camera above Z=0. Set it to `overhead` to place the camera below Z=0 for an upward view. `camera_height` remains a positive distance in both modes. The origin must be below the horizon for ground mode and above it for overhead mode.

Stagecraft supports finite two-point perspective of perpendicular horizontal axes. One-point perspective, unknown principal point, lens correction, nonorthogonal axes, automatic segmentation, geometry fitting, occlusion recovery, and fSpy project import are outside this slice. No claim of fSpy feature parity is made.
