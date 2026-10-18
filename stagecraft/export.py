import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from .camera import solve
from .scene import validate_scene
from .project import load


def export(project, scene_file, output, blender="blender", force=False):
    path, data = load(project)
    if not isinstance(data.get("alignment"), dict):
        raise ValueError("Project needs human alignment; run stagecraft align first")
    camera = solve(data["width"], data["height"], data["alignment"])
    scene = validate_scene(json.loads(Path(scene_file).read_text()))
    output = Path(output).resolve()
    if output.suffix.lower() != ".blend":
        raise ValueError("Output must have a .blend extension")
    if output.exists() and not force:
        raise ValueError("Output exists; choose another path or pass --force")
    executable = shutil.which(blender)
    if not executable:
        raise ValueError("Blender executable not found; pass --blender /path/to/blender")
    if not output.parent.is_dir():
        raise ValueError("Output directory does not exist")
    # Blender writes in a private temporary directory; failed exports leave no partial output.
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".stagecraft-") as tmp:
        generated = Path(tmp) / "scene.blend"
        payload = {"camera": camera, "scene": scene, "image": str(path / "image.png"), "output": str(generated)}
        payload_path = Path(tmp) / "payload.json"
        payload_path.write_text(json.dumps(payload, allow_nan=False))
        try:
            result = subprocess.run([executable, "--background", "--factory-startup", "--python-exit-code", "1",
                                     "--python", str(Path(__file__).with_name("blender_export.py")), "--", str(payload_path)],
                                    capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Blender export timed out after 180 seconds") from exc
        if result.returncode != 0 or not generated.is_file():
            raise ValueError(f"Blender export failed: {(result.stderr + result.stdout)[-4000:]}")
        if force:
            generated.replace(output)
        else:
            # Atomic no-clobber publication, even if another process created output meanwhile.
            import os
            os.link(generated, output)
    return {"status": "exported", "output": str(output), "objects": len(scene["objects"]), "camera": camera}
