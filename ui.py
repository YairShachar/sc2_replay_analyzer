"""
SC2 Replay Analyzer UI

Terminal UI using Rich library for formatted tables and output.
"""
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from config import (
    BENCHMARK_WORKERS_6M,
    BENCHMARK_WORKERS_8M,
    AVAILABLE_COLUMNS,
    DISPLAY_COLUMNS,
)

console = Console()


def format_duration(seconds: int) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    if seconds is None:
        return "-"
    minutes, secs = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_date(iso_date: str) -> str:
    """Format ISO date to readable format."""
    if not iso_date:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%b %d %H:%M")
    except (ValueError, AttributeError):
        return iso_date[:16] if iso_date else "-"


def format_workers(count: Optional[int], benchmark: int) -> Text:
    """Format worker count with warning if below benchmark."""
    if count is None:
        return Text("-", style="dim")
    text = Text(str(count))
    if count < benchmark:
        text.append(" !", style="bold red")
    return text


def format_result(result: str) -> Text:
    """Format result with color coding."""
    if not result:
        return Text("-")
    result_lower = result.lower()
    if result_lower == "win":
        return Text("Win", style="bold green")
    elif result_lower == "loss":
        return Text("Loss", style="bold red")
    return Text(result)


def format_army(supply: Optional[int], minerals: Optional[int]) -> str:
    """Format army as 'supply (value)'."""
    if supply is None:
        return "-"
    if minerals is None:
        return str(supply)
    # Format minerals in k if over 1000
    if minerals >= 1000:
        return f"{supply} ({minerals/1000:.1f}k)"
    return f"{supply} ({minerals})"


def format_mmr(player_mmr: Optional[int], opponent_mmr: Optional[int]) -> Text:
    """Format MMR comparison with color coding."""
    if player_mmr is None:
        return Text("-", style="dim")

    text = Text(str(player_mmr))
    if opponent_mmr:
        diff = player_mmr - opponent_mmr
        if diff > 0:
            text.append(f" (+{diff})", style="green")
        elif diff < 0:
            text.append(f" ({diff})", style="red")
    return text


def get_column_value(col_key: str, r: dict):
    """Get formatted value for a column key from a replay dict."""
    renderers = {
        "date": lambda: format_date(r.get("played_at")),
        "map": lambda: (r.get("map_name") or "-")[:14],
        "matchup": lambda: r.get("matchup") or "-",
        "result": lambda: format_result(r.get("result")),
        "mmr": lambda: format_mmr(r.get("player_mmr"), r.get("opponent_mmr")),
        "opponent_mmr": lambda: str(r.get("opponent_mmr") or "-"),
        "workers_6m": lambda: format_workers(r.get("workers_6m"), BENCHMARK_WORKERS_6M),
        "workers_8m": lambda: format_workers(r.get("workers_8m"), BENCHMARK_WORKERS_8M),
        "workers_10m": lambda: str(r.get("workers_10m") or "-"),
        "army": lambda: format_army(r.get("army_supply_8m"), r.get("army_minerals_8m")),
        "length": lambda: format_duration(r.get("game_length_sec")),
        "bases_6m": lambda: str(r.get("bases_by_6m") or "-"),
        "bases_8m": lambda: str(r.get("bases_by_8m") or "-"),
        "worker_kills": lambda: str(r.get("worker_kills_8m") or "0"),
        "worker_losses": lambda: str(r.get("worker_losses_8m") or "0"),
    }
    renderer = renderers.get(col_key, lambda: "-")
    return renderer()


def show_replays_table(replays: list):
    """Display replays in a rich table with configurable columns."""
    if not replays:
        console.print("[yellow]No replays found.[/yellow]")
        return

    table = Table(title="Recent Games", show_header=True, header_style="bold cyan")

    # Add columns dynamically from config
    for col_key in DISPLAY_COLUMNS:
        if col_key in AVAILABLE_COLUMNS:
            header, width, justify = AVAILABLE_COLUMNS[col_key]
            style = "dim" if col_key == "date" else None
            table.add_column(header, width=width, justify=justify, style=style)

    # Add rows
    for r in replays:
        row_values = [get_column_value(col_key, r) for col_key in DISPLAY_COLUMNS if col_key in AVAILABLE_COLUMNS]
        table.add_row(*row_values)

    console.print(table)
    console.print(f"\n[dim]Showing {len(replays)} game(s). '!' = below worker benchmark[/dim]")


def show_latest_game(replay: dict):
    """Display detailed stats for the latest game."""
    if not replay:
        console.print("[yellow]No replays found.[/yellow]")
        return

    result_style = "green" if replay.get("result", "").lower() == "win" else "red"

    header = Text()
    header.append(replay.get("result", "?"), style=f"bold {result_style}")
    header.append(f" vs {replay.get('matchup', '?')} on {replay.get('map_name', '?')}")

    lines = []
    lines.append(f"[bold]Game Length:[/bold] {format_duration(replay.get('game_length_sec'))}")
    lines.append(f"[bold]Played:[/bold] {format_date(replay.get('played_at'))}")

    # MMR
    player_mmr = replay.get("player_mmr")
    opponent_mmr = replay.get("opponent_mmr")
    if player_mmr:
        mmr_diff = player_mmr - opponent_mmr if opponent_mmr else 0
        diff_str = f" ([green]+{mmr_diff}[/green])" if mmr_diff > 0 else f" ([red]{mmr_diff}[/red])" if mmr_diff < 0 else ""
        lines.append(f"[bold]MMR:[/bold] {player_mmr} vs {opponent_mmr or '?'}{diff_str}")
    lines.append("")

    # Worker stats
    w6 = replay.get("workers_6m")
    w8 = replay.get("workers_8m")
    w10 = replay.get("workers_10m")

    w6_warning = " [red](!)[/red]" if w6 and w6 < BENCHMARK_WORKERS_6M else ""
    w8_warning = " [red](!)[/red]" if w8 and w8 < BENCHMARK_WORKERS_8M else ""

    lines.append("[bold cyan]Workers:[/bold cyan]")
    lines.append(f"  @6m: {w6 or '-'}{w6_warning}")
    lines.append(f"  @8m: {w8 or '-'}{w8_warning}")
    lines.append(f"  @10m: {w10 or '-'}")
    lines.append("")

    # Base timings
    lines.append("[bold cyan]Bases:[/bold cyan]")
    nat = replay.get("natural_timing")
    third = replay.get("third_timing")
    lines.append(f"  Natural: {format_duration(nat) if nat else '-'}")
    lines.append(f"  Third: {format_duration(third) if third else '-'}")
    lines.append("")

    # Army stats
    lines.append("[bold cyan]Army @8m:[/bold cyan]")
    lines.append(f"  Supply: {replay.get('army_supply_8m') or '-'}")
    lines.append(f"  Minerals: {replay.get('army_minerals_8m') or '-'}")
    lines.append(f"  Gas: {replay.get('army_gas_8m') or '-'}")
    lines.append("")

    # Combat stats
    lines.append("[bold cyan]First 8 Minutes:[/bold cyan]")
    lines.append(f"  Worker kills: {replay.get('worker_kills_8m') or 0}")
    lines.append(f"  Worker losses: {replay.get('worker_losses_8m') or 0}")
    first_attack = replay.get("first_attack_time")
    lines.append(f"  First attack: {format_duration(first_attack) if first_attack else '-'}")

    panel = Panel(
        "\n".join(lines),
        title=header,
        border_style=result_style,
    )
    console.print(panel)


def show_stats(stats: dict, matchup_stats: list, days: Optional[int] = None):
    """Display aggregate statistics."""
    title = "SC2 Stats"
    if days:
        title += f": Last {days} Days"
    else:
        title += ": All Time"

    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]")
    console.print()

    total = stats.get("total_games", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    winrate = (wins / total * 100) if total > 0 else 0

    # Overall stats
    console.print(f"  [bold]Games:[/bold] {total}  |  ", end="")
    console.print(f"[green]Wins: {wins}[/green] ({winrate:.1f}%)  |  ", end="")
    console.print(f"[red]Losses: {losses}[/red]")
    console.print()

    # Averages
    avg_w8 = stats.get("avg_workers_8m")
    avg_army = stats.get("avg_army_supply_8m")
    avg_length = stats.get("avg_game_length")

    if avg_w8 or avg_army or avg_length:
        console.print(f"  [bold]Avg Workers @8m:[/bold] {avg_w8:.1f}" if avg_w8 else "", end="  ")
        console.print(f"[bold]Avg Army @8m:[/bold] {avg_army:.1f}" if avg_army else "", end="  ")
        console.print(f"[bold]Avg Game:[/bold] {format_duration(int(avg_length))}" if avg_length else "")
        console.print()

    # By matchup
    if matchup_stats:
        table = Table(title="By Matchup", show_header=True, header_style="bold")
        table.add_column("Matchup", width=8)
        table.add_column("Games", width=6, justify="right")
        table.add_column("Winrate", width=8, justify="right")
        table.add_column("Avg W@8m", width=8, justify="right")

        for m in matchup_stats:
            games = m.get("total_games", 0)
            wins = m.get("wins", 0)
            wr = (wins / games * 100) if games > 0 else 0
            avg_w = m.get("avg_workers_8m")

            wr_style = "green" if wr >= 50 else "red"
            wr_text = Text(f"{wr:.0f}%", style=wr_style)

            table.add_row(
                m.get("matchup", "?"),
                str(games),
                wr_text,
                f"{avg_w:.1f}" if avg_w else "-",
            )

        console.print(table)

    console.print()


def show_scan_progress(current: int, total: int, filename: str):
    """Show scan progress."""
    console.print(f"[dim][{current}/{total}][/dim] {filename[:50]}", end="\r")


def show_scan_complete(new_count: int, total_count: int):
    """Show scan completion message."""
    console.print(" " * 80, end="\r")  # Clear progress line
    console.print(f"[green]Scan complete![/green] Added {new_count} new replay(s). Total: {total_count}")
