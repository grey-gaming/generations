from __future__ import annotations

import argparse
import os
from pathlib import Path
import threading
import sys

from generations.config import AppConfig
from generations.runner import Runner, init_repo_if_needed
from generations.state import load_runtime_state, save_runtime_state
from generations.web.exporter import export_site


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="generations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--seed", required=True)
    run_parser.add_argument("--host", default="127.0.0.1")
    run_parser.add_argument("--port", type=int, default=8000)
    run_parser.add_argument("--debug", action="store_true")

    web_parser = subparsers.add_parser("web")
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8000)

    export_parser = subparsers.add_parser("export-web")
    export_parser.add_argument("--out", default="./site")

    opencode_test_parser = subparsers.add_parser("opencode-write-test")
    opencode_test_parser.add_argument("--debug", action="store_true")

    subparsers.add_parser("status")
    subparsers.add_parser("pause")
    subparsers.add_parser("resume")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "debug", False):
        os.environ["GENERATIONS_DEBUG"] = "1"
    root = Path.cwd()
    config = AppConfig.from_root(root)
    init_repo_if_needed(root)

    if args.command == "run":
        _maybe_start_embedded_web(root, args.host, args.port)
        Runner(root, args.seed).run()
        return 0

    if args.command == "web":
        import uvicorn
        from generations.web.app import create_app

        app = create_app(root)
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    if args.command == "export-web":
        export_site(root, Path(args.out))
        print(Path(args.out).resolve())
        return 0

    if args.command == "opencode-write-test":
        from generations.adapters.opencode import OpenCodeAdapter

        success, details = OpenCodeAdapter(root).probe_write_access()
        print({"success": success, **details})
        return 0 if success else 1

    if args.command == "status":
        runtime = load_runtime_state(config.runtime_path)
        print(runtime.as_dict())
        return 0

    if args.command == "pause":
        config.pause_flag.write_text("paused\n", encoding="utf-8")
        runtime = load_runtime_state(config.runtime_path)
        runtime.paused = True
        runtime.last_decision = "paused"
        save_runtime_state(config.runtime_path, runtime)
        print("paused")
        return 0

    if args.command == "resume":
        if config.pause_flag.exists():
            config.pause_flag.unlink()
        runtime = load_runtime_state(config.runtime_path)
        runtime.paused = False
        runtime.last_decision = "resumed"
        save_runtime_state(config.runtime_path, runtime)
        print("resumed")
        return 0

    return 1


def _maybe_start_embedded_web(root: Path, host: str, port: int) -> None:
    config = AppConfig.from_root(root)
    if config.test_mode or config.disable_web:
        return
    try:
        import uvicorn
        from generations.web.app import create_app
    except ModuleNotFoundError:
        print("web unavailable: install project dependencies to enable the embedded journey server", flush=True)
        return

    app = create_app(root)
    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="generations-web")
    thread.start()
    print(f"web ready: http://{host}:{port}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
