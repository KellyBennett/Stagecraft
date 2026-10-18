import contextlib
import io
import json
import socket
import time
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path
from PIL import Image
from stagecraft.cli import main
from stagecraft.project import initialize, load
from stagecraft.scene import validate_scene
from stagecraft.server import align
from stagecraft.storage import ScenePaths, create_project
from helpers import alignment


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.image = self.root/'input.jpg'
        Image.new('RGB',(1000,800)).save(self.image)
        create_project(self.root, 'demo')
        self.paths = ScenePaths(self.root, 'demo', 'stage')
        self.paths.initialize(self.image, Path(__file__).resolve().parents[1] / 'examples/scene.json')
        self.project = self.paths.assets
        self.cli_args = ['--root', str(self.root), '--project', 'demo', '--scene', 'stage']

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
            self.assertEqual(main(['status', *self.cli_args]),0)
            self.assertEqual(main(['solve', *self.cli_args]),1)
        results=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([r['status'] for r in results],['needs_human','error'])

    def test_server_validates_resaves_reads_latest_and_finishes(self):
        ready=threading.Event();events=[];errors=[]
        def announce(event): events.append(event);ready.set()
        def run():
            try: align(self.project,timeout=8,open_browser=False,announce=announce, paths=self.paths)
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
        self.assertTrue(thread.is_alive())
        latest = alignment(); latest['camera_height'] = 7
        with urllib.request.urlopen(urllib.request.Request(url+'alignment', data=json.dumps(latest).encode())) as response:
            self.assertTrue(json.load(response)['saved'])
        with urllib.request.urlopen(url+'state') as response:
            state = json.load(response)
            self.assertEqual(state['alignment'], latest)
            self.assertEqual(state['active_project'], 'demo')
        with urllib.request.urlopen(urllib.request.Request(url+'finish', data=b'')) as response:
            self.assertTrue(json.load(response)['finished'])
        thread.join(3);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(load(self.project)[1]['alignment'],latest)

    def test_timeout_preserves_project(self):
        with self.assertRaises(TimeoutError): align(self.project,timeout=.05,open_browser=False)
        self.assertNotIn('alignment',load(self.project)[1])

    def test_incomplete_requests_respect_absolute_session_deadline(self):
        for partial, drip in [(b"GET /", False), (b"GET /", True), (None, False), (None, True)]:
            with self.subTest(body=partial is None, drip=drip):
                ready = threading.Event()
                events, errors = [], []
                def announce(event):
                    events.append(event)
                    ready.set()
                def run():
                    try:
                        align(self.project, timeout=.5, open_browser=False, announce=announce)
                    except Exception as exc:
                        errors.append(exc)
                thread = threading.Thread(target=run)
                thread.start()
                self.assertTrue(ready.wait(3))
                url = urlsplit(events[0]['url'])
                with socket.create_connection((url.hostname, url.port), timeout=1) as client:
                    if partial is None:
                        partial = (f"POST {url.path}alignment HTTP/1.1\r\n"
                                   f"Host: {url.netloc}\r\nContent-Length: 1000\r\n\r\n").encode()
                    client.sendall(partial)
                    start = time.monotonic()
                    while thread.is_alive() and time.monotonic() - start < 1.2:
                        if drip:
                            try:
                                client.sendall(b" ")
                            except OSError:
                                pass
                        thread.join(.04)
                    completed_before_close = not thread.is_alive()
                thread.join(2)
                self.assertTrue(completed_before_close, "An incomplete request outlived the session deadline")
                self.assertFalse(thread.is_alive())
                self.assertEqual(len(errors), 1)
                self.assertIsInstance(errors[0], TimeoutError)
                self.assertNotIn('alignment', load(self.project)[1])

    def test_cli_reports_non_object_project_json_as_error(self):
        for value in [None, [], "project", 1, True]:
            with self.subTest(value=value):
                (self.project / 'project.json').write_text(json.dumps(value))
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = main(['status', *self.cli_args])
                self.assertEqual(result, 1)
                response = json.loads(output.getvalue())
                self.assertEqual(response['status'], 'error')
                self.assertEqual(response['error'], 'Project must be an object')
