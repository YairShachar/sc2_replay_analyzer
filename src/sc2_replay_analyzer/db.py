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
    opponent_name TEXT,

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
        _migrate_add_column(conn, "opponent_name", "TEXT")


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


def get_streaks(
    streak_type: str,
    min_length: int = 3,
    matchup: Optional[str] = None,
    map_name: Optional[str] = None,
    days: Optional[int] = None,
) -> list:
    """
    Find streaks of consecutive wins or losses.

    Args:
        streak_type: "win" or "loss" - type of streak to find
        min_length: Minimum streak length to include (default 3)
        matchup: Optional matchup filter (e.g., "TvZ")
        map_name: Optional map name filter (partial match)
        days: Optional filter for last N days

    Returns:
        List of replay dicts for all games in qualifying streaks,
        INCLUDING the game that ends each streak.
    """
    # Build query to get all replays ordered chronologically (oldest first)
    query = "SELECT * FROM replays WHERE 1=1"
    params = []

    if matchup:
        query += " AND UPPER(matchup) = UPPER(?)"
        params.append(matchup)

    if map_name:
        query += " AND map_name LIKE ?"
        params.append(f"%{map_name}%")

    if days:
        query += " AND played_at >= datetime('now', ?)"
        params.append(f"-{days} days")

    query += " ORDER BY played_at ASC"

    with get_connection() as conn:
        cursor = conn.execute(query, params)
        all_replays = [dict(row) for row in cursor.fetchall()]

    if not all_replays:
        return []

    # Determine the target result based on streak type
    target_result = "Win" if streak_type.lower() == "win" else "Loss"

    result_replays = []
    current_streak = []

    for replay in all_replays:
        replay_result = (replay.get("result") or "").capitalize()

        if replay_result == target_result:
            # Continue streak
            current_streak.append(replay)
        else:
            # Streak ended - check if it qualifies
            if len(current_streak) >= min_length:
                # Add all games from the streak plus the ending game
                result_replays.extend(current_streak)
                result_replays.append(replay)
            # Start fresh
            current_streak = []

    # Note: We don't include ongoing streaks at the end (no ending game)
    # since user requested streaks "ending with a loss/win"

    # Return in descending order (newest first) for display
    return list(reversed(result_replays))


def expand_results(
    replays: list,
    prev_count: int = 0,
    next_count: int = 0,
) -> list:
    """
    Expand replay results with adjacent games.

    Args:
        replays: Current list of replays (ordered by played_at DESC)
        prev_count: Number of games before the oldest result to add
        next_count: Number of games after the newest result to add

    Returns:
        Expanded list with additional games added
    """
    if not replays:
        return replays

    # Get replay IDs to exclude duplicates
    existing_ids = {r["replay_id"] for r in replays}

    # Get timestamps for boundary queries
    # replays[0] is newest (highest timestamp), replays[-1] is oldest (lowest timestamp)
    newest_timestamp = replays[0]["played_at"]
    oldest_timestamp = replays[-1]["played_at"]

    result = list(replays)  # Copy current results

    # Query for next games (newer than newest)
    if next_count > 0:
        query = "SELECT * FROM replays WHERE played_at > ? ORDER BY played_at ASC LIMIT ?"
        with get_connection() as conn:
            cursor = conn.execute(query, (newest_timestamp, next_count))
            next_games = [dict(row) for row in cursor.fetchall()]
        # Filter out duplicates and prepend (reversed to maintain DESC order)
        next_games = [g for g in next_games if g["replay_id"] not in existing_ids]
        result = list(reversed(next_games)) + result

    # Query for previous games (older than oldest)
    if prev_count > 0:
        query = "SELECT * FROM replays WHERE played_at < ? ORDER BY played_at DESC LIMIT ?"
        with get_connection() as conn:
            cursor = conn.execute(query, (oldest_timestamp, prev_count))
            prev_games = [dict(row) for row in cursor.fetchall()]
        # Filter out duplicates and append (already in DESC order)
        prev_games = [g for g in prev_games if g["replay_id"] not in existing_ids]
        result = result + prev_games

    return result


def get_unique_map_names() -> list:
    """Get list of unique map names from database."""
    query = "SELECT DISTINCT map_name FROM replays WHERE map_name IS NOT NULL ORDER BY map_name"
    with get_connection() as conn:
        cursor = conn.execute(query)
        return [row[0] for row in cursor.fetchall()]
