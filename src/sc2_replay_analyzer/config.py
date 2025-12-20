"""
SC2 Replay Analyzer Configuration

Handles loading/saving user config and auto-detection of SC2 paths.
"""
import os
import sys
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib

import tomli_w


# ============================================================
# PATHS
# ============================================================

def get_config_dir() -> Path:
    """Get the config directory path (~/.sc2analyzer)."""
    return Path.home() / ".sc2analyzer"


def get_config_path() -> Path:
    """Get the config file path (~/.sc2analyzer/config.toml)."""
    return get_config_dir() / "config.toml"


def get_db_path() -> Path:
    """Get the database file path (~/.sc2analyzer/replays.db)."""
    return get_config_dir() / "replays.db"


def ensure_config_dir():
    """Create the config directory if it doesn't exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)


def config_exists() -> bool:
    """Check if config file exists."""
    return get_config_path().exists()


# ============================================================
# DEFAULT VALUES
# ============================================================

DEFAULT_CONFIG = {
    "player_name": "",
    "replay_folder": "",
    "benchmarks": {
        "workers_6m": 40,
        "workers_8m": 55,
    },
    "display": {
        "columns": [
            "date",
            "map",
            "matchup",
            "result",
            "mmr",
            "apm",
            "workers_8m",
            "army",
            "length",
        ],
    },
}

# Unit classifications (constant, not configurable)
WORKERS = {"SCV", "Drone", "Probe"}
TOWNHALLS = {
    "CommandCenter", "OrbitalCommand", "PlanetaryFortress",
    "Hatchery", "Lair", "Hive",
    "Nexus",
}

# Time snapshots for metrics (in seconds)
SNAPSHOTS = {
    "6m": 360,
    "8m": 480,
    "10m": 600,
}

# Available columns for display
AVAILABLE_COLUMNS = {
    "date": ("Date", 12, "left"),
    "map": ("Map", 14, "left"),
    "matchup": ("vs", 5, "left"),
    "result": ("Result", 6, "left"),
    "mmr": ("MMR", 12, "right"),
    "opponent_mmr": ("Opp MMR", 8, "right"),
    "apm": ("APM", 5, "right"),
    "opponent_apm": ("Opp APM", 7, "right"),
    "workers_6m": ("W@6m", 5, "right"),
    "workers_8m": ("W@8m", 5, "right"),
    "workers_10m": ("W@10m", 6, "right"),
    "army": ("Army@8m", 10, "right"),
    "length": ("Length", 7, "right"),
    "bases_6m": ("B@6m", 5, "right"),
    "bases_8m": ("B@8m", 5, "right"),
    "worker_kills": ("Kills", 5, "right"),
    "worker_losses": ("Deaths", 6, "right"),
}


# ============================================================
# CONFIG LOADING/SAVING
# ============================================================

_config_cache: Optional[dict] = None


def load_config() -> dict:
    """Load config from file, or return defaults if not found."""
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    config = DEFAULT_CONFIG.copy()

    if config_exists():
        with open(get_config_path(), "rb") as f:
            user_config = tomllib.load(f)

        # Merge user config with defaults
        config["player_name"] = user_config.get("player_name", "")
        config["replay_folder"] = user_config.get("replay_folder", "")

        if "benchmarks" in user_config:
            config["benchmarks"].update(user_config["benchmarks"])

        if "display" in user_config:
            config["display"].update(user_config["display"])

    _config_cache = config
    return config


def save_config(config: dict):
    """Save config to file."""
    global _config_cache

    ensure_config_dir()

    with open(get_config_path(), "wb") as f:
        tomli_w.dump(config, f)

    _config_cache = config


def clear_config_cache():
    """Clear the config cache (for testing or after config changes)."""
    global _config_cache
    _config_cache = None


# ============================================================
# CONFIG ACCESSORS
# ============================================================

def get_player_name() -> str:
    """Get the configured player name."""
    return load_config()["player_name"]


def get_replay_folder() -> str:
    """Get the configured replay folder path."""
    folder = load_config()["replay_folder"]
    return os.path.expanduser(folder)


def get_benchmark_workers_6m() -> int:
    """Get the 6-minute worker benchmark."""
    return load_config()["benchmarks"]["workers_6m"]


def get_benchmark_workers_8m() -> int:
    """Get the 8-minute worker benchmark."""
    return load_config()["benchmarks"]["workers_8m"]


def get_display_columns() -> list:
    """Get the list of columns to display."""
    return load_config()["display"]["columns"]


# ============================================================
# AUTO-DETECTION
# ============================================================

def find_replay_folders() -> list:
    """
    Find SC2 replay folders on the system.

    Returns a list of paths to Multiplayer replay folders.
    """
    candidates = []

    if sys.platform == "darwin":
        # macOS
        base = Path.home() / "Library/Application Support/Blizzard/StarCraft II/Accounts"
        if base.exists():
            # Pattern: Accounts/<id>/<id>/Replays/Multiplayer
            for account_dir in base.glob("*"):
                if account_dir.is_dir() and account_dir.name.isdigit():
                    for sub_dir in account_dir.glob("*"):
                        if sub_dir.is_dir():
                            replay_dir = sub_dir / "Replays" / "Multiplayer"
                            if replay_dir.exists():
                                candidates.append(str(replay_dir))

    elif sys.platform == "win32":
        # Windows
        docs = Path.home() / "Documents"
        base = docs / "StarCraft II" / "Accounts"
        if base.exists():
            for account_dir in base.glob("*"):
                if account_dir.is_dir():
                    for sub_dir in account_dir.glob("*"):
                        if sub_dir.is_dir():
                            replay_dir = sub_dir / "Replays" / "Multiplayer"
                            if replay_dir.exists():
                                candidates.append(str(replay_dir))

    else:
        # Linux (Wine)
        wine_base = Path.home() / ".wine/drive_c/users"
        if wine_base.exists():
            for user_dir in wine_base.glob("*"):
                docs = user_dir / "Documents" / "StarCraft II" / "Accounts"
                if docs.exists():
                    for account_dir in docs.glob("*"):
                        if account_dir.is_dir():
                            for sub_dir in account_dir.glob("*"):
                                if sub_dir.is_dir():
                                    replay_dir = sub_dir / "Replays" / "Multiplayer"
                                    if replay_dir.exists():
                                        candidates.append(str(replay_dir))

    return candidates


def validate_player_name(player_name: str, replay_folder: str, max_replays: int = 10) -> tuple:
    """
    Validate that a player name exists in replays.

    Returns (found_count, total_checked) tuple.
    """
    import sc2reader

    folder = Path(replay_folder)
    if not folder.exists():
        return (0, 0)

    replays = sorted(folder.glob("*.SC2Replay"), key=lambda p: p.stat().st_mtime, reverse=True)
    replays = replays[:max_replays]

    found = 0
    checked = 0

    for replay_path in replays:
        try:
            r = sc2reader.load_replay(str(replay_path), load_level=1)
            checked += 1
            for p in r.players:
                if p.name == player_name:
                    found += 1
                    break
        except Exception:
            continue

    return (found, checked)
