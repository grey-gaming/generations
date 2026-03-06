from __future__ import annotations

from pathlib import Path

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.state import load_current_loop_plan, load_runtime_state
from generations.web.presentation import build_dashboard_context, visible_journal_entries


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
    all_entries = journal_entries if journal_entries is not None else JournalStore(config.journal_path).read_all()
    entries = visible_journal_entries(all_entries)
    memory_payload = memory if memory is not None else MemoryStore(config.memory_path).latest()
    runtime = load_runtime_state(config.runtime_path).as_dict()
    current_loop_plan = load_current_loop_plan(config.current_loop_plan_path) or memory_payload.get("current_loop_plan") or {}
    dashboard = build_dashboard_context(runtime, current_loop_plan, memory_payload, entries)
    html = _render_html(dashboard, entries)
    (output / "index.html").write_text(html, encoding="utf-8")
    style_source = Path(__file__).resolve().parent / 'static' / 'style.css'
    (output / 'style.css').write_text(style_source.read_text(encoding='utf-8'), encoding='utf-8')
    return output


def _render_html(dashboard: dict[str, object], entries: list[dict[str, object]]) -> str:
    now = dashboard["now"]
    loop = dashboard["loop"]
    planning = dashboard["planning"]
    support = dashboard["support"]
    diary = dashboard["diary"]
    status_strip = dashboard["status_strip"]
    task_cards = "".join(_task_card_html(task) for task in loop["tasks"]) or "<p>No active task plan.</p>"
    pillar_cards = "".join(_pillar_card_html(pillar) for pillar in planning["pillars"])
    metric_cards = "".join(
        f"<article class='metric-card'><span class='metric-name'>{name}</span><strong class='metric-value'>{value}%</strong></article>"
        for name, value in status_strip["metrics"].items()
    )
    diary_entries = "".join(_render_entry(entry) for entry in entries) or "<p>No entries yet.</p>"
    milestones = "".join(f"<li>{item}</li>" for item in planning["milestones_100"]) or "<li>No 100-loop milestones recorded yet.</li>"
    warning = f"<p class='warning'>Model fallback active: {status_strip['fallback']}</p>" if status_strip.get("fallback") else ""
    blocking = f"<p class='warning'>{loop['blocking_issue']}</p>" if loop.get("blocking_issue") else ""
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Generations Journey</title>
  <link rel='stylesheet' href='./style.css'>
</head>
<body>
  <main class='page'>
    <section class='hero'>
      <p class='eyebrow'>Generations</p>
      <h1>{_escape(now['active_game_name']).replace('_', ' ').title()}</h1>
      <p class='lede'>{_escape(now['active_game_thesis'])}</p>
      <div class='status-strip'>
        <span>Loop {_escape(now['loop_count'])}</span>
        <span>Validation: {_escape(now['last_validation'])}</span>
        <span>Model: {_escape(status_strip['model'])}</span>
        <span>Provider: {_escape(status_strip['provider'])}</span>
      </div>
      {warning}
    </section>

    <section class='grid top-grid'>
      <article class='card'>
        <h2>Now</h2>
        <p><strong>Active game:</strong> {_escape(now['active_game_name']).replace('_', ' ').title()}</p>
        <p><strong>Status:</strong> {_escape(now['active_game_status'])}</p>
        <p><strong>Last commit:</strong> {_escape(now['last_commit'])}</p>
        <p><strong>Validation:</strong> {_escape(now['last_validation'])}</p>
        <div class='pill-row'>
          <span class='pill'>Passes {_escape(now['pass_count'])}</span>
          <span class='pill'>Fails {_escape(now['fail_count'])}</span>
        </div>
      </article>
      <article class='card'>
        <h2>Current Loop</h2>
        <p class='feature-title'>{_escape(loop['theme'])}</p>
        <p>{_escape(loop['goal'])}</p>
        <div class='pill-row'>
          <span class='pill'>Integration {_escape(loop['integration_status'])}</span>
          <span class='pill'>Validation {_escape(loop['validation_status'])}</span>
        </div>
        <p class='muted'>{_escape(loop['summary'])}</p>
        {blocking}
      </article>
      <article class='card'>
        <h2>Planning</h2>
        <p><strong>Next 10 loops:</strong> {_escape(planning['theme_10'])}</p>
        <p><strong>100-loop direction:</strong></p>
        <ul>{milestones}</ul>
        <p><strong>250-loop vision:</strong> {_escape(planning['vision_250'])}</p>
      </article>
      <article class='card'>
        <h2>Support</h2>
        <p>{_escape(support['summary'])}</p>
        <p class='muted'>{_escape(support['disclosure'])}</p>
        <p><strong>Current experiment:</strong> {_escape(support['current_experiment'])}</p>
      </article>
    </section>

    <section class='card wide'>
      <h2>Current Tasks</h2>
      <div class='task-grid'>{task_cards}</div>
    </section>

    <section class='card wide'>
      <h2>Pillar Health</h2>
      <div class='pillar-grid'>{pillar_cards}</div>
    </section>

    <section class='card wide metrics-card'>
      <h2>Recent Metrics</h2>
      <div class='metric-grid'>{metric_cards}</div>
    </section>

    <section class='card wide'>
      <h2>Diary</h2>
      <article class='diary-highlight'>
        <p class='feature-title'>Mood: {_escape(diary['mood'])}</p>
        <p>{_escape(diary['latest_entry'])}</p>
        <p class='muted'>Next desire: {_escape(diary['next_desire'])}</p>
      </article>
      {diary_entries}
    </section>
  </main>
</body>
</html>"""


def _task_card_html(task: dict[str, object]) -> str:
    changed = task.get("changed_files") or []
    changed_html = ""
    if changed:
        changed_html = "<ul>" + "".join(f"<li>{_escape(path)}</li>" for path in changed) + "</ul>"
    return (
        "<article class='task-card'>"
        f"<header><strong>{_escape(task['id'])}</strong><span class='pill'>{_escape(task['scope'])}</span>"
        f"<span class='pill status-{_escape(str(task['status']).replace(' ', '-'))}'>{_escape(task['status'])}</span></header>"
        f"<p>{_escape(task['objective'])}</p>"
        f"<p class='muted'>{_escape(task['summary'])}</p>"
        f"{changed_html}"
        "</article>"
    )


def _pillar_card_html(pillar: dict[str, object]) -> str:
    return (
        "<article class='pillar-card'>"
        f"<header><strong>{_escape(pillar['name'])}</strong>"
        f"<span class='pill trajectory-{_escape(str(pillar['trajectory']).replace(' ', '-'))}'>{_escape(pillar['trajectory'])}</span>"
        f"<span class='pill'>{_escape(pillar['confidence'])}%</span></header>"
        f"<p>{_escape(pillar['current_state'])}</p>"
        f"<p class='muted'>Risk: {_escape(pillar['risk'])}</p>"
        "</article>"
    )


def _render_entry(entry: dict[str, object]) -> str:
    loop_counter = entry.get("loop_counter", "-")
    timestamp = entry.get("timestamp", "")
    body = _entry_body(entry)
    return f"<article class='entry'><header><strong>Loop {_escape(loop_counter)}</strong> <span>{_escape(timestamp)}</span></header><p>{_escape(body)}</p></article>"


def _entry_body(entry: dict[str, object]) -> str:
    entry_type = entry.get("entry_type")
    if entry_type == "loop":
        diary = entry.get("diary") or {}
        if isinstance(diary, dict) and diary.get("entry"):
            return str(diary.get("entry"))
        proposal = entry.get("proposal") or {}
        if isinstance(proposal, dict):
            return str(proposal.get("goal") or proposal.get("theme") or "Loop recorded.")
    if entry_type == "planning_phase":
        planning = entry.get("planning") or {}
        if isinstance(planning, dict):
            horizon_10 = planning.get("horizon_10") or {}
            if isinstance(horizon_10, dict) and horizon_10.get("theme"):
                return f"Planning checkpoint: {horizon_10['theme']}"
        return "Planning checkpoint recorded."
    return "Entry recorded."


def _escape(value: object) -> str:
    text = str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
