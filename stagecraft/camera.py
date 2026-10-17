"""Two orthogonal vanishing points, centered principal point, square pixels.

Image coordinates are pixels, x right, y down. Camera coordinates follow
Blender: x right, y up, looking down -z. Rotation rows map camera coordinates to world coordinates.
"""
import math


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def unit(v):
    n = math.sqrt(dot(v, v))
    if n < 1e-10:
        raise ValueError("Degenerate direction")
    return [x/n for x in v]


def finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def point(value, label):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must contain two pixel coordinates")
    return [finite_number(v, label) for v in value]


def intersection(lines):
    if not isinstance(lines, list) or len(lines) != 2:
        raise ValueError("Each axis needs two line segments")
    homogeneous = []
    for line in lines:
        if not isinstance(line, list) or len(line) != 2:
            raise ValueError("Each line needs two endpoints")
        a, b = [point(p, "Endpoint") for p in line]
        if math.dist(a, b) < 2:
            raise ValueError("Line segments must be at least two pixels long")
        homogeneous.append(cross([*a, 1], [*b, 1]))
    p = cross(*homogeneous)
    # Relative angle avoids unstable intersections at infinity.
    normal_product = math.hypot(*homogeneous[0][:2]) * math.hypot(*homogeneous[1][:2])
    if abs(p[2]) / normal_product < 1e-5:
        raise ValueError("Lines are parallel or nearly parallel; choose converging edges")
    return [p[0]/p[2], p[1]/p[2]]


def solve(width, height, alignment):
    if not isinstance(alignment, dict):
        raise ValueError("Alignment must be an object")
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive")
    vx, vy = [intersection(alignment.get(k)) for k in ("x", "y")]
    cx, cy = width/2, height/2
    f2 = -((vx[0]-cx)*(vy[0]-cx) + (vx[1]-cy)*(vy[1]-cy))
    if f2 <= 1 or not math.isfinite(f2):
        raise ValueError("These guides cannot describe perpendicular axes with a centered camera")
    f = math.sqrt(f2)
    x = unit([vx[0]-cx, cy-vx[1], -f])
    y = unit([vy[0]-cx, cy-vy[1], -f])
    z = unit(cross(x, y))
    # Select the sign of the horizontal axes so world Z points image-up.
    if z[1] < 0:
        y = [-v for v in y]
        z = [-v for v in z]
    origin = point(alignment.get("origin"), "Plane origin")
    if not (0 <= origin[0] <= width and 0 <= origin[1] <= height):
        raise ValueError("Plane origin must lie inside the image")
    reference_plane = alignment.get("reference_plane", "ground")
    if reference_plane not in ("ground", "overhead"):
        raise ValueError("Reference plane must be ground or overhead")
    h = finite_number(alignment.get("camera_height", 1.6), "Camera height")
    if h <= 0:
        raise ValueError("Camera height must be positive")
    ray = [(origin[0]-cx)/f, (cy-origin[1])/f, -1]
    ray_world = [dot(axis, ray) for axis in (x, y, z)]
    signed_height = h if reference_plane == "ground" else -h
    if abs(ray_world[2]) < 1e-6 or signed_height * ray_world[2] >= 0:
        side = "below" if reference_plane == "ground" else "above"
        raise ValueError(f"{reference_plane.capitalize()} origin must be {side} the horizon")
    distance = -signed_height/ray_world[2]
    location = [-distance*r for r in ray_world]
    rotation = [list(row) for row in (x, y, z)]  # camera-to-world rows
    return {"focal_px": f, "lens_mm": f*36/width, "sensor_width_mm": 36,
            "location": location, "rotation": rotation,
            "reference_plane": reference_plane, "vanishing_points": [vx, vy], "width": width, "height": height}
