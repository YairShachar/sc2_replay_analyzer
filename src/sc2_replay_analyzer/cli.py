#!/usr/bin/env python3
"""
SC2 Replay Analyzer CLI

Analyze your StarCraft II replays with filtering, stats, and beautiful terminal output.

Usage:
    sc2                    # Auto-scan for new replays, then interactive mode
    sc2 show               # One-time query of recent games
    sc2 stats              # Show aggregate statistics
    sc2 scan               # Full scan with progress display
    sc2 config             # Re-run setup / change settings
    sc2 export             # Export to CSV
"""
import argparse
import csv
import sys
from pathlib import Path

from . import db
from .config import (
    config_exists,
    load_config,
    save_config,
    find_replay_folders,
    validate_player_name,
    get_player_name,
    get_replay_folder,
    DEFAULT_CONFIG,
)
from .parser import parse_replay, sha1
from . import ui


def find_replays(folder: str) -> list:
    """Find all .SC2Replay files in folder."""
    folder_path = Path(folder)
    if not folder_path.exists():
        ui.console.print(f"[red]Replay folder not found:[/red] {folder}")
        sys.exit(1)

    replays = list(folder_path.glob("*.SC2Replay"))
    return sorted(replays, key=lambda p: p.stat().st_mtime, reverse=True)


def auto_scan() -> int:
    """Automatically scan for new replays. Returns count of new replays found."""
    replay_folder = get_replay_folder()
    player_name = get_player_name()

    folder_path = Path(replay_folder)
    if not folder_path.exists():
        return 0

    replays = list(folder_path.glob("*.SC2Replay"))
    new_count = 0

    for replay_path in replays:
        replay_id = sha1(str(replay_path))
        if not db.replay_exists(replay_id):
            try:
                data = parse_replay(str(replay_path), player_name)
                if data:
                    db.insert_replay(data)
                    new_count += 1
            except Exception:
                pass  # Silently skip errors during auto-scan

    if new_count > 0:
        ui.console.print(f"[green]Found {new_count} new replay(s)[/green]")

    return new_count


def run_setup_wizard() -> bool:
    """
    Run the first-time setup wizard.
    Returns True if setup completed successfully.
    """
    ui.console.print()
    ui.console.print("[bold cyan]Welcome to SC2 Replay Analyzer![/bold cyan]")
    ui.console.print()
    ui.console.print("Let's set up your configuration.")
    ui.console.print()

    config = DEFAULT_CONFIG.copy()

    # Step 1: Find replay folder
    ui.console.print("[bold]Searching for SC2 replay folders...[/bold]")
    folders = find_replay_folders()

    if not folders:
        ui.console.print("[yellow]No replay folders found automatically.[/yellow]")
        ui.console.print()
        replay_folder = ui.console.input("Enter the path to your Replays/Multiplayer folder: ").strip()
        if not Path(replay_folder).exists():
            ui.console.print(f"[red]Folder not found:[/red] {replay_folder}")
            return False
    elif len(folders) == 1:
        ui.console.print(f"[green]Found:[/green] {folders[0]}")
        ui.console.print()
        use_it = ui.console.input("Use this folder? [Y/n]: ").strip().lower()
        if use_it in ('n', 'no'):
            replay_folder = ui.console.input("Enter the path to your Replays/Multiplayer folder: ").strip()
        else:
            replay_folder = folders[0]
    else:
        ui.console.print("[green]Found multiple replay folders:[/green]")
        for i, folder in enumerate(folders, 1):
            ui.console.print(f"  {i}. {folder}")
        ui.console.print()
        choice = ui.console.input(f"Choose folder [1-{len(folders)}]: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(folders):
                replay_folder = folders[idx]
            else:
                ui.console.print("[red]Invalid choice.[/red]")
                return False
        except ValueError:
            ui.console.print("[red]Invalid choice.[/red]")
            return False

    config["replay_folder"] = replay_folder
    ui.console.print()

    # Step 2: Get player name
    player_name = ui.console.input("Enter your SC2 player name: ").strip()
    if not player_name:
        ui.console.print("[red]Player name cannot be empty.[/red]")
        return False

    # Step 3: Validate player name
    ui.console.print()
    ui.console.print("[bold]Validating player name...[/bold]")
    found, checked = validate_player_name(player_name, replay_folder)

    if found > 0:
        ui.console.print(f"[green]Found {found} games as \"{player_name}\"[/green]")
    elif checked > 0:
        ui.console.print(f"[yellow]Warning: Player \"{player_name}\" not found in {checked} recent replays.[/yellow]")
        confirm = ui.console.input("Continue anyway? [y/N]: ").strip().lower()
        if confirm not in ('y', 'yes'):
            return False
    else:
        ui.console.print("[yellow]Could not validate player name (no replays found).[/yellow]")

    config["player_name"] = player_name

    # Save config
    save_config(config)
    ui.console.print()
    ui.console.print(f"[green]Configuration saved![/green]")
    ui.console.print()

    return True


def ensure_config():
    """Ensure config exists, running setup if needed."""
    if not config_exists():
        if not run_setup_wizard():
            sys.exit(1)


def cmd_config(args):
    """Run setup wizard to configure or reconfigure."""
    run_setup_wizard()


def cmd_scan(args):
    """Scan replay folder and add new replays to database."""
    ensure_config()
    db.init_db()

    replay_folder = get_replay_folder()
    player_name = get_player_name()

    replays = find_replays(replay_folder)
    if not replays:
        ui.console.print(f"[yellow]No replays found in:[/yellow] {replay_folder}")
        return

    ui.console.print(f"[cyan]Scanning {len(replays)} replay(s) in:[/cyan] {replay_folder}")
    ui.console.print(f"[cyan]Player:[/cyan] {player_name}")
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
            data = parse_replay(str(replay_path), player_name)
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
    ensure_config()
    db.init_db()

    replays = db.get_replays(
        matchup=args.matchup,
        result=args.result,
        map_name=args.map,
        days=args.days,
        limit=args.last or 20,
    )

    ui.show_replays_table(replays)
    ui.show_summary_row(replays)


def cmd_latest(args):
    """Show detailed stats for the most recent game."""
    ensure_config()
    db.init_db()

    replay = db.get_latest_replay()
    ui.show_latest_game(replay)


def cmd_stats(args):
    """Show aggregate statistics."""
    ensure_config()
    db.init_db()

    stats = db.get_stats(matchup=args.matchup, days=args.days)
    matchup_stats = db.get_stats_by_matchup(days=args.days) if not args.matchup else []

    ui.show_stats(stats, matchup_stats, days=args.days)


def cmd_export(args):
    """Export replays to CSV."""
    ensure_config()
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
    ensure_config()
    db.init_db()
    auto_scan()
    ui.run_interactive_mode()


def main():
    parser = argparse.ArgumentParser(
        description="SC2 Replay Analyzer - Track your StarCraft II progress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # config command
    config_parser = subparsers.add_parser("config", help="Configure or reconfigure settings")
    config_parser.set_defaults(func=cmd_config)

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

    # Default behavior: auto-scan and launch live mode
    if not args.command:
        if not config_exists():
            run_setup_wizard()
        ensure_config()
        db.init_db()
        auto_scan()
        ui.run_interactive_mode()
        return

    args.func(args)


if __name__ == "__main__":
    main()
