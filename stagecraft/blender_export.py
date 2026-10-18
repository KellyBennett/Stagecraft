"""Executed by Blender's Python, without importing the Stagecraft package."""
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix


def build(payload_path):
    payload = json.loads(Path(payload_path).read_text())
    camera = payload["camera"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    for obj in payload["scene"]["objects"]:
        kind = obj["type"]
        if kind == "box":
            bpy.ops.mesh.primitive_cube_add(size=1)
        elif kind == "plane":
            bpy.ops.mesh.primitive_plane_add(size=1)
        elif kind == "cylinder":
            bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.5, depth=1)
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=0.5)
        primitive = bpy.context.object
        primitive.name = obj["name"]
        primitive.location = obj["location"]
        primitive.dimensions = obj["dimensions"]
        primitive.rotation_euler = [math.radians(v) for v in obj["rotation_degrees"]]
    cam_data = bpy.data.cameras.new("Stagecraft Camera")
    cam = bpy.data.objects.new("Stagecraft Camera", cam_data)
    scene.collection.objects.link(cam)
    cam.location = camera["location"]
    cam.rotation_euler = Matrix(camera["rotation"]).to_euler()
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = camera["sensor_width_mm"]
    cam_data.lens = camera["lens_mm"]
    cam_data.clip_end = 10000
    cam_data.show_background_images = True
    bg = cam_data.background_images.new()
    bg.image = bpy.data.images.load(payload["image"])
    bg.image.pack()
    bg.alpha = 0.5
    scene.camera = cam
    scene.render.resolution_x = camera["width"]
    scene.render.resolution_y = camera["height"]
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.view_layers[0].use_pass_z = True
    scene["stagecraft_version"] = 1
    scene["stagecraft_assumptions"] = "Centered principal point; square pixels; perpendicular horizontal axes; supplied plane distance and primitives"
    bpy.ops.wm.save_as_mainfile(filepath=payload["output"])


if __name__ == "__main__":
    build(sys.argv[sys.argv.index("--") + 1])
