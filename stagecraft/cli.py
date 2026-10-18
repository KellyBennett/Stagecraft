import argparse
import json
import sys
from .camera import solve
from .export import export
from .project import initialize, load
from .server import align


def emit(data):
    print(json.dumps(data, allow_nan=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Match a photo camera and export an agent-described primitive Blender stage.")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Normalize an image and create a new project")
    init.add_argument("image")
    init.add_argument("--project", required=True)
    for name in ("align", "solve", "export", "status", "run"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--project", required=True)
        if name in ("align", "run"):
            cmd.add_argument("--timeout", type=float, default=900)
            cmd.add_argument("--no-open", action="store_true")
        if name in ("export", "run"):
            cmd.add_argument("--scene", required=True)
            cmd.add_argument("--output", required=True)
            cmd.add_argument("--blender", default="blender")
            cmd.add_argument("--force", action="store_true")
        if name == "run":
            cmd.add_argument("image")
    args = parser.parse_args(argv)
    try:
        if args.command in ("align", "run") and not 0 < args.timeout <= 86400:
            raise ValueError("Timeout must be between 0 and 86400 seconds")
        if args.command in ("init", "run"):
            path, _ = initialize(args.image, args.project)
            emit({"status": "created", "project": str(path)})
        if args.command in ("align", "run"):
            emit(align(args.project, args.timeout, not args.no_open, emit))
        if args.command in ("export", "run"):
            emit(export(args.project, args.scene, args.output, args.blender, args.force))
        if args.command in ("status", "solve"):
            path, data = load(args.project)
            if args.command == "status":
                emit({"status": "aligned" if data.get("alignment") else "needs_human", "project": str(path)})
            else:
                if not isinstance(data.get("alignment"), dict):
                    raise ValueError("Project needs human alignment")
                emit({"status": "solved", "camera": solve(data["width"], data["height"], data["alignment"])})
        return 0
    except KeyboardInterrupt:
        emit({"status": "cancelled"})
        return 130
    except (OSError, ValueError, TypeError, TimeoutError, KeyError) as exc:
        emit({"status": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
