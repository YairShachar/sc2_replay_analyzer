"""
SC2 Replay Analyzer Configuration

Handles loading/saving user config and auto-detection of SC2 paths.
"""
import copy
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

# Game speed factor: SC2 "Faster" speed runs at 1.4x real-time
# sc2reader returns game-time seconds, so we multiply real-time by this factor
GAME_SPEED_FACTOR = 1.4

# Time snapshots for metrics (in game-time seconds)
# These represent when the in-game timer shows 6:00, 8:00, 10:00
SNAPSHOTS = {
    "6m": int(360 * GAME_SPEED_FACTOR),   # 504 game seconds
    "8m": int(480 * GAME_SPEED_FACTOR),   # 672 game seconds
    "10m": int(600 * GAME_SPEED_FACTOR),  # 840 game seconds
}

# Available columns for display
AVAILABLE_COLUMNS = {
    "date": ("Date", 12, "left"),
    "map": ("Map", 14, "left"),
    "opponent": ("Opponent", 16, "left"),
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
    "bases_10m": ("B@10m", 6, "right"),
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

    config = copy.deepcopy(DEFAULT_CONFIG)

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


def set_display_columns(columns: list):
    """Set the list of columns to display and save to config."""
    config = load_config()
    config["display"]["columns"] = columns
    save_config(config)
    clear_config_cache()


def add_display_columns(columns: list) -> list:
    """Add columns to display. Returns list of actually added columns."""
    current = get_display_columns()
    added = []
    for col in columns:
        if col in AVAILABLE_COLUMNS and col not in current:
            current.append(col)
            added.append(col)
    if added:
        set_display_columns(current)
    return added


def remove_display_columns(columns: list) -> list:
    """Remove columns from display. Returns list of actually removed columns."""
    current = get_display_columns()
    removed = []
    for col in columns:
        if col in current:
            current.remove(col)
            removed.append(col)
    if removed:
        set_display_columns(current)
    return removed


def reset_display_columns():
    """Reset columns to defaults."""
    set_display_columns(DEFAULT_CONFIG["display"]["columns"].copy())


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


def find_matching_players(search_term: str, replay_folder: str, max_replays: int = 10) -> tuple:
    """
    Find player names in replays that match the search term.

    Matching is case-insensitive and uses 'contains' logic.

    Returns (matching_names, total_checked) tuple where matching_names is a dict
    mapping exact player names to their occurrence count.
    """
    import sc2reader

    folder = Path(replay_folder)
    if not folder.exists():
        return ({}, 0)

    replays = sorted(folder.glob("*.SC2Replay"), key=lambda p: p.stat().st_mtime, reverse=True)
    replays = replays[:max_replays]

    matches = {}  # player_name -> count
    checked = 0
    search_lower = search_term.lower()

    for replay_path in replays:
        try:
            r = sc2reader.load_replay(str(replay_path), load_level=2)
            checked += 1
            for p in r.players:
                if search_lower in p.name.lower():
                    matches[p.name] = matches.get(p.name, 0) + 1
        except Exception:
            continue

    return (matches, checked)


def validate_player_name(player_name: str, replay_folder: str, max_replays: int = 10) -> tuple:
    """
    Validate that a player name exists in replays (exact match).

    Returns (found_count, total_checked) tuple.
    """
    matches, checked = find_matching_players(player_name, replay_folder, max_replays)

    # Count exact matches (case-insensitive)
    found = 0
    for name, count in matches.items():
        if name.lower() == player_name.lower():
            found += count

    return (found, checked)
