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

Stagecraft uses your ComfyLoom resource folder from `~/Library/Application Support/ComfyGateway/settings.json`. List its projects, then choose one by name. If you need a new project, create it explicitly:

```sh
stagecraft projects
stagecraft create-project --project short-film
```

Without ComfyLoom settings, pass `--root /path/to/your/assets` to each command. The resource folder must already exist. Stagecraft keeps scenes under the selected project's `blender/` folder and their working images and settings under `blender/assets/<scene>/`.

Have your agent write a primitive scene description. [The example](examples/scene.json) shows boxes, planes, cylinders, and spheres with estimated sizes and positions in meters. Replace `photo.jpg` with your photograph and `short-film` with your chosen project:

```sh
stagecraft run photo.jpg --project short-film --scene room \
  --primitives examples/scene.json
```

The browser shows the active project and scene. Drag each pair of colored guides onto parallel edges. The orange and cyan directions must be perpendicular to each other. Choose a reference plane below or above the camera, place the purple origin on it, and enter the camera's distance to that plane.

Click **Save camera alignment** whenever you want to save the controls. You can keep adjusting and saving in the same page. Click **Finish alignment session** when you are ready for `run` to export. The scene is saved as `projects/short-film/blender/room.blend` in your resource folder.

Blender must be on your PATH, or add `--blender /Applications/Blender.app/Contents/MacOS/Blender` on macOS.

Use `run` for a new scene. To continue an existing scene, open its alignment page and export the latest saved controls:

```sh
stagecraft align --project short-film --scene room
stagecraft export --project short-film --scene room
```

Export replaces the same Stagecraft scene. It checks for Blender files changed outside Stagecraft before and after generation. Keep manual Blender work in a separately named file and avoid saving to the export destination while export runs. Save updates one set of controls without creating numbered versions. Existing task files are not moved automatically.

The Blender file contains the primitives, matched camera, packed reference photograph, original image resolution, and an enabled depth pass. Open it in Blender to refine the blockout or render guidance with your downstream tools. Geometry is an estimate; matching the camera alone does not reconstruct the scene. Distance to the reference plane supplies scale, and the selected point on that plane supplies the origin. Plane dimensions use X and Y; their Z value is ignored.

For agent integrations, every CLI response is JSON on its own line. `run` emits `needs_human` with a local browser URL, keeps the alignment page available for up to 15 minutes, then continues when the human chooses Finish alignment session. Use `--no-open` when your agent will present that URL itself. A timeout or cancellation preserves the project so `align` can resume it. [The agent contract](docs/agent-contract.md) covers scene files, coordinates, and errors.

## How to contribute

Report a failed camera match with a reproducible image and alignment, or open a pull request. Include only images you can share. See [development checks](docs/development.md) for running the tests.
