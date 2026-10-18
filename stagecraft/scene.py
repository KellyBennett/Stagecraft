"""Validate the small, versioned agent contract before starting Blender."""
from .camera import finite_number


def vector(value, label, positive=False):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{label} must be a three-number array")
    result = [finite_number(v, label) for v in value]
    if positive and any(v <= 0 for v in result):
        raise ValueError(f"{label} must be positive")
    return result


def validate_scene(data):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Scene version must be 1")
    objects = data.get("objects")
    if not isinstance(objects, list) or not objects or len(objects) > 1000:
        raise ValueError("Scene needs between 1 and 1000 objects")
    result, names = [], set()
    for obj in objects:
        if not isinstance(obj, dict):
            raise ValueError("Objects must be JSON objects")
        kind = obj.get("type")
        if kind not in ("box", "plane", "cylinder", "sphere"):
            raise ValueError("Primitive must be box, plane, cylinder, or sphere")
        name = obj.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Primitive names must be nonempty and unique")
        names.add(name)
        result.append({"name": name, "type": kind,
                       "location": vector(obj.get("location"), "Location"),
                       "dimensions": vector(obj.get("dimensions"), "Dimensions", True),
                       "rotation_degrees": vector(obj.get("rotation_degrees", [0, 0, 0]), "Rotation")})
    return {"version": 1, "objects": result}
