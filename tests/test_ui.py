"""
Tests for sc2_replay_analyzer.ui module.
"""
from unittest.mock import patch, MagicMock

import pytest


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_format_duration_none(self):
        """format_duration returns '-' for None."""
        from sc2_replay_analyzer.ui import format_duration

        assert format_duration(None) == "-"

    def test_format_duration_seconds_only(self):
        """format_duration formats short durations."""
        from sc2_replay_analyzer.ui import format_duration

        assert format_duration(45) == "0:45"

    def test_format_duration_minutes_seconds(self):
        """format_duration formats minutes:seconds."""
        from sc2_replay_analyzer.ui import format_duration

        assert format_duration(125) == "2:05"
        assert format_duration(600) == "10:00"
        assert format_duration(720) == "12:00"

    def test_format_duration_hours(self):
        """format_duration formats hours:minutes:seconds for long games."""
        from sc2_replay_analyzer.ui import format_duration

        assert format_duration(3661) == "1:01:01"
        assert format_duration(7200) == "2:00:00"

    def test_format_duration_pads_seconds(self):
        """format_duration pads seconds with zero."""
        from sc2_replay_analyzer.ui import format_duration

        assert format_duration(61) == "1:01"
        assert format_duration(65) == "1:05"


class TestFormatDate:
    """Tests for format_date function."""

    def test_format_date_none(self):
        """format_date returns '-' for None/empty."""
        from sc2_replay_analyzer.ui import format_date

        assert format_date(None) == "-"
        assert format_date("") == "-"

    def test_format_date_iso_format(self):
        """format_date parses ISO format dates."""
        from sc2_replay_analyzer.ui import format_date

        result = format_date("2024-12-15T12:30:00+00:00")
        assert "Dec" in result
        assert "15" in result
        assert "12:30" in result

    def test_format_date_with_z_suffix(self):
        """format_date handles Z timezone suffix."""
        from sc2_replay_analyzer.ui import format_date

        result = format_date("2024-12-15T12:30:00Z")
        assert "Dec" in result

    def test_format_date_invalid_falls_back(self):
        """format_date falls back for invalid dates."""
        from sc2_replay_analyzer.ui import format_date

        result = format_date("not-a-date")
        assert result == "not-a-date"[:16]


class TestParseTime:
    """Tests for parse_time function."""

    def test_parse_time_minutes_only(self):
        """parse_time converts minutes to seconds."""
        from sc2_replay_analyzer.ui import parse_time

        assert parse_time("5") == 300
        assert parse_time("10") == 600

    def test_parse_time_minutes_seconds(self):
        """parse_time converts MM:SS to seconds."""
        from sc2_replay_analyzer.ui import parse_time

        assert parse_time("5:30") == 330
        assert parse_time("8:00") == 480
        assert parse_time("12:45") == 765

    def test_parse_time_zero(self):
        """parse_time handles zero."""
        from sc2_replay_analyzer.ui import parse_time

        assert parse_time("0") == 0
        assert parse_time("0:00") == 0


class TestFilterState:
    """Tests for FilterState dataclass."""

    def test_filter_state_defaults(self):
        """FilterState has correct defaults."""
        from sc2_replay_analyzer.ui import FilterState

        state = FilterState()
        assert state.limit == 50
        assert state.matchup is None
        assert state.result is None
        assert state.map_name is None
        assert state.days is None

    def test_filter_state_reset(self):
        """FilterState.reset clears all filters."""
        from sc2_replay_analyzer.ui import FilterState

        state = FilterState()
        state.matchup = "TvZ"
        state.result = "Win"
        state.days = 7
        state.limit = 100

        state.reset()

        assert state.matchup is None
        assert state.result is None
        assert state.days is None
        assert state.limit == 50

    def test_filter_state_describe_basic(self):
        """FilterState.describe returns basic description."""
        from sc2_replay_analyzer.ui import FilterState

        state = FilterState()
        desc = state.describe(10)
        assert "Showing 10 games" in desc

    def test_filter_state_describe_with_matchup(self):
        """FilterState.describe includes matchup."""
        from sc2_replay_analyzer.ui import FilterState

        state = FilterState()
        state.matchup = "TvZ"
        desc = state.describe(5)
        assert "TvZ" in desc

    def test_filter_state_describe_with_result(self):
        """FilterState.describe includes result."""
        from sc2_replay_analyzer.ui import FilterState

        state = FilterState()
        state.result = "Win"
        desc = state.describe(5)
        assert "wins" in desc

    def test_filter_state_describe_with_days(self):
        """FilterState.describe includes days filter."""
        from sc2_replay_analyzer.ui import FilterState

        state = FilterState()
        state.days = 7
        desc = state.describe(5)
        assert "7 days" in desc

    def test_filter_state_describe_with_length_filter(self):
        """FilterState.describe includes length filter."""
        from sc2_replay_analyzer.ui import FilterState

        state = FilterState()
        state.min_length = 480
        desc = state.describe(5)
        assert "length" in desc
        assert "> 8:00" in desc

    def test_filter_state_describe_with_worker_filter(self):
        """FilterState.describe includes worker filter."""
        from sc2_replay_analyzer.ui import FilterState

        state = FilterState()
        state.min_workers_8m = 50
        desc = state.describe(5)
        assert "workers@8m" in desc
        assert "> 50" in desc


class TestParseFilterCommand:
    """Tests for parse_filter_command function."""

    def test_parse_empty_command(self):
        """parse_filter_command handles empty input."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("", state)
        assert error is None

    def test_parse_clear_command(self):
        """parse_filter_command handles clear/reset."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state.matchup = "TvZ"
        state, error = parse_filter_command("clear", state)

        assert error is None
        assert state.matchup is None

    def test_parse_help_command(self):
        """parse_filter_command returns HELP for help commands."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        for cmd in ["h", "help", "?"]:
            state, error = parse_filter_command(cmd, state)
            assert error == "HELP"

    def test_parse_n_command(self):
        """parse_filter_command sets limit with -n."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-n 100", state)

        assert error is None
        assert state.limit == 100

    def test_parse_m_command_matchup(self):
        """parse_filter_command sets matchup with -m."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-m TvZ", state)

        assert error is None
        assert state.matchup == "TvZ"

    def test_parse_m_command_normalizes_matchup(self):
        """parse_filter_command normalizes matchup format."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-m tvz", state)

        assert error is None
        assert state.matchup == "TvZ"

    def test_parse_r_command_win(self):
        """parse_filter_command sets result with -r W."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-r W", state)

        assert error is None
        assert state.result == "Win"

    def test_parse_r_command_loss(self):
        """parse_filter_command sets result with -r L."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-r l", state)

        assert error is None
        assert state.result == "Loss"

    def test_parse_l_command_min_length(self):
        """parse_filter_command sets min length with -l >."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-l >8:00", state)

        assert error is None
        assert state.min_length == 480

    def test_parse_l_command_max_length(self):
        """parse_filter_command sets max length with -l <."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-l <5:00", state)

        assert error is None
        assert state.max_length == 300

    def test_parse_w_command_min_workers(self):
        """parse_filter_command sets min workers with -w >."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-w >50", state)

        assert error is None
        assert state.min_workers_8m == 50

    def test_parse_w_command_max_workers(self):
        """parse_filter_command sets max workers with -w <."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-w <40", state)

        assert error is None
        assert state.max_workers_8m == 40

    def test_parse_map_command(self):
        """parse_filter_command sets map filter with --map."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("--map Alcyone", state)

        assert error is None
        assert state.map_name == "Alcyone"

    def test_parse_d_command_days(self):
        """parse_filter_command sets days filter with -d."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("-d 7", state)

        assert error is None
        assert state.days == 7

    def test_parse_unknown_command(self):
        """parse_filter_command returns error for unknown commands."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("--invalid xyz", state)

        assert error is not None
        assert "Unknown command" in error

    def test_parse_columns_command(self):
        """parse_filter_command returns COLUMNS for columns command."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState

        state = FilterState()
        state, error = parse_filter_command("columns", state)

        assert error == "COLUMNS"

    def test_parse_columns_add_command(self, mock_config_dir):
        """parse_filter_command handles columns add."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState
        from sc2_replay_analyzer.config import set_display_columns, get_display_columns

        set_display_columns(["date", "map"])
        state = FilterState()
        state, error = parse_filter_command("columns add result", state)

        assert error is None
        assert "result" in get_display_columns()

    def test_parse_columns_remove_command(self, mock_config_dir):
        """parse_filter_command handles columns remove."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState
        from sc2_replay_analyzer.config import set_display_columns, get_display_columns

        set_display_columns(["date", "map", "result"])
        state = FilterState()
        state, error = parse_filter_command("columns remove map", state)

        assert error is None
        assert "map" not in get_display_columns()

    def test_parse_columns_reset_command(self, mock_config_dir):
        """parse_filter_command handles columns reset."""
        from sc2_replay_analyzer.ui import parse_filter_command, FilterState
        from sc2_replay_analyzer.config import set_display_columns, get_display_columns, DEFAULT_CONFIG

        set_display_columns(["date"])
        state = FilterState()
        state, error = parse_filter_command("columns reset", state)

        assert error is None
        assert get_display_columns() == DEFAULT_CONFIG["display"]["columns"]


class TestBases10mRenderer:
    """Tests for bases_10m column rendering."""

    def test_get_column_value_bases_10m(self, mock_config_dir):
        """get_column_value renders bases_10m."""
        from sc2_replay_analyzer.ui import get_column_value

        replay = {"bases_by_10m": 4}
        result = get_column_value("bases_10m", replay)
        assert result == "4"

    def test_get_column_value_bases_10m_none(self, mock_config_dir):
        """get_column_value handles None bases_10m."""
        from sc2_replay_analyzer.ui import get_column_value

        replay = {"bases_by_10m": None}
        result = get_column_value("bases_10m", replay)
        assert result == "-"


class TestCalculateSummary:
    """Tests for calculate_summary function."""

    def test_calculate_summary_empty(self):
        """calculate_summary returns empty dict for empty list."""
        from sc2_replay_analyzer.ui import calculate_summary

        result = calculate_summary([])
        assert result == {}

    def test_calculate_summary_counts_wins_losses(self, sample_replay_data):
        """calculate_summary counts wins and losses."""
        from sc2_replay_analyzer.ui import calculate_summary

        replays = [
            {"result": "Win", "player_apm": 100, "workers_8m": 50, "game_length_sec": 600},
            {"result": "Win", "player_apm": 120, "workers_8m": 55, "game_length_sec": 720},
            {"result": "Loss", "player_apm": 110, "workers_8m": 45, "game_length_sec": 480},
        ]

        result = calculate_summary(replays)
        assert result["wins"] == 2
        assert result["losses"] == 1
        assert result["winrate"] == pytest.approx(66.67, rel=0.1)

    def test_calculate_summary_calculates_averages(self):
        """calculate_summary calculates correct averages."""
        from sc2_replay_analyzer.ui import calculate_summary

        replays = [
            {"result": "Win", "player_apm": 100, "workers_8m": 50, "game_length_sec": 600},
            {"result": "Win", "player_apm": 200, "workers_8m": 60, "game_length_sec": 800},
        ]

        result = calculate_summary(replays)
        assert result["avg_apm"] == 150
        assert result["avg_workers_8m"] == 55
        assert result["avg_length"] == 700

    def test_calculate_summary_handles_none_values(self):
        """calculate_summary skips None values in averages."""
        from sc2_replay_analyzer.ui import calculate_summary

        replays = [
            {"result": "Win", "player_apm": 100, "workers_8m": None, "game_length_sec": 600},
            {"result": "Win", "player_apm": None, "workers_8m": 50, "game_length_sec": 720},
        ]

        result = calculate_summary(replays)
        assert result["avg_apm"] == 100  # Only one APM value
        assert result["avg_workers_8m"] == 50  # Only one workers value


class TestFormatWorkers:
    """Tests for format_workers function."""

    def test_format_workers_none(self):
        """format_workers handles None."""
        from sc2_replay_analyzer.ui import format_workers

        result = format_workers(None, 50)
        assert result.plain == "-"

    def test_format_workers_above_benchmark(self):
        """format_workers formats workers above benchmark."""
        from sc2_replay_analyzer.ui import format_workers

        result = format_workers(55, 50)
        assert "55" in result.plain
        assert "!" not in result.plain

    def test_format_workers_below_benchmark(self):
        """format_workers adds warning for below benchmark."""
        from sc2_replay_analyzer.ui import format_workers

        result = format_workers(35, 50)
        assert "35" in result.plain
        assert "!" in result.plain


class TestFormatResult:
    """Tests for format_result function."""

    def test_format_result_none(self):
        """format_result handles None/empty."""
        from sc2_replay_analyzer.ui import format_result

        assert format_result(None).plain == "-"
        assert format_result("").plain == "-"

    def test_format_result_win(self):
        """format_result formats Win."""
        from sc2_replay_analyzer.ui import format_result

        result = format_result("Win")
        assert result.plain == "Win"

    def test_format_result_loss(self):
        """format_result formats Loss."""
        from sc2_replay_analyzer.ui import format_result

        result = format_result("Loss")
        assert result.plain == "Loss"


class TestFormatArmy:
    """Tests for format_army function."""

    def test_format_army_none(self):
        """format_army handles None supply."""
        from sc2_replay_analyzer.ui import format_army

        assert format_army(None, None) == "-"
        assert format_army(None, 1000) == "-"

    def test_format_army_supply_only(self):
        """format_army shows supply when minerals is None."""
        from sc2_replay_analyzer.ui import format_army

        assert format_army(50, None) == "50"

    def test_format_army_with_value(self):
        """format_army shows supply and value."""
        from sc2_replay_analyzer.ui import format_army

        assert format_army(50, 500) == "50 (500)"

    def test_format_army_large_value(self):
        """format_army formats large values in k."""
        from sc2_replay_analyzer.ui import format_army

        assert format_army(80, 2500) == "80 (2.5k)"


class TestFormatMmr:
    """Tests for format_mmr function."""

    def test_format_mmr_none(self):
        """format_mmr handles None."""
        from sc2_replay_analyzer.ui import format_mmr

        result = format_mmr(None, None)
        assert result.plain == "-"

    def test_format_mmr_no_opponent(self):
        """format_mmr handles missing opponent MMR."""
        from sc2_replay_analyzer.ui import format_mmr

        result = format_mmr(4500, None)
        assert "4500" in result.plain

    def test_format_mmr_higher(self):
        """format_mmr shows positive diff when higher."""
        from sc2_replay_analyzer.ui import format_mmr

        result = format_mmr(4500, 4400)
        assert "4500" in result.plain
        assert "+100" in result.plain

    def test_format_mmr_lower(self):
        """format_mmr shows negative diff when lower."""
        from sc2_replay_analyzer.ui import format_mmr

        result = format_mmr(4400, 4500)
        assert "4400" in result.plain
        assert "-100" in result.plain
