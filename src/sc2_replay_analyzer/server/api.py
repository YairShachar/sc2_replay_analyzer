"""Data transformation for API responses."""
from .. import db
from ..config import get_player_name


def get_mmr_history(limit: int = 100) -> dict:
    """Get MMR history for graphing.

    Args:
        limit: Maximum number of games to return

    Returns:
        Dict with player_name, data (list of mmr entries, oldest first), and tags
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

    # Get all tags with full details including end_date
    all_tags = db.get_tags()
    tags = []
    for tag in all_tags:
        start_date = tag["tag_date"]
        end_date = tag.get("end_date")

        # Determine tag type
        if end_date is None:
            tag_type = "ongoing"
        elif end_date == start_date:
            tag_type = "single"
        else:
            tag_type = "range"

        tags.append({
            "label": tag["label"],
            "start_date": start_date,
            "end_date": end_date,
            "type": tag_type,
        })

    return {
        "player_name": get_player_name(),
        "data": data,
        "tags": tags,
    }
