"""
SC2 Replay Analyzer UI

Terminal UI using Rich library for formatted tables and output.
"""
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .commands import CommandKey, FILTER_COMMANDS, SIMPLE_COMMANDS
from .completer import SC2Completer
from .config import (
    get_benchmark_workers_6m,
    get_benchmark_workers_8m,
    get_config_dir,
    get_display_columns,
    add_display_columns,
    remove_display_columns,
    reset_display_columns,
    AVAILABLE_COLUMNS,
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
    benchmark_6m = get_benchmark_workers_6m()
    benchmark_8m = get_benchmark_workers_8m()

    renderers = {
        "date": lambda: format_date(r.get("played_at")),
        "map": lambda: (r.get("map_name") or "-")[:14],
        "opponent": lambda: (r.get("opponent_name") or "-")[:16],
        "matchup": lambda: r.get("matchup") or "-",
        "result": lambda: format_result(r.get("result")),
        "mmr": lambda: format_mmr(r.get("player_mmr"), r.get("opponent_mmr")),
        "opponent_mmr": lambda: str(r.get("opponent_mmr") or "-"),
        "apm": lambda: str(r.get("player_apm") or "-"),
        "opponent_apm": lambda: str(r.get("opponent_apm") or "-"),
        "workers_6m": lambda: format_workers(r.get("workers_6m"), benchmark_6m),
        "workers_8m": lambda: format_workers(r.get("workers_8m"), benchmark_8m),
        "workers_10m": lambda: str(r.get("workers_10m") or "-"),
        "army": lambda: format_army(r.get("army_supply_8m"), r.get("army_minerals_8m")),
        "length": lambda: format_duration(r.get("game_length_sec")),
        "bases_6m": lambda: str(r.get("bases_by_6m") or "-"),
        "bases_8m": lambda: str(r.get("bases_by_8m") or "-"),
        "bases_10m": lambda: str(r.get("bases_by_10m") or "-"),
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

    display_columns = get_display_columns()
    table = Table(title="Recent Games", show_header=True, header_style="bold cyan")

    # Add columns dynamically from config
    for col_key in display_columns:
        if col_key in AVAILABLE_COLUMNS:
            header, width, justify = AVAILABLE_COLUMNS[col_key]
            style = "dim" if col_key == "date" else None
            table.add_column(header, width=width, justify=justify, style=style)

    # Add rows
    for r in replays:
        row_values = [get_column_value(col_key, r) for col_key in display_columns if col_key in AVAILABLE_COLUMNS]
        table.add_row(*row_values)

    console.print(table)


def show_latest_game(replay: dict):
    """Display detailed stats for the latest game."""
    if not replay:
        console.print("[yellow]No replays found.[/yellow]")
        return

    benchmark_6m = get_benchmark_workers_6m()
    benchmark_8m = get_benchmark_workers_8m()

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

    # APM
    player_apm = replay.get("player_apm")
    opponent_apm = replay.get("opponent_apm")
    if player_apm:
        lines.append(f"[bold]APM:[/bold] {player_apm} vs {opponent_apm or '?'}")
    lines.append("")

    # Worker stats
    w6 = replay.get("workers_6m")
    w8 = replay.get("workers_8m")
    w10 = replay.get("workers_10m")

    w6_warning = " [red](!)[/red]" if w6 and w6 < benchmark_6m else ""
    w8_warning = " [red](!)[/red]" if w8 and w8 < benchmark_8m else ""

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


def calculate_summary(replays: list) -> dict:
    """Calculate summary statistics for a list of replays."""
    if not replays:
        return {}

    wins = sum(1 for r in replays if (r.get("result") or "").lower() == "win")
    losses = sum(1 for r in replays if (r.get("result") or "").lower() == "loss")
    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0

    # Calculate averages, excluding None values
    apms = [r.get("player_apm") for r in replays if r.get("player_apm") is not None]
    workers = [r.get("workers_8m") for r in replays if r.get("workers_8m") is not None]
    lengths = [r.get("game_length_sec") for r in replays if r.get("game_length_sec") is not None]

    return {
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "avg_apm": sum(apms) / len(apms) if apms else None,
        "avg_workers_8m": sum(workers) / len(workers) if workers else None,
        "avg_length": sum(lengths) / len(lengths) if lengths else None,
    }


def show_summary_row(replays: list):
    """Display summary statistics below the table."""
    stats = calculate_summary(replays)
    if not stats:
        return

    parts = []

    # Win/Loss ratio with color
    wins, losses = stats["wins"], stats["losses"]
    winrate = stats["winrate"]
    wr_style = "green" if winrate >= 50 else "red"
    parts.append(f"[green]{wins}W[/green] / [red]{losses}L[/red] ([{wr_style}]{winrate:.1f}%[/{wr_style}])")

    # Averages
    if stats["avg_apm"] is not None:
        parts.append(f"Avg APM: {stats['avg_apm']:.0f}")

    if stats["avg_workers_8m"] is not None:
        parts.append(f"Avg W@8m: {stats['avg_workers_8m']:.0f}")

    if stats["avg_length"] is not None:
        parts.append(f"Avg Length: {format_duration(int(stats['avg_length']))}")

    console.print("  " + "  |  ".join(parts))


# ============================================================
# INTERACTIVE MODE
# ============================================================

@dataclass
class FilterState:
    """Holds the current filter state for interactive mode."""
    limit: int = 50
    matchup: Optional[str] = None
    result: Optional[str] = None
    map_name: Optional[str] = None
    days: Optional[int] = None
    min_length: Optional[int] = None  # seconds
    max_length: Optional[int] = None
    min_workers_8m: Optional[int] = None
    max_workers_8m: Optional[int] = None
    streak_type: Optional[str] = None  # "win" or "loss"
    min_streak_length: Optional[int] = None
    prev_games: int = 0  # Number of previous games to add
    next_games: int = 0  # Number of next games to add

    def describe(self, count: int) -> str:
        """Return human-readable filter description."""
        # Start with base description
        parts = []

        # Game type
        if self.matchup:
            parts.append(f"{self.matchup} games")
        elif self.result:
            result_word = "wins" if self.result.lower() == "win" else "losses"
            parts.append(result_word)
        else:
            parts.append("games")

        # Add result if we have matchup
        if self.matchup and self.result:
            result_word = "wins" if self.result.lower() == "win" else "losses"
            parts[-1] = f"{self.matchup} {result_word}"

        # Map filter
        if self.map_name:
            parts.append(f"on '{self.map_name}'")

        # Time filters
        if self.days:
            parts.append(f"from last {self.days} days")

        # Length filters
        length_parts = []
        if self.min_length:
            mins = self.min_length // 60
            secs = self.min_length % 60
            length_parts.append(f"> {mins}:{secs:02d}")
        if self.max_length:
            mins = self.max_length // 60
            secs = self.max_length % 60
            length_parts.append(f"< {mins}:{secs:02d}")
        if length_parts:
            parts.append(f"length {', '.join(length_parts)}")

        # Worker filters
        worker_parts = []
        if self.min_workers_8m:
            worker_parts.append(f"> {self.min_workers_8m}")
        if self.max_workers_8m:
            worker_parts.append(f"< {self.max_workers_8m}")
        if worker_parts:
            parts.append(f"workers@8m {', '.join(worker_parts)}")

        # Streak filter
        if self.streak_type and self.min_streak_length:
            streak_ending = "loss" if self.streak_type == "win" else "win"
            parts.append(f"{self.min_streak_length}+ {self.streak_type} streaks (ending with {streak_ending})")

        # Prev/next games
        expand_parts = []
        if self.prev_games > 0:
            expand_parts.append(f"+{self.prev_games} prev")
        if self.next_games > 0:
            expand_parts.append(f"+{self.next_games} next")
        if expand_parts:
            parts.append(f"({', '.join(expand_parts)})")

        # Build final string
        base = parts[0]
        modifiers = parts[1:] if len(parts) > 1 else []

        result = f"Showing {count} {base}"
        if modifiers:
            result += ", " + ", ".join(modifiers)

        return result

    def reset(self):
        """Reset all filters to defaults."""
        self.matchup = None
        self.result = None
        self.map_name = None
        self.days = None
        self.min_length = None
        self.max_length = None
        self.min_workers_8m = None
        self.max_workers_8m = None
        self.streak_type = None
        self.min_streak_length = None
        self.prev_games = 0
        self.next_games = 0
        self.limit = 50


def parse_time(time_str: str) -> int:
    """Parse time string like '8:00' or '8' to seconds."""
    if ':' in time_str:
        parts = time_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    return int(time_str) * 60  # Assume minutes if no colon


def parse_filter_command(cmd: str, state: FilterState) -> tuple:
    """
    Parse a filter command and update state.
    Returns (state, error_message or None)
    """
    cmd = cmd.strip()

    if not cmd:
        return state, None

    if cmd.lower() in ('clear', 'reset'):
        state.reset()
        return state, None

    if cmd.lower() in ('h', 'help', '?'):
        return state, "HELP"

    # Parse -n/--limit <num>
    cmd_def = FILTER_COMMANDS[CommandKey.LIMIT]
    match = re.match(cmd_def.build_regex(), cmd)
    if match:
        state.limit = int(match.group(1))
        return state, None

    # Parse -m/--matchup <matchup>
    cmd_def = FILTER_COMMANDS[CommandKey.MATCHUP]
    flags = 0 if cmd_def.case_sensitive else re.IGNORECASE
    match = re.match(cmd_def.build_regex(), cmd, flags)
    if match:
        matchup = match.group(1).upper()
        # Normalize: tvz -> TvZ
        if len(matchup) == 3 and matchup[1] == 'V':
            matchup = f"{matchup[0]}v{matchup[2]}"
        state.matchup = matchup
        return state, None

    # Parse -r/--result <result> (W/L/win/loss)
    cmd_def = FILTER_COMMANDS[CommandKey.RESULT]
    flags = 0 if cmd_def.case_sensitive else re.IGNORECASE
    match = re.match(cmd_def.build_regex(), cmd, flags)
    if match:
        result = match.group(1).lower()
        if result in ('w', 'win'):
            state.result = 'Win'
        elif result in ('l', 'loss'):
            state.result = 'Loss'
        else:
            state.result = result.capitalize()
        return state, None

    # Parse -l/--length <op><time> (e.g., -l >8:00, --length <5:00)
    cmd_def = FILTER_COMMANDS[CommandKey.LENGTH]
    match = re.match(cmd_def.build_regex(), cmd)
    if match:
        op, time_str = match.groups()
        seconds = parse_time(time_str)
        if op in ('>', '>='):
            state.min_length = seconds
            # Clear max if it conflicts (max < new min)
            if state.max_length is not None and state.max_length < seconds:
                state.max_length = None
        else:
            state.max_length = seconds
            # Clear min if it conflicts (min > new max)
            if state.min_length is not None and state.min_length > seconds:
                state.min_length = None
        return state, None

    # Parse -w/--workers <op><num> (e.g., -w <40, --workers >50)
    cmd_def = FILTER_COMMANDS[CommandKey.WORKERS]
    match = re.match(cmd_def.build_regex(), cmd)
    if match:
        op, num = match.groups()
        value = int(num)
        if op in ('>', '>='):
            state.min_workers_8m = value
            # Clear max if it conflicts (max < new min)
            if state.max_workers_8m is not None and state.max_workers_8m < value:
                state.max_workers_8m = None
        else:
            state.max_workers_8m = value
            # Clear min if it conflicts (min > new max)
            if state.min_workers_8m is not None and state.min_workers_8m > value:
                state.min_workers_8m = None
        return state, None

    # Parse --map <name>
    cmd_def = FILTER_COMMANDS[CommandKey.MAP]
    flags = 0 if cmd_def.case_sensitive else re.IGNORECASE
    match = re.match(cmd_def.build_regex(), cmd, flags)
    if match:
        state.map_name = match.group(1).strip()
        return state, None

    # Parse -d/--days <days>
    cmd_def = FILTER_COMMANDS[CommandKey.DAYS]
    match = re.match(cmd_def.build_regex(), cmd)
    if match:
        state.days = int(match.group(1))
        return state, None

    # Parse -s/--streaks win:3+ or loss:3+ (streak filter)
    cmd_def = FILTER_COMMANDS[CommandKey.STREAKS]
    flags = 0 if cmd_def.case_sensitive else re.IGNORECASE
    match = re.match(cmd_def.build_regex(), cmd, flags)
    if match:
        state.streak_type = match.group(1).lower()
        state.min_streak_length = int(match.group(2))
        return state, None

    # Parse +p/--prev <num> (add previous games - cumulative)
    cmd_def = FILTER_COMMANDS[CommandKey.PREV]
    match = re.match(cmd_def.build_regex(), cmd)
    if match:
        state.prev_games += int(match.group(1))
        return state, None

    # Parse +n/--next <num> (add next games - cumulative)
    cmd_def = FILTER_COMMANDS[CommandKey.NEXT]
    match = re.match(cmd_def.build_regex(), cmd)
    if match:
        state.next_games += int(match.group(1))
        return state, None

    # Parse columns commands
    if cmd.lower() == 'columns':
        return state, "COLUMNS"

    match = re.match(r'columns\s+add\s+(.+)', cmd, re.IGNORECASE)
    if match:
        cols = match.group(1).split()
        added = add_display_columns(cols)
        if added:
            console.print(f"[green]Added:[/green] {', '.join(added)}")
        else:
            console.print("[yellow]No columns added (already present or invalid)[/yellow]")
        return state, None

    match = re.match(r'columns\s+remove\s+(.+)', cmd, re.IGNORECASE)
    if match:
        cols = match.group(1).split()
        removed = remove_display_columns(cols)
        if removed:
            console.print(f"[green]Removed:[/green] {', '.join(removed)}")
        else:
            console.print("[yellow]No columns removed (not present)[/yellow]")
        return state, None

    if cmd.lower() == 'columns reset':
        reset_display_columns()
        console.print("[green]Columns reset to defaults[/green]")
        return state, None

    return state, f"Unknown command: {cmd}"


def show_columns():
    """Display available columns with current selection."""
    current_columns = get_display_columns()
    console.print()
    console.print("[bold cyan]Available columns:[/bold cyan]")
    console.print("[dim](* = currently shown)[/dim]")
    console.print()

    for key, (header, width, justify) in AVAILABLE_COLUMNS.items():
        marker = "[green]*[/green]" if key in current_columns else " "
        console.print(f"  {marker} [bold]{key:15}[/bold] {header:10}")

    console.print()
    console.print(f"[dim]Current: {', '.join(current_columns)}[/dim]")
    console.print()
    console.print("[dim]Use 'columns add <col>' or 'columns remove <col>' to modify[/dim]")


def show_help():
    """Display help for interactive mode commands."""
    # Generate filter commands section from definitions
    lines = ["", "[bold cyan]Filter Commands:[/bold cyan]", ""]
    for cmd_def in FILTER_COMMANDS.values():
        display = cmd_def.display_text
        lines.append(
            f"  [green]{display:18}[/green] {cmd_def.description:25} [dim]e.g. {cmd_def.example}[/dim]"
        )

    # Static sections
    lines.extend([
        "",
        "[bold cyan]Column Commands:[/bold cyan]",
        "",
        "  [green]columns[/green]             List available columns",
        "  [green]columns add <col>[/green]   Add column(s)         [dim]e.g. columns add bases_6m bases_8m[/dim]",
        "  [green]columns remove <col>[/green] Remove column(s)     [dim]e.g. columns remove mmr[/dim]",
        "  [green]columns reset[/green]       Reset to defaults",
        "",
        "[bold cyan]Other:[/bold cyan]",
        "",
        "  [yellow]clear[/yellow]        Reset all filters",
        "  [yellow]help[/yellow]         Show this help",
        "  [yellow]q[/yellow]            Quit",
        "",
        "[dim]Operators: > >= < <=   |   Filters stack together. Use 'clear' to reset all.[/dim]",
        "[dim]+p/+n commands are cumulative (each use adds more games).[/dim]",
    ])
    console.print("\n".join(lines))


def run_interactive_mode():
    """Run the interactive filtering mode."""
    from . import db

    db.init_db()
    state = FilterState()

    # Setup prompt_toolkit session with history and completion
    history_file = get_config_dir() / "interactive_history.txt"
    session = PromptSession(
        history=FileHistory(str(history_file)),
        completer=SC2Completer(get_map_names_func=db.get_unique_map_names),
    )

    console.print()
    console.print("[bold cyan]SC2 Replay Analyzer - Interactive Mode[/bold cyan]")
    console.print("[dim]Type commands to filter. 'help' for options, 'q' to quit. Tab for completion.[/dim]")
    console.print()

    need_refresh = True  # Flag to control when to redraw table

    while True:
        if need_refresh:
            # Fetch replays - use streak query if streak filter is active
            if state.streak_type and state.min_streak_length:
                replays = db.get_streaks(
                    streak_type=state.streak_type,
                    min_length=state.min_streak_length,
                    matchup=state.matchup,
                    map_name=state.map_name,
                    days=state.days,
                )
            else:
                replays = db.get_replays(
                    matchup=state.matchup,
                    result=state.result,
                    map_name=state.map_name,
                    days=state.days,
                    limit=state.limit,
                    min_length=state.min_length,
                    max_length=state.max_length,
                    min_workers_8m=state.min_workers_8m,
                    max_workers_8m=state.max_workers_8m,
                )

            # Expand results with adjacent games if requested
            if state.prev_games > 0 or state.next_games > 0:
                replays = db.expand_results(replays, state.prev_games, state.next_games)

            # Display table
            show_replays_table(replays)

            # Show summary row
            show_summary_row(replays)

            # Show filter status below table
            filter_desc = state.describe(len(replays))
            console.print(f"[dim]{filter_desc}[/dim]")

        need_refresh = True  # Default to refresh on next iteration

        # Get user input
        try:
            console.print()
            cmd = session.prompt("> ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if cmd.lower() in ('q', 'quit', 'exit'):
            console.print("[dim]Goodbye![/dim]")
            break

        # Parse and apply command
        state, error = parse_filter_command(cmd, state)

        if error == "HELP":
            show_help()
            need_refresh = False  # Stay on current view after help
        elif error == "COLUMNS":
            show_columns()
            need_refresh = False  # Stay on current view after columns
        elif error:
            console.print(f"[red]{error}[/red]")
            console.print("[dim]Type 'help' for available commands.[/dim]")
            need_refresh = False  # Stay on current view after error
