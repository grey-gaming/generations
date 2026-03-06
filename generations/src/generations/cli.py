from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path

from .config import AppConfig
from .runner import Runner
from .state import default_runtime, load_runtime, save_runtime
from .web.exporter import export_site


def _start_embedded_web(root: Path, host: str, port: int) -> threading.Thread | None:
    try:
        import uvicorn
        from .web.app import create_app
    except ImportError:
        print("web unavailable: install project dependencies to enable the embedded journey server")
        return None

    app = create_app(root)

    def _serve() -> None:
        uvicorn.run(app, host=host, port=port, log_level="warning")

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    print(f"web ready: http://{host}:{port}")
    return thread


def main() -> int:
    parser = argparse.ArgumentParser(prog="generations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--seed", required=True)
    run_parser.add_argument("--debug", action="store_true")
    run_parser.add_argument("--parallel-tasks", type=int, default=3)
    run_parser.add_argument("--host", default="127.0.0.1")
    run_parser.add_argument("--port", type=int, default=80)

    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=80)

    export_parser = subparsers.add_parser("export-web")
    export_parser.add_argument("--out", required=True)

    subparsers.add_parser("status")
    subparsers.add_parser("pause")
    subparsers.add_parser("resume")

    args = parser.parse_args()
    root = Path.cwd()
    config = AppConfig.from_root(root)

    if args.command == "run":
        if not config.disable_web:
            _start_embedded_web(root, args.host, args.port)
        runner = Runner(root, args.seed, debug=args.debug, parallel_tasks=args.parallel_tasks)
        runner.run()
        return 0

    if args.command == "web":
        import uvicorn
        from .web.app import create_app

        uvicorn.run(create_app(root), host=args.host, port=args.port)
        return 0

    if args.command == "export-web":
        export_site(root, config, [], None, out_dir=Path(args.out))
        print(Path(args.out))
        return 0

    if args.command == "status":
        runtime = load_runtime(config.runtime_path)
        if not runtime:
            runtime = default_runtime()
            save_runtime(config.runtime_path, runtime)
        runtime["paused"] = config.pause_flag.exists()
        print(json.dumps(runtime, indent=2, sort_keys=True))
        return 0

    if args.command == "pause":
        config.pause_flag.parent.mkdir(parents=True, exist_ok=True)
        config.pause_flag.write_text("paused\n", encoding="utf-8")
        print("paused")
        return 0

    if args.command == "resume":
        if config.pause_flag.exists():
            config.pause_flag.unlink()
        print("resumed")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
