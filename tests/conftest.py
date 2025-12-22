"""
Shared pytest fixtures for SC2 Replay Analyzer tests.
"""
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset config cache before and after each test to prevent leakage."""
    from sc2_replay_analyzer.config import clear_config_cache

    clear_config_cache()
    yield
    clear_config_cache()


@pytest.fixture
def temp_dir():
    """Create a temporary directory that's cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db(temp_dir):
    """Create a temporary database file path."""
    return temp_dir / "test_replays.db"


@pytest.fixture
def mock_config_dir(temp_dir):
    """Mock the config directory to use a temp directory."""
    config_dir = temp_dir / ".sc2analyzer"
    config_dir.mkdir(parents=True, exist_ok=True)

    with patch("sc2_replay_analyzer.config.get_config_dir", return_value=config_dir):
        yield config_dir


@pytest.fixture
def mock_db_path(temp_dir):
    """Mock the database path to use a temp directory."""
    db_path = temp_dir / "test_replays.db"

    with patch("sc2_replay_analyzer.db.get_db_path", return_value=db_path):
        with patch("sc2_replay_analyzer.db.ensure_config_dir"):
            yield db_path


@pytest.fixture
def sample_replay_data():
    """Sample parsed replay data for testing."""
    return {
        "replay_id": "abc123def456",
        "file_path": "/path/to/replay.SC2Replay",
        "played_at": "2024-12-15T12:00:00+00:00",
        "map_name": "Alcyone LE",
        "player_race": "Terran",
        "opponent_race": "Zerg",
        "matchup": "TvZ",
        "result": "Win",
        "game_length_sec": 720,
        "player_mmr": 4500,
        "opponent_mmr": 4400,
        "player_apm": 180,
        "opponent_apm": 220,
        "workers_6m": 42,
        "workers_8m": 55,
        "workers_10m": 66,
        "bases_by_6m": 2,
        "bases_by_8m": 3,
        "natural_timing": 90,
        "third_timing": 240,
        "army_supply_8m": 45,
        "army_minerals_8m": 2500,
        "army_gas_8m": 800,
        "worker_kills_8m": 5,
        "worker_losses_8m": 2,
        "first_attack_time": 300,
        "parsed_at": "2024-12-15T12:05:00+00:00",
    }


@pytest.fixture
def sample_unit_data():
    """Sample unit tracking data for testing alive_at and army calculations."""
    return {
        1: {"name": "SCV", "born": 0, "died": None, "pid": 1, "supply": 1, "minerals": 50, "vespene": 0, "is_army": False},
        2: {"name": "SCV", "born": 12, "died": None, "pid": 1, "supply": 1, "minerals": 50, "vespene": 0, "is_army": False},
        3: {"name": "SCV", "born": 24, "died": 200, "pid": 1, "supply": 1, "minerals": 50, "vespene": 0, "is_army": False},
        4: {"name": "Marine", "born": 60, "died": None, "pid": 1, "supply": 1, "minerals": 50, "vespene": 0, "is_army": True},
        5: {"name": "Marine", "born": 70, "died": 300, "pid": 1, "supply": 1, "minerals": 50, "vespene": 0, "is_army": True},
        6: {"name": "Marauder", "born": 120, "died": None, "pid": 1, "supply": 2, "minerals": 100, "vespene": 25, "is_army": True},
        7: {"name": "Drone", "born": 0, "died": None, "pid": 2, "supply": 1, "minerals": 50, "vespene": 0, "is_army": False},
        8: {"name": "Zergling", "born": 100, "died": None, "pid": 2, "supply": 0.5, "minerals": 25, "vespene": 0, "is_army": True},
    }


@pytest.fixture
def initialized_db(mock_db_path):
    """Initialize a test database with schema."""
    from sc2_replay_analyzer import db

    db.init_db()
    yield mock_db_path


@pytest.fixture
def db_with_replays(initialized_db, sample_replay_data):
    """Database populated with sample replay data."""
    from sc2_replay_analyzer import db

    # Insert a few variations of replay data
    db.insert_replay(sample_replay_data)

    # Add a loss
    loss_data = sample_replay_data.copy()
    loss_data["replay_id"] = "loss123"
    loss_data["result"] = "Loss"
    loss_data["played_at"] = "2024-12-14T12:00:00+00:00"
    loss_data["workers_8m"] = 38
    db.insert_replay(loss_data)

    # Add a TvP game
    tvp_data = sample_replay_data.copy()
    tvp_data["replay_id"] = "tvp123"
    tvp_data["matchup"] = "TvP"
    tvp_data["opponent_race"] = "Protoss"
    tvp_data["played_at"] = "2024-12-13T12:00:00+00:00"
    db.insert_replay(tvp_data)

    yield initialized_db
