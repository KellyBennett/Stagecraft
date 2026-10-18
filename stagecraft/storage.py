"""ComfyLoom project discovery and Stagecraft's managed scene paths."""
import hashlib
import fcntl
from contextlib import contextmanager
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from .project import initialize, load, write_json
from .scene import validate_scene
from .export import export


def component(value):
    if (not isinstance(value, str) or not value.strip() or value in ('.', '..')
            or '/' in value or '\\' in value or any(ord(c) < 32 for c in value)):
        raise ValueError('Project and scene names must be safe single folder names')
    return value


def resource_root(root=None, config=None):
    if root is None:
        config = Path(config) if config else Path.home() / 'Library/Application Support/ComfyGateway/settings.json'
        settings = json.loads(config.read_text())
        if not isinstance(settings, dict) or settings.get('schema_version') != 1 or not isinstance(settings.get('project_root'), str):
            raise ValueError('Expected ComfyLoom settings schema_version 1 with project_root')
        root = settings['project_root']
        if not Path(root).expanduser().is_absolute():
            raise ValueError('Configured project_root must be an absolute path')
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        raise ValueError('ComfyLoom resource root must already exist')
    return path


def checked(root, *parts):
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError(f'Symlinks are not allowed in managed paths: {path}')
    return path


def projects(root):
    directory = checked(root, 'projects')
    if not directory.exists():
        return []
    return sorted(p.name for p in directory.iterdir() if p.is_dir() and not p.is_symlink())


def create_project(root, name):
    path = checked(root, 'projects', component(name))
    path.mkdir(parents=True, exist_ok=False)
    return path


@dataclass(frozen=True)
class ScenePaths:
    root: Path
    project: str
    scene: str

    def __post_init__(self):
        component(self.project)
        component(self.scene)
        self.validate()

    def validate(self):
        if not checked(self.root, 'projects', self.project).is_dir():
            raise ValueError('Project does not exist; select an existing project or use create-project')
        for path in (self.assets, self.blend, self.depth):
            checked(self.root, *path.relative_to(self.root).parts)
        for name in ('image.png', 'project.json', 'scene.json', '.stagecraft.lock'):
            checked(self.root, *self.assets.relative_to(self.root).parts, name)

    @property
    def assets(self):
        return self.root / 'projects' / self.project / 'blender' / 'assets' / self.scene

    @property
    def blend(self):
        return self.root / 'projects' / self.project / 'blender' / (self.scene + '.blend')

    @property
    def depth(self):
        return self.root / 'projects' / self.project / 'outputs' / (self.scene + '-depth.png')

    def describe(self):
        return {'active_project': self.project, 'scene': self.scene, 'project': str(self.assets),
                'image': str(self.assets / 'image.png'), 'controls': str(self.assets / 'project.json'),
                'primitives': str(self.assets / 'scene.json'), 'output': str(self.blend), 'depth_output': str(self.depth)}

    def owned(self):
        self.validate()
        _, data = load(self.assets)
        if data.get('stagecraft') != {'project': self.project, 'scene': self.scene}:
            raise ValueError('Scene assets are not owned by Stagecraft; choose a new scene name')
        return data

    def initialize(self, image, primitives):
        self.validate()
        scene = validate_scene(json.loads(Path(primitives).read_text()))
        if self.blend.exists() or self.assets.exists():
            raise ValueError('Scene already exists; choose a new name or resume with align')
        _, data = initialize(image, self.assets)
        data['stagecraft'] = {'project': self.project, 'scene': self.scene}
        write_json(self.assets / 'project.json', data)
        write_json(self.assets / 'scene.json', scene)
        self.depth.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def lock(self):
        self.validate()
        with (self.assets / '.stagecraft.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError('Scene is busy exporting or saving; retry when it finishes') from exc
            yield

    def save_alignment(self, alignment):
        with self.lock():
            data = self.owned()
            write_json(self.assets / 'project.json', {**data, 'alignment': alignment})

    def export(self, blender='blender'):
        with self.lock():
            return self._export(blender)

    def _export(self, blender):
        data = self.owned()
        if self.blend.exists() and data.get('blend_sha256') != hashlib.sha256(self.blend.read_bytes()).hexdigest():
            raise ValueError('Existing Blender file is unowned or changed outside Stagecraft; preserve it and choose a new scene')
        original_hash = data.get('blend_sha256') if self.blend.exists() else None
        with tempfile.TemporaryDirectory(dir=self.blend.parent, prefix='.stagecraft-publish-') as tmp:
            candidate = Path(tmp) / 'scene.blend'
            result = export(self.assets, self.assets / 'scene.json', candidate, blender)
            candidate_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
            self.validate()
            current_hash = hashlib.sha256(self.blend.read_bytes()).hexdigest() if self.blend.exists() else None
            if current_hash != original_hash:
                raise ValueError('Blender file changed during export; existing file preserved')
            if original_hash is None:
                # Atomic no-clobber publication if another writer creates it now.
                try:
                    os.link(candidate, self.blend)
                except FileExistsError as exc:
                    raise ValueError('Blender file changed during export; existing file preserved') from exc
            else:
                # Recheck immediately before replacement. This is not a filesystem
                # compare-and-swap against writers that do not share our lock.
                candidate.replace(self.blend)
            data['blend_sha256'] = candidate_hash
            write_json(self.assets / 'project.json', data)
        return {**result, **self.describe()}
