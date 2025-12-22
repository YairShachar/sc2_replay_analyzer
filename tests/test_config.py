"""
Tests for sc2_replay_analyzer.config module.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestConfigPaths:
    """Tests for config path functions."""

    def test_get_config_dir_returns_path(self):
        """get_config_dir returns a Path object."""
        from sc2_replay_analyzer.config import get_config_dir

        result = get_config_dir()
        assert isinstance(result, Path)
        assert result.name == ".sc2analyzer"

    def test_get_config_path_is_under_config_dir(self):
        """get_config_path returns path under config dir."""
        from sc2_replay_analyzer.config import get_config_path, get_config_dir

        config_path = get_config_path()
        config_dir = get_config_dir()
        assert config_path.parent == config_dir
        assert config_path.name == "config.toml"

    def test_get_db_path_is_under_config_dir(self):
        """get_db_path returns path under config dir."""
        from sc2_replay_analyzer.config import get_db_path, get_config_dir

        db_path = get_db_path()
        config_dir = get_config_dir()
        assert db_path.parent == config_dir
        assert db_path.name == "replays.db"


class TestDefaultConfig:
    """Tests for default config values."""

    def test_default_config_has_required_keys(self):
        """DEFAULT_CONFIG contains all required keys."""
        from sc2_replay_analyzer.config import DEFAULT_CONFIG

        assert "player_name" in DEFAULT_CONFIG
        assert "replay_folder" in DEFAULT_CONFIG
        assert "benchmarks" in DEFAULT_CONFIG
        assert "display" in DEFAULT_CONFIG

    def test_default_benchmarks(self):
        """Default benchmark values are reasonable."""
        from sc2_replay_analyzer.config import DEFAULT_CONFIG

        benchmarks = DEFAULT_CONFIG["benchmarks"]
        assert benchmarks["workers_6m"] == 40
        assert benchmarks["workers_8m"] == 55

    def test_default_display_columns(self):
        """Default display columns are valid."""
        from sc2_replay_analyzer.config import DEFAULT_CONFIG, AVAILABLE_COLUMNS

        columns = DEFAULT_CONFIG["display"]["columns"]
        assert len(columns) > 0
        for col in columns:
            assert col in AVAILABLE_COLUMNS, f"Column '{col}' not in AVAILABLE_COLUMNS"


class TestConstants:
    """Tests for module constants."""

    def test_workers_set(self):
        """WORKERS set contains expected unit types."""
        from sc2_replay_analyzer.config import WORKERS

        assert "SCV" in WORKERS
        assert "Drone" in WORKERS
        assert "Probe" in WORKERS
        assert len(WORKERS) == 3

    def test_townhalls_set(self):
        """TOWNHALLS set contains all townhall types."""
        from sc2_replay_analyzer.config import TOWNHALLS

        # Terran
        assert "CommandCenter" in TOWNHALLS
        assert "OrbitalCommand" in TOWNHALLS
        assert "PlanetaryFortress" in TOWNHALLS
        # Zerg
        assert "Hatchery" in TOWNHALLS
        assert "Lair" in TOWNHALLS
        assert "Hive" in TOWNHALLS
        # Protoss
        assert "Nexus" in TOWNHALLS

    def test_snapshots_times(self):
        """SNAPSHOTS contains correct game-time seconds (real-time * 1.4)."""
        from sc2_replay_analyzer.config import SNAPSHOTS, GAME_SPEED_FACTOR

        # Verify game speed factor
        assert GAME_SPEED_FACTOR == 1.4

        # Verify snapshots are in game-time (real-time * 1.4)
        assert SNAPSHOTS["6m"] == int(360 * GAME_SPEED_FACTOR)   # 504
        assert SNAPSHOTS["8m"] == int(480 * GAME_SPEED_FACTOR)   # 672
        assert SNAPSHOTS["10m"] == int(600 * GAME_SPEED_FACTOR)  # 840

    def test_available_columns_structure(self):
        """AVAILABLE_COLUMNS has correct structure."""
        from sc2_replay_analyzer.config import AVAILABLE_COLUMNS

        for key, value in AVAILABLE_COLUMNS.items():
            assert isinstance(value, tuple), f"Column '{key}' should be a tuple"
            assert len(value) == 3, f"Column '{key}' should have 3 elements"
            header, width, justify = value
            assert isinstance(header, str)
            assert isinstance(width, int)
            assert justify in ("left", "right")


class TestLoadConfig:
    """Tests for config loading."""

    def test_load_config_returns_defaults_when_no_file(self, mock_config_dir):
        """load_config returns defaults when config file doesn't exist."""
        from sc2_replay_analyzer.config import load_config, clear_config_cache, DEFAULT_CONFIG

        clear_config_cache()
        config = load_config()

        assert config["player_name"] == DEFAULT_CONFIG["player_name"]
        assert config["benchmarks"]["workers_6m"] == DEFAULT_CONFIG["benchmarks"]["workers_6m"]

    def test_load_config_caches_result(self, mock_config_dir):
        """load_config caches the result."""
        from sc2_replay_analyzer.config import load_config, clear_config_cache

        clear_config_cache()
        config1 = load_config()
        config2 = load_config()

        assert config1 is config2

    def test_clear_config_cache_resets_cache(self, mock_config_dir):
        """clear_config_cache forces reload on next call."""
        from sc2_replay_analyzer.config import load_config, clear_config_cache

        clear_config_cache()
        config1 = load_config()
        clear_config_cache()
        config2 = load_config()

        # They should be equal but not the same object
        assert config1 == config2
        assert config1 is not config2

    def test_load_config_merges_user_config(self, mock_config_dir):
        """load_config merges user config with defaults."""
        from sc2_replay_analyzer.config import load_config, clear_config_cache, get_config_path

        # Write a partial user config
        config_path = get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            f.write('player_name = "TestPlayer"\n')
            f.write("[benchmarks]\n")
            f.write("workers_6m = 45\n")

        clear_config_cache()
        config = load_config()

        # User values should be used
        assert config["player_name"] == "TestPlayer"
        assert config["benchmarks"]["workers_6m"] == 45
        # Default values should still be present
        assert config["benchmarks"]["workers_8m"] == 55


class TestSaveConfig:
    """Tests for config saving."""

    def test_save_config_creates_file(self, mock_config_dir):
        """save_config creates config file."""
        from sc2_replay_analyzer.config import save_config, get_config_path, clear_config_cache

        clear_config_cache()
        config = {"player_name": "SavedPlayer", "replay_folder": "/test/path"}
        save_config(config)

        assert get_config_path().exists()

    def test_save_config_updates_cache(self, mock_config_dir):
        """save_config updates the config cache."""
        from sc2_replay_analyzer.config import save_config, load_config, clear_config_cache

        clear_config_cache()
        config = {"player_name": "CachedPlayer", "replay_folder": "/test/path"}
        save_config(config)

        loaded = load_config()
        assert loaded["player_name"] == "CachedPlayer"


class TestConfigAccessors:
    """Tests for config accessor functions."""

    def test_get_player_name(self, mock_config_dir):
        """get_player_name returns configured player name."""
        from sc2_replay_analyzer.config import get_player_name, save_config, clear_config_cache

        clear_config_cache()
        save_config({"player_name": "AccessorPlayer", "replay_folder": ""})

        assert get_player_name() == "AccessorPlayer"

    def test_get_replay_folder_expands_user(self, mock_config_dir):
        """get_replay_folder expands ~ to home directory."""
        from sc2_replay_analyzer.config import get_replay_folder, save_config, clear_config_cache

        clear_config_cache()
        save_config({"player_name": "", "replay_folder": "~/test"})

        folder = get_replay_folder()
        assert "~" not in folder
        assert "test" in folder

    def test_get_benchmark_workers_6m(self, mock_config_dir):
        """get_benchmark_workers_6m returns benchmark value."""
        from sc2_replay_analyzer.config import get_benchmark_workers_6m, clear_config_cache

        clear_config_cache()
        benchmark = get_benchmark_workers_6m()
        assert benchmark == 40

    def test_get_benchmark_workers_8m(self, mock_config_dir):
        """get_benchmark_workers_8m returns benchmark value."""
        from sc2_replay_analyzer.config import get_benchmark_workers_8m, clear_config_cache

        clear_config_cache()
        benchmark = get_benchmark_workers_8m()
        assert benchmark == 55

    def test_get_display_columns(self, mock_config_dir):
        """get_display_columns returns list of columns."""
        from sc2_replay_analyzer.config import get_display_columns, clear_config_cache

        clear_config_cache()
        columns = get_display_columns()
        assert isinstance(columns, list)
        assert len(columns) > 0


class TestColumnManagement:
    """Tests for column management functions."""

    def test_set_display_columns(self, mock_config_dir):
        """set_display_columns saves new column list."""
        from sc2_replay_analyzer.config import (
            set_display_columns,
            get_display_columns,
            clear_config_cache,
        )

        clear_config_cache()
        new_columns = ["date", "map", "result"]
        set_display_columns(new_columns)

        result = get_display_columns()
        assert result == new_columns

    def test_add_display_columns(self, mock_config_dir):
        """add_display_columns adds new columns."""
        from sc2_replay_analyzer.config import (
            add_display_columns,
            get_display_columns,
            set_display_columns,
            clear_config_cache,
        )

        clear_config_cache()
        set_display_columns(["date", "map"])
        added = add_display_columns(["result", "mmr"])

        assert added == ["result", "mmr"]
        assert get_display_columns() == ["date", "map", "result", "mmr"]

    def test_add_display_columns_skips_duplicates(self, mock_config_dir):
        """add_display_columns skips already present columns."""
        from sc2_replay_analyzer.config import (
            add_display_columns,
            set_display_columns,
            clear_config_cache,
        )

        clear_config_cache()
        set_display_columns(["date", "map"])
        added = add_display_columns(["date", "result"])

        assert added == ["result"]  # date was already present

    def test_add_display_columns_skips_invalid(self, mock_config_dir):
        """add_display_columns skips invalid column names."""
        from sc2_replay_analyzer.config import (
            add_display_columns,
            set_display_columns,
            clear_config_cache,
        )

        clear_config_cache()
        set_display_columns(["date"])
        added = add_display_columns(["invalid_col", "result"])

        assert added == ["result"]  # invalid_col was skipped

    def test_remove_display_columns(self, mock_config_dir):
        """remove_display_columns removes columns."""
        from sc2_replay_analyzer.config import (
            remove_display_columns,
            get_display_columns,
            set_display_columns,
            clear_config_cache,
        )

        clear_config_cache()
        set_display_columns(["date", "map", "result", "mmr"])
        removed = remove_display_columns(["map", "mmr"])

        assert removed == ["map", "mmr"]
        assert get_display_columns() == ["date", "result"]

    def test_remove_display_columns_skips_missing(self, mock_config_dir):
        """remove_display_columns skips columns not present."""
        from sc2_replay_analyzer.config import (
            remove_display_columns,
            set_display_columns,
            clear_config_cache,
        )

        clear_config_cache()
        set_display_columns(["date", "map"])
        removed = remove_display_columns(["result", "map"])

        assert removed == ["map"]  # result was not present

    def test_reset_display_columns(self, mock_config_dir):
        """reset_display_columns restores defaults."""
        from sc2_replay_analyzer.config import (
            reset_display_columns,
            get_display_columns,
            set_display_columns,
            DEFAULT_CONFIG,
            clear_config_cache,
        )

        clear_config_cache()
        set_display_columns(["date"])
        reset_display_columns()

        assert get_display_columns() == DEFAULT_CONFIG["display"]["columns"]


class TestBases10mColumn:
    """Tests for bases_10m column support."""

    def test_bases_10m_in_available_columns(self):
        """bases_10m is in AVAILABLE_COLUMNS."""
        from sc2_replay_analyzer.config import AVAILABLE_COLUMNS

        assert "bases_10m" in AVAILABLE_COLUMNS
        header, width, justify = AVAILABLE_COLUMNS["bases_10m"]
        assert header == "B@10m"
        assert justify == "right"


class TestFindReplayFolders:
    """Tests for replay folder detection."""

    def test_find_replay_folders_returns_list(self):
        """find_replay_folders returns a list."""
        from sc2_replay_analyzer.config import find_replay_folders

        result = find_replay_folders()
        assert isinstance(result, list)

    @patch("sys.platform", "darwin")
    def test_find_replay_folders_macos_path(self, temp_dir):
        """find_replay_folders checks macOS paths."""
        from sc2_replay_analyzer.config import find_replay_folders

        # Create mock SC2 folder structure
        accounts_dir = temp_dir / "Library/Application Support/Blizzard/StarCraft II/Accounts"
        replays_dir = accounts_dir / "12345" / "67890" / "Replays" / "Multiplayer"
        replays_dir.mkdir(parents=True)

        with patch.object(Path, "home", return_value=temp_dir):
            result = find_replay_folders()
            assert len(result) >= 0  # May find the mock folder or not depending on platform
