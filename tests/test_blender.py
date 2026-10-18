import os
import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from PIL import Image
from stagecraft.export import export
from stagecraft.project import initialize, write_json
from helpers import alignment, project
BLENDER = os.environ.get('STAGECRAFT_TEST_BLENDER') or shutil.which('blender')


@unittest.skipUnless(BLENDER, 'Set STAGECRAFT_TEST_BLENDER or put Blender on PATH')
class BlenderTests(unittest.TestCase):
    def test_real_export_reopens_with_matching_projections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new('RGB',(1000,800)).save(root/'photo.png')
            path,data=initialize(root/'photo.png',root/'project')
            write_json(path/'project.json',{**data,'alignment':alignment()})
            scene=Path(__file__).resolve().parents[1]/'examples/scene.json'
            scene_data=json.loads(scene.read_text())
            scene_data['objects'].append({'name':'Sphere','type':'sphere','location':[0,3,1],'dimensions':[1,1,1]})
            scene=root/'scene.json';scene.write_text(json.dumps(scene_data))
            result=export(path,scene,root/'scene.blend',BLENDER)
            self.assertEqual(result['objects'],4)
            with self.assertRaises(ValueError): export(path,scene,root/'scene.blend',BLENDER)
            expected=[project(p) for p in [[0,0,0],[2,0,0],[0,2,0],[0,0,2]]]
            script=root/'verify.py'
            script.write_text('''import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
s=bpy.context.scene
assert len([o for o in s.objects if o.type=='MESH'])==4
assert s.camera.data.background_images[0].image.packed_file
assert s.view_layers[0].use_pass_z
assert s.render.resolution_x==1000 and s.render.resolution_y==800
assert abs(s.camera.location.z-5)<1e-5
expected='''+repr(expected)+'''
for point,wanted in zip([[0,0,0],[2,0,0],[0,2,0],[0,0,2]],expected):
    v=world_to_camera_view(s,s.camera,Vector(point))
    actual=[v.x*1000,(1-v.y)*800]
    assert v.z>0
    assert max(abs(a-b) for a,b in zip(actual,wanted))<0.01,(actual,wanted)
''')
            completed=subprocess.run([BLENDER,'--background',str(root/'scene.blend'),'--python-exit-code','1','--python',str(script)],capture_output=True,text=True,timeout=180)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)

    def test_managed_repeat_export_uses_latest_saved_camera_and_preserves_other_data(self):
        from stagecraft.storage import ScenePaths, create_project
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            Image.new('RGB', (1000, 800)).save(root / 'photo.png')
            create_project(root, 'demo')
            paths = ScenePaths(root, 'demo', 'stage')
            paths.initialize(root / 'photo.png', Path(__file__).resolve().parents[1] / 'examples/scene.json')
            note = paths.blend.parent / 'unrelated.blend'; note.write_bytes(b'keep me')
            for height in (5, 8):
                value = alignment(); value['camera_height'] = height
                paths.save_alignment(value)
                result = paths.export(BLENDER)
                self.assertEqual(result['output'], str(paths.blend))
                script = root / 'verify_latest.py'
                script.write_text(f'import bpy\nassert abs(bpy.context.scene.camera.location.z - {height}) < 1e-5\n')
                completed = subprocess.run([BLENDER, '--background', str(paths.blend), '--python-exit-code', '1', '--python', str(script)], capture_output=True, text=True, timeout=180)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(note.read_bytes(), b'keep me')
            self.assertFalse(paths.blend.with_suffix('.blend1').exists())
            paths.blend.write_bytes(b'manual changes')
            with self.assertRaises(ValueError): paths.export(BLENDER)
            self.assertEqual(paths.blend.read_bytes(), b'manual changes')

    def test_managed_export_preserves_file_changed_while_blender_runs(self):
        from stagecraft.storage import ScenePaths, create_project
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                Image.new('RGB', (1000, 800)).save(root / 'photo.png')
                create_project(root, 'demo')
                paths = ScenePaths(root, 'demo', 'stage')
                paths.initialize(root / 'photo.png', Path(__file__).resolve().parents[1] / 'examples/scene.json')
                paths.save_alignment(alignment())
                if existing:
                    paths.export(BLENDER)
                previous_controls = (paths.assets / 'project.json').read_bytes()
                errors = []
                def run():
                    try:
                        paths.export(BLENDER)
                    except Exception as exc:
                        errors.append(exc)
                worker = threading.Thread(target=run)
                worker.start()
                try:
                    deadline = time.monotonic() + 10
                    # Observe the real export's input handoff before Blender
                    # finishes, then emulate a manual save to its destination.
                    while not list(paths.blend.parent.rglob('payload.json')):
                        if not worker.is_alive() or time.monotonic() >= deadline:
                            self.fail('Did not observe the running Blender export')
                        time.sleep(.001)
                    paths.blend.write_bytes(b'manual save during export')
                finally:
                    worker.join(190)
                self.assertFalse(worker.is_alive())
                self.assertEqual(len(errors), 1)
                self.assertIsInstance(errors[0], ValueError)
                self.assertEqual(paths.blend.read_bytes(), b'manual save during export')
                self.assertEqual((paths.assets / 'project.json').read_bytes(), previous_controls)
