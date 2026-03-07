#!/usr/bin/env python3
"""Static site generator that reads memory state and outputs HTML journey page."""

import json
import os
from pathlib import Path
from datetime import datetime

# Mock memory state
MEMORY_STATE = {
    "journey_title": "Project Genesis",
    "blocks": [
        {
            "id": "block-001",
            "title": "Foundation Setup",
            "status": "completed",
            "progress": 100,
            "description": "Initial project structure and configuration",
            "timestamp": "2026-03-07T10:00:00"
        },
        {
            "id": "block-002",
            "title": "Core Implementation",
            "status": "in_progress",
            "progress": 65,
            "description": "Building core functionality and modules",
            "timestamp": "2026-03-07T11:30:00"
        },
        {
            "id": "block-003",
            "title": "Testing & Validation",
            "status": "pending",
            "progress": 0,
            "description": "Unit tests, integration tests, and validation",
            "timestamp": "2026-03-07T14:00:00"
        },
        {
            "id": "block-004",
            "title": "Documentation",
            "status": "pending",
            "progress": 0,
            "description": "API docs, user guides, and deployment instructions",
            "timestamp": "2026-03-07T16:00:00"
        }
    ],
    "summary": {
        "total_blocks": 4,
        "completed": 1,
        "in_progress": 1,
        "pending": 2,
        "overall_progress": 41
    },
    "last_updated": "2026-03-07T12:45:00"
}


def get_status_class(status: str) -> str:
    """Return CSS class based on block status."""
    status_map = {
        "completed": "status-completed",
        "in_progress": "status-in-progress",
        "pending": "status-pending"
    }
    return status_map.get(status, "status-pending")


def get_status_icon(status: str) -> str:
    """Return icon based on block status."""
    if status == "completed":
        return "✓"
    elif status == "in_progress":
        return "⋯"
    else:
        return "○"


def render_journey_html(state: dict) -> str:
    """Render the journey page HTML from memory state."""
    blocks_html = ""
    for block in state["blocks"]:
        status_class = get_status_class(block["status"])
        status_icon = get_status_icon(block["status"])
        blocks_html += f"""
        <div class="journey-block {status_class}">
            <div class="block-header">
                <span class="block-status-icon">{status_icon}</span>
                <h3 class="block-title">{block["title"]}</h3>
                <span class="block-id">{block["id"]}</span>
            </div>
            <p class="block-description">{block["description"]}</p>
            <div class="progress-container">
                <div class="progress-bar" style="width: {block['progress']}%"></div>
            </div>
            <span class="progress-text">{block["progress"]}% complete</span>
            <span class="block-timestamp">{block["timestamp"]}</span>
        </div>
"""

    summary = state["summary"]
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{state["journey_title"]} - Journey</title>
    <style>
        :root {{
            --bg-primary: #0f0f0f;
            --bg-secondary: #1a1a1a;
            --bg-block: #252525;
            --text-primary: #ffffff;
            --text-secondary: #a0a0a0;
            --text-muted: #666666;
            --accent-green: #00ff88;
            --accent-yellow: #ffcc00;
            --accent-gray: #4a4a4a;
            --border-color: #333333;
            --shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        
        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: var(--text-primary);
        }}
        
        .summary {{
            display: flex;
            gap: 2rem;
            margin-bottom: 1rem;
        }}
        
        .summary-stat {{
            text-align: center;
        }}
        
        .summary-value {{
            font-size: 2rem;
            font-weight: bold;
            color: var(--accent-green);
        }}
        
        .summary-label {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        .overall-progress {{
            margin-bottom: 2rem;
        }}
        
        .progress-bar-container {{
            background: var(--bg-secondary);
            border-radius: 4px;
            height: 8px;
            overflow: hidden;
            margin-top: 0.5rem;
        }}
        
        .progress-bar {{
            background: linear-gradient(90deg, var(--accent-green), #00cc6a);
            height: 100%;
            transition: width 0.3s ease;
        }}
        
        .journey-block {{
            background: var(--bg-block);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: var(--shadow);
        }}
        
        .journey-block.status-completed {{
            border-left: 4px solid var(--accent-green);
        }}
        
        .journey-block.status-in-progress {{
            border-left: 4px solid var(--accent-yellow);
        }}
        
        .journey-block.status-pending {{
            border-left: 4px solid var(--accent-gray);
            opacity: 0.7;
        }}
        
        .block-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }}
        
        .block-status-icon {{
            font-size: 1.25rem;
            min-width: 24px;
        }}
        
        .status-completed .block-status-icon {{
            color: var(--accent-green);
        }}
        
        .status-in-progress .block-status-icon {{
            color: var(--accent-yellow);
        }}
        
        .status-pending .block-status-icon {{
            color: var(--text-muted);
        }}
        
        .block-title {{
            flex: 1;
            font-size: 1.125rem;
        }}
        
        .block-id {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: monospace;
            background: var(--bg-secondary);
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
        }}
        
        .block-description {{
            color: var(--text-secondary);
            margin-bottom: 1rem;
        }}
        
        .progress-container {{
            background: var(--bg-secondary);
            border-radius: 4px;
            height: 6px;
            overflow: hidden;
            margin-bottom: 0.5rem;
        }}
        
        .progress-bar {{
            height: 100%;
            transition: width 0.3s ease;
        }}
        
        .status-completed .progress-bar {{
            background: var(--accent-green);
        }}
        
        .status-in-progress .progress-bar {{
            background: var(--accent-yellow);
        }}
        
        .status-pending .progress-bar {{
            background: var(--accent-gray);
        }}
        
        .progress-text {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        .block-timestamp {{
            float: right;
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: monospace;
        }}
        
        footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-color);
            text-align: center;
            color: var(--text-muted);
            font-size: 0.875rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{state["journey_title"]}</h1>
            <div class="summary">
                <div class="summary-stat">
                    <div class="summary-value">{summary["total_blocks"]}</div>
                    <div class="summary-label">Total Blocks</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-value" style="color: var(--accent-green);">{summary["completed"]}</div>
                    <div class="summary-label">Completed</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-value" style="color: var(--accent-yellow);">{summary["in_progress"]}</div>
                    <div class="summary-label">In Progress</div>
                </div>
                <div class="summary-stat">
                    <div class="summary-value" style="color: var(--text-muted);">{summary["pending"]}</div>
                    <div class="summary-label">Pending</div>
                </div>
            </div>
            <div class="overall-progress">
                <strong>Overall Progress:</strong> {summary["overall_progress"]}%
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: {summary["overall_progress"]}%"></div>
                </div>
            </div>
        </header>
        
        <main class="journey-list">
{blocks_html}
        </main>
        
        <footer>
            <p>Last updated: {state["last_updated"]}</p>
            <p>Generated by Generations Platform</p>
        </footer>
    </div>
</body>
</html>"""
    return html


def load_state_from_file(state_path: str) -> dict:
    """Load memory state from JSON file."""
    with open(state_path, 'r') as f:
        return json.load(f)


def generate_journey(state: dict | None = None, output_path: str | None = None) -> str:
    """Generate journey HTML from memory state."""
    if state is None:
        state = MEMORY_STATE
    
    html_content = render_journey_html(state)
    
    if output_path is None:
        output_path_obj = Path(__file__).parent / "templates" / "journey.html"
    else:
        output_path_obj = Path(output_path)
    
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path_obj, 'w') as f:
        f.write(html_content)
    
    print(f"Journey page generated: {output_path_obj}")
    return str(output_path_obj)


if __name__ == "__main__":
    generate_journey()
