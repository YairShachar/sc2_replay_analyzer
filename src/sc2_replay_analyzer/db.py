"""
SC2 Replay Database Layer

SQLite-based storage for parsed replay data.
"""
import sqlite3
from contextlib import contextmanager
from typing import Optional

from .config import get_db_path, ensure_config_dir


SCHEMA = """
CREATE TABLE IF NOT EXISTS replays (
    replay_id TEXT PRIMARY KEY,
    file_path TEXT,
    played_at TEXT,
    map_name TEXT,
    player_race TEXT,
    opponent_race TEXT,
    matchup TEXT,
    result TEXT,
    game_length_sec INTEGER,
    player_mmr INTEGER,
    opponent_mmr INTEGER,
    player_apm INTEGER,
    opponent_apm INTEGER,

    -- Worker metrics
    workers_6m INTEGER,
    workers_8m INTEGER,
    workers_10m INTEGER,

    -- Base metrics
    bases_by_6m INTEGER,
    bases_by_8m INTEGER,
    bases_by_10m INTEGER,
    natural_timing INTEGER,
    third_timing INTEGER,

    -- Army metrics
    army_supply_8m INTEGER,
    army_minerals_8m INTEGER,
    army_gas_8m INTEGER,
    worker_kills_8m INTEGER,
    worker_losses_8m INTEGER,
    first_attack_time INTEGER,

    -- Metadata
    parsed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_played_at ON replays(played_at DESC);
CREATE INDEX IF NOT EXISTS idx_matchup ON replays(matchup);
CREATE INDEX IF NOT EXISTS idx_result ON replays(result);
CREATE INDEX IF NOT EXISTS idx_map_name ON replays(map_name);
"""


def init_db():
    """Initialize the database and create tables if needed."""
    ensure_config_dir()
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        # Migrations: add columns that may be missing from older databases
        _migrate_add_column(conn, "bases_by_6m", "INTEGER")
        _migrate_add_column(conn, "bases_by_8m", "INTEGER")
        _migrate_add_column(conn, "bases_by_10m", "INTEGER")


def _migrate_add_column(conn, column_name: str, column_type: str):
    """Add a column to replays table if it doesn't exist."""
    cursor = conn.execute("PRAGMA table_info(replays)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column_name not in existing_columns:
        conn.execute(f"ALTER TABLE replays ADD COLUMN {column_name} {column_type}")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def replay_exists(replay_id: str) -> bool:
    """Check if a replay is already in the database."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT 1 FROM replays WHERE replay_id = ?",
            (replay_id,)
        )
        return cursor.fetchone() is not None


def insert_replay(data: dict):
    """Insert a parsed replay into the database."""
    columns = list(data.keys())
    placeholders = ", ".join("?" * len(columns))
    column_names = ", ".join(columns)

    with get_connection() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO replays ({column_names}) VALUES ({placeholders})",
            tuple(data.values())
        )


def get_replays(
    matchup: Optional[str] = None,
    result: Optional[str] = None,
    map_name: Optional[str] = None,
    days: Optional[int] = None,
    limit: Optional[int] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    min_workers_8m: Optional[int] = None,
    max_workers_8m: Optional[int] = None,
) -> list:
    """
    Query replays with optional filters.

    Returns list of dictionaries, ordered by played_at descending.
    """
    query = "SELECT * FROM replays WHERE 1=1"
    params = []

    if matchup:
        query += " AND UPPER(matchup) = UPPER(?)"
        params.append(matchup)

    if result:
        query += " AND LOWER(result) = LOWER(?)"
        params.append(result)

    if map_name:
        query += " AND map_name LIKE ?"
        params.append(f"%{map_name}%")

    if days:
        query += " AND played_at >= datetime('now', ?)"
        params.append(f"-{days} days")

    if min_length is not None:
        query += " AND game_length_sec >= ?"
        params.append(min_length)

    if max_length is not None:
        query += " AND game_length_sec <= ?"
        params.append(max_length)

    if min_workers_8m is not None:
        query += " AND workers_8m >= ?"
        params.append(min_workers_8m)

    if max_workers_8m is not None:
        query += " AND workers_8m <= ?"
        params.append(max_workers_8m)

    query += " ORDER BY played_at DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_latest_replay() -> Optional[dict]:
    """Get the most recently played replay."""
    replays = get_replays(limit=1)
    return replays[0] if replays else None


def get_stats(matchup: Optional[str] = None, days: Optional[int] = None) -> dict:
    """
    Get aggregate statistics.

    Returns dict with total games, wins, losses, averages.
    """
    query = """
        SELECT
            COUNT(*) as total_games,
            SUM(CASE WHEN LOWER(result) = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN LOWER(result) = 'loss' THEN 1 ELSE 0 END) as losses,
            AVG(workers_6m) as avg_workers_6m,
            AVG(workers_8m) as avg_workers_8m,
            AVG(workers_10m) as avg_workers_10m,
            AVG(army_supply_8m) as avg_army_supply_8m,
            AVG(game_length_sec) as avg_game_length
        FROM replays
        WHERE 1=1
    """
    params = []

    if matchup:
        query += " AND UPPER(matchup) = UPPER(?)"
        params.append(matchup)

    if days:
        query += " AND played_at >= datetime('now', ?)"
        params.append(f"-{days} days")

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else {}


def get_stats_by_matchup(days: Optional[int] = None) -> list:
    """Get stats grouped by matchup."""
    query = """
        SELECT
            matchup,
            COUNT(*) as total_games,
            SUM(CASE WHEN LOWER(result) = 'win' THEN 1 ELSE 0 END) as wins,
            AVG(workers_8m) as avg_workers_8m
        FROM replays
        WHERE 1=1
    """
    params = []

    if days:
        query += " AND played_at >= datetime('now', ?)"
        params.append(f"-{days} days")

    query += " GROUP BY matchup ORDER BY total_games DESC"

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_replay_count() -> int:
    """Get total number of replays in database."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM replays")
        return cursor.fetchone()[0]
