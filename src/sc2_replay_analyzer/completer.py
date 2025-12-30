"""Auto-completion for SC2 Replay Analyzer interactive mode."""
from typing import Callable, List, Optional

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

from .commands import (
    CommandKey,
    FILTER_COMMANDS,
    MATCHUPS,
    RESULTS,
    STREAK_TYPES,
    get_completion_commands,
)
from .config import AVAILABLE_COLUMNS

# Get commands from single source of truth
COMMANDS = get_completion_commands()


class SC2Completer(Completer):
    """Custom completer for SC2 Replay Analyzer commands."""

    def __init__(self, get_map_names_func: Optional[Callable[[], List[str]]] = None):
        """
        Initialize completer.

        Args:
            get_map_names_func: Function that returns list of map names from database.
        """
        self.get_map_names = get_map_names_func

    def get_completions(self, document: Document, complete_event):
        """Get completions for the current input."""
        text = document.text_before_cursor
        word = document.get_word_before_cursor()

        # Command completion at start of line or after spaces
        if not text.strip() or text == word:
            for insert_text, display_text, usage in COMMANDS:
                if insert_text.lower().startswith(word.lower()):
                    yield Completion(
                        insert_text,
                        start_position=-len(word),
                        display=display_text,
                        display_meta=usage,
                    )
            return

        # Context-specific completion based on command prefix
        # Use lower() but NOT strip() to preserve space detection
        text_lower = text.lower()

        # Helper to check if text starts with a command's short or long form
        def starts_with_cmd(cmd_key: str) -> bool:
            cmd_def = FILTER_COMMANDS[cmd_key]
            return (
                text_lower.startswith(f"{cmd_def.short.lower()} ")
                or text_lower.startswith(f"{cmd_def.long.lower()} ")
            )

        # Matchup completion after -m or --matchup
        if starts_with_cmd(CommandKey.MATCHUP):
            for m in MATCHUPS:
                if m.lower().startswith(word.lower()):
                    yield Completion(m, start_position=-len(word))
            return

        # Result completion after -r or --result
        if starts_with_cmd(CommandKey.RESULT):
            for r in RESULTS:
                if r.lower().startswith(word.lower()):
                    yield Completion(r, start_position=-len(word))
            return

        # Streak type completion after -s or --streaks
        if starts_with_cmd(CommandKey.STREAKS):
            for s in STREAK_TYPES:
                if s.startswith(word.lower()):
                    yield Completion(s, start_position=-len(word))
            return

        # Columns subcommand completion
        if text_lower.startswith("columns "):
            remaining = text[8:]

            # Subcommand completion
            if remaining == word or not remaining.strip():
                for sub in ["add", "remove", "reset"]:
                    if sub.startswith(word.lower()):
                        yield Completion(sub, start_position=-len(word))
                return

            # Column name completion after add/remove
            remaining_lower = remaining.lower()
            if remaining_lower.startswith("add ") or remaining_lower.startswith("remove "):
                for col in AVAILABLE_COLUMNS.keys():
                    if col.startswith(word.lower()):
                        yield Completion(col, start_position=-len(word))
                return

        # Map name completion after --map
        if starts_with_cmd(CommandKey.MAP) and self.get_map_names:
            try:
                map_names = self.get_map_names()
                for name in map_names:
                    if name.lower().startswith(word.lower()):
                        yield Completion(name, start_position=-len(word))
            except Exception:
                # If db is not available, skip map completion
                pass
            return
