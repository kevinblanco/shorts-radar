"""shorts-radar run "ai agents"    find and score this week's Shorts in a niche
shorts-radar show "ai agents"   print a saved run again, without spending searches
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from rich.console import Console

from . import collect, report
from .models import Budget
from .score import score
from .serp import Serp, SerpError

console = Console(highlight=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="shorts-radar", description="Find the YouTube Shorts that beat their own channel.")
    commands = parser.add_subparsers(dest="command", required=True)

    run_cmd = commands.add_parser("run", help="collect, score and save a niche")
    run_cmd.add_argument("niche", help='a seed topic, e.g. "ai agents"')
    defaults = Budget()
    run_cmd.add_argument("--keywords", type=int, default=defaults.keywords, help="related searches from Google Trends")
    run_cmd.add_argument("--details", type=int, default=defaults.details, help="Shorts to look up in detail")
    run_cmd.add_argument("--channels", type=int, default=defaults.channels, help="channels to baseline")
    run_cmd.add_argument("--hooks", type=int, default=defaults.hooks, help="top Shorts whose opening lines to read")
    run_cmd.add_argument("--data", type=Path, default=Path("data"), help="where runs and the cache live")
    run_cmd.add_argument("--refresh", action="store_true", help="ignore cached responses")
    run_cmd.add_argument("--estimate", action="store_true", help="print the search budget and stop")

    show_cmd = commands.add_parser("show", help="print a saved run")
    show_cmd.add_argument("niche", help="the niche, or a path to a shorts.json")
    show_cmd.add_argument("--data", type=Path, default=Path("data"))

    args = parser.parse_args(argv)
    try:
        run(args) if args.command == "run" else show(args)
    except SerpError as error:
        console.print(f"[red]{error}[/]")
        sys.exit(1)


def run(args: argparse.Namespace) -> None:
    budget = Budget(args.keywords, args.details, args.channels, args.hooks)
    if args.estimate:
        console.print(f"A run spends up to {budget.max_searches()} searches; anything already cached is free.")
        return

    def on_call(engine: str, label: str, cached: bool) -> None:
        count = "[dim]cached[/]" if cached else f"[magenta]{serp.live:>3}[/]"
        console.print(f"   {engine:<25} {label[:52]:<52} {count}")

    serp = Serp.from_env(args.data / "cache", refresh=args.refresh, on_call=on_call)
    left = serp.searches_left()
    console.print(
        f"[bold]shorts-radar[/] · {args.niche} · up to {budget.max_searches()} searches"
        + (f" · {left} left this month" if left is not None else "")
    )

    step("What people search on YouTube around this topic")
    keywords = collect.related_keywords(serp, args.niche, budget.keywords)

    step(f"The Shorts YouTube shows for {len(keywords)} searches")
    found = collect.discover_shorts(serp, keywords)
    console.print(f"   [dim]{len(found)} different Shorts[/]")

    picked = collect.pick_for_details(found, budget.details)
    step(f"Views, dates and channel size for the top {len(picked)}")
    collect.add_details(serp, picked, date.today())

    step("What normal looks like on each channel")
    collect.add_baselines(serp, picked, budget.channels)

    ranked = score(found)
    step(f"How the top {budget.hooks} open, word for word")
    collect.add_hooks(serp, ranked, budget.hooks)

    searches = {"live": serp.live, "cached": serp.cached}
    data = report.build_dataset(args.niche, keywords, ranked, searches)
    json_path, md_path = report.write_run(args.data / report.slugify(args.niche), data)

    console.print()
    report.print_table(console, ranked)
    console.print()
    console.print(f"[bold]{serp.live}[/] searches spent, {serp.cached} from cache. Saved {json_path} and {md_path}.")


def show(args: argparse.Namespace) -> None:
    path = Path(args.niche)
    if path.suffix != ".json":
        path = args.data / report.slugify(args.niche) / "shorts.json"
    if not path.exists():
        raise SerpError(f"No saved run at {path}. Run: shorts-radar run \"{args.niche}\"")
    data, shorts = report.load_dataset(path)
    console.print(f"[bold]{data['niche']}[/] · collected {data['collected_at'][:10]} · {data['counts']['scored']} Shorts scored")
    console.print()
    report.print_table(console, shorts)


def step(text: str) -> None:
    console.print(f"\n[bold]{text}[/]")
