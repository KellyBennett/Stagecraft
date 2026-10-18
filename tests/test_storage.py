import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from stagecraft.cli import main
from stagecraft.storage import ScenePaths, create_project, resource_root


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.image = self.root / 'photo.png'
        Image.new('RGB', (100, 80)).save(self.image)
        self.primitives = Path(__file__).resolve().parents[1] / 'examples/scene.json'

    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main([*args, '--root', str(self.root)])
        return result, json.loads(output.getvalue())

    def test_create_select_and_storage_contract(self):
        self.assertEqual(self.cli('projects')[1]['projects'], [])
        self.assertEqual(self.cli('create-project', '--project', 'stay_focused')[0], 0)
        self.assertEqual(self.cli('projects')[1]['projects'], ['stay_focused'])
        self.assertEqual(self.cli('create-project', '--project', 'stay_focused')[0], 1)
        args = ['--project', 'stay_focused', '--scene', 'Hangers2']
        self.assertEqual(self.cli('status', *args)[0], 1)
        code, result = self.cli('init', str(self.image), '--primitives', str(self.primitives), *args)
        self.assertEqual(code, 0)
        base = self.root / 'projects/stay_focused'
        self.assertEqual(result['output'], str(base / 'blender/Hangers2.blend'))
        self.assertEqual(result['depth_output'], str(base / 'outputs/Hangers2-depth.png'))
        for name in ('image.png', 'project.json', 'scene.json'):
            self.assertTrue((base / 'blender/assets/Hangers2' / name).is_file())
        self.assertEqual(self.cli('status', *args)[1]['active_project'], 'stay_focused')
        self.assertEqual(self.cli('init', str(self.image), '--primitives', str(self.primitives), *args)[0], 1)

    def test_config_and_missing_root(self):
        config = self.root / 'settings.json'
        config.write_text(json.dumps({'schema_version': 1, 'project_root': str(self.root)}))
        self.assertEqual(resource_root(config=config), self.root.resolve())
        with self.assertRaises(ValueError): resource_root(self.root / 'missing')
        config.write_text('[]')
        with self.assertRaises(ValueError): resource_root(config=config)

    def test_traversal_and_symlink_paths_are_rejected_without_touching_targets(self):
        create_project(self.root, 'demo')
        for name in ('../escape', '/tmp/x', '.', '..', 'a/b', 'a\\b', ''):
            with self.subTest(name=name):
                with self.assertRaises(ValueError): create_project(self.root, name)
                with self.assertRaises(ValueError): ScenePaths(self.root, 'demo', name)
        outside = self.root / 'outside'; outside.mkdir()
        project = self.root / 'projects/demo'
        (project / 'blender').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError): ScenePaths(self.root, 'demo', 'stage')
        (project / 'blender').unlink()
        paths = ScenePaths(self.root, 'demo', 'stage')
        paths.initialize(self.image, self.primitives)
        for name in ('image.png', 'project.json', 'scene.json', '.stagecraft.lock'):
            target = paths.assets / name
            if target.exists(): target.unlink()
            target.symlink_to(outside / name)
            with self.assertRaises(ValueError): paths.owned()
            target.unlink()
        self.assertEqual(list(outside.iterdir()), [])

    def test_foreign_scene_and_blend_are_preserved(self):
        create_project(self.root, 'demo')
        paths = ScenePaths(self.root, 'demo', 'stage')
        paths.blend.parent.mkdir()
        paths.blend.write_bytes(b'foreign blender data')
        with self.assertRaises(ValueError): paths.initialize(self.image, self.primitives)
        self.assertEqual(paths.blend.read_bytes(), b'foreign blender data')
        self.assertFalse(paths.assets.exists())
        paths.blend.unlink()
        paths.assets.mkdir(parents=True)
        note = paths.assets / 'notes.txt'; note.write_text('keep this')
        with self.assertRaises(ValueError): paths.initialize(self.image, self.primitives)
        self.assertEqual(note.read_text(), 'keep this')

    def test_existing_names_with_spaces_and_dots_are_selectable(self):
        project = self.root / 'projects' / 'Stay Focused.v2'
        project.mkdir(parents=True)
        self.assertIn('Stay Focused.v2', self.cli('projects')[1]['projects'])
        paths = ScenePaths(self.root, 'Stay Focused.v2', 'Main Stage.v2')
        paths.initialize(self.image, self.primitives)
        self.assertEqual(paths.owned()['stagecraft']['project'], 'Stay Focused.v2')

    def test_busy_scene_refuses_save_without_losing_controls(self):
        from helpers import alignment
        create_project(self.root, 'demo')
        paths = ScenePaths(self.root, 'demo', 'stage')
        paths.initialize(self.image, self.primitives)
        first = alignment()
        paths.save_alignment(first)
        with paths.lock():
            latest = alignment(); latest['camera_height'] = 9
            with self.assertRaisesRegex(ValueError, 'busy'):
                paths.save_alignment(latest)
        self.assertEqual(paths.owned()['alignment'], first)
        paths.save_alignment(latest)
        self.assertEqual(paths.owned()['alignment'], latest)
