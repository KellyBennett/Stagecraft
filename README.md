# Stagecraft

Turn a photograph into a rough Blender stage with a matched camera. An agent describes the scene with simple shapes. A human aligns perspective guides in a browser. Stagecraft combines the two into a `.blend` file for downstream depth maps and other image or video guidance.

Stagecraft is an early working slice. It solves camera perspective and builds the shapes you supply. It does not recognize objects, recover hidden geometry, or generate imagery.

## How to install it

You need Python 3.10 or newer and Blender installed on your computer.

```sh
git clone https://github.com/KellyBennett/Stagecraft.git
cd Stagecraft
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

## How to use it

Start with a photograph that has straight edges along two perpendicular horizontal directions, such as the sides of a building or room. The camera model assumes a centered optical axis, square pixels, and no lens distortion. Cropped, panoramic, or impossible-perspective images may not match.

Have your agent write a scene description. [The example](examples/scene.json) shows the supported boxes, planes, cylinders, and spheres. Their positions and dimensions are explicit estimates in meters. Stagecraft does not infer those measurements from the photograph.

```sh
stagecraft run photo.jpg --project .stagecraft/room \
  --scene examples/scene.json --output room.blend
```

The browser opens your photograph. Drag each pair of colored guides onto parallel edges in the scene. The orange and cyan directions must be perpendicular to each other. Choose whether the reference plane is below or above the camera. Put the purple origin on that plane and enter the distance to it. Use the overhead option for an upward view of a roof or catwalk. Click **Save camera alignment** to resume the CLI and export the Blender file.

Blender must be on your PATH, or pass its executable with `--blender`. On macOS, a typical path is:

```sh
stagecraft run photo.jpg --project .stagecraft/room \
  --scene examples/scene.json --output room.blend \
  --blender /Applications/Blender.app/Contents/MacOS/Blender
```

Choose a new project directory for each `run`. To adjust an existing project or its shapes, use the separate commands:

```sh
stagecraft align --project .stagecraft/room
stagecraft solve --project .stagecraft/room
stagecraft export --project .stagecraft/room \
  --scene examples/scene.json --output revised.blend
```

The Blender file contains the primitives, matched camera, packed reference photograph, original image resolution, and an enabled depth pass. Open it in Blender to refine the blockout or render guidance with your downstream tools. Geometry is an estimate; matching the camera alone does not reconstruct the scene. Distance to the reference plane supplies scale, and the selected point on that plane supplies the origin. Plane dimensions use X and Y; their Z value is ignored.

For agent integrations, every CLI response is JSON on its own line. `run` emits `needs_human` with a local browser URL, waits up to 15 minutes, then continues when the human saves. Use `--no-open` when your agent will present that URL itself. A timeout or cancellation preserves the project so `align` can resume it. [The agent contract](docs/agent-contract.md) covers scene files, coordinates, and errors.

## How to contribute

Report a failed camera match with a reproducible image and alignment, or open a pull request. Include only images you can share. See [development checks](docs/development.md) for running the tests.
