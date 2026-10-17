import contextlib
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from PIL import Image
from stagecraft.cli import main
from stagecraft.project import initialize, load
from stagecraft.scene import validate_scene
from stagecraft.server import align
from helpers import alignment


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.image = self.root/'input.jpg'
        Image.new('RGB',(1000,800)).save(self.image)
        self.project = self.root/'project'; initialize(self.image,self.project)

    def test_init_refuses_existing_project_and_normalizes_exif(self):
        with self.assertRaises(FileExistsError): initialize(self.image,self.project)
        img=Image.new('RGB',(40,20)); exif=Image.Exif(); exif[274]=6
        img.save(self.root/'rotated.jpg',exif=exif)
        _,data=initialize(self.root/'rotated.jpg',self.root/'rotated')
        self.assertEqual((data['width'],data['height']),(20,40))

    def test_scene_rejects_unsupported_and_nonfinite_objects(self):
        valid={"version":1,"objects":[{"name":"Box","type":"box","location":[0,0,1],"dimensions":[2,2,2]}]}
        self.assertEqual(validate_scene(valid)['objects'][0]['rotation_degrees'],[0,0,0])
        for key,value in [('type','mesh'),('location',[0,float('nan'),0]),('dimensions',[0,1,1]),('name','')]:
            bad=json.loads(json.dumps(valid));bad['objects'][0][key]=value
            with self.assertRaises(ValueError): validate_scene(bad)

    def test_cli_reports_human_handoff_and_error(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(['status','--project',str(self.project)]),0)
            self.assertEqual(main(['solve','--project',str(self.project)]),1)
        results=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r['status'] for r in results],['needs_human','error'])

    def test_server_validates_then_persists_and_exits(self):
        ready=threading.Event();events=[];errors=[]
        def announce(event): events.append(event);ready.set()
        def run():
            try: align(self.project,timeout=8,open_browser=False,announce=announce)
            except Exception as exc: errors.append(exc)
        thread=threading.Thread(target=run);thread.start();self.addCleanup(lambda:thread.join(9))
        self.assertTrue(ready.wait(3));url=events[0]['url']
        with urllib.request.urlopen(url+'state') as response: self.assertEqual(json.load(response)['width'],1000)
        for suffix in ['../../project.json','not-a-file']:
            with self.assertRaises(urllib.error.HTTPError): urllib.request.urlopen(url+suffix)
        wrong=urllib.request.Request(url+'alignment',data=b'{}',headers={'Origin':'https://evil.example'})
        with self.assertRaises(urllib.error.HTTPError) as rejected: urllib.request.urlopen(wrong)
        self.assertEqual(rejected.exception.code,403)
        bad=urllib.request.Request(url+'alignment',data=b'{}')
        with self.assertRaises(urllib.error.HTTPError) as rejected: urllib.request.urlopen(bad)
        self.assertEqual(rejected.exception.code,422)
        request=urllib.request.Request(url+'alignment',data=json.dumps(alignment()).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response: self.assertTrue(json.load(response)['saved'])
        thread.join(3);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(load(self.project)[1]['alignment'],alignment())

    def test_timeout_preserves_project(self):
        with self.assertRaises(TimeoutError): align(self.project,timeout=.05,open_browser=False)
        self.assertNotIn('alignment',load(self.project)[1])
