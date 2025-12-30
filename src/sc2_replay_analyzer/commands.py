"""Command definitions - single source of truth for all commands."""
import re
from dataclasses import dataclass


class CommandKey:
    """Single source of truth for command keys."""

    LIMIT = "limit"
    MATCHUP = "matchup"
    RESULT = "result"
    LENGTH = "length"
    WORKERS = "workers"
    DAYS = "days"
    STREAKS = "streaks"
    MAP = "map"
    PREV = "prev"
    NEXT = "next"


@dataclass
class CommandDefinition:
    """Definition for a filter command."""

    short: str  # "-n"
    long: str  # "--limit"
    description: str  # "Limit to N games"
    value_pattern: str  # r'(\d+)'
    example: str  # "-n 50"
    requires_space: bool = True  # Whether space required before value
    case_sensitive: bool = True  # Whether value is case-sensitive

    @property
    def display_text(self) -> str:
        """Text shown in completion menu."""
        if self.short == self.long:
            return self.short
        return f"{self.short}, {self.long}"

    def build_regex(self) -> str:
        """Build regex pattern for this command."""
        prefix = f"(?:{re.escape(self.short)}|{re.escape(self.long)})"
        space = r"\s+" if self.requires_space else r"\s*"
        return f"{prefix}{space}{self.value_pattern}"


# Registry of all filter commands
FILTER_COMMANDS = {
    CommandKey.LIMIT: CommandDefinition(
        short="-n",
        long="--limit",
        description="Limit results to N games",
        value_pattern=r"(\d+)",
        example="-n 50",
    ),
    CommandKey.MATCHUP: CommandDefinition(
        short="-m",
        long="--matchup",
        description="Filter by matchup (TvZ, TvP, etc)",
        value_pattern=r"(\w+)",
        example="-m TvZ",
        case_sensitive=False,
    ),
    CommandKey.RESULT: CommandDefinition(
        short="-r",
        long="--result",
        description="Filter by result (W/L)",
        value_pattern=r"(\w+)",
        example="-r W",
        case_sensitive=False,
    ),
    CommandKey.LENGTH: CommandDefinition(
        short="-l",
        long="--length",
        description="Filter by game length",
        value_pattern=r"([<>]=?)\s*([\d:]+)",
        example="-l >8:00",
        requires_space=False,
    ),
    CommandKey.WORKERS: CommandDefinition(
        short="-w",
        long="--workers",
        description="Filter by workers @8m",
        value_pattern=r"([<>]=?)\s*(\d+)",
        example="-w <40",
        requires_space=False,
    ),
    CommandKey.DAYS: CommandDefinition(
        short="-d",
        long="--days",
        description="Games from last N days",
        value_pattern=r"(\d+)",
        example="-d 7",
    ),
    CommandKey.STREAKS: CommandDefinition(
        short="-s",
        long="--streaks",
        description="Find win/loss streaks",
        value_pattern=r"(win|loss):(\d+)\+?",
        example="-s win:3+",
        case_sensitive=False,
    ),
    CommandKey.MAP: CommandDefinition(
        short="--map",
        long="--map",
        description="Filter by map name",
        value_pattern=r"(.+)",
        example="--map Alcyone",
        case_sensitive=False,
    ),
    CommandKey.PREV: CommandDefinition(
        short="+p",
        long="--prev",
        description="Add N previous games (cumulative)",
        value_pattern=r"(\d+)",
        example="+p 1",
    ),
    CommandKey.NEXT: CommandDefinition(
        short="+n",
        long="--next",
        description="Add N next games (cumulative)",
        value_pattern=r"(\d+)",
        example="+n 2",
    ),
}

# Simple commands without values
SIMPLE_COMMANDS = {
    "columns": ("columns", "Manage display columns"),
    "clear": ("clear", "Reset all filters"),
    "help": ("help", "Show help"),
    "quit": ("q", "Quit"),
}

# Completion value options for specific commands
MATCHUPS = ["TvT", "TvP", "TvZ", "PvT", "PvP", "PvZ", "ZvT", "ZvP", "ZvZ"]
RESULTS = ["W", "L", "win", "loss"]
STREAK_TYPES = ["win:", "loss:"]


def get_completion_commands():
    """Get command list for auto-completion.

    Returns list of (insert_text, display_text, usage_hint) tuples.
    """
    commands = []
    for cmd_def in FILTER_COMMANDS.values():
        commands.append((cmd_def.short, cmd_def.display_text, cmd_def.description))
    for name, desc in SIMPLE_COMMANDS.values():
        commands.append((name, name, desc))
    return commands
