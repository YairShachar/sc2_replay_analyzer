"""Tests for sc2_replay_analyzer.commands module."""
import re

import pytest

from sc2_replay_analyzer.commands import (
    CommandKey,
    CommandDefinition,
    FILTER_COMMANDS,
    SIMPLE_COMMANDS,
    MATCHUPS,
    RESULTS,
    STREAK_TYPES,
    get_completion_commands,
)


class TestCommandDefinition:
    """Tests for CommandDefinition dataclass."""

    def test_display_text_with_different_short_long(self):
        """display_text shows 'short, long' when they differ."""
        cmd = CommandDefinition(
            short="-n",
            long="--limit",
            description="Test",
            value_pattern=r"(\d+)",
            example="-n 50",
        )
        assert cmd.display_text == "-n, --limit"

    def test_display_text_with_same_short_long(self):
        """display_text shows just the command when short == long."""
        cmd = CommandDefinition(
            short="--map",
            long="--map",
            description="Test",
            value_pattern=r"(.+)",
            example="--map Test",
        )
        assert cmd.display_text == "--map"

    def test_build_regex_with_space(self):
        """build_regex creates pattern with required space."""
        cmd = CommandDefinition(
            short="-n",
            long="--limit",
            description="Test",
            value_pattern=r"(\d+)",
            example="-n 50",
            requires_space=True,
        )
        pattern = cmd.build_regex()
        assert re.match(pattern, "-n 50")
        assert re.match(pattern, "--limit 100")
        assert not re.match(pattern, "-n50")  # No space

    def test_build_regex_without_space(self):
        """build_regex creates pattern with optional space."""
        cmd = CommandDefinition(
            short="-l",
            long="--length",
            description="Test",
            value_pattern=r"([<>]=?)\s*([\d:]+)",
            example="-l >8:00",
            requires_space=False,
        )
        pattern = cmd.build_regex()
        assert re.match(pattern, "-l >8:00")
        assert re.match(pattern, "-l>8:00")  # No space OK
        assert re.match(pattern, "--length >5:00")

    def test_build_regex_escapes_special_chars(self):
        """build_regex properly escapes +p."""
        cmd = CommandDefinition(
            short="+p",
            long="--prev",
            description="Test",
            value_pattern=r"(\d+)",
            example="+p 1",
        )
        pattern = cmd.build_regex()
        assert re.match(pattern, "+p 1")
        assert re.match(pattern, "--prev 2")
        # + should be escaped, not treated as "one or more p"
        assert not re.match(pattern, "pppp 1")


class TestFilterCommands:
    """Tests for FILTER_COMMANDS registry."""

    def test_all_expected_commands_present(self):
        """All expected filter commands are in registry."""
        expected = ["limit", "matchup", "result", "length", "workers",
                    "days", "streaks", "map", "prev", "next"]
        for key in expected:
            assert key in FILTER_COMMANDS, f"Missing command: {key}"

    def test_limit_command_definition(self):
        """limit command has correct definition."""
        cmd = FILTER_COMMANDS[CommandKey.LIMIT]
        assert cmd.short == "-n"
        assert cmd.long == "--limit"
        assert re.match(cmd.build_regex(), "-n 50")
        assert re.match(cmd.build_regex(), "--limit 100")

    def test_matchup_command_definition(self):
        """matchup command has correct definition."""
        cmd = FILTER_COMMANDS[CommandKey.MATCHUP]
        assert cmd.short == "-m"
        assert cmd.long == "--matchup"
        assert cmd.case_sensitive is False
        assert re.match(cmd.build_regex(), "-m TvZ")
        assert re.match(cmd.build_regex(), "--matchup PvP")

    def test_prev_command_definition(self):
        """prev command (with +p) has correct definition."""
        cmd = FILTER_COMMANDS[CommandKey.PREV]
        assert cmd.short == "+p"
        assert cmd.long == "--prev"
        assert re.match(cmd.build_regex(), "+p 1")
        assert re.match(cmd.build_regex(), "--prev 5")


class TestSimpleCommands:
    """Tests for SIMPLE_COMMANDS registry."""

    def test_all_simple_commands_present(self):
        """All expected simple commands are in registry."""
        expected = ["columns", "clear", "help", "quit"]
        for key in expected:
            assert key in SIMPLE_COMMANDS, f"Missing command: {key}"

    def test_simple_command_format(self):
        """Simple commands have (name, description) format."""
        for key, (name, desc) in SIMPLE_COMMANDS.items():
            assert isinstance(name, str)
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestCompletionValues:
    """Tests for completion value lists."""

    def test_matchups_list(self):
        """MATCHUPS contains all 9 matchup combinations."""
        assert len(MATCHUPS) == 9
        assert "TvT" in MATCHUPS
        assert "TvZ" in MATCHUPS
        assert "ZvP" in MATCHUPS

    def test_results_list(self):
        """RESULTS contains win/loss variants."""
        assert "W" in RESULTS
        assert "L" in RESULTS
        assert "win" in RESULTS
        assert "loss" in RESULTS

    def test_streak_types_list(self):
        """STREAK_TYPES contains win:/loss:."""
        assert "win:" in STREAK_TYPES
        assert "loss:" in STREAK_TYPES


class TestGetCompletionCommands:
    """Tests for get_completion_commands function."""

    def test_returns_list_of_tuples(self):
        """get_completion_commands returns list of 3-tuples."""
        commands = get_completion_commands()
        assert isinstance(commands, list)
        assert len(commands) > 0
        for cmd in commands:
            assert isinstance(cmd, tuple)
            assert len(cmd) == 3

    def test_includes_filter_commands(self):
        """get_completion_commands includes filter commands."""
        commands = get_completion_commands()
        insert_texts = [c[0] for c in commands]
        assert "-n" in insert_texts
        assert "-m" in insert_texts
        assert "+p" in insert_texts

    def test_includes_simple_commands(self):
        """get_completion_commands includes simple commands."""
        commands = get_completion_commands()
        insert_texts = [c[0] for c in commands]
        assert "columns" in insert_texts
        assert "clear" in insert_texts
        assert "help" in insert_texts
        assert "q" in insert_texts

    def test_tuple_format(self):
        """Tuples have (insert_text, display_text, description) format."""
        commands = get_completion_commands()
        # Find the limit command
        limit_cmd = next((c for c in commands if c[0] == "-n"), None)
        assert limit_cmd is not None
        insert_text, display_text, description = limit_cmd
        assert insert_text == "-n"
        assert display_text == "-n, --limit"
        assert "Limit" in description
