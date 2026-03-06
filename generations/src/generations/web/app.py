from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.state import load_current_loop_plan, load_runtime_state


def create_app(root: Path) -> FastAPI:
    config = AppConfig.from_root(root)
    app = FastAPI(title="Generations")
    templates = Jinja2Templates(directory=str(root / "generations" / "src" / "generations" / "web" / "templates"))
    app.mount("/static", StaticFiles(directory=root / "generations" / "src" / "generations" / "web" / "static"), name="static")
    journal = JournalStore(config.journal_path)
    memory = MemoryStore(config.memory_path)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "entries": list(reversed(journal.read_all()[-20:])),
                "memory": memory.latest(),
                "runtime": load_runtime_state(config.runtime_path).as_dict(),
                "current_loop_plan": load_current_loop_plan(config.current_loop_plan_path),
            },
        )

    @app.get("/journal")
    async def journal_route() -> JSONResponse:
        return JSONResponse(journal.read_all())

    @app.get("/memory")
    async def memory_route() -> JSONResponse:
        return JSONResponse(memory.latest())

    @app.get("/planning")
    async def planning_route() -> JSONResponse:
        return JSONResponse(memory.latest().get("planning", {}))

    @app.get("/diary")
    async def diary_route() -> JSONResponse:
        entries = [entry.get("diary", {}) for entry in journal.read_all() if entry.get("diary")]
        return JSONResponse(entries)

    @app.get("/current-loop-plan")
    async def current_loop_plan_route() -> JSONResponse:
        return JSONResponse(load_current_loop_plan(config.current_loop_plan_path))

    @app.get("/status")
    async def status_route() -> JSONResponse:
        return JSONResponse(load_runtime_state(config.runtime_path).as_dict())

    return app
