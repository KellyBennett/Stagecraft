import os
import json
import shutil
import subprocess
import tempfile
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
