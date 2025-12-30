"""
Tests for sc2_replay_analyzer.parser module.
"""
import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestSha1:
    """Tests for sha1 hash function."""

    def test_sha1_generates_hash(self, temp_dir):
        """sha1 generates a valid SHA1 hash."""
        from sc2_replay_analyzer.parser import sha1

        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        result = sha1(str(test_file))
        assert len(result) == 40  # SHA1 produces 40 hex characters
        assert all(c in "0123456789abcdef" for c in result)

    def test_sha1_consistent_for_same_content(self, temp_dir):
        """sha1 returns same hash for same content."""
        from sc2_replay_analyzer.parser import sha1

        # Create two files with same content
        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.write_text("identical content")
        file2.write_text("identical content")

        assert sha1(str(file1)) == sha1(str(file2))

    def test_sha1_different_for_different_content(self, temp_dir):
        """sha1 returns different hash for different content."""
        from sc2_replay_analyzer.parser import sha1

        file1 = temp_dir / "file1.txt"
        file2 = temp_dir / "file2.txt"
        file1.write_text("content A")
        file2.write_text("content B")

        assert sha1(str(file1)) != sha1(str(file2))


class TestSafeUtc:
    """Tests for safe_utc datetime conversion."""

    def test_safe_utc_with_none(self):
        """safe_utc returns empty string for None."""
        from sc2_replay_analyzer.parser import safe_utc

        assert safe_utc(None) == ""

    def test_safe_utc_with_naive_datetime(self):
        """safe_utc adds UTC timezone to naive datetime."""
        from sc2_replay_analyzer.parser import safe_utc

        dt = datetime(2024, 12, 15, 12, 0, 0)
        result = safe_utc(dt)
        assert "+00:00" in result or "Z" in result
        assert "2024-12-15" in result

    def test_safe_utc_with_aware_datetime(self):
        """safe_utc converts aware datetime to UTC."""
        from sc2_replay_analyzer.parser import safe_utc

        dt = datetime(2024, 12, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = safe_utc(dt)
        assert "2024-12-15" in result
        assert isinstance(result, str)

    def test_safe_utc_returns_iso_format(self):
        """safe_utc returns ISO format string."""
        from sc2_replay_analyzer.parser import safe_utc

        dt = datetime(2024, 12, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = safe_utc(dt)
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(result)
        assert parsed.year == 2024
        assert parsed.month == 12
        assert parsed.day == 15


class TestAliveAt:
    """Tests for alive_at function (counts units alive at a time)."""

    def test_alive_at_counts_units(self, sample_unit_data):
        """alive_at counts units that are alive at given time."""
        from sc2_replay_analyzer.parser import alive_at

        # Count SCVs for player 1 at time 100
        # Unit 1: born 0, not dead -> alive
        # Unit 2: born 12, not dead -> alive
        # Unit 3: born 24, died 200 -> alive at 100
        count = alive_at(sample_unit_data, pid=1, names={"SCV"}, t=100)
        assert count == 3

    def test_alive_at_excludes_not_yet_born(self, sample_unit_data):
        """alive_at excludes units not yet born."""
        from sc2_replay_analyzer.parser import alive_at

        # At time 10, only unit 1 is born
        count = alive_at(sample_unit_data, pid=1, names={"SCV"}, t=10)
        assert count == 1

    def test_alive_at_excludes_dead_units(self, sample_unit_data):
        """alive_at excludes units that have died."""
        from sc2_replay_analyzer.parser import alive_at

        # At time 250, unit 3 (died at 200) should not be counted
        count = alive_at(sample_unit_data, pid=1, names={"SCV"}, t=250)
        assert count == 2

    def test_alive_at_filters_by_player(self, sample_unit_data):
        """alive_at only counts units for specified player."""
        from sc2_replay_analyzer.parser import alive_at

        # Player 2 only has 1 Drone
        count = alive_at(sample_unit_data, pid=2, names={"Drone"}, t=100)
        assert count == 1

        # Player 1 has no Drones
        count = alive_at(sample_unit_data, pid=1, names={"Drone"}, t=100)
        assert count == 0

    def test_alive_at_with_multiple_unit_types(self, sample_unit_data):
        """alive_at counts multiple unit types."""
        from sc2_replay_analyzer.parser import alive_at

        workers = {"SCV", "Drone", "Probe"}
        # At time 100: 3 SCVs for player 1, no Drones/Probes
        count = alive_at(sample_unit_data, pid=1, names=workers, t=100)
        assert count == 3

    def test_alive_at_edge_case_born_exactly_at_time(self, sample_unit_data):
        """alive_at includes units born exactly at the given time."""
        from sc2_replay_analyzer.parser import alive_at

        # Unit 4 (Marine) born at 60
        count = alive_at(sample_unit_data, pid=1, names={"Marine"}, t=60)
        assert count == 1

    def test_alive_at_edge_case_died_exactly_at_time(self, sample_unit_data):
        """alive_at excludes units that died exactly at the given time."""
        from sc2_replay_analyzer.parser import alive_at

        # Unit 3 died at 200, so at t=200 it should NOT be counted
        count = alive_at(sample_unit_data, pid=1, names={"SCV"}, t=200)
        assert count == 2


class TestArmySupplyAt:
    """Tests for army_supply_at function."""

    def test_army_supply_at_counts_army_units(self, sample_unit_data):
        """army_supply_at sums supply of army units."""
        from sc2_replay_analyzer.parser import army_supply_at

        # At time 150:
        # Unit 4: Marine (supply 1) - alive
        # Unit 5: Marine (supply 1) - alive (dies at 300)
        # Unit 6: Marauder (supply 2) - alive
        # Total army supply for player 1: 4
        supply = army_supply_at(sample_unit_data, pid=1, t=150)
        assert supply == 4

    def test_army_supply_at_excludes_non_army(self, sample_unit_data):
        """army_supply_at excludes non-army units (workers)."""
        from sc2_replay_analyzer.parser import army_supply_at

        # Workers are not counted as army
        supply = army_supply_at(sample_unit_data, pid=1, t=50)
        assert supply == 0  # No army units born yet

    def test_army_supply_at_excludes_dead(self, sample_unit_data):
        """army_supply_at excludes dead army units."""
        from sc2_replay_analyzer.parser import army_supply_at

        # At time 350: Marine (unit 5) died at 300
        # Remaining: Marine (unit 4) + Marauder (unit 6) = 3 supply
        supply = army_supply_at(sample_unit_data, pid=1, t=350)
        assert supply == 3

    def test_army_supply_at_filters_by_player(self, sample_unit_data):
        """army_supply_at only counts specified player's army."""
        from sc2_replay_analyzer.parser import army_supply_at

        # Player 2 has 1 Zergling (supply 0.5)
        supply = army_supply_at(sample_unit_data, pid=2, t=150)
        assert supply == 0.5


class TestArmyValueAt:
    """Tests for army_value_at function."""

    def test_army_value_at_returns_tuple(self, sample_unit_data):
        """army_value_at returns (minerals, gas) tuple."""
        from sc2_replay_analyzer.parser import army_value_at

        result = army_value_at(sample_unit_data, pid=1, t=150)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_army_value_at_sums_values(self, sample_unit_data):
        """army_value_at sums mineral and gas costs."""
        from sc2_replay_analyzer.parser import army_value_at

        # At time 150:
        # Unit 4: Marine - 50 minerals, 0 gas
        # Unit 5: Marine - 50 minerals, 0 gas
        # Unit 6: Marauder - 100 minerals, 25 gas
        # Total: 200 minerals, 25 gas
        minerals, gas = army_value_at(sample_unit_data, pid=1, t=150)
        assert minerals == 200
        assert gas == 25

    def test_army_value_at_excludes_non_army(self, sample_unit_data):
        """army_value_at excludes worker value."""
        from sc2_replay_analyzer.parser import army_value_at

        # At time 50, no army units are alive yet
        minerals, gas = army_value_at(sample_unit_data, pid=1, t=50)
        assert minerals == 0
        assert gas == 0


class TestExtractUnits:
    """Tests for extract_units function."""

    def test_extract_units_from_mock_replay(self):
        """extract_units extracts unit data from replay events."""
        from sc2_replay_analyzer.parser import extract_units
        from sc2reader.events import tracker as tr

        # Create mock replay with events
        mock_replay = MagicMock()

        # Create mock UnitBornEvent
        mock_unit = MagicMock()
        mock_unit.name = "Marine"
        mock_unit.supply = 1
        mock_unit.minerals = 50
        mock_unit.vespene = 0
        mock_unit.is_army = True

        born_event = MagicMock(spec=tr.UnitBornEvent)
        born_event.unit = mock_unit
        born_event.unit_id = 1
        born_event.unit_type_name = "Marine"
        born_event.second = 60
        born_event.control_pid = 1

        # Create mock UnitDiedEvent
        died_event = MagicMock(spec=tr.UnitDiedEvent)
        died_event.unit_id = 1
        died_event.second = 300

        mock_replay.tracker_events = [born_event, died_event]

        units = extract_units(mock_replay)

        assert 1 in units
        assert units[1]["name"] == "Marine"
        assert units[1]["born"] == 60
        assert units[1]["died"] == 300
        assert units[1]["pid"] == 1


class TestParseReplay:
    """Tests for parse_replay function."""

    def test_parse_replay_returns_none_for_missing_player(self):
        """parse_replay returns None if player not in replay."""
        from sc2_replay_analyzer.parser import parse_replay

        # Create mock replay without our player
        mock_player = MagicMock()
        mock_player.name = "OtherPlayer"
        mock_player.play_race = "Terran"

        mock_replay = MagicMock()
        mock_replay.players = [mock_player]

        with patch("sc2reader.load_replay", return_value=mock_replay):
            with patch("sc2_replay_analyzer.parser.sha1", return_value="abc123"):
                result = parse_replay("/fake/path.SC2Replay", player_name="MyPlayer")

        assert result is None

    def test_parse_replay_extracts_matchup(self):
        """parse_replay correctly formats matchup string."""
        from sc2_replay_analyzer.parser import parse_replay

        # Create mock replay
        mock_player1 = MagicMock()
        mock_player1.name = "TestPlayer"
        mock_player1.play_race = "Terran"
        mock_player1.pid = 1
        mock_player1.result = "Win"
        mock_player1.init_data = {"scaled_rating": 4500}
        mock_player1.events = [MagicMock() for _ in range(100)]

        mock_player2 = MagicMock()
        mock_player2.name = "Opponent"
        mock_player2.play_race = "Zerg"
        mock_player2.pid = 2
        mock_player2.init_data = {"scaled_rating": 4400}
        mock_player2.events = [MagicMock() for _ in range(150)]

        mock_replay = MagicMock()
        mock_replay.players = [mock_player1, mock_player2]
        mock_replay.date = datetime(2024, 12, 15, 12, 0, 0)
        mock_replay.map_name = "Test Map"
        mock_replay.length.total_seconds.return_value = 720
        mock_replay.tracker_events = []

        with patch("sc2reader.load_replay", return_value=mock_replay):
            with patch("sc2_replay_analyzer.parser.sha1", return_value="abc123"):
                result = parse_replay("/fake/path.SC2Replay", player_name="TestPlayer")

        assert result is not None
        assert result["matchup"] == "TvZ"
        assert result["result"] == "Win"
        assert result["player_race"] == "Terran"
        assert result["opponent_race"] == "Zerg"
        assert result["opponent_name"] == "Opponent"
