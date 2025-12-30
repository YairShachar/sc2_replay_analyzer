"""
Tests for sc2_replay_analyzer.completer module.
"""
from prompt_toolkit.document import Document

import pytest


class TestSC2Completer:
    """Tests for SC2Completer class."""

    def test_completer_initialization(self):
        """SC2Completer initializes correctly."""
        from sc2_replay_analyzer.completer import SC2Completer, COMMANDS

        completer = SC2Completer()
        assert completer.get_map_names is None
        # COMMANDS is a module-level list of tuples
        assert len(COMMANDS) > 0

    def test_completer_with_map_func(self):
        """SC2Completer accepts map names function."""
        from sc2_replay_analyzer.completer import SC2Completer

        def mock_get_maps():
            return ["Alcyone LE", "Site Delta"]

        completer = SC2Completer(get_map_names_func=mock_get_maps)
        assert completer.get_map_names is mock_get_maps

    def test_completes_commands_at_start(self):
        """SC2Completer completes commands at start of line."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        # Empty document - should suggest all commands
        doc = Document("")

        completions = list(completer.get_completions(doc, None))

        # text = what gets inserted (short form)
        texts = [c.text for c in completions]
        assert "-m" in texts
        assert "-r" in texts
        assert "help" in texts

        # display = what shows in menu (includes long alias)
        # display can be FormattedText, so check if text is contained
        displays_str = " ".join(str(c.display) for c in completions)
        assert "-m, --matchup" in displays_str
        assert "-r, --result" in displays_str

    def test_completes_matchups_after_m(self):
        """SC2Completer completes matchups after -m."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("-m T", cursor_position=4)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        assert "TvT" in labels
        assert "TvP" in labels
        assert "TvZ" in labels

    def test_completes_results_after_r(self):
        """SC2Completer completes results after -r."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("-r ", cursor_position=3)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        assert "W" in labels
        assert "L" in labels
        assert "win" in labels
        assert "loss" in labels

    def test_completes_streak_types_after_s(self):
        """SC2Completer completes streak types after -s."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("-s ", cursor_position=3)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        assert "win:" in labels
        assert "loss:" in labels

    def test_completes_columns_subcommands(self):
        """SC2Completer completes columns subcommands."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("columns ", cursor_position=8)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        assert "add" in labels
        assert "remove" in labels
        assert "reset" in labels

    def test_completes_column_names_after_add(self):
        """SC2Completer completes column names after columns add."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("columns add m", cursor_position=13)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        # Should suggest columns starting with 'm'
        assert "map" in labels or "matchup" in labels or "mmr" in labels

    def test_completes_map_names_when_func_provided(self):
        """SC2Completer completes map names when function is provided."""
        from sc2_replay_analyzer.completer import SC2Completer

        def mock_get_maps():
            return ["Alcyone LE", "Site Delta"]

        completer = SC2Completer(get_map_names_func=mock_get_maps)
        doc = Document("--map A", cursor_position=7)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        assert "Alcyone LE" in labels

    def test_no_map_completions_when_func_not_provided(self):
        """SC2Completer returns no map completions when function is not provided."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()  # No map function
        doc = Document("--map A", cursor_position=7)

        completions = list(completer.get_completions(doc, None))

        # Should be empty since no map function provided
        assert len(completions) == 0

    def test_handles_exception_in_map_function(self):
        """SC2Completer handles exceptions in map names function."""
        from sc2_replay_analyzer.completer import SC2Completer

        def failing_get_maps():
            raise RuntimeError("Database error")

        completer = SC2Completer(get_map_names_func=failing_get_maps)
        doc = Document("--map A", cursor_position=7)

        # Should not raise, just return no completions
        completions = list(completer.get_completions(doc, None))
        assert len(completions) == 0

    def test_case_insensitive_matchup_completion(self):
        """SC2Completer matchup completion is case insensitive."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("-m t", cursor_position=4)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        # Should match lowercase 't' to TvT, TvP, TvZ
        assert "TvT" in labels
        assert "TvP" in labels
        assert "TvZ" in labels

    def test_completions_have_usage_hints(self):
        """SC2Completer provides usage hints via display_meta."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("")

        completions = list(completer.get_completions(doc, None))

        # Find the matchup completion and check its hint
        matchup_completion = next((c for c in completions if "-m" in c.text), None)
        assert matchup_completion is not None
        assert matchup_completion.display_meta is not None
        # display_meta can be string or FormattedText, convert to string
        meta_text = str(matchup_completion.display_meta)
        assert "matchup" in meta_text.lower()

    def test_completes_matchups_after_long_alias(self):
        """SC2Completer completes matchups after --matchup."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("--matchup T", cursor_position=11)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        assert "TvT" in labels
        assert "TvP" in labels
        assert "TvZ" in labels

    def test_completes_results_after_long_alias(self):
        """SC2Completer completes results after --result."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("--result ", cursor_position=9)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        assert "W" in labels
        assert "L" in labels

    def test_completes_streak_types_after_long_alias(self):
        """SC2Completer completes streak types after --streaks."""
        from sc2_replay_analyzer.completer import SC2Completer

        completer = SC2Completer()
        doc = Document("--streaks ", cursor_position=10)

        completions = list(completer.get_completions(doc, None))

        labels = [c.text for c in completions]
        assert "win:" in labels
        assert "loss:" in labels
