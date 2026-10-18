import argparse
import json
import sys
from .camera import solve
from .server import align
from .storage import ScenePaths, create_project, projects, resource_root


def emit(data):
    print(json.dumps(data, allow_nan=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Match a photo camera inside an explicitly selected ComfyLoom project.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('projects', 'create-project', 'init', 'align', 'solve', 'export', 'status', 'run'):
        cmd = commands.add_parser(name)
        location = cmd.add_mutually_exclusive_group()
        location.add_argument('--root', help='Existing ComfyLoom resource root')
        location.add_argument('--config', help='ComfyGateway settings.json')
        if name != 'projects':
            cmd.add_argument('--project', required=True, help='ComfyLoom project name')
        if name not in ('projects', 'create-project'):
            cmd.add_argument('--scene', required=True, help='Scene name within the selected project')
        if name in ('init', 'run'):
            cmd.add_argument('image')
            cmd.add_argument('--primitives', required=True, help='Primitive scene JSON to copy into managed assets')
        if name in ('align', 'run'):
            cmd.add_argument('--timeout', type=float, default=900)
            cmd.add_argument('--no-open', action='store_true')
        if name in ('export', 'run'):
            cmd.add_argument('--blender', default='blender')
    args = parser.parse_args(argv)
    try:
        root = resource_root(args.root, args.config)
        if args.command == 'projects':
            emit({'status': 'ok', 'root': str(root), 'projects': projects(root)})
            return 0
        if args.command == 'create-project':
            path = create_project(root, args.project)
            emit({'status': 'created', 'active_project': args.project, 'path': str(path)})
            return 0
        paths = ScenePaths(root, args.project, args.scene)
        if args.command in ('align', 'run') and not 0 < args.timeout <= 86400:
            raise ValueError('Timeout must be between 0 and 86400 seconds')
        if args.command in ('init', 'run'):
            paths.initialize(args.image, args.primitives)
            emit({'status': 'created', **paths.describe()})
        else:
            paths.owned()
        if args.command in ('align', 'run'):
            emit(align(paths.assets, args.timeout, not args.no_open, emit, paths=paths))
        if args.command in ('export', 'run'):
            emit(paths.export(args.blender))
        if args.command in ('status', 'solve'):
            data = paths.owned()
            if args.command == 'status':
                emit({'status': 'aligned' if data.get('alignment') else 'needs_human', **paths.describe()})
            else:
                if not isinstance(data.get('alignment'), dict):
                    raise ValueError('Project needs human alignment')
                emit({'status': 'solved', 'camera': solve(data['width'], data['height'], data['alignment']), **paths.describe()})
        return 0
    except KeyboardInterrupt:
        emit({'status': 'cancelled'})
        return 130
    except (OSError, ValueError, TypeError, TimeoutError, KeyError) as exc:
        emit({'status': 'error', 'error': str(exc)})
        return 1


if __name__ == '__main__':
    sys.exit(main())
