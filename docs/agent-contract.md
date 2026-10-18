# Agent contract, version 1

Stagecraft is local. An agent provides geometry; the human provides the perspective alignment. No model API or image generation service is called.

## Projects and storage

Read the configured `project_root` from `~/Library/Application Support/ComfyGateway/settings.json` with `schema_version: 1`. Every command also accepts `--root ROOT` or `--config FILE`, which are mutually exclusive. The resource root must exist. Projects are directories under `projects/`, as in ComfyLoom; there is no additional registry.

Select a project explicitly by name. Creation is a separate command and never replaces an existing project. Scene names identify one working copy within that project. Managed paths are:

```text
<root>/projects/<project>/
  blender/<scene>.blend
  blender/assets/<scene>/image.png
  blender/assets/<scene>/project.json
  blender/assets/<scene>/scene.json
  outputs/<scene>-depth.png
```

The depth path is a destination for downstream rendering, not a depth-render command. Stagecraft does not move old files or generate renders. Project and scene names must be single safe path components; managed paths reject symlinks. No CLI output override can bypass this layout.

Initialization requires a fresh scene name and copies the normalized image and validated primitive description into its assets folder. `project.json` holds saved controls and Stagecraft ownership metadata. Export replaces its own unchanged output, but rejects an existing unowned or externally modified Blender file. The candidate is built privately and the destination is checked again immediately before publication. A first export uses atomic no-clobber publication. Replacing an existing file still has a small check/replace race with external writers that do not share the scene lock; do not manually save to that destination during export. Unrelated project resources remain untouched. There are no archived runs, snapshots or numbered scene copies.

## Commands and results

- `projects`: list existing project names and the resource root.
- `create-project --project NAME`: create a project explicitly.
- `init IMAGE --project NAME --scene NAME --primitives FILE`: initialize a scene in an existing project.
- `align --project NAME --scene NAME [--no-open] [--timeout SECONDS]`: open a loopback alignment session. Save persists the controls and leaves the session usable. Finish closes the session. The default timeout is 900 seconds. Keep the session URL private.
- `status --project NAME --scene NAME`: report alignment presence, active project, scene and resolved paths.
- `solve --project NAME --scene NAME`: solve from the latest saved controls.
- `export --project NAME --scene NAME [--blender EXECUTABLE]`: reload saved controls and managed primitives, then replace the owned scene at its fixed path.
- `run IMAGE --project NAME --scene NAME --primitives FILE`: initialize, align, and export after Finish. It accepts the alignment and export options above.

The agent can export separately while the alignment page stays open. Unsaved browser edits are not exported. Save atomically replaces the current controls; subsequent exports read the latest completed save. To change geometry, edit the scene's managed `scene.json` rather than creating another scene copy.

Stdout is newline-delimited JSON. Results identify the active project and scene where applicable. `needs_human` includes the local URL. Exit 0 means success; exit 1 means a JSON error; Ctrl-C returns 130 and `cancelled`. Argument parsing errors use argparse's stderr and exit 2. Blender output is captured in export errors. Timeout and cancellation preserve saved controls so `align` can resume them.

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
