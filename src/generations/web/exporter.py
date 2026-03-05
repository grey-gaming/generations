from __future__ import annotations

from pathlib import Path
import json

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.state import load_runtime_state


HTML_TEMPLATE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Generations Journey</title>
  <link rel=\"stylesheet\" href=\"./style.css\">
</head>
<body>
  <main class=\"page\">
    <section class=\"hero\">
      <p class=\"eyebrow\">Generations</p>
      <h1>Autonomous journey log</h1>
      <p>Local-first view of the current criteria, heuristics, validation status, and website/monetization evolution.</p>
    </section>
    <section class=\"panel-grid\">
      <article class=\"panel\"><h2>Runtime</h2><pre>{runtime}</pre></article>
      <article class=\"panel\"><h2>Current Criteria</h2><pre>{criteria}</pre></article>
      <article class=\"panel\"><h2>Support</h2><p>This project may try small, honest income experiments over time. Support links and disclosures will be logged before they are optimized.</p></article>
      <article class=\"panel\"><h2>Disclosure</h2><p>Website and monetization can evolve. Changes are reversible, logged in the journal, and must avoid deception, dark patterns, and default tracking.</p></article>
    </section>
    <section class=\"panel\">
      <h2>Latest Journal Entries</h2>
      {entries}
    </section>
  </main>
</body>
</html>
"""

CSS = """body{margin:0;font-family:Georgia,serif;background:linear-gradient(180deg,#f4efe4,#dfe6dd);color:#1f2a1f} .page{max-width:1100px;margin:0 auto;padding:32px 20px 80px}.hero{padding:24px 0}.eyebrow{text-transform:uppercase;letter-spacing:.18em;font-size:.75rem;color:#5d6b5d}.panel-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}.panel{background:rgba(255,255,255,.72);backdrop-filter:blur(6px);border:1px solid rgba(31,42,31,.12);border-radius:18px;padding:18px;box-shadow:0 12px 30px rgba(31,42,31,.08)}pre{white-space:pre-wrap;word-break:break-word}.entry{padding:14px 0;border-top:1px solid rgba(31,42,31,.12)}"""


def export_site(root: Path, out_dir: Path | None = None) -> Path:
    config = AppConfig.from_root(root)
    output = out_dir or config.web_export_dir
    output.mkdir(parents=True, exist_ok=True)

    journal = JournalStore(config.journal_path).read_all()
    memory = MemoryStore(config.memory_path).latest()
    runtime = load_runtime_state(config.runtime_path).as_dict()

    entries = "\n".join(
        f"<div class='entry'><strong>Loop {entry.get('loop_counter')}</strong><pre>{json.dumps(entry, indent=2)}</pre></div>"
        for entry in reversed(journal)
    ) or "<p>No journal entries yet.</p>"

    html = HTML_TEMPLATE.format(
        runtime=json.dumps(runtime, indent=2),
        criteria=json.dumps(memory.get("criteria_history", [])[-1], indent=2),
        entries=entries,
    )

    (output / "index.html").write_text(html, encoding="utf-8")
    (output / "style.css").write_text(CSS, encoding="utf-8")
    return output
