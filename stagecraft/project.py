import json
import os
import tempfile
from pathlib import Path
from PIL import Image, ImageOps


def write_json(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".stagecraft-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, allow_nan=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load(project):
    path = Path(project).resolve()
    data = json.loads((path / "project.json").read_text())
    if not isinstance(data, dict):
        raise ValueError("Project must be an object")
    if data.get("version") != 1:
        raise ValueError("Unsupported project version")
    # Read dimensions from the actual normalized image, not editable metadata.
    with Image.open(path / "image.png") as image:
        data["width"], data["height"] = image.size
    return path, data


def initialize(image, project):
    project = Path(project).resolve()
    # Decode before creating output. EXIF orientation is baked into working pixels.
    with Image.open(image) as source:
        normalized = ImageOps.exif_transpose(source).convert("RGB")
        width, height = normalized.size
        project.mkdir(parents=True, exist_ok=False)
        normalized.save(project / "image.png")
    data = {"version": 1, "width": width, "height": height}
    write_json(project / "project.json", data)
    return project, data
