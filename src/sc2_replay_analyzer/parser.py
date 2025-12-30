"""
SC2 Replay Parser

Extracts game data from .SC2Replay files using sc2reader.
"""
import hashlib
from datetime import datetime, timezone

import sc2reader
from sc2reader.events import tracker as tr

from .config import get_player_name, WORKERS, TOWNHALLS, SNAPSHOTS


def sha1(path: str) -> str:
    """Generate SHA1 hash of a file for unique identification."""
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_utc(dt) -> str:
    """Convert datetime to ISO UTC format."""
    if not dt:
        return ""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.astimezone(timezone.utc).isoformat()


def extract_units(replay):
    """Extract unit lifecycle data from replay tracker events."""
    units = {}
    for e in replay.tracker_events:
        if isinstance(e, tr.UnitBornEvent):
            unit = e.unit
            name = getattr(unit, "name", None) or e.unit_type_name
            units[e.unit_id] = {
                "name": name,
                "born": int(e.second),
                "died": None,
                "pid": e.control_pid,
                "supply": getattr(unit, "supply", 0) or 0,
                "minerals": getattr(unit, "minerals", 0) or 0,
                "vespene": getattr(unit, "vespene", 0) or 0,
                "is_army": getattr(unit, "is_army", False),
            }
        elif isinstance(e, tr.UnitDiedEvent):
            if e.unit_id in units:
                units[e.unit_id]["died"] = int(e.second)
    return units


def alive_at(units: dict, pid: int, names: set, t: int) -> int:
    """Count units of specific types alive at time t."""
    return sum(
        1 for u in units.values()
        if u["pid"] == pid
        and u["name"] in names
        and u["born"] <= t
        and (u["died"] is None or u["died"] > t)
    )


def army_supply_at(units: dict, pid: int, t: int) -> int:
    """Calculate total army supply for a player at a given time."""
    return sum(
        u["supply"] for u in units.values()
        if u["pid"] == pid
        and u["is_army"]
        and u["born"] <= t
        and (u["died"] is None or u["died"] > t)
    )


def army_value_at(units: dict, pid: int, t: int) -> tuple:
    """Calculate total army value (minerals, gas) for a player at a given time."""
    minerals = gas = 0
    for u in units.values():
        if (u["pid"] == pid
            and u["is_army"]
            and u["born"] <= t
            and (u["died"] is None or u["died"] > t)):
            minerals += u["minerals"]
            gas += u["vespene"]
    return minerals, gas


def parse_replay(replay_path: str, player_name: str = None) -> dict:
    """
    Parse a single replay file and return extracted data.

    Returns a dictionary with all game metrics, ready for database insertion.
    Returns None if the player is not found in the replay.
    """
    if player_name is None:
        player_name = get_player_name()

    r = sc2reader.load_replay(replay_path, load_level=4)
    replay_id = sha1(replay_path)

    # Find the player
    me = next((p for p in r.players if p.name == player_name), None)
    if me is None:
        return None

    opp = next((p for p in r.players if p.name != player_name), None)
    if opp is None:
        return None

    units = extract_units(r)
    game_length = int(r.length.total_seconds())

    # Build matchup string (e.g., "TvZ")
    race_abbrev = {"Terran": "T", "Zerg": "Z", "Protoss": "P"}
    my_race = race_abbrev.get(me.play_race, "?")
    opp_race = race_abbrev.get(opp.play_race, "?")
    matchup = f"{my_race}v{opp_race}"

    # Extract MMR from init_data (scaled_rating)
    def get_mmr(player):
        if hasattr(player, 'init_data') and player.init_data:
            return player.init_data.get('scaled_rating')
        return None

    player_mmr = get_mmr(me)
    opponent_mmr = get_mmr(opp)

    # Calculate APM (Actions Per Minute) from events
    def get_apm(player, length_sec):
        if length_sec <= 0:
            return None
        events = getattr(player, 'events', [])
        game_minutes = length_sec / 60
        return int(len(events) / game_minutes) if game_minutes > 0 else None

    player_apm = get_apm(me, game_length)
    opponent_apm = get_apm(opp, game_length)

    data = {
        "replay_id": replay_id,
        "file_path": replay_path,
        "played_at": safe_utc(r.date),
        "map_name": r.map_name,
        "player_race": me.play_race,
        "opponent_race": opp.play_race,
        "opponent_name": opp.name,
        "matchup": matchup,
        "result": me.result,
        "game_length_sec": game_length,
        "player_mmr": player_mmr,
        "opponent_mmr": opponent_mmr,
        "player_apm": player_apm,
        "opponent_apm": opponent_apm,

        # Workers at snapshots
        "workers_6m": alive_at(units, me.pid, WORKERS, SNAPSHOTS["6m"]) if game_length >= SNAPSHOTS["6m"] else None,
        "workers_8m": alive_at(units, me.pid, WORKERS, SNAPSHOTS["8m"]) if game_length >= SNAPSHOTS["8m"] else None,
        "workers_10m": alive_at(units, me.pid, WORKERS, SNAPSHOTS["10m"]) if game_length >= SNAPSHOTS["10m"] else None,

        # Bases
        "bases_by_6m": alive_at(units, me.pid, TOWNHALLS, SNAPSHOTS["6m"]) if game_length >= SNAPSHOTS["6m"] else None,
        "bases_by_8m": alive_at(units, me.pid, TOWNHALLS, SNAPSHOTS["8m"]) if game_length >= SNAPSHOTS["8m"] else None,
        "bases_by_10m": alive_at(units, me.pid, TOWNHALLS, SNAPSHOTS["10m"]) if game_length >= SNAPSHOTS["10m"] else None,
    }

    # Base timings
    townhall_times = sorted(
        u["born"] for u in units.values()
        if u["pid"] == me.pid and u["name"] in TOWNHALLS
    )
    data["natural_timing"] = townhall_times[1] if len(townhall_times) > 1 else None
    data["third_timing"] = townhall_times[2] if len(townhall_times) > 2 else None

    # Army at 8m
    if game_length >= SNAPSHOTS["8m"]:
        data["army_supply_8m"] = army_supply_at(units, me.pid, SNAPSHOTS["8m"])
        minerals_8m, gas_8m = army_value_at(units, me.pid, SNAPSHOTS["8m"])
        data["army_minerals_8m"] = minerals_8m
        data["army_gas_8m"] = gas_8m
    else:
        data["army_supply_8m"] = None
        data["army_minerals_8m"] = None
        data["army_gas_8m"] = None

    # Worker kills/losses in first 8 minutes
    kills = losses = 0
    for e in r.tracker_events:
        if isinstance(e, tr.UnitDiedEvent) and e.second <= SNAPSHOTS["8m"]:
            unit_name = e.unit.name if e.unit else None
            if unit_name in WORKERS:
                if e.killer_pid == me.pid:
                    kills += 1
                elif e.killer_pid == opp.pid:
                    losses += 1
    data["worker_kills_8m"] = kills
    data["worker_losses_8m"] = losses

    # First attack timing
    first_attack = next(
        (int(e.second) for e in r.tracker_events
         if isinstance(e, tr.UnitDiedEvent)
         and e.killer_pid == me.pid),
        None
    )
    data["first_attack_time"] = first_attack

    # Metadata
    data["parsed_at"] = datetime.now(timezone.utc).isoformat()

    return data
