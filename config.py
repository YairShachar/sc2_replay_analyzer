"""
SC2 Replay Analyzer Configuration

Edit these settings to match your setup.
"""
import os
from pathlib import Path

# Your in-game player name
PLAYER_NAME = "AppleJuice"

# Path to your SC2 replays folder
# Mac default: ~/Library/Application Support/Blizzard/StarCraft II/Accounts/<id>/<id>/Replays/Multiplayer
# Windows default: C:/Users/<name>/Documents/StarCraft II/Accounts/<id>/<id>/Replays/Multiplayer
REPLAY_FOLDER = os.path.expanduser(
    "~/Library/Application Support/Blizzard/StarCraft II/Accounts/1782072/2-S2-1-1509213/Replays/Multiplayer"
)

# Where to store the SQLite database
DB_PATH = os.path.expanduser("~/.sc2analyzer/replays.db")

# Worker benchmarks (games below these trigger warnings)
BENCHMARK_WORKERS_6M = 40
BENCHMARK_WORKERS_8M = 55

# Unit classifications
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

# ============================================================
# TABLE DISPLAY CONFIGURATION
# ============================================================
# Available columns: (header_name, width, justify)
# Customize DISPLAY_COLUMNS to change which columns appear
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

# Columns to display in order (edit this list to customize)
DISPLAY_COLUMNS = [
    "date",
    "map",
    "matchup",
    "result",
    "mmr",
    "apm",
    "workers_8m",
    "army",
    "length",
]


def ensure_db_dir():
    """Create the database directory if it doesn't exist."""
    db_dir = Path(DB_PATH).parent
    db_dir.mkdir(parents=True, exist_ok=True)
