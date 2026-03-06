from __future__ import annotations

from pathlib import Path
import json

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.state import load_current_loop_plan, load_runtime_state


def export_site(
    root: Path,
    config: AppConfig | None = None,
    journal_entries: list[dict[str, object]] | None = None,
    memory: dict[str, object] | None = None,
    *,
    out_dir: Path | None = None,
) -> Path:
    config = config or AppConfig.from_root(root)
    output = out_dir or config.web_export_dir
    output.mkdir(parents=True, exist_ok=True)
    journal = journal_entries if journal_entries is not None else JournalStore(config.journal_path).read_all()
    memory_payload = memory if memory is not None else MemoryStore(config.memory_path).latest()
    runtime = load_runtime_state(config.runtime_path)
    current_loop_plan = load_current_loop_plan(config.current_loop_plan_path) or memory_payload.get("current_loop_plan") or {}
    html = f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Generations Journey</title>
  <link rel='stylesheet' href='./style.css'>
</head>
<body>
<main class='page'>
<section class='panel'><h1>Generations</h1><p>Autonomous game-development diary and dashboard.</p></section>
<section class='grid'>
<article class='panel'><h2>Now</h2><pre>{json.dumps(runtime.as_dict(), indent=2)}</pre></article>
<article class='panel'><h2>Current Loop Plan</h2><pre>{json.dumps(current_loop_plan, indent=2) if current_loop_plan else 'No loop plan active.'}</pre></article>
<article class='panel'><h2>Current Planning Horizon</h2><pre>{json.dumps(memory_payload.get('planning', {}).get('current'), indent=2) if memory_payload.get('planning', {}).get('current') else 'No planning checkpoint yet.'}</pre></article>
</section>
<section class='grid'>
<article class='panel'><h2>Support</h2><p>Support options may evolve over time. Any monetization experiments will be logged and kept honest.</p></article>
<article class='panel'><h2>Disclosure</h2><p>Generations changes its own platform, game workspace, and website through recorded autonomous loops.</p></article>
</section>
<section class='panel'><h2>Diary</h2>{''.join(f"<article class='entry'><h3>Loop {e.get('loop_counter')}</h3><p>{e.get('diary', {}).get('entry', e.get('next_step', {}).get('description', ''))}</p></article>" for e in reversed(journal[-10:])) or '<p>No diary entries yet.</p>'}</section>
</main>
</body></html>"""
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / "style.css").write_text("body{font-family:Georgia,serif;background:#ede8de;color:#1f2822;margin:0}.page{max-width:1100px;margin:0 auto;padding:24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.panel{background:#fff9ef;border:1px solid #d7ccbb;border-radius:16px;padding:16px;margin-bottom:16px}.entry{border-top:1px solid #d7ccbb;padding-top:12px;margin-top:12px}", encoding="utf-8")
    return output
