from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.state import load_runtime_state


def create_app(root: Path) -> FastAPI:
    config = AppConfig.from_root(root)
    app = FastAPI(title="Generations")
    templates = Jinja2Templates(directory=str(root / "src" / "generations" / "web" / "templates"))
    static_dir = root / "src" / "generations" / "web" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    journal = JournalStore(config.journal_path)
    memory = MemoryStore(config.memory_path)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        entries = list(reversed(journal.read_all()))
        runtime = load_runtime_state(config.runtime_path)
        latest_memory = memory.latest()
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "entries": entries,
                "memory": latest_memory,
                "runtime": runtime.as_dict(),
            },
        )

    @app.get("/journal")
    async def journal_route() -> JSONResponse:
        return JSONResponse(journal.read_all())

    @app.get("/memory")
    async def memory_route() -> JSONResponse:
        return JSONResponse(memory.latest())

    @app.get("/status")
    async def status_route() -> JSONResponse:
        return JSONResponse(load_runtime_state(config.runtime_path).as_dict())

    return app
