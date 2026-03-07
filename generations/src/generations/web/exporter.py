from __future__ import annotations

from pathlib import Path

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.state import load_current_loop_plan, load_runtime_state
from generations.web.presentation import build_dashboard_context, entry_body, visible_journal_entries


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
    visible = visible_journal_entries(all_entries)
    memory_payload = memory if memory is not None else MemoryStore(config.memory_path).latest()
    runtime = load_runtime_state(config.runtime_path).as_dict()
    current_loop_plan = load_current_loop_plan(config.current_loop_plan_path) or memory_payload.get("current_loop_plan") or {}
    dashboard = build_dashboard_context(runtime, current_loop_plan, memory_payload, visible)
    html = _render_html(dashboard, [{**entry, "body": entry_body(entry)} for entry in visible])
    (output / "index.html").write_text(html, encoding="utf-8")
    style_source = Path(__file__).resolve().parent / "static" / "style.css"
    (output / "style.css").write_text(style_source.read_text(encoding="utf-8"), encoding="utf-8")
    return output


def _render_html(dashboard: dict[str, object], entries: list[dict[str, object]]) -> str:
    hero = dashboard["hero"]
    now = dashboard["now"]
    vision = dashboard["vision"]
    block = dashboard["block"]
    current_loop = dashboard["current_loop"]
    retrospective = dashboard["retrospective"]
    support = dashboard["support"]
    diary = dashboard["diary"]
    task_cards = "".join(_task_card_html(task) for task in current_loop["tasks"]) or "<p>No active execution tasks.</p>"
    pillar_cards = "".join(_pillar_card_html(pillar) for pillar in dashboard["pillars"])
    metric_cards = "".join(
        f"<article class='metric-card'><span class='metric-name'>{_escape(metric['name'])}</span><strong class='metric-value'>{_escape(metric['value'])}%</strong><p class='muted'>{_escape(metric['hint'])}</p></article>"
        for metric in dashboard["metrics"]
    )
    vision_cards = "".join(
        f"<article class='pillar-card'><header><strong>{_escape(pillar['name'])}</strong></header><p>{_escape(pillar['summary'])}</p><p class='muted'>{_escape(pillar['good_end_state'])}</p></article>"
        for pillar in vision["pillars"]
    ) or "<p>No long-term vision recorded yet.</p>"
    diary_entries = "".join(_render_entry(entry) for entry in entries) or "<p>No entries yet.</p>"
    outcomes = "".join(f"<li>{_escape(item)}</li>" for item in block["outcomes"]) or "<li>No target outcomes recorded yet.</li>"
    support_work = "".join(f"<li>{_escape(item)}</li>" for item in block["support_work"]) or "<li>No support work recorded yet.</li>"
    non_goals = "".join(f"<li>{_escape(item)}</li>" for item in block["non_goals"]) or "<li>No non-goals recorded yet.</li>"
    review_focus = "".join(f"<li>{_escape(item)}</li>" for item in block["review_focus"]) or "<li>No review focus recorded yet.</li>"
    retro_wins = "".join(f"<li>{_escape(item)}</li>" for item in retrospective["wins"]) or "<li>No wins recorded yet.</li>"
    retro_stalls = "".join(f"<li>{_escape(item)}</li>" for item in retrospective["stalls"]) or "<li>No stalls recorded yet.</li>"
    retro_change = "".join(f"<li>{_escape(item)}</li>" for item in retrospective["change_next_time"]) or "<li>No next changes recorded yet.</li>"
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
      <h1>{_escape(hero['game_name']).replace('_', ' ').title()}</h1>
      <p class='lede'>{_escape(hero['thesis'])}</p>
      <div class='status-strip'>
        <span>Loop {_escape(hero['loop_count'])}</span>
        <span>Vision v{_escape(hero['vision_version'])}</span>
        <span>Validation: {_escape(hero['last_validation'])}</span>
        <span>Model: {_escape(hero['model'])}</span>
      </div>
    </section>

    <section class='grid top-grid'>
      <article class='card'>
        <h2>Now</h2>
        <p><strong>Current block:</strong> {_escape(now['block_id'])}</p>
        <p><strong>Primary pillar:</strong> {_escape(now['primary_pillar']).replace('_', ' ')}</p>
        <p><strong>Execution range:</strong> {_escape(now['execution_range'])}</p>
        <p>{_escape(now['why_now'])}</p>
        <div class='pill-row'>
          <span class='pill'>Passes {_escape(now['pass_count'])}</span>
          <span class='pill'>Fails {_escape(now['fail_count'])}</span>
          <span class='pill'>Rests {_escape(now['rest_count'])}</span>
        </div>
      </article>

      <article class='card'>
        <h2>Current Loop</h2>
        <p class='feature-title'>{_escape(current_loop['theme'])}</p>
        <p>{_escape(current_loop['goal'])}</p>
        <p><strong>Working on:</strong> {_escape(current_loop['working_on'])}</p>
        {"<p><strong>Loop drift:</strong> " + _escape(current_loop['block_alignment']) + (f" - {_escape(current_loop['drift_reason'])}" if current_loop['drift_reason'] else "") + "</p>" if current_loop['block_alignment'] != 'aligned' else ""}
        <div class='pill-row'>
          <span class='pill'>Integration {_escape(current_loop['integration_status'])}</span>
          <span class='pill'>Validation {_escape(current_loop['validation_status'])}</span>
        </div>
        <p class='muted'>{_escape(current_loop['summary'])}</p>
      </article>

      <article class='card'>
        <h2>Long-Term Vision</h2>
        <p>{_escape(vision['index_summary'])}</p>
        <p class='muted'>Last refined loop: {_escape(vision['last_refined_loop'])}</p>
      </article>

      <article class='card'>
        <h2>Support</h2>
        <p>{_escape(support['summary'])}</p>
        <p class='muted'>{_escape(support['disclosure'])}</p>
        <p><strong>Current experiment:</strong> {_escape(support['current_experiment'])}</p>
      </article>
    </section>

    <section class='card wide'>
      <h2>Current Block</h2>
      <p class='feature-title'>{_escape(block['title'])} focused on {_escape(block['primary_pillar'])}</p>
      <div class='grid two-up'>
        <div><h3>Target Outcomes</h3><ul>{outcomes}</ul></div>
        <div><h3>Allowed Support Work</h3><ul>{support_work}</ul></div>
        <div><h3>Explicit Non Goals</h3><ul>{non_goals}</ul></div>
        <div><h3>Review Focus</h3><ul>{review_focus}</ul></div>
      </div>
    </section>

    <section class='card wide'>
      <h2>Current Tasks</h2>
      <div class='task-grid'>{task_cards}</div>
    </section>

    <section class='card wide'>
      <h2>Pillar Visions</h2>
      <div class='pillar-grid'>{vision_cards}</div>
    </section>

    <section class='card wide'>
      <h2>Pillar Health</h2>
      <div class='pillar-grid'>{pillar_cards}</div>
    </section>

    <section class='card wide'>
      <h2>Retrospective</h2>
      <p>{_escape(retrospective['summary'])}</p>
      <div class='grid two-up'>
        <div><h3>Wins</h3><ul>{retro_wins}</ul></div>
        <div><h3>Stalls</h3><ul>{retro_stalls}</ul></div>
        <div><h3>Change Next Time</h3><ul>{retro_change}</ul></div>
      </div>
    </section>

    <section class='card wide metrics-card'>
      <h2>Metrics As Signals</h2>
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
    changed = task.get('changed_files') or []
    changed_html = ''
    if changed:
        changed_html = '<ul>' + ''.join(f"<li>{_escape(path)}</li>" for path in changed) + '</ul>'
    return (
        "<article class='task-card'>"
        f"<header><strong>{_escape(task['id'])}</strong><span class='pill'>{_escape(task['route'])}</span>"
        f"<span class='pill'>{_escape(task['intent_label'])}</span>"
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
    return f"<article class='entry'><header><strong>Loop {_escape(entry.get('loop_counter', '-'))}</strong> <span>{_escape(entry.get('timestamp', ''))}</span></header><p>{_escape(entry.get('body', 'Entry recorded.'))}</p></article>"


def _escape(value: object) -> str:
    text = str(value)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
