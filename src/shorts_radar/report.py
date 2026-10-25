"""Step 3: write the run down where people and agents can read it.

  shorts.json   every Short with its numbers, scores and hook (the agent's input)
  snapshot.md   the niche at a glance, for people
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .collect import words
from .models import Short


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "niche"


def cell(text: str) -> str:
    """Text that can sit in a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def compact(n: float | None) -> str:
    if n is None:
        return "–"
    for size, unit in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= size:
            return f"{n / size:.1f}".rstrip("0").rstrip(".") + unit
    return f"{n:.0f}" if n >= 10 or n == int(n) else f"{n:.1f}"


def times(x: float | None) -> str:
    if x is None:
        return "–"
    return f"{x:.0f}×" if x >= 10 else f"{x:.1f}×"


def build_dataset(niche: str, keywords: list[str], shorts: list[Short], searches: dict, collected_at: datetime | None = None) -> dict:
    collected_at = collected_at or datetime.now(timezone.utc)
    return {
        "niche": niche,
        "collected_at": collected_at.isoformat(timespec="seconds"),
        "keywords": keywords,
        "searches": searches,
        "counts": {
            "found": len(shorts),
            "looked_up": sum(1 for s in shorts if s.published),
            "with_baseline": sum(1 for s in shorts if s.channel_median_views),
            "scored": sum(1 for s in shorts if s.radar_score is not None),
            "with_hook": sum(1 for s in shorts if s.hook),
        },
        "shorts": [s.to_dict() for s in shorts],
    }


def load_dataset(path: Path) -> tuple[dict, list[Short]]:
    data = json.loads(path.read_text())
    return data, [Short.from_dict(s) for s in data["shorts"]]


def write_run(run_dir: Path, data: dict) -> tuple[Path, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "shorts.json"
    md_path = run_dir / "snapshot.md"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    md_path.write_text(snapshot_markdown(data))
    return json_path, md_path


def snapshot_markdown(data: dict, top: int = 10) -> str:
    shorts = [Short.from_dict(s) for s in data["shorts"]]
    scored = [s for s in shorts if s.radar_score is not None][:top]
    counts = data["counts"]
    day = data["collected_at"][:10]
    searches = data["searches"]
    lines = [
        f"# Shorts radar: {data['niche']}",
        "",
        f"Collected {day} from {searches['live'] + searches['cached']} SerpApi responses "
        f"({searches['live']} fetched in this run, {searches['cached']} from the local cache). "
        f"YouTube searches: {', '.join(data['keywords'])}.",
        f"{counts['found']} Shorts found, {counts['looked_up']} looked up, {counts['with_baseline']} judged against their own channel.",
        "",
        f"## Top {len(scored)} by radar score",
        "",
        "| # | Short | Channel | Views | × its channel | Views/day | Views/sub | Score |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, s in enumerate(scored, 1):
        lines.append(
            f"| {i} | [{cell(s.title)}]({s.url}) | {cell(s.channel_name or '–')} | {compact(s.views)} | {times(s.vs_channel)} "
            f"| {compact(s.views_per_day)} | {times(s.views_per_sub)} | {s.radar_score:.0f} |"
        )

    hooked = [s for s in scored if s.hook]
    if hooked:
        lines += ["", f"## Hooks of the top {len(hooked)}", ""]
        for s in hooked:
            hook = s.hook if s.hook.rstrip().endswith((".", "!", "?")) else f"{s.hook}…"
            lines += [f"> \"{hook}\"", ">", f"> [{s.title}]({s.url}), {compact(s.views)} views", ""]

    lines += ["", "## Patterns", "", *patterns(scored), ""]
    return "\n".join(lines)


def patterns(top: list[Short]) -> list[str]:
    """A few plain observations about the top Shorts. Heuristics, labelled as such."""
    if not top:
        return ["- Not enough scored Shorts to see a pattern."]
    out = []
    ages = sorted(s.age_days for s in top if s.age_days is not None)
    if ages:
        recent = sum(1 for a in ages if a <= 30)
        out.append(f"- Posted in the last 30 days: {recent} of the top {len(top)}. Median age: {ages[len(ages) // 2]} days.")
    counter = Counter(w for s in top for w in words(s.title) if len(w) > 2)
    shared = [w for w, n in counter.most_common(8) if n >= 3]
    if shared:
        out.append(f"- Title words in three or more of the top {len(top)}: {', '.join(shared)}.")
    hooks = [s.hook for s in top if s.hook]
    silent = sum(1 for s in top if s.spoken is False)
    if hooks:
        questions = sum(1 for h in hooks if "?" in h)
        out.append(f"- Spoken hooks: {questions} of {len(hooks)} open with a question.")
    if silent:
        out.append(f"- No transcript (likely text on screen or music, so the hook is visual): {silent} of the Shorts checked.")
    out.append("- These are observations from one run, not rules. Check them against the Shorts themselves.")
    return out


def clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def print_table(console: Console, shorts: list[Short], limit: int = 15) -> None:
    # The numbers keep their width; the title and channel give way in a narrow terminal.
    title_width = max(16, min(46, console.width - 76))
    channel_width = max(12, min(22, console.width - 56 - title_width))
    table = Table(header_style="bold", box=None, pad_edge=False, show_edge=False)
    for name, justify in (("#", "right"), ("Short", "left"), ("Channel", "left"), ("Views", "right"),
                          ("× channel", "right"), ("/day", "right"), ("/sub", "right"), ("Score", "right")):
        table.add_column(name, justify=justify, no_wrap=True)
    for i, s in enumerate((s for s in shorts if s.radar_score is not None), 1):
        if i > limit:
            break
        table.add_row(str(i), clip(s.title, title_width), clip(s.channel_name or "–", channel_width), compact(s.views),
                      times(s.vs_channel), compact(s.views_per_day), times(s.views_per_sub), f"[bold magenta]{s.radar_score:.0f}[/]")
    console.print(table)
