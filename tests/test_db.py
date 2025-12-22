"""
Tests for sc2_replay_analyzer.db module.
"""
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


class TestInitDb:
    """Tests for database initialization."""

    def test_init_db_creates_database(self, mock_db_path):
        """init_db creates the database file."""
        from sc2_replay_analyzer.db import init_db

        init_db()
        assert mock_db_path.exists()

    def test_init_db_creates_replays_table(self, initialized_db):
        """init_db creates the replays table."""
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='replays'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "replays"

    def test_init_db_creates_indexes(self, initialized_db):
        """init_db creates required indexes."""
        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert "idx_played_at" in indexes
        assert "idx_matchup" in indexes
        assert "idx_result" in indexes
        assert "idx_map_name" in indexes

    def test_init_db_idempotent(self, initialized_db):
        """init_db can be called multiple times safely."""
        from sc2_replay_analyzer.db import init_db

        # Should not raise
        init_db()
        init_db()

        conn = sqlite3.connect(str(initialized_db))
        cursor = conn.execute("SELECT COUNT(*) FROM replays")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0  # Table exists and is empty


class TestInsertReplay:
    """Tests for replay insertion."""

    def test_insert_replay_adds_row(self, initialized_db, sample_replay_data):
        """insert_replay adds a row to the database."""
        from sc2_replay_analyzer.db import insert_replay, get_replay_count

        insert_replay(sample_replay_data)
        assert get_replay_count() == 1

    def test_insert_replay_stores_all_fields(self, initialized_db, sample_replay_data):
        """insert_replay stores all data fields."""
        from sc2_replay_analyzer.db import insert_replay, get_replays

        insert_replay(sample_replay_data)
        replays = get_replays()

        assert len(replays) == 1
        replay = replays[0]
        assert replay["replay_id"] == sample_replay_data["replay_id"]
        assert replay["map_name"] == sample_replay_data["map_name"]
        assert replay["matchup"] == sample_replay_data["matchup"]
        assert replay["result"] == sample_replay_data["result"]
        assert replay["workers_8m"] == sample_replay_data["workers_8m"]

    def test_insert_replay_replaces_on_duplicate(self, initialized_db, sample_replay_data):
        """insert_replay replaces existing replay with same ID."""
        from sc2_replay_analyzer.db import insert_replay, get_replays, get_replay_count

        insert_replay(sample_replay_data)

        # Insert again with different result
        modified_data = sample_replay_data.copy()
        modified_data["result"] = "Loss"
        insert_replay(modified_data)

        assert get_replay_count() == 1
        replays = get_replays()
        assert replays[0]["result"] == "Loss"


class TestReplayExists:
    """Tests for replay existence check."""

    def test_replay_exists_returns_false_for_new(self, initialized_db):
        """replay_exists returns False for non-existent replay."""
        from sc2_replay_analyzer.db import replay_exists

        assert replay_exists("nonexistent123") is False

    def test_replay_exists_returns_true_for_existing(self, initialized_db, sample_replay_data):
        """replay_exists returns True for existing replay."""
        from sc2_replay_analyzer.db import insert_replay, replay_exists

        insert_replay(sample_replay_data)
        assert replay_exists(sample_replay_data["replay_id"]) is True


class TestGetReplays:
    """Tests for replay querying."""

    def test_get_replays_returns_list(self, initialized_db):
        """get_replays returns a list."""
        from sc2_replay_analyzer.db import get_replays

        result = get_replays()
        assert isinstance(result, list)

    def test_get_replays_returns_empty_for_no_data(self, initialized_db):
        """get_replays returns empty list when no data."""
        from sc2_replay_analyzer.db import get_replays

        result = get_replays()
        assert result == []

    def test_get_replays_returns_all_replays(self, db_with_replays):
        """get_replays returns all replays when no filters."""
        from sc2_replay_analyzer.db import get_replays

        replays = get_replays()
        assert len(replays) == 3

    def test_get_replays_ordered_by_date_desc(self, db_with_replays):
        """get_replays returns replays ordered by date descending."""
        from sc2_replay_analyzer.db import get_replays

        replays = get_replays()
        dates = [r["played_at"] for r in replays]
        assert dates == sorted(dates, reverse=True)

    def test_get_replays_filter_by_matchup(self, db_with_replays):
        """get_replays filters by matchup."""
        from sc2_replay_analyzer.db import get_replays

        replays = get_replays(matchup="TvZ")
        assert len(replays) == 2  # Win and Loss are both TvZ
        for r in replays:
            assert r["matchup"] == "TvZ"

    def test_get_replays_filter_by_matchup_case_insensitive(self, db_with_replays):
        """get_replays matchup filter is case insensitive."""
        from sc2_replay_analyzer.db import get_replays

        replays_lower = get_replays(matchup="tvz")
        replays_upper = get_replays(matchup="TVZ")
        assert len(replays_lower) == len(replays_upper)

    def test_get_replays_filter_by_result(self, db_with_replays):
        """get_replays filters by result."""
        from sc2_replay_analyzer.db import get_replays

        wins = get_replays(result="Win")
        losses = get_replays(result="Loss")

        assert len(wins) == 2
        assert len(losses) == 1
        assert all(r["result"] == "Win" for r in wins)
        assert all(r["result"] == "Loss" for r in losses)

    def test_get_replays_filter_by_map(self, db_with_replays):
        """get_replays filters by map name (partial match)."""
        from sc2_replay_analyzer.db import get_replays

        replays = get_replays(map_name="Alcyone")
        assert len(replays) == 3  # All have "Alcyone LE"

    def test_get_replays_filter_by_limit(self, db_with_replays):
        """get_replays respects limit parameter."""
        from sc2_replay_analyzer.db import get_replays

        replays = get_replays(limit=2)
        assert len(replays) == 2

    def test_get_replays_filter_by_min_length(self, db_with_replays):
        """get_replays filters by minimum game length."""
        from sc2_replay_analyzer.db import get_replays

        # All sample replays are 720 seconds
        replays = get_replays(min_length=700)
        assert len(replays) == 3

        replays = get_replays(min_length=800)
        assert len(replays) == 0

    def test_get_replays_filter_by_max_length(self, db_with_replays):
        """get_replays filters by maximum game length."""
        from sc2_replay_analyzer.db import get_replays

        replays = get_replays(max_length=800)
        assert len(replays) == 3

        replays = get_replays(max_length=600)
        assert len(replays) == 0

    def test_get_replays_filter_by_min_workers(self, db_with_replays):
        """get_replays filters by minimum workers at 8m."""
        from sc2_replay_analyzer.db import get_replays

        # 2 replays have workers_8m=55, 1 has workers_8m=38
        replays = get_replays(min_workers_8m=50)
        assert len(replays) == 2

    def test_get_replays_filter_by_max_workers(self, db_with_replays):
        """get_replays filters by maximum workers at 8m."""
        from sc2_replay_analyzer.db import get_replays

        replays = get_replays(max_workers_8m=40)
        assert len(replays) == 1
        assert replays[0]["workers_8m"] == 38

    def test_get_replays_combined_filters(self, db_with_replays):
        """get_replays handles multiple filters."""
        from sc2_replay_analyzer.db import get_replays

        replays = get_replays(matchup="TvZ", result="Win")
        assert len(replays) == 1


class TestGetLatestReplay:
    """Tests for get_latest_replay."""

    def test_get_latest_replay_returns_none_when_empty(self, initialized_db):
        """get_latest_replay returns None when no replays."""
        from sc2_replay_analyzer.db import get_latest_replay

        assert get_latest_replay() is None

    def test_get_latest_replay_returns_most_recent(self, db_with_replays):
        """get_latest_replay returns the most recently played replay."""
        from sc2_replay_analyzer.db import get_latest_replay

        latest = get_latest_replay()
        assert latest is not None
        assert latest["played_at"] == "2024-12-15T12:00:00+00:00"


class TestGetStats:
    """Tests for aggregate statistics."""

    def test_get_stats_empty_db(self, initialized_db):
        """get_stats handles empty database."""
        from sc2_replay_analyzer.db import get_stats

        stats = get_stats()
        assert stats["total_games"] == 0

    def test_get_stats_counts_games(self, db_with_replays):
        """get_stats counts total games."""
        from sc2_replay_analyzer.db import get_stats

        stats = get_stats()
        assert stats["total_games"] == 3

    def test_get_stats_counts_wins_losses(self, db_with_replays):
        """get_stats counts wins and losses."""
        from sc2_replay_analyzer.db import get_stats

        stats = get_stats()
        assert stats["wins"] == 2
        assert stats["losses"] == 1

    def test_get_stats_calculates_averages(self, db_with_replays):
        """get_stats calculates average metrics."""
        from sc2_replay_analyzer.db import get_stats

        stats = get_stats()
        assert stats["avg_workers_8m"] is not None
        assert stats["avg_game_length"] is not None

    def test_get_stats_filter_by_matchup(self, db_with_replays):
        """get_stats filters by matchup."""
        from sc2_replay_analyzer.db import get_stats

        stats = get_stats(matchup="TvZ")
        assert stats["total_games"] == 2

        stats = get_stats(matchup="TvP")
        assert stats["total_games"] == 1


class TestGetStatsByMatchup:
    """Tests for matchup breakdown statistics."""

    def test_get_stats_by_matchup_groups_correctly(self, db_with_replays):
        """get_stats_by_matchup groups by matchup."""
        from sc2_replay_analyzer.db import get_stats_by_matchup

        stats = get_stats_by_matchup()

        assert len(stats) == 2  # TvZ and TvP
        matchups = {s["matchup"] for s in stats}
        assert matchups == {"TvZ", "TvP"}

    def test_get_stats_by_matchup_counts_wins(self, db_with_replays):
        """get_stats_by_matchup counts wins per matchup."""
        from sc2_replay_analyzer.db import get_stats_by_matchup

        stats = get_stats_by_matchup()

        tvz_stats = next(s for s in stats if s["matchup"] == "TvZ")
        assert tvz_stats["total_games"] == 2
        assert tvz_stats["wins"] == 1


class TestGetReplayCount:
    """Tests for replay count."""

    def test_get_replay_count_empty(self, initialized_db):
        """get_replay_count returns 0 for empty db."""
        from sc2_replay_analyzer.db import get_replay_count

        assert get_replay_count() == 0

    def test_get_replay_count_with_data(self, db_with_replays):
        """get_replay_count returns correct count."""
        from sc2_replay_analyzer.db import get_replay_count

        assert get_replay_count() == 3
