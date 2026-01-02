"""Data transformation for API responses."""
from .. import db
from ..config import get_player_name


def get_mmr_history(limit: int = 100) -> dict:
    """Get MMR history for graphing.

    Args:
        limit: Maximum number of games to return

    Returns:
        Dict with player_name and data (list of mmr entries, oldest first)
    """
    replays = db.get_replays(limit=limit)
    data = [
        {
            "date": r["played_at"],
            "mmr": r["player_mmr"],
            "result": r["result"],
            "matchup": r["matchup"],
        }
        for r in reversed(replays)  # Oldest first for graph
        if r.get("player_mmr")
    ]
    return {
        "player_name": get_player_name(),
        "data": data,
    }
