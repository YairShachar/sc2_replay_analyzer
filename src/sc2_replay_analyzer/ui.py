"""
SC2 Replay Analyzer UI

Terminal UI using Rich library for formatted tables and output.
"""
from dataclasses import dataclass
from datetime import datetime
import re
import threading
import time
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
    get_auto_scan_interval_ms,
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

# Tag color palette (deterministic assignment based on label hash)
TAG_COLORS = [
    "#00d4ff",  # cyan
    "#b966ff",  # purple
    "#ffd700",  # yellow
    "#ff6bcd",  # pink
    "#00ffc8",  # teal
    "#6b9dff",  # blue
]


def get_tag_color(label: str) -> str:
    """Get deterministic color for a tag label."""
    return TAG_COLORS[hash(label) % len(TAG_COLORS)]


def is_valid_date(date_str: str) -> bool:
    """Check if string is valid YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def get_date_from_position(pos: int, replays: list) -> Optional[str]:
    """Get date string from 1-indexed position in replay list.

    Args:
        pos: 1-indexed position (as displayed in table)
        replays: List of replay dicts

    Returns:
        Date string (YYYY-MM-DD) or None if invalid position
    """
    if not replays or pos < 1 or pos > len(replays):
        return None
    replay = replays[pos - 1]  # Convert to 0-indexed
    played_at = replay.get("played_at")
    if played_at:
        # Extract just the date part (YYYY-MM-DD)
        return played_at[:10]
    return None


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


def format_date_with_tag(played_at: Optional[str], tagged_dates: set) -> Text:
    """Format date with tag marker if date is tagged."""
    formatted = format_date(played_at)
    if played_at and played_at[:10] in tagged_dates:
        text = Text()
        text.append("* ", style="bold cyan")
        text.append(formatted, style="dim")
        return text
    return Text(formatted, style="dim")


def get_column_value(col_key: str, r: dict, tagged_dates: Optional[set] = None):
    """Get formatted value for a column key from a replay dict."""
    benchmark_6m = get_benchmark_workers_6m()
    benchmark_8m = get_benchmark_workers_8m()
    tagged = tagged_dates or set()

    renderers = {
        "date": lambda: format_date_with_tag(r.get("played_at"), tagged),
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


def show_replays_table(replays: list, tagged_dates: Optional[set] = None):
    """Display replays in a rich table with configurable columns.

    Args:
        replays: List of replay dicts to display
        tagged_dates: Optional set of dates (YYYY-MM-DD) that have tags
    """
    if not replays:
        console.print("[yellow]No replays found.[/yellow]")
        return

    display_columns = get_display_columns()
    table = Table(title="Recent Games", show_header=True, header_style="bold cyan")

    # Add columns dynamically from config
    for col_key in display_columns:
        if col_key in AVAILABLE_COLUMNS:
            header, width, justify = AVAILABLE_COLUMNS[col_key]
            # Don't set style here - format_date_with_tag handles it
            table.add_column(header, width=width, justify=justify)

    # Add rows
    tagged = tagged_dates or set()
    for r in replays:
        row_values = [get_column_value(col_key, r, tagged) for col_key in display_columns if col_key in AVAILABLE_COLUMNS]
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

    # Parse tags command (list all tags)
    if cmd.lower() == 'tags':
        return state, "TAGS"

    # Parse endpoints command (show server endpoints)
    if cmd.lower() in ('endpoints', 'server'):
        return state, "ENDPOINTS"

    # Parse tag end command: tag end "label" or tag end 2025-01-15 "label"
    # With date
    match = re.match(r'tag\s+end\s+(\d{4}-\d{2}-\d{2})\s+["\'](.+)["\']$', cmd)
    if match:
        end_date, label = match.groups()
        return state, ("TAG_END", end_date, label)
    match = re.match(r'tag\s+end\s+(\d{4}-\d{2}-\d{2})\s+(.+)$', cmd)
    if match:
        end_date, label = match.groups()
        return state, ("TAG_END", end_date, label.strip())
    # Without date (use today)
    match = re.match(r'tag\s+end\s+["\'](.+)["\']$', cmd)
    if match:
        return state, ("TAG_END", None, match.group(1))
    match = re.match(r'tag\s+end\s+(.+)$', cmd)
    if match:
        return state, ("TAG_END", None, match.group(1).strip())

    # Parse tag start command: tag start "label" or tag start 2025-01-15 "label"
    # With date
    match = re.match(r'tag\s+start\s+(\d{4}-\d{2}-\d{2})\s+["\'](.+)["\']$', cmd)
    if match:
        start_date, label = match.groups()
        return state, ("TAG_START", start_date, label)
    match = re.match(r'tag\s+start\s+(\d{4}-\d{2}-\d{2})\s+(.+)$', cmd)
    if match:
        start_date, label = match.groups()
        return state, ("TAG_START", start_date, label.strip())
    # Without date (use today)
    match = re.match(r'tag\s+start\s+["\'](.+)["\']$', cmd)
    if match:
        return state, ("TAG_START", None, match.group(1))
    match = re.match(r'tag\s+start\s+(.+)$', cmd)
    if match:
        return state, ("TAG_START", None, match.group(1).strip())

    # Parse tag command (ongoing from today): tag "label"
    match = re.match(r'tag\s+["\'](.+)["\']$', cmd)
    if match:
        return state, ("TAG_START", None, match.group(1))

    # Parse tag command with date: tag <date|position> "<label>" (single-day tag)
    # Match: tag 2024-01-15 "Label" or tag 3 "Label"
    match = re.match(r'tag\s+(\S+)\s+["\'](.+)["\']$', cmd)
    if match:
        date_or_pos, label = match.groups()
        return state, ("TAG", date_or_pos, label)

    # Also support without quotes: tag 2024-01-15 Label here
    match = re.match(r'tag\s+(\S+)\s+(.+)$', cmd)
    if match:
        date_or_pos, label = match.groups()
        return state, ("TAG", date_or_pos, label.strip())

    # Parse untag command: untag <date|position> ["<label>"]
    match = re.match(r'untag\s+(\S+)\s+["\'](.+)["\']$', cmd)
    if match:
        date_or_pos, label = match.groups()
        return state, ("UNTAG", date_or_pos, label)

    # Untag with unquoted label
    match = re.match(r'untag\s+(\S+)\s+(.+)$', cmd)
    if match:
        date_or_pos, label = match.groups()
        return state, ("UNTAG", date_or_pos, label.strip())

    # Untag without label (remove all for date)
    match = re.match(r'untag\s+(\S+)$', cmd)
    if match:
        date_or_pos = match.group(1)
        return state, ("UNTAG", date_or_pos, None)

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


def show_tags():
    """Display all tags grouped by type (ongoing vs completed/single)."""
    from . import db

    tags = db.get_tags()
    if not tags:
        console.print("[yellow]No tags found.[/yellow]")
        return

    console.print()
    console.print("[bold cyan]Tags:[/bold cyan]")
    console.print()

    # Separate ongoing from completed/single
    ongoing = [t for t in tags if t.get("end_date") is None]
    completed = [t for t in tags if t.get("end_date") is not None]

    # Show ongoing tags first
    if ongoing:
        console.print("  [bold yellow]Ongoing:[/bold yellow]")
        for tag in ongoing:
            color = get_tag_color(tag["label"])
            console.print(f"    [{color}]▸[/{color}] {tag['label']} [dim](since {tag['tag_date']})[/dim]")
        console.print()

    # Show completed/single tags grouped by date
    if completed:
        console.print("  [bold]Completed/Single:[/bold]")
        from collections import defaultdict
        by_date = defaultdict(list)
        for tag in completed:
            by_date[tag["tag_date"]].append(tag)

        for date in sorted(by_date.keys(), reverse=True):
            tags_on_date = by_date[date]
            console.print(f"    [bold]{date}[/bold]")
            for tag in tags_on_date:
                color = get_tag_color(tag["label"])
                end_date = tag.get("end_date")
                if end_date and end_date != date:
                    # Range tag
                    console.print(f"      [{color}]◆─◆[/{color}] {tag['label']} [dim]→ {end_date}[/dim]")
                else:
                    # Single date tag
                    console.print(f"      [{color}]◆[/{color}] {tag['label']}")
        console.print()
    elif not ongoing:
        console.print()  # Just add spacing if we only showed ongoing


def show_endpoints(server_port: Optional[int]):
    """Display available server endpoints."""
    console.print()
    if server_port is None:
        console.print("[yellow]Server not running.[/yellow]")
        console.print("[dim]Enable with: server_enabled = true in config[/dim]")
        return

    base_url = f"http://localhost:{server_port}"
    console.print("[bold cyan]Server Endpoints:[/bold cyan]")
    console.print()
    console.print(f"  [bold]Base URL:[/bold]        {base_url}/")
    console.print()
    console.print("  [bold cyan]Overlays:[/bold cyan]")
    console.print(f"    MMR Graph:      {base_url}/overlays/mmr-graph")
    console.print()
    console.print("  [bold cyan]API:[/bold cyan]")
    console.print(f"    MMR History:    {base_url}/api/v1/mmr/history")
    console.print()


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
        "[bold cyan]Tag Commands:[/bold cyan]",
        "",
        "  [green]tag \"<label>\"[/green]          Start ongoing tag from today  [dim]e.g. tag \"Practicing 1/1/1\"[/dim]",
        "  [green]tag start <label>[/green]     Start ongoing tag from today  [dim]e.g. tag start \"New build\"[/dim]",
        "  [green]tag start <date> <label>[/green] Start from specific date   [dim]e.g. tag start 2025-01-01 \"Macro focus\"[/dim]",
        "  [green]tag end <label>[/green]       End ongoing tag today         [dim]e.g. tag end \"Practicing 1/1/1\"[/dim]",
        "  [green]tag end <date> <label>[/green] End on specific date         [dim]e.g. tag end 2025-01-15 \"New build\"[/dim]",
        "  [green]tag <date> <label>[/green]   Single-date tag               [dim]e.g. tag 2025-01-15 \"Coaching session\"[/dim]",
        "  [green]tag <pos> <label>[/green]    Tag by table position         [dim]e.g. tag 3 \"Good game\"[/dim]",
        "  [green]tags[/green]                 List all tags",
        "  [green]untag <date>[/green]         Remove all tags               [dim]e.g. untag 2025-01-15[/dim]",
        "  [green]untag <date> <label>[/green] Remove specific tag           [dim]e.g. untag 2025-01-15 \"Old tag\"[/dim]",
        "",
        "[bold cyan]Other:[/bold cyan]",
        "",
        "  [yellow]endpoints[/yellow]    Show server endpoints",
        "  [yellow]clear[/yellow]        Reset all filters",
        "  [yellow]help[/yellow]         Show this help",
        "  [yellow]q[/yellow]            Quit",
        "",
        "[dim]Operators: > >= < <=   |   Filters stack together. Use 'clear' to reset all.[/dim]",
        "[dim]+p/+n commands are cumulative (each use adds more games).[/dim]",
    ])
    console.print("\n".join(lines))


def run_interactive_mode(server_port: Optional[int] = None, startup_message: Optional[str] = None):
    """Run the interactive filtering mode.

    Args:
        server_port: Port the overlay server is running on, if any
        startup_message: Message to display after first table refresh (e.g., server status)
    """
    from . import db
    from .cli import auto_scan

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
    replays = []  # Keep track of current replays for position-based tagging
    pending_message = startup_message  # Show startup message after first table refresh

    # Background scanner setup
    scan_interval_ms = get_auto_scan_interval_ms()
    new_replays_event = threading.Event()
    stop_scanner = threading.Event()

    def background_scanner():
        """Background thread that periodically scans for new replays."""
        while not stop_scanner.is_set():
            stop_scanner.wait(scan_interval_ms / 1000.0)
            if stop_scanner.is_set():
                break
            try:
                count = auto_scan(silent=True)
                if count > 0:
                    new_replays_event.set()
            except Exception:
                pass  # Continue scanning even if one cycle fails

    # Start scanner if enabled
    scanner_thread = None
    if scan_interval_ms > 0:
        scanner_thread = threading.Thread(target=background_scanner, daemon=True)
        scanner_thread.start()

    try:
        while True:
            # Check for new replays from background scanner
            if new_replays_event.is_set():
                new_replays_event.clear()
                need_refresh = True
                pending_message = "[green]New replay(s) detected[/green]"

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

                # Get tagged dates for display
                tagged_dates = db.get_tagged_dates()

                # Display table
                show_replays_table(replays, tagged_dates)

                # Show summary row
                show_summary_row(replays)

                # Show filter status below table
                filter_desc = state.describe(len(replays))
                console.print(f"[dim]{filter_desc}[/dim]")

                # Show pending message after table if any
                if pending_message:
                    console.print(pending_message)
                    pending_message = None

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
            elif error == "TAGS":
                show_tags()
                need_refresh = False
            elif error == "ENDPOINTS":
                show_endpoints(server_port)
                need_refresh = False
            elif isinstance(error, tuple) and error[0] == "TAG_START":
                _, start_date, label = error
                # Use today if no date provided
                if start_date is None:
                    start_date = datetime.now().strftime("%Y-%m-%d")
                elif not is_valid_date(start_date):
                    console.print(f"[red]Invalid date format: {start_date}. Use YYYY-MM-DD[/red]")
                    need_refresh = False
                    continue

                # Check for ongoing tags and notify user
                ongoing_tags = db.get_ongoing_tags()
                if ongoing_tags:
                    ongoing_labels = [t["label"] for t in ongoing_tags]
                    console.print(f"[dim]Note: {len(ongoing_tags)} ongoing tag(s): {', '.join(ongoing_labels)}[/dim]")

                # Add the ongoing tag
                if db.add_tag(start_date, label):
                    color = get_tag_color(label)
                    pending_message = f"[green]Started ongoing tag:[/green] [{color}]▸[/{color}] {label} (from {start_date})"
                else:
                    pending_message = f"[yellow]Tag already exists:[/yellow] {label} from {start_date}"
                need_refresh = True

            elif isinstance(error, tuple) and error[0] == "TAG_END":
                _, end_date, label = error
                # Use today if no date provided
                if end_date is None:
                    end_date = datetime.now().strftime("%Y-%m-%d")
                elif not is_valid_date(end_date):
                    console.print(f"[red]Invalid date format: {end_date}. Use YYYY-MM-DD[/red]")
                    need_refresh = False
                    continue

                # End the ongoing tag
                if db.end_tag(label, end_date):
                    color = get_tag_color(label)
                    pending_message = f"[green]Ended tag:[/green] [{color}]◆─◆[/{color}] {label} (ended {end_date})"
                else:
                    pending_message = f"[yellow]No ongoing tag found:[/yellow] {label}"
                need_refresh = True

            elif isinstance(error, tuple) and error[0] == "TAG":
                _, date_or_pos, label = error
                # Resolve position to date if needed
                if date_or_pos.isdigit():
                    tag_date = get_date_from_position(int(date_or_pos), replays)
                    if not tag_date:
                        console.print(f"[red]Invalid position: {date_or_pos}[/red]")
                        need_refresh = False
                        continue
                elif is_valid_date(date_or_pos):
                    tag_date = date_or_pos
                else:
                    console.print(f"[red]Invalid date format: {date_or_pos}. Use YYYY-MM-DD[/red]")
                    need_refresh = False
                    continue

                # Check for ongoing tags and notify user
                ongoing_tags = db.get_ongoing_tags()
                if ongoing_tags:
                    ongoing_labels = [t["label"] for t in ongoing_tags]
                    console.print(f"[dim]Note: {len(ongoing_tags)} ongoing tag(s): {', '.join(ongoing_labels)}[/dim]")

                # Add the tag (single date with same start/end)
                if db.add_tag(tag_date, label, end_date=tag_date):
                    color = get_tag_color(label)
                    pending_message = f"[green]Added tag:[/green] [{color}]◆[/{color}] {label} on {tag_date}"
                else:
                    pending_message = f"[yellow]Tag already exists:[/yellow] {label} on {tag_date}"
                need_refresh = True  # Refresh to show tag marker
            elif isinstance(error, tuple) and error[0] == "UNTAG":
                _, date_or_pos, label = error
                # Resolve position to date if needed
                if date_or_pos.isdigit():
                    tag_date = get_date_from_position(int(date_or_pos), replays)
                    if not tag_date:
                        console.print(f"[red]Invalid position: {date_or_pos}[/red]")
                        need_refresh = False
                        continue
                elif is_valid_date(date_or_pos):
                    tag_date = date_or_pos
                else:
                    console.print(f"[red]Invalid date format: {date_or_pos}. Use YYYY-MM-DD[/red]")
                    need_refresh = False
                    continue
                # Remove the tag(s)
                count = db.remove_tag(tag_date, label)
                if count > 0:
                    if label:
                        pending_message = f"[green]Removed tag:[/green] {label} from {tag_date}"
                    else:
                        pending_message = f"[green]Removed {count} tag(s)[/green] from {tag_date}"
                else:
                    pending_message = f"[yellow]No matching tags found for {tag_date}[/yellow]"
                need_refresh = True  # Refresh to update tag markers
            elif error:
                console.print(f"[red]{error}[/red]")
                console.print("[dim]Type 'help' for available commands.[/dim]")
                need_refresh = False  # Stay on current view after error
    finally:
        # Signal the background scanner to stop
        stop_scanner.set()
