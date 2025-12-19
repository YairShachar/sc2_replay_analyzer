#!/usr/bin/env python3
"""
SC2 Replay Analyzer

Analyze your StarCraft II replays with filtering, stats, and beautiful terminal output.

Usage:
    python sc2_analyzer.py scan              # Scan replay folder for new games
    python sc2_analyzer.py show              # Show recent games
    python sc2_analyzer.py latest            # Show stats for most recent game
    python sc2_analyzer.py stats             # Show aggregate statistics
    python sc2_analyzer.py export            # Export to CSV
"""
import argparse
import csv
import os
import sys
from pathlib import Path

from config import REPLAY_FOLDER, PLAYER_NAME
import db
from parser import parse_replay, sha1
import ui


def find_replays(folder: str) -> list:
    """Find all .SC2Replay files in folder."""
    folder_path = Path(folder)
    if not folder_path.exists():
        ui.console.print(f"[red]Replay folder not found:[/red] {folder}")
        sys.exit(1)

    replays = list(folder_path.glob("*.SC2Replay"))
    return sorted(replays, key=lambda p: p.stat().st_mtime, reverse=True)


def cmd_scan(args):
    """Scan replay folder and add new replays to database."""
    db.init_db()

    replays = find_replays(REPLAY_FOLDER)
    if not replays:
        ui.console.print(f"[yellow]No replays found in:[/yellow] {REPLAY_FOLDER}")
        return

    ui.console.print(f"[cyan]Scanning {len(replays)} replay(s) in:[/cyan] {REPLAY_FOLDER}")
    ui.console.print(f"[cyan]Player:[/cyan] {PLAYER_NAME}")
    ui.console.print()

    new_count = 0
    skipped = 0
    errors = 0

    for i, replay_path in enumerate(replays, 1):
        ui.show_scan_progress(i, len(replays), replay_path.name)

        # Check if already in database (unless force)
        replay_id = sha1(str(replay_path))
        if not args.force and db.replay_exists(replay_id):
            skipped += 1
            continue

        try:
            data = parse_replay(str(replay_path))
            if data:
                db.insert_replay(data)
                new_count += 1
            else:
                # Player not found in replay
                skipped += 1
        except Exception as e:
            errors += 1
            if args.verbose:
                ui.console.print(f"\n[red]Error parsing {replay_path.name}:[/red] {e}")

    ui.show_scan_complete(new_count, db.get_replay_count())

    if errors > 0:
        ui.console.print(f"[yellow]Skipped {errors} replay(s) due to errors[/yellow]")
    if skipped > 0 and args.verbose:
        ui.console.print(f"[dim]Skipped {skipped} already-parsed or non-matching replay(s)[/dim]")


def cmd_show(args):
    """Show replays with optional filtering."""
    db.init_db()

    replays = db.get_replays(
        matchup=args.matchup,
        result=args.result,
        map_name=args.map,
        days=args.days,
        limit=args.last or 20,
    )

    ui.show_replays_table(replays)


def cmd_latest(args):
    """Show detailed stats for the most recent game."""
    db.init_db()

    replay = db.get_latest_replay()
    ui.show_latest_game(replay)


def cmd_stats(args):
    """Show aggregate statistics."""
    db.init_db()

    stats = db.get_stats(matchup=args.matchup, days=args.days)
    matchup_stats = db.get_stats_by_matchup(days=args.days) if not args.matchup else []

    ui.show_stats(stats, matchup_stats, days=args.days)


def cmd_export(args):
    """Export replays to CSV."""
    db.init_db()

    replays = db.get_replays(
        matchup=args.matchup,
        result=args.result,
        days=args.days,
        limit=args.last,
    )

    if not replays:
        ui.console.print("[yellow]No replays to export.[/yellow]")
        return

    output_path = args.out or "sc2_export.csv"

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=replays[0].keys())
        writer.writeheader()
        writer.writerows(replays)

    ui.console.print(f"[green]Exported {len(replays)} replay(s) to:[/green] {output_path}")


def cmd_live(args):
    """Run interactive filtering mode."""
    ui.run_interactive_mode()


def main():
    parser = argparse.ArgumentParser(
        description="SC2 Replay Analyzer - Track your StarCraft II progress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan replay folder for new games")
    scan_parser.add_argument("--force", action="store_true", help="Re-parse all replays")
    scan_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    scan_parser.set_defaults(func=cmd_scan)

    # show command
    show_parser = subparsers.add_parser("show", help="Show recent games")
    show_parser.add_argument("--matchup", "-m", help="Filter by matchup (TvZ, TvP, TvT)")
    show_parser.add_argument("--result", "-r", help="Filter by result (win, loss)")
    show_parser.add_argument("--map", help="Filter by map name (partial match)")
    show_parser.add_argument("--days", "-d", type=int, help="Only show games from last N days")
    show_parser.add_argument("--last", "-l", type=int, help="Show last N games (default: 20)")
    show_parser.set_defaults(func=cmd_show)

    # latest command
    latest_parser = subparsers.add_parser("latest", help="Show stats for most recent game")
    latest_parser.set_defaults(func=cmd_latest)

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show aggregate statistics")
    stats_parser.add_argument("--matchup", "-m", help="Filter by matchup (TvZ, TvP, TvT)")
    stats_parser.add_argument("--days", "-d", type=int, help="Only include games from last N days")
    stats_parser.set_defaults(func=cmd_stats)

    # export command
    export_parser = subparsers.add_parser("export", help="Export replays to CSV")
    export_parser.add_argument("--out", "-o", help="Output file path (default: sc2_export.csv)")
    export_parser.add_argument("--matchup", "-m", help="Filter by matchup")
    export_parser.add_argument("--result", "-r", help="Filter by result")
    export_parser.add_argument("--days", "-d", type=int, help="Only include games from last N days")
    export_parser.add_argument("--last", "-l", type=int, help="Export last N games")
    export_parser.set_defaults(func=cmd_export)

    # live command
    live_parser = subparsers.add_parser("live", help="Interactive filtering mode")
    live_parser.set_defaults(func=cmd_live)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
